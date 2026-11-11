"""Where live info comes from, each source's reply turned into Evidence.

Two sources need no account. The game's own event posts on Roblox are its
patch notes, with the real start date of each update. The community wiki puts
up a page for each new Brainrot within minutes of its update, and keeps an
update log. A web search (Tavily or Brave, with your own API key) is optional
on top of those.

Everything that comes back is untrusted text from the internet. It's cut down
to short plain text here and only ever shown to the model as data.
"""
import email.utils
import html
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Nothing about this PC or its user goes out: a generic name, and only the
# words being searched for.
USER_AGENT = "Mozilla/5.0 (compatible; riddle-helper/1.0)"
HTTP_TIMEOUT = 6.0      # one request; the riddle stops waiting sooner, and a late reply still fills the cache
MAX_BYTES = 3_000_000
OFFICIAL, COMMUNITY, WEB = 0, 1, 2
TIER_NAMES = {OFFICIAL: "official", COMMUNITY: "community wiki", WEB: "web"}
TEXT_LIMIT = 320        # characters of one piece of evidence
RECENT_DAYS = 21        # a wiki page this new can be a new release


@dataclass(frozen=True)
class Evidence:
    """One thing a source said. Dates are kept apart, because a page posted
    today can be about an update from last week.

    Aware datetimes are exact moments. Naive ones are calendar days with no
    time ("November 7th, 2026" on the wiki).
    """
    title: str
    text: str
    source: str
    url: str
    tier: int
    happened: datetime = None   # when the thing itself happens: an update starting, a release
    happened_as: str = "starts"
    ends: datetime = None
    published: datetime = None  # when the page or post about it went up
    published_as: str = "published"
    topics: frozenset = frozenset()
    searched: bool = False      # found by searching for the riddle's words, not read off a feed


class SourceError(Exception):
    """A source that couldn't answer. wait is how many seconds to leave it alone."""

    def __init__(self, reason, wait=30.0):
        super().__init__(reason)
        self.reason, self.wait = reason, wait


# --- fetching ----------------------------------------------------------------

def get_json(url, body=None, headers=None, timeout=HTTP_TIMEOUT):
    """GET url, or POST body as JSON, and decode the JSON reply.

    Every failure is a SourceError whose reason is safe to show: it never
    holds a header, so never an API key.
    """
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json",
        **({"Content-Type": "application/json"} if data is not None else {}), **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise refusal(e) from None
    except urllib.error.URLError as e:
        raise SourceError("timed out" if isinstance(e.reason, TimeoutError) else "couldn't connect") from None
    except TimeoutError:
        raise SourceError("timed out") from None
    except (OSError, http.client.HTTPException, ValueError):
        raise SourceError("couldn't connect") from None
    if len(raw) > MAX_BYTES:
        raise SourceError("sent too much back", 300)
    try:
        return json.loads(raw)
    except ValueError:
        raise SourceError("sent something unreadable", 120) from None


def refusal(error):
    """A SourceError for an HTTP error status, saying how long to back off."""
    status = error.code
    try:
        detail = error.read(4000).decode("utf-8", "replace")
    except (OSError, http.client.HTTPException, ValueError):
        detail = ""
    finally:
        error.close()
    retry = (error.headers or {}).get("Retry-After", "")
    wait = float(retry) if retry.strip().isdigit() else 300.0
    # Brave says 422 for a bad key, with the reason in the body.
    if status in (401, 403) or "TOKEN_INVALID" in detail or "invalid API key" in detail:
        return SourceError("the API key was refused", 900)
    if status == 429 or "RATE_LIMITED" in detail:
        return SourceError("rate limited", min(wait, 3600))
    if status in (432, 433, 434):
        return SourceError("the plan's limit is used up", min(wait, 3600))
    if status >= 500:
        return SourceError(f"server error {status}", 60)
    return SourceError(f"refused the request ({status})", 120)


# --- reading what comes back -------------------------------------------------

CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​-‏‪-‮⁦-⁩]")
URL = re.compile(r"https?://\S+|www\.\S+")
# The model's own answer format, which a page could use to steer the parser.
ANSWER_LIKE = re.compile(r"\banswer\s*:", re.I)


def clean(text, limit=TEXT_LIMIT):
    """Plain text on one line, cut at a word."""
    text = CONTROL.sub(" ", text if isinstance(text, str) else "")
    text = ANSWER_LIKE.sub("answer -", URL.sub("", text))
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-") + "..."
    return text


def parse_time(value):
    """An ISO 8601 or e-mail style timestamp as an aware datetime, or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            moment = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


WRITTEN_DATE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?"
                          r"\s+(\d{4})\b", re.I)
MONTH_ABBR = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def parse_day(text):
    """"November 7th, 2026" as a naive datetime (a calendar day), or None."""
    found = WRITTEN_DATE.search(text or "")
    if not found:
        return None
    try:
        return datetime(int(found[3]), MONTH_ABBR.index(found[1].lower()) + 1, int(found[2]))
    except ValueError:
        return None


def parse_age(text):
    """Brave's "age": a written date, or "3 days ago"."""
    day = parse_day(text)
    if day:
        return day
    found = re.fullmatch(r"\s*(\d+)\s+(minute|hour|day|week)s?\s+ago\s*", text or "", re.I)
    if not found:
        return None
    unit = {"minute": timedelta(minutes=1), "hour": timedelta(hours=1), "day": timedelta(days=1),
            "week": timedelta(weeks=1)}[found[2].lower()]
    return datetime.now(timezone.utc) - int(found[1]) * unit


def host(url):
    try:
        name = urllib.parse.urlsplit(url).hostname or ""
    except ValueError:
        return ""
    return name[4:] if name.startswith("www.") else name


# --- the game's Roblox page --------------------------------------------------

class Roblox:
    """The game's official page on Roblox: its event posts and live numbers."""

    name = "Roblox"
    UNIVERSE, PLACE = 7709344486, 109983668079237

    def __init__(self, events_url="https://apis.roblox.com/virtual-events/v1/universes/{}/virtual-events",
                 games_url="https://games.roblox.com/v1/games"):
        self.events_url, self.games_url = events_url.format(self.UNIVERSE), games_url

    def events(self, now, days=45):
        """Update posts that started in the last few weeks or haven't started yet."""
        since = (now - timedelta(days=days)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = get_json(f"{self.events_url}?{urllib.parse.urlencode({'limit': 25, 'fromUtc': since})}")
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise SourceError("sent something unreadable", 120)
        items = []
        for row in rows:
            if not isinstance(row, dict) or row.get("eventVisibility", "public") != "public":
                continue
            when = row.get("eventTime") if isinstance(row.get("eventTime"), dict) else {}
            start = parse_time(when.get("startUtc"))
            if start is None:
                continue
            title = clean(row.get("displayTitle") or row.get("title"), 80)
            subtitle = clean(row.get("displaySubtitle") or row.get("subtitle"), 80)
            if subtitle and subtitle.lower() != title.lower():
                title = f"{title} ({subtitle})"
            event_id = str(row.get("id", ""))
            items.append(Evidence(
                title=title or "Update", text=clean(row.get("displayDescription") or row.get("description")),
                source="Roblox event post", tier=OFFICIAL,
                url=f"https://www.roblox.com/events/{event_id}" if event_id.isdigit() else "",
                happened=start, ends=parse_time(when.get("endUtc")),
                published=parse_time(row.get("createdUtc")), published_as="posted",
                topics=frozenset({"update", "event"})))
        return items

    def stats(self):
        """How many are playing now, and the game's totals."""
        data = get_json(f"{self.games_url}?universeIds={self.UNIVERSE}")
        rows = data.get("data") if isinstance(data, dict) else None
        if not rows or not isinstance(rows[0], dict):
            raise SourceError("sent something unreadable", 120)
        game = rows[0]
        numbers = {key: game.get(key) for key in ("playing", "visits", "favoritedCount")}
        if not all(isinstance(n, int) for n in numbers.values()):
            raise SourceError("sent something unreadable", 120)
        return [Evidence(
            title="Steal a Brainrot's numbers on Roblox",
            text=(f"{numbers['playing']:,} people playing right now, {numbers['visits']:,} visits in total, "
                  f"{numbers['favoritedCount']:,} favorites."),
            source="Roblox game page", url=f"https://www.roblox.com/games/{self.PLACE}", tier=OFFICIAL,
            published=datetime.now(timezone.utc), published_as="read", topics=frozenset({"stats"}))]


# --- the community wiki ------------------------------------------------------

FILE_LINK = re.compile(r"\[\[\s*(?:File|Image|Category|Media)\s*:[^\]]*\]\]", re.I)
LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]|]*)\]\]")
INNER_TEMPLATE = re.compile(r"\{\{((?:(?!\{\{|\}\}).)*)\}\}", re.S)
RARITIES = {"common", "rare", "epic", "legendary", "mythic", "brainrotgod", "god", "secret", "og", "celestial",
            "admin", "taco", "festive", "limited"}
# Headings that only label the page's layout, and the wiki's blank-page prompts.
BARE_HEADINGS = {"overview", "description", "appearance", "gallery", "references", "obtainment"}
PLACEHOLDER = re.compile(r"(?:add your custom \w+ here|please add custom [\w ]+? here|add some trivia"
                         r"|(?:event|machine) article|to help you with developing go and learn)[.!]?", re.I)
EMPTY_LABEL = re.compile(r"\s*\b\w+(?: \w+)?:\s*$")    # a heading with nothing left under it
KEEP_FIRST = {"bt", "brainrot", "eventlink", "item", "gear", "b", "rarity", "mutation", "trait"}
INFOBOX_FIELDS = ("rarity", "income", "cost", "status", "release", "obtained", "starts", "ends")


def wiki_text(text, title, found=None):
    """Wikitext as plain sentences.

    Templates the wiki uses for names, rarities and money become their words,
    and the rest (stubs, tabs, galleries) go. Infoboxes and update log entries
    go into found, as (template name, {field: value}), since their fields are
    worth more than any sentence.
    """
    text = re.sub(r"<!--.*?-->|<ref[^>]*/>|<ref.*?</ref>|<gallery.*?</gallery>", "", text or "", flags=re.S | re.I)
    text = FILE_LINK.sub("", text)
    # Links first: their "|" would split a template's fields.
    text = LINK.sub(lambda m: m[1], text)
    for _ in range(20):     # innermost templates first, until none are left
        text, n = INNER_TEMPLATE.subn(lambda m: template(m[1], title, found), text)
        if not n:
            break
    text = re.sub(r"<[^>]+>|__[A-Z]+__|'{2,}", "", text)
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "{|!" or line.startswith("|"):
            continue    # table markup
        heading = re.fullmatch(r"=+\s*(.*?)\s*=+", line)
        if heading and heading[1].lower() in BARE_HEADINGS:
            continue
        lines.append(f"{heading[1]}:" if heading else line.lstrip("*#: "))
    return "\n".join(lines)


def template(body, title, found):
    """What one template ({{...}}) stands for in plain text."""
    name, *params = [part.strip() for part in body.split("|")]
    key = re.sub(r"[\s_]+", "", name).lower()
    named, positional = {}, []
    for param in params:
        field, eq, value = param.partition("=")
        if eq:
            named[field.strip().lower()] = value.strip()
        elif param:
            positional.append(param)
    if key.endswith("infobox") or key == "updatelogentry":
        if found is not None:
            found.append((key, named))
        return ""
    if key in ("pagename", "fullpagename"):
        return title
    if key == "$/s":
        return f"${positional[0]}/s" if positional else ""
    if key == "$":
        return f"${positional[0]}" if positional else ""
    if key == "obtainment":
        ways = [w.strip(" .") for w in named.get("obtainment", "").split("#") if w.strip(" .")]
        return f" Obtained: {'; '.join(ways)}." if ways else ""
    if key == "specialcontent":
        return f" {named['reason']}" if named.get("reason") else ""
    for field in ("rarity", "mutation", "name", "trait"):
        if named.get(field):
            return named[field]
    if key in RARITIES:
        return "Brainrot God" if key in ("brainrotgod", "god") else name
    if key in KEEP_FIRST and positional:
        return positional[0]
    return ""


def summary(text, limit=TEXT_LIMIT):
    """The opening sentences of a page, leaving out lists of look-alike names."""
    keep = []
    for line in text.splitlines():
        if line.lower().startswith(("not to be confused", "gallery:", "references:")):
            continue
        keep.append(line)
    text = PLACEHOLDER.sub("", re.sub(r"Not to be confused with[^.]*\.", "", " ".join(keep)))
    return clean(EMPTY_LABEL.sub("", " ".join(text.split())), limit)


def infobox_text(kind, fields):
    """An infobox's fields as a sentence: "Secret brainrot, earns $23.5M/s, costs $3.2B"."""
    get = {k: clean(fields.get(k, ""), 80) for k in INFOBOX_FIELDS}
    if kind.startswith("brainrot"):
        bits = [f"{get['rarity']} brainrot" if get["rarity"] else "brainrot"]
        bits += [f"earns ${get['income'].lstrip('$')}/s"] if get["income"] else []
        bits += [f"costs ${get['cost'].lstrip('$')}"] if get["cost"] else []
        bits += [f"status: {get['status']}"] if get["status"] else []
        bits += [f"released: {get['release']}"] if get["release"] else []
        return ", ".join(bits) + "."
    if kind.startswith("event"):
        bits = [f"starts {get['starts']}"] if get["starts"] else []
        bits += [f"ends {get['ends']}"] if get["ends"] else []
        return ("Event, " + ", ".join(bits) + ".") if bits else "Event."
    return ""


class Wiki:
    """The community wiki at stealabrainrot.fandom.com, read through its API
    (its normal pages turn scripts away)."""

    name = "wiki"
    SOURCE = "Steal a Brainrot wiki"

    def __init__(self, api="https://stealabrainrot.fandom.com/api.php",
                 site="https://stealabrainrot.fandom.com/wiki/"):
        self.api, self.site = api, site

    def query(self, **params):
        query = {"action": "query", "format": "json", "formatversion": 2, **params}
        data = get_json(f"{self.api}?{urllib.parse.urlencode(query)}")
        if not isinstance(data, dict) or not isinstance(data.get("query", {}), dict):
            raise SourceError("sent something unreadable", 120)
        return data.get("query", {})

    def link(self, title):
        return self.site + urllib.parse.quote(title.replace(" ", "_"))

    def recent(self, now, days=RECENT_DAYS):
        """Pages for new Brainrots and events, newest first, and where the
        update log says the game is."""
        found = self.query(list="recentchanges", rctype="new", rcnamespace=0, rclimit=50,
                           rcprop="title|timestamp", titles="Update Log", prop="revisions",
                           rvprop="content", rvslots="main")
        made = {}
        for change in found.get("recentchanges") or []:
            if not isinstance(change, dict):
                continue
            title, when = change.get("title"), parse_time(change.get("timestamp"))
            # Subpages are galleries and update log stubs, not things in the game.
            if isinstance(title, str) and when and "/" not in title and now - when <= timedelta(days=days):
                made.setdefault(title, when)
        items = self.update_log(dict(page_contents(found)).get("Update Log", ""))
        if made:
            pages = self.query(titles="|".join(list(made)[:40]), prop="revisions", rvprop="content", rvslots="main")
            for title, content in page_contents(pages):
                if title in made:
                    item = self.page(title, content, made[title], "wiki page made")
                    if item and item.topics:
                        items.append(item)
        return items

    def search(self, words, limit=3):
        """Pages matching the riddle's words, best match first."""
        found = self.query(generator="search", gsrsearch=words, gsrlimit=limit + 2, prop="revisions",
                           rvprop="content|timestamp", rvslots="main")
        items = []
        for title, content, edited in page_contents(found, with_time=True):
            if title.endswith("/Gallery"):
                continue
            item = self.page(title, content, edited, "wiki page last edited", searched=True)
            if item:
                items.append(item)
            if len(items) >= limit:
                break
        return items

    def page(self, title, content, published, published_as, searched=False):
        boxes = []
        text = wiki_text(content, title, boxes)
        kind, fields = next(((k, f) for k, f in boxes if k.endswith("infobox")), ("", {}))
        topics = frozenset({"brainrot"} if kind.startswith("brainrot") else {"event"} if kind.startswith("event")
                           else set())
        if not searched and not topics:
            return None
        body = summary(text, TEXT_LIMIT - 120)
        text = clean(f"{infobox_text(kind, fields)} {body}".strip())
        if not text:
            return None
        return Evidence(title=clean(title, 100), text=text, source=self.SOURCE, url=self.link(title), tier=COMMUNITY,
                        happened=parse_day(fields.get("release") or fields.get("starts", "")),
                        happened_as="starts" if kind.startswith("event") else "released",
                        published=published, published_as=published_as, topics=topics, searched=searched)

    def update_log(self, content):
        """The current and next update from the wiki's Update Log, and the last
        one before them."""
        parts = re.split(r"^===\s*(.+?)\s*===\s*$", content or "", flags=re.M)
        items = []
        for heading, body in zip(parts[1::2], parts[2::2]):
            which = heading.lower()
            label = ("current update" if "current" in which else "next update" if "future" in which
                     else "last past update" if "past" in which else None)
            if label is None:
                continue
            boxes = []
            wiki_text(body, "Update Log", boxes)
            # Templates are read innermost first, so put them back in update order.
            entries = sorted((fields for key, fields in boxes if key == "updatelogentry"), key=update_number)
            for fields in entries[-1:] if label == "last past update" else entries:
                number, name = clean(fields.get("update"), 40), clean(fields.get("name"), 60)
                when = clean(fields.get("date"), 40) or "TBA"
                title = " ".join(part for part in (number, f'"{name}"' if name else "") if part) or "Update"
                items.append(Evidence(
                    title=title, text=clean(f"The wiki's {label}. Release date: {when}. Main features: "
                                            f"{clean(fields.get('main features'), 200) or 'TBA'}."),
                    source=f"{self.SOURCE} update log", url=self.link("Update Log"), tier=COMMUNITY,
                    happened=parse_day(when), happened_as="released", topics=frozenset({"update"})))
        return items


def update_number(fields):
    found = re.search(r"\d+", fields.get("update", ""))
    return int(found[0]) if found else 0


def page_contents(found, with_time=False):
    """(title, wikitext) for each page in a query's reply, in search order."""
    pages = found.get("pages") or []
    if isinstance(pages, dict):
        pages = list(pages.values())
    pages = sorted((p for p in pages if isinstance(p, dict)), key=lambda p: p.get("index", 0))
    for page in pages:
        revisions = page.get("revisions") or [{}]
        revision = revisions[0] if isinstance(revisions[0], dict) else {}
        slot = (revision.get("slots") or {}).get("main") or {}
        content = slot.get("content", revision.get("content", ""))
        title = page.get("title")
        if isinstance(title, str) and isinstance(content, str):
            yield (title, content, parse_time(revision.get("timestamp"))) if with_time else (title, content)


# --- web search (optional, with your own key) --------------------------------

def untag(text):
    """Snippets can carry HTML (<strong> around matches, &amp;)."""
    return html.unescape(re.sub(r"<[^>]+>", "", text)) if isinstance(text, str) else ""


def web_item(title, text, url, published):
    url = url if isinstance(url, str) and url.startswith(("https://", "http://")) else ""
    return Evidence(title=clean(untag(title), 100), text=clean(untag(text)), source=host(url) or "web", url=url,
                    tier=WEB, published=published, searched=True)


class Tavily:
    """Tavily's search API, made for feeding search results to a model. Its free
    plan has 1,000 searches a month: https://tavily.com"""

    name = "Tavily"
    RANGES = {"day": "day", "week": "week", "month": "month"}

    def __init__(self, url="https://api.tavily.com/search"):
        self.url = url

    def search(self, query, key, fresh=None, limit=5):
        body = {"query": query, "max_results": limit, "search_depth": "basic", "topic": "general",
                "include_published_date": True, "include_answer": False}
        if fresh in self.RANGES:
            body["time_range"] = self.RANGES[fresh]
        data = get_json(self.url, body=body, headers={"Authorization": f"Bearer {key}"})
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            raise SourceError("sent something unreadable", 120)
        return [web_item(r.get("title"), r.get("content"), r.get("url"), parse_time(r.get("published_date")))
                for r in results if isinstance(r, dict)]


class Brave:
    """Brave's independent search index: https://brave.com/search/api"""

    name = "Brave"
    FRESHNESS = {"day": "pd", "week": "pw", "month": "pm"}

    def __init__(self, url="https://api.search.brave.com/res/v1/web/search"):
        self.url = url

    def search(self, query, key, fresh=None, limit=5):
        params = {"q": query, "count": limit, "safesearch": "moderate", "text_decorations": "false"}
        if fresh in self.FRESHNESS:
            params["freshness"] = self.FRESHNESS[fresh]
        data = get_json(f"{self.url}?{urllib.parse.urlencode(params)}", headers={"X-Subscription-Token": key})
        if not isinstance(data, dict):
            raise SourceError("sent something unreadable", 120)
        results = (data.get("web") or {}).get("results") or []     # no "web" at all when nothing matched
        return [web_item(r.get("title"), r.get("description"), r.get("url"),
                         parse_time(r.get("page_age")) or parse_age(r.get("age")))
                for r in results if isinstance(r, dict)]


WEB_SEARCHES = {"tavily": Tavily, "brave": Brave}

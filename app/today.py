"""Today's date and time, worked out on this PC instead of asked of the model.

A model's idea of "now" is wherever its training stopped. So riddles that are
only about the date ("what year is it", "what day of the week is tomorrow",
"how many days until christmas") are answered here outright, and riddles that
depend on it some other way get today's date written into their prompt.

Everything uses this PC's own clock and time zone, the same one "and the day
today" uses.
"""
import re
from datetime import date, datetime, timedelta

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def local_now():
    """Now, in this PC's time zone."""
    return datetime.now().astimezone()


# --- writing dates down ----------------------------------------------------
# Names are spelled out here rather than with strftime, which follows the
# Windows language and would hand the model "trečiadienis".

def long_date(day):
    """"Wednesday, November 11, 2026"."""
    return f"{WEEKDAYS[day.weekday()]}, {MONTHS[day.month - 1]} {day.day}, {day.year}"


def short_date(day, today=None):
    """"Nov 7", with the year when it isn't this one."""
    text = f"{MONTHS[day.month - 1][:3]} {day.day}"
    return text if today is not None and day.year == today.year else f"{text}, {day.year}"


def clock_time(moment):
    return f"{moment.hour % 12 or 12}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'}"


def relative(day, today):
    """"today", "yesterday", "3 days ago", "in 2 days"."""
    days = (day - today).days
    if -1 <= days <= 1:
        return ("yesterday", "today", "tomorrow")[days + 1]
    return f"{-days} days ago" if days < 0 else f"in {days} days"


def utc_offset(moment):
    offset = moment.utcoffset() or timedelta(0)
    minutes = abs(int(offset.total_seconds())) // 60
    return f"UTC{'-' if offset < timedelta(0) else '+'}{minutes // 60:02d}:{minutes % 60:02d}"


def season(day, south=False):
    """The season by months: December to February is winter in the north."""
    names = ("winter", "spring", "summer", "autumn")
    return names[(day.month % 12 // 3 + (2 if south else 0)) % 4]


def describe(now, with_season=False):
    """Today's date for a prompt. Yesterday and tomorrow are spelled out too,
    since a small model gets date arithmetic wrong."""
    today = now.date()
    text = (f"Today is {long_date(today)}, and it's {clock_time(now)} ({utc_offset(now)}) on this PC's clock. "
            f"Yesterday was {long_date(today - timedelta(days=1))}, and tomorrow is "
            f"{long_date(today + timedelta(days=1))}.")
    if with_season:
        text += (f" It's {season(today)} in the northern hemisphere and {season(today, south=True)} "
                 f"in the southern.")
    return text


# --- answering date questions outright ---------------------------------------

def words(text):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower().replace("'", "").replace("’", "")).split())


# Words a question about the date can have besides what it asks for. Any
# other word means it's about something else ("what year did sab release").
FILLER = set("""what whats which is it its was will be the a an current currently right now today todays we are
in on of this at moment tell me say please exactly gonna""".split())
# What the question wants. Plain "day" isn't here: "what day is it" could
# want Wednesday or the 11th, so the model gets it with the date in front of it.
TARGETS = [(re.compile(r"\bday of (?:the )?week\b|\bweek ?day\b"), "weekday"),
           (re.compile(r"\bday of (?:the )?month\b|\bnumber day\b|\bday number\b"), "monthday"),
           (re.compile(r"\bmonth\b"), "month"),
           (re.compile(r"\byear\b"), "year")]
OFFSETS = [(re.compile(r"\b(?:the )?day after tomorrow\b"), "days", 2),
           (re.compile(r"\b(?:the )?day before yesterday\b"), "days", -2),
           (re.compile(r"\btomorrows?\b"), "days", 1),
           (re.compile(r"\byesterdays?\b"), "days", -1),
           (re.compile(r"\bnext week\b"), "days", 7),
           (re.compile(r"\blast week\b"), "days", -7),
           (re.compile(r"\bnext month\b"), "months", 1),
           (re.compile(r"\blast month\b"), "months", -1),
           (re.compile(r"\bnext year\b"), "years", 1),
           (re.compile(r"\blast year\b"), "years", -1)]
DAYS_UNTIL = re.compile(r"^(?:how many|number of) days (?:are )?(?:there )?(?:left )?(?:is it )?"
                        r"(?P<way>until|till|til|before|to|since|after|from) (?P<what>.+)$"
                        r"|^how long (?:is it )?(?P<way2>until|till|til|before) (?P<what2>.+)$")
DAYS_LEFT = re.compile(r"^(?:how many|number of) days (?:are )?(?:there )?(?:left|remaining) in (?:the |this )?"
                       r"(?P<what>year|month|week)$")
NAMED_DAYS = {"christmas": (12, 25), "christmas day": (12, 25), "xmas": (12, 25), "christmas eve": (12, 24),
              "halloween": (10, 31), "new year": (1, 1), "new years": (1, 1), "new years day": (1, 1),
              "the new year": (1, 1), "new years eve": (12, 31), "valentines": (2, 14), "valentines day": (2, 14),
              "april fools": (4, 1), "april fools day": (4, 1), "st patricks day": (3, 17),
              "independence day": (7, 4), "the fourth of july": (7, 4), "fourth of july": (7, 4),
              "4th of july": (7, 4), "the 4th of july": (7, 4)}
ORDINAL = r"(\d{1,2})(?:st|nd|rd|th)?"
MONTH_NAME = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"


def shift_months(day, months):
    total = day.year * 12 + day.month - 1 + months
    return date(total // 12, total % 12 + 1, 1)


def answer(question, now):
    """The answer to a question that's only about the date, or None.

    Only questions with one sensible answer are answered: the year, the month,
    the day of the week, the day of the month, and days until or since a date.
    """
    text = words(question)
    today = now.date()
    days = days_between(text, today)
    if days is not None:
        return str(days)
    unit, amount = None, 0
    for pattern, kind, n in OFFSETS:
        if pattern.search(text):
            text, unit, amount = pattern.sub(" ", text, count=1), kind, n
            break
    target = None
    for pattern, kind in TARGETS:
        if pattern.search(text):
            text, target = pattern.sub(" ", text, count=1), kind
            break
    # "what is next month" asks for the month itself.
    if target is None and unit in ("months", "years"):
        target = unit[:-1]
    if target is None or not set(text.split()) <= FILLER:
        return None
    if unit == "days":
        if target in ("month", "year") and abs(amount) > 1:
            return None     # "what month is it next week" is a question about the calendar
        day = today + timedelta(days=amount)
    elif unit in ("months", "years"):
        if target in ("weekday", "monthday"):
            return None
        day = shift_months(today, amount * (12 if unit == "years" else 1))
    else:
        day = today
    return {"weekday": WEEKDAYS[day.weekday()], "monthday": str(day.day),
            "month": MONTHS[day.month - 1], "year": str(day.year)}[target]


def days_between(text, today):
    """Days until or since a date ("how many days until christmas"), or None."""
    left = DAYS_LEFT.match(text)
    if left:
        what = left["what"]
        if what == "year":
            return (date(today.year, 12, 31) - today).days
        if what == "month":
            return (shift_months(today, 1) - timedelta(days=1) - today).days
        return 6 - today.weekday()
    match = DAYS_UNTIL.match(text)
    if not match:
        return None
    way, what = (match["way"], match["what"]) if match["way"] else (match["way2"], match["what2"])
    since = way in ("since", "after", "from")
    target = when_is(what.strip(), today, since)
    if target is None:
        return None
    days = (today - target).days if since else (target - today).days
    return days if days >= 0 else None


def when_is(what, today, past):
    """The date a phrase names, the next one from today (or the last one, if
    past). None if it isn't a date this understands."""
    what = re.sub(r" (?:this year|is it|is)$", "", what)
    year = None
    found = re.fullmatch(r"(.*[a-z].*?),? (\d{4})", what)
    if found:
        what, year = found[1], int(found[2])
    month_day = None
    if what in NAMED_DAYS:
        month_day = NAMED_DAYS[what]
    elif what in ("thanksgiving", "thanksgiving day"):
        return around(today, past, year, thanksgiving)
    elif what in ("the weekend", "weekend", "saturday", "sunday") or what in (d.lower() for d in WEEKDAYS):
        name = "saturday" if "weekend" in what else what
        target = [d.lower() for d in WEEKDAYS].index(name)
        step = (target - today.weekday()) % 7
        return today - timedelta(days=(today.weekday() - target) % 7) if past else today + timedelta(days=step)
    else:
        found = (re.fullmatch(rf"(?:the )?{ORDINAL} (?:of )?{MONTH_NAME}", what)
                 or re.fullmatch(rf"{MONTH_NAME} (?:the )?{ORDINAL}", what))
        if not found:
            return None
        a, b = found[1], found[2]
        number, month = (int(a), b) if a.isdigit() else (int(b), a)
        month = [name[:3].lower() for name in MONTHS].index(month[:3]) + 1
        month_day = (month, number)
    return around(today, past, year, lambda y: date(y, *month_day))


def around(today, past, year, make):
    """make(year) for the given year, or the nearest one on the right side of today."""
    try:
        if year is not None:
            return make(year)
        day = make(today.year)
        if past and day > today:
            day = make(today.year - 1)
        elif not past and day < today:
            day = make(today.year + 1)
        return day
    except ValueError:      # February 30th
        return None


def thanksgiving(year):
    """The fourth Thursday of November, as in the US."""
    first = date(year, 11, 1)
    return first + timedelta(days=(3 - first.weekday()) % 7 + 21)

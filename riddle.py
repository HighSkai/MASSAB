"""Read riddles off the overlay and solve them with a local model.

Riddles are mostly trivia about the game, shown as one long overlay message
that shrinks and wraps onto two rows:

    month and year the first fuse machine in
                 sab released

The code reader can't use those: its crop cuts through both rows, and it treats
sentences as hints. So this module finds rows on its own, tracks whole messages,
and answers them with llama-server, adding whichever lines of data/sab_facts.md
match the riddle. The model wouldn't otherwise know facts about the game.
"""
import http.client
import json
import math
import os
import re
import subprocess
import threading
import time
from collections import Counter
from datetime import date

import cv2
import numpy as np
from rapidfuzz import fuzz

from codereader import WORK_H, Read, dim_gain, has_lower, is_hint, normalize, similarity, to_work_scale, white_mask
from setup_ai import APP_DIR, DEFAULT_MODEL, LLAMA_SERVER, model_path

# Where overlay rows can be, as fractions of the frame (x0, y0, x1, y1). It stops
# above the Codes menu, whose white centered text would otherwise pass for a row.
BAND = (0.02, 0.07, 0.98, 0.36)
# A row's middle is this close to the screen's (fraction of width). The text is
# what's centered, with the icon hanging off to the left of it.
CENTER_TOLERANCE = 0.03
ICON_MARGIN = 0.005
GLYPH_MIN_H, GLYPH_MAX_H = 8, 64    # tall enough for videos that zoom in 1.7x
ROW_MIN_LETTERS = 4
# Two letters are neighbors if they're side by side and share this much of the
# shorter one's height. A descender and the ascender below it barely overlap,
# so wrapped rows stay apart, while a "d" and an "n" overlap fully.
SHARED_HEIGHT = 0.5
LETTER_HEIGHTS = 1.7    # the tallest letter of a row against the shortest; a sign is far taller
LOOK_BACK = 3  # letters at the end of a chain to try, in case the last is a speck
# Pixels at WORK_H between the middles of two rows of one wrapped message. They
# measure ~24 apart, while separate overlay lines are ~52 apart.
WRAP_PITCH = 36


def neighbors(a, b):
    """Could b, further right, be the next letter after a?"""
    gap = b[0] - (a[0] + a[2])
    shared = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    similar = max(a[3], b[3]) <= LETTER_HEIGHTS * min(a[3], b[3])
    return similar and gap <= max(a[3], b[3]) and shared >= SHARED_HEIGHT * min(a[3], b[3])


def chain_letters(letters):
    """Group letter boxes into lines of text, left to right."""
    lines, open_lines = [], []
    for box in sorted(letters):
        # Lines that ended well to the left can't be continued.
        open_lines = [line for line in open_lines
                      if box[0] - max(b[0] + b[2] for b in line[-LOOK_BACK:]) <= GLYPH_MAX_H]
        line = next((line for line in open_lines if any(neighbors(b, box) for b in line[-LOOK_BACK:])), None)
        if line is None:
            line = []
            lines.append(line)
            open_lines.append(line)
        line.append(box)
    return lines


def find_rows(frame):
    """Find centered white text rows in a WORK_H frame: [(x0, y0, x1, y1, n_words)] top to bottom."""
    fh, fw = frame.shape[:2]
    bx, by = int(BAND[0] * fw), int(BAND[1] * fh)
    band = frame[by:int(BAND[3] * fh), bx:int(BAND[2] * fw)]
    _, _, stats, _ = cv2.connectedComponentsWithStats(white_mask(band))
    letters = [(int(x), int(y), int(w), int(h)) for x, y, w, h, area in stats[1:]
               if GLYPH_MIN_H <= h <= GLYPH_MAX_H and w <= 2 * GLYPH_MAX_H and area >= 6]

    rows = []
    for line in chain_letters(letters):
        run = centered(line, fw / 2 - bx, fw)
        if len(run) < ROW_MIN_LETTERS:
            continue
        height = float(np.median([b[3] for b in run]))
        words, edge = 1, run[0][0] + run[0][2]
        for x, _, w, _ in run[1:]:
            words += x - edge > 0.37 * height
            edge = max(edge, x + w)
        rows.append((bx + run[0][0], by + min(b[1] for b in run), bx + edge,
                     by + max(b[1] + b[3] for b in run), words))
    return sorted(rows, key=lambda row: row[1])


def centered(line, center, fw):
    """A line of letters without any icon bits, or [] if it isn't on the screen's center."""
    end = max(b[0] + b[2] for b in line)
    # The text is centered, so it starts as far left of center as it ends right
    # of it. White bits further left than that are the icon.
    limit = 2 * center - end - ICON_MARGIN * fw
    line = [b for b in line if b[0] + b[2] / 2 >= limit]
    if line and abs((line[0][0] + end) / 2 - center) <= CENTER_TOLERANCE * fw:
        return line
    return []


def read_rows(ocr, frame, boxes=None):
    """OCR every overlay message in a frame: [(text, score, n_words, y)] top to bottom.

    Rows are found at WORK_H but read from the full-size frame, since small
    wrapped text loses a lot when it's scaled down. Given a list, boxes also
    gets each row's (x0, y0, x1, y1, text) in frame pixels, for drawing.
    """
    work = to_work_scale(frame)
    fh, fw = work.shape[:2]
    gain = dim_gain(cv2.cvtColor(work[int(BAND[1] * fh):int(BAND[3] * fh)], cv2.COLOR_BGR2HSV))
    if gain != 1.0:
        work = cv2.convertScaleAbs(work, alpha=gain)
    scale = frame.shape[0] / WORK_H

    messages = []
    last_middle = None
    for x0, y0, x1, y1, words in find_rows(work):
        pad = max(3, (y1 - y0) // 5)
        crop = frame[int(max(0, y0 - pad) * scale):int((y1 + pad) * scale),
                     int(max(0, x0 - pad) * scale):int((x1 + pad) * scale)]
        if gain != 1.0:
            crop = cv2.convertScaleAbs(crop, alpha=gain)
        img = cv2.copyMakeBorder(crop, 6, 6, 10, 10, cv2.BORDER_REPLICATE)
        (text, score), = ocr.text_recognizer([img])[0]
        text, score, middle = text.strip(), float(score), (y0 + y1) // 2
        if not text:
            continue
        if boxes is not None:
            boxes.append((int(x0 * scale), int(y0 * scale), int(x1 * scale), int(y1 * scale), text))
        if last_middle is not None and middle - last_middle <= WRAP_PITCH:
            first, first_score, first_words, first_y = messages[-1]
            messages[-1] = (f"{first} {text}", min(score, first_score), first_words + words, first_y)
        else:
            messages.append((text, score, words, middle))
        last_middle = middle
    return messages


# --- tracking messages across frames -----------------------------------------

RIDDLE_MIN_WORDS, RIDDLE_MIN_LETTERS = 3, 6
# A riddle is one long message, or arrives a few words at a time like a code. A
# message this long is the whole riddle: anything after it is chatter, and
# letting it join could replace a right answer with a wrong one.
WHOLE_RIDDLE_WORDS = 5
RIDDLE_MAX_WORDS = 20
SENTENCE_MIN_LETTERS = 20
SAME_PLACE = 20         # pixels at WORK_H a long message can drift between frames
# Hints and code intros are short ("it contains no numbers"). A longer line that
# uses their words can be a riddle ("which update number added the divine fuse").
SHORT_LINE_WORDS = 5
SAME_TEXT = 80          # similarity of two reads of one message
RIDDLE_WAIT = 8.0       # a riddle can start this long after its intro was last seen
INTRO_GONE = 3.0        # an intro back after this long is a new one, not the same line
INTRO_MIN_LETTERS = 6   # shorter intros are too easy to find inside other lines
FRAGMENT_MIN_LETTERS = 4    # and shorter lines are too easy to find inside an intro
JOIN_GAP = 2.0          # a message this soon after the last one continues the riddle
LONGER_BY = 3           # letters a better read must add to count as an update
# The word that makes a line a riddle intro: "here is the riddle...", "riddle
# time", "next question", "trivia!". OCR swaps the thin letters of "riddle"
# (r1ddle, riddie), but the R has to be there or "middle" would count.
# "question" alone is too common in chat, so it needs an intro's wording.
RIDDLE_WORD = re.compile(r"r[il1][do0]{2}[li1][e3]s?|trivia|quiz|puzzle|brain\s*teaser"
                         r"|(?:the|next|new|this|your)\s*question(?!s)|question\s*(?:is\b|:)", re.I)
# What can sit between that word and a riddle on the same line ("riddle is: ...").
INTRO_JOINER = re.compile(r"^[\W_]*(?:(?:is|are|for|of|time|today)\b[\W_]*)*", re.I)
# Lines between an intro and its riddle: a countdown, or hurrying the chat along.
FILLER = re.compile(r"\d|(?:GET)?READY|GOODLUCK|HURRY(?:UP)?|(?:GO)+|OK|OKAY|LETSGO")
# Sammy often says "code" and means a riddle: "the code is the rarity of dragon
# cannelloni and 67". Or he names the prize: "this is for 100 dragons". Either
# may lead to a riddle or to a plain code, so only a sentence after one counts.
SOFT_INTRO = re.compile(r"codes?|this\s*(?:one\s*)?(?:is\s*|'?s\s*)?for\b|\bfor\s*\d+\s*\w+|\bprize|\breward"
                        r"|^\W*\d+\s*[a-z]+s\W*$", re.I)    # the last one is a bare prize: "5 skibidis"
QUESTION_START = re.compile(r"\s*(?:what|which|who|when|where|how|the name|name)\b", re.I)
# Giving the answer away afterward: "the answer was GRIFFIN10", "it was polaroidini23".
REVEAL = re.compile(r"(?:answer|code|^\W*it)\s*was\b", re.I)


def over_already(text, match):
    """Talk about one that's finished: "that was a bad riddle", "the code was X"."""
    return "was" in text[:match.start()].lower() or text[match.end():].lstrip(" .:-").lower().startswith("was")


def after_intro(text, match):
    return INTRO_JOINER.sub("", text[match.end():], count=1).strip()


def riddle_intro(text):
    """What comes after the riddle word in an intro line, or None if this isn't
    one. A plain intro gives "", and a riddle on the same line gives that riddle."""
    match = RIDDLE_WORD.search(text)
    if not match or over_already(text, match):
        return None
    rest = after_intro(text, match)
    words = len(rest.split())
    if words < RIDDLE_MIN_WORDS or not_riddle_text(rest, words):
        return ""       # "riddle coming up", "riddle for the code is"
    return rest


def soft_intro(text):
    """Like riddle_intro, for lines that only might lead to a riddle."""
    match = SOFT_INTRO.search(text)
    if not match or over_already(text, match):
        return None
    rest = after_intro(text, match)
    return rest if looks_like_riddle(rest, len(rest.split())) else ""


def looks_like_riddle(text, n_words):
    """A sentence or a question, not the words of a code ("SAB IS AMAZING")."""
    if not_riddle_text(text, n_words):
        return False
    # Commas hide gaps from the image's count, and OCR can drop spaces from its
    # own. Stray letters inflate both, so a sentence needs enough text as well.
    n_words = max(n_words, len(text.split()))
    if n_words >= WHOLE_RIDDLE_WORDS and len(normalize(text)) >= SENTENCE_MIN_LETTERS and has_lower(text):
        return True
    asks = text.rstrip().endswith("?") or QUESTION_START.match(text)
    return n_words >= RIDDLE_MIN_WORDS and bool(asks)


def not_riddle_text(text, n_words):
    """Filler, or an intro or hint belonging to a code."""
    read = Read(text, 1.0, n_words)
    if not read.text or FILLER.fullmatch(read.text) or REVEAL.search(text):
        return True
    return n_words <= SHORT_LINE_WORDS and (read.intro or is_hint(read.text, n_words >= 2))


class Part:
    """One overlay message of a riddle, over every frame it's been read in."""

    def __init__(self, text, n_words, y, t, stamp):
        self.reads = Counter({text: 1})
        self.agreed = 1         # reads that match another, not just its place
        self.n_words = n_words
        self.y = y
        self.first_stamp = stamp
        self.last_seen = t
        self.confirmed = False

    @property
    def text(self):
        """The longest reading seen twice, or the most common. A message can be
        read short while it's fading in, never long."""
        twice = [text for text, n in self.reads.items() if n >= 2]
        if twice:
            return max(twice, key=lambda text: (len(normalize(text)), self.reads[text]))
        return self.reads.most_common(1)[0][0]

    def matches(self, text):
        return any(similarity(normalize(text), normalize(known)) >= SAME_TEXT for known in self.reads)


class RiddleTracker:
    """Turns per-frame messages into riddles.

    Nothing counts until an intro arms it, the same way a code needs "code
    is...". Without that, everything anyone says gets solved. A riddle intro
    makes every line after it part of the riddle. A soft intro ("the code is...")
    only lets a sentence through, since a plain code can follow one too. A
    riddle is reported as soon as two frames agree on it, and again as more
    arrives so the answer can be replaced.

    on_riddle gets (text, stamp), stamp being when the newest part was first on
    screen. With riddle_intros off, only soft intros count: code mode wants
    riddles posing as codes, not ones announced as riddles.
    """

    def __init__(self, on_riddle, riddle_intros=True):
        self.on_riddle = on_riddle
        self.riddle_intros = riddle_intros
        self.parts = []
        self.sent = ""
        self.intro = ""         # the current intro line, normalized
        self.intro_seen = None
        self.sure = False       # the intro said riddle, so short lines count too
        self.older = set()      # lines that were above the intro, normalized

    def claimed(self, t):
        """Is a riddle on screen or sure to come, so that no line is a code's?
        One bad read isn't enough to go on: that would lose real codes."""
        confirmed = [p for p in self.parts if p.confirmed]
        if confirmed:
            return t - max(p.last_seen for p in confirmed) <= JOIN_GAP
        return self.sure and self.armed(t)

    def armed(self, t):
        """Could a new message at time t be part of a riddle?"""
        # Only confirmed parts count: one misread mustn't cut the wait short.
        confirmed = [p for p in self.parts if p.confirmed]
        if confirmed:
            return not self._finished(confirmed) and t - max(p.last_seen for p in confirmed) <= JOIN_GAP
        return self.intro_seen is not None and t - self.intro_seen <= RIDDLE_WAIT

    @staticmethod
    def _finished(confirmed):
        whole = any(p.n_words >= WHOLE_RIDDLE_WORDS or p.text.rstrip().endswith("?") for p in confirmed)
        return whole or sum(p.n_words for p in confirmed) >= RIDDLE_MAX_WORDS

    def feed(self, t, messages, stamp=None):
        stamp = t if stamp is None else stamp
        # Lines are added at the bottom, so anything above an intro came before
        # it and can't be its riddle, even once the intro has been misread.
        intro_at = max((i for i, m in enumerate(messages) if self._intro(m[0])[0] is not None), default=0)
        for text, score, n_words, y in messages[intro_at:]:
            self._add(text, n_words, y, t, stamp)
        self.older.update(normalize(m[0]) for m in messages[:intro_at])
        confirmed = [p for p in self.parts if p.confirmed or p.agreed >= 2]
        for part in confirmed:
            part.confirmed = True
        riddle = " ".join(p.text for p in confirmed)
        enough = (sum(p.n_words for p in confirmed) >= RIDDLE_MIN_WORDS
                  and len(normalize(riddle)) >= RIDDLE_MIN_LETTERS)
        if enough and self._changed(riddle):
            self.sent = riddle
            self.on_riddle(riddle, max(p.first_stamp for p in confirmed))

    def _intro(self, text):
        """(what follows the intro, whether it's a sure one), or (None, False)."""
        rest = riddle_intro(text) if self.riddle_intros else None
        if rest is not None:
            return rest, True
        return soft_intro(text), False

    def _add(self, text, n_words, y, t, stamp):
        rest, sure = self._intro(text)
        if rest is not None:
            self._saw_intro(text, sure, t)
            if not rest:
                return
            text, n_words = rest, len(rest.split())
        elif self._bad_read_of_intro(text):
            return
        if any(similarity(normalize(text), line) >= SAME_TEXT for line in self.older):
            return
        known = self._part_for(text, n_words, y, t)
        if known:
            known.agreed += known.matches(text)
            known.reads[text] += 1
            known.last_seen = t
            known.y = y
        elif self.armed(t) and self._fits(text, n_words):
            self.parts.append(Part(text, n_words, y, t, stamp))

    def _part_for(self, text, n_words, y, t):
        """The part this is another read of. A long message misread into
        something unrecognizable is still sitting in the same place."""
        known = next((p for p in self.parts if p.matches(text)), None)
        if known or n_words < WHOLE_RIDDLE_WORDS:
            return known
        return next((p for p in self.parts if p.n_words >= WHOLE_RIDDLE_WORDS and p.last_seen < t
                     and t - p.last_seen <= JOIN_GAP and abs(p.y - y) <= SAME_PLACE), None)

    def _bad_read_of_intro(self, text):
        """"this isfor100 dragohsBee" hides the words that mark an intro, a sign
        next to it can add more, and a video zooming past it leaves just "ddle".
        So look for one inside the other."""
        letters = normalize(text)
        return (len(self.intro) >= INTRO_MIN_LETTERS and len(letters) >= FRAGMENT_MIN_LETTERS
                and fuzz.partial_ratio(self.intro, letters) >= SAME_TEXT)

    def _fits(self, text, n_words):
        return not not_riddle_text(text, n_words) if self.sure else looks_like_riddle(text, n_words)

    def _saw_intro(self, text, sure, t):
        """A new intro starts a new riddle. The same one still on screen doesn't,
        and a soft one can't take over from "the riddle is..."."""
        if self.sure and not sure and self.armed(t):
            return
        same = (self.intro_seen is not None and t - self.intro_seen <= INTRO_GONE
                and similarity(normalize(text), self.intro) >= SAME_TEXT)
        if not same:
            self.parts = []
            self.sent = ""
            self.older = set()
            self.sure = False
        self.sure = self.sure or sure
        self.intro = normalize(text)
        self.intro_seen = t

    def _changed(self, riddle):
        if not self.sent:
            return True
        grown = len(normalize(riddle)) - len(normalize(self.sent))
        return grown >= LONGER_BY or similarity(normalize(riddle), normalize(self.sent)) < SAME_TEXT


# --- the facts file ----------------------------------------------------------

FACTS_PATH = os.path.join(APP_DIR, "data", "sab_facts.md")
SYSTEM_PROMPT_PATH = os.path.join(APP_DIR, "prompts", "riddle_system.txt")
FACTS_LIMIT = 6
FACT_MIN_COVERAGE = 0.6  # share of a riddle's words the facts must have, or the answer is a guess
FUZZY_WORD = 85          # how close a word must be to match; OCR drops and swaps letters
GLUED_MIN_LETTERS = 6    # shorter words aren't worth trying to split
STRAY_APOSTROPHE = re.compile(r"(?<=[a-z])'(?=[a-z]{2,})", re.I)
STOPWORDS = set("""a about an and animal are as at be been but by came can come creature did do does for from game
get gets got had has have how i in into is it its kind me month my no not of on or out sab sort steal brainrot
that the their this to type was were what when where which who why will with year you your""".split())
SOURCE_NOTE = re.compile(r"\s*\[source:[^\]]*\]", re.I)
# Everything from this heading on is a conflict between sources, not a fact.
UNREVIEWED = "## needs review"


def words_of(text):
    return {w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in STOPWORDS}


class Facts:
    """The fact sheet, one fact per line. Lines are ranked against a riddle by
    the words they share, with rare words counting for more."""

    def __init__(self, path=FACTS_PATH):
        self.lines = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.lower().startswith(UNREVIEWED):
                        break
                    if line.strip() and not line.startswith("#"):
                        self.lines.append(SOURCE_NOTE.sub("", line.strip().lstrip("-* ")))
        self.words = [words_of(line) for line in self.lines]
        counts = Counter(w for words in self.words for w in words)
        self.weight = {w: 1 + math.log(max(1, len(self.lines)) / n) for w, n in counts.items()}
        self.vocabulary = {w for line in self.lines for w in re.findall(r"[a-z]+", line.lower()) if len(w) > 1 or w == "a"}

    def unglue(self, text):
        """Put back spaces OCR lost, wherever a word splits cleanly into ones
        the facts use. "dragoncannelloni" stops the model cold, even with the
        right fact in front of it. OCR also reads specks as apostrophes."""
        text = STRAY_APOSTROPHE.sub(" ", text)
        return re.sub(rf"[A-Za-z]{{{GLUED_MIN_LETTERS},}}", lambda m: self._split(m[0]), text)

    def _split(self, word):
        low = word.lower()
        if low in self.vocabulary:
            return word
        fewest = {0: []}    # end of a stretch that splits into words -> those words
        for end in range(1, len(low) + 1):
            for start in sorted(fewest):
                if low[start:end] in self.vocabulary:
                    pieces = fewest[start] + [word[start:end]]
                    if end not in fewest or len(pieces) < len(fewest[end]):
                        fewest[end] = pieces
        return " ".join(fewest[len(low)]) if len(low) in fewest else word

    def top(self, riddle, limit=FACTS_LIMIT):
        """The best lines for a riddle, and the share of its words they cover
        between them (0 to 1). Together, because a riddle can ask two things at
        once, with no one fact covering both."""
        query = words_of(riddle)
        hits = {}   # word in the facts -> the riddle's words it matches
        for w in self.weight:
            matched = {q for q in query if w == q or (len(w) > 3 and fuzz.ratio(w, q) >= FUZZY_WORD)}
            if matched:
                hits[w] = matched
        scored = [(sum(self.weight[w] for w in words & hits.keys()), i) for i, words in enumerate(self.words)]
        scored = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]))[:limit]
        covered = set().union(*(hits[w] for _, i in scored for w in self.words[i] & hits.keys()))
        return [self.lines[i] for _, i in scored], len(covered) / max(1, len(query))


# --- the model ---------------------------------------------------------------

PORT = 8765
MAX_ANSWER_TOKENS = 24
ANSWER = re.compile(r"ANSWER\s*:\s*\[?(?P<answer>[^\]\n]*)", re.I)
MONTH_DAY_YEAR = re.compile(r"\b(?P<month>jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*)"
                            r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+(?P<year>\d{4})\b", re.I)
TRAILING_NUMBER = re.compile(r"(?:and\s*|,\s*)(?P<number>\d+)\W*$", re.I)    # OCR can glue it: "albumand777"
TRAILING_DAY = re.compile(r"(?:\band\s+|,\s*)(?:(?:the\s+)?(?:day|date)\s+today|today'?s\s+(?:day|date))\W*$", re.I)
REPEAT = re.compile(r"\b(?P<times>\d+)\s*times\b(?!\s*\d)", re.I)
# The model's ways of saying this isn't a riddle, which must never get pasted.
NOT_ANSWERS = {"NONE", "UNKNOWN", "NA", "NOTARIDDLE"}


def load_system_prompt(path=SYSTEM_PROMPT_PATH):
    with open(path, encoding="utf-8") as f:
        return f.read()


def gpu_memory():
    """(used, total) MiB, or None if nvidia-smi can't say."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout
        used, total = out.splitlines()[0].split(",")
        return int(used), int(total)
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


def parse_answer(reply, riddle=""):
    """The code in a model reply ("ANSWER: August 2025" -> "AUGUST2025"), or "".

    The model copies a whole date out of a fact even when the riddle only wants
    the month and year, and no prompt wording fixed that without breaking
    riddles that do want the day.
    """
    match = ANSWER.search(reply)
    if not match:
        return ""
    answer = match["answer"]
    if "MONTHANDYEAR" in normalize(riddle):
        answer = MONTH_DAY_YEAR.sub(r"\g<month> \g<year>", answer)
    code = normalize(answer)
    if not code or code in NOT_ANSWERS:
        return ""
    return follow_instructions(code, riddle)


def split_add_ons(riddle, day=None):
    """(the question, times to repeat its answer, what goes on the end of it).

    Sammy adds exact steps to riddles: "my favorite color 3 times and 67", "...
    and the day today". A small model finds the answer and then drops them, and
    can't know the date, so they're done in code.
    """
    question, suffix = riddle.strip(), ""
    while True:
        number, today = TRAILING_NUMBER.search(question), TRAILING_DAY.search(question)
        if not number and not today:
            break
        suffix = (number["number"] if number else str(day or date.today().day)) + suffix
        question = question[:(number or today).start()].rstrip(" ,")
    repeat = REPEAT.search(question)
    if repeat:
        question = (question[:repeat.start()] + question[repeat.end():]).strip(" ,")
    return question, int(repeat["times"]) if repeat else 1, suffix


def strip_add_ons(riddle):
    """The riddle as the model should see it. It refuses "the rarity of dragon
    cannelloni and 67" with the answer in front of it."""
    return split_add_ons(riddle)[0]


def follow_instructions(code, riddle, day=None):
    _, times, suffix = split_add_ons(riddle, day)
    if suffix and code.endswith(suffix):
        code = code[:-len(suffix)]
    if 2 <= times <= 9 and code != code[:len(code) // times] * times:
        code *= times
    return code + suffix


class LlamaServer:
    """llama-server on localhost, kept loaded so a riddle never waits for the model."""

    def __init__(self, model=DEFAULT_MODEL, port=PORT):
        self.model = model_path(model)
        self.port = port
        self.process = None

    def healthy(self):
        try:
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=1)
            conn.request("GET", "/health")
            ok = conn.getresponse().status == 200
            conn.close()
            return ok
        except OSError:
            return False

    def start(self, timeout=120):
        """Start the server and wait until it can answer. One left running by a
        crashed session is reused."""
        if self.healthy():
            return
        if not os.path.exists(LLAMA_SERVER) or not os.path.exists(self.model):
            raise FileNotFoundError("The AI isn't installed. Click Install AI, or run: python setup_ai.py")
        self.process = subprocess.Popen(
            [LLAMA_SERVER, "-m", self.model, "--host", "127.0.0.1", "--port", str(self.port),
             "-ngl", "99", "-c", "2048", "-np", "1", "-fa", "on", "--reasoning", "off"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + timeout
        while not self.healthy():
            if self.process.poll() is not None:
                raise RuntimeError(f"llama-server stopped with exit code {self.process.returncode}")
            if time.monotonic() > deadline:
                self.stop()
                raise TimeoutError("llama-server took too long to load the model")
            time.sleep(0.1)

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)
        self.process = None


class Solved:
    """What came back for one riddle."""

    def __init__(self, riddle, answer, reply, facts, guess, seconds):
        self.riddle = riddle
        self.answer = answer    # ready to paste, "" if the model gave none
        self.reply = reply      # the model's raw reply
        self.facts = facts      # fact lines sent with the riddle
        self.guess = guess      # no fact covered the riddle, so don't trust this
        self.seconds = seconds


class Solver:
    """Answers riddles on a background thread. A new riddle cancels the one in
    flight, so only the answer to the newest text is ever reported.

    on_answer gets (Solved, stamp) and on_error (message); both are called on
    the solver's thread.
    """

    def __init__(self, on_answer, on_error=None, system_prompt=None, facts=None, port=PORT):
        self.on_answer = on_answer
        self.on_error = on_error or (lambda message: None)
        self.system_prompt = load_system_prompt() if system_prompt is None else system_prompt
        self.facts = Facts() if facts is None else facts
        self.port = port
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.job = 0
        self.pending = None
        self.stopped = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def submit(self, riddle, stamp=None):
        with self.lock:
            self.job += 1
            self.pending = (self.job, riddle, stamp)
        self.wake.set()

    def stop(self):
        self.stopped = True
        self.submit("")

    def _run(self):
        while True:
            self.wake.wait()
            self.wake.clear()
            with self.lock:
                pending, self.pending = self.pending, None
            if self.stopped:
                return
            if pending is None:
                continue
            job, riddle, stamp = pending
            try:
                solved = self.solve(riddle, job)
            except (OSError, http.client.HTTPException, ValueError, KeyError, IndexError) as e:
                if job == self.job:
                    self.on_error(f"The model didn't answer: {e}")
                continue
            if solved and job == self.job:
                self.on_answer(solved, stamp)

    def messages(self, riddle, facts):
        notes = "Facts:\n" + "\n".join(f"- {fact}" for fact in facts) + "\n\n" if facts else ""
        return [{"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"{notes}Riddle: {riddle}"}]

    def solve(self, riddle, job=None):
        """Ask the model one riddle and wait for the reply. Returns None if job
        stops being the newest one."""
        start = time.perf_counter()
        cleaned = self.facts.unglue(strip_add_ons(riddle))
        facts, coverage = self.facts.top(cleaned)
        # Facts that only share a word with the riddle pull the model toward
        # game terms ("first one wins" -> DUELSMACHINE), so send good ones or none.
        if coverage < FACT_MIN_COVERAGE:
            facts = []
        reply = self.ask(cleaned, facts, job)
        # Facts can also put it off a riddle it could answer alone.
        if facts and reply is not None and not parse_answer(reply, riddle):
            facts = []
            reply = self.ask(cleaned, facts, job)
        if reply is None:
            return None
        return Solved(riddle, parse_answer(reply, riddle), reply, facts, not facts, time.perf_counter() - start)

    def ask(self, riddle, facts, job=None):
        """One request to the model. Returns its reply, or None if job goes stale.

        The reply is streamed because that's what makes cancelling work: on
        Windows nothing can interrupt a blocking read from another thread, but
        between tokens this can notice it's stale and hang up, which also stops
        the server generating.
        """
        body = json.dumps({
            "messages": self.messages(riddle, facts), "temperature": 0, "max_tokens": MAX_ANSWER_TOKENS,
            "stop": ["\n"], "stream": True, "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": False},
        })
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        reply = ""
        try:
            conn.request("POST", "/v1/chat/completions", body, {"Content-Type": "application/json"})
            response = conn.getresponse()
            if response.status != 200:
                raise ValueError(f"server said {response.status}")
            for line in response:
                if job is not None and job != self.job:
                    return None
                if line.startswith(b"data: ") and not line.startswith(b"data: [DONE]"):
                    choices = json.loads(line[6:])["choices"]
                    reply += (choices[0]["delta"].get("content") or "") if choices else ""
        finally:
            conn.close()
        return reply

"""Read promo codes that scroll by in the top-center chat overlay.

Each overlay line is a red-hat emoji icon followed by white outlined text,
centered horizontally near the top of the screen. Lines are added at the
bottom and drop off the top, so a code arrives one word at a time:

    "code is..." -> "KEYBOARD" -> "ESCAPE" -> "IS" -> "BORING"

Usage:
    python codereader.py                      # watch the primary monitor live
    python codereader.py --region 0,120,1280,720   # only a windowed video player
    python codereader.py --video clip.mp4     # test on a recording

Codes are printed, copied to the clipboard, and pasted into the game if its
window is active. Click the Codes box first so the paste lands there.
"""
import argparse
import ctypes
import itertools
import re
import sys
import time

import cv2
import numpy as np
from rapidfuzz import fuzz
from rapidocr_onnxruntime import RapidOCR

# Everything is measured on frames scaled to this height.
WORK_H = 720
# Where the overlay lives, as fractions of the frame (x0, y0, x1, y1). Lines
# are centered, so a long one ("this code has NO NUMBERS") starts far left.
ROI = (0.02, 0.04, 0.98, 0.45)
# The icon's yellow face is ~25x22px at WORK_H; videos zoom in on it up to ~1.7x.
FACE_MIN_H, FACE_MAX_H = 12, 48


def to_work_scale(frame):
    h = frame.shape[0]
    if h == WORK_H:
        return frame
    return cv2.resize(frame, None, fx=WORK_H / h, fy=WORK_H / h, interpolation=cv2.INTER_AREA)


def find_lines(frame):
    """Find overlay lines by their icon. Returns [(y_center, text_crop, letter_boxes, n_words)] top to bottom.

    The icon is anchored on its yellow face, checked for a red hat above it
    and a red body below it. The face is a small solid blob, so it stays
    separate even when stacked icons touch or the background is red.
    """
    fh, fw = frame.shape[:2]
    rx0, ry0, rx1, ry1 = int(ROI[0] * fw), int(ROI[1] * fh), int(ROI[2] * fw), int(ROI[3] * fh)
    hsv = cv2.cvtColor(frame[ry0:ry1, rx0:rx1], cv2.COLOR_BGR2HSV)
    # Purchase prompts dim the whole screen, overlay included. The overlay's
    # white text is normally the brightest thing here, so undo the dimming.
    brightest = np.percentile(hsv[..., 2], 99.5)
    if brightest < 200:
        frame = cv2.convertScaleAbs(frame, alpha=min(4.0, 250 / max(brightest, 1)))
        hsv = cv2.cvtColor(frame[ry0:ry1, rx0:rx1], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    red = ((h <= 10) | (h >= 170)) & (s > 110) & (v > 90)
    yellow = ((h >= 15) & (h <= 38) & (s > 110) & (v > 140)).astype(np.uint8)

    lines = []
    _, _, stats, _ = cv2.connectedComponentsWithStats(yellow)
    for x, y, w, bh, area in stats[1:]:
        if not (FACE_MIN_H <= bh <= FACE_MAX_H and 0.85 <= w / bh <= 1.5 and area >= 0.4 * w * bh):
            continue
        hat = red[max(0, y - int(0.7 * bh)):y, x:x + w]
        body = red[y + bh:y + bh + int(0.6 * bh), x:x + w]
        if hat.size == 0 or body.size == 0 or hat.mean() < 0.3 or body.mean() < 0.2:
            continue

        # Back to frame coordinates. The line (icon + text) is centered on the
        # screen, so the text ends about as far right of center as the icon
        # starts left of it.
        fx, fy = rx0 + x, ry0 + y
        icon_left = fx - 0.54 * w
        text_left = int(fx + 1.5 * w)
        text_right = int(min(fw, fw - icon_left + 0.5 * w))
        cy = fy + bh // 2
        top, bottom = max(0, cy - bh), min(fh, cy + bh)
        if text_right - text_left < w:
            continue
        line = trim_to_glyphs(frame[top:bottom, text_left:text_right], bh)
        if line is not None:
            lines.append((cy, bh, int(area), line))
    # Lines are ~2 face heights apart; two finds closer than that are the same
    # icon (a stray yellow blob on it). Keep the bigger face.
    kept = []
    for line in sorted(lines, key=lambda l: l[0]):
        if kept and line[0] - kept[-1][0] < 0.8 * line[1]:
            if line[2] > kept[-1][2]:
                kept[-1] = line
            continue
        kept.append(line)
    return [(cy, *line) for cy, _, _, line in kept]


def white_mask(crop):
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    return ((hsv[..., 2] > 190) & (hsv[..., 1] < 60)).astype(np.uint8)


def trim_to_glyphs(crop, face_h):
    """Cut the crop down to the run of white text that starts next to the icon.

    Returns (crop, letter_boxes, n_words), or None if no letters are there.
    Trimming keeps background clutter (signs, walls) out of the OCR input.
    Short letters, hyphens and dots join the run too, so lowercase words and
    "X-RAY" aren't cut short. Words are counted from the gaps between
    letters, which is more reliable than the spaces OCR returns.
    """
    ch = crop.shape[0]
    _, _, stats, _ = cv2.connectedComponentsWithStats(white_mask(crop))
    parts = sorted(
        (int(x), int(y), int(w), int(h)) for x, y, w, h, area in stats[1:]
        if h <= 1.5 * face_h and w <= 3 * face_h and area >= 3 and abs(y + h / 2 - ch / 2) <= 0.5 * face_h
    )
    start = next((i for i, p in enumerate(parts) if p[3] >= 0.45 * face_h), None)
    if start is None or parts[start][0] > face_h:
        return None
    run, right = [parts[start]], parts[start][0] + parts[start][2]
    for p in parts[start + 1:]:
        # Letters can be a word space apart; dots and hyphens sit right next
        # to a letter. Specks further out are background.
        letter = p[3] >= 0.45 * face_h
        if p[0] - right > (0.9 if letter else 0.4) * face_h:
            if letter:
                break
            continue
        run.append(p)
        right = max(right, p[0] + p[2])
    tall = [p[3] for p in run if p[3] >= 0.6 * face_h]
    if not tall:
        return None
    # Letter gaps are under ~0.3x the letter height, spaces over ~0.4x.
    n_words, edge = 1, run[0][0] + run[0][2]
    for p in run[1:]:
        if p[0] - edge > 0.37 * float(np.median(tall)):
            n_words += 1
        edge = max(edge, p[0] + p[2])
    x0 = max(0, run[0][0] - 4)
    letters = [(x - x0, y, w, h) for x, y, w, h in run if h >= 0.45 * face_h]
    return crop[:, x0:right + 4], letters, n_words


def read_frame(ocr, frame):
    """OCR every overlay line in a frame: [(text, score, n_words, y)] top to bottom."""
    return [(*read_text(ocr, *line), y) for y, *line in find_lines(to_work_scale(frame))]


def read_text(ocr, crop, letters, n_words=1):
    """OCR one overlay line. Returns (text, score, n_words).

    Runs recognition only (no text detection): the icon already told us where
    the line is, and the detector tends to skip lone short words.
    """
    # A lone solid bar is "I"; the recognizer reads it as "-" or nothing.
    # Smaller bits next to it (specks, a trailing dot) don't count.
    tallest = max(h for _, _, _, h in letters)
    tall = [b for b in letters if b[3] >= 0.6 * tallest]
    if len(tall) == 1:
        x, y, w, h = tall[0]
        if h >= 2.5 * w and white_mask(crop)[y:y + h, x:x + w].mean() >= 0.75:
            return "I", 0.9, n_words
    img = cv2.copyMakeBorder(crop, 6, 6, 10, 10, cv2.BORDER_REPLICATE)
    (text, score), = ocr.text_recognizer([img])[0]
    return text, float(score), n_words


def normalize(text):
    return re.sub(r"[^A-Z0-9]", "", text.upper())


LOOKALIKES = str.maketrans("0Q158Z2G", "OOISBZZC")


def similarity(a, b):
    """0-100; characters OCR mixes up (0/O/Q, 1/I, 5/S, 8/B, 2/Z, G/C) count as equal."""
    return fuzz.ratio(a.translate(LOOKALIKES), b.translate(LOOKALIKES)) if a and b else 0.0


# Lowercase letters OCR doesn't mix up with their capitals (unlike c o s v w x z).
DISTINCT_LOWER = set("abdefghnqrty")
# A multi-word line with one of these is a hint about the code ("NO NUMBERS").
HINT_WORDS = ("NUMBER", "CONTAIN", "LETTER", "CAPS", "CAPITAL", "LOWERCASE", "UPPERCASE",
              "SPACE", "DIGIT", "HINT", "WORDS", "SENSITIVE")
CODE_WORD = re.compile(r"(?<![A-Z0-9])CODES?(?![A-Z0-9])")
AFTER_CODE = re.compile(r"^.*codes?\b(?P<rest>.*)$", re.I | re.S)


def has_lower(text):
    """Two clearly lowercase letters; OCR gets case wrong on single letters ("Hot", "COLd")."""
    return sum(c in DISTINCT_LOWER for c in text) >= 2


def is_hint(text, multi):
    return multi and any(w in text for w in HINT_WORDS)


class Read:
    """One OCR read of one line, and what it says about the line's role."""

    def __init__(self, raw, score, n_words=None, y=None):
        """n_words and y (line center, in WORK_H pixels) come from the image;
        without n_words, OCR's spaces stand in."""
        raw = raw.strip()
        self.text = normalize(raw)
        self.score = score
        self.y = y
        self.multi = (n_words if n_words is not None else len(raw.split())) >= 2
        self.lower = has_lower(raw)
        self.question = "?" in raw or "!" in raw
        if self.lower:
            # OCR often drops spaces in sentences ("this codehas NO NUMBERS").
            self.intro = "CODE" in self.text
        else:
            self.intro = bool(CODE_WORD.search(raw.upper()) or re.fullmatch(r"[A-Z]*CODE(S|IS)?", self.text))
        # The code can sit on the intro line itself: "code: SPOOKY", "CODE IS SPOOKY".
        self.head = ""
        m = AFTER_CODE.match(raw) if self.intro else None
        if m:
            rest = re.sub(r"^\s*is\b", "", m["rest"], flags=re.I).strip(" :-=>")
            # In capitals, so "code i..." (a misread "code is...") isn't a code "I".
            if (len(normalize(rest)) >= 2 and not re.search("[a-z]", rest)
                    and not is_hint(normalize(rest), len(rest.split()) >= 2)):
                self.head = normalize(rest)


class Slot:
    """One overlay line over its whole lifetime. Every OCR read of it votes on
    its text and on its role. order is its place in the overlay, top to bottom
    across all time; it's a float so a line found late can go between two."""

    def __init__(self, t, order):
        self.order = order
        self.first_seen = self.last_seen = t
        self.votes = {}       # text -> summed score
        self.reads = {}       # text -> number of reads
        self.flags = {}       # flag -> (reads with it, reads)
        self.heads = {}       # code on the intro line -> reads
        self.y = None         # where it was last seen

    def add(self, read):
        if read.y is not None:
            self.y = read.y
        if not read.text:
            return
        self.votes[read.text] = self.votes.get(read.text, 0.0) + read.score
        self.reads[read.text] = self.reads.get(read.text, 0) + 1
        for name in ("intro", "lower", "multi", "question"):
            yes, n = self.flags.get(name, (0, 0))
            self.flags[name] = (yes + getattr(read, name), n + 1)
        if read.head:
            self.heads[read.head] = self.heads.get(read.head, 0) + 1

    def flag(self, name):
        """True if most reads say so; one odd read out of two doesn't count."""
        yes, n = self.flags.get(name, (0, 0))
        return 2 * yes > n

    @property
    def text(self):
        """The most common reading. On a tie, one that another reading only
        adds a stray character to ("CODE1" over "ICODE1"), then the surest."""
        def rank(text):
            inside = any(text != other and text in other for other in self.reads)
            return self.reads[text], inside, self.votes[text]
        return max(self.reads, key=rank) if self.reads else ""

    @property
    def head(self):
        """Code on the intro line, if most reads of it roughly agree on one.
        Reads often carry a stray last letter ("SPOOKYU", "SPOOKYR"), so the
        pick is the reading that most of the others contain."""
        if not self.flag("intro") or not self.heads:
            return ""
        common = max(self.heads, key=self.heads.get)
        group = [h for h in self.heads if similarity(h, common) >= 80]
        if 2 * sum(self.heads[h] for h in group) <= self.flags["intro"][0]:
            return ""
        return max(group, key=lambda h: (sum(self.heads[o] for o in group if h in o), self.heads[h]))

    @property
    def confirmed(self):
        """Read the same way in at least two frames."""
        return self.reads.get(self.text, 0) >= 2

    @property
    def settled(self):
        return sum(self.reads.values()) >= 2


def role(slot, prior):
    """What a line after an intro is: "intro", "hint" or "word".

    prior holds, for each code word collected so far, whether its line had
    several words. A single word is always a code word, whatever its case.
    """
    if slot.flag("intro"):
        return "intro"
    if slot.flag("question"):
        return "hint"
    if slot.flag("multi"):
        if slot.flag("lower") or is_hint(slot.text, True):
            return "hint"
        # Codes come one word per line or all on one line, so a sentence
        # after single words is chatter ("GO GO GO").
        if prior and not any(prior):
            return "hint"
    return "word"


def strip_countdown(words, intro):
    """Drop a "3", "2", "1" countdown before the code."""
    k = 0
    while (k < len(words) and len(words[k]) == 1 and words[k].isdigit()
           and (k == 0 or int(words[k]) == int(words[k - 1]) - 1)):
        k += 1
    if k and words[k - 1] == "1" and (k >= 2 or intro.endswith(str(int(words[0]) + 1))):
        return words[k:]
    return words


def agree(a, b):
    """Do two frames show the same lines, allowing for a scroll between them?"""
    for shift in range(len(a)):
        pairs = [(x.text, y.text) for x, y in zip(a[shift:], b) if x.text and y.text]
        if pairs and all(similarity(x, y) >= WEAK_MATCH for x, y in pairs):
            return True
    return False


# Matching a frame's lines to known lines, in points: a pair scores its text
# similarity - 50. Lines only move up and only leave from the top (oldest
# first), so a match that moved down costs MOVED_DOWN, and a line from the
# last frame that's gone while a line above it is still there costs VANISHED
# (it went undetected). With repeated words ("GO", "GO") that's what tells
# the lines apart. Matching a line missing from the last frame costs
# MISSED_LINE. A weak match that stayed in place gets SAME_PLACE back: it's
# probably a misread ("G" for "C"). A new line costs NEW_LINE at the bottom,
# NEW_ABOVE above a known line (one that went unread until now), or
# NEW_UNREAD if OCR couldn't read it: that's almost always a known line.
WEAK_MATCH, MOVED_DOWN, VANISHED, MISSED_LINE, SAME_PLACE = 60, 45, 30, 30, 15
NEW_LINE, NEW_ABOVE, NEW_UNREAD = 10, 25, 40
MOVE_SLACK = 20  # pixels at WORK_H; lines are ~52px apart


class CodeReader:
    """Turns per-frame overlay lines into finished codes.

    Each frame's lines are matched, in order, to the lines seen in the last
    three frames or three seconds, by text and position. Unmatched lines are
    new. So each real line keeps one Slot however many frames it's in, even
    if it went unread or undetected for a while. A frame that only matches
    weakly is held until the next one: if that agrees with it the lines
    really changed, otherwise it was a misread and is dropped.

    After an intro line ("code is...") come hint lines, which are skipped,
    then the code words. A hint, chatter or another intro after the words
    ends the code.
    """

    def __init__(self, end_gap=6.0, empty_gap=1.5, expect_words=0,
                 on_partial=None, on_ready=None, on_code=None):
        self.end_gap = end_gap        # finish if no new line for this long
        self.empty_gap = empty_gap    # ...or if the overlay is empty this long
        # Codes are usually this many words: report one as ready as soon as
        # that many are in (and again for every extra word), instead of
        # waiting for the end. 0 = only report finished codes.
        self.expect_words = expect_words
        self.on_partial = on_partial or (lambda code: None)
        self.on_ready = on_ready or (lambda code: None)
        self.on_code = on_code or (lambda code: None)
        self.ready = ""
        self.slots = []
        self.recent = []              # slot indices of the last 3 frames, newest last
        self.prev_t = None
        self.pending = None           # (t, reads) of an unconfirmed frame
        self.last_lines_t = None
        self.done_order = -1.0        # lines up to here were already used
        self.trigger = None           # the "code is..." Slot
        self.partial = ""
        self.now = 0.0

    def feed(self, t, reads):
        """reads: [(text, score, n_words, y)] for the lines in this frame, top
        to bottom (see Read); n_words and y may be left off."""
        self.now = t
        reads = [Read(*r) for r in reads]
        if reads:
            self.last_lines_t = t
            self._match(t, reads)
        self._update(t, empty=not reads)

    def _match(self, t, reads):
        recent = set().union(*self.recent)
        recent.update(i for i in range(max(0, len(self.slots) - 10), len(self.slots))
                      if t - self.slots[i].last_seen <= 3.0)
        recent = sorted(recent, key=lambda i: self.slots[i].order)
        plan, weak = self._align(recent, reads, allow_weak=True)
        if not weak:
            self.pending = None
            self._commit(t, reads, plan)
        elif t - self.prev_t > 2.5:
            # The overlay was gone a while; lines that don't match are new.
            self.pending = None
            self._commit(t, reads, self._align(recent, reads, allow_weak=False)[0])
        elif self.pending and agree(self.pending[1], reads):
            pending_t, pending_reads = self.pending
            self.pending = None
            self._commit(pending_t, pending_reads, self._align(recent, pending_reads, allow_weak=False)[0])
            self._match(t, reads)
        else:
            self.pending = (t, reads)

    def _align(self, recent, reads, allow_weak):
        """Match reads (top to bottom) to recent slots (in order), keeping the
        order. Returns (slot index or None for a new line, per read; whether
        any match was weak)."""
        prev = set(self.recent[-1]) if self.recent else set()
        n = len(reads)
        best = None
        # Try matching as many lines as possible first, so ties keep lines.
        for mask in sorted(range(1 << n), key=lambda m: -bin(m).count("1")):
            matched = [i for i in range(n) if mask >> i & 1]
            for combo in itertools.combinations(recent, len(matched)):
                plan = [None] * n
                score, weak, ok = 0.0, False, True
                for r, s in zip(matched, combo):
                    plan[r] = s
                    read, slot = reads[r], self.slots[s]
                    known_y = read.y is not None and slot.y is not None
                    if read.text and slot.text:
                        sim = similarity(read.text, slot.text)
                        weak |= sim < WEAK_MATCH
                        ok &= allow_weak or sim >= WEAK_MATCH
                        score += sim - 50
                        if sim < WEAK_MATCH and s in prev and known_y and abs(read.y - slot.y) <= MOVE_SLACK:
                            score += SAME_PLACE
                    if known_y and read.y > slot.y + MOVE_SLACK:
                        score -= MOVED_DOWN
                    if s not in prev:
                        score -= MISSED_LINE
                if combo:
                    top = min(self.slots[s].order for s in combo)
                    score -= VANISHED * sum(1 for p in prev if p not in combo and self.slots[p].order > top)
                last = matched[-1] if matched else -1
                score -= sum(NEW_UNREAD if not reads[r].text else NEW_LINE if r > last else NEW_ABOVE
                             for r in range(n) if plan[r] is None)
                if ok and (best is None or score > best[0]):
                    best = (score, plan, weak)
        return best[1], best[2]

    def _commit(self, t, reads, plan):
        kept = []
        for k, (i, read) in enumerate(zip(plan, reads)):
            if i is None:
                i = self._new_slot(t, plan, k)
                plan[k] = i
            self.slots[i].add(read)
            self.slots[i].last_seen = t
            kept.append(i)
        self.recent = (self.recent + [kept])[-3:]
        self.prev_t = t

    def _new_slot(self, t, plan, k):
        """Add a line for read k, placed just below the line above it in this
        frame, or at the bottom if no known line is below it."""
        below = next((self.slots[i].order for i in plan[k + 1:] if i is not None), None)
        if below is None:
            order = max((s.order for s in self.slots), default=-1.0) + 1
        else:
            above = self.slots[plan[k - 1]].order if k else max(
                (s.order for s in self.slots if s.order < below), default=below - 1)
            order = (above + below) / 2
        self.slots.append(Slot(t, order))
        return len(self.slots) - 1

    def _after(self, order):
        return sorted((s for s in self.slots if s.order > order), key=lambda s: s.order)

    def _scan(self):
        """Collect the code after the intro. Returns (words, last word's slot,
        the line that ends the code or None while it may still grow)."""
        intro = self.trigger
        words, last = ([intro.head], intro) if intro.head else ([], None)
        prior = [False] if intro.head else []
        for slot in self._after(intro.order):
            # A line read once and then never again was a misread.
            if not slot.text or (not slot.settled and self.now - slot.last_seen > 0.6):
                continue
            kind = role(slot, prior)
            if kind == "word":
                words.append(slot.text)
                prior.append(slot.flag("multi"))
                last = slot
            elif not words:
                if kind == "intro":  # "code coming up" ... "code is..."
                    self.trigger = slot
                    return self._scan()
            elif slot.settled:
                return strip_countdown(words, intro.text), last, slot
            else:
                break  # might end the code; wait for another read of it
        return strip_countdown(words, intro.text), last, None

    def _update(self, t, empty):
        words = []
        while True:
            if self.trigger is None:
                self.trigger = next((s for s in self._after(self.done_order) if s.flag("intro")), None)
                if self.trigger is None:
                    return
            words, last, end = self._scan()
            code = "".join(words)
            if code != self.partial:
                self.partial = code
                self.on_partial(code)
            # Wait for the newest word to be read twice so a misread isn't reported.
            if (self.expect_words and len(words) >= self.expect_words
                    and last.confirmed and code != self.ready):
                self.ready = code
                self.on_ready(code)
            if end is None:
                break
            # The line that ended this code may start the next one.
            self._close(code, max(s.order for s in self.slots if s.order < end.order))

        quiet = t - max(s.first_seen for s in self.slots) >= self.end_gap
        # An empty overlay ends the code, unless it's still short: then the
        # streamer may just be typing slowly.
        gone = (empty and self.last_lines_t is not None and t - self.last_lines_t >= self.empty_gap
                and len(words) >= self.expect_words)
        if quiet or gone:
            self.finish()

    def _close(self, code, upto):
        if code:
            self.on_code(code)
        self.done_order = upto
        self.trigger = None
        self.partial = ""
        self.ready = ""

    def finish(self):
        code = "".join(self._scan()[0]) if self.trigger is not None else ""
        self._close(code, max((s.order for s in self.slots), default=-1.0))


def frames_from_video(path, fps):
    cap = cv2.VideoCapture(path)
    step = max(1, round(cap.get(cv2.CAP_PROP_FPS) / fps))
    i = 0
    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            return
        yield cap.get(cv2.CAP_PROP_POS_MSEC) / 1000, frame
        i += step


def frames_from_screen(fps, monitor=1, region=None):
    import mss
    with mss.mss() as sct:
        if region:
            x, y, w, h = region
            box = {"left": x, "top": y, "width": w, "height": h}
        else:
            box = sct.monitors[monitor]
        start = time.monotonic()
        while True:
            t0 = time.monotonic()
            frame = np.ascontiguousarray(np.asarray(sct.grab(box))[..., :3])
            yield t0 - start, frame
            time.sleep(max(0.0, 1 / fps - (time.monotonic() - t0)))


def active_window():
    """Title of the window that has keyboard focus."""
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    title = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(user32.GetForegroundWindow(), title, 256)
    return title.value


def press_paste():
    """Ctrl+A then Ctrl+V in the active window, so a longer code replaces a
    shorter one. Keys carry scan codes and stay down briefly: games read scan
    codes and can miss a press shorter than a frame."""
    user32 = ctypes.windll.user32
    ctrl, a, v, key_up = 0x11, 0x41, 0x56, 0x0002

    def key(vk, flags=0):
        user32.keybd_event(vk, user32.MapVirtualKeyW(vk, 0), flags, 0)
        time.sleep(0.03)

    key(ctrl)
    try:
        for vk in (a, v):
            key(vk)
            key(vk, key_up)
    finally:
        key(ctrl, key_up)


def paste_into(title):
    """Paste the clipboard if the active window is titled exactly this (so a
    browser tab called "Roblox codes" doesn't count). Returns whether it did."""
    if active_window().casefold() != title.casefold():
        return False
    press_paste()
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", help="read from a video file instead of the screen")
    ap.add_argument("--fps", type=float, default=4, help="frames to check per second (default 4)")
    ap.add_argument("--monitor", type=int, default=1, help="monitor to capture, 1 = primary")
    ap.add_argument("--region", help="capture only x,y,w,h (e.g. a windowed video player)")
    ap.add_argument("--words", type=int, default=3,
                    help="copy as soon as this many words are in, and again for each extra word "
                         "(default 3, 0 = wait for the code to finish)")
    ap.add_argument("--end-gap", type=float, default=6.0,
                    help="seconds with no new word before a code counts as finished (default 6)")
    ap.add_argument("--copy-partial", action="store_true",
                    help="update the clipboard with every new word, not just the finished code")
    ap.add_argument("--no-copy", action="store_true", help="never touch the clipboard (also stops pasting)")
    ap.add_argument("--no-paste", action="store_true", help="copy codes but don't paste them")
    ap.add_argument("--paste-window", default="Roblox",
                    help='only paste when the active window has exactly this title (default "Roblox")')
    ap.add_argument("--verbose", action="store_true", help="print every frame's OCR reads")
    args = ap.parse_args()
    # Raw OCR reads can contain characters the Windows console can't print.
    sys.stdout.reconfigure(errors="replace")

    import pyperclip

    state = {"copied": "", "early": False}

    def copy(code):
        """Copy and paste the code. Returns a note on what happened."""
        state["copied"] = code
        if args.no_copy:
            return ""
        pyperclip.copy(code)
        if args.no_paste:
            return "  (copied)"
        if paste_into(args.paste_window):
            return "  (copied and pasted)"
        return f"  (copied, not pasted: {args.paste_window} isn't the active window)"

    def on_partial(code):
        print(f"[{now:6.1f}s] building: {code}")
        if args.copy_partial:
            copy(code)

    def on_ready(code):
        note = "updated: another word came in" if state["early"] else \
            f"{args.words} words in, will update if more come"
        state["early"] = True
        print(f"[{now:6.1f}s] CODE: {code}{copy(code)}  [{note}]")

    def on_code(code):
        if state["early"] and code == state["copied"]:
            print(f"[{now:6.1f}s] done: {code}")
        else:
            print(f"[{now:6.1f}s] CODE: {code}{copy(code)}")
        state["early"] = False

    ocr = RapidOCR()
    reader = CodeReader(end_gap=args.end_gap, expect_words=args.words,
                        on_partial=on_partial, on_ready=on_ready, on_code=on_code)
    if args.video:
        frames = frames_from_video(args.video, args.fps)
    else:
        region = tuple(int(v) for v in args.region.split(",")) if args.region else None
        frames = frames_from_screen(args.fps, args.monitor, region)
        print("Watching the screen. Ctrl+C to stop.")

    now = 0.0
    try:
        for now, frame in frames:
            reads = read_frame(ocr, frame)
            if args.verbose:
                print(f"  {now:6.1f}s  {reads}")
            reader.feed(now, reads)
    except KeyboardInterrupt:
        pass
    reader.finish()


if __name__ == "__main__":
    main()

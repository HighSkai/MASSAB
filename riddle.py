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

import cv2
import numpy as np
from rapidfuzz import fuzz

from codereader import WORK_H, Read, dim_gain, is_hint, normalize, similarity, to_work_scale, white_mask
from setup_ai import APP_DIR, DEFAULT_MODEL, LLAMA_SERVER, model_path

# Where overlay rows can be, as fractions of the frame (x0, y0, x1, y1). It stops
# above the Codes menu, whose white centered text would otherwise pass for a row.
BAND = (0.02, 0.07, 0.98, 0.36)
# A row's middle is this close to the screen's (fraction of width). The text is
# what's centered, with the icon hanging off to the left of it.
CENTER_TOLERANCE = 0.03
ICON_MARGIN = 0.005
GLYPH_MIN_H, GLYPH_MAX_H = 8, 48
ROW_MIN_LETTERS = 4
# Two letters are neighbors if they're side by side and share this much of the
# shorter one's height. A descender and the ascender below it barely overlap,
# so wrapped rows stay apart, while a "d" and an "n" overlap fully.
SHARED_HEIGHT = 0.5
LOOK_BACK = 3   # letters at the end of a chain to try, in case the last is a speck
# Pixels at WORK_H between the middles of two rows of one wrapped message. They
# measure ~24 apart, while separate overlay lines are ~52 apart.
WRAP_PITCH = 36


def neighbors(a, b):
    """Could b, further right, be the next letter after a?"""
    gap = b[0] - (a[0] + a[2])
    shared = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return gap <= max(a[3], b[3]) and shared >= SHARED_HEIGHT * min(a[3], b[3])


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


def read_rows(ocr, frame):
    """OCR every overlay message in a frame: [(text, score, n_words, y)] top to bottom.

    Rows are found at WORK_H but read from the full-size frame, since small
    wrapped text loses a lot when it's scaled down.
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
        if last_middle is not None and middle - last_middle <= WRAP_PITCH:
            first, first_score, first_words, first_y = messages[-1]
            messages[-1] = (f"{first} {text}", min(score, first_score), first_words + words, first_y)
        else:
            messages.append((text, score, words, middle))
        last_middle = middle
    return messages


# --- tracking messages across frames -----------------------------------------

RIDDLE_MIN_WORDS, RIDDLE_MIN_LETTERS = 3, 12
# Intros and hints are short ("code is...", "it contains no numbers"). A longer
# line that happens to use their words is a riddle ("which update number added
# the divine fuse", "the code is the month the first fuse machine released").
SHORT_LINE_WORDS = 5
# An intro or hint stays on screen for seconds, and one bad read shouldn't turn
# it into a riddle. Remember them this long, if they're long enough to recognize.
NOT_RIDDLE_MEMORY, NOT_RIDDLE_MIN_LETTERS = 8.0, 8
SAME_TEXT = 80          # similarity of two reads of one message
JOIN_GAP = 2.0          # a message this soon after the last one continues the riddle
LONGER_BY = 3           # letters a better read must add to count as an update


class Part:
    """One overlay message of a riddle, over every frame it's been read in."""

    def __init__(self, text, t, stamp):
        self.reads = Counter({text: 1})
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
    """Turns per-frame messages into riddles, reporting one as soon as two
    frames agree on it. Follow-on messages, or a fuller read of the same one,
    report the riddle again so the answer can be replaced.

    on_riddle gets (text, stamp), stamp being when the newest part was first on
    screen. Intros and hints are left alone, they belong to the code reader.
    """

    def __init__(self, on_riddle):
        self.on_riddle = on_riddle
        self.parts = []
        self.sent = ""
        self.not_riddles = {}   # text -> when it was last seen

    def feed(self, t, messages, stamp=None):
        stamp = t if stamp is None else stamp
        for text, score, n_words, *_ in messages:
            self._add(text, n_words, t, stamp)
        confirmed = [p for p in self.parts if p.confirmed or sum(p.reads.values()) >= 2]
        for part in confirmed:
            part.confirmed = True
        riddle = " ".join(p.text for p in confirmed)
        if riddle and self._changed(riddle):
            self.sent = riddle
            self.on_riddle(riddle, max(p.first_stamp for p in confirmed))

    def _add(self, text, n_words, t, stamp):
        read = Read(text, 1.0, n_words)
        if self._not_a_riddle(read, n_words, t):
            return
        known = next((p for p in self.parts if p.matches(text)), None)
        if known:
            known.reads[text] += 1
            known.last_seen = t
            return
        recent = self.parts and t - max(p.last_seen for p in self.parts) <= JOIN_GAP
        if recent:
            if n_words >= 2:
                self.parts.append(Part(text, t, stamp))
        elif n_words >= RIDDLE_MIN_WORDS and len(read.text) >= RIDDLE_MIN_LETTERS:
            self.parts = [Part(text, t, stamp)]
            self.sent = ""

    def _not_a_riddle(self, read, n_words, t):
        """Is this an intro or hint, or a bad read of one seen just now?"""
        self.not_riddles = {text: seen for text, seen in self.not_riddles.items() if t - seen <= NOT_RIDDLE_MEMORY}
        if n_words <= SHORT_LINE_WORDS and (read.intro or is_hint(read.text, n_words >= 2)):
            if len(read.text) >= NOT_RIDDLE_MIN_LETTERS:
                self.not_riddles[read.text] = t
            return True
        return any(fuzz.partial_ratio(text, read.text) >= SAME_TEXT for text in self.not_riddles)

    def _changed(self, riddle):
        if not self.sent:
            return True
        grown = len(normalize(riddle)) - len(normalize(self.sent))
        return grown >= LONGER_BY or similarity(normalize(riddle), normalize(self.sent)) < SAME_TEXT


# --- the facts file ----------------------------------------------------------

FACTS_PATH = os.path.join(APP_DIR, "data", "sab_facts.md")
SYSTEM_PROMPT_PATH = os.path.join(APP_DIR, "prompts", "riddle_system.txt")
FACTS_LIMIT = 6
FACT_MIN_COVERAGE = 0.6  # share of a riddle's words one fact must have, or the answer is a guess
FUZZY_WORD = 85          # how close a word must be to match; OCR drops and swaps letters
STOPWORDS = set("""a about an and are as at be been but by came can come did do does for from game
get gets got had has have how i in into is it its me my no not of on or out sab steal brainrot that
the their this to was were what when where which who why will with you your""".split())
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

    def top(self, riddle, limit=FACTS_LIMIT):
        """The best lines for a riddle, and the largest share of its words any
        of them covers (0 to 1)."""
        query = words_of(riddle)
        hits = {}   # word in the facts -> the riddle's words it matches
        for w in self.weight:
            matched = {q for q in query if w == q or (len(w) > 3 and fuzz.ratio(w, q) >= FUZZY_WORD)}
            if matched:
                hits[w] = matched
        scored = [(sum(self.weight[w] for w in words & hits.keys()), i) for i, words in enumerate(self.words)]
        scored = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]))[:limit]
        coverage = max((len(set().union(*(hits[w] for w in self.words[i] & hits.keys()))) / len(query)
                        for _, i in scored), default=0.0)
        return [self.lines[i] for _, i in scored], coverage


# --- the model ---------------------------------------------------------------

PORT = 8765
MAX_ANSWER_TOKENS = 24
ANSWER = re.compile(r"ANSWER\s*:\s*\[?(?P<answer>[^\]\n]*)", re.I)
MONTH_DAY_YEAR = re.compile(r"\b(?P<month>jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*)"
                            r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+(?P<year>\d{4})\b", re.I)


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
    return normalize(answer)


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
        stops being the newest one.

        The reply is streamed because that's what makes cancelling work: on
        Windows nothing can interrupt a blocking read from another thread, but
        between tokens this can notice it's stale and hang up, which also stops
        the server generating.
        """
        start = time.perf_counter()
        facts, coverage = self.facts.top(riddle)
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
        return Solved(riddle, parse_answer(reply, riddle), reply, facts, coverage < FACT_MIN_COVERAGE,
                      time.perf_counter() - start)

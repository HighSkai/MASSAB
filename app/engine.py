"""The capture loop behind both the command line and the GUI.

Every frame goes to the riddle tracker, and to the code reader unless a riddle
has the screen. Whatever comes out is copied and pasted here. Everything that
happens is reported through one on_event(kind, now=seconds, ...) callback:

    building    code            a code is being collected
    code        code note ready a code was copied (ready: more words may come)
    done        code            the last code copied has ended
    riddle      text            a riddle was read, the model is on it
    answer      solved note total paste unchanged
                                the model answered; total is seconds since the
                                text first appeared on screen, paste included
    no_answer   solved          the model gave nothing usable
    lookup      state note      a riddle about now is being looked up online: state is
                                "searching", "found", "cached", "nothing" or "failed"
    ai          state           "loading", "ready" or "off"
    error       message
    frame       reads           every frame's OCR reads (verbose only)
    rows        boxes           each text row found in a frame, as (x0, y0, x1, y1, text)
                                in frame pixels (show_reads only)
"""
import argparse
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import pyperclip

import codereader
from codereader import KEY_DELAY, CodeReader, frames_from_screen, frames_from_video, paste_into, read_frame
from lookup import INTRO_REFRESH, WAIT, WEB_SEARCHES, LiveInfo
from riddle import FACTS_PATH, Facts, LlamaServer, RiddleTracker, Solver, load_system_prompt, read_rows
from setup_ai import DEFAULT_MODEL, MODELS, ai_installed
from today import local_now

# Codes last seconds, so 4 frames a second is plenty. Riddles are on the clock.
# The code reader is tuned for its rate and drops codes at 12, so with frames
# coming in at the riddle rate it only gets every third one.
CODE_FPS, RIDDLE_FPS = 4, 12
# The first request is the slow one. A real riddle pays that with a full prompt.
WARM_UP_RIDDLE = "month and year the first fuse machine in sab released"


@dataclass
class Options:
    words: int = 3
    end_gap: float = 6.0
    copy_partial: bool = False
    no_copy: bool = False
    no_paste: bool = False
    paste_window: str = "Roblox"
    key_delay: float = KEY_DELAY    # seconds after each key of a paste
    verbose: bool = False
    model: str = DEFAULT_MODEL
    system_prompt: str = None   # None = prompts/riddle_system.txt
    facts_path: str = FACTS_PATH
    code_step: int = 1          # give the code reader every Nth frame
    show_reads: bool = False    # report where text was read, for drawing it on screen
    online: bool = False        # look up riddles about now (today's releases, the latest update)
    web_search: str = "off"     # and also search the web with "tavily" or "brave"
    lookup_wait: float = WAIT   # seconds a riddle waits for lookups
    # Replaying a recording: when it was made ("2026-11-10T18:15"), so "today"
    # in its riddles is that day, not the day it's replayed. "" is the real clock.
    today: str = ""


def replay_clock(when):
    """A clock that starts at when (ISO, this PC's time zone unless it says
    otherwise) and runs on from there, or the real one for ""."""
    if not when:
        return local_now
    start, then = time.monotonic(), datetime.fromisoformat(when)
    then = then.astimezone() if then.tzinfo is None else then
    return lambda: then + timedelta(seconds=time.monotonic() - start)


class Engine:
    def __init__(self, options, on_event):
        self.options = options
        self.on_event = on_event
        self.now = 0.0
        self.frames_seen = 0
        self.ocr = None
        self.server = None
        self.solver = None
        # One for the engine's whole life, so its cache outlasts reloading the AI.
        self.live = LiveInfo(options.online, options.web_search, options.lookup_wait)
        self.intro_seen = None
        self.paste_lock = threading.Lock()
        self.stopping = threading.Event()
        self.reset()

    def emit(self, kind, **fields):
        self.on_event(kind, now=self.now, **fields)

    def reset(self):
        """Start the readers over, so half-read lines don't carry into the next watch."""
        self.copied = ""
        self.early = False
        self.reader = self.new_reader()
        self.tracker = RiddleTracker(self.on_riddle)

    def new_reader(self):
        return CodeReader(end_gap=self.options.end_gap, expect_words=self.options.words,
                          on_partial=self.on_partial, on_ready=self.on_ready, on_code=self.on_code)

    def stop(self):
        self.stopping.set()

    # --- the AI ---------------------------------------------------------------

    def start_ai(self):
        """Load the model and warm it up, so the first riddle isn't slow. Blocks
        until it's ready. Reports problems as an error event."""
        if self.solver:
            return True
        self.emit("ai", state="loading")
        try:
            prompt = self.options.system_prompt
            self.server = LlamaServer(self.options.model)
            self.server.start()
            self.solver = Solver(self.on_answer, self.on_ai_error, load_system_prompt() if prompt is None else prompt,
                                 Facts(self.options.facts_path), live=self.live, on_lookup=self.on_lookup,
                                 clock=replay_clock(self.options.today))
            self.solver.solve(WARM_UP_RIDDLE)
        except (OSError, RuntimeError, ValueError) as e:
            self.stop_ai()
            self.emit("error", message=str(e))
            return False
        self.live.refresh(local_now())
        self.emit("ai", state="ready")
        return True

    def configure_live(self, online=None, web_search=None, lookup_wait=None):
        """Change online lookups from the next riddle on; safe from any thread."""
        for name, value in (("online", online), ("web_search", web_search), ("lookup_wait", lookup_wait)):
            if value is not None:
                setattr(self.options, name, value)
        self.live.configure(online, web_search, lookup_wait)
        if online and self.solver:
            self.live.refresh(local_now())

    def on_lookup(self, state, note):
        self.emit("lookup", state=state, note=note)

    def stop_ai(self):
        if not self.solver and not self.server:
            return
        if self.solver:
            self.solver.stop()
            self.solver = None
        if self.server:
            self.server.stop()
            self.server = None
        self.emit("ai", state="off")

    def on_ai_error(self, message):
        self.emit("error", message=message)

    def screen_blocked(self):
        self.emit("error", message="Windows is blocking screen capture, maybe a lock screen or admin prompt. "
                                   "Watching picks up again when it's gone.")

    def set_system_prompt(self, prompt):
        """Use this prompt from the next riddle on; safe from any thread."""
        self.options.system_prompt = prompt
        if self.solver:
            self.solver.system_prompt = prompt

    # --- copy and paste -------------------------------------------------------

    def deliver(self, code):
        """Copy and paste a code. Returns a note on what happened."""
        with self.paste_lock:
            self.copied = code
            if self.options.no_copy:
                return ""
            pyperclip.copy(code)
            if self.options.no_paste:
                return "  (copied)"
            if paste_into(self.options.paste_window, self.options.key_delay):
                return "  (copied and pasted)"
            return f"  (copied, not pasted: {self.options.paste_window} isn't the active window)"

    # --- what the readers report ----------------------------------------------

    def on_partial(self, code):
        self.emit("building", code=code)
        if self.options.copy_partial:
            self.deliver(code)

    def on_ready(self, code):
        note = self.deliver(code)
        self.emit("code", code=code, note=note, ready="more" if self.early else "first")
        self.early = True

    def on_code(self, code):
        if self.early and code == self.copied:
            self.emit("done", code=code)
        else:
            self.emit("code", code=code, note=self.deliver(code), ready=None)
        self.early = False

    def on_riddle(self, text, stamp):
        self.emit("riddle", text=text)
        if self.solver:
            self.solver.submit(text, stamp)
        else:
            self.emit("error", message="A riddle came in, but the AI isn't loaded.")

    def on_answer(self, solved, stamp):
        """Runs on the solver's thread."""
        if not solved.answer:
            self.emit("no_answer", solved=solved)
            return
        # Re-solving a fuller read usually lands on the same answer.
        unchanged = solved.answer == self.copied
        start = time.perf_counter()
        note = "" if unchanged else self.deliver(solved.answer)
        done = time.perf_counter()
        self.emit("answer", solved=solved, note=note, total=done - stamp, paste=done - start, unchanged=unchanged)

    # --- the loop -------------------------------------------------------------

    def run(self, frames):
        """Read frames until they run out or stop() is called."""
        if self.ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            self.ocr = RapidOCR()
        for self.now, frame in frames:
            stamp = time.perf_counter()
            if self.stopping.is_set():
                break
            if frame is not None:   # None while the screen can't be captured
                self.process(frame, stamp)
        self.reader.finish()

    def process(self, frame, stamp):
        self.frames_seen += 1
        # Riddles come first: "the code is the rarity of dragon cannelloni and
        # 67" looks like a code but needs solving.
        if self.options.show_reads:
            boxes = []
            messages = read_rows(self.ocr, frame, boxes)
            self.emit("rows", boxes=boxes)
        else:
            messages = read_rows(self.ocr, frame)
        if self.options.verbose:
            self.emit("frame", reads=messages)
        was_claimed = self.tracker.claimed(self.now)
        self.tracker.feed(self.now, messages, stamp)
        claimed = self.tracker.claimed(self.now)
        # An intro means a riddle is a few seconds off: get the feeds fresh for it now.
        if self.tracker.intro_seen != self.intro_seen:
            self.intro_seen = self.tracker.intro_seen
            if self.solver and self.live.enabled:
                self.live.refresh(local_now(), INTRO_REFRESH)
        # Those lines read as a code intro too, and the riddle would become its words.
        if claimed and not was_claimed:
            self.reader = self.new_reader()
        if not claimed and self.frames_seen % self.options.code_step == 0:
            reads = read_frame(self.ocr, frame)
            if self.options.verbose:
                self.emit("frame", reads=reads)
            self.reader.feed(self.now, reads)


def print_event(kind, now, **e):
    """Show events on the command line."""
    stamp = f"[{now:6.1f}s]"
    if kind == "building":
        print(f"{stamp} building: {e['code']}")
    elif kind == "code":
        note = {"first": "  [{} words in, will update if more come]", "more": "  [updated: another word came in]"}
        print(f"{stamp} CODE: {e['code']}{e['note']}" + note.get(e["ready"], "").format(e.get("words")))
    elif kind == "done":
        print(f"{stamp} done: {e['code']}")
    elif kind == "riddle":
        print(f"{stamp} riddle: {e['text']}")
    elif kind == "answer":
        solved = e["solved"]
        guess = f"  [GUESS: {getattr(solved, 'flag', '') or 'no fact matched'}]" if solved.guess else ""
        live = sorted({item.source for item in getattr(solved, "sources", ())})
        live = f"  [live: {', '.join(live)}]" if live else ""
        same = "  (same answer)" if e["unchanged"] else e["note"]
        print(f"{stamp} ANSWER: {solved.answer}{same}  [{e['total']:.2f}s total, model {solved.seconds:.2f}s]"
              f"{guess}{live}")
    elif kind == "no_answer":
        print(f"{stamp} no answer from the model: {e['solved'].reply!r}")
    elif kind == "lookup":
        print(f"{stamp} lookup: {e['note']}")
    elif kind == "ai":
        print(f"{stamp} AI: {e['state']}")
    elif kind == "error":
        print(f"{stamp} error: {e['message']}")
    elif kind == "frame":
        print(f"  {now:6.1f}s  {e['reads']}")


def check_today(text):
    try:
        text and datetime.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("use a date like 2026-11-10, or 2026-11-10T18:15 with the time") from None
    return text


def main():
    ap = argparse.ArgumentParser(description=codereader.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", help="read from a video file instead of the screen")
    ap.add_argument("--fps", type=float, default=RIDDLE_FPS,
                    help=f"frames to check per second (default {RIDDLE_FPS}). The code reader only "
                         f"gets about {CODE_FPS} of them")
    ap.add_argument("--monitor", type=int, default=1, help="monitor to capture, 1 = primary")
    ap.add_argument("--region", help="read only x,y,w,h, in pixels of the screen or the --video "
                                     "(default: the top half of it, all the way across)")
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
    ap.add_argument("--key-delay", type=float, default=KEY_DELAY * 1000,
                    help="milliseconds after each key of a paste (default 15)")
    ap.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL, help="which downloaded model riddles use")
    ap.add_argument("--online", action="store_true",
                    help="look up riddles about now (today's releases, the latest update) on the game's Roblox "
                         "page and its wiki. Only the riddle's words are sent")
    ap.add_argument("--web-search", choices=[name for name in WEB_SEARCHES if name != "off"],
                    help="with --online, also search the web; the API key comes from TAVILY_API_KEY or "
                         "BRAVE_API_KEY, or the one saved in the window's Settings")
    ap.add_argument("--lookup-wait", type=float, default=WAIT,
                    help=f"seconds a riddle waits for lookups (default {WAIT:g})")
    ap.add_argument("--today", type=check_today, default="",
                    help="with --video, the date and time the recording was made (2026-11-10 or "
                         "2026-11-10T18:15), so riddles about today are answered for that day")
    ap.add_argument("--verbose", action="store_true", help="print every frame's OCR reads")
    args = ap.parse_args()
    # Raw OCR reads can contain characters the Windows console can't print.
    sys.stdout.reconfigure(errors="replace")

    options = Options(words=args.words, end_gap=args.end_gap, copy_partial=args.copy_partial,
                      no_copy=args.no_copy, no_paste=args.no_paste, paste_window=args.paste_window,
                      key_delay=args.key_delay / 1000,
                      verbose=args.verbose, model=args.model,
                      code_step=max(1, round(args.fps / CODE_FPS)), online=args.online,
                      web_search=args.web_search or "off", lookup_wait=args.lookup_wait, today=args.today)
    engine = Engine(options, lambda kind, now, **e: print_event(kind, now, words=args.words, **e))
    # Codes don't need the AI, so without it only riddles go unsolved.
    if not ai_installed(args.model):
        print("The AI isn't installed, so only codes will be read. Run app\\setup_ai.py to solve riddles too.")
    elif not engine.start_ai():
        return 1

    region = tuple(int(v) for v in args.region.split(",")) if args.region else None
    if args.video:
        frames = frames_from_video(args.video, args.fps, region)
    else:
        frames = frames_from_screen(args.fps, args.monitor, region, engine.screen_blocked)
        print("Watching the screen. Ctrl+C to stop.")
    try:
        engine.run(frames)
    except KeyboardInterrupt:
        engine.reader.finish()
    finally:
        engine.stop_ai()
    return 0


if __name__ == "__main__":
    sys.exit(main())

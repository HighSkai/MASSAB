"""Check that riddles get solved and pasted in under 2 seconds on this PC.

Run it with your usual apps open (Roblox, Chrome, Discord, Spotify), because
they compete with the model for the GPU. Your clipboard gets overwritten, but
no keys are pressed: the paste is timed by waiting as long as it takes.

    python bench_riddle.py
    python bench_riddle.py --model 2b

The full-pipeline part needs sim.py and testdata/, and is skipped without them.
"""
import argparse
import os
import statistics
import subprocess
import sys
import time

import cv2
import mss

import engine as engine_module
from codereader import frames_from_video, normalize, similarity
from engine import RIDDLE_FPS, Engine, Options
from riddle import FACTS_PATH, gpu_memory
from setup_ai import DEFAULT_MODEL, MODELS

LIMIT = 2.0
PASTE_SECONDS = 0.18        # press_paste's six 30 ms key steps
LOW_VRAM_MIB = 500
CLIP = os.path.join(os.environ.get("CODEREADER_CLIPS", os.path.expanduser("~/Videos")), "2026-11-03 09-24-45.mp4")
CLIP_TEXT = "month and year the first fuse machine in sab released"
# (riddle, accepted answers). Only the first is a real riddle; the rest are
# written from data/sab_facts.md in the same style.
TRIVIA = [
    ("month and year the first fuse machine in\nsab released", "AUGUST2025"),
    ("what month and year did santas fuse\ncome out in sab", "DECEMBER2025"),
    ("month and year the divine fuse machine\nreleased in sab", "MARCH2026"),
    ("month and year the summer fuse update\nreleased in sab", "MAY2026"),
    ("month and year the witch fuse\nreleased in sab", "OCTOBER2025"),
    ("month and year steal a brainrot\nlaunched on roblox", "MAY2025"),
    ("what replaced the first fuse\nmachine in sab", "CRAFTMACHINE|THECRAFTMACHINE"),
    ("which update number added the\ndivine fuse", "41|UPDATE41"),
    ("which update number added the\nwitch fuse", "20|UPDATE20"),
    ("how many brainrots does\nsantas fuse take", "4|FOUR"),
    ("which rebirth requires the secret\nbrainrot los tralaleritos", "16|REBIRTH16"),
    ("what rarity is tralalero tralala\nin sab", "BRAINROTGOD"),
]
TRIVIA_TARGET = 0.8
ROUNDS = 3


def running_apps():
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, errors="replace").stdout
    names = {line.split(",")[0].strip('"').lower() for line in out.splitlines() if line}
    wanted = {"Roblox": "robloxplayerbeta.exe", "Chrome": "chrome.exe", "Discord": "discord.exe",
              "Spotify": "spotify.exe"}
    return [app for app, exe in wanted.items() if exe in names]


def p95(values):
    return sorted(values)[min(len(values) - 1, int(len(values) * 0.95))]


class Report:
    def __init__(self):
        self.failed = False

    def check(self, passed, text):
        print(f"  {'PASS' if passed else 'FAIL'}  {text}")
        self.failed |= not passed


def bench_model(engine, report):
    """Time the model alone on every riddle, a few rounds each."""
    print("\nModel on its own")
    times, thinking, right, total = [], 0, 0, 0
    for _ in range(ROUNDS):
        for text, expected in TRIVIA:
            solved = engine.solver.solve(text.replace("\n", " "))
            times.append(solved.seconds)
            thinking += "<think" in solved.reply or not solved.reply.strip().upper().startswith("ANSWER")
            good = solved.answer in expected.split("|")
            right += good
            total += 1
            if total <= len(TRIVIA):
                print(f"        {solved.seconds * 1000:4.0f} ms  {text.replace(chr(10), ' ')[:44]:44} -> "
                      f"{solved.answer or solved.reply!r}" + ("" if good else f"  (wanted {expected})"))
    median = statistics.median(times)
    report.check(max(times) < 3 * median + 0.1, f"speed steady: median {median * 1000:.0f} ms, "
                                                f"p95 {p95(times) * 1000:.0f} ms, max {max(times) * 1000:.0f} ms")
    report.check(thinking == 0, f"no thinking output ({thinking} of {total} replies)")
    report.check(right >= TRIVIA_TARGET * total, f"trivia answers right: {right} of {total}")


def bench_clip(engine, report):
    """The real recording, through the real reader and solver."""
    print("\nReal riddle clip")
    if not os.path.exists(CLIP):
        print("  skip  clip not found")
        return
    events = []
    engine.on_event = lambda kind, now, **e: events.append((kind, e))
    engine.reset()
    engine.run(frames_from_video(CLIP, RIDDLE_FPS))
    wait_for_answer(events)
    riddles = [e["text"] for kind, e in events if kind == "riddle"]
    answers = [e["solved"].answer for kind, e in events if kind == "answer"]
    report.check(bool(riddles) and similarity(normalize(riddles[0]), normalize(CLIP_TEXT)) >= 95,
                 f"read: {riddles[0] if riddles else 'nothing'}")
    report.check(answers[:1] == ["AUGUST2025"], f"answered: {answers}")


def wait_for_answer(events, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not any(kind in ("answer", "no_answer", "error") for kind, _ in events):
        time.sleep(0.01)


def bench_pipeline(engine, report):
    """Riddles drawn at 1080p and fed at the live frame rate, with a real screen
    grab per frame. A riddle lands at a random moment between two frames, so
    each result counts the worst case: a full frame of waiting, plus the grab."""
    print(f"\nFull pipeline at 1080p, {RIDDLE_FPS} fps, everything from the text appearing to the paste finishing")
    try:
        from sim import Renderer, have_testdata
    except ImportError:
        print("  skip  sim.py not found")
        return
    if not have_testdata():
        print("  skip  testdata not found")
        return
    renderer = Renderer()
    period = 1 / RIDDLE_FPS
    totals, grabs, frame_times = [], [], []
    with mss.MSS() as sct:
        monitor = sct.monitors[1]

        def frames(blank, full):
            t = 0.0
            for i in range(16):
                start = time.perf_counter()
                sct.grab(monitor)
                grabs.append(time.perf_counter() - start)
                yield t, full if i >= 3 else blank
                frame_times.append(time.perf_counter() - start)
                time.sleep(max(0.0, period - (time.perf_counter() - start)))
                t += period

        for n in range(ROUNDS):
            for k, (text, _) in enumerate(TRIVIA):
                base = renderer.background(f"bg{(n * len(TRIVIA) + k) % 9}")
                blank, full = (cv2.resize(renderer.draw(base, lines), (1920, 1080), interpolation=cv2.INTER_LINEAR)
                               for lines in ([], [text]))
                events = []
                engine.on_event = lambda kind, now, **e: events.append((kind, e))
                engine.reset()
                engine.run(frames(blank, full))
                wait_for_answer(events)
                got = [e for kind, e in events if kind == "answer"]
                if got:
                    totals.append(got[0]["total"])
    if not totals:
        report.check(False, "no riddles got through")
        return
    grab = statistics.median(grabs)
    worst = [total + period + grab for total in totals]
    report.check(len(totals) == ROUNDS * len(TRIVIA), f"{len(totals)} of {ROUNDS * len(TRIVIA)} riddles answered")
    report.check(p95(frame_times) < period, f"keeps up with {RIDDLE_FPS} fps: frame work median "
                                            f"{statistics.median(frame_times) * 1000:.0f} ms, p95 {p95(frame_times) * 1000:.0f} ms "
                                            f"of {period * 1000:.0f} ms")
    report.check(p95(worst) < LIMIT, f"under {LIMIT:.0f} s: median {statistics.median(worst):.2f} s, "
                                     f"p95 {p95(worst):.2f} s, max {max(worst):.2f} s")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)
    ap.add_argument("--facts", default=FACTS_PATH, help="facts file to use instead of the normal one")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    # Roblox may well be the active window, so no step may press keys for real.
    engine_module.paste_into = lambda title: time.sleep(PASTE_SECONDS) or True
    report = Report()
    print(f"Open apps: {', '.join(running_apps()) or 'none of Roblox, Chrome, Discord, Spotify'}")
    if "Roblox" not in running_apps():
        print("Roblox isn't open, so this isn't the real test. Open it and run this again.")
    if not os.path.exists(args.facts):
        print(f"No facts file at {args.facts}: trivia can only be guessed.")
    before = gpu_memory()[0]

    def show(kind, now, **e):
        if kind == "error":
            print("error:", e["message"])

    engine = Engine(Options(mode="riddle", model=args.model, facts_path=args.facts), show)
    start = time.perf_counter()
    if not engine.start_ai():
        return 1
    used, total = gpu_memory()
    print(f"Model {args.model} ready in {time.perf_counter() - start:.1f} s. VRAM {before} -> {used} of {total} MiB")
    try:
        report.check(total - used >= LOW_VRAM_MIB, f"VRAM headroom: {total - used} MiB free")
        bench_model(engine, report)
        bench_clip(engine, report)
        bench_pipeline(engine, report)
        used = gpu_memory()[0]
        report.check(total - used >= LOW_VRAM_MIB, f"VRAM after the run: {total - used} MiB free")
    finally:
        engine.stop_ai()
    print("\nGATE " + ("FAILED" if report.failed else "PASSED"))
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())

# MASSAB

Reads promo codes off a Roblox overlay in real time, then copies them and pastes them into the game.

The overlay shows a code one word at a time, in lines that scroll up and disappear after a few seconds:

```
here is the code...
it contains no numbers
SAB
IS
AMAZING
```

MASSAB watches the screen, works out which lines are the code, and joins them into `SABISAMAZING`.

It's built for one overlay style: white outlined text near the top center of the screen, with a red-hat emoji icon before each line. Other overlays won't be detected.

## Setup

Windows only. Tested on Windows 11 with Python 3.14.

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Usage

1. Open the Codes menu in Roblox and click the text box.
2. Start the reader:

```bash
.venv\Scripts\python codereader.py
```

Each code is printed, copied to the clipboard, and pasted into the box:

```
[   5.3s] CODE: KEYBOARDESCAPEIS  (copied and pasted)  [3 words in, will update if more come]
[   7.2s] CODE: KEYBOARDESCAPEISBORING  (copied and pasted)  [updated: another word came in]
[  10.7s] done: KEYBOARDESCAPEISBORING
```

Most codes are 3 words, so the code is pasted as soon as 3 words are in, and replaced if more arrive. Check for an `updated` line before you submit; `done:` means the code has ended. Nothing is submitted for you.

It only pastes when the active window's title is exactly `Roblox`. Otherwise the code is still copied, and the line says it wasn't pasted.

| Option | What it does |
|---|---|
| `--video FILE` | Read a recording instead of the screen |
| `--monitor N` | Monitor to watch (default 1, the primary) |
| `--region x,y,w,h` | Watch only this area, for a video that doesn't fill the screen |
| `--fps N` | Frames to check per second (default 4) |
| `--words N` | Copy once this many words are in (default 3, 0 = wait for the end) |
| `--end-gap N` | Seconds with no new word before a code counts as finished (default 6) |
| `--copy-partial` | Update the clipboard with every new word |
| `--no-paste` | Copy but don't paste |
| `--no-copy` | Don't touch the clipboard, which also stops pasting |
| `--paste-window TITLE` | Paste into the window with this exact title (default `Roblox`) |
| `--verbose` | Print every frame's OCR reads |

## How it works

1. **Find lines.** Each line is located by its icon: a yellow face with a red hat above and a red body below.
2. **Read lines.** The crop is trimmed to the white letters and read with RapidOCR.
3. **Track lines.** Lines are matched between frames by text and position, so each real line gets a vote from every frame it's seen in, and one-off misreads lose.
4. **Assemble the code.** A line containing "code" starts collecting. Hint lines are skipped, and the words after them form the code. A hint, chatter or new intro after the words ends it.

## Known limits

- A code word that is exactly `CODE` looks like a new intro and splits the code.
- Repeated identical words (`GO`, `GO`, `GO`) can gain or lose a copy if a line goes undetected right as another expires.
- All-caps single-word chatter right after a code (`HURRY`) gets added to it.
- Lines shown for under a second may not get enough clean reads.
- Symbols in codes are dropped, so `X-RAY` becomes `XRAY`.

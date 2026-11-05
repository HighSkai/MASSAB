# MASSAB

Reads promo codes and solves riddles off a Roblox overlay in real time, then copies the answer and pastes it into the game. Nothing is submitted for you.

**Codes** come one word at a time, in lines that scroll up and disappear after a few seconds:

```
here is the code...
it contains no numbers
SAB
IS
AMAZING
```

MASSAB works out which lines are the code and joins them into `SABISAMAZING`.

**Riddles** are mostly trivia about the game, in one long message that wraps onto two rows:

```
month and year the first fuse machine in
              sab released
```

A local AI model answers them using a fact sheet, and `AUGUST2025` is pasted in under a second.

It's built for one overlay style: white outlined text near the top center of the screen, with a red-hat emoji icon beside each line. Other overlays won't be detected.

## Setup

Windows only, with an NVIDIA GPU for riddles. Tested on Windows 11, Python 3.14 and an 8 GB RTX 4060.

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python setup_ai.py
```

`setup_ai.py` downloads `llama-server` and the Qwen3.5-4B model (about 3 GB) into `bin\` and `models\`, and checks their hashes. Code mode works without them.

## Usage

1. Double-click `MASSAB.bat`.
2. Open the Codes menu in Roblox and click the text box.
3. Press **Start** in MASSAB and go back to the game.

| Mode | What it does |
|---|---|
| Code | Reads codes only |
| Riddle | Sends longer messages to the AI |
| Auto | Both: "code is..." lines go to the code reader, anything else long goes to the AI |

Press **F8** in the game to switch modes. The hotkey can be changed in Settings.

The strip at the bottom left of the screen shows the mode, the answer, how long it took and whether it pasted. It can't be clicked and never takes focus, because pasting only works while the active window's title is exactly `Roblox`. If it isn't, the answer is still copied.

An answer is pasted as soon as there is one, and replaced if more text arrives. Check it before you submit.

**`GUESS`** means no line of the fact sheet covers the riddle, so the model answered from memory. Don't trust it.

The system prompt can be edited in the **System prompt** tab, and takes effect on the next riddle. The reply has to keep the `ANSWER:` format.

## The fact sheet

`data/sab_facts.md` is what makes trivia work. Without it the model answered `2024` for the riddle above. The AI reads the few lines that best match each riddle, so a wrong line means a confident wrong answer.

- One fact per line, ending in `[source: url]`.
- Lines starting with `#` are ignored.
- Everything under `## Needs review` is ignored. Move a line above it once you've settled it.

Changes apply the next time the AI loads.

## Command line

```bash
.venv\Scripts\python codereader.py
.venv\Scripts\python codereader.py --mode riddle
```

```
[   5.3s] CODE: KEYBOARDESCAPEIS  (copied and pasted)  [3 words in, will update if more come]
[   7.2s] CODE: KEYBOARDESCAPEISBORING  (copied and pasted)  [updated: another word came in]
[  10.7s] done: KEYBOARDESCAPEISBORING
```

| Option | What it does |
|---|---|
| `--mode MODE` | `code`, `riddle` or `auto` (default `code`) |
| `--video FILE` | Read a recording instead of the screen |
| `--monitor N` | Monitor to watch (default 1, the primary) |
| `--region x,y,w,h` | Watch only this area, for a video that doesn't fill the screen |
| `--fps N` | Frames to check per second (default 4, or 12 for riddle and auto) |
| `--words N` | Copy once this many words are in (default 3, 0 = wait for the end) |
| `--end-gap N` | Seconds with no new word before a code counts as finished (default 6) |
| `--copy-partial` | Update the clipboard with every new word |
| `--no-paste` | Copy but don't paste |
| `--no-copy` | Don't touch the clipboard, which also stops pasting |
| `--paste-window TITLE` | Paste into the window with this exact title (default `Roblox`) |
| `--model NAME` | `4b` or the smaller `2b`, which needs `setup_ai.py --model 2b` |
| `--verbose` | Print every frame's OCR reads |

## Checking the speed

```bash
.venv\Scripts\python bench_riddle.py
```

Run it while you're in a game, because Roblox competes with the model for the GPU. It reports the time from text appearing to the paste finishing, counting the worst case for where the text lands between two frames. It overwrites your clipboard, but presses no keys.

## Building the .exe

```bash
.venv\Scripts\python -m pip install pyinstaller==6.22.3
.venv\Scripts\python -m PyInstaller --noconfirm MASSAB.spec
```

The app is the folder `dist\MASSAB`. It keeps its own `data\` and `prompts\`, and needs `bin\` and `models\` inside it. Its **Install AI** button downloads them.

`MASSAB.exe --check` tries screen capture, OCR and the model without opening a window, and writes the result to `check.txt`.

## How it works

Codes:

1. **Find lines.** Each line is located by its icon: a yellow face with a red hat above and a red body below.
2. **Read lines.** The crop is trimmed to the white letters and read with RapidOCR.
3. **Track lines.** Lines are matched between frames by text and position, so each real line gets a vote from every frame it's seen in, and one-off misreads lose.
4. **Assemble the code.** A line containing "code" starts collecting. Hint lines are skipped, and the words after them form the code. A hint, chatter or new intro after the words ends it.

Riddles:

1. **Find rows.** White letters are chained to their neighbors, and only chains centered on the screen count. Rows about 24 pixels apart at 720p are one wrapped message.
2. **Track messages.** Two frames that agree make a riddle. Short intros and hints are left to the code reader.
3. **Pick facts.** The fact sheet lines sharing the riddle's rarest words are chosen.
4. **Ask the model.** `llama-server` runs on localhost with your system prompt, and the reply is streamed so newer text can cancel it.

## Known limits

- A code word that is exactly `CODE` looks like a new intro and splits the code.
- Repeated identical words (`GO`, `GO`, `GO`) can gain or lose a copy if a line goes undetected right as another expires.
- All-caps single-word chatter right after a code (`HURRY`) gets added to it.
- Lines shown for under a second may not get enough clean reads.
- Symbols in codes are dropped, so `X-RAY` becomes `XRAY`.
- The code reader is tuned for 4 frames a second and drops codes at 12, so it only gets every third frame when riddles need more.
- Riddles are only as good as the fact sheet, and the model can still pick the wrong line.
- In Riddle mode any longer line goes to the AI, so chatter like `first one wins` can get an answer pasted.
- A short riddle (5 words or fewer) that uses a hint word like `number`, or mentions `code`, is taken for a hint or intro.
- Only one real riddle recording exists so far, so riddles spread over several messages are untested on real footage.

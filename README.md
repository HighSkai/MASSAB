# MASSAB

**A lightweight, locally hosted AI assistant that detects Roblox stream promo codes and solves game trivia in real time using OCR and GPU-accelerated language models. Features automated code assembly, intelligent riddle solving, and clipboard integration.**

![MASSAB solving a riddle: AUGUST2025, pasted in 0.93 seconds](docs/home-riddle.png)

- **Codes.** Code words arrive one line at a time and scroll away. MASSAB joins them into one code and pastes it as soon as it's in.
- **Riddles.** A small AI on your own GPU answers game trivia from a fact sheet, usually in about a second.
- **Nothing to pick.** It watches for both at once and works out which one is on screen.
- **Never submits.** It types the answer into the Codes box; pressing Redeem is up to you.
- **Runs locally.** No account, no API key, nothing sent anywhere.

## Contents

- [Requirements](#requirements)
- [Getting started](#getting-started)
- [Using MASSAB](#using-massab)
- [Settings](#settings)
- [The fact sheet](#the-fact-sheet)
- [Troubleshooting](#troubleshooting)
- [Command line](#command-line)
- [How it works](#how-it-works)
- [Known limits](#known-limits)
- [Project layout](#project-layout)

## Requirements

| | |
|---|---|
| **System** | Windows 10 or 11 |
| **Python** | 3.14 from [python.org](https://www.python.org/downloads/), with "Add python.exe to PATH" ticked |
| **For riddles** | An NVIDIA GPU with about 3 GB of free VRAM, and 3 GB of disk space for the AI. Codes work without it. |

Tested on Windows 11 with an 8 GB RTX 4060.

## Getting started

1. **Download MASSAB.** On GitHub, click **Code → Download ZIP** and unzip it anywhere, or `git clone` it.
2. **Double-click `MASSAB.bat`.** The first time, it sets up everything Python needs in a `.venv` folder, which takes a few minutes. After that it opens straight away.
3. **Install the AI** (only for riddles). Click **Install AI** at the bottom left. It downloads the AI program and model, about 3 GB, checks them, and loads them. You can close MASSAB partway: the download picks up where it stopped.

   ![The Install AI button showing download progress](docs/install-ai.png)

Once MASSAB has opened, there's also a `MASSAB` shortcut with the M icon in the folder. Pin that to your taskbar or Start menu. MASSAB remakes it whenever it's missing or the folder has moved.

<details>
<summary>Setting up by hand instead</summary>

```bash
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app\setup_ai.py
.venv\Scripts\pythonw app\gui.py
```

`setup_ai.py --model 2b` downloads the smaller model instead, for GPUs with less VRAM.
</details>

## Using MASSAB

1. Open the **Codes** menu in Roblox and click its text box.
2. Press **Start** in MASSAB and go back to the game.
3. When a code or riddle shows up on the stream, MASSAB pastes the answer. Check it, then press Redeem.

![MASSAB after pasting a code](docs/home-code.png)

**Home** shows the last answer, how long reading, the AI and pasting took, and a log of everything MASSAB saw. **Chat**, **Overlay** and **Settings** are in the sidebar; Ctrl+1 to Ctrl+4 switch between them.

A small strip in a corner of the game shows each answer and whether it pasted, so you don't need to look at MASSAB while playing. It can't be clicked and never takes focus, because pasting only works while the active window is titled exactly `Roblox`. If it isn't, the answer is still copied.

### What gets read

Codes come one word at a time, in lines that scroll up and disappear after a few seconds:

```
here is the code...
it contains no numbers
SAB
IS
AMAZING
```

MASSAB works out which lines are the code and pastes `SABISAMAZING`.

Riddles come after an intro, often in one long message that wraps onto two rows:

```
the riddle is
What brainrot is scarino crowino a reskin
of? and what day in may did sab release
```

The answer is pasted as `FISHINOCLOWNINO15`: its parts joined together, the way the streamer's codes are. A riddle called a code, like `the code is the rarity of dragon cannelloni and 67`, is solved too, so the answer is `SECRET67`, not the sentence.

A riddle needs an intro, just as a code does, so everyday chat is left alone:

- **Riddle intros** have the word riddle, trivia, quiz or puzzle, or wording like "the question is": "here is the riddle...", "riddle is", "RIDDLE TIME".
- **Code and prize lines** like "the code is...", "this is for 100 dragons" or "5 skibidis" can lead to either. Only a sentence or question after one counts as a riddle, so `KEYBOARD` stays a code.
- **Lines about one that's over**, like "that was a bad riddle" or "the answer was X", are ignored.

MASSAB is built for one overlay style: white outlined text near the top center of the screen, with a red-hat emoji icon beside each line. Other overlays aren't detected.

### Where it reads

![The Overlay page](docs/overlay.png)

By default MASSAB reads the top half of your main monitor, all the way across, which is where the overlay is. On the **Overlay** page:

- **Pick on screen** lets you drag a box over the part to read, or type it as `x,y,w,h` in pixels. **Top half** and **Whole monitor** are one click.
- For a stream in a browser window, drag across the video's full width, from its top edge down about halfway.
- The **On-screen box** draws the area over the game and can label each line with what was read. It's the quickest way to check MASSAB is looking in the right place, and MASSAB can't see it, so it never reads its own labels.
- The **Game strip** can sit in any corner, in three sizes.

### Chat

The Chat page talks to the same AI that solves riddles, once it's loaded. With **Use the fact sheet** on, questions about the game get the matching lines of the fact sheet. Replies are short, because the model is small. A riddle on screen always comes first and cuts off any reply that's still coming in.

## Settings

![The Settings page](docs/settings.png)

| Setting | What it does |
|---|---|
| **Copy after** | Paste once this many words of a code are in, and again if more come. *Whole code* waits for the end. |
| **Code ends after** | Seconds with no new word before a code counts as finished |
| **Sound on copy** | A short Windows sound whenever a code or answer is copied |
| **Paste automatically** | Off: answers are only copied |
| **Paste into** | Only paste while the active window has exactly this title |
| **Wait after each key** | Raise it if pastes go missing or come out wrong (default 15 ms) |
| **Model** | 4B gives the best answers; 2B uses less VRAM |
| **Load when MASSAB opens** | So the first riddle doesn't wait for the AI to load |
| **Start watching on open** | Starts reading as soon as MASSAB opens |
| **Keep on top** | Keeps the window above the game |
| **Animations** | On, off, or follow Windows' Animation effects setting |

Settings that only take effect when watching starts, like the reading area and pasting, are greyed out until you press Stop. They're saved in `app\settings.json`.

## The fact sheet

`app/data/sab_facts.md` is what makes trivia work. For each riddle the AI gets the few lines that best match it. If no lines cover most of the riddle, it gets none, and the answer is marked **GUESS**: don't trust those.

- One fact per line, ending in `[source: url]`.
- Lines starting with `#` are ignored, and so is everything under `## Needs review`.
- When the streamer reveals an answer, add what it proves to `## Answers Sammy confirmed`.

**Settings → Fact sheet → Open** opens it. Changes apply the next time the AI loads. The AI's instructions are in `app/prompts/riddle_system.txt`; replies must keep the `ANSWER:` format, and `ANSWER: NONE` means nothing is pasted.

## Troubleshooting

| Problem | Fix |
|---|---|
| `MASSAB.bat` says Python isn't installed | Install Python 3.14 from python.org with "Add python.exe to PATH" ticked, then run it again |
| Nothing is read | Set **On-screen box** to *Always* on the Overlay page and check the box covers the overlay. For a stream in a browser, pick the video's area. |
| Answers are copied but not pasted | The game window must be active and titled exactly `Roblox`, or change **Paste into** |
| Pastes miss letters | Raise **Wait after each key** in Settings |
| Riddles are slow | Close other things using the GPU. The VRAM meter at the bottom left turns red when it's nearly full. |
| The AI says it isn't installed | Click **Install AI** again. A model that's already there and passes its check isn't downloaded twice. |
| Screen capture stops at a lock screen | Normal: Windows blocks it there. Watching carries on by itself afterwards. |

## Command line

```bash
.venv\Scripts\python app\codereader.py
```

This reads codes and riddles together, like the window does, and prints what it finds:

```
[   5.3s] CODE: KEYBOARDESCAPEIS  (copied and pasted)  [3 words in, will update if more come]
[   7.2s] CODE: KEYBOARDESCAPEISBORING  (copied and pasted)  [updated: another word came in]
[  10.7s] done: KEYBOARDESCAPEISBORING
```

| Option | What it does |
|---|---|
| `--video FILE` | Read a recording instead of the screen |
| `--monitor N` | Monitor to watch (default 1, the primary) |
| `--region x,y,w,h` | Read only this area (default: the top half, all the way across) |
| `--fps N` | Frames to check per second (default 12); the code reader gets about 4 of them |
| `--words N` | Copy once this many words are in (default 3, 0 = wait for the end) |
| `--end-gap N` | Seconds with no new word before a code counts as finished (default 6) |
| `--copy-partial` | Update the clipboard with every new word |
| `--no-paste` | Copy but don't paste |
| `--no-copy` | Don't touch the clipboard, which also stops pasting |
| `--paste-window TITLE` | Paste into the window with this exact title (default `Roblox`) |
| `--key-delay N` | Milliseconds to wait after each key of a paste (default 15) |
| `--model NAME` | `4b`, or the smaller `2b` |
| `--verbose` | Print every frame's OCR reads |

`tests\bench_riddle.py` checks that riddles are solved and pasted in under 2 seconds on your PC. Run it while you're in a game, since Roblox shares the GPU. It overwrites your clipboard but presses no keys.

## How it works

**Codes**

1. **Find lines.** Each line is found by its icon: a yellow face with a red hat above and a red body below.
2. **Read lines.** The crop is trimmed to the white letters and read with RapidOCR.
3. **Track lines.** Lines are matched between frames by text and position, so each real line gets a vote from every frame it's seen in, and one-off misreads lose.
4. **Assemble the code.** A line containing "code" starts collecting. Hint lines are skipped, and the words after them form the code. Chatter or a new intro ends it. The intro waits up to 20 seconds for the first word, because streamers often pause after "the code is...".

**Riddles**

1. **Find rows.** White letters are chained to their neighbors, and only chains centered on the screen count. Rows about 24 pixels apart at 720p are one wrapped message.
2. **Wait for an intro.** Nothing counts until a riddle, code or prize intro. Lines above it came before it, so they're ignored.
3. **Track messages.** Two frames that agree make a riddle. A message of 5 or more words, or one ending in `?`, is the whole riddle; after a riddle intro, shorter lines add up like a code's words.
4. **Pick facts.** The fact sheet lines sharing the riddle's rarest words are chosen.
5. **Ask the model.** `llama-server` runs on localhost, and the reply is streamed so newer text can cancel it.
6. **Finish the answer.** Exact steps are applied in code: `3 times` repeats the answer, a final `and 67` adds the number, and `and the day today` adds today's date.

## Known limits

- Only white letters with a dark outline are read, like the overlay's own. Coloured text, very large text, or a blurry stream can be missed.
- A code word that is exactly `CODE` looks like a new intro and splits the code. Symbols are dropped, so `X-RAY` becomes `XRAY`.
- Repeated words (`GO`, `GO`, `GO`) can gain or lose a copy if a line goes undetected right as another expires.
- All-caps chatter right after a code (`HURRY`, `GG`) can be added to it.
- Short number lines like `11` are read with low confidence and can be dropped.
- Riddles are only as good as the fact sheet. Riddles about today, like "the most op brainrot that released today", can't be answered from it, and `and the day today` uses this PC's date.
- A riddle with no intro is missed. A chatty sentence within 8 seconds of an intro can reach the AI; it answers `NONE` to most, but not all.
- A riddle told as several full sentences only gets its first one, and up to 2 seconds of short chatter right after a short riddle can join it.

## Project layout

```
MASSAB.bat            starts MASSAB, and sets it up the first time
requirements.txt      the Python packages it needs, pinned
app/
  gui.py              the window
  engine.py           the capture loop behind the window and the command line
  codereader.py       finds and reads code lines, and assembles codes
  riddle.py           finds riddle rows, tracks riddles, and talks to the AI
  overlay.py          the on-screen box and area picker
  chat.py             the Chat page's model calls
  theme.py            colors, fonts and custom widgets
  setup_ai.py         downloads and checks the AI (also run by Install AI)
  shortcut.py         makes the MASSAB shortcut
  data/sab_facts.md   the fact sheet
  prompts/            the AI's instructions
  fonts/              Big Shoulders Display and Martian Mono (SIL Open Font License)
  bin/, models/       the AI, once installed (not in git)
tests/bench_riddle.py checks riddle speed on this PC
docs/                 the screenshots in this README
```

The fonts' licenses are next to them in `app\fonts\`. Body text uses Windows' Segoe UI.

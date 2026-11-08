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

**Riddles** are mostly trivia about the game. They come after an intro, in one long message that wraps onto two rows:

```
the riddle is
What brainrot is scarino crowino a reskin
of? and what day in may did sab release
```

A local AI model answers them using a fact sheet, and `FISHINOCLOWNINO15` is pasted in about a second. The parts of an answer are joined together, the way Sammy's codes are.

Sammy often calls a riddle a code: `the code is the rarity of dragon cannelloni and 67`. MASSAB treats that as a riddle, so the answer is `SECRET67`, not the sentence.

It's built for one overlay style: white outlined text near the top center of the screen, with a red-hat emoji icon beside each line. Other overlays won't be detected.

## Setup

Windows only, with an NVIDIA GPU for riddles. Tested on Windows 11, Python 3.14 and an 8 GB RTX 4060.

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python setup_ai.py
```

`setup_ai.py` downloads `llama-server` and the Qwen3.5-4B model (about 3 GB) into `bin\` and `models\`, and checks their hashes. Without them MASSAB still reads codes, but can't solve riddles.

## Usage

1. Double-click `MASSAB.bat`.
2. Open the Codes menu in Roblox and click the text box.
3. Press **Start** in MASSAB and go back to the game.

There's nothing to pick. MASSAB watches for codes and riddles at the same time and works out which one is on screen.

A riddle needs an intro, the same way a code does, so everyday chat is left alone:

- **Riddle intros** have the word riddle, trivia, quiz or puzzle, or wording like "the question is": "here is the riddle...", "riddle is", "next riddle:", "RIDDLE TIME". Every line after one is part of the riddle.
- **Code and prize lines** may lead to a riddle or a plain code: "the code is...", "this is for 100 dragons", "5 skibidis". Only a sentence or question after one counts as a riddle, so `KEYBOARD` stays a code.

The riddle can be on the same line as either kind. Lines about one that's over, like "that was a bad riddle", "the code was X" or "the answer was X", are ignored.

The window has four pages:

| Page | What's on it |
|---|---|
| Home | The last answer, with how long each step took, and a log of everything that happened |
| Chat | Ask the AI anything. It's the riddle model, so it's quick but small |
| Overlay | Where on screen MASSAB reads, a box that shows it over the game, and the strip |
| Settings | Codes, pasting and the AI |

The strip at the bottom left of the screen shows whether it's a code or a riddle, the answer, how long it took and whether it pasted. It can't be clicked and never takes focus, because pasting only works while the active window's title is exactly `Roblox`. If it isn't, the answer is still copied. Its corner, size and how see-through it is are on the Overlay page.

### The reading area and box

MASSAB reads the whole monitor unless you give it an area. On the Overlay page, **Pick on screen** lets you drag a box over the part to read, or type it as `x,y,w,h` in pixels. The preview shows where it is, with the zones inside it where code lines and riddle rows are looked for.

**Show the box** draws that area over the game: never, while watching, or always. It can also mark the two zones, and highlight each line of text as it's read, labeled with what OCR made of it. That's the quickest way to check MASSAB is looking in the right place. The box can't be clicked and is hidden from screen capture, so MASSAB never reads its own labels. Its color, line width and opacity can be changed.

Settings that only take effect when watching starts, like the area and pasting, are greyed out until you press Stop.

### Chat

The Chat page talks to the same model that solves riddles, once it's loaded. With **Fact sheet** on, questions about the game get the matching lines of `data/sab_facts.md`, like riddles do. Replies are short, because the model only has room for about the last 3,000 characters of the chat.

The model can only do one thing at a time, so a riddle on screen always comes first: it cuts off any reply that's still coming in.

An answer is pasted as soon as there is one, and replaced if more of the riddle arrives. Check it before you submit.

If Windows blocks screen capture, for example at a lock screen or admin prompt, the log says so and watching carries on by itself once it's gone.

A paste presses six keys with a short wait after each, 15 ms by default, so Roblox sees every one. If pastes go missing or come out wrong, raise **Wait after each pasted key** in Settings.

**`GUESS`** means no line of the fact sheet covers the riddle, so the model answered from memory. Don't trust it.

The riddle system prompt is `prompts/riddle_system.txt`, and takes effect the next time the AI loads. The reply has to keep the `ANSWER:` format. When the model replies `ANSWER: NONE`, nothing is pasted.

## The fact sheet

`data/sab_facts.md` is what makes trivia work. Without it the model answered `2024` when asked what month and year the first fuse machine released. The AI reads the few lines that best match each riddle, so a wrong line means a confident wrong answer. If those lines don't cover most of the riddle, it gets no facts at all, because loosely related ones pull it toward game terms.

When Sammy reveals an answer, it's worth adding what it proves to the `## Answers Sammy confirmed` section.

- One fact per line, ending in `[source: url]`.
- Lines starting with `#` are ignored.
- Everything under `## Needs review` is ignored. Move a line above it once you've settled it.

Changes apply the next time the AI loads.

## Command line

```bash
.venv\Scripts\python codereader.py
```

It reads codes and riddles together, like the window does. Without the AI installed it still reads codes.

```
[   5.3s] CODE: KEYBOARDESCAPEIS  (copied and pasted)  [3 words in, will update if more come]
[   7.2s] CODE: KEYBOARDESCAPEISBORING  (copied and pasted)  [updated: another word came in]
[  10.7s] done: KEYBOARDESCAPEISBORING
```

| Option | What it does |
|---|---|
| `--video FILE` | Read a recording instead of the screen |
| `--monitor N` | Monitor to watch (default 1, the primary) |
| `--region x,y,w,h` | Watch only this area, for a video that doesn't fill the screen |
| `--fps N` | Frames to check per second (default 12). The code reader only gets about 4 of them |
| `--words N` | Copy once this many words are in (default 3, 0 = wait for the end) |
| `--end-gap N` | Seconds with no new word before a code counts as finished (default 6) |
| `--copy-partial` | Update the clipboard with every new word |
| `--no-paste` | Copy but don't paste |
| `--no-copy` | Don't touch the clipboard, which also stops pasting |
| `--paste-window TITLE` | Paste into the window with this exact title (default `Roblox`) |
| `--key-delay N` | Milliseconds to wait after each key of a paste (default 15) |
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
2. **Wait for an intro.** Nothing counts until a riddle, code or prize intro. Lines above it came before it, so they're ignored.
3. **Track messages.** Two frames that agree make a riddle. A message of 5 or more words, or one ending in `?`, is the whole riddle. After a riddle intro, shorter lines add up, like the words of a code.
4. **Pick facts.** The fact sheet lines sharing the riddle's rarest words are chosen.
5. **Ask the model.** `llama-server` runs on localhost with your system prompt, and the reply is streamed so newer text can cancel it. If it refuses with facts in front of it, it's asked once more without them.
6. **Finish the answer.** Exact steps are kept from the model and applied in code: `3 times` repeats the answer, a final `and 67` or `, 67` adds the number, and `and the day today` adds today's date.

## Known limits

- A code word that is exactly `CODE` looks like a new intro and splits the code.
- Repeated identical words (`GO`, `GO`, `GO`) can gain or lose a copy if a line goes undetected right as another expires.
- All-caps single-word chatter right after a code (`HURRY`) gets added to it.
- Lines shown for under a second may not get enough clean reads.
- Symbols in codes are dropped, so `X-RAY` becomes `XRAY`.
- The code reader is tuned for 4 frames a second and drops codes at 12, so it only gets every third frame when riddles need more.
- Riddles are only as good as the fact sheet, and the model can still pick the wrong line. Riddles about the day, like "the most op brainrot that released today", can't be answered from it.
- `and the day today` uses this PC's date, so it's the day of the month where you are.
- A riddle with no intro is missed, like `may favorite color 3 times and 67` in one recording, where the video starts at that line.
- A chatty sentence within 8 seconds of an intro can reach the AI. It replies `NONE` to many of them, but not all, so a wrong answer can get pasted.
- A plain code written as a sentence after "the code is" is treated as a riddle.
- A riddle told as several full sentences only gets its first one, because a message of 5 or more words closes it.
- Up to 2 seconds of short chatter right after a short riddle can join it.
- A short riddle line (5 words or fewer) that uses a hint word like `number`, or mentions `code`, is taken for a hint or intro.
- Row reading needs the overlay centered in what's being watched. For a video in a browser, set the area to the video. Editing zooms in recordings can still cut rows short, which doesn't happen live.

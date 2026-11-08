# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Steal a Brainrot (SAB) players on Windows who watch Sammy's (SpyderSammy's) live streams, where codes and riddles appear on an overlay and the first players to enter the right answer win. MASSAB is public: anyone can find the repo or the `.exe`, and they set it up alone, with no one to ask when something breaks.

While it's watching, the player's attention is on the game. They're racing other viewers with the Codes box in Roblox focused. They glance at the strip in the corner of the screen, check the answer that was pasted, and press Enter themselves. The window is where they set things up before a stream and look back afterwards: the last answer, the log, the reading area and the settings.

## Product Purpose

MASSAB reads promo codes and solves riddles off Sammy's overlay in real time, copies the answer and pastes it into the Roblox Codes box, usually within about a second. Codes arrive one word per line and are joined. Riddles, which are mostly game trivia, are answered by a local AI model using a cited fact sheet.

Success is the right answer sitting in the Codes box before other viewers have typed theirs, with the player still the one who submits it.

## Positioning

- It's built for one overlay: white outlined text near the top center, with a red-hat emoji icon beside each line. It finds lines by that icon and tracks them across frames, so one-off misreads get outvoted.
- Riddles are answered from `data/sab_facts.md`, a sourced fact sheet with one fact per line. The model only sees facts when they cover most of the riddle. When none do, the answer is marked `GUESS`.
- It runs entirely on the player's PC: OCR, the model and `llama-server` on localhost.
- It stops at the paste. Nothing is ever submitted for the player.

## Operating Context

- Roblox runs fullscreen or windowed with the Codes menu open and its text box clicked. Pasting only works while the active window's title is exactly `Roblox`. Otherwise the answer is still copied.
- The flow is: open MASSAB, press Start, go back to the game. There are no modes to pick, because codes and riddles are watched at the same time.
- Roblox and the model share the GPU (tested on an 8 GB RTX 4060). VRAM is shown in the window.
- Before or after a stream, players tune the reading area by dragging a box on screen, check it with the on-screen box, and read the log. They may also edit the fact sheet and `prompts/riddle_system.txt`.
- Players who run it from source use `MASSAB.bat` and `setup_ai.py`. Others use the `dist\MASSAB` folder and its Install AI button, which downloads about 3 GB.

## Capabilities and Constraints

- **Runtime:** this is a Windows-only desktop app built on PySide6 (Qt 6), not a browser app. `web` is recorded under Platform only because the field has no desktop value. Styling is Qt style sheets plus QPainter-drawn widgets in `theme.py`, and Qt style sheets can't do CSS features like box shadows or blur. It ships as a PyInstaller one-folder build.
- **Surfaces:** the main window has four pages: Home (the last answer, step timings and the activity log), Chat (talks to the riddle model and gives way to riddles), Overlay (the reading area, the on-screen box and the strip) and Settings (codes, pasting and the AI). There's also the strip, the on-screen box and the area picker.
- **The strip and the box** are drawn over the game. They can't be clicked, never take focus and are hidden from screen capture, so MASSAB never reads its own labels and pasting keeps working.
- **Locked settings:** settings that only take effect when watching starts are greyed out until the player presses Stop.
- **Without the AI** installed, MASSAB still reads codes. Riddles and Chat need it.
- **Known limits** are listed in the README, and future work shouldn't claim to have fixed them unless it actually has.
- **Terms used in the app:**
  - code, riddle, intro, hint line
  - the strip (the in-game HUD), the box (the on-screen reading box), reading area, zones (code lines, riddle rows)
  - fact sheet, `GUESS`, `NONE`
  - Brainrot, SAB, Sammy

## Evidence on Hand

- `data/sab_facts.md`: the researched fact sheet. Every line carries a `[source: url]`, and there's a `## Needs review` section and a `## Answers Sammy confirmed` section.
- `bench_riddle.py` measures the time from text appearing to the paste finishing. It's the only basis for any speed claim.
- `testdata/` holds local test recordings cut from other people's videos. They're gitignored, and they must never be published or used as product imagery.
- There's no logo. The window shows the title MASSAB in Big Shoulders Display, and the taskbar icon is just its letter M, drawn in code (`theme.window_icon`). There's no logo image file.
- The bundled fonts, Big Shoulders Display and Martian Mono, are in `fonts\` under the SIL Open Font License, with their licenses.
- There are no screenshots, testimonials, download counts or user reports. Don't invent any.

## Product Principles

1. **The player submits.** MASSAB gets the answer into the box, and the player checks it and presses Enter. No feature may submit, confirm or press Enter for them.
2. **Readable at a glance, mid-race.** Anything the player needs while watching must be readable from the strip in a moment, without clicking or switching windows. The window is for setup and review.
3. **Fast, and honest about confidence.** Paste as soon as there's an answer and replace it if more arrives, but always make `GUESS` and other low-confidence states visible. Never hide uncertainty to look faster.
4. **Never fight the game for focus.** Nothing MASSAB shows over the game may take focus, accept clicks or appear in its own screen capture.
5. **Local and self-explaining.** Everything runs on the player's PC, with no cloud AI, accounts or telemetry. Downloads happen only at setup. Because public users have no one to ask, every state, error and greyed-out control has to say what's happening and what to do.

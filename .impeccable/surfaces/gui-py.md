---
version: 1
slug: "gui-py"
primary_target: "gui.py"
related_targets: ["overlay.py","theme.py"]
---

# Surface: MASSAB control window

Scope: the desktop control window (`gui.py`), plus everything else it draws: the game strip, the on-screen box and the area picker (`overlay.py`). Visitor mode: Operate. The player sets things up before a stream, presses Start, and looks back at the last answer and the log afterwards.

Pinned by the user (2026-11-08, second redesign; this replaces the dark-glass direction):
- **Look:** a dark, minimalist UI that feels brutalist. The color and layout references are seven dark dashboards: the ByeWind/SnowUI eCommerce dashboard, CMSolutions, a black finance overview, an "Automation Operations" console and a dark customer-card grid.
- **Type:** sharp, niche, distinctive fonts that work for both minimalist and brutalist.
- **Motion:** smooth, springy, Apple-style hops for animations and transitions.
- **Copy:** clean, simple and functional.
- **Branding:** no logo, just a text title.
- **Fonts chosen by the user:** Big Shoulders Display and Martian Mono, bundled under OFL in `fonts/`. Body text stays Segoe UI Variable.

Apple sources behind the motion and the fundamentals:
- WWDC23 "Animate with springs": duration and bounce, velocity carried through retargets, bounce 0 as the default, about 0.15 for a small bounce and 0.3 for a noticeable one.
- WWDC18 "Designing Fluid Interfaces": interruptible and redirectable, spatial consistency, bounce used deliberately.
- HIG Motion: purposeful, brief and precise, limited on frequent interactions, cancellable, and optional.
- WWDC17 "Essential Design Principles": wayfinding, feedback, visibility, consistency, proximity, grouping, progressive disclosure.

## Direction contract

THESIS: A black instrument sheet. Flat near-black planes are cut by 1px rules, with tall condensed poster type for names and the answer and crisp monospace for every label and number. The last answer sits on the one light slab on screen. This replaces the glowing glass dashboard (gradients, glows, glass, rounded capsules): there's no light source and no glass, only value steps and lines.

OWN-WORLD:
- **Surfaces:**
  - The ground is #0b0b0c, panels are #131314, and raised and hover states are #1b1b1d.
  - Rules are 1px #232326, and a strong rule is #3a3a40.
  - Corners are 2px, so they read as square.
- **Text:** #ededee, #9b9ba3 and #81818a.
- **The answer slab:** an ice-white slab (#e4ecf2) with black ink.
- **Accent:** ice blue (#a9c8e0) for focus and selection details only.
- **Signals:** mint green (live, pasted), amber (guess, loading) and coral red (stop, error, low VRAM).
- **Type roles:**
  - Big Shoulders Display Black/ExtraBold for the title, the uppercase page titles and the answer.
  - Martian Mono for the uppercase labels, buttons, chips, numbers and the log.
  - Segoe UI Variable for body text.
- **Shapes:**
  - Toggles, segmented controls, swatches and status dots are square.
  - The primary action is a white block with black text.
  - There are no shadows and no gradients.

STORY: The player sees in one glance whether MASSAB is watching, what the last answer was, whether it pasted, and how long it took. They set up the reading area and preferences in ruled panels, press Start, and go back to the game.

FIRST VIEWPORT: 980 × 640.
- **Left rail (200px, the ground color, a 1px rule on its right):**
  - The title MASSAB in Big Shoulders Black, 23pt, smaller than the page title so the page leads.
  - Four text tabs in mono with their Ctrl+1–4 shortcut numbers, and a raised block that springs to the chosen tab.
  - The AI state and VRAM at the bottom.
- **Main header:** the uppercase page title in Big Shoulders ExtraBold at 28pt, a mono status with a square dot, and the white START block. A 1px rule sits under the header.
- **Home:**
  - The ice answer slab: the answer at 44pt, the riddle text, mono chips for kind, paste and guess, the total in Big Shoulders, and the read/AI/paste bar in three greys and black.
  - The bar's stages are grey (read), steel blue #3f6482 (AI) and black (paste). The blue is the references' pale chart blue, darkened to read on the light slab.
  - Below it, the activity panel with the mono log.

FORM: Pinned by the user from references. The direction roll ran afterwards for the record, and a user-pinned decision beats the roll, so its assignment wasn't used.
- **Signature moves:**
  - The ice answer slab with its proportional timing bar.
  - The rail's selection block springing between tabs (0.42s, bounce 0.35, launched toward the tab, so it overshoots about 4–5px on a one-tab move).
  - Pages hop in from the side they live on: later tabs rise from below and earlier ones drop from above. They travel 36px at 0.5s, bounce 0.35, launched at 450px/s, so they overshoot about 5px. The old page fades out over 0.22s.
- **Motion:**
  - All motion is a duration/bounce spring that keeps its velocity when interrupted.
  - Toggles (bounce 0.32) and segmented controls (bounce 0.3) are springy.
  - The timing bar grows smoothly with no bounce.
  - With Windows' animation effects off, things snap to their place.
seed:13b9307a10193998

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

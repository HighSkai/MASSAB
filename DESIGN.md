---
name: MASSAB
description: A floating glass control window over a deep indigo sky, built to read Sammy's codes and riddles and paste the answer.
colors:
  accent-blue: "#4d7cff"
  accent-light: "#7c9dff"
  gradient-bright: "#6a93ff"
  gradient-deep: "#3a5ef0"
  chip-ink-blue: "#c9d6ff"
  stage-violet: "#8a6bff"
  stage-cyan: "#3cc8ff"
  signal-green: "#2fd38a"
  signal-amber: "#ffb547"
  signal-red: "#ff5a6e"
  strip-green: "#4ee6a0"
  strip-amber: "#ffc35c"
  chip-ink-green: "#93f0c4"
  chip-ink-amber: "#ffd08a"
  chip-ink-red: "#ffc6cd"
  stop-ink: "#ffd9de"
  ink: "#f3f5ff"
  ink-secondary: "#aab3d8"
  ink-tertiary: "#858fb6"
  log-ink: "#cdd3f0"
  dim-slate: "#5d6690"
  ground: "#0b1140"
  popup: "#151b48"
  backdrop-top: "#0d1546"
  backdrop-mid: "#080c2a"
  backdrop-floor: "#04061a"
  glow-blue: "#2f5bff"
  glow-violet: "#7b3cff"
  glow-azure: "#0090ff"
  glass-panel: "rgba(12, 17, 50, 0.55)"
  glass-rail: "rgba(14, 19, 56, 0.59)"
  glass-hero: "rgba(14, 20, 60, 0.55)"
  well: "rgba(0, 0, 0, 0.25)"
  strip-glass-top: "#1c2456"
  strip-glass-floor: "#080b22"
  tag-glass: "rgba(10, 14, 40, 0.88)"
typography:
  display:
    fontFamily: "Segoe UI Variable Display Semibold, Segoe UI Semibold, Segoe UI, sans-serif"
    fontSize: "30pt"
    fontWeight: 600
    lineHeight: 1.1
  headline:
    fontFamily: "Segoe UI Variable Display Semibold, Segoe UI Semibold, Segoe UI, sans-serif"
    fontSize: "20pt"
    fontWeight: 600
  title-large:
    fontFamily: "Segoe UI Variable Display Semibold, Segoe UI Semibold, Segoe UI, sans-serif"
    fontSize: "14pt"
    fontWeight: 600
  brand:
    fontFamily: "Segoe UI Variable Display Semibold, Segoe UI Semibold, Segoe UI, sans-serif"
    fontSize: "13pt"
    fontWeight: 600
  title:
    fontFamily: "Segoe UI Variable Text Semibold, Segoe UI Semibold, Segoe UI, sans-serif"
    fontSize: "11pt"
    fontWeight: 600
  body:
    fontFamily: "Segoe UI Variable Text, Segoe UI, sans-serif"
    fontSize: "10pt"
    fontWeight: 400
  label:
    fontFamily: "Segoe UI Variable Text Semibold, Segoe UI Semibold, Segoe UI, sans-serif"
    fontSize: "9.5pt"
    fontWeight: 600
  caption:
    fontFamily: "Segoe UI Variable Text, Segoe UI, sans-serif"
    fontSize: "9pt"
    fontWeight: 400
  chip:
    fontFamily: "Segoe UI Variable Text Semibold, Segoe UI Semibold, Segoe UI, sans-serif"
    fontSize: "8.5pt"
    fontWeight: 600
  mono:
    fontFamily: "Cascadia Mono, Consolas, monospace"
    fontSize: "9pt"
    fontWeight: 400
rounded:
  bar: "2px"
  menu-item: "6px"
  field: "11px"
  control: "14px"
  button: "16px"
  capsule: "18px"
  panel: "22px"
  rail: "24px"
spacing:
  hair: "2px"
  xs: "4px"
  sm: "8px"
  md: "10px"
  lg: "16px"
  panel: "18px"
  xl: "22px"
  brand-gap: "26px"
components:
  button:
    backgroundColor: "rgba(255, 255, 255, 0.08)"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.button}"
    padding: "7px 16px"
  button-hover:
    backgroundColor: "rgba(255, 255, 255, 0.14)"
  button-primary:
    backgroundColor: "{colors.gradient-bright}"
    textColor: "#ffffff"
    typography: "{typography.label}"
    rounded: "{rounded.button}"
    padding: "7px 16px"
  button-primary-hover:
    backgroundColor: "#82a5ff"
  button-small:
    backgroundColor: "rgba(255, 255, 255, 0.08)"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "5px 13px"
  button-start:
    backgroundColor: "{colors.gradient-bright}"
    textColor: "#ffffff"
    rounded: "{rounded.capsule}"
    padding: "0 28px"
    height: "36px"
  button-stop:
    backgroundColor: "rgba(255, 90, 110, 0.18)"
    textColor: "{colors.stop-ink}"
    rounded: "{rounded.capsule}"
    padding: "0 28px"
    height: "36px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "40px"
  nav-item-active:
    backgroundColor: "rgba(106, 147, 255, 0.31)"
    textColor: "{colors.ink}"
  input:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "6px 10px"
  input-focus:
    backgroundColor: "rgba(0, 0, 0, 0.33)"
  chip-kind:
    backgroundColor: "rgba(77, 124, 255, 0.18)"
    textColor: "{colors.chip-ink-blue}"
    typography: "{typography.chip}"
    rounded: "{rounded.field}"
    padding: "0 10px"
    height: "22px"
  chip-pasted:
    backgroundColor: "rgba(47, 211, 138, 0.13)"
    textColor: "{colors.chip-ink-green}"
    rounded: "{rounded.field}"
    height: "22px"
  chip-guess:
    backgroundColor: "rgba(255, 181, 71, 0.13)"
    textColor: "{colors.chip-ink-amber}"
    typography: "{typography.caption}"
    rounded: "{rounded.field}"
    padding: "0 11px"
    height: "22px"
  glass-panel:
    backgroundColor: "{colors.glass-panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "18px"
  glass-rail:
    backgroundColor: "{colors.glass-rail}"
    rounded: "{rounded.rail}"
    padding: "12px"
    width: "228px"
  bubble-user:
    backgroundColor: "{colors.gradient-bright}"
    textColor: "#ffffff"
    rounded: "{rounded.capsule}"
    padding: "10px 15px"
  bubble-ai:
    backgroundColor: "rgba(255, 255, 255, 0.07)"
    textColor: "{colors.ink}"
    rounded: "{rounded.capsule}"
    padding: "10px 15px"
  strip:
    backgroundColor: "{colors.strip-glass-top}"
    textColor: "#ffffff"
    height: "36px"
    padding: "6px 16px 6px 8px"
---

# Design System: MASSAB

## Overview

**Creative North Star: "The Floating Glass Console"** (the documenter's name for it, drawn from the direction contract's thesis; the user didn't name one.)

MASSAB is one glass control window floating over a deep indigo sky. A dark navy-to-black backdrop carries three large soft glows (blue top-left, violet top-right, azure from below) and a faint grain. Frosted navy glass panels float on it, each with a 1px rim lit from the top-left and a soft dark shadow. A frosted side rail holds four icon tabs, and a glass pill slides between them. Pages cross-fade inside the one shell rather than swapping, so the window reads as a single console and not as a settings form. The look pairs the Vision UI dashboard with Apple Vision Pro (visionOS) glass. The user pinned that direction.

The last answer is the brightest object on screen. It is the only 30pt type, and it sits in the hero panel, which catches extra accent light. A proportional read → AI → paste bar sits under it. Everything else is quieter: lavender-gray secondary text, capsule controls, and grouped rows split by hairlines. The density is calm. Setup happens here between streams, while the race itself happens in the game, watched through the strip.

Anything drawn over the game uses the same dark glass at a smaller scale, with white text. The strip and the box can't be clicked, never take focus, and are hidden from screen capture. The light Frutiger Aero look (a light sky, light glass cards and gloss buttons) is retired, and nothing from it carries forward.

**Key Characteristics:**
- Deep indigo backdrop with large soft color glows and a 2.8% grain.
- Navy-tinted glass panels with a top-left-lit 1px rim and a painted soft shadow.
- One electric-blue accent for selection and primary actions, and three signal colors for state.
- Capsule controls throughout, with painted switches, segmented pills and a sliding rail pill.
- Exponential ease-out motion at 220–260ms, with one long 700ms moment (the answer bar growing).
- Over-game surfaces are dark glass with white text, and they are passive.

## Colors

A night-sky palette: navy and near-black grounds, white-alpha glass, one electric blue, and a strict green / amber / red signal set.

### Primary
- **Electric Blue** (accent-blue): the one accent. It marks selection (menu and list highlights, text selection, the Segmented pill, the rail pill's tint, the kind chip), progress and primary actions. On buttons, the toggle's on state and the user's chat bubbles, it's applied as a diagonal gradient from **Bright Periwinkle** (gradient-bright) to **Deep Cobalt** (gradient-deep).
- **Periwinkle Light** (accent-light): focus rings and borders on every control, and links.
- **Ice Blue Ink** (chip-ink-blue): text on blue-tinted chips.

### Secondary
- **Stage Cyan** (stage-cyan): the "Read" stage of the answer bar, the start of the VRAM bar's gradient, and the on-screen box's default color.
- **Stage Violet** (stage-violet): the "AI" stage of the answer bar.

### Tertiary (signals)
- **Live Green** (signal-green): live and pasted. Used for the status light while watching, "AI ready", the pasted chip's tint and the "Paste" stage of the answer bar.
- **Guess Amber** (signal-amber): guess and loading. Used for the guess chip, the lock note, and the AI light while loading or downloading.
- **Stop Red** (signal-red): stop, error and low VRAM. Used for the Start button while running (as Stop), invalid fields, error bubbles and the VRAM bar when free memory is under 500 MB.
- **Strip Green / Strip Amber** (strip-green, strip-amber): brighter versions of the signals for the strip's "pasted" and "guess" words, so they hold up over any game.
- **Chip inks** (chip-ink-green, chip-ink-amber, chip-ink-red, stop-ink): pale tints of each signal, used for text on that signal's translucent fill.

### Neutral
- **Moon White** (ink): primary text on every surface.
- **Lavender Gray** (ink-secondary): secondary text, unselected tabs and segments, chevrons, and answer-bar legends.
- **Dusk Gray** (ink-tertiary): hints, placeholders, empty states and the empty answer.
- **Log Ink** (log-ink): monospace log text.
- **Dim Slate** (dim-slate): the off/gray status light and disabled icons.
- **Midnight Ground** (ground): the window palette base and the Windows title bar (set through DWM to match the top of the backdrop).
- **Popup Navy** (popup): menus, drop-down lists and tooltips. These are solid because Qt can't blur them.
- **Backdrop** (backdrop-top → backdrop-mid → backdrop-floor): the diagonal base gradient. **Glow Blue**, **Glow Violet** and **Glow Azure** are the three radial lights painted over it.
- **Glass** (glass-panel, glass-rail, glass-hero): the navy tint of each glass kind, before its white sheen.
- **Well** (well): the black-alpha inset behind inputs. The log and the Segmented track use the same kind of well.
- **Over-game glass** (strip-glass-top → strip-glass-floor, tag-glass): the strip's vertical gradient and the box tags' fill.

### Named Rules
**The One Blue Rule.** Electric Blue marks selection and primary actions, and nothing else. It never signals state.

**The Signal Trio Rule.** Green means live or pasted, amber means guess or loading, and red means stop, error or low VRAM. These colors are never decorative, and no fourth state color exists.

**The Amber Guess Rule.** A guess is always flagged in amber: a "Guess: …" chip on Home and a "guess" word on the strip. It stays visible beside "pasted", because a pasted guess is still a guess.

## Typography

**Display Font:** Segoe UI Variable Display Semibold (with Segoe UI Semibold, then Segoe UI 600)
**Body Font:** Segoe UI Variable Text (with Segoe UI)
**Label/Mono Font:** Segoe UI Variable Text Semibold for labels. Cascadia Mono (with Consolas) for the log.

**Character:** Windows 11's own variable face, so the console feels native to the machine it runs on. The optical Display cut is reserved for titles and the answer, and Text Semibold carries labels, buttons and chips.

### Hierarchy
- **Display** (Display Semibold, 30pt): the last answer only. It shrinks one point at a time down to 11pt to fit, rather than being cut off. When empty it shows in Dusk Gray.
- **Headline** (Display Semibold, 20pt): the page title in the header.
- **Title Large** (Display Semibold, 14pt): the answer's total time and the chat's empty-state title.
- **Brand** (Display Semibold, 13pt): the "MASSAB" wordmark beside the mark in the rail.
- **Title** (Text Semibold, 11pt): panel titles ("Codes", "Activity", "Reading area").
- **Body** (Text, 10pt): the app default, used for setting names, chat text and secondary lines. Nav tabs use Text Semibold at 10pt.
- **Label** (Text Semibold, 9.5pt): buttons, the status capsule text and Segmented choices. The Start button uses 10.5pt.
- **Caption** (Text, 9pt): hints in Dusk Gray, the VRAM label and the answer-bar legend.
- **Chip** (Text Semibold, 8.5pt): kind and paste chips. The guess and lock-note chips use 9pt.
- **Mono** (Cascadia Mono, 9pt): the activity log only.

### Named Rules
**The Loudest Answer Rule.** Only the answer is set at display size. Nothing else on any page competes with it.

**The Mono Is For Machines Rule.** Monospace appears only in the log, where it shows raw reads and timestamps.

## Layout

The window opens at 980 × 640, with a minimum of 880 × 580. A Backdrop fills it, with an 8px outer margin. The left column is the glass rail (228px wide; the contract planned 208px, and the build's 228px is what's recorded). It holds the mark and wordmark, then a 26px gap, the four nav tabs 4px apart, a stretch, and the AI light, AI button and VRAM bar pinned to the bottom. The main column holds a header row (the page title on the left, and the status capsule and Start button on the right, both 36px tall) above a stacked page area.

Every glass panel reserves 8px around its body for the painted shadow (PAD) and pads its contents 18px inside. Layout spacing defaults to 10px. Setting rows are a label on the left and a control on the right, with 9px above and below, a 16px gap, and hairline separators between rows. Fields are 150px wide (180px on the Overlay page). Every page keeps a 10px scroll gutter, and the vertical scroll bar is always present but invisible when there's nothing to scroll, so panels line up from tab to tab and never jump sideways.

Responsive behavior: panel pairs sit side by side in a Columns row and stack vertically below 700px of width. Home is the hero answer panel above an Activity panel that fills the rest. Chat is one panel (toggle row, scrolling bubbles, input row). Overlay and Settings scroll.

**The Steady Gutter Rule.** Every page reserves the same 10px scroll gutter whether or not it scrolls, so panel edges never shift between tabs.

## Elevation & Depth

Depth is painted, not styled. Qt style sheets can't blur, cast shadows or animate, so theme.py paints the backdrop, the shadows, the glass sheen and the rims with QPainter. There are three layers: the glowing backdrop, the floating glass panels (each with a soft dark shadow and a lit rim), and the popups, which are solid Popup Navy with a white-alpha border. Glass doesn't actually blur what's behind it. The frost effect comes from the navy tint (55–59% opacity) plus a white vertical sheen (from 8.5–10% at the top down to 3.5–4% at the bottom).

### Shadow Vocabulary
- **Glass drop** (`box-shadow: 0 3px 8px rgba(0, 0, 0, 0.43)`): under every glass panel and the rail. It's a Gaussian blur (sigma 4px) of the rounded body, dropped 3px.
- **Knob lift** (`box-shadow: 0 1px 0 rgba(0, 0, 20, 0.27)`): under the toggle's white knob.
- **Status halo** (`box-shadow: 0 0 0 2.5px` in the light's color at 24%): around each 7px status dot.

### Named Rules
**The Lit Rim Rule.** Every glass surface (panels, the rail, the rail pill, the Segmented pill and the mark) has a 1px rim drawn as a gradient that's brightest at the top-left (white at 31%, or periwinkle at 47% on the hero) and fades to about 5% at the bottom-right.

**The Hero Light Rule.** Only the answer panel catches accent light: a radial Electric Blue wash from its top-left at 27%, fading to nothing.

## Shapes

The language is capsules and soft rectangles. Every control is a capsule or near-capsule: buttons (16px radius), small buttons and nav tabs (14px), the Start button and status capsule (18px, half their height), chips (11px on 22px), the toggle, the Segmented control and the strip (each half its height). Containers are larger soft rectangles: glass panels (22px), the rail (24px), the log well (14px), chat bubbles (18px) and inputs (11px). Bars are 4px tall with 2px radii, and the answer bar is 8px tall with 4px radii. The mark is a rounded tile (28% radius) with a viewfinder glyph.

The one square form is the viewfinder. The on-screen box's capture area is a square-cornered faint outline with bright corner arms (6% of the shorter side). Zones are dashed (code lines) or dotted (riddle rows). This shape repeats in the Overlay tab icon and the mark.

Icons are drawn as line paths on a 24-unit grid, with a 1.9 stroke and round caps and joins. Glyph fonts are not used.

## Components

### Buttons
Translucent glass capsules that brighten on hover. Primary actions get the blue gradient.
- **Shape:** capsule (16px radius; 14px on small buttons; 18px on Start).
- **Default:** white at 8% with a white 12% border, Moon White label text, 7px × 16px padding.
- **Hover / Pressed / Focus:** hover raises the fill to 14% and the border to 20%. Pressed drops the fill to 5%. Focus turns the border Periwinkle Light (white on primary buttons). Disabled text drops to 35%.
- **Primary** ("Pick on screen", "Load AI", "Send"): a diagonal gradient from Bright Periwinkle to Deep Cobalt, white text, and a white 20% border. Hover brightens it to #82a5ff → #4a6cff, and pressed deepens it to #5279f2 → #314fd8.
- **Start / Stop:** a 36px capsule in the header with the same gradient, at 10.5pt with 28px horizontal padding. While watching it becomes Stop: Stop Red at 18% (28% on hover), a red 55% border and stop-ink text.
- **Suggestion:** the default glass capsule with Lavender Gray body text, which turns Moon White on hover.

### Chips
- **Style:** 22px capsules with an 11px radius, Text Semibold at 8.5pt, a translucent fill and a stronger border in the same hue.
- **Kind** (RIDDLE / CODE): Electric Blue at 18% with a periwinkle 39% border and Ice Blue Ink text.
- **Pasted:** Live Green at 13% with a 43% border. **Copied** is plain white at 6% with Lavender Gray text.
- **Guess / lock note:** Guess Amber at 13% with a 43% border and amber chip ink, at 9pt.

### Cards / Containers
- **Corner Style:** 22px (the rail is 24px).
- **Background:** the navy glass tint of each kind (panel, rail or hero) plus the white sheen.
- **Shadow Strategy:** the glass drop and lit rim (see Elevation & Depth). The hero adds the accent wash.
- **Border:** the painted 1px gradient rim. There are no stylesheet borders.
- **Internal Padding:** 18px (12px in the rail), inside an 8px shadow margin.

### Inputs / Fields
- **Style:** a black 25% well with a white 10% border, an 11px radius and 6px × 10px padding. The chat input uses a 16px radius and 8px × 12px padding at 50px tall.
- **Hover / Focus:** hover raises the border to 18%. Focus turns the border Periwinkle Light and deepens the well to 33%.
- **Error / Disabled:** an invalid field gets a Stop Red border on a red 10% wash. Disabled fields drop to a 12% well with a 5% border and 35% text.
- **Drop-downs and spin boxes:** painted Lavender Gray chevrons (2.4 stroke, round caps), dimmed to #4a5280 when disabled. Lists open on Popup Navy with selection in Electric Blue at 59%.
- **Toggle:** a 42 × 24 track (white 14% when off), which cross-fades to the blue gradient when on. It has a 20px white knob and slides in 220ms.
- **Segmented:** a 32px capsule well (black 28%) with a glass pill (periwinkle-to-cobalt at 43% → 35%, with a periwinkle rim) that slides to the chosen segment in 240ms. Labels are Moon White when chosen or hovered and Lavender Gray otherwise. Left and right arrow keys move the choice.
- **Slider:** a 4px groove (white 14%), a fill from Bright Periwinkle to Electric Blue, and an 18px white handle.
- **Swatches:** five 16px color dots (cyan #3cc8ff, green #3ee39a, yellow #ffd23f, pink #ff5fd2 and white) with a white 20% rim. The chosen dot gets a 2px white ring, which turns Periwinkle Light under focus.

### Navigation
- **Style:** 40px tabs in Text Semibold at 10pt, each with an 18px line icon. Unselected tabs are Lavender Gray on transparent, and hover adds Moon White text on white 4%.
- **Active:** Moon White text and a white icon over the RailPill, a 14px-radius glass capsule (periwinkle 31% → cobalt 20%, with a lit rim) that slides to the chosen tab in 260ms.
- **Page change:** the old page's snapshot fades out over the new page (260ms) while the new page rises 10px into place from 35% opacity.

### Status Lights
A 7px dot inside a 12px halo at 24% of the same color. Green is live or ready, amber is loading, red is error, gray is off, and blue is available. In the header the light sits inside the status capsule (white 6% fill with a white 10% border, 18px radius), and the status text turns from Lavender Gray to Moon White while live.

### Answer Pipeline (signature)
A proportional bar under the answer showing where the time went: an 8px track (white 8%) holds Read (cyan), AI (violet) and Paste (green) segments with 3px gaps and 4px radii. It grows from zero over 700ms with exponential ease-out, the one long motion in the system. Below it, a legend gives each stage's dot, name and seconds in Lavender Gray at 9pt.

### Chat Bubbles
User bubbles are right-aligned on the blue gradient with white text. AI bubbles are left-aligned on white 7% glass with a white 10% border. Error bubbles use Stop Red at 12% with a 40% border and chip-ink-red text. All three have an 18px radius and 10px × 15px padding.

### The Strip (over the game)
A capsule (30, 36 or 44px tall, with a radius of half the height) in a vertical dark glass gradient (strip-glass-top → strip-glass-floor), with a white border at 24%. The player's opacity setting (0–100%, default 85%) scales both the glass and the border. Contents, left to right: a kind chip (Electric Blue at 47% with a periwinkle border), the answer in Display Semibold white, the seconds in pale lavender, the state in Strip Green (or white at 86% for copied or building), and "guess" in Strip Amber. Text sizes are 9, 11 or 14pt. The strip sits 16px in from a chosen screen corner.

### The Box and the Picker (over the game)
Box tags are capsules filled with tag-glass, rimmed in the box color at 78%, with white Text Semibold at 12px. Read lines are boxed with a 5px radius at 18% of the box color. The area picker shades the screen with navy at 55% and cuts the selection out of the shade. The selection is outlined in cyan with a size tag, and the instructions sit in a dark glass capsule (22px radius) at the top. The reading-area preview in the window shows the monitor as a dark glass pane with a faint 8 × 5 grid.

### Named Rules
**The Dark Glass Over the Game Rule.** Anything drawn over the game is dark navy glass with white text. The strip and the box are click-through, never take focus, and are excluded from screen capture. The picker is the one exception: it's a deliberate, temporary capture of the mouse, and Esc or right-click cancels it.

**The Capsule Control Rule.** Every interactive control is a capsule. Square corners belong only to the viewfinder.

## Do's and Don'ts

### Do:
- **Do** float every grouping on Glass (22px radius, 18px padding, 8px shadow margin) over the painted Backdrop. Never put a grouping on a flat fill.
- **Do** keep Electric Blue for selection and primary actions, and use the blue gradient (#6a93ff → #3a5ef0) for the one primary action in a group.
- **Do** flag every guess in amber, beside the pasted or copied state rather than in its place.
- **Do** use green for live or pasted, amber for guess or loading, and red for stop, error or low VRAM, everywhere, including the strip.
- **Do** animate with exponential ease-out at 220–260ms, and keep 700ms for the answer bar alone.
- **Do** give every control a Periwinkle Light focus ring for Tab, and no ring after a mouse click.
- **Do** keep the answer the only display-size text, shrinking it to fit rather than truncating it.

### Don't:
- **Don't** use Electric Blue to mean a state, or a signal color as decoration.
- **Don't** bring back the retired light look: light skies, light glass cards and glossy buttons.
- **Don't** make anything drawn over the game clickable or focusable, light-colored, or visible to MASSAB's own screen capture.
- **Don't** try to fake blur or shadows in the style sheet. Paint them in theme.py, and carry new depth through Glass.
- **Don't** add square-cornered controls. Square corners belong to the viewfinder only.
- **Don't** use monospace outside the log.

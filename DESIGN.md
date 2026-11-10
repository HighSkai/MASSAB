---
name: MASSAB
description: A black instrument sheet for reading Sammy's codes and riddles and pasting the answer, with one light slab for the last answer.
colors:
  ground: "#0b0b0c"
  panel: "#131314"
  raised: "#1b1b1d"
  field: "#0e0e0f"
  popup: "#151516"
  rule: "#232326"
  rule-strong: "#3a3a40"
  rule-hover: "#55555c"
  ink: "#ededee"
  white: "#ffffff"
  ink-pressed: "#c9c9cd"
  text-secondary: "#9b9ba3"
  text-tertiary: "#81818a"
  ice: "#a9c8e0"
  slab: "#e4ecf2"
  slab-ink-secondary: "#46525d"
  slab-ink-tertiary: "#7a8794"
  slab-track: "#cdd7df"
  stage-read: "#8a99a6"
  stage-ai: "#3f6482"
  mint: "#5ee0a0"
  amber: "#f5b041"
  amber-ink: "#1a1205"
  coral: "#ff5c5c"
  coral-ink: "#ffb4ac"
  coral-wash: "rgba(255, 92, 92, 0.08)"
  overlay-cyan: "#3cc8ff"
  strip-ground: "rgba(11, 11, 12, 0.85)"
  tag-ground: "rgba(11, 11, 12, 0.91)"
typography:
  display:
    fontFamily: "Big Shoulders Display, Segoe UI, sans-serif"
    fontSize: "44pt"
    fontWeight: 900
  brand:
    fontFamily: "Big Shoulders Display, Segoe UI, sans-serif"
    fontSize: "23pt"
    fontWeight: 900
  headline:
    fontFamily: "Big Shoulders Display, Segoe UI, sans-serif"
    fontSize: "28pt"
    fontWeight: 800
  title:
    fontFamily: "Big Shoulders Display, Segoe UI, sans-serif"
    fontSize: "24pt"
    fontWeight: 800
  title-empty:
    fontFamily: "Big Shoulders Display, Segoe UI, sans-serif"
    fontSize: "22pt"
    fontWeight: 800
  body:
    fontFamily: "Segoe UI Variable Text, Segoe UI, sans-serif"
    fontSize: "10pt"
    fontWeight: 400
  body-hint:
    fontFamily: "Segoe UI Variable Text, Segoe UI, sans-serif"
    fontSize: "9pt"
    fontWeight: 400
  label:
    fontFamily: "Martian Mono, Cascadia Mono, Consolas, monospace"
    fontSize: "8.5pt"
    fontWeight: 500
  label-nav:
    fontFamily: "Martian Mono, Cascadia Mono, Consolas, monospace"
    fontSize: "9pt"
    fontWeight: 500
  label-small:
    fontFamily: "Martian Mono, Cascadia Mono, Consolas, monospace"
    fontSize: "8pt"
    fontWeight: 500
  data:
    fontFamily: "Martian Mono, Cascadia Mono, Consolas, monospace"
    fontSize: "8.5pt"
    fontWeight: 400
  data-small:
    fontFamily: "Martian Mono, Cascadia Mono, Consolas, monospace"
    fontSize: "8pt"
    fontWeight: 400
rounded:
  none: "0px"
  hairline: "1px"
  sm: "2px"
spacing:
  2xs: "4px"
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  panel: "18px"
  slab: "22px"
  page: "24px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
  button-primary-hover:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ground}"
  button-primary-pressed:
    backgroundColor: "{colors.ink-pressed}"
    textColor: "{colors.ground}"
  button-start:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 22px"
    height: "34px"
  button-start-running:
    backgroundColor: "transparent"
    textColor: "{colors.coral}"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
  button-outline-hover:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink}"
  button-small:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label-small}"
    rounded: "{rounded.sm}"
    padding: "5px 10px"
  input:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    typography: "{typography.data}"
    rounded: "{rounded.sm}"
    padding: "7px 10px"
  panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "18px"
  answer-slab:
    backgroundColor: "{colors.slab}"
    textColor: "{colors.ground}"
    rounded: "{rounded.sm}"
    padding: "22px"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label-small}"
    rounded: "{rounded.sm}"
    padding: "0 8px"
    height: "20px"
  chip-pasted:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.slab}"
  chip-guess:
    backgroundColor: "{colors.amber}"
    textColor: "{colors.amber-ink}"
    typography: "{typography.label-small}"
    rounded: "{rounded.sm}"
    padding: "0 8px"
    height: "20px"
  nav-tab:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    typography: "{typography.label-nav}"
    padding: "0 14px"
    height: "38px"
  nav-tab-active:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink}"
  toggle:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.none}"
    size: "44px 26px"
  toggle-on:
    backgroundColor: "{colors.ink}"
  segmented:
    backgroundColor: "{colors.field}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.label-small}"
    rounded: "{rounded.none}"
    height: "30px"
  segmented-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
  bubble-user:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "10px 15px"
  bubble-ai:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "10px 15px"
  game-strip:
    backgroundColor: "{colors.strip-ground}"
    textColor: "{colors.white}"
    rounded: "{rounded.sm}"
    padding: "0 14px 0 7px"
    height: "36px"
  box-tag:
    backgroundColor: "{colors.tag-ground}"
    textColor: "{colors.white}"
    rounded: "{rounded.none}"
    padding: "3px 6px"
---

# Design System: MASSAB

## Overview

**Creative North Star: "The Black Instrument Sheet"** (taken from the direction contract's thesis)

MASSAB is laid out like a black instrument sheet. Flat near-black planes are separated by 1px rules. Names, page titles and the answer are set in tall condensed poster type, and every label, number and log line is in crisp monospace. Nothing glows and nothing is glass. There is no light source, so depth comes only from value steps and lines. The one bright object is the light slab holding the last answer, and that's where the eye goes first.

The window is dense but calm, a setup and review console. The player glances at it, presses START, and goes back to the game. Everything drawn over the game follows the same rules: dark, square and white-lettered, and it never gets in the way. Motion is springy and brief, in the style Apple describes: springs set by duration and bounce that keep their velocity when interrupted, that move in the direction of the page you're going to, and that can be turned off.

This replaces the earlier dark-glass console. Glows, gradients, glass panels and rounded capsules are confirmed rejections.

**Key Characteristics:**
- Flat near-black planes stepped by value (ground, panel, raised), cut by 1px rules.
- Square geometry: 2px corners on framed controls, true squares on painted controls.
- Big Shoulders Display for names and the answer, Martian Mono in capitals for every label and number, and Segoe UI Variable for sentences.
- One light slab per screen, and it holds the last answer.
- Color is a signal, never decoration: mint, amber and coral each carry one meaning.
- Spring motion with bounce at or under 0.35, which snaps into place when motion is off.

## Colors

A near-monochrome graphite palette with one ice-white slab, plus three signal colors that each mean exactly one thing.

### Primary
- **Instrument Ink** (#ededee): the main text color, and the fill of the primary action block (START, Send, Load AI, Pick on screen) with ground-black text on it. Hover lifts it to pure white and pressing settles it to Pressed Ink (#c9c9cd). It also fills the user's chat bubbles, the segmented control's moving block, a toggle's on state, slider fills, selection highlights and progress chunks.
- **Ice Slab** (#e4ecf2): the answer slab, the only light surface on screen. Text on it is ground black, with Slab Secondary (#46525d) for the riddle line and Slab Tertiary (#7a8794) for the empty "No answer yet" state.

### Secondary
- **Signal Mint** (#5ee0a0): live or pasted. The status light while watching, AI ready, and PASTED on the game strip.
- **Signal Amber** (#f5b041): guess or loading. The GUESS chip (a solid amber block with Amber Ink (#1a1205) lettering), the strip's GUESS flag, and the AI loading or downloading light.
- **Signal Coral** (#ff5c5c): stop, error or low VRAM. The running START button turns into a coral-outlined STOP, and coral also marks invalid fields (with an 8% coral wash), error chat bubbles (Coral Ink (#ffb4ac) text) and the VRAM bar when it runs low.

### Tertiary
- **Focus Ice** (#a9c8e0): a 1px focus ring on buttons, fields, toggles, segmented controls, swatches and rail tabs. Nothing else.
- **Timing Stages** (#8a99a6 read, #3f6482 AI, ground black for paste, on a #cdd7df track): the three segments of the timing bar on the answer slab. The AI stage is the references' pale chart blue, darkened so it reads on the light slab.
- **Overlay Cyan** (#3cc8ff): the default outline color for the on-screen box and the color of the area picker's selection. The box's color can be changed with five swatches chosen to show up over any game (#3cc8ff, #3ee39a, #ffd23f, #ff5fd2, #ffffff). These are a user setting, not part of the window's palette.

### Neutral
- **Ground** (#0b0b0c): the window, the rail and the title bar. It is also the ink on the slab and on Instrument Ink blocks.
- **Panel** (#131314): ruled panels, the toggle track.
- **Raised** (#1b1b1d): hover fills, the rail's selection block, the AI's chat bubbles.
- **Field** (#0e0e0f): text fields, spin boxes, drop-downs, the segmented track, the reading-area preview pane.
- **Popup** (#151516): menus, drop-down lists and tooltips.
- **Rule** (#232326): every 1px divider, panel border and disabled outline.
- **Strong Rule** (#3a3a40): control outlines, chips, the slider groove and the empty toggle.
- **Hover Rule** (#55555c): the outline on hover. It is also the disabled text color and the "off" status light.
- **Secondary Text** (#9b9ba3) and **Tertiary Text** (#81818a): panel titles, status text and inactive tabs, then hints, placeholders and shortcut numbers.

### Named Rules
**The One Slab Rule.** The last answer sits on the only light surface on screen. No other panel, banner or card may be light.

**The Signal Rule.** Mint means live or pasted, amber means guess or loading, coral means stop, error or low VRAM. A signal color is never decoration, and a meaning is never shown in any other color.

**The Ice Is Focus Rule.** Focus Ice draws focus rings and nothing else: no fills, no text, no selected states.

## Typography

**Display Font:** Big Shoulders Display, a bundled variable font used at weights 900 and 800 (falls back to Segoe UI 700)
**Body Font:** Segoe UI Variable Text (falls back to Segoe UI)
**Label/Mono Font:** Martian Mono, a bundled variable font used at weights 400 and 500 (falls back to Cascadia Mono, then Consolas)

**Character:** Tall condensed poster capitals do the shouting and a wide technical monospace does all the reading of values. They work like the stencil and the readout of the same instrument. Sentences stay in a quiet Windows sans so that explanations read as plain speech.

Sizes are Qt points.

### Hierarchy
- **Display** (900, 44pt, shrinking a point at a time to 14pt to fit the slab): the last answer, and nothing else. The game strip sets the answer in the same face at 1.5× its text size.
- **Brand** (900, 23pt): the text title MASSAB in the rail. It's smaller than the page title so the page leads. The taskbar icon is its letter M in the same face.
- **Headline** (800, 28pt, uppercase): the page title in the header.
- **Title** (800, 24pt): the answer's total time ("0.94 s"). The empty Chat title uses 22pt, uppercase.
- **Body** (400, 10pt): setting names, riddle text, chat messages, explanations. **Hint** is 9pt in Tertiary Text.
- **Label** (500, 8.5pt, uppercase): panel titles, the status line, AI state and button text. Rail tabs use 9pt, and chips, small buttons and segmented cells use 8pt.
- **Data** (400, 8.5pt): field values, drop-downs and the activity log. Timing captions and shortcut numbers use 8pt, and the preview caption 7.5pt.

### Named Rules
**The Mono Readout Rule.** Every label, number, button, chip and log line is in Martian Mono, in capitals where it labels something. Big Shoulders is reserved for the title, page titles, the total and the answer.

**The Lowercase Unit Rule.** Units stay lowercase inside capitalized mono text: "READ 0.42 s", "0.94 s", "15 ms". Capitalize the label, never the unit.

## Layout

The first viewport is 980 × 640, and the window's minimum is 900 × 600. A fixed 200px rail on the left is in the ground color with a 1px rule down its right edge. It holds the title at the top, four tabs with their Ctrl+1–4 numbers, and the AI state, the Load/Unload button and the VRAM bar at the bottom. The main column has a header (page title on the left, then the mono status with its square light and the START block on the right, with 24px side insets), a 1px rule, and then the page body at 24px side and 20px top and bottom insets.

Pages are vertical stacks of panels with 12px gaps. Two panels sit side by side in columns 12px apart, and they stack when the content is narrower than 720px. Every page keeps an 8px gutter for a scroll bar, so panels line up the same from tab to tab, and the scroll bar is invisible when there's nothing to scroll. Panels have 18px insets. A panel's mono title is followed by an optional hint (6px below) and then the content (8px below). Setting rows have a label on the left and a control on the right, 10px of vertical padding, 16px between label and control, and 1px rules between rows. The answer slab uses 22px insets.

The spacing rhythm is 4 / 6 / 8 / 12 / 16 / 18 / 22 / 24px. 12px is the default gap between blocks.

## Elevation & Depth

The system is completely flat: no shadows and no gradients. Depth comes from three value steps (ground, then panel, then raised) and from 1px rules. Panels stand on the ground through their fill and a Rule border. The rail's selection and hover states step up to Raised. The only surface that comes forward is the light answer slab, and it does that through value, not lift. Page transitions move content along a single vertical axis, so there's no z-depth.

### Named Rules
**The No Light Source Rule.** Nothing casts a shadow, glows or is lit by a gradient. To separate two things, step the value or draw a 1px rule.

## Shapes

The form language is square. Framed controls drawn by the style sheet (buttons, fields, chips, panels, the slab, bubbles, the strip) have 2px corners, small enough to read as square. Thumb-scale details (the slider handle, the scroll bar handle, the strip's CODE/RIDDLE chip) use 1px. Everything painted is a true square with 0 radius: toggle tracks and knobs, segmented cells and their block, swatches, status lights, the timing bar and its legend squares, box tags and the picker's size card. Lines are 1px. Chevrons are square-capped, mitred 2.2px strokes. The only icon in the system is the letter M.

**The Square Rule.** Corners never go above 2px. There are no pills, no circles and no capsules: a status light is a 7px square, and a toggle knob is a 13px square.

## Components

### Buttons
Blocks and outlines, set in capitals, with nothing soft about them.
- **Shape:** squared (2px), with a 1px border.
- **Primary:** an Instrument Ink block with ground-black text (8px 14px). Hover goes to pure white and pressed to Pressed Ink. START is the same block at 34px tall with 22px side padding and a 72px minimum width. While watching it becomes STOP: transparent with a coral outline and coral text, and hover adds an 11% coral wash.
- **Outline (default):** transparent with a Strong Rule outline and Instrument Ink text. Hover gives a Hover Rule outline on a Raised fill, and pressed gives a near-ground fill (#0f0f10).
- **Small:** the outline button at 8pt with 5px 10px padding (Copy, Clear, New chat, Load/Unload AI).
- **On the slab:** a ground-black outline with ground-black text. Hover inverts it to a ground fill with slab-colored text.
- **Suggestion:** a sentence-case body-font outline button, left-aligned, in Secondary Text that turns Instrument Ink on hover. This is the one exception to capitals.
- **Focus:** the border turns Focus Ice. **Disabled:** dims to Hover Rule text and a Rule outline (on the primary, the fill drops to Rule).

### Chips
- **Style:** 20px tall, 8px side padding, 2px corners, 8pt mono medium in capitals. On the dark panels a chip has a Strong Rule outline. On the slab it has a ground-black outline.
- **State:** PASTED inverts to a solid ground-black chip with slab-colored text, and COPIED stays as an outline. The GUESS chip ("Guess: no fact matched") is a solid amber block with Amber Ink text.

### Cards / Containers
- **Corner Style:** squared (2px).
- **Background:** Panel, with a 1px Rule border. The answer slab is Ice Slab with no border.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Internal Padding:** 18px for panels, 22px for the slab.

### Inputs / Fields
- **Style:** Field fill, a 1px Strong Rule outline, 2px corners, 7px 10px padding, values in 8.5pt mono. Spin boxes and drop-downs use painted square chevrons in Secondary Text. Selection is Instrument Ink with ground-black text.
- **Focus:** the outline turns Focus Ice. **Hover:** the outline turns Hover Rule.
- **Error / Disabled:** an invalid field gets a coral outline on an 8% coral wash. A disabled field goes transparent with Hover Rule text and a Rule outline.
- **Slider:** a 2px Strong Rule groove with an Instrument Ink fill and a 12px square handle that turns white on hover.

### Navigation
Four text tabs (HOME, CHAT, OVERLAY, SETTINGS), 38px tall, in 9pt mono capitals, with their Ctrl shortcut number right-aligned in 8pt mono. Inactive tabs are Secondary Text. Hover and the selected tab are Instrument Ink. The selected tab sits on a Raised block with a 1px ink bar on its left edge, and the block springs between tabs (0.42s, bounce 0.35, launched toward the target at 12 px/s per px of travel, up to 600 px/s, so it overshoots about 4–5px). When you change pages, later tabs rise in from below and earlier ones drop in from above: the page travels 36px on a 0.5s, 0.35-bounce spring launched at 450 px/s, while the old page fades out over 0.22s and drifts 10px the other way.

### Toggles and Segmented Controls
- **Toggle:** a square 38 × 19 track (Panel, Strong Rule outline) with a 13px square knob in Secondary Text. When it's on, the track fills with Instrument Ink and the knob turns ground black. It springs at 0.34s, bounce 0.32.
- **Segmented:** square cells 30px tall on Field, with 1px Rule dividers. A square Instrument Ink block springs to the chosen cell (0.36s, bounce 0.3), and text under the block is clipped to ground black. It's used for the Model choice and Animations (On / Windows / Off).
- **Swatches:** 14px squares that grow to 18px when chosen, with a 1px ring offset 3.5px (Instrument Ink, or Focus Ice when focused).

### The Answer Slab (signature)
The one light slab: the answer in Display type with a small Copy button, the riddle line in Slab Secondary, then a row of chips (kind, PASTED or COPIED, and GUESS when there is one) with the total time in Title type on the right. Under that is the timing bar: a 6px bar split into read, AI and paste segments with 2px gaps, proportional to where the time went, and a legend of 6px squares with "READ 0.42 s"-style captions. The bar grows from zero on a 0.6s spring with no bounce.

### The Game Strip, Box Tags and Picker (signature)
Everything drawn over the game is dark and square with white text, and can't be clicked or focused. The strip and the box are also hidden from screen capture. The strip is a 36px bar (30 and 44px at the small and large sizes) of translucent ground with a faint white hairline, both scaled by the strip's opacity setting (85% by default). It shows a CODE/RIDDLE chip (ink on ground), the answer in Big Shoulders, the seconds in dimmed white mono, the state (PASTED in mint, COPIED in plain ink), and a separate amber GUESS flag. A pasted guess shows both. Box tags are square mono-capital labels on 91% ground, outlined in the box color. The area picker dims the screen to 59% black, draws the selection in Overlay Cyan with a size tag, and shows its instructions on a square card. It's the only one of these that takes focus, and only while you drag.

### Activity Log and Chat
The log is borderless 8.5pt mono in a light grey (#c9c9ce) inside a panel. User chat bubbles are Instrument Ink blocks with ground-black text, AI bubbles are Raised with a Rule border, and error bubbles are a coral outline on a coral wash. All of them have 2px corners and 10px 15px padding.

## Do's and Don'ts

### Do:
- **Do** separate surfaces only with the three value steps (ground, panel, raised) and 1px rules.
- **Do** keep the answer slab the one light surface on screen, and give the last answer Display type on it.
- **Do** set every label, button, chip and number in Martian Mono capitals, with units left lowercase ("READ 0.42 s").
- **Do** flag every guess in amber, and show PASTED next to it when a guess was pasted. Never let one replace the other.
- **Do** keep anything drawn over the game dark, square and white-lettered, and make it impossible to click or focus. The picker is the one exception, and only while dragging.
- **Do** drive motion with springs defined by duration and bounce, with bounce at or under 0.35, and carry the current velocity into any retarget.
- **Do** move pages along their tab order: later tabs come from below, earlier ones from above.
- **Do** snap every spring to its end when Animations is Off, or when it's set to Windows and Windows' animation effects are off.
- **Do** keep feedback brief and exact: state changes show up as a square light, a chip or a one-line mono status, not a dialog.

### Don't:
- **Don't** use shadows, glows, gradients, blur or glass anywhere.
- **Don't** round past 2px or use pills, circles or capsules. Lights, knobs and swatches are squares.
- **Don't** use Focus Ice for anything except focus rings.
- **Don't** use mint, amber or coral decoratively, or show one of their meanings in another color.
- **Don't** add a second light slab, banner or card. The light surface belongs to the answer.
- **Don't** use Big Shoulders for labels or body text, or Segoe for numbers.
- **Don't** use bounce above 0.35, start a spring from zero velocity when it's interrupted mid-flight, or make motion that can't be turned off.
- **Don't** add a logo or icon set. The title is text, and its letter M is the icon.

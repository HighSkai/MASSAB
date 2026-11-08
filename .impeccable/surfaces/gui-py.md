---
version: 1
slug: "gui-py"
primary_target: "gui.py"
related_targets: ["overlay.py","theme.py"]
---

# Surface: MASSAB control window

Scope: the desktop control window (`gui.py`), plus everything else it draws: the game strip, the on-screen box and the area picker (`overlay.py`). Visitor mode: Operate. The player sets things up before a stream, presses Start, and looks back at the last answer and the log afterwards.

Pinned by the user (2026-11-08): a full redesign that looks like the Vision UI dashboard mixed with an Apple Vision Pro (visionOS) dashboard. The tabs should flow and feel defined and polished. All text should be cleaned up and simplified, unnecessary extras removed, and sizing, spacing and color tidied. The window becomes wide, with a sidebar.

Cuts were left to the designer:
- Most hint lines become tooltips.
- The on-screen box's line width and opacity controls go, and its color becomes preset swatches.
- The chat's intro paragraph goes, but its suggestion chips stay.

The settings keys stay, so saved values still load.

## Direction contract

THESIS: A floating glass control window over a deep indigo environment. Navigation is a frosted side rail with a pill that slides from tab to tab, and the last answer is the brightest object on screen. This replaces the stacked light-blue cards with top tabs: there's one shell, the pages move inside it, and it doesn't look like a settings form.

OWN-WORLD:
- **Environment:** a deep navy-indigo ground (#060a22 to #0c1442), with large soft blue (#2f5bff) and violet (#7b3cff) glows.
- **Panels:** navy-tinted glass with white fills of 4–9%, a 1px rim that's brighter at the top-left, soft dark shadows, and a 20–22px radius.
- **Controls and type:** capsule controls, Segoe UI Variable (Display Semibold for titles), and white text with lavender-gray secondary text.
- **Color:** one electric-blue accent (#4d7cff) for actions and selection. State colors are green (live, pasted), amber (guess, loading) and red (stop, error).

STORY: The player sees in one glance whether MASSAB is watching, what the last answer was, and whether it pasted. They set up the reading area and preferences in grouped glass panels, and press Start.

FIRST VIEWPORT: The window opens at 980 × 640.
- **Left (208px):** a glass rail with the mark and MASSAB at the top, four icon tabs with a sliding pill, and AI status and VRAM pinned at the bottom.
- **Main column, header:** the page title at 20pt, and on the right a live status capsule and a Start capsule.
- **Main column, Home:** the answer panel, with the answer at 30pt, the riddle text, kind and paste chips, Copy, and the timing pipeline. Below it, the activity panel fills the rest.

FORM: Pinned by the user (Vision UI × visionOS dashboard). This is the first of one: the user pinned the direction, so no roll was run. Signature move: the answer pipeline, a proportional read → AI → paste bar under the answer, plus the sliding rail pill and pages that cross-fade (the old page fades out over the new one as it rises). Motion is exponential ease-out at 220–260ms; the answer bar's 700ms grow is the one long moment.
seed: none (no roll ran: the user pinned the direction, so concept-seed was never called)

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

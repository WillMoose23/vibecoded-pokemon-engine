---
name: map_data.h doc indent
overview: "Align the `FILE: include/map_data.h` block in `docs/source_doc.md` with the repository’s mandatory documentation indentation (left-aligned labels, 4-space values, 8-space list lines)—which already matches the intended structure—and apply any small fixes (e.g. NOTES backticks) if needed."
todos:
  - id: audit-map-data-doc
    content: Re-read docs/source_doc.md FILE include/map_data.h; fix tabs/mis-indent or NOTES backticks if needed
    status: completed
  - id: tracker-if-changed
    content: If edits are non-trivial, log/update docs/tracker.md (IMPROVEMENT-DOC-*) and mark DONE
    status: completed
isProject: false
---

# Normalize `include/map_data.h` documentation indentation

## Repo rule (authoritative)

[`.cursor/rules/Documentation-Rule.mdc`](.cursor/rules/Documentation-Rule.mdc) requires:

- Section labels (`FILE`, `PURPOSE`, `DEPENDENCIES`, `KEY COMPONENTS`, `NOTES`, etc.) **left-aligned** (column 0).
- **One** 4-space indent for scalar/multi-line values under a label.
- **Eight** spaces before each `-` list item under `DEPENDENCIES` / `KEY COMPONENTS` (and similar list fields).

The example you pasted indents `PURPOSE:` / `KEY COMPONENTS:` with four leading spaces; that **conflicts** with the always-applied rule (“All field labels … must be LEFT-ALIGNED”). Implementation will **not** adopt indented labels.

## Current state

In [`docs/source_doc.md`](docs/source_doc.md) (lines 38–59), the `include/map_data.h` entry **already** matches the rule:

- `FILE:` / `PURPOSE:` / `DEPENDENCIES:` / `KEY COMPONENTS:` / `NOTES:` at column 0.
- Body lines under `PURPOSE` / `NOTES` use 4 spaces.
- Bullets under `DEPENDENCIES` and `KEY COMPONENTS` use 8 spaces.

No structural re-indent is required unless a later read shows mixed tabs/spaces or drift.

## Edits to perform after plan approval

1. **Re-read** the `include/map_data.h` block (and immediately following `FILE: src/map_data.cpp` if you want strict continuity) for stray tabs or inconsistent spaces; normalize to spaces-only, 4/8 pattern.
2. **NOTES polish (optional):** On line 58, ensure inline code around `` `layers.overPlayer[y][x] == 1` `` is closed correctly for readability (matching intent, no rule violation).
3. **Tracker:** If any non-trivial edit is made, add a short `IMPROVEMENT-DOC-*` entry in [`docs/tracker.md`](docs/tracker.md) (or extend the existing doc-improvement item if your process prefers a single open doc-hygiene ticket) and set `STATUS` to `DONE` when finished.
4. **No** changes to [`include/map_data.h`](include/map_data.h) unless you explicitly want header comments (not requested).

## Verification

- Visual scan of lines 38–59: labels column 0; list items exactly 8 spaces; prose under `NOTES` 4 spaces per line.

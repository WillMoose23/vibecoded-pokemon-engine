---
name: NPC Sprite Editor v2
overview: Fix map toolbar overlap (layer lock vs Settings) and NPC sprite editor bugs (reference label, default zoom 12), then add collapsible sprite-search panel, reference grid/label, selector copy/paste, and expanded shortcuts — documented, tested, code-reviewed, and committed.
todos:
  - id: bug-106-toolbar-lock-overlap
    content: "BUG-MAP-106: layer lock button overlaps Settings toolbar button on map chip row"
    status: completed
  - id: bug-105-ref-label-overlap
    content: "BUG-MAP-105: remove old ref-label-above-canvas placement (fixed structurally by moving label under image)"
    status: completed
  - id: feature-106-zoom12-footer
    content: "FEATURE-MAP-106: default zoom 12, config update, extract/test _footer_start_y"
    status: completed
  - id: feature-107-ref-label-grid
    content: "FEATURE-MAP-107: yellow ref label under image + grid overlay/toggle"
    status: completed
  - id: feature-108-sprite-search-panel
    content: "FEATURE-MAP-108: collapsible searchable sprite panel to pick reference image"
    status: completed
  - id: feature-109-selector-copy-paste
    content: "FEATURE-MAP-109: rectangular selector tool + copy/paste, normalize_pixel_rect helper"
    status: completed
  - id: feature-110-shortcuts
    content: "FEATURE-MAP-110: Z/R undo-redo, Ctrl+S/Shift+S/C/V shortcuts"
    status: completed
  - id: docs-tracker-help
    content: Update tracker.md, tools_doc.md, session_changelog.md, and Help → NPC Sprites tab
    status: completed
  - id: tests
    content: Add/extend unit tests for helpers, footer calc, filtering, copy/paste, shortcuts
    status: completed
  - id: review-commit
    content: Run test suite, self code-review the diff, commit if clean
    status: completed
isProject: false
---

# NPC Sprite Editor v2 — bugs, panels, selector, shortcuts

All work is in [tools/npc_sprite_editor_modal.py](tools/npc_sprite_editor_modal.py), [tools/npc_sprite_sheet_helpers.py](tools/npc_sprite_sheet_helpers.py), [tools/map_editor_config.json](tools/map_editor_config.json), and [tools/map_editor.py](tools/map_editor.py) (map chip toolbar layout + Help tab). Confirmed scope from user answers:

- "Toolbar moves up on zoom decrease" = the **footer row** (palette/W/H/File), which already tracks `canvas.bottom`/`ref.bottom` — verify with a regression test rather than rewriting.
- Sprite search panel selects the **reference** image (not the editable sheet).
- Shortcuts: **Z**/**R** plain keys for undo/redo (replacing Ctrl+Z/Ctrl+Y), **Ctrl+S** save, **Ctrl+Shift+S** save as, **Ctrl+C** copy, **Ctrl+V** paste.
- Selector tool = rectangular marquee; Copy grabs the active layer's pixels in the selection; Paste stamps the clipboard onto the active layer at the last hovered canvas pixel (or the original spot if the canvas isn't hovered).

## 1. Bug fixes (first)

**BUG-MAP-106 — Layer lock button overlaps Settings on map toolbar row.**
Root cause: FEATURE-MAP-103 added `layer_chip_lock_btn` at `layer_chip_rect.right - lock_w - 6` in [draw()](tools/map_editor.py) (~4452), while IMPROVEMENT-MAP-093/094 placed Event / Overworld / Help / Settings on the **same chip row** anchored to `map_viewport_rect.right` in [relayout()](tools/map_editor.py) (~2001–2012). Both claim the right edge — the lock square renders on top of Settings (user screenshot: small button stuck under/over Settings).

Fix:
- In `relayout()`, after sizing the four toolbar buttons, store `self._map_toolbar_left = self.events_btn_rect.x` (left edge of the cluster).
- In `draw()`, position `layer_chip_lock_btn` immediately **left** of `_map_toolbar_left` with a small gap (e.g. `lock_btn.right = _map_toolbar_left - btn_gap`), not at `layer_chip_rect.right`.
- Recompute `chip_avail` so map-id / layer text truncates before the lock button (not before the viewport right edge).
- Assert in `tests/test_map_layer_lock.py` (or a small layout test): `layer_chip_lock_btn.right <= gear_rect.x` after `relayout()` + a representative `draw()` pass.

**BUG-MAP-105 — Reference label overlaps toolbar row at narrow widths (NPC Sprite Editor).**
Root cause: `ref_label_y = y - 18 ...` in [draw()](tools/npc_sprite_editor_modal.py) places "Ref: name" in the ~24px gap above the reference canvas; when the panel narrows, the preceding toolbar row grows/wraps and the label lands on top of it (visible in the "Ref: base_dive.png" screenshot overlapping the Zoom row). Fix: remove that label placement entirely — see item 3 (label moves under the picture), which structurally eliminates the collision.

**FEATURE-MAP-106 — Default zoom 12; footer tracking verified.**
- `_DEFAULT_ZOOM = 12` (was 8); update `tools/map_editor_config.json` → `npcSpriteEditor.defaultZoom: 12`.
- `pal_y = max(canvas_rect.bottom, ref_rect.bottom) + 8` already shrinks as zoom drops. Extract this into a small `_footer_start_y()` helper so it's directly unit-testable, and add a test asserting `_footer_start_y()` decreases when `_zoom` decreases (locks in existing behavior, satisfies the "verify" requirement).

## 2. Reference image panel — label, color, grid toggle

**FEATURE-MAP-107 — Reference label under image, yellow; grid overlay + toggle.**
- Remove the old "Ref: name" line above the canvas row.
- Add a small "Grid" toggle button above the reference box (where the old label used to sit) controlling new `_ref_grid_on: bool` (default True).
- After blitting the scaled reference cell, draw `self._reference_name or "(no ref)"` **below** `_ref_rect` in yellow (`(255, 225, 90)`), truncated with `mtext.truncate_to_width`.
- When `_ref_grid_on` and a reference image is loaded, draw grid lines across `_ref_rect` sized to the reference's own cell dimensions (`rcx`/`rcy`), mirroring the existing edit-canvas grid loop.
- Reserve label height in the footer calc (`_footer_start_y`) so the yellow label never collides with the palette row below.

## 3. Collapsible sprite search panel (left side)

**FEATURE-MAP-108 — Searchable sprite picker for the reference image.**
- New collapsed-by-default strip (`_SPRITE_PANEL_COLLAPSED_W = 22`) left of the existing tool rail, with a toggle button; expands to `_SPRITE_PANEL_EXPANDED_W = 150` showing a search textbox + scrollable filtered list of `list_character_pngs(self._characters_dir())`, styled like the existing layer-row list.
- Filtering via a small testable method `_filtered_sprite_names() -> list[str]` (case-insensitive substring match on `_sprite_search_query`).
- Clicking a row sets `_reference_name` + calls `_load_reference_surface()`; highlights the active reference.
- `work_left`/`max_pair_w` calculations in `draw()` account for the panel's current width so the edit/reference canvases keep fitting.
- Search text entry reuses the existing high-priority text-input pattern in `handle_key` (like `_save_prompt_active`) via new `_sprite_search_focus`, so typing "player" doesn't trigger the P/E/F/S tool shortcuts.

## 4. Selector tool + copy/paste

**FEATURE-MAP-109 — Rectangular marquee selection with copy/paste.**
- `ToolId` gains `"select"`; new rail button "Select (S)".
- Drag on canvas with the tool active defines `_selection_rect` (px0,py0,px1,py1) in active-cell pixel space; drawn as an outlined marquee over the canvas.
- `_copy_selection()`: `active_layer_surface().subsurface(...)`.copy() → `self._clipboard`.
- `_paste_clipboard()`: pushes undo, blits `_clipboard` onto the active layer at `_last_canvas_pixel` (clamped so it fits the cell) or the selection's original origin if the canvas isn't hovered; respects `_layer_edit_blocked()`; re-syncs mirror when applicable.
- New pure helper `normalize_pixel_rect(x0, y0, x1, y1, max_w, max_h)` added to `npc_sprite_sheet_helpers.py` for easy unit testing of the clamp/order logic.
- Escape clears an active selection.

## 5. Keyboard shortcuts

**FEATURE-MAP-110 — Expanded shortcuts.**
- Replace Ctrl+Z/Ctrl+Y with plain **Z** (undo) / **R** (redo), consistent with P/E/F/S.
- Add **Ctrl+S** (save), **Ctrl+Shift+S** (save as), **Ctrl+C** (copy selection), **Ctrl+V** (paste). Ctrl-combos are checked before the plain-key tool shortcuts so `S` still means "select tool" without Ctrl.

## 6. Documentation (mandatory before commit)

- `docs/tracker.md`: add `BUG-MAP-106`, `BUG-MAP-105`, `FEATURE-MAP-106..110` entries (Logging-Rule format).
- `docs/tools_doc.md`: update `TOOL: tools/map_editor.py` (toolbar layout note for BUG-MAP-106) and `TOOL: tools/npc_sprite_editor_modal.py` / `npc_sprite_sheet_helpers.py` entries.
- `docs/session_changelog.md`: append entries per file changed.
- Help → NPC Sprites tab in `tools/map_editor.py`: document the sprite search panel, reference grid toggle, selector + copy/paste, and the new shortcut list (Z/R, Ctrl+S/Shift+S/C/V), replacing the stale "Ctrl+Z / Ctrl+Y" line.

## 7. Tests

- `tests/test_map_layer_lock.py`: layout assertion — lock button does not overlap `gear_rect` (BUG-MAP-106).
- `tests/test_npc_sprite_sheet_helpers.py`: `normalize_pixel_rect` (swap ordering, clamping to bounds).
- `tests/test_npc_sprite_editor_modal.py`:
  - Default `_zoom == 12` on a fresh modal.
  - `_footer_start_y()` decreases when `_zoom` decreases (footer-tracks-canvas regression test).
  - `_filtered_sprite_names()` substring filtering.
  - Copy → paste round trip mutates the target cell to match the source.
  - `handle_key`: plain `Z`/`R` undo/redo; Ctrl+S triggers `_save_sheet(save_as=False)`; plain `S` sets `_active_tool == "select"` while Ctrl+S does not.

## 8. Review and commit

- Run `make test` and `python3 -m unittest discover -s tests -q`.
- Perform a code-review pass over the diff (bugs/regressions/security/missing tests, severity-ordered) before committing.
- If clean: commit only (per Logging/Documentation/Change-Tracking rules), referencing the tracker IDs above. No push unless requested.

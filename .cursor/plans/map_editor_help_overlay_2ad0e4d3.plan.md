---
name: Map editor help overlay
overview: Add a full-screen-style modal help panel in `tools/map_editor.py`, toggled with the existing `toggle_help` binding (default **H**), with a home table of contents, per-mode tabs (paint/walk/transparent/over-player plus events/world/map metadata), a structured keybindings section with subsections, and scroll plus mouse navigation—while updating `docs/tools_doc.md` and `docs/tracker.md` per repo rules.
todos:
  - id: tracker-doc
    content: Add tracker entry + update docs/tools_doc.md (H = help panel; remove stale footer-expand description).
    status: completed
  - id: state-draw
    content: Add help overlay state, _draw_help_overlay (TOC, tabs, scrollable content, hit rects).
    status: completed
  - id: input
    content: "Wire KEYDOWN/MOUSE/WHEEL: toggle H, Esc close, TOC/tab clicks, scroll clamp; gate map/tools when open; retire footer_help_expanded."
    status: completed
  - id: content
    content: "Author tab copy: Paint (+ eraser/fill), Walk, Transparent, Over_player, Map ID & conn, Events, World, Keys subsections using key_primary/keys_for."
    status: completed
  - id: verify
    content: "Manual run map_editor: navigation, close paths, no edits through overlay."
    status: completed
isProject: false
---

# Map editor help guide (H)

## Current behavior

- [`tools/map_editor.py`](tools/map_editor.py): `toggle_help` (default **H**) flips `footer_help_expanded`, which only grows the footer text ([~4070–4149](tools/map_editor.py)). There is no centered modal today.
- Edit modes cycled by **Tab**: `paint` → `walk` → `transparent` → `over_player` ([`cycle_edit_mode`](tools/map_editor.py) ~4709–4714). **I** / **C** switch `map_id` / `conn` (hardcoded keys, not in [`tools/map_editor_config.json`](tools/map_editor_config.json)).
- Modal UI precedent: [`_draw_settings_overlay`](tools/map_editor.py) (~4193+) uses dimmed backdrop + bordered panel + hit rects.

## Goal / acceptance criteria

- Pressing **H** (configurable via `toggle_help`) opens a **modal help panel**; pressing **H** again or **Esc** closes it.
- **First view** is a **table of contents**: clear sections linking to each major area (modes, workspaces, keys). Clicking a row (and optionally number keys **1–9** on the home tab) switches to the right tab.
- **Tabs** (horizontal row under the title): one tab per **edit / workspace “mode”** the user cares about—at minimum **Paint** (including eraser + fill as subsections inside that tab), **Walk**, **Transparent**, **Over-player**, **Map ID & connections**, **Events workspace**, **World workspace**, plus a dedicated **Keybindings** tab.
- **Keybindings** tab: **subsections** (e.g. File & maps, Layers & tilesets, Editing & brush, Canvas navigation, Events, World, Overlays, Settings / misc) listing actions with **`key_primary()`** / `keys_for()` so text stays aligned with [`map_editor_config.json`](tools/map_editor_config.json).
- **Readable layout**: clipped content region, **mouse wheel** scroll, short intro line (“Esc / H to close”), consistent fonts (`font` for titles, `font_small` for body), section headers visually distinct (color + optional small spacing).
- While the panel is open: **do not** apply map edits or pass conflicting shortcuts through—mirror the pattern used for `settings_open` (early `continue` on keys; gate wheel / mouse paths similarly).

## UX decision (footer vs modal)

- **Replace** the current “H expands footer” behavior with the modal so there is a single help surface (avoids two competing help UIs).
- Collapsed footer hint text should say that **H opens the help guide** (not “expand footer”). Remove or drastically shrink the `footer_help_expanded` branch and related state (`footer_help_expanded` in `__init__` ~757, drawing ~4070–4149, toggle ~5834–5836).

## Implementation sketch (all in `map_editor.py` unless split is justified)

1. **State** (near other overlay flags ~753): `help_overlay_open: bool`, `help_tab: str` (e.g. `"home"`, `"paint"`, …), `help_scroll_y: int`, and per-frame `help_*_rect` attributes for tab bars / TOC rows (set during draw, read on click—same idiom as `settings_add_event_rect`).
2. **`_draw_help_overlay(self)`** (new): dim backdrop; large centered `panel` rect (scale with `screen.get_size()`, min margins); draw title “Map editor help”; tab strip; subtitle for current tab; content area with `screen.set_clip(content_rect)`, blit wrapped lines offset by `-help_scroll_y`, restore clip; footer hint “Esc or H to close”.
3. **Content source**: a small internal structure (e.g. list of sections per tab: title + paragraphs, or pre-wrapped lines via existing [`_wrap_lines_to_width`](tools/map_editor.py) ~420+) so paint tab can include **Paint**, **Eraser**, **Flood fill** subheadings. Pull copy from current footer / [`docs/tools_doc.md`](docs/tools_doc.md) / mode tooltips so it stays accurate (events ~2187, world notes in tools_doc, walk/over_player strings ~4034–4050, valid-stand toggles, **Shift+S** Save As, **Ctrl+S**, palette **Ctrl/Shift+wheel**, etc.). Call **`self.key_primary("save")`** etc. in strings so rebinding is reflected.
4. **Input wiring**:
   - **KEYDOWN**: Early branch—if `help_overlay_open`, handle **Esc** / **H** (`toggle_help`) to close; optional **1–9** on `home` tab to jump tabs; **wheel** already global—add a branch before palette/map zoom when `help_overlay_open` to adjust `help_scroll_y` with clamping based on total content height.
   - **MOUSEBUTTONDOWN**: If `help_overlay_open`, hit-test tabs / TOC / “content area” (optional drag later—skip for v1), `continue` without falling through to map editing.
   - **Opening help**: On `toggle_help` when overlay was closed, set `help_tab = "home"`, `help_scroll_y = 0`; if `settings_open`, close settings first to avoid stacked modals.
   - **Closing help**: Reset scroll; ensure `map_id` / `conn` branches remain unchanged (today `toggle_help` is skipped in those modes—keep that so text entry is not interrupted, **or** only allow H when not in those modes—match existing guard `edit_mode not in ("map_id", "conn")`).
5. **Draw order**: Call `_draw_help_overlay()` **after** `_draw_settings_overlay()` (and ideally near the end of the frame, before `flip`) so it paints on top when open ([~4168–4189](tools/map_editor.py)).

## Verification

- Run `python3 tools/map_editor.py`, press **H**: panel appears, TOC clickable, tabs switch, **Keys** tab shows subsections, wheel scrolls long tabs, **Esc**/**H** closes, map does not paint while open.
- Resize window: panel still usable (tabs wrap or compress—pick simplest: smaller font or two-row tabs if width is tight).

## Repo integration (planning rule)

- Add a **tracker** row in [`docs/tracker.md`](docs/tracker.md) before implementation (feature ID + scope).
- Update [`docs/tools_doc.md`](docs/tools_doc.md) **NOTES** for `map_editor.py`: describe **H** = in-app help panel (replace the sentence that says **H** only expands the footer—see current line ~40).

## Risks / edge cases

- **Small window height**: clamp scroll; ensure tab row + at least a few lines of content remain visible.
- **Stacking with other overlays** (`open_map_overlay`, prompts): either block **H** when those are active, or draw help on top and consume input—prefer **block opening** help when a blocking prompt is active (same spirit as not editing through modals).

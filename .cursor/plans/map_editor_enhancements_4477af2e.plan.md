---
name: Map editor enhancements
overview: "Add four features to the Pygame map editor: backup the current version, horizontal scrolling on the tileset selector, map zoom in/out, and mouse-based map panning."
todos:
  - id: backup
    content: Create tools/backup_2026-04-12/ with copies of map_editor.py and map_editor_config.json
    status: completed
  - id: tileset-hscroll
    content: Add horizontal scroll state, Shift+Wheel handler, and render offset to the tileset list panel
    status: completed
  - id: map-zoom
    content: Add Ctrl/Cmd+Wheel zoom on map canvas, adjusting cell_px with cursor-anchored zoom
    status: completed
  - id: map-mouse-pan
    content: Add plain Wheel vertical pan and Shift+Wheel horizontal pan on the map canvas
    status: completed
  - id: tracker-entries
    content: Log FEATURE-MAP-023 through FEATURE-MAP-026 in docs/tracker.md
    status: completed
isProject: false
---

# Map Editor Enhancements

All changes target [tools/map_editor.py](tools/map_editor.py) and [tools/map_editor_config.json](tools/map_editor_config.json). Each feature will be logged in [docs/tracker.md](docs/tracker.md) per workspace rules.

---

## 1. Backup current version

Copy the entire `tools/` folder (specifically `map_editor.py` and `map_editor_config.json`) into a new `tools/backup_v<date>/` directory before any edits. This preserves a rollback point.

- Create `tools/backup_2026-04-12/` containing copies of `map_editor.py` and `map_editor_config.json`.

---

## 2. Tileset selector horizontal scroll

**Problem:** The tileset list column has a fixed width (`TILESET_LIST_W = 292`) and only supports vertical scrolling (`tileset_list_scroll_y`). When tileset names are long or rows scale, content gets cut off horizontally.

**Approach:** Add horizontal scroll state (`tileset_list_scroll_x`) and allow Shift+Wheel on the tileset list to scroll left/right. Adjust the rendering in `draw()` to offset row content by `-tileset_list_scroll_x` and clamp accordingly.

Key changes:
- Add `self.tileset_list_scroll_x = 0` in `__init__` (~line 661)
- Add `_clamp_tileset_list_scroll_x()` method alongside the existing `_clamp_tileset_list_scroll()` (~line 1813)
- In the MOUSEWHEEL handler (~line 3318), when hovering tileset list with Shift held, scroll horizontally instead of vertically
- In the `draw()` method (~lines 2176-2250), apply `self.tileset_list_scroll_x` offset to the x-position of row text rendering
- Add a horizontal scrollbar indicator below the tileset list (similar to the existing vertical one)

---

## 3. Map editor zoom in/out

**Problem:** `cell_px` is hardcoded at 24 and never changes at runtime. There is no way to zoom the map canvas.

**Approach:** Use Ctrl/Cmd+Wheel on the map canvas to adjust `cell_px`, with configurable min/max bounds. This scales tile rendering, grid lines, hover highlight, and drag overlays — all of which already use `cell_px` for sizing.

Key changes:
- Add constants `MAP_ZOOM_MIN = 8` and `MAP_ZOOM_MAX = 64` (~line 152)
- In the MOUSEWHEEL handler (~line 3303), add a new branch: when the mouse is over `map_canvas_rect` and Ctrl/Cmd is held, increment/decrement `cell_px` by a step (e.g. 4px per notch, clamped to min/max)
- Zoom toward the mouse cursor: adjust `map_view_off_x/y` so the cell under the cursor stays in place after zoom
- The existing `draw()` loop, `map_cell_at_pixel()`, and all map overlay code already use `self.cell_px` — so everything scales automatically with no further rendering changes

---

## 4. Mouse scroll panning on the map editor

**Problem:** Map panning currently only works via keyboard arrow keys (`pan_up/down/left/right` in config). There is no mouse-driven scroll.

**Approach:** Use the mouse wheel on the map canvas (without modifier keys) to pan. Vertical wheel scrolls up/down, Shift+Wheel scrolls left/right. This mirrors the palette panel's scroll behavior.

Key changes:
- In the MOUSEWHEEL handler (~line 3303), add a branch for when mouse is over `map_canvas_rect`:
  - No modifier: `map_view_off_y -= event.y * cell_px` (vertical pan)
  - Shift held: `map_view_off_x -= event.y * cell_px` (horizontal pan)
  - Ctrl/Cmd held: zoom (from feature 3 above)
- All three behaviors share the same `map_canvas_rect.collidepoint(mx, my)` guard

**Combined MOUSEWHEEL logic for the map canvas:**

```python
elif self.map_canvas_rect.collidepoint(mx, my):
    mods = pygame.key.get_mods()
    ctrl_or_meta = bool(mods & pygame.KMOD_CTRL) or bool(mods & pygame.KMOD_META)
    if ctrl_or_meta:
        # zoom
    elif mods & pygame.KMOD_SHIFT:
        self.map_view_off_x -= int(event.y) * self.cell_px
    else:
        self.map_view_off_y -= int(event.y) * self.cell_px
```

---

## 5. Tracker entries

Log four entries in [docs/tracker.md](docs/tracker.md) with IDs FEATURE-MAP-023 through FEATURE-MAP-026, following the workspace logging rule format.

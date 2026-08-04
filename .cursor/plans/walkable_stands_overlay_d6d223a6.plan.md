---
name: Walkable stands overlay
overview: Add a map-editor toggle that draws bright green 2×2 (player footprint) outlines at every anchor where the in-game walk/collision rules allow the player to stand, reusing overworld_view.json footprint data on the existing 1×1 tile grid.
todos:
  - id: tracker
    content: Add IMPROVEMENT-MAP-037 (or next id) to docs/tracker.md before implementation
    status: completed
  - id: keys
    content: Add toggle_valid_player_stands to default_key_config, map_editor_config.json, and KEYDOWN handler
    status: completed
  - id: logic-draw
    content: Implement _player_anchor_walkable + draw green pw×ph outlines when toggle on
    status: completed
  - id: footer-doc
    content: Footer/help line + docs/tools_doc.md NOTES; mark tracker DONE
    status: completed
isProject: false
---

# Walkable player-stand overlay (map editor)

## Interpretation (locked for this plan)

- **Underlying grid:** unchanged 1×1 cells (`self.walk[y][x]`, `map_w` × `map_h`).
- **What to show:** For each **anchor** `(ax, ay)` with `0 ≤ ax ≤ map_w - pw` and `0 ≤ ay ≤ map_h - ph` (using `pw, ph = playerTilesW/H` from [`src/overworld_view.json`](src/overworld_view.json)), if **all collision sub-cells** are in-bounds and **walkable** (`walk == 0`), draw a **single bright green rectangular outline** around the **full visual footprint** (`pw × ph` cells in screen space — a 2×2 box when defaults apply).
- This matches “tiles meant to be walked on” in the **gameplay** sense (where the player may stand), not merely every 1×1 cell with `walk==0` (which would be a different visualization).

If you later want a second mode (“outline every walkable 1×1 cell”), that would be a separate toggle or mode; this plan only implements the **valid-stand** overlay.

## Implementation

### 1. Tracker and docs (per repo rules)

- Add **IMPROVEMENT-MAP-037** (or next free id) in [`docs/tracker.md`](docs/tracker.md) before coding: goal, expected behavior, scope (`tools/map_editor.py`, [`tools/map_editor_config.json`](tools/map_editor_config.json), [`docs/tools_doc.md`](docs/tools_doc.md)).
- After implementation: mark **DONE** with a one-line validation note.

### 2. State and keybinding

- In [`tools/map_editor.py`](tools/map_editor.py) `MapEditor.__init__`: boolean e.g. `self.show_valid_player_stands = False`.
- Extend [`default_key_config()`](tools/map_editor.py) with e.g. `"toggle_valid_player_stands": ["j"]` (no conflict with existing defaults; `j` is unused in [`tools/map_editor_config.json`](tools/map_editor_config.json) today).
- Add the same key entry to [`tools/map_editor_config.json`](tools/map_editor_config.json) so discoverability matches other toggles.
- In the main event loop `KEYDOWN` handling (same pattern as `toggle_help` / `toggle_eraser`), flip the boolean when `event_matches_key(event, self.key_config.get("toggle_valid_player_stands", []))`.
- Optional: brief `status_message` when toggling (“Valid stands overlay on/off”).

### 3. Collision check (mirror game, editor-local)

- Reuse existing cached overworld fields from IMPROVEMENT-MAP-036 (`_ov_player_tiles_w`, `_ov_player_tiles_h`, collision off/size) via `_refresh_overworld_view_player_config()` so behavior stays aligned with [`src/map_view.cpp`](src/map_view.cpp) `loadOverworldViewConfig_` / `mapPlayerFootprintBlockedAt_`.
- Add a small helper on `MapEditor`, e.g. `_player_anchor_walkable(self, ax: int, ay: int) -> bool`:
  - For each `(dx, dy)` in `0..collision_w-1` × `0..collision_h-1`, map cell `(cx, cy) = (ax + off_x + dx, ay + off_y + dy)`.
  - If any cell is out of `[0, map_w)` × `[0, map_h)`, return **False** (matches game out-of-bounds blocking).
  - If any `self.walk[cy][cx] != 0`, return **False**.
  - Else return **True**.

No dependency on `edit_mode`; overlay can show in paint/walk/transparent when the toggle is on (still only when **not** `world_workspace_open`, consistent with other map-canvas overlays).

### 4. Drawing

- After the main per-cell map draw loop in the non-world branch (around where walk/transparent overlays and grid lines are drawn; see ~3705–3726 in [`tools/map_editor.py`](tools/map_editor.py)), if `self.show_valid_player_stands` and not `world_workspace_open`:
  - Call `_refresh_overworld_view_player_config()`.
  - `pw, ph = self._ov_player_tiles_w, self._ov_player_tiles_h`.
  - Loop `ay` from `0` to `map_h - ph`, `ax` from `0` to `map_w - pw`.
  - If `_player_anchor_walkable(ax, ay)`, compute screen rect:
    - `rx = map_origin_x + ax * cell_px - map_view_off_x`, same for `ry`, `rw = pw * cell_px`, `rh = ph * cell_px`.
  - If rect intersects `map_canvas_rect`, `pygame.draw.rect(screen, GREEN, rect, width)` with a vivid green e.g. `(40, 255, 90)` and line width **2** (or **3** if too thin at low zoom).
- **Z-order:** draw this **below** the walk-mode hover preview (cyan/magenta) and yellow hover cell so the interactive previews remain readable when walk mode is on.

### 5. Performance and invalidation

- Worst case **O(map_w × map_h)** per frame when the toggle is on. For typical maps this is fine.
- If profiling shows issues on very large maps (e.g. 512×512), a follow-up can cache a mask invalidated on walk edits / undo / map load (not required for the initial feature).

### 6. Footer / help

- When the overlay is **on**, add one short line to the footer (collapsed or expanded) stating the toggle key and meaning: e.g. “Green boxes: valid player stand anchors (see overworld_view collision). Toggle: J.”
- Mention in expanded help block alongside other toggles.

### 7. Documentation

- Update [`docs/tools_doc.md`](docs/tools_doc.md) under `tools/map_editor.py` NOTES: new toggle, default key, semantics (2×2 outline = visual footprint at valid anchors, 1×1 walk grid unchanged).

## Risks / edge cases

- **Empty `walk` after new map:** ensure `_alloc_walk_trans` always matches map size before testing anchors (existing editor invariants).
- **`playerTilesW/H` larger than 2:** outline size follows JSON; still one rect per valid anchor.
- **World workspace open:** do not draw on world canvas (same as current walk preview scope); document.

## Acceptance criteria

- Toggle off: no green stand outlines.
- Toggle on: every legal anchor gets exactly one green `pw×ph` outline; no outline where feet/collision would hit a blocked or out-of-bounds cell.
- Changing [`src/overworld_view.json`](src/overworld_view.json) collision or footprint size changes which anchors get outlines after mtime refresh (already handled by `_refresh_overworld_view_player_config`).
- 1×1 tile grid and cell painting behavior unchanged.

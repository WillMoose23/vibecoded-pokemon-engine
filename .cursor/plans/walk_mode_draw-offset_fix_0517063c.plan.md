---
name: Walk mode draw-offset fix
overview: The map editor's walk-mode preview and valid-stands overlay are shifted 1 tile left because `_refresh_overworld_view_player_config` never reads `playerDrawOffsetTilesX` from `overworld_view.json`. Three editor functions must be updated to add this offset to their column calculations, matching the game's `walkLx = lx + playerDrawOffsetTilesX_` formula fixed earlier.
todos:
  - id: read-draw-off
    content: Add _ov_player_draw_off_x member and read playerDrawOffsetTilesX in _refresh_overworld_view_player_config; include in prev/new_t cache tuple
    status: completed
  - id: fix-anchor-walkable
    content: Add _ov_player_draw_off_x to cx in _player_anchor_walkable
    status: completed
  - id: fix-preview
    content: Shift visual box rx and collision cell cx in _draw_walk_mode_player_footprint_preview
    status: completed
  - id: fix-overlay
    content: Shift xx in _draw_valid_player_stands_overlay and tighten anchor iteration range
    status: completed
  - id: cleanup-instrumentation
    content: "Remove the two #region agent log blocks from the walk MOUSEBUTTONUP handler in map_editor.py"
    status: completed
  - id: docs-tracker
    content: Update docs/source_doc.md for changed functions and add/close tracker entry in docs/tracker.md
    status: completed
isProject: false
---

# Walk Mode Draw-Offset Fix

## Root cause

`overworld_view.json` has `"playerDrawOffsetTilesX": 1`. The in-game `worldWalkabilityBlocksAt_` already uses this correctly (`walkLx = lx + playerDrawOffsetTilesX_`).

In the editor, [`tools/map_editor.py`](tools/map_editor.py) `_refresh_overworld_view_player_config` (line 837) reads `playerCollisionOffX/Y/W/H` and `playerTilesW/H` but **never reads `playerDrawOffsetTilesX`**. Every downstream function therefore works with a column index that is 1 tile to the left of what the game actually checks/renders.

## Affected editor functions

All three are in [`tools/map_editor.py`](tools/map_editor.py):

- **`_player_anchor_walkable` (line 957)** — walk look-up formula:
  `cx = ax + cox + dx` should be `cx = ax + cox + dx + self._ov_player_draw_off_x`
  (Currently checks `walk[ay+1][ax]`; game checks `walk[ay+1][ax+1]`.)

- **`_draw_walk_mode_player_footprint_preview` (line 923)** — blue visual box origin and pink collision cell position both need `+ self._ov_player_draw_off_x` added to their column:
  - Blue box: `rx = map_origin_x + (hx + draw_off) * cp - map_view_off_x`
  - Pink cells: `cx = hx + cox + dx + draw_off`

- **`_draw_valid_player_stands_overlay` (line 973)** — the covered-cells marking uses:
  `xx = ax + dx` → should be `xx = ax + dx + self._ov_player_draw_off_x`
  Also the anchor iteration range (`range(max(0, self.map_w - pw + 1))`) should be tightened to `range(max(0, self.map_w - pw - draw_off + 1))` so the green footprint is not drawn partially off the right edge of the map.

## Changes required

### 1. `_refresh_overworld_view_player_config` (line 837)

Add a new member `_ov_player_draw_off_x` (default `0`, clamped `[0, pw-1]`). Read `playerDrawOffsetTilesX` the same way the C++ side does (matching the default of `1` from the JSON):

```python
# existing __init__ near line 698
self._ov_player_draw_off_x = 0
```

Inside `_refresh_overworld_view_player_config`:
```python
dox = 0
# ...
if "playerDrawOffsetTilesX" in data:
    dox = int(data["playerDrawOffsetTilesX"])
# after pw is clamped:
dox = max(0, min(dox, max(0, pw - 1)))
self._ov_player_draw_off_x = dox
```
Also include `dox` in the `prev`/`new_t` tuple to invalidate the cache on change.

### 2. `_player_anchor_walkable` (line 957)

```python
# before:
cx = ax + cox + dx
# after:
cx = ax + cox + dx + self._ov_player_draw_off_x
```

### 3. `_draw_walk_mode_player_footprint_preview` (line 923)

```python
# visual footprint origin (rx) — before:
rx = self.map_origin_x + hx * cp - self.map_view_off_x
# after:
rx = self.map_origin_x + (hx + self._ov_player_draw_off_x) * cp - self.map_view_off_x

# collision cell column (cx) — before:
cx = hx + cox + dx
# after:
cx = hx + cox + dx + self._ov_player_draw_off_x
```

### 4. `_draw_valid_player_stands_overlay` (line 973)

```python
# covered-cells mark — before:
xx = ax + dx
# after:
xx = ax + dx + self._ov_player_draw_off_x

# anchor iteration — before:
for ax in range(max(0, self.map_w - pw + 1)):
# after:
for ax in range(max(0, self.map_w - pw - self._ov_player_draw_off_x + 1)):
```

### 5. Clean up leftover debug instrumentation

Remove the two `# #region agent log … # #endregion` blocks in the walk `MOUSEBUTTONUP` handler (lines ~5429–5467 and ~5472–5505 in `map_editor.py`).

### 6. Docs & tracker

- `docs/source_doc.md`: update entries for `_refresh_overworld_view_player_config`, `_player_anchor_walkable`, `_draw_walk_mode_player_footprint_preview`, `_draw_valid_player_stands_overlay`.
- `docs/tracker.md`: add a new bug entry (next ID after current) and mark it DONE.

## Verification

With `playerDrawOffsetTilesX = 1`:
- Hover over tile (5, 3) in walk mode → blue box should appear at columns 6–7, rows 3–4 (shifted 1 right vs. today)
- Pink collision cell should appear at (6, 4) — 1 right of (5, 4) shown today
- J overlay green borders should align with the same visual region
- Painting walk=1 at the tile under the pink box should actually block the player in-game at the matching visual position

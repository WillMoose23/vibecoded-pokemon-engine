---
name: World tile-grid workspace
overview: Retarget the map editor world workspace so node bounds use map-tile units (width/height equal map tile size), treat world X/Y as the same grid, migrate existing `world_layout.json`, and snap node origins after edits so maps align to integer tile coordinates.
todos:
  - id: tracker-doc
    content: Add FEATURE/IMPROVEMENT tracker entry (ID) with acceptance criteria; plan doc updates to tools_doc + source_doc
    status: completed
  - id: constants-migration
    content: "map_editor.py: tile-sized width/height; WORLD_EDGE_SNAP_TILES; legacy load migration + camera rescale"
    status: completed
  - id: snap-ux
    content: "map_editor.py: _world_snap_node_origin_to_grid + call sites (mouseup, paste, add, post-fixup)"
    status: completed
  - id: grid-draw
    content: "map_editor.py: adaptive world grid step so 1-tile lines when zoom allows"
    status: completed
  - id: world-layout-notes
    content: "world_layout.py: clarify distance/edge_snap units in docstrings or comments"
    status: completed
  - id: verify
    content: "Manual repro: new sizes ratio, snap integers, legacy world_layout load + F9 export"
    status: completed
isProject: false
---

# World workspace: 1 map tile = 1 world unit + snap

## Goal and acceptance criteria

- A map of size **W×H** in map tiles occupies **W×H** units in world space (`widthPx`/`heightPx` match `mapWidthTiles`/`mapHeightTiles` numerically).
- **worldX / worldY** are interpreted on the same **integer tile grid** (placement precision); after drag, paste, and new-node placement, node origins are **snapped** to integer tile coordinates (top-left convention: `math.floor` on the world position used for the node’s AABB origin).
- Existing [`src/maps/world_layout.json`](src/maps/world_layout.json) (or path from [`WORLD_LAYOUT_JSON_PATH`](tools/map_editor.py)) still loads: **legacy** nodes where extents were `8 × tileCount` are converted to tile-space **once on load** (and camera zoom/position adjusted so on-screen layout stays comparable where possible).
- Export via [`tools/world_layout.py`](tools/world_layout.py) continues to use `_node_aabb` with `worldX/worldY/widthPx/heightPx`; numeric **separation** and `distanceWorldPx` become **tile-space distances** (field name unchanged for JSON stability; document semantic change in [`docs/tools_doc.md`](docs/tools_doc.md)).

## Root cause (current behavior)

- [`_world_add_node_from_map_id`](tools/map_editor.py) sets `widthPx`/`heightPx` to `mw * WORLD_PX_PER_MAP_TILE` (constant **8** at [`WORLD_PX_PER_MAP_TILE`](tools/map_editor.py)), so world “size” is decoupled from tile count by a fixed scale.
- [`_load_world_workspace_disk_state`](tools/map_editor.py) uses the same rule when `mapWidthTiles`/`mapHeightTiles` are present.
- No snap: [`MOUSEMOTION`](tools/map_editor.py) / drag updates `worldX`/`worldY` as raw floats from [`_world_screen_to_world`](tools/map_editor.py).

## Design decisions (minimal, explicit)

1. **Single coordinate system**: One world unit = one map tile on the logical grid. Screen mapping stays `sx = map_canvas.x + (wx - cam_x) * z` (so **`world_cam_zoom` = pixels per world tile**). After shrinking world numbers by 8×, **default / migrated camera** should multiply `zoom` by **8** and divide `cam_x`/`cam_y` by **8** so a typical session still opens at a similar pixel scale (optional but recommended to avoid “everything is 1px” at `zoom==1`).

2. **JSON field names**: Keep `widthPx`/`heightPx` and `distanceWorldPx` to avoid breaking consumers; update documentation to state values are **tile-based spans / distances** (not literal old “px” scale).

3. **Proximity threshold**: [`WORLD_EDGE_SNAP_PX`](tools/map_editor.py) (48 in old space) becomes **6 world tiles** equivalent (`48/8`); introduce e.g. `WORLD_EDGE_SNAP_TILES = 6.0` and use it for proximity draw + [`build_proximity_edges(..., edge_snap_px=...)`](tools/world_layout.py) (parameter name can stay; pass the tile threshold).

4. **Grid rendering**: [`_draw_world_workspace`](tools/map_editor.py) currently uses `step = 64` world units. Switch to an **adaptive step** (e.g. choose smallest `step` in `{1,2,4,8,...}` such that `step * z` is below a pixel cap, or cap line count) so a **1-tile grid** appears when zoomed in enough, without drawing millions of lines when zoomed out.

5. **Snap points**: Call a small helper e.g. `_world_snap_node_origin_to_grid(n: dict) -> None` after:
   - world node drag end ([`MOUSEBUTTONUP`](tools/map_editor.py) world branch, after clearing drag state / alongside overlap fixup if still needed),
   - paste offset application ([`_world_run_ctx_action`](tools/map_editor.py) `"paste"`),
   - new node insert ([`_world_add_node_from_map_id`](tools/map_editor.py) after choosing default position),
   - optionally after [`_world_fixup_overlaps`](tools/map_editor.py) (integerize again if fixup nudges floats).

6. **Secondary offsets**: Replace magic `48.0` paste nudge with **1 or 2 tiles** (e.g. `(1.0, 1.0)`). Adjust [`_world_default_node_position`](tools/map_editor.py) to return **integer** stagger positions on the tile grid.

## Files to touch

| Area | File |
|------|------|
| Node size, load migration, snap, grid step, snap threshold, paste/default pos | [`tools/map_editor.py`](tools/map_editor.py) |
| Comments / parameter semantics for edge distance | [`tools/world_layout.py`](tools/world_layout.py) (light touch) |
| Tracker + docs | [`docs/tracker.md`](docs/tracker.md), [`docs/tools_doc.md`](docs/tools_doc.md), [`docs/source_doc.md`](docs/source_doc.md) |

## Migration algorithm (on disk load)

In `_load_world_workspace_disk_state` after building each node (or once for the list):

- If `mapWidthTiles`/`mapHeightTiles` > 0 and `widthPx` ≈ `mapWidthTiles * 8` and `heightPx` ≈ `mapHeightTiles * 8` (use integer equality or tolerant check), treat as **legacy**:
  - `worldX /= 8`, `worldY /= 8`, `widthPx = mapWidthTiles`, `heightPx = mapHeightTiles`.
- If tile dims missing but `widthPx`/`heightPx` divisible by 8 and consistent with inferred map size from file, document fallback or keep as-is with conservative rule (only migrate when unambiguous).

For `editorCamera` in the same JSON: if any node was legacy-migrated, set `cam.x /= 8`, `cam.y /= 8`, `cam.zoom *= 8` (clamp to [`WORLD_CAM_ZOOM_MIN`](tools/map_editor.py) / `MAX`).

## Verification (bug-checking)

1. **New node**: Add 20×20 and 120×120 maps; at same zoom, the 120×120 node’s screen width/height ratio should be **6×** the 20×20 (matches tile ratio), not skewed by the old constant factor.
2. **Snap**: Drag a map so cursor stops between tiles; on mouse-up, node `worldX`/`worldY` are integers (or match chosen floor rule).
3. **Legacy file**: Backup current `world_layout.json`, load editor, confirm relative layout and proximity lines still look sane; re-export and diff structure (ids/order) aside from numeric rescale.
4. **F9 export**: Proximity edges still generate; distances scale consistently (tile units).

## Tracker / documentation (repo rules)

- Add a **FEATURE** (or **IMPROVEMENT**) entry in [`docs/tracker.md`](docs/tracker.md) **before** implementation with success criteria matching the above; reference **ID** in commit/changelog if you use one.
- Update [`docs/tools_doc.md`](docs/tools_doc.md) NOTES for world workspace: tile-unit world space, snap behavior, migration, proximity threshold in tiles, semantic note on `distanceWorldPx`.
- Update [`docs/source_doc.md`](docs/source_doc.md) for [`tools/map_editor.py`](tools/map_editor.py) world helpers / constants touched.

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Wrong auto-migration for hand-edited JSON | Prefer strict legacy detection (`widthPx == 8 * mw`); document manual fix path. |
| Grid perf at `step=1` when zoomed out | Adaptive grid step with pixel / count caps. |
| Zoom feels wrong after migration | Always apply `cam.zoom *= 8` when legacy nodes detected; optionally set editor default `world_cam_zoom` to `8.0` for new sessions. |

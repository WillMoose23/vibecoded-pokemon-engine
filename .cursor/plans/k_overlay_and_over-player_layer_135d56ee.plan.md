---
name: K overlay and over-player layer
overview: Add a `K`-toggled bright-orange 2x2 valid-stand overlay in the editor, and add a new separate-grid map layer that marks tiles to render over the player in both editor and runtime.
todos:
  - id: tracker-log
    content: Create/update tracker entries before implementation and keep statuses synced
    status: completed
  - id: k-toggle-overlay
    content: Add K keybinding and bright-orange valid-stand overlay toggle in map_editor
    status: completed
  - id: editor-overplayer-grid
    content: Add separate over-player grid editing, visualization, and JSON save/load in map_editor
    status: completed
  - id: runtime-schema-parse
    content: Extend MapData and map_data parsing for new over-player layer with backward compatibility
    status: completed
  - id: runtime-draw-pass
    content: Split map/world tile draws into base + player + over-player passes
    status: completed
  - id: qa-verify
    content: Run requested performance-focused QA checks and functional verification
    status: completed
  - id: docs-update
    content: Update source_doc/tools_doc and finalize tracker DONE records
    status: completed
isProject: false
---

# K Overlay + Over-Player Layer Plan

## Goal

Implement two aligned features:
- `K` toggles a bright-orange overlay showing every valid 2x2 player stand footprint in the map editor.
- A new separate binary grid marks tiles that render over the player sprite (roof/canopy effect) in both editor and game runtime.

## Acceptance Criteria

- Pressing `K` toggles the valid-stand overlay (orange lines) on/off with status text and help/footer key listing.
- Overlay boundaries match current collision logic (`playerDrawOffsetTilesX`, `playerCollisionOff*`, `playerCollisionW/H`) and map pan/zoom.
- New over-player grid is editable in the editor and persisted in map JSON.
- Runtime draws marked over-player tiles after player draw in both single-map and world-view rendering.
- Existing maps (without the new layer) continue to load/render safely.

## Code Review Findings (Pre-implementation)

- **HIGH:** No current per-tile over-player priority exists. Runtime currently draws all tile layers before player (`src/map_view.cpp`), so roofs cannot occlude player without a new data path.
- **MEDIUM:** `K` is not currently bound in `tools/map_editor.py`; adding it is low-risk but must not conflict with text-entry/edit-mode guards.
- **MEDIUM:** Any new per-tile flag must stay performant in render loops (`drawMapView_`, `drawWorldLayoutView_`) to avoid extra allocations/scans.

## Files / Subsystems to Change

- Editor behavior and overlays: [`/Users/rheyn/Desktop/project/tools/map_editor.py`](/Users/rheyn/Desktop/project/tools/map_editor.py)
- Runtime map schema: [`/Users/rheyn/Desktop/project/include/map_data.h`](/Users/rheyn/Desktop/project/include/map_data.h)
- JSON parsing/loading: [`/Users/rheyn/Desktop/project/src/map_data.cpp`](/Users/rheyn/Desktop/project/src/map_data.cpp)
- Runtime render passes: [`/Users/rheyn/Desktop/project/src/map_view.cpp`](/Users/rheyn/Desktop/project/src/map_view.cpp)
- Tool docs: [`/Users/rheyn/Desktop/project/docs/tools_doc.md`](/Users/rheyn/Desktop/project/docs/tools_doc.md)
- Source docs: [`/Users/rheyn/Desktop/project/docs/source_doc.md`](/Users/rheyn/Desktop/project/docs/source_doc.md)
- Tracker lifecycle record: [`/Users/rheyn/Desktop/project/docs/tracker.md`](/Users/rheyn/Desktop/project/docs/tracker.md)

## Implementation Steps

1. **Tracker-first bug/feature logging (required by repo rules)**
   - Add new entries in `docs/tracker.md` before substantive code edits:
     - one for `K` overlay enhancement
     - one for over-player runtime feature
   - Include required fields and keep statuses updated through DONE after verification.

2. **Editor: add `K` toggle + orange valid-stand overlay**
   - Add key config action (e.g., `toggle_orange_valid_stands`) defaulting to `k` in `default_key_config` and config load/merge paths.
   - Reuse existing valid-stand cache and geometry build path; switch overlay color to bright orange for the `K` overlay path.
   - Keep existing `J` behavior intact unless explicitly merged; avoid regressions in walk-mode preview and footer help.
   - Update footer/help/status text to reflect `K` toggle.

3. **Data model: separate over-player grid in editor + JSON**
   - Add editor grid storage similar to `self.walk` / `self.trans` (e.g., `self.over_player`).
   - Load/save under `layers` as separate binary grid (chosen approach), with safe defaults for missing data.
   - Add an editor mode and paint interaction for this grid, including overlay tint for visibility.

4. **Runtime schema + parsing**
   - Extend `MapData` with an over-player grid field and validation helper behavior matching map dimensions.
   - Parse optional `layers.overPlayer` (or chosen key) in `src/map_data.cpp` with robust fallback when absent.

5. **Runtime draw-order integration (single-map + world)**
   - Split tile rendering into two passes without changing camera math:
     - base tiles (not over-player)
     - draw player
     - over-player tiles only
   - Apply in `drawMapView_` and `drawWorldLayoutView_` consistently.
   - Ensure event sprite layering behavior remains intentional.

6. **Performance-focused QA checks (requested)**
   - Validate no per-frame heap churn from new overlays (reuse surfaces, avoid temp vectors in hot loops).
   - Keep render loops O(visible_tiles × layers) with simple branch checks against over-player grid.
   - Verify world-view remains responsive on large maps.

7. **Verification**
   - Editor: toggle `K`, pan/zoom, and confirm orange overlay alignment with hover footprint/collision boxes.
   - Editor paint/save/load: mark over-player cells, reload map, confirm persistence.
   - Runtime: stand behind roof-marked tiles; marked cells must render above player.
   - Regression: maps lacking over-player layer still load and render as before.

8. **Documentation + tracker closeout**
   - Update `docs/tools_doc.md` for editor key/mode and map JSON layer behavior.
   - Update `docs/source_doc.md` for changed runtime/editor functions and schema fields.
   - Set tracker entries to DONE with root-cause/fix/validation notes.

## Risks / Edge Cases

- Keybinding conflicts or toggle handling while in text-entry modes.
- Partial footprints near right map boundary with `playerDrawOffsetTilesX`.
- World view with overlapping instances: over-player pass must use the same instance/tile visibility rules as base pass.
- Backward compatibility: absent `overPlayer` layer must default to zeros.

## Validation Matrix (minimal)

- `K` overlay on/off + correct orange color.
- Walk/collision alignment remains unchanged after overlay refactor.
- Over-player roof tile draws above player in both map modes.
- Save/load round-trip preserves over-player grid.
- No significant FPS drop in dense maps.
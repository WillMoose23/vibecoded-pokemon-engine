---
name: Map editor layer-ui upgrade
overview: Implement the requested map-editor UI/workflow changes with a pre-change filesystem backup, then run behavior-preserving refactor, RAM/runtime QA review, and validation/testing. Keep tracker and docs updated per repo rules before and after substantive work.
todos:
  - id: log-and-backup
    content: Create required tracker entries and filesystem backup snapshot before code edits
    status: completed
  - id: layout-migration
    content: Move tileset filesystem to bottom horizontal strip and stretch map viewport
    status: completed
  - id: layer-popup
    content: Implement L-triggered layer manager popup with rename/reorder/over-player applicability/add/delete
    status: completed
  - id: safe-refactor
    content: Run behavior-preserving refactor on touched editor code paths
    status: completed
  - id: qa-perf
    content: Perform RAM/runtime QA review and apply low-risk fixes if needed
    status: completed
  - id: validate-and-docs
    content: Run validators/tests and update tracker/source_doc/tools_doc to DONE
    status: completed
isProject: false
---

# Map Editor Feature + QA Plan

## Goal
Deliver the requested map editor improvements:
- Create a rollback backup before any code change.
- Remove bottom tab usage and move the tileset filesystem there in a horizontal strip.
- Expand/stretch map view to use reclaimed layout space.
- Bind `L` to open a layer popup menu for all map layers with rename, vertical drag reorder, over-player applicability toggle, add, and delete.
- After implementation, perform behavior-preserving refactor, RAM/runtime QA review, and run unit/validation tests.

## Acceptance Criteria
- Pressing `L` opens a modal/popup layer manager (not direct layer add).
- Popup supports: add layer, delete layer, rename layer, drag-reorder in vertical stack, and per-layer toggle controlling whether layer participates in over-player pass.
- Bottom UI no longer uses old tab presentation; tileset filesystem is shown horizontally at bottom.
- Map canvas visibly expands where old bottom-tab area existed and remains responsive after resize.
- Existing map loading/saving still works for legacy and current schema.
- Tracker entries exist (FEATURE + REFACTOR + QA/BUG as needed) with required fields/status transitions.
- Docs updated in `/docs/source_doc.md` and `/docs/tools_doc.md` for changed behavior/tooling.
- Validation/test commands complete without new failures.

## Files and Subsystems to Touch
- Primary editor implementation: [`/Users/rheyn/Desktop/project/tools/map_editor.py`](/Users/rheyn/Desktop/project/tools/map_editor.py)
- Keybind config updates: [`/Users/rheyn/Desktop/project/tools/map_editor_config.json`](/Users/rheyn/Desktop/project/tools/map_editor_config.json)
- Tracker logging lifecycle: [`/Users/rheyn/Desktop/project/docs/tracker.md`](/Users/rheyn/Desktop/project/docs/tracker.md)
- Source documentation updates: [`/Users/rheyn/Desktop/project/docs/source_doc.md`](/Users/rheyn/Desktop/project/docs/source_doc.md)
- Tool documentation updates (if validation/test flow or tool behavior notes change): [`/Users/rheyn/Desktop/project/docs/tools_doc.md`](/Users/rheyn/Desktop/project/docs/tools_doc.md)
- Map schema compatibility/verification references: [`/Users/rheyn/Desktop/project/tools/validate_maps.py`](/Users/rheyn/Desktop/project/tools/validate_maps.py), [`/Users/rheyn/Desktop/project/src/map_data.cpp`](/Users/rheyn/Desktop/project/src/map_data.cpp), [`/Users/rheyn/Desktop/project/include/map_data.h`](/Users/rheyn/Desktop/project/include/map_data.h)

## Implementation Steps
1. **Log before work + backup snapshot**
   - Add tracker records (at minimum one `FEATURE`; separate `REFACTOR` and `IMPROVEMENT`/`BUG` entries if scope requires) with required fields and `OPEN` status.
   - Create filesystem backup snapshot of targeted files/directories (editor/config/docs touched by this task) under a timestamped backup path and record location in tracker.
2. **Bottom layout migration**
   - In `MapEditor.relayout` and corresponding draw/input code, remove old bottom-tab usage.
   - Rehome tileset filesystem UI into a bottom horizontal strip (horizontal scrolling/selection behavior where needed).
   - Update hit-testing and drag/drop logic to new geometry.
3. **Map viewport expansion**
   - Recompute layout rectangles so map canvas expands into reclaimed area while preserving minimum sizes/margins.
   - Verify pan/zoom, world workspace clipping, and overlays still respect clip rects.
4. **Layer popup on `L`**
   - Replace `layer_add` direct behavior for `L` with opening a dedicated layer-manager popup.
   - Ensure world-label toggle precedence remains valid where intended (world workspace conflict handling).
5. **Layer manager capabilities (all map layers)**
   - Add popup state + rendering for a vertical draggable layer stack.
   - Implement rename workflow (inline edit or focused prompt), add, delete, and drag reorder.
   - Add per-layer `applies_to_over_player` flag (or equivalent persisted property) and integrate draw/save/load behavior so non-applicable layers are excluded from over-player mode contribution.
   - Preserve legacy schema compatibility on load/save.
6. **Behavior-preserving refactor pass**
   - Apply minimal safe cleanup in touched editor code (extract repeated popup/layout blocks, simplify branching, remove dead paths) without changing behavior.
   - Log/update `REFACTOR` tracker status accordingly.
7. **QA RAM + performance review**
   - Review hot paths in editor draw loop and popup interactions (allocation churn, list reorder operations, cache reuse).
   - Apply only justified, low-risk optimizations if needed (no speculative rewrites), then document findings and verification steps.
8. **Validation and tests**
   - Run map/event validators and project test commands available in repo conventions (`validate_maps.py`, `validate_map_events.py`, plus any discovered unit-test runner).
   - Manually verify critical editor flows: open popup with `L`, add/rename/delete/reorder/toggle layers, save/reload map, over-player behavior, resized layout.
9. **Docs + tracker closure**
   - Update `/docs/source_doc.md` and `/docs/tools_doc.md` with new keybinding/modal/layout/layer semantics.
   - Move tracker entries through `IN_PROGRESS` → `REVIEW` → `DONE` after validation evidence.

## Risks and Edge Cases to Verify
- `L` key overlap with world-label toggle in world workspace.
- Drag reorder stability while list is filtered/scrolled and while active layer changes.
- Prevent deleting the last required base layer.
- Rename collisions/empty names and persistence integrity.
- Legacy maps (`ground`/`groundCells`) upgrade path and backward compatibility.
- Over-player applicability flags interacting with existing `layers.overPlayer` behavior.
- Large layer counts and frequent redraws causing frame drops or allocation spikes.

## Verification Matrix
- Functional: popup operations + save/load persistence + mode interactions.
- Compatibility: old map JSONs still load and render correctly.
- Performance: no obvious regression in editor frame responsiveness during drag/reorder and redraw.
- Tooling/tests: validator and unit-test commands pass.
- Documentation: source/tool docs and tracker fully aligned with final behavior.
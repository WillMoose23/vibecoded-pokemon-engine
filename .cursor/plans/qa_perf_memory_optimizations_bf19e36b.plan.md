---
name: qa perf memory optimizations
overview: Implement all RAM/performance adjustments identified by the qa-ram-performance review, while complying with project logging and documentation rules.
todos:
  - id: log-improvement
    content: Create tracker entry and set status OPEN -> IN_PROGRESS before code edits
    status: completed
  - id: text-cache
    content: Implement text texture caching in Game to remove per-frame text allocations
    status: completed
  - id: map-metadata
    content: Precompute tileset render metadata and use fast lookups in map draw loop
    status: completed
  - id: walkability-cache
    content: Cache walkability grid validity and remove repeated shape scans
    status: completed
  - id: pokedex-index
    content: Add pokedex lookup index and refactor random foe selection lookups
    status: completed
  - id: low-cleanups
    content: Add display text line cache and throttle perf sampler frequency
    status: completed
  - id: verify-docs
    content: Run validation checks, update source docs, and finalize tracker status
    status: completed
isProject: false
---

# QA RAM/Performance Optimization Plan

## Scope
Implement HIGH, MEDIUM, and LOW optimization fixes from the review across rendering hot paths, map-view logic, and data lookup paths.

## 1) Track Work Before Code
- Add a new improvement entry in [`/Users/rheyn/Desktop/project/docs/tracker.md`](/Users/rheyn/Desktop/project/docs/tracker.md) with required fields (`ID`, `TYPE`, `TITLE`, `DESCRIPTION`, `EXPECTED_BEHAVIOR`, `SCOPE`, `PRIORITY`, `STATUS`, `ASSIGNED_TO`), and include bug-style fields only if marked as `BUG`.
- Set `TYPE: IMPROVEMENT`, `STATUS: OPEN` first, then progress `IN_PROGRESS -> REVIEW -> DONE` as changes complete.
- Reference the created issue ID in modified source files/comments where project convention already does so.

## 2) Remove Per-Frame Text Allocation Churn (HIGH)
- In [`/Users/rheyn/Desktop/project/include/game.h`](/Users/rheyn/Desktop/project/include/game.h), add a lightweight text texture cache structure (keyed by text + color) and cache lifecycle helpers.
- In [`/Users/rheyn/Desktop/project/src/game.cpp`](/Users/rheyn/Desktop/project/src/game.cpp), refactor `renderText` call path to reuse cached textures instead of recreating `SDL_Surface`/`SDL_Texture` every frame.
- Pre-cache static HUD/help lines used by `drawKeybindHud_`, `drawPerfHud_`, and map-picker title/help text; invalidate cache on shutdown and when font/renderer lifecycle changes.

## 3) Precompute Map Render Metadata (HIGH)
- In [`/Users/rheyn/Desktop/project/include/game.h`](/Users/rheyn/Desktop/project/include/game.h), add a fast tileset render metadata map (texture pointer, queried texture dimensions, computed columns/stride).
- In [`/Users/rheyn/Desktop/project/src/map_view.cpp`](/Users/rheyn/Desktop/project/src/map_view.cpp), populate metadata once when map/tilesets load (`loadMapForView_`) and clear on `destroyMapViewTextures_`/map close.
- Update `drawMapView_` to use O(1) metadata lookups per cell and avoid repeated `findMapTilesetDef_` and `SDL_QueryTexture` in inner loops.

## 4) Cache Walkability Grid Validity (MEDIUM)
- In [`/Users/rheyn/Desktop/project/include/game.h`](/Users/rheyn/Desktop/project/include/game.h), add a boolean state for walkability-grid validity.
- In [`/Users/rheyn/Desktop/project/src/map_view.cpp`](/Users/rheyn/Desktop/project/src/map_view.cpp), compute this once after map load and consume it in `mapWalkabilityBlocksAt_` / movement checks instead of rescanning dimensions repeatedly.

## 5) Build Pokedex Lookup Index (MEDIUM)
- In [`/Users/rheyn/Desktop/project/include/game.h`](/Users/rheyn/Desktop/project/include/game.h), add cached lookup storage for `pokedexNum -> speciesKey` and any needed candidate list.
- In [`/Users/rheyn/Desktop/project/src/game.cpp`](/Users/rheyn/Desktop/project/src/game.cpp), build the index once after loading `monster.json`.
- Refactor `speciesKeyForPokedexNum` and `pickRandomFoeKey` to use the cache and remove repeated full-dataset scans.

## 6) Low-Impact Cleanups (LOW)
- In [`/Users/rheyn/Desktop/project/src/game.cpp`](/Users/rheyn/Desktop/project/src/game.cpp), avoid per-frame substring allocations in `drawDisplayText` by caching split lines when `displayText_` changes.
- In [`/Users/rheyn/Desktop/project/src/perf_stats.cpp`](/Users/rheyn/Desktop/project/src/perf_stats.cpp), throttle expensive sampling to a fixed interval (e.g., 250ms) while preserving EMA output behavior.

## 7) Verification and Documentation
- Run project build/tests used by this repo and sanity-check runtime behavior (title, battle, map viewer, F3/F4 HUD).
- Run lints for touched files and fix introduced issues.
- Update [`/Users/rheyn/Desktop/project/docs/source_doc.md`](/Users/rheyn/Desktop/project/docs/source_doc.md) with required sections/indentation for each changed file/function.
- Update tracker status to `REVIEW`, then `DONE` after verification.

## Key Implementation Notes
- Keep optimization changes behavior-preserving (no gameplay logic changes).
- Prefer localized refactors over broad rewrites.
- Ensure all new caches are explicitly cleared during teardown to avoid texture/resource leaks.
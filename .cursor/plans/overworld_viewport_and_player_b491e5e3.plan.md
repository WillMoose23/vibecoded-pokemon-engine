---
name: Overworld viewport and player
overview: Extend the existing SDL map viewer (FEATURE-MAP-008) so map JSON renders at a playable scale, the visible region is a configurable N×M tile window defaulting to 15×15, and WASD moves a player tile with the camera following—using `walkability` when present.
todos:
  - id: log-feature
    content: Add FEATURE-MAP-027 entry to docs/tracker.md (before code changes)
    status: completed
  - id: config-viewport
    content: Add overworld_view.json + load viewTilesW/H with15×15 defaults and clamping
    status: completed
  - id: scale-and-draw
    content: Fix tilePx/panel math; parameterize loops on view W/H; draw player overlay
    status: completed
  - id: move-and-camera
    content: WASD moves player with walkability; spawn logic; syncCameraToFollowPlayer_
    status: completed
  - id: help-text
    content: Update game.cpp key-3 description for new controls
    status: completed
isProject: false
---

# Overworld: JSON map render, configurable viewport, player movement

## Current state (what you already have)

- Map JSON is **already parsed** in [`src/map_data.cpp`](src/map_data.cpp) into [`MapData`](include/map_data.h) (`tileLayers`, optional `walkabilityLayer`, dimensions, tile size metadata).
- The “map viewer” path (key **3**) in [`src/map_view.cpp`](src/map_view.cpp) **already draws** those layers using [`loadMapForView_`](src/map_view.cpp) and tileset textures from [`src/tilesets.json`](src/tilesets.json).
- The **tiny20×20 dot** look in your screenshot is largely from **scaling**: `tilePx` is computed as `min(kLogicalWidth / (kViewTiles * tw), …)` with `tw = 16`, so the height constraint yields very small tiles (~4px) instead of filling the 1280×720 logical view.

```332:333:src/map_view.cpp
    int tilePx = std::min(kLogicalWidth / (kViewTiles * tw), kLogicalHeight / (kViewTiles * th));
    tilePx = std::max(4, tilePx);
```

## Intended behavior after the change

1. **Rendering** — Keep the existing layer blit logic; change **only** how `tilePx` (and panel size) is chosen so the **viewport rectangle** (N×M tiles) **fills** the logical resolution (e.g. `tilePx = min(kLogicalWidth / N, kLogicalHeight / M)` with reasonable min/max clamps). Optionally keep a small inner margin if you want UI chrome later; not required for the first pass.
2. **Configurable camera size** — Replace the fixed `constexpr int kViewTiles = 10` with **runtime width/height in tiles**, default **15×15**.
   - **Suggested approach**: optional JSON [`src/overworld_view.json`](src/overworld_view.json) (or similar) e.g. `{ "viewTilesW": 15, "viewTilesH": 15 }`, read once when entering map view (or on `loadMapForView_`). If the file is missing or invalid, fall back to 15×15. Clamp to sane bounds (e.g. 3–64) to avoid divide-by-zero or absurd panels.
   - Wire these into `clampMapCamera_`, `drawMapView_` loops, and any user-facing hint text (show current viewport size).
3. **Player + movement** — Add **integer tile coordinates** for the player (e.g. `mapPlayerTileX_`, `mapPlayerTileY_` in [`include/game.h`](include/game.h)).
   - On `loadMapForView_`, **spawn** at the first **walkable** cell (scan row-major) if `walkabilityLayer` is populated and matches `width`×`height`; otherwise spawn at **(0, 0)** or map center, clamped in-bounds.
   - **WASD** in `handleMapUiKey_` attempts a **one-tile** step; **do not** free-pan the camera with WASD anymore.
   - **Collision**: if `walkabilityLayer` is valid, treat `1` as blocked, `0` as walkable; if absent, only clamp to map bounds.
   - After a successful move, call **`syncCameraToFollowPlayer_()`**: set `mapCamTileX_` / `mapCamTileY_` so the player stays **centered** when possible:
     - `camX = clamp(playerX - viewW/2, 0, max(0, mapW - viewW))` (and similarly for Y), using integer math consistent with your tile indexing (document the choice: top-left of camera vs “center” bias for even widths).
4. **Draw the character** — After all tile layers for a cell, draw a simple **placeholder** on the player’s screen tile (e.g. semi-transparent filled rect, or a small distinct border) so movement is visible without requiring new art yet. Keep it in [`drawMapView_`](src/map_view.cpp) or a small helper.
5. **Copy / discoverability** — Update the key-3 blurb in [`src/game.cpp`](src/game.cpp) (still says “10×10” and “WASD pans”) to match **configurable viewport** and **WASD moves**.

## Process / tracker (workspace rule)

Before implementation, add **`FEATURE-MAP-027`** (or next free ID) to [`docs/tracker.md`](docs/tracker.md) describing: playable-scale viewport, configurable N×M tiles (default 15×15), player movement with walkability, camera follow. Reference **`FEATURE-MAP-027`** in code comments where you touch the map viewer. Update status through the lifecycle as you work.

## Files to touch (minimal set)

| File | Change |
|------|--------|
| [`docs/tracker.md`](docs/tracker.md) | New feature entry |
| [`include/game.h`](include/game.h) | Player tile state; optional loaded `viewTilesW_` / `viewTilesH_`; private helpers declarations |
| [`src/map_view.cpp`](src/map_view.cpp) | Load view config; replace `kViewTiles`; fix `tilePx`; camera follow; WASD → player; draw player |
| [`src/game.cpp`](src/game.cpp) | Help text for key 3 |
| [`src/overworld_view.json`](src/overworld_view.json) | **New** optional config (defaults documented in code if file absent) |

No change required to JSON **schema** of maps themselves; [`loadMapFromFile`](src/map_data.cpp) already provides what you need.

## Architecture sketch```mermaid
flowchart LR
  subgraph load [Load map]
    JSON[Map JSON file]
    MapData[MapData + walkability]
    JSON --> MapData
  end
  subgraph play [Per frame / input]
    Keys[WASD]
    Move[Try step + collision]
    Cam[Clamp camera to follow player]
    Draw[Draw NxM tiles + player]
    Keys --> Move
    Move --> Cam
    Cam --> Draw
  end MapData --> Move
  MapData --> Draw
```

## Success criteria

- From repo root, key **3** → pick a map → you see a **large** 15×15 (or configured) tile window, not a miniature grid.
- WASD moves a visible marker **one tile** at a time; camera **follows**; edges of the map clamp the camera so the view never shows invalid coordinates.
- Maps with `layers.walkability` in JSON (e.g. [`src/maps/tree_map_border.json`](src/maps/tree_map_border.json)) **block** movement onto `1` cells.
- Changing `viewTilesW` / `viewTilesH` in config (within bounds) changes the visible tile count without recompiling.

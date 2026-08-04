---
name: Player grid and walk frames
overview: Apply a +1 tile-width horizontal render offset for the player sprite, and replace the current 4/8-frame walk with parity-based 2-frame pairs (1–2 then 3–4) plus a 5-frame merged sequence (1,2,3,4,1) for continuous two-stride moves.
todos:
  - id: draw-offset-x
    content: Add +1*tilePx to baseX in drawMapViewPlayerFootprint_ (or JSON-driven offset)
    status: completed
  - id: walk-parity-frames
    content: Restore mapWalkStepParity_; 2-frame [0,1]/[2,3]; merge 5-frame [0,1,2,3,0]; fix merge gate to frameCount==2
    status: completed
  - id: docs-tracker
    content: Update source_doc.md + tracker (and tools_doc if JSON offset)
    status: completed
isProject: false
---

# Player horizontal alignment + walk frame patterns

## 1. Horizontal “off by one” fix

**Approach:** Treat this as **visual alignment** unless you later confirm gameplay coordinates must change. The 2×2 **logical** anchor (`mapPlayerTileX_` / `mapPlayerTileY_`) stays the source of truth for collision, events, and scripts.

- In [`drawMapViewPlayerFootprint_`](src/map_view.cpp), after computing `baseX` from `mapPlayerTileX_`, camera, walk lerp, and `tilePx`, add a fixed **horizontal screen offset of one tile width**: `baseX += tilePx` (i.e. shift the drawn footprint **one cell to the right**). This matches “move the player horizontal by 1” on the same grid the renderer uses.
- **If** playtesting shows the error is the opposite direction, flip the sign once (`baseX -= tilePx`).
- **Optional hardening:** add `playerDrawOffsetTilesX` (default `1`) to [`src/overworld_view.json`](src/overworld_view.json) and parse it in [`loadOverworldViewConfig_`](src/map_view.cpp) into a member like `playerDrawOffsetTilesX_` (float or int), so tuning does not require recompiles. Only include if you want config; otherwise a named constant in `map_view.cpp` is enough.

## 2. Walk animation rules (1-based user frames = columns 0–3)

| Case | Frames (1-based) | `mapWalkCols_` (0-based) | `mapWalkFrameCount_` |
|------|------------------|---------------------------|----------------------|
| A → B (first stride) | 1, 2 | `[0, 1]` | 2 |
| B → C (next stride, same facing / parity) | 3, 4 | `[2, 3]` | 2 |
| Continuous A → B → C (merged segment) | 1, 2, 3, 4, 1 | `[0, 1, 2, 3, 0]` | 5 |

**Parity:** Reintroduce **`mapWalkStepParity_`** in [`include/game.h`](include/game.h) (removed when switching to the 1–2–3–4 full cycle). On starting a **single-stride** segment from idle:

- `mapWalkStepParity_ == 0`: `mapWalkFrameCount_ = 2`, columns `0, 1`
- `mapWalkStepParity_ == 1`: `mapWalkFrameCount_ = 2`, columns `2, 3`

On **`commitCompletedMapWalk_`**, flip parity **once per stride committed**: `for (t = 0; t < mapWalkTilesInSegment_; ++t) mapWalkStepParity_ ^= 1;` (same structure as before parity was removed).

**Merge (repeat on frame 0):** In [`requestPlayerMoveOnMap_`](src/map_view.cpp), change the upgrade check from `mapWalkFrameCount_ == 4` to **`== 2`** (first frame of a normal 2-frame stride). On success:

- `mapWalkTilesInSegment_ = 2`
- `mapWalkFrameCount_ = 5`
- `mapWalkCols_ = {0, 1, 2, 3, 0, ...}` (only first five indices used)

Keep existing **blocked-cell** checks for `+stride` and `+2*stride` anchors (`kMapWalkAnchorStrideTiles` unchanged).

**Defaults:** Set `mapWalkFrameCount_` default in `game.h` to **2** (not 4).

## 3. Unchanged pieces

- [`mapPlayerWalkVisualOffsetsTiles_`](src/map_view.cpp): Still lerps over `mapWalkTilesInSegment_ * kMapWalkAnchorStrideTiles` tiles; only frame **count** and **column indices** change.
- Idle pose: keep column **0** (frame 1) when not walking.
- Auto-chain and `playerLocked` behavior unchanged.

## 4. Documentation and tracker

- Update [`docs/source_doc.md`](docs/source_doc.md) (`requestPlayerMoveOnMap_` / walk description): 2-frame pairs by parity, 5-frame merge, draw offset.
- Add a short note to [`docs/tracker.md`](docs/tracker.md) (e.g. extend **FEATURE-MAP-031** or **IMPROVEMENT-MAP-032** follow-up) describing alignment + frame rules.
- If JSON offset is added, mention keys in [`docs/tools_doc.md`](docs/tools_doc.md).

## 5. Verification

- Build: `make`
- Manual: single step alternates **1–2** / **3–4** on successive steps; hold/repeat merge shows **1,2,3,4,1** over two strides; sprite sits correctly on the building/door grid after `+tilePx` X offset.

---
name: Configurable collision footprint
overview: "Add a configurable collision sub-rectangle within the player's visual 2x2 footprint, loaded from overworld_view.json, so 1x1 blocked cells only block the player when they fall under the collision region (default: bottom-left 1x1 cell)."
todos:
  - id: backup
    content: Copy src/ and tools/ to backups/pre_collision_footprint_YYYYMMDD/
    status: completed
  - id: tracker
    content: Add IMPROVEMENT entry to docs/tracker.md
    status: completed
  - id: json-config
    content: Add collision footprint fields to overworld_view.json
    status: completed
  - id: game-h
    content: Add four collision footprint members to include/game.h
    status: completed
  - id: load-config
    content: Parse and clamp new fields in loadOverworldViewConfig_()
    status: completed
  - id: collision-map
    content: Update mapPlayerFootprintBlockedAt_ to use collision sub-rect
    status: completed
  - id: collision-world
    content: Update worldPlayerFootprintBlockedAt_ to use collision sub-rect
    status: completed
  - id: source-doc
    content: Update docs/source_doc.md for new fields and changed functions
    status: completed
isProject: false
---

# Configurable Collision Footprint

## Problem

The player visual sprite occupies a 2x2 tile area, and `mapPlayerFootprintBlockedAt_` checks **all four** 1x1 cells. A single blocked cell anywhere under the sprite blocks the entire anchor position. This makes fine 1x1 walkability editing behave unexpectedly: one blocked cell can make two or more "logical tiles" unreachable.

## Solution

Decouple the **visual footprint** (2x2, used for drawing) from the **collision footprint** (a configurable sub-rectangle, used for walkability checks). Default: bottom-left 1x1 cell only (Pokemon-style "feet" collision).

## Design

New JSON fields in [src/overworld_view.json](src/overworld_view.json):

```json
{
  "playerCollisionOffX": 0,
  "playerCollisionOffY": 1,
  "playerCollisionW": 1,
  "playerCollisionH": 1
}
```

These define a sub-rectangle **relative to the visual anchor** (top-left of the 2x2 sprite). With the defaults above, the collision cell is `(anchor.x + 0, anchor.y + 1)` -- the bottom-left cell.

```
Visual 2x2:       Collision (default):
 [TL] [TR]         [ ]  [ ]
 [BL] [BR]         [X]  [ ]
```

The user can later change to e.g. `offX:0, offY:1, W:2, H:1` (full bottom row) or any other sub-rect.

## Files to change

### 1. Backup (first step)

Copy current `src/` and `tools/` to `backups/pre_collision_footprint_YYYYMMDD/` before any edits.

### 2. [src/overworld_view.json](src/overworld_view.json)

Add the four new fields with defaults (`offX:0, offY:1, W:1, H:1`).

### 3. [include/game.h](include/game.h)

Add four new members alongside the existing visual footprint fields (~line 252):

```cpp
int playerCollisionOffX_ = 0;
int playerCollisionOffY_ = 1;
int playerCollisionW_ = 1;
int playerCollisionH_ = 1;
```

### 4. [src/map_view.cpp](src/map_view.cpp) -- three changes

**a) `loadOverworldViewConfig_()` (~line 105):** Parse and clamp the four new JSON fields. Clamp collision rect to stay within visual footprint bounds:
- `offX` in `[0, playerTilesW - 1]`, `offY` in `[0, playerTilesH - 1]`
- `W` in `[1, playerTilesW - offX]`, `H` in `[1, playerTilesH - offY]`

**b) `mapPlayerFootprintBlockedAt_()` (~line 633):** Replace the full `pw x ph` loop with the collision sub-rect:

```cpp
bool Game::mapPlayerFootprintBlockedAt_(int topLeftX, int topLeftY) const
{
    if (mapUiMode_ == MapUiMode::ViewWorld)
    {
        return worldPlayerFootprintBlockedAt_(topLeftX, topLeftY);
    }
    for (int dy = 0; dy < playerCollisionH_; ++dy)
    {
        for (int dx = 0; dx < playerCollisionW_; ++dx)
        {
            if (mapWalkabilityBlocksAt_(
                    topLeftX + playerCollisionOffX_ + dx,
                    topLeftY + playerCollisionOffY_ + dy))
            {
                return true;
            }
        }
    }
    return false;
}
```

**c) `worldPlayerFootprintBlockedAt_()` (~line 317):** Same change -- use collision sub-rect instead of full `pw x ph`.

### 5. [docs/tracker.md](docs/tracker.md)

Add IMPROVEMENT entry before implementation.

### 6. [docs/source_doc.md](docs/source_doc.md)

Update `loadOverworldViewConfig_` description, `mapPlayerFootprintBlockedAt_`, `worldPlayerFootprintBlockedAt_`, and the `overworld_view.json` NOTES to document the collision footprint fields and their defaults.

## Edge cases

- **Collision rect larger than visual footprint:** Clamped during load so this cannot happen.
- **Missing JSON fields:** Fall back to defaults (offX:0, offY:1, W:1, H:1) -- bottom-left cell.
- **Spawn logic** (`spawnPlayerOnLoadedMap_`, `spawnPlayerOnWorldLayout_`): Already calls `mapPlayerFootprintBlockedAt_` / `worldPlayerFootprintBlockedAt_`, so spawn will respect the new collision rect automatically.
- **Merged two-stride walks:** `requestPlayerMoveOnMap_` calls `mapPlayerFootprintBlockedAt_` for intermediate and final positions; no change needed there since the function signature is unchanged.
- **Map editor:** No changes needed. 1x1 paint stays as-is; the game engine now interprets it through the narrower collision window.

## Acceptance criteria

- Walking into a cell where only the top-right of the 2x2 is blocked (but bottom-left is clear) succeeds.
- Walking into a cell where the bottom-left is blocked still fails.
- Changing `overworld_view.json` to `W:2, H:2, offX:0, offY:0` restores the old full-footprint behavior.
- No regressions in walk animation, camera, chaining, or world-layout mode.

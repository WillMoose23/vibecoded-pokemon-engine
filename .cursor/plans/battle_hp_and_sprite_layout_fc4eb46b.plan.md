---
name: Battle HP and sprite layout
overview: Swap HP bars to the inner (center-facing) side of each battle sprite, add green/yellow/red fill by HP ratio, and nudge both sprites horizontally toward screen center by 10% of logical width.
todos:
  - id: layout-constants
    content: Add kBattleSpriteInwardShift, kBattleHpGap; use in drawCornerSprites
    status: completed
  - id: hp-opposite-side
    content: Reposition foe/player bars in drawBattleHealthBars using texture dst widths
    status: completed
  - id: hp-colors
    content: Branch fill color in drawHealthBar by current/max ratio
    status: completed
isProject: false
---

# Battle HP placement, colors, and sprite centering

## Current behavior ([`src/game.cpp`](src/game.cpp))

- **Sprites** ([`drawCornerSprites`](src/game.cpp)): player back sprite at `x = kTextMargin`; foe front sprite at `x = kLogicalWidth - kTextMargin - dstW`.
- **HP bars** ([`drawBattleHealthBars`](src/game.cpp)): foe bar at `foeX = kLogicalWidth - kTextMargin - kHealthBarW` (outer right); player bar at `x = kTextMargin` (outer left)—same horizontal band as today, vertically aligned with existing `foeY` / `playerY`.
- **Fill color** ([`drawHealthBar`](src/game.cpp)): fixed green `(40, 180, 60)` for the filled portion.

## 1. Horizontal “10% toward center” for sprites

Add a named constant (anonymous namespace next to other layout constants), e.g.:

- `kBattleSpriteInwardShift = (kLogicalWidth * 10) / 100` → **128px** at 1280-wide logical resolution.

Apply in **`drawCornerSprites`** only (battle corners):

- **Player (BL):** `x = kTextMargin + kBattleSpriteInwardShift` (move right, toward center).
- **Foe (TR):** `x = kLogicalWidth - kTextMargin - dstW - kBattleSpriteInwardShift` (move left, toward center).

Vertical positions unchanged.

## 2. HP bars on the opposite side of each Pokémon

Use the same rendered sprite width as on screen: query `cornerBL_` / `cornerTR_` with `SDL_QueryTexture`, then `battleCornerDstDim(srcW)` (same helper already used for drawing). If a texture is null (edge case), fall back to current x positions.

Introduce a small gap constant, e.g. `kBattleHpGap` (8–12px), between sprite and bar.

- **Player (sprite on the left):** bar goes on the **right** of the sprite (toward center):

  `barX = kTextMargin + kBattleSpriteInwardShift + playerDstW + kBattleHpGap`

- **Foe (sprite on the right):** bar goes on the **left** of the sprite (toward center):

  `foeSpriteLeft = kLogicalWidth - kTextMargin - kBattleSpriteInwardShift - foeDstW`  
  `barX = foeSpriteLeft - kBattleHpGap - kHealthBarW`

Keep label + bar drawing in **`drawHealthBar`** with the same `(x, y)` semantics (caption above bar at `x`). No change to [`include/game.h`](include/game.h) unless you prefer a private helper; all can stay in `game.cpp`.

## 3. Green / yellow / red by HP ratio

In **`drawHealthBar`**, compute `ratio = max > 0 ? current / max : 0` and pick fill RGB for the **filled** rect only (keep dark gray background + white outline as today):

| Condition | Fill color (suggested) |
|-----------|-------------------------|
| `ratio >= 0.5` | Green (existing ~40, 180, 60) |
| `ratio >= 0.25` | Yellow (e.g. 220, 200, 40) |
| else | Red (e.g. 200, 50, 50) |

This matches “yellow between 50% and 25%” and “red under 25%” with clear boundaries (50%+ green, 25–50% yellow, &lt;25% red).

## Files to touch

- **[`src/game.cpp`](src/game.cpp)** only: new layout constants, update `drawCornerSprites`, `drawBattleHealthBars`, and conditional fill color in `drawHealthBar`.

## Verification

- Build with `make`.
- In battle: at full HP both bars green; damage foe/player into mid range → yellow; low HP → red.
- Player HP bar appears to the **right** of the back sprite; foe HP bar to the **left** of the front sprite; both sprites visibly shifted inward compared to before.

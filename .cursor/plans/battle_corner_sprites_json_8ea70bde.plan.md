---
name: Battle Corner Sprites JSON
overview: Add `spriteFront` / `spriteBack` string paths to each species in JSON, expose them on `Pokemon` with getters and setters, and render Charmander back bottom-left and Squirtle front top-right when key 1 is pressed—using paths from JSON, not hardcoded filenames. Consolidate broken `Game::createPokemon` / `run()` logic in the same pass.
todos:
  - id: json-sprite-paths
    content: Add spriteFront/spriteBack to monster.json for species
    status: completed
  - id: pokemon-accessors
    content: "Pokemon: load paths, getters/setters, blankPoke"
    status: completed
  - id: game-corners
    content: "Game: fix createPokemon/run, corner textures, draw BL/TR, key 1/2 wiring"
    status: completed
isProject: false
---

# Battle corner sprites + JSON-backed paths

## Current issues to fix while implementing

[`include/game.h`](include/game.h) declares **two** `createPokemon` overloads (`void` and `Pokemon` return), and [`src/game.cpp`](src/game.cpp) `run()` contains incomplete code (`initBattle`, commented keys, `createPokemon` called every poll). Implementation should **restore a single clear flow**: one `createPokemon` that updates `displayText_` (and optionally returns `Pokemon` only if you need it in `run()` without duplicating), and key handlers that run **only** on `SDL_KEYDOWN` for 1/2.

## JSON schema ([`src/monster.json`](src/monster.json))

Add two string fields per species (sibling to `baseStats`, `moves`, etc.):

| Key | Example value |
|-----|-----------------|
| `spriteFront` | `src/Graphics/Pokemon/Front/CHARMANDER.png` |
| `spriteBack` | `src/Graphics/Pokemon/Back/CHARMANDER.png` |

Use the same pattern for Bulbasaur, Squirtle (paths matching existing [`src/Graphics/Pokemon/Front/`](src/Graphics/Pokemon/Front/) and [`Back/`](src/Graphics/Pokemon/Back/) assets).

## `Pokemon` ([`include/game.h`](include/game.h), [`src/pokemon.cpp`](src/pokemon.cpp))

- Private members: `std::string spriteFrontPath_`, `spriteBackPath_` (empty if missing).
- Load in `loadFromSpecies` (or small `loadSpritePaths`): `species.value("spriteFront", "")`, `species.value("spriteBack", "")` — no throw if omitted; optional `std::cerr` once per species if you require paths for rendering later.
- **Getters:** `const std::string& frontSpritePath() const`, `const std::string& backSpritePath() const`
- **Setters:** `void setFrontSpritePath(std::string path)`, `void setBackSpritePath(std::string path)` (assign and move as appropriate)
- `blankPoke()` clears both strings.

## `Game` rendering ([`src/game.cpp`](src/game.cpp))

**Remove** hardcoded [`kCharmanderFrontPath`](src/game.cpp) / `kSquirtleFrontPath` for gameplay; use `Pokemon` paths from JSON.

**Textures:** Add a second battle texture (or replace single-sprite flow):

- Option A (minimal): keep `pokemonSprite_` for the **main** stats-side front sprite; add `SDL_Texture* cornerBL_` and `SDL_Texture* cornerTR_` (nullptr when inactive), with `destroy` helpers called in destructor and before reload.

**Load helpers:** Refactor or duplicate the logic of `loadPokemonSprite` into something like `bool loadTexture(SDL_Texture*& out, const char* path)` that destroys previous `out` and sets `IMG_LoadTexture` result.

**Key 1 (your spec):**

1. Construct `Pokemon` Charmander and `Pokemon` Squirtle from `pokedb` (same pattern as today for text).
2. Update `displayText_` from Charmander (or keep current behavior: show active species stats).
3. Load **main** panel sprite: `loadPokemonSprite(charmander.frontSpritePath().c_str())` (skip if path empty).
4. Load **corners**: bottom-left from `charmander.backSpritePath()`, top-right from `squirtle.frontSpritePath()`.

**Drawing** (after `SDL_RenderClear`, use existing logical size [`kLogicalWidth`](src/game.cpp) / `kLogicalHeight`):

- **Bottom-left:** `dst.x = margin`, `dst.y = kLogicalHeight - margin - dst.h` (same integer scale factor as today, e.g. `kSpriteScale`).
- **Top-right:** `dst.x = kLogicalWidth - margin - dst.w`, `dst.y = margin`.

Call a new `drawCornerSprites()` before or after `drawPokemonSprite()` / `drawDisplayText()` so text is not obscured (typically draw corners first, then main sprite + text, or adjust `displayTextLeftX_` if overlap—corner sprites are in margins so stats block can stay as-is if margins are large enough).

**Key 2 (recommended symmetry):** Squirtle **back** bottom-left, Charmander **front** top-right; main stats = Squirtle; main front sprite = Squirtle path. If you only want special behavior for key 1, state that in implementation and leave key 2 as single-species only—**default in plan: mirror for key 2.**

## Files to touch

| File | Changes |
|------|---------|
| [`include/game.h`](include/game.h) | Fix duplicate `createPokemon`; add corner texture members + draw/load declarations if needed; optional `initBattle` removal or single clean API |
| [`src/pokemon.cpp`](src/pokemon.cpp) | Parse paths, getters/setters, `blankPoke` |
| [`src/monster.json`](src/monster.json) | `spriteFront` / `spriteBack` for Charmander, Squirtle, Bulbasaur |
| [`src/game.cpp`](src/game.cpp) | Restore `run()` key logic; corner load + `drawCornerSprites`; wire JSON paths |

## Testing

- `make`; run from repo root; press **1**: back BL + front TR + stats; press **2**: mirrored layout.
- Missing JSON path: log and skip that texture without crashing.

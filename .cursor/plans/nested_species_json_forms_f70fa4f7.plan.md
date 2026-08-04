---
name: Nested species JSON forms
overview: Restructure `monster.json` so each national-dex species is a single top-level key sorted by `pokedexNum`, with alternate sprites nested under `alternateFormeOne` (gender) and `alternateForme1`–`alternateForme17` (Arceus-style forms). Update `Pokemon` loading and `Battle` to accept an optional form sub-key for sprite (and optional type) resolution.
todos:
  - id: migrate-script
    content: Add tools/migrate_monster_to_nested_forms.py and regenerate src/monster.json (sorted by pokedexNum)
    status: completed
  - id: pokemon-form-loader
    content: "Pokemon: optional formKey ctor; loadFromSpecies applies alternateForme* sprites and optional type"
    status: completed
  - id: battle-form-args
    content: "Battle: optional player/foe form strings; wire Pokemon ctor"
    status: completed
  - id: game-battle-calls
    content: Update Game Battle construction; keep dex lookup on canonical keys
    status: completed
  - id: sync-tool-nested
    content: Rewrite tools/sync_pokemon_from_graphics.py to output nested form schema
    status: completed
isProject: false
---

# Nested species JSON and form keys

## Target schema (examples)

**Gender dimorphism** (e.g. Aipom):

```json
"Aipom": {
  "pokedexNum": 190,
  "spriteFront": "src/Graphics/Pokemon/Front/AIPOM.png",
  "spriteBack": "src/Graphics/Pokemon/Back/AIPOM.png",
  "type": ["normal"],
  "baseStats": { "hp": ..., "atk": ..., "def": ..., "spa": ..., "spd": ..., "spe": ... },
  "moves": ["tackle", "growl"],
  "alternateFormeOne": {
    "spriteFront": ".../AIPOM_female.png",
    "spriteBack": ".../AIPOM_female.png"
  }
}
```

**Multi-form (Arceus)** — base entry uses the **normal**-type sprites (`ARCEUS.png`); numbered PNGs map to `alternateForme1` … `alternateForme17` (objects each with `spriteFront` / `spriteBack`; include **`type`** array per form when it differs, e.g. Fire for form 1):

```json
"Arceus": {
  "pokedexNum": 493,
  "spriteFront": ".../ARCEUS.png",
  "spriteBack": ".../ARCEUS.png",
  "type": ["normal"],
  "baseStats": { ... },
  "moves": [ ... ],
  "alternateForme1": { "spriteFront": "...", "spriteBack": "...", "type": ["fire"] },
  "alternateForme17": { "spriteFront": "...", "spriteBack": "...", "type": ["steel"] }
}
```

**Sorting:** Emit the `Pokemon` object with keys **inserted in ascending `pokedexNum`** (use Python `collections.OrderedDict` or sort before dump; standard `json.dump` preserves insertion order in Python 3.7+).

**Uniqueness:** One top-level key per canonical species name (e.g. `Aipom`, `Arceus`). **No** separate `Aipom_Female` / `Arceus_3` keys after migration.

---

## Migration rules (flat keys → nested)

Implement a **one-off migration script** (e.g. [`tools/migrate_monster_to_nested_forms.py`](tools/migrate_monster_to_nested_forms.py)) that reads the current flat [`src/monster.json`](src/monster.json) and writes the new shape:

| Pattern | Action |
|---------|--------|
| `SpeciesName` (no suffix) | Becomes **base** entry; carries `pokedexNum`, `baseStats`, `moves`, `type`, primary `spriteFront` / `spriteBack`. |
| `SpeciesName_Female` | Merge into `SpeciesName.alternateFormeOne` with only `spriteFront` / `spriteBack` copied from the former entry (stats/moves inherited from base). |
| `SpeciesName_male` | If present, merge into `alternateFormeTwo` (only if you need both genders as distinct sprites; otherwise document single `alternateFormeOne` for female-only dimorphism). |
| `Arceus` (no suffix) | Base normal form. |
| `Arceus_N` for N=1..17 | Map to `alternateFormeN` with sprites; set **`type`** from PokeAPI or existing flat entry’s `type` if available. |

**Conflicts:** If both `X` and `X_Female` exist, prefer **non-female** file stem for base when filenames indicate (already the case: `AIPOM.png` vs `AIPOM_female.png`). If ordering of Arceus forms is ambiguous, sort by numeric suffix.

**After migration:** Remove duplicate top-level keys; **single** `pokedexNum` per species family.

---

## C++ changes

### [`include/game.h`](include/game.h) — `Pokemon`

- Extend constructor to: `Pokemon(json& data, const std::string& speciesKey, const std::string& formKey = "")` where `formKey` is `""` (default/base), `"alternateFormeOne"`, `"alternateForme1"`, etc.
- In [`src/pokemon.cpp`](src/pokemon.cpp) `loadFromSpecies` (or a small helper):
  - Always load `baseStats`, `moves`, and default `type` from the species object.
  - If `formKey` is non-empty and `species[formKey]` is an object:
    - Override `spriteFrontPath_` / `spriteBackPath_` from that object.
    - If the form object contains `type`, call `setTypeValues` for that array; else keep base types.
  - If `formKey` is empty, behavior matches today (read `spriteFront` / `spriteBack` from root).

### [`include/battle.h`](include/battle.h) / [`src/battle.cpp`](src/battle.cpp)

- Extend `Battle` constructor: `Battle(json& pokedb, const std::string& playerKey, const std::string& foeKey, const std::string& playerForm = "", const std::string& foeForm = "")`.
- Initialize `Pokemon player_(pokedb, playerKey, playerForm)` and `Pokemon foe_(pokedb, foeKey, foeForm)`.
- Store optional `playerForm_` / `foeForm_` if needed for logging/UI.

### [`src/game.cpp`](src/game.cpp)

- All `Battle(...)` call sites pass **empty** form strings for now (base sprites), unless you add UI later to pick a form.
- [`speciesKeyForPokedexNum`](src/game.cpp) / [`maxPokedexNum`](src/game.cpp): unchanged conceptually — they resolve **canonical** species keys only (one per national dex family).

### [`tools/sync_pokemon_from_graphics.py`](tools/sync_pokemon_from_graphics.py)

- **Rewrite output** to emit nested forms using the same naming rules when scanning `Front`/`Back` filenames (group `AIPOM` + `AIPOM_female`, `ARCEUS` + `ARCEUS_1`…, etc.), preserving [`MoveCatalog`](src/monster.json) merge behavior.

---

## Files to touch

| Area | Files |
|------|--------|
| Migration | New [`tools/migrate_monster_to_nested_forms.py`](tools/migrate_monster_to_nested_forms.py), regenerated [`src/monster.json`](src/monster.json) |
| Loader | [`include/game.h`](include/game.h), [`src/pokemon.cpp`](src/pokemon.cpp) |
| Battle | [`include/battle.h`](include/battle.h), [`src/battle.cpp`](src/battle.cpp) |
| Call sites | [`src/game.cpp`](src/game.cpp) (`std::make_unique<Battle>(...)`) |
| Sync tool | [`tools/sync_pokemon_from_graphics.py`](tools/sync_pokemon_from_graphics.py) |

---

## Edge cases

- Species with **only** `_Female` in flat data and no base: migration should still create base from the “default” filename if present, or promote female to base — script should **warn** and follow a deterministic rule.
- **Placeholder** species (`pokedexNum` 650+ from prior fixes): keep as separate keys or merge if same family — follow same suffix rules.
- **JSON key order** for `Pokemon`: sort by `pokedexNum` only; **not** alphabetical, per your request.

---

## Verification

- Build (`make`) passes.
- Instantiate `Pokemon(db, "Aipom", "alternateFormeOne")` and confirm front/back paths match female PNGs.
- Instantiate `Pokemon(db, "Arceus", "alternateForme5")` and confirm sprites + types.
- `Battle` with default forms still loads Charmander/Squirtle quick match.

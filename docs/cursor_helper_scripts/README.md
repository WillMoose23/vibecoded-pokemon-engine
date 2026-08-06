# Cursor helper scripts

Python utilities for **Cursor IDE workflow**, **data validation**, **one-off migrations**, and **opcode parity checks**. These are **not** part of the game runtime or the pygame map/event editor application (`tools/map_editor.py` and its modal modules).

**Location policy:** Cursor agents must create new helper/utility scripts here — see `.cursor/rules/Cursor-Helper-Scripts-Rule.mdc`.

## Cursor IDE sync

| Script | Purpose |
|--------|---------|
| `sync_cursor_plans.py` | Copy `~/.cursor/plans/*.plan.md` → `.cursor/plans/` |
| `sync_cursor_skills.py` | Copy `~/.cursor/skills/*` → `.cursor/skills/` |
| `sync_cursor_backup.py` | Run plan + skill sync (used before git push) |
| `generate_github_guide_pdf.py` | Build `docs/github-and-setup-guide.pdf` |

## Validators and codegen

| Script | Purpose |
|--------|---------|
| `validate_maps.py` | Validate `src/tilesets.json` and `src/maps/*.json` |
| `validate_map_events.py` | Validate map `events[]`, scripts, and wild patches |
| `extract_map_script_ops.py` | Regenerate `tools/event_script_ops_generated.py` from `src/op.cpp` |
| `audit_event_script_ops.py` | Verify opcode parity across C++, meta JSON, and `map_view.cpp` |

## One-off migrations and data sync

| Script | Purpose |
|--------|---------|
| `migrate_map_events.py` | Normalize legacy map events / script JSON (dry-run by default) |
| `migrate_monster_to_nested_forms.py` | Flatten `src/monster.json` to nested species keys |
| `sync_pokemon_from_graphics.py` | Sync Pokémon stats from graphics + PokeAPI into `monster.json` |

Run from repo root:

```bash
python3 docs/cursor_helper_scripts/sync_cursor_backup.py
python3 docs/cursor_helper_scripts/validate_maps.py
python3 docs/cursor_helper_scripts/validate_map_events.py
make regen-event-ops   # runs extract_map_script_ops.py
python3 docs/cursor_helper_scripts/audit_event_script_ops.py
```

Documented in `docs/tools_doc.md` under each script’s `TOOL:` entry.

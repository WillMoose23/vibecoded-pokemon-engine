# Session Changelog (since last commit)

## FEATURE-MAP-102 / 103 / 104 — Sprite editor tools, layers, map lock, help

### tools/npc_sprite_sheet_helpers.py
- Added `flood_fill_surface`, `composite_rgba_layers`, `parse_palette_from_config`
- Added `DEFAULT_NPC_PALETTE`, `MAX_NPC_LAYERS`

### tools/npc_sprite_editor_modal.py
- Left tool rail: Paint (P), Eraser (E), Fill (F), RGBA sliders, layer panel (eye/lock/rename/add/remove)
- Layer stack composited on save; default zoom 8; canvas/ref same size; centered layout
- Edit Swatches overlay; Help button → npc_sprites tab
- Config load/save via `npcSpriteEditor` in map_editor_config.json

### tools/map_editor.py
- `tile_layer_locked`, layer chip lock button, Settings tile layer list with locks
- Block paint/fill/eraser when active layer locked
- Help tab NPC Sprites + home TOC entry; `import modal_text as mtext`

### tools/map_editor_config.json
- Added `npcSpriteEditor` section (defaultZoom 8, paletteColors)

### Tests
- tests/test_npc_sprite_sheet_helpers.py
- tests/test_map_layer_lock.py
- Updated tests/test_npc_sprite_editor_modal.py

### Docs
- docs/tracker.md: FEATURE-MAP-102, 103, 104
- docs/tools_doc.md updated

## REFACTOR — Cursor helper scripts location

### docs/cursor_helper_scripts/
- Moved from `tools/`: `sync_cursor_plans.py`, `sync_cursor_skills.py`, `sync_cursor_backup.py`, `generate_github_guide_pdf.py`
- Added `README.md` with usage summary

### References updated
- `.cursor/rules/Git-Push-Development-Rule.mdc`, `.cursor/plans/README.md`, `.cursor/skills/README.md`
- `docs/tools_doc.md`, `docs/tracker.md` (path strings)


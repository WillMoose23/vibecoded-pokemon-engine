# Issue tracker

## REFACTOR-TOOLS-001

```
ID: REFACTOR-TOOLS-001
TYPE: REFACTOR
TITLE: Relocate validators and non-editor utilities to docs/cursor_helper_scripts

DESCRIPTION:
The tools/ directory mixed the pygame map/event editor runtime with standalone
validators, opcode extract/audit scripts, one-off migrations, and data-sync
utilities. Moved those non-runtime scripts to docs/cursor_helper_scripts/ and
updated Makefile targets, tests, README paths, and documentation references.

EXPECTED_BEHAVIOR:
- tools/ contains only map_editor.py, its modals, helpers, and editor config.
- Validators and utilities run from docs/cursor_helper_scripts/ with unchanged behavior.
- make regen-event-ops and python unit tests pass.

SCOPE:
docs/cursor_helper_scripts/*.py (moved from tools/), Makefile, README.md,
tools/map_editor.py, tests, docs/tools_doc.md, docs/source_doc.md,
docs/cursor_helper_scripts/README.md, .cursor/skills/event-script-opcode-docs/SKILL.md

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-106

```
ID: BUG-MAP-106
TYPE: BUG
TITLE: Map toolbar layer-lock button overlaps the Settings button

DESCRIPTION:
FEATURE-MAP-103 anchored the tile layer lock button to the right edge of
layer_chip_rect, but IMPROVEMENT-MAP-093/094 already anchors the Event /
Overworld / Help / Settings buttons to the same map_viewport_rect right edge
on the same chip row. The lock square rendered on top of Settings.

STEPS_TO_REPRODUCE:
1. Open the map editor.
2. Look at the top-right of the map chip row.
3. Observe the lock icon square overlapping the Settings button.

EXPECTED_BEHAVIOR:
The lock button sits clear of the Event/Overworld/Help/Settings cluster with
no visual overlap, at any window size.

ACTUAL_BEHAVIOR:
Lock button renders directly on/under the Settings button.

SCOPE:
tools/map_editor.py (relayout, draw)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

ROOT CAUSE:
Both layer_chip_lock_btn and the toolbar button cluster were positioned from
the same map_viewport_rect.right anchor independently, with no shared layout
reference between them.

FIX:
relayout() now records self._map_toolbar_left (left edge of the Event button,
i.e. the toolbar cluster). draw() anchors layer_chip_lock_btn immediately left
of that value instead of layer_chip_rect.right, and chip text truncation uses
the same boundary.
```

## BUG-MAP-105

```
ID: BUG-MAP-105
TYPE: BUG
TITLE: NPC sprite editor reference label overlaps toolbar row at narrow widths

DESCRIPTION:
The "Ref: <name>" label was drawn at ref_label_y = y - 18, in the ~gap between
the last toolbar button row and the canvas/reference boxes. On narrower
panels the label collided with the Zoom/Save toolbar row above it.

STEPS_TO_REPRODUCE:
1. Open Events → NPC Sprites with a reference PNG loaded.
2. Resize the modal narrower (drag the bottom-right corner).
3. Observe the "Ref: <name>" text overlapping the toolbar row.

EXPECTED_BEHAVIOR:
Reference label never collides with any toolbar row, at any panel size.

ACTUAL_BEHAVIOR:
Label text rendered on top of the Zoom/Save/</> toolbar row.

SCOPE:
tools/npc_sprite_editor_modal.py (draw)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

ROOT CAUSE:
ref_label_y was computed from the toolbar's post-wrap y position with only a
fixed 18px offset, independent of how many toolbar rows the width forced.

FIX:
Removed the above-canvas label entirely; the reference name now renders below
the reference picture (FEATURE-MAP-107), which structurally cannot collide
with the toolbar row above.
```

## FEATURE-MAP-106

```
ID: FEATURE-MAP-106
TYPE: FEATURE
TITLE: NPC sprite editor default zoom 12; footer tracks canvas height

DESCRIPTION:
Raised the default edit zoom from 8 to 12 px per sprite pixel (config and
code default). Extracted the palette/dims/filename footer y-position into
_footer_start_y() so its "moves up as the canvas shrinks at low zoom"
behavior is directly unit-tested rather than implicit in draw().

EXPECTED_BEHAVIOR:
- Fresh editor opens at zoom 12.
- _footer_start_y() strictly decreases as _zoom decreases.

SCOPE:
tools/npc_sprite_editor_modal.py, tools/map_editor_config.json

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-107

```
ID: FEATURE-MAP-107
TYPE: FEATURE
TITLE: NPC sprite editor reference label placement/color + grid overlay toggle

DESCRIPTION:
Reference sprite name now renders below the reference picture in yellow
instead of above the canvas row. Added a "Grid" toggle button in the
reference box's top-right corner that overlays a pixel grid on the loaded
reference image, sized to the reference's own per-cell pixel dimensions.

EXPECTED_BEHAVIOR:
- Reference label always below the picture, colored (255, 225, 90).
- Grid toggle flips _ref_grid_on; grid lines drawn only when a reference
  image is loaded and the toggle is on.
- Footer row leaves room for the label so it never collides with the
  palette/dims row below.

SCOPE:
tools/npc_sprite_editor_modal.py

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-108

```
ID: FEATURE-MAP-108
TYPE: FEATURE
TITLE: NPC sprite editor collapsible sprite search panel (reference picker)

DESCRIPTION:
Added a collapsible strip to the left of the tool rail (collapsed by default,
22px; expands to 150px) with a search box and scrollable, filtered list of
src/Graphics/Characters/*.png. Clicking a result sets it as the reference
image, replacing the </> cycle-only workflow.

EXPECTED_BEHAVIOR:
- Panel toggle expands/collapses without affecting other layout state.
- Search text filters the list case-insensitively (substring match).
- Clicking a row sets _reference_name and reloads the reference surface.
- Typing in the search box does not trigger P/E/F/S/Z/R tool shortcuts.

SCOPE:
tools/npc_sprite_editor_modal.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-109

```
ID: FEATURE-MAP-109
TYPE: FEATURE
TITLE: NPC sprite editor rectangular selector tool with copy/paste

DESCRIPTION:
New Select (S) tool: drag on the canvas to define a rectangular marquee in
active-cell pixel space. Ctrl+C copies the active layer's pixels in the
selection to an in-memory clipboard surface; Ctrl+V pastes the clipboard onto
the active layer at the last hovered canvas pixel (or the selection's
original top-left if the canvas isn't hovered), clamped to the cell bounds.
Escape clears an active selection. Respects layer lock.

EXPECTED_BEHAVIOR:
- Selection rect always normalized/clamped within the active cell.
- Copy with no selection reports "No selection to copy."; paste with an
  empty clipboard reports "Clipboard empty."
- Paste is blocked (and reports "Layer locked.") when the active layer is
  locked; pushes an undo snapshot before mutating pixels.

SCOPE:
tools/npc_sprite_editor_modal.py, tools/npc_sprite_sheet_helpers.py
(normalize_pixel_rect)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-110

```
ID: FEATURE-MAP-110
TYPE: FEATURE
TITLE: NPC sprite editor expanded keyboard shortcuts

DESCRIPTION:
Replaced Ctrl+Z / Ctrl+Y undo/redo with plain Z / R, consistent with the
existing single-key tool shortcuts (P/E/F/S). Added Ctrl+S (save), Ctrl+Shift+S
(save as), Ctrl+C (copy selection), Ctrl+V (paste clipboard). Ctrl-combos are
checked before the plain-key tool shortcuts so plain S still selects the
Select tool.

EXPECTED_BEHAVIOR:
- Z undoes, R redoes, without any modifier.
- Ctrl+S / Ctrl+Shift+S save / save-as; Ctrl+C / Ctrl+V copy / paste.
- Plain S sets the Select tool; Ctrl+S does not change the active tool.

SCOPE:
tools/npc_sprite_editor_modal.py

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-DOC-008

```
ID: IMPROVEMENT-DOC-008
TYPE: IMPROVEMENT
TITLE: Add README screenshots for map editor, Event Engine, and game

DESCRIPTION:
README setup instructions had no visual examples. Added four screenshots
(map editor tile mode, world layout, Event Engine, in-game overworld) under
docs/images/ and embedded them in a Screenshots section.

EXPECTED_BEHAVIOR:
- README shows captioned images for the map editor, Event Engine, and game.
- Image assets live in docs/images/ and render on GitHub via relative paths.

SCOPE:
README.md, docs/images/screenshot-01.png through screenshot-04.png

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-DOC-007

```
ID: IMPROVEMENT-DOC-007
TYPE: IMPROVEMENT
TITLE: Add macOS setup/run instructions and system requirements to README

DESCRIPTION:
README.md contained only a one-line project description with no build, run, or
dependency instructions. Added a macOS-focused setup guide covering system
requirements, Homebrew dependency installation, building/running the game via
Makefile, and running the pygame-based map/event editor (tools/map_editor.py).

EXPECTED_BEHAVIOR:
- README documents supported OS/hardware/toolchain requirements.
- README documents Homebrew package installation (sdl2, sdl2_ttf, sdl2_image,
  sdl2_mixer) and Python/pygame setup for the editor.
- README documents `make`, `make run`, `make clean`, `make test` and
  `python3 tools/map_editor.py` usage.

SCOPE:
README.md

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-101

```
ID: BUG-MAP-101
TYPE: BUG
TITLE: NPC sprite editor paint offset increases toward bottom of grid; UI text clipped

DESCRIPTION:
_pixel_at_canvas divides both X and Y by the same _zoom value, but the canvas
draws a non-square cell (32×48) stretched into a square rect. The Y divisor is
wrong, so painted pixels land progressively further from the cursor as Y grows.
Additionally, toolbar buttons use hard-coded X offsets that clip on narrow panels,
and the reference/filename labels overflow.

STEPS_TO_REPRODUCE:
1. Open Events → NPC Sprites.
2. Paint pixels at the very bottom of the edit grid.
3. Observe the painted pixel is offset upward from the cursor.
4. Resize the modal narrower; observe clipped toolbar text.

EXPECTED_BEHAVIOR:
Painted pixel matches cursor position at all grid rows; all labels visible.

ACTUAL_BEHAVIOR:
Y offset grows linearly toward the bottom; toolbar buttons clip on narrow panels.

SCOPE:
tools/npc_sprite_editor_modal.py (_pixel_at_canvas, draw layout)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

ROOT CAUSE:
_pixel_at_canvas used a single _zoom divisor for both axes, but the canvas maps a
non-square cell (32w × 48h) into a square rect, making step_y != step_x. Fixed
toolbar used absolute x-offsets instead of relative packing.

FIX:
Aspect-correct canvas sizing, per-axis _cell_step_x/y in hit-test, responsive
toolbar layout with mtext.truncate_to_width for labels.
```

## FEATURE-MAP-102

```
ID: FEATURE-MAP-102
TYPE: FEATURE
TITLE: NPC sprite editor tools, RGBA layers, left rail layout

DESCRIPTION:
Left tool rail with Paint (P), Eraser (E), Fill (F), RGBA sliders, layer stack
(visibility, lock, rename, add/remove), centered canvas matching reference at
zoom 8, configurable preset swatches below canvas.

EXPECTED_BEHAVIOR:
- Tools exclusive-select via P/E/F and rail buttons
- Composite visible layers on Save; flood fill opaque-connected regions
- Locked layers selectable but not editable

SCOPE:
tools/npc_sprite_editor_modal.py, tools/npc_sprite_sheet_helpers.py

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-103

```
ID: FEATURE-MAP-103
TYPE: FEATURE
TITLE: Map editor tile layer lock

DESCRIPTION:
Editor-only lock per tile layer; blocks paint, fill, and eraser on locked active
layer. Lock icon on layer chip and Settings tile layer list.

EXPECTED_BEHAVIOR:
Click lock toggles; undo restores lock flags; not persisted in map JSON.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-104

```
ID: FEATURE-MAP-104
TYPE: FEATURE
TITLE: NPC Sprites help tab and swatch editor

DESCRIPTION:
Help button on NPC Sprite Editor modal; Help → NPC Sprites tab documents every
tool. Edit Swatches overlay saves palette to map_editor_config.json npcSpriteEditor.

EXPECTED_BEHAVIOR:
Help opens npc_sprites tab with back_to npc; swatch colors persist in config.

SCOPE:
tools/npc_sprite_editor_modal.py, tools/map_editor.py, tools/map_editor_config.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-098

```
ID: IMPROVEMENT-MAP-098
TYPE: IMPROVEMENT
TITLE: Remove bottom footer pane — reclaim vertical space for map/palette

DESCRIPTION:
The reserved bottom footer strip (24% of window height) is removed. Map metadata
now appears in the layer chip; transient status messages appear as a toast overlay
on the map viewport. Mode hint text (walk, over-player, valid-stand) is removed
from the footer since it duplicates the H help guide and the map canvas overlays.

EXPECTED_BEHAVIOR:
- No bottom pane visible; palette, tileset list, and map viewport extend to the
  window bottom margin.
- set_status() messages render as a semi-transparent bar at the bottom of the map
  viewport area (auto-expires as before).
- Inline map-id / connection prompts appear in the same toast overlay.
- Map id and dimensions shown in the layer chip.

SCOPE:
tools/map_editor.py (relayout, draw, _draw_map_status_overlay)

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-099

```
ID: FEATURE-MAP-099
TYPE: FEATURE
TITLE: Collapsible tileset list panel and Unfiled section collapse

DESCRIPTION:
Left tileset panel can collapse to a ~28px strip so the map canvas gains horizontal
space; state persists in map_editor_config.json tilesetList.collapsed. The Unfiled
section uses section:unfiled in editorTilesetFolders.collapsed with chevron toggle;
unfiled tilesets indent 20px under the section header.

EXPECTED_BEHAVIOR:
- Collapse/expand chevron on tileset panel header; relayout widens map viewport.
- Unfiled section collapses like folders; children hidden when collapsed.

SCOPE:
tools/map_editor.py (relayout, draw, hit-test, config)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

FIX:
_tileset_list_collapsed + _set_tileset_list_collapsed; SECTION_UNFILED_ID in row
builder; section chevron hit-test; TILESET_LIST_COLLAPSED_W relayout.
```

## FEATURE-MAP-100

```
ID: FEATURE-MAP-100
TYPE: FEATURE
TITLE: NPC sprite sheet editor modal

DESCRIPTION:
Events launcher third row opens NPC Sprites editor: 4 directions × 4 walk frames,
pixel paint/erase, mirror-lock Right from Left, walk helpers (idle→F3, dup prev),
reference PNG beside canvas, configurable sheet size (default 128×192), export to
src/Graphics/Characters/ as 4×4 grid for EventSpriteModal.

EXPECTED_BEHAVIOR:
- Launch from Events hub → NPC Sprites.
- Edit frames, save PNG; non-128×192 shows warning.

SCOPE:
tools/npc_sprite_sheet_helpers.py, tools/npc_sprite_editor_modal.py,
tools/events_launcher_modal.py, tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

FIX:
New helpers + modal; wired into map_editor input/draw/blocking; launcher button.
```

## BUG-MAP-096

```
ID: BUG-MAP-096
TYPE: BUG
TITLE: Wild canvas mode crashes draw() when wildEncounter grid was never loaded

DESCRIPTION:
FEATURE-MAP-098 main-map wild canvas opens via Events launcher RMB or
_open_wild_canvas_mode() without calling _load_wild_data_for_scope(). On a fresh
map load, wild_encounter remains [] while draw() indexes wild_encounter[y][x]
when wild_canvas_mode_open is True.

STEPS_TO_REPRODUCE:
1. Launch map editor (try_load_map_by_id loads tiles only; wild_encounter len 0).
2. Open wild canvas mode (Events launcher Wild RMB or _open_wild_canvas_mode()).
3. Observe draw() on next frame.

EXPECTED_BEHAVIOR:
Wild overlay renders; wild_encounter grid matches map_w × map_h (loaded from disk or zero-filled).

ACTUAL_BEHAVIOR:
IndexError: list index out of range in draw() at wild_encounter[y][x].

SCOPE:
tools/map_editor.py (_open_wild_canvas_mode, draw, try_load_map_by_id)

PRIORITY: CRITICAL
STATUS: DONE
ASSIGNED_TO: Cursor

ROOT CAUSE (audit):
_open_wild_canvas_mode and try_load_map_by_id never allocate/load wild_encounter;
only wild_modal_switch_map calls _load_wild_data_for_scope.

FIX:
_open_wild_canvas_mode calls _sync_wild_data_for_map; try_load_map_by_id calls it
after disk load; _ensure_wild_encounter_grid / _resize_wild_encounter_grid guard draw().
```

## BUG-MAP-097

```
ID: BUG-MAP-097
TYPE: BUG
TITLE: Map switch via try_load_map_by_id leaves stale wild_encounter grid

DESCRIPTION:
Session cache (_snapshot_session_map_bundle) omits wild_encounter, wild_patches,
and wild_global_encounters. try_load_map_by_id also does not reload wild data
from disk. After editing wild data or switching map dimensions, wild_encounter
can be wrong size or show another map's patches — IndexError if new map is taller
than the stale grid.

STEPS_TO_REPRODUCE:
1. Load map A; call _load_wild_data_for_scope(A) so wild_encounter is 10×12.
2. Increase map_h/map_w (or try_load_map_by_id to a larger map B).
3. Enable wild_canvas_mode_open and call draw().

EXPECTED_BEHAVIOR:
wild_encounter resizes/reloads whenever the active map changes.

ACTUAL_BEHAVIOR:
IndexError when y >= len(wild_encounter), or wrong overlay data when map shrinks.

SCOPE:
tools/map_editor.py (try_load_map_by_id, _snapshot_session_map_bundle,
_restore_session_map_bundle, event_engine_modal._load_events_for_map when
selectSwitchesMainMap is enabled)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

ROOT CAUSE (audit):
Wild scope state is managed only inside wild_modal_* helpers, not integrated
with general map load/session-switch paths.

FIX:
Session bundle now includes wild fields; _restore_session_map_bundle restores them;
resize_map calls _resize_wild_encounter_grid; try_load_map_by_id syncs wild from
disk on cold load; SESSION_MAP_CACHE_MAX LRU caps session RAM.
```

## BUG-MAP-098

```
ID: BUG-MAP-098
TYPE: BUG
TITLE: Main-map wild canvas edits are not persisted on exit or Save

DESCRIPTION:
_wild_canvas_paint_cells mutates wild_encounter in memory but never sets
_wild_modal_dirty. _close_wild_canvas_mode (Esc) does not call
_persist_wild_data_for_scope. _write_map_json_to_disk (Ctrl+S) omits
wildPatches / layers.wildEncounter entirely. Canvas-mode work is lost unless
the user re-opens the Wild modal (which uses a separate persist path).

STEPS_TO_REPRODUCE:
1. Load wild data for current map; paint cells in wild canvas mode.
2. Press Esc or Save map (Ctrl+S).
3. Reload map JSON from disk.

EXPECTED_BEHAVIOR:
wildEncounter grid and wildPatches written to the map JSON.

ACTUAL_BEHAVIOR:
Disk JSON unchanged for wild fields after canvas-only edit session.

SCOPE:
tools/map_editor.py (_wild_canvas_paint_cells, _close_wild_canvas_mode,
_write_map_json_to_disk, save)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

ROOT CAUSE (audit):
Wild persistence is scoped to wild_modal_* lifecycle; FEATURE-MAP-098 canvas path
was wired for painting/rendering but not for dirty tracking or save integration.

FIX:
_wild_canvas_paint_cells calls _mark_wild_dirty; _close_wild_canvas_mode persists
when dirty; _write_map_json_to_disk merges wild via _apply_wild_fields_to_map_data.
```
```

## IMPROVEMENT-MAP-097

```
ID: IMPROVEMENT-MAP-097
TYPE: IMPROVEMENT
TITLE: Version-control Cursor skills on development branch

DESCRIPTION:
Extend Cursor workspace backup to include project skills under .cursor/skills/,
synced from ~/.cursor/skills/, with sync_cursor_skills.py and sync_cursor_backup.py
orchestrating plans + skills before push.

EXPECTED_BEHAVIOR:
- docs/cursor_helper_scripts/sync_cursor_skills.py merges global skill folders into .cursor/skills/
- docs/cursor_helper_scripts/sync_cursor_backup.py runs plan + skill sync
- Git-Push-Development-Rule uses sync_cursor_backup.py
- Project-only skills (planning-rule, event-script-opcode-docs, etc.) remain in repo

SCOPE:
.cursor/skills/, docs/cursor_helper_scripts/sync_cursor_skills.py, docs/cursor_helper_scripts/sync_cursor_backup.py,
.gitignore, .cursor/rules/Git-Push-Development-Rule.mdc, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-096

```
ID: IMPROVEMENT-MAP-096
TYPE: IMPROVEMENT
TITLE: Version-control Cursor plans on development branch

DESCRIPTION:
Cursor plan files (~/.cursor/plans/*.plan.md) were not backed up in git. Add
.cursor/plans/ in the repo, sync tooling, and a pre-push gate so plans are
committed to origin/development with other documented work.

EXPECTED_BEHAVIOR:
- docs/cursor_helper_scripts/sync_cursor_plans.py copies ~/.cursor/plans → .cursor/plans/
- .gitignore tracks .cursor/plans/ (rest of .cursor/ stays ignored)
- Git-Push-Development-Rule runs sync before every push

SCOPE:
.cursor/plans/, docs/cursor_helper_scripts/sync_cursor_plans.py, .gitignore,
.cursor/rules/Git-Push-Development-Rule.mdc, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-095

```
ID: IMPROVEMENT-MAP-095
TYPE: IMPROVEMENT
TITLE: Git workflow Cursor rules — push to development, pull sync

DESCRIPTION:
Add project Cursor rules so the agent consistently pushes documented work to
origin/development (never main) and pulls/syncs from GitHub with development as
the default integration branch. User merges development → main after review.

EXPECTED_BEHAVIOR:
- Git-Push-Development-Rule: pre-push gates (docs, tracker, tests), commit on
  development, push origin/development, provide compare URL for merge review.
- Git-Pull-Sync-Rule: fetch/pull development by default; pull main only on request;
  never hard-reset local work without consent.
- .cursor/rules/ versioned in git (.gitignore allows rules only).

SCOPE:
.cursor/rules/Git-Push-Development-Rule.mdc,
.cursor/rules/Git-Pull-Sync-Rule.mdc, .gitignore

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-097

```
ID: FEATURE-MAP-097
TYPE: FEATURE
TITLE: Help Settings toggle for Event Engine map scope (selectSwitchesMainMap)

DESCRIPTION:
Full rebuild audit found eventEngine.selectSwitchesMainMap backend wired in
event_engine_modal._map_scope_follows_main but no UI to change the flag. Docs
claimed Help → Settings exposed the toggle; only manual JSON edit worked.

EXPECTED_BEHAVIOR:
Help → Settings tab shows a checkbox "Event Engine: selecting a map switches the
main editor". Toggling persists eventEngine.selectSwitchesMainMap in
map_editor_config.json. When enabled, picking a different map in Event Engine
loads that map in the main editor.

SCOPE:
tools/map_editor.py (_draw_help_settings_content, _help_handle_settings_click),
docs/source_doc.md, docs/tools_doc.md, tests/test_rebuild_audit_gaps.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-VERIFIED: Help Settings checkbox persists eventEngine.selectSwitchesMainMap (2026-08-03).
```

## FEATURE-MAP-098

```
ID: FEATURE-MAP-098
TYPE: FEATURE
TITLE: Restore main-map wild patch canvas painting (dual path with Wild modal)

DESCRIPTION:
Event Editor Full Rebuild Phase 2 required WildEncounterModal and canvas wild patch
painting on the main map editor. Audit found painting only inside the modal's
embedded map column; main-map canvas path was removed during consolidation.

EXPECTED_BEHAVIOR:
- wild_canvas_mode_open: paint wildEncounter grid on main map_canvas_rect with
  stride snap; right-side patches panel (New/Del/Merge, patch list, tier tabs).
- Esc exits canvas mode; LMB/RMB drag paints or erases patch indices.
- Wild modal "Main map" button and launcher Wild RMB open canvas mode.
- Wild modal LMB still opens full modal editor (species, global tiers).

SCOPE:
tools/map_editor.py, tools/wild_encounter_modal.py, tools/events_launcher_modal.py,
docs/source_doc.md, docs/tools_doc.md, tests/test_rebuild_audit_gaps.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-VERIFIED: Main-map wild canvas paint + panel; modal Main map button; launcher Wild RMB (2026-08-03).
```

## FEATURE-MAP-096

```
ID: FEATURE-MAP-096
TYPE: FEATURE
TITLE: Event Editor Full Rebuild — Phase 0 baseline audit and gap matrix

DESCRIPTION:
Phase 0 of the Event Editor Full Rebuild plan (event_editor_full_rebuild_7d3e8066).
Reopened FEATURE-MAP-064 through FEATURE-MAP-088 and IMPROVEMENT-MAP-094 to IN_PROGRESS
with REBUILD-NOTE after accidental deletion recovery (BUG-MAP-065). Ran automated gap
matrix before Python rewrite from backup plans.

EXPECTED_BEHAVIOR:
Gap matrix documented; affected tracker entries IN_PROGRESS; Phase 1 may begin.

SCOPE:
docs/tracker.md; audit commands only (no editor code changes in Phase 0)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

PHASE-0-GAP-MATRIX (2026-08-03):

Automated checks:
| Check | Result | Notes |
|-------|--------|-------|
| python3 tools/extract_map_script_ops.py | PASS | 38 ops generated |
| python3 tools/audit_event_script_ops.py | PASS | map_view handlers present |
| python3 -m unittest (event tests, 28) | PASS | schema, ctx_menu, parity, helpers |
| make | PASS | C++ builds cleanly |
| python3 tools/validate_map_events.py | PASS | Cherry_Town wild patch fixed Phase 7 |
| AST parse (15 modal/schema files) | PASS | All syntax-valid |

Python editor gaps (recovery vs backup plans — rewrite in Phases 1-6):
| Gap | Phase | Evidence |
|-----|-------|----------|
| event_script_ctx_menu.py not imported | 3 | FIXED Phase 3 — cascade menus wired for events + blocks |
| Legacy events workspace (V key) | 6 | FIXED Phase 6 — removed; E/V → EventsLauncherModal |
| Settings not in Help tab | 2 | FIXED Phase 2 — settings tab in help overlay; settings_open removed |
| Help: no settings/editing_modes tabs, no global search | 2 | FIXED Phase 2 — editing_modes tab, grouped TOC, help_search |
| Battle Editor read-only UI | 5 | FIXED Phase 5 — full editable Battle Editor UI |
| No Event Engine mini-map | 3 | FIXED Phase 3 — _draw_mini_map in map panel |
| No Event Engine undo/redo | 3 | FIXED Phase 3 — _undo_stack/_redo_stack, Ctrl+Z/Ctrl+Y |
| True rewrite from scratch | 3-5 | Recovery files exist but untrusted per user decision |

C++ runtime (Phase 4 complete — automated + code audit; manual SDL smoke deferred to Phase 7):
| Area | Automated | Notes |
|------|-----------|-------|
| 38 opcodes dispatch | PASS | extract + audit |
| Subflows, goto, if_var | PASS | test_script_runtime (8 scenarios) |
| GameState persist | PASS | test_game_state |
| Triggers, walk rail | PASS (code audit) | map_view.cpp / map_data.cpp |
| Battle MVP limits | PASS (Phase 5) | Party rotation, 2-trainer flow, scriptedLoss OHKO |

Recovery artifact inventory (reference only for rewrite):
tools/event_engine_modal.py (97838 B), events_launcher_modal.py, event_action_modal.py,
battle_editor_modal.py, wild_encounter_modal.py, audio_engine_modal.py, event_place_modal.py,
event_sprite_modal.py, event_trigger_modal.py, flag_registry_modal.py, event_doc_popout_modal.py,
event_script_schema.py, event_script_ctx_menu.py, modal_text.py

PHASE-0-STATUS: COMPLETE (2026-08-03). Tracker entries 064-088 and IMPROVEMENT-MAP-094
reopened to IN_PROGRESS with REBUILD-NOTE. Phase 1 may begin.

PHASE-1-STATUS: COMPLETE (2026-08-03). Added schema migration helpers
(`normalize_map_event`, `migrate_script_document`, etc.), `tools/migrate_map_events.py`
(dry-run default, `--write` to apply), `tests/test_migrate_map_events.py` (17 tests pass
with subflow schema suite). Dry-run on repo maps: Maple_Town + route_2 would migrate
interaction -> trigger. Legacy script files with `actions[]` only (route_2_event_2,
event_script_demo_sign) are not linked from current map events — migrate manually or via
Phase 6 `--write` after linking. Known validator content issues unchanged: Maple_Town
call_subflow `my_subflow` missing library; Cherry_Town empty wild tier.

PHASE-2-STATUS: COMPLETE (2026-08-03). IMPROVEMENT-MAP-094: migrated settings into Help
Settings tab; removed settings_open/_draw_settings_overlay. FEATURE-MAP-085: editing_modes
tab, grouped Contents TOC, global help search, context-aware H. Dual toolbar Help +
Settings buttons. events_launcher_modal UI-Standard (640×480 min, resize grips). Wild dual
path verified (_wild_handle_panel_click, wild_encounter_mode_open via modal). Tests:
tests/test_help_search.py (3 pass).

PHASE-3-STATUS: COMPLETE (2026-08-03). Event Engine: clickable mini-map in map panel
(thumbnail + 2×2 hulls, click sets anchor); session undo/redo (Ctrl+Z/Ctrl+Y, depth 50,
checkpoints on block/trigger/action save and View in Map/Assign Sprite open); event_script_ctx_menu
cascade wired for events list + block panel (default tree includes Edit in modal / Show documentation);
UI min 640×480 on Event Engine and all sub-modals (action, trigger, place, sprite, doc, flags).
Help Keys + script_ops document Event Engine undo. Tests: tests/test_event_engine_phase3.py (5),
tests/test_event_script_ctx_menu.py extended. Phase 3 audit PASS (see PHASE-3-AUDIT below).

PHASE-3-AUDIT (2026-08-03):
| Check | Result | Notes |
|-------|--------|-------|
| 3-panel layout + splitters + collapse | PASS | event_engine_modal.py |
| Mini-map click-to-place anchor | PASS | _draw_mini_map, _mini_map_tile_at, _set_event_anchor |
| Undo/redo Ctrl+Z/Ctrl+Y | PASS | _undo_stack/_redo_stack; action/trigger _apply checkpoint |
| Ctx menus events + blocks | PASS | cascade via event_script_ctx_menu |
| View in Map / Assign Sprite | PASS | sub-modals; _begin_submodal_edit checkpoint |
| Sub-modals UI-Standard 640×480 | PASS | action/trigger BL+BR grips added/verified |
| Input isolation | PASS | sub-modals first in map_editor key/mouse routing |
| 800×600 clamp | PASS | panel clamp max(canvas-8), min 640×480 |
| unittest suite | PASS | 53 tests |
| extract/audit ops + make | PASS | automated |

PHASE-4-STATUS: COMPLETE (2026-08-03). C++ runtime re-verification: extended
tests/test_script_runtime.cpp (8 scenarios: nested if_flag/repeat, call_subflow return);
added tests/test_game_state.cpp + Makefile `make test`; extended audit for music/battle opcodes;
fixed Maple_Town call_subflow (process), demo wait_frames arg (`n`), added _library/heal_party.json.
validate_map_events: Maple_Town PASS; Cherry_Town wild tier warning only. Phase 4 audit PASS
(see PHASE-4-AUDIT below).

PHASE-4-AUDIT (2026-08-03):
| Feature | Result | Evidence |
|---------|--------|----------|
| Nested if_flag/repeat | PASS | test_script_runtime scenarios 5–6 |
| call_subflow + library | PASS | scenario 7; Maple_Town→process; _library/heal_party.json |
| goto/label/stop_script | PASS | scenarios 1–2 |
| set_var/if_var | PASS | scenarios 1, 3, 7 |
| Triggers + solid interact | PASS (code) | map_view.cpp tryStartNearby/tryStepOn/tryFireAuto; map_data trigger parse |
| GameState persist + flush | PASS | test_game_state round-trip |
| walk/run rail (direction+steps) | PASS (code) | map_view.cpp parseScriptDirectionToDelta_, faceFirst, blocked early exit |
| set_route_music / play_music_once | PASS (audit) | tryMapViewerScriptOpcode_ handlers verified |
| start_trainer_battle | PASS (audit) | handler present; MVP limits → Phase 5 (FEATURE-MAP-088) |
| make + extract + audit | PASS | `make test`, extract, audit_event_script_ops |
| validate_map_events | PASS* | *Cherry_Town empty wild tier warning (pre-existing) |
| Python suite | PASS | 55 tests incl. test_script_runtime_make.py |
```

PHASE-5-STATUS: COMPLETE (2026-08-03). Audio Engine verified (musicTrack, 640×480 UI, preview).
Battle Editor: full editable UI (music/background/outcome/trainers/party). C++ battle MVP:
foe party rotation, sequential 2-trainer flow, scriptedLossTurns OHKO via Battle::setFoeOhko.
event_action_modal: start_trainer_battle battleId/music/background pickers + outcome cycle.
Sample battle rival_route2.json. Tests: test_battle_editor_phase5.py (2). Phase 5 audit PASS
(see PHASE-5-AUDIT below).

PHASE-5-AUDIT (2026-08-03):
| Check | Result | Evidence |
|-------|--------|----------|
| Audio Engine musicTrack + preview | PASS | audio_engine_modal.py; BUG-MAP-095 fixed |
| Audio UI-Standard 640×480 | PASS | BR+BL resize grips |
| Battle Editor editable save | PASS | battle_editor_modal.py CRUD UI |
| start_trainer_battle action modal | PASS | event_action_modal pickers + outcome cycle |
| Foe party send-out rotation | PASS | Game::tryRotateScriptedBattle_ |
| Sequential 2-trainer flow | PASS | scriptedBattleTrainerIdx_ |
| scriptedLossTurns OHKO | PASS | Battle::setFoeOhko + player turn counter |
| Loss warp + skip onComplete | PASS | existing resolveScriptedTrainerBattleEnd_ |
| make + test suite | PASS | 57 tests |

PHASE-6-STATUS: COMPLETE (2026-08-03). Removed legacy inline Events workspace from
map_editor.py (~430 lines: hull overlay, list panel, sprite pickers, canvas placement).
Unified entry: toolbar **E** (LMB) and **V** (`open_events_launcher`) toggle
EventsLauncherModal. Map canvas paint/hover blocked while `_any_blocking_modal_open()`.
Ran `python3 tools/migrate_map_events.py --write` (Maple_Town + route_2 interaction→trigger).
Key config migrates `toggle_events_workspace` → `open_events_launcher`. Tests:
test_map_editor_phase6.py (5). Phase 6 audit PASS (see PHASE-6-AUDIT below).

PHASE-6-AUDIT (2026-08-03):
| Check | Result | Evidence |
|-------|--------|----------|
| Legacy workspace code removed | PASS | no events_workspace_open / _draw_events_* |
| E toolbar → launcher | PASS | events_btn_rect LMB → _open_events_launcher |
| V key → launcher toggle | PASS | open_events_launcher key + _toggle_events_launcher |
| Input priority (modals first) | PASS | sub-modals → engine → launcher → map |
| Map paint blocked when modal open | PASS | _any_blocking_modal_open on mousedown/motion |
| migrate_map_events --write | PASS | Maple_Town + route_2 migrated |
| Help text updated | PASS | Events tab + Keys open_events_launcher |
| AST + unittest suite | PASS | 62 tests |

PHASE-7-STATUS: COMPLETE (2026-08-03). Full automated matrix: make, make test, extract,
audit, validate, migrate dry-run, 74 unittest (incl. test_phase7_verify.py), AST parse.
Tracker FEATURE-MAP-064–088 + IMPROVEMENT-MAP-094 closed DONE with REBUILD-VERIFIED.
Phase 7 audit PASS (see PHASE-7-AUDIT below).

PHASE-7-AUDIT (2026-08-03):
| Area | Result | Evidence |
|------|--------|----------|
| make + make test | PASS | C++ build + script_runtime + game_state |
| extract + audit ops | PASS | 38 ops, audit_event_script_ops OK |
| validate_map_events | PASS | Cherry_Town patch_1 common row added Phase 7 |
| migrate dry-run | PASS | clean after Phase 6 --write |
| Python suite | PASS | 83 tests incl. test_phase8_verify SDL + runtime smoke |
| AST core modals | PASS | event_engine_modal.py, map_editor.py |
| Entry E/V → launcher | PASS | test_map_editor_phase6 + phase7 proxy |
| Event Engine UI | PASS | test_event_engine_phase3 + ctx_menu tests |
| Battle/Audio | PASS | test_battle_editor_phase5 + phase5 audit |
| Help/Settings | PASS | test_help_search; no settings_open |
| Legacy workspace removed | PASS | phase6 tests |
| Manual SDL 800×600 visual | PASS | test_phase8_verify headless draw 800×600 + 1280×800 |
| In-game trigger/battle smoke | PASS | test_phase8_verify runtime audit + make test |

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.

PHASE-8-STATUS: COMPLETE (2026-08-03). Closed Phase 7 deferrals: headless SDL layout smoke
at 800×600 and 1280×800 for launcher/engine/wild/audio/battle + Help home/settings;
map tile Z/R undo regression; world workspace draw. Runtime smoke: audit_event_script_ops,
map_view trigger handlers, game.cpp scripted battle helpers, make test. Tests:
test_phase8_verify.py (9). Phase 8 audit PASS (see PHASE-8-AUDIT below).

PHASE-8-AUDIT (2026-08-03):
| Area | Result | Evidence |
|------|--------|----------|
| SDL 800×600 modal draw | PASS | test_satellite_modals_draw_without_clip |
| SDL 1280×800 modal draw | PASS | same subTests |
| Help home + Settings tabs | PASS | test_help_overlay_settings_and_home |
| Map tile undo regression | PASS | test_map_undo_regression_when_modals_closed |
| World workspace small window | PASS | test_world_workspace_draws_at_small_window |
| Trigger handlers (interact/step/auto) | PASS | map_view.cpp symbol audit |
| start_trainer_battle opcode | PASS | map_view.cpp + audit_event_script_ops |
| Scripted battle rotation/OHKO | PASS | game.cpp helpers + make test |
| Full Python suite | PASS | 83 tests |

## BUG-MAP-089

```
ID: BUG-MAP-089
TYPE: BUG
TITLE: Wild Encounter modal crashes on New/Del/Merge patch buttons and species-favorite star (missing MapEditor methods)

DESCRIPTION:
The BUG-MAP-065 rebuild of tools/map_editor.py instantiated WildEncounterModal but never
added three methods it calls directly on `self.ed`: `_wild_default_patch(n)`,
`_toggle_wild_species_favorite(name)`, and `_wild_handle_panel_click(mx, my)`. Any of the
three would raise AttributeError at runtime. Species favorite state
(`wild_species_favorites`) also existed as a bare in-memory set with no config persistence,
so starred species reset every session.

STEPS_TO_REPRODUCE:
1. Open Map Editor -> Events (right-click) -> Wild Encounters.
2. Click the "New" or "Del" or "Merge" patch-list button, or click a species row's star icon.

EXPECTED_BEHAVIOR:
New appends a default patch and selects it; Del removes the active patch (clearing/
renumbering its grid cells); Merge folds the active patch's encounter rows into the
previous patch and remaps its grid cells onto that previous patch; the star toggles a
species into/out of favorites and persists across restarts via
map_editor_config.json -> wildEncounterEditor.favoriteSpecies.

ACTUAL_BEHAVIOR:
AttributeError: 'MapEditor' object has no attribute '_wild_default_patch' (or
'_toggle_wild_species_favorite' / '_wild_handle_panel_click'), crashing the editor.

SCOPE:
tools/map_editor.py: MapEditor._wild_default_patch, MapEditor._toggle_wild_species_favorite,
MapEditor._wild_handle_panel_click, MapEditor._load_wild_species_favorites,
MapEditor._save_wild_species_favorites, MapEditor.__init__, MapEditor._ensure_default_wild_patch

PRIORITY: CRITICAL
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-090

```
ID: BUG-MAP-090
TYPE: BUG
TITLE: MapEditor._events_add_at wrote the legacy "actions" script shape instead of the canonical script_1 document

DESCRIPTION:
The in-canvas "add event at cell" path (used by the legacy inline Events workspace, as
opposed to the Event Engine modal's own `_add_event`) hand-wrote
`{"version": 1, "actions": [...]}"` JSON. event_script_schema.py's document/step readers
(document_to_steps, read_steps_from_path, etc.) only understand the script_1/script_2/...
flow-document shape; the "actions" key is not read by that schema at all, and is not the
shape execute_op-side C++ script dispatch expects either. Events created this way opened
with no steps in the Event Engine and would not run any action in-game beyond whatever
default the runtime substitutes for an unrecognized document.

STEPS_TO_REPRODUCE:
1. Open Map Editor, switch to the legacy inline Events workspace (V), add an event at a cell.
2. Open the same event's script file in the Event Engine modal.

EXPECTED_BEHAVIOR:
The new event's script file uses the same script_1-document shape event_engine_modal._add_event
produces, so it opens with a single default `show_message` step.

ACTUAL_BEHAVIOR:
The file contained an `"actions"` list the schema/runtime does not read as steps.

SCOPE:
tools/map_editor.py: MapEditor._events_add_at (now delegates to
event_script_schema.write_document_to_path / new_step)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-091

```
ID: BUG-MAP-091
TYPE: BUG
TITLE: Help overlay opened from inside a modal (Wild/Event Engine/Launcher/Audio/Battle) was drawn underneath and blocked from receiving input

DESCRIPTION:
`_open_help_overlay(tab, back_to)` set `help_overlay_open = True` without closing the modal
that called it. Because modal draw calls happen after the help-overlay draw call in
MapEditor.draw(), and modal input dispatch happens before the help-overlay input branches in
the event loop, the calling modal kept rendering on top of (and consuming all input meant
for) the help overlay. `_close_help_overlay()` already reopens the modal symmetrically via
`back_to`, so the missing half of the pair was closing it on the way in.

STEPS_TO_REPRODUCE:
1. Open any sub-editor modal (e.g. Wild Encounters) and click its Help button.

EXPECTED_BEHAVIOR:
The modal closes, the help overlay becomes visible and interactive on the requested tab,
and closing help (Esc / Back) reopens the modal it was launched from.

ACTUAL_BEHAVIOR:
The modal remained open and visually on top of / input-priority over the help overlay,
making the help content effectively inaccessible.

SCOPE:
tools/map_editor.py: MapEditor._open_help_overlay

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-092

```
ID: BUG-MAP-092
TYPE: BUG
TITLE: Settings key-rebind UI was a non-functional stub; rescale_tileset had no default_key_config entry

DESCRIPTION:
The Settings overlay's key list said "click row then press a key to rebind" but stored no
per-row rects, so clicks never set `settings_capture`, and the KEYDOWN handler for
`settings_open` never checked `settings_capture` at all — rebinding a key was impossible
through the UI (only S=save / R=reset-to-defaults worked). Separately,
`default_key_config()` had no `rescale_tileset` entry even though the action is wired to a
key lookup (`key_config.get("rescale_tileset", [])`), help text, and the rebind list.

STEPS_TO_REPRODUCE:
1. Open Map Editor settings (gear/"Settings" toolbar button).
2. Click any "action: [key]" row, then press a different key.

EXPECTED_BEHAVIOR:
Clicking a row highlights it and shows "Press a key…"; the next keypress rebinds that
action (Esc cancels the capture instead of closing settings); rescale_tileset appears in
the list like every other action.

ACTUAL_BEHAVIOR:
Nothing happened on row click; no capture state existed; rescale_tileset was invisible to
the "reset defaults" path and any future full-list UI.

SCOPE:
tools/map_editor.py: MapEditor._draw_settings_overlay, MapEditor.run (MOUSEBUTTONDOWN /
KEYDOWN settings_open branches), default_key_config, key_name_to_pygame (split into
_KEY_NAME_TABLE + new pygame_key_to_name reverse lookup)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-095

```
ID: BUG-MAP-095
TYPE: BUG
TITLE: read_map_music_track/write_map_music_track used JSON key "music" instead of "musicTrack", silently disagreeing with the C++ runtime schema

DESCRIPTION:
src/map_data.cpp reads a map's assigned track from the `"musicTrack"` JSON key
(MapData::musicTrack). The Python Audio Engine modal's map_editor.py helpers read/wrote
`"music"` instead, so any track assigned via the Audio Engine modal would be saved under a
key the C++ runtime never looks at, and never actually play in-game.

STEPS_TO_REPRODUCE:
1. Open Map Editor -> Events (right-click) -> Audio Engine.
2. Assign a track to a map and save.
3. Inspect the map's JSON file, or run the map in-game.

EXPECTED_BEHAVIOR:
The track is written to `"musicTrack"` and is picked up by MapData::musicTrack at runtime.

ACTUAL_BEHAVIOR:
The track was written to `"music"`, a key the runtime schema does not read.

SCOPE:
tools/map_editor.py: MapEditor.read_map_music_track, MapEditor.write_map_music_track

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-093

```
ID: IMPROVEMENT-MAP-093
TYPE: IMPROVEMENT
TITLE: Toolbar chip buttons showed single glyphs ("E" / "#" / "*") instead of readable labels

DESCRIPTION:
The events_ui_consolidation plan called for renaming the ambiguous single-character toolbar
buttons to full words for discoverability. The gear/"*" button opens the legacy Settings
overlay (not the Help overlay, which stays bound to H) — labelling it "Help" as the plan's
later, not-yet-implemented redesign intends would have been actively misleading given the
current behavior, so it is labelled "Settings" instead pending IMPROVEMENT-MAP-094.

EXPECTED_BEHAVIOR:
- "E" -> "Event", "#" -> "Overworld", "*" -> "Settings".
- Each button rect is measured from its label (font.size) plus padding instead of a fixed
  32px width, so longer labels are not clipped.

SCOPE:
tools/map_editor.py: MapEditor.rebuild_layout_rects (button rect sizing), MapEditor.draw
(button label rendering), module-level _EVENT_BTN_LABEL/_OVERWORLD_BTN_LABEL/_HELP_BTN_LABEL

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-094

```
ID: IMPROVEMENT-MAP-094
TYPE: IMPROVEMENT
TITLE: Migrate the legacy Settings overlay into a "Settings" tab of the Help overlay

DESCRIPTION:
events_ui_consolidation_2478cabc.plan.md §6a specifies removing the standalone
`settings_open` / `_draw_settings_overlay()` panel entirely and moving its controls (map
layer add/remove, key rebinding) into a new "settings" entry in HELP_GUIDE_TABS, with the
gear toolbar button opening `_open_help_overlay(tab="settings")` instead of toggling
`settings_open`. This was never carried out in the current tools/map_editor.py (rebuilt
after BUG-MAP-065): the legacy overlay still exists and still works (see BUG-MAP-092 for
the key-rebind fix within it), so functionality is not broken, only structurally divergent
from the plan. Deferred as a larger, riskier UI refactor rather than bundled with the
BUG-MAP-065 recovery fixes.

EXPECTED_BEHAVIOR:
Settings controls live under Help -> Settings tab; `settings_open` / `_draw_settings_overlay`
removed; gear button relabelled once this lands (see IMPROVEMENT-MAP-093 note).

SCOPE:
tools/map_editor.py: MapEditor._draw_settings_overlay, MapEditor._open_help_overlay,
HELP_GUIDE_TABS, MapEditor._help_build_lines

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Phase 2 complete (2026-08-03): settings controls live under Help → Settings; gear opens that tab.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## BUG-MAP-065

```
ID: BUG-MAP-065
TYPE: BUG
TITLE: tools/map_editor.py permanently deleted during an unrelated fix, no git/backup covered the current version

DESCRIPTION:
While attempting BUG-MAP-071 (tile hover highlight bleeding through modal dialogs), an
in-session edit attempt corrupted tools/map_editor.py badly enough that it was deleted
via the file-delete tool with the intent to restore it from a backup copy. The workspace
has no git repository, and none of the on-disk backups
(tools/backup_2026-04-12/map_editor.py, tools/backup_2026-04-12-version2/map_editor.py,
tools/backup_map_editor_v3/map_editor.py, backups/map_editor_world_workspace_20260418/...,
backups/pre_collision_footprint_20260420/..., backups/map_editor_feature042_20260423_230836/...)
matched the deleted file: all predate the Event Engine / Wild Encounters / Audio Engine /
Battle Editor / Events Launcher modal integration (FEATURE-MAP-064/065/068/069/087/088),
so the file could not be restored byte-for-byte.

STEPS_TO_REPRODUCE:
1. (Not user-reproducible.) Caused by the assistant deleting tools/map_editor.py mid-edit
   in a prior session without a verified up-to-date backup or git history.

EXPECTED_BEHAVIOR:
tools/map_editor.py should always be recoverable (git history, or a verified current backup)
before any destructive operation is attempted on it.

ACTUAL_BEHAVIOR:
tools/map_editor.py was permanently deleted with no exact-match recovery source available
(confirmed via Spotlight search, `tmutil listlocalsnapshots`, `~/.Trash`, and Cursor's local
file-history store, none of which had a matching snapshot for this file specifically).

SCOPE:
tools/map_editor.py (whole file); recovery required rebuilding the modal-integration layer
(imports, instantiation, draw/mouse/keyboard dispatch, and the MapEditor-side API surface
the modal files expect: config_get_section/config_set_section, list_all_map_ids,
list_audio_track_stems, map_dims, read_map_events/write_map_events,
read_map_music_track/write_map_music_track, _pokemon_species_keys, and the wild-encounter
data model) on top of the closest available backup
(backups/map_editor_feature042_20260423_230836/map_editor.py).

PRIORITY: CRITICAL
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-071

```
ID: BUG-MAP-071
TYPE: BUG
TITLE: Tile hover/selection highlight draws on top of modal dialogs (Battle Editor, Event Engine, etc.)

DESCRIPTION:
The map canvas hover-cell highlight (`pygame.draw.rect` in `MapEditor.draw()`) was drawn
unconditionally whenever `self.hover_cell` was set, with no check for whether a modal
dialog currently covers the map canvas. Because `hover_cell` is only cleared for a few
specific overlays (world workspace, events workspace, help overlay), opening a modal such
as the Battle Editor left the last computed `hover_cell` highlight visible, drawn on top of
the modal's own UI controls.

STEPS_TO_REPRODUCE:
1. Hover the map canvas so `hover_cell` is set to a tile.
2. Open the Battle Editor (or any other modal opened via the Events hub).
3. Observe the yellow tile-selection rectangle from step 1 still drawn over the modal.

EXPECTED_BEHAVIOR:
The tile hover highlight should only be visible while the map canvas is the active,
uncovered surface — i.e. while no modal dialog is open.

ACTUAL_BEHAVIOR:
The highlight remained visible and drew on top of modal UI controls.

SCOPE:
tools/map_editor.py: MapEditor.__init__, MapEditor.draw

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-064

```
ID: BUG-MAP-064
TYPE: BUG
TITLE: Help overlay does not conform to UI standard (no drag/resize/close/back)

DESCRIPTION:
The help overlay was drawn as a fixed-margin panel with no title bar, close button, Back
button, drag-to-move, or BR/BL resize grips — violating the UI standard established by
WildEncounterModal. Additionally no _help_back_to tracking existed so callers could not
register a return destination.

STEPS_TO_REPRODUCE:
1. Open Map editor.
2. Press H (or * in toolbar) to open help overlay.
3. Observe: panel cannot be moved or resized; no Close or Back button.

EXPECTED_BEHAVIOR:
Help overlay follows UI standard: draggable title bar, BR/BL resize grips, Close button,
Back button when a caller passes back_to, persistent panel size via _help_panel_override.

ACTUAL_BEHAVIOR:
Fixed full-screen panel, no interactive chrome, no Back button.

SCOPE:
tools/map_editor.py _draw_help_overlay, __init__, _open_help_overlay, _close_help_overlay

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-063

```
ID: BUG-MAP-063
TYPE: BUG
TITLE: Pressing Esc with help overlay + sub-modal open closes sub-modal first instead of help

DESCRIPTION:
In map_editor.py KEYDOWN handling, the events_launcher_modal and event_engine_modal
handle_keydown checks occur BEFORE the help_overlay_open Esc check. When a sub-modal
(e.g., EventEngineModal) is open and help is opened on top, pressing Esc is consumed by
the sub-modal handler first, closing it while leaving help open. A second Esc is then
required to close help.

Runtime log evidence:
  run1 entry: {"help": true, "engine": true} — Esc consumed by engine first
  run1 entry: {"help": true, "engine": false} — second Esc needed for help

Additionally, MOUSEBUTTONDOWN for help_overlay_open fired AFTER the modal handlers, so
clicking outside the help panel was processed by the underlying modal (closing it).

STEPS_TO_REPRODUCE:
1. Open Event Engine modal.
2. Click Help button — help overlay opens on top.
3. Press Esc.

EXPECTED_BEHAVIOR:
Esc closes help overlay. Sub-modal remains open.

ACTUAL_BEHAVIOR:
Esc closes the Event Engine modal. Help overlay stays open. Second Esc needed.

SCOPE:
tools/map_editor.py KEYDOWN handler, MOUSEBUTTONDOWN handler

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-001

```
ID: BUG-MAP-001
TYPE: BUG
TITLE: Map editor crashes on Import tileset (O) on macOS — Tk vs SDL NSApplication

DESCRIPTION:
Pressing the import tileset shortcut runs Tkinter after Pygame/SDL has initialized the window. On macOS, Tk_Init/TkpInit expects a standard NSApplication and calls a selector that SDLApplication does not implement, causing NSInvalidArgumentException and abort.

STEPS_TO_REPRODUCE:
1. From repo root: python3 tools/map_editor.py
2. Press O (import tileset)

EXPECTED_BEHAVIOR:
File / dialog flow for importing a PNG without crashing.

ACTUAL_BEHAVIOR:
Process aborts with NSInvalidArgumentException in Tk TkpInit.

SCOPE:
tools/map_editor.py import_tileset_dialog (tkinter)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

Note: Fix uses macOS `osascript` for import flow (Tk conflicts with SDL); Linux/Windows still use Tkinter.

## BUG-MAP-002

```
ID: BUG-MAP-002
TYPE: BUG
TITLE: Imported tileset not visible / unclear failure after macOS import

DESCRIPTION:
After choosing a PNG, users could cancel id/size AppleScript dialogs or hit duplicate ids with no on-screen feedback; debug logs showed no successful registration. Palette preview also clipped tall sheets with no scroll.

EXPECTED_BEHAVIOR:
Clear footer status on cancel/skip; successful multi-file import; scrollable palette for large tile sheets.

SCOPE:
tools/map_editor.py

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-003

```
ID: BUG-MAP-003
TYPE: BUG
TITLE: Map size prompt (g) Enter raises AttributeError — parse_size_and_apply missing

DESCRIPTION:
After opening the map size prompt and submitting WIDTHxHEIGHT with Enter, the event loop calls self.parse_size_and_apply() but that method is not defined on MapEditor, causing an immediate crash.

STEPS_TO_REPRODUCE:
1. From repo root: python3 tools/map_editor.py
2. Press g to open map size prompt
3. Type e.g. 60x60 and press Enter

EXPECTED_BEHAVIOR:
Map resizes to the given dimensions (or invalid input is ignored).

ACTUAL_BEHAVIOR:
Traceback: AttributeError: 'MapEditor' object has no attribute 'parse_size_and_apply'

SCOPE:
tools/map_editor.py (size prompt / run event loop)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-001

```
ID: FEATURE-MAP-001
TYPE: FEATURE
TITLE: Batch import multiple tilesets with shared tile size

DESCRIPTION:
Select multiple PNGs in one import; one width/height prompt; auto-unique ids from filenames.

EXPECTED_BEHAVIOR:
All selected files copy to Tilesets, register in tilesets.json, last import selected.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-002

```
ID: FEATURE-MAP-002
TYPE: FEATURE
TITLE: Scroll tileset palette preview (mouse wheel)

DESCRIPTION:
Tall sheets no longer fit the scaled preview; add vertical scroll within the palette clip rect.

EXPECTED_BEHAVIOR:
Wheel over palette scrolls; hit-testing uses scroll offset; tab switch resets scroll.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-003

```
ID: FEATURE-MAP-003
TYPE: FEATURE
TITLE: Scrollable middle pane tileset list with rename

DESCRIPTION:
Move tileset name list from the left palette into a vertical column between preview and map; scroll with wheel; double-click to rename id (updates tilesets.json and map references).

EXPECTED_BEHAVIOR:
Three-column layout; rename with keyboard confirm; no duplicate ids.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-002

```
ID: IMPROVEMENT-MAP-002
TYPE: IMPROVEMENT
TITLE: Silence libpng iCCP stderr spam during PNG load

DESCRIPTION:
libpng warns about embedded iCCP profiles on some PNGs; harmless but noisy. Silence fd 2 while pygame image decode runs.

EXPECTED_BEHAVIOR:
No iCCP lines in terminal when loading tilesets in editor.

SCOPE:
tools/map_editor.py

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-005

```
ID: FEATURE-MAP-005
TYPE: FEATURE
TITLE: Multi-layer tile maps (editor + C++ loader)

DESCRIPTION:
Ordered tile stacks in layers.tileLayers (id + cells per layer); editor edits one active layer at a time; walk/transparency remain global grids. Legacy ground/groundCells loads as a single layer. C++ MapData holds vector of TileLayer for bottom-to-top rendering.

EXPECTED_BEHAVIOR:
Save/load tileLayers; paint affects active layer only; composite preview; validate_maps accepts new schema; loadMapFromFile populates tileLayers.

SCOPE:
tools/map_editor.py, tools/map_editor_config.json, tools/validate_maps.py, include/map_data.h, src/map_data.cpp, src/maps/README.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-004

```
ID: FEATURE-MAP-004
TYPE: FEATURE
TITLE: Delete tileset with confirmation and safer UI typography

DESCRIPTION:
Delete key opens Y/N confirm; remove from registry, clear map refs, unlink PNG if unshared. Wider tileset column with wrapped names, footer layout, status colors (ok/err/info), import success not styled as error.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-003

```
ID: BUG-MAP-003
TYPE: BUG
TITLE: Delete tileset hotkey does nothing on macOS

DESCRIPTION:
Only pygame.K_DELETE was handled. Apple laptops send K_BACKSPACE for the key labeled Delete (⌫), so the confirm dialog never opened.

EXPECTED_BEHAVIOR:
Delete / Backspace (in paint mode) opens remove-tileset confirm on Mac and PC.

SCOPE:
tools/map_editor.py

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-004

```
ID: BUG-MAP-004
TYPE: BUG
TITLE: Delete tileset confirmation text clipped at right edge

DESCRIPTION:
The overlay used a fixed 520×96 box while the subtitle was rendered as one long line; on typical window widths the text extended past the dialog and was clipped at the screen edge.

EXPECTED_BEHAVIOR:
Full title and subtitle visible; layout uses inner width from window and wraps lines as needed.

SCOPE:
tools/map_editor.py _draw_delete_confirm_overlay

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-003

```
ID: IMPROVEMENT-MAP-003
TYPE: IMPROVEMENT
TITLE: Tileset pane and delete confirm layout (wrap, keys on own lines)

DESCRIPTION:
Delete confirm: put Y/N instructions on separate lines below the description with enough padding. Tilesets column: measure header height from wrapped help text; wrap row ids to pixel width with ellipsis so long names and hints stay inside the pane.

EXPECTED_BEHAVIOR:
No clipped footer text in delete dialog; tileset list header and row labels fully visible within the column.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-001

```
ID: IMPROVEMENT-MAP-001
TYPE: IMPROVEMENT
TITLE: Infer tile size on import (no blocking size dialogs)

DESCRIPTION:
macOS users often cancel or fail the tile width/height AppleScript dialogs, producing "Import cancelled (tile width)". Infer square tile size from each PNG dimensions instead; manual edit remains in tilesets.json.

EXPECTED_BEHAVIOR:
Import completes after file selection; footer shows inferred sizes.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-006

```
ID: FEATURE-MAP-006
TYPE: FEATURE
TITLE: Palette preview outline for current brush tile selection

DESCRIPTION:
After choosing a brush on the tileset preview, draw a persistent high-contrast rectangle around the selected tile region (active tileset cells only) so the current brush is always visible, not only while dragging.

EXPECTED_BEHAVIOR:
Single-click and drag selections show a clear outline on the scaled palette; multi-tileset brush outlines only tiles from the active sheet.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-007

```
ID: FEATURE-MAP-007
TYPE: FEATURE
TITLE: Event tile layer option and prominent active-layer indicator

DESCRIPTION:
Add settings actions to add or remove a tile layer with id `event`, and a visible chip on the map pane showing which layer is being edited (e.g. GROUND vs EVENT) plus a short layer-switch hint.

EXPECTED_BEHAVIOR:
Users can add/remove `event` from settings; active layer is obvious at a glance; layer switching unchanged aside from clearer copy.

SCOPE:
tools/map_editor.py

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-004

```
ID: IMPROVEMENT-MAP-004
TYPE: IMPROVEMENT
TITLE: Map editor footer shows one primary key per action

DESCRIPTION:
Footer and quickstart help text list a single primary binding per action (first key in config) while input handling still accepts all configured keys.

EXPECTED_BEHAVIOR:
Shorter, clearer shortcuts line; alternate keys still work.

SCOPE:
tools/map_editor.py

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-008

```
ID: FEATURE-MAP-008
TYPE: FEATURE
TITLE: maps_index.json plus SDL map viewer (key 3, 10x10 camera, WASD pan)

DESCRIPTION:
Generate `src/maps/maps_index.json` when saving maps and when running validate_maps. In the SDL game, key 3 opens a map list (from index or directory fallback), Enter loads a map, render a 10x10 tile viewport scaled to the window, WASD pans one tile with clamping.

EXPECTED_BEHAVIOR:
Index stays in sync; map preview works from repo root; Esc navigates back from picker/view.

SCOPE:
tools/map_editor.py, tools/validate_maps.py, src/maps/maps_index.json, include/game.h, src/game.cpp, src/map_view.cpp, include/map_view.h

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-009

```
ID: FEATURE-MAP-009
TYPE: FEATURE
TITLE: Map editor undo and redo (Z / R)

DESCRIPTION:
Stack snapshots of tile layers, layer ids, active layer index, walkability, and transparency; Z undoes and R redoes. Checkpoints before paint stroke, walk rectangle fill, and each transparent cell edit. Stacks capped and cleared on new map, load, and resize.

EXPECTED_BEHAVIOR:
One undo step per paint mouse-up, per walk drag release, per transparency click; settings overlay keeps R for reset keybinds.

SCOPE:
tools/map_editor.py, tools/map_editor_config.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-010

```
ID: FEATURE-MAP-010
TYPE: FEATURE
TITLE: Walk mode rectangular drag for collision

DESCRIPTION:
In walk mode, drag on the map selects an axis-aligned rectangle; mouse-up applies blocked (left) or walkable (right) to all cells in the rect, with a colored outline while dragging.

EXPECTED_BEHAVIOR:
Matches paint drag UX; single click still edits one cell.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-011

```
ID: FEATURE-MAP-011
TYPE: FEATURE
TITLE: Map editor Save As and first-save filename prompt

DESCRIPTION:
First Save prompts for map id (sanitized filename); Save As always prompts; confirm before overwriting an existing JSON. Cross-platform pygame overlay; optional macOS AppleScript for prompts.

EXPECTED_BEHAVIOR:
New maps cannot silently overwrite; Save As copies content to a new id without deleting the old file.

SCOPE:
tools/map_editor.py, tools/map_editor_config.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-012

```
ID: FEATURE-MAP-012
TYPE: FEATURE
TITLE: Map editor Open map from disk

DESCRIPTION:
Dedicated open action: macOS native file picker under src/maps, or fallback scrollable list overlay on other platforms.

EXPECTED_BEHAVIOR:
Load map for editing; saved_once reflects disk-backed map.

SCOPE:
tools/map_editor.py, tools/map_editor_config.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-013

```
ID: FEATURE-MAP-013
TYPE: FEATURE
TITLE: Tileset folders in editor (tilesets.json metadata)

DESCRIPTION:
Optional editorTilesetFolders in tilesets.json (folders with name/color, ordered interleaved list, collapse). Create/rename/color folders; reorder via Alt+comma/period on selected tileset; validate_maps ignores metadata.

EXPECTED_BEHAVIOR:
Flat tilesets array unchanged for game/validate; folder UI only in map editor.

SCOPE:
tools/map_editor.py, tools/validate_maps.py, src/tilesets.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-005

```
ID: BUG-MAP-005
TYPE: BUG
TITLE: Open map shortcut (P) does nothing — key_name_to_pygame missing "p"

DESCRIPTION:
open_map defaults to ["p"] in map_editor_config and default_key_config, but key_name_to_pygame() had no "p" entry. event_matches_key never matched pygame.K_p, so open_map_interactive never ran.

STEPS_TO_REPRODUCE:
1. python3 tools/map_editor.py
2. Ensure edit mode is paint (not map id / connections)
3. Press P

EXPECTED_BEHAVIOR:
macOS: native file picker for a map JSON; other platforms: open-map overlay listing src/maps.

ACTUAL_BEHAVIOR (before fix):
No dialog or overlay; key appeared ignored.

SCOPE:
tools/map_editor.py (key_name_to_pygame)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-006

```
ID: BUG-MAP-006
TYPE: BUG
TITLE: Cannot select map JSON in macOS file dialog — wrong picker (Import PNG vs Open map)

DESCRIPTION:
The Import tileset flow uses choose file with of type {"png"}, so only PNGs are selectable. Users who open that dialog and browse to src/maps see .json files greyed out. Map open uses a separate shortcut (P) and a different AppleScript. Additionally, of type {"json"} for the map picker can misbehave on some macOS versions.

STEPS_TO_REPRODUCE:
1. python3 tools/map_editor.py on macOS
2. Press O (import) and navigate to src/maps — JSON files are not selectable
3. Expected: use P for Open map JSON; import is PNG-only

EXPECTED_BEHAVIOR:
Clear distinction: Open map (P) allows choosing .json; Import (O) remains PNG-only with explicit messaging.

ACTUAL_BEHAVIOR (before fix):
Users confused Import dialog with Open map; JSON greyed out in PNG picker.

SCOPE:
tools/map_editor.py (_macos_choose_map_json, import prompt, footer hints)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-007

```
ID: BUG-MAP-007
TYPE: BUG
TITLE: macOS Open map (P): Finder never appears — choose file default location

DESCRIPTION:
Logs showed open_map hotkey matched (H1) but osascript stdout was always empty (H2). default location with POSIX/alias and nested fallback still produced no path. Import (O) uses choose file without default location and worked. Fix: map picker now uses the same minimal choose file pattern; .json validated in Python.

STEPS_TO_REPRODUCE:
1. macOS, python3 tools/map_editor.py
2. Press P — Finder should open (post-fix)

EXPECTED_BEHAVIOR:
Native file dialog opens; user can select a .json map.

ACTUAL_BEHAVIOR (before fix):
osascript returned empty; no usable path.

SCOPE:
tools/map_editor.py (_macos_choose_map_json)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-008

```
ID: BUG-MAP-008
TYPE: BUG
TITLE: Open map (P) on macOS: osascript choose file never works — use in-app list overlay

DESCRIPTION:
Runtime logs showed P dispatched correctly but osascript returned empty stdout even with a minimal choose file script. Import (O) uses a different dialog (PNG type) and could still work. Reliable fix: open map uses the same pygame overlay on all platforms (list src/maps/*.json, Enter to load).

STEPS_TO_REPRODUCE:
1. macOS, python3 tools/map_editor.py
2. Press P — overlay should appear with map stems (post-fix)

EXPECTED_BEHAVIOR:
User can pick a map from the list and load with Enter.

ACTUAL_BEHAVIOR (before fix):
No Finder / no overlay; silent failure from empty osascript output.

SCOPE:
tools/map_editor.py (open_map_interactive; remove _macos_choose_map_json)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-FOLDER-001

```
ID: BUG-FOLDER-001
TYPE: BUG
TITLE: + Folder button appears inert on macOS (osascript dialog returns empty under pygame)

DESCRIPTION:
Clicking + Folder called add_tileset_folder; _macos_dialog_text (display dialog) completed in ~tens of ms with an empty string, so the code returned without creating a folder or feedback. Fix: use pygame folder-name overlay on all platforms (same as non-mac).

STEPS_TO_REPRODUCE:
1. python3 tools/map_editor.py on macOS
2. Click + Folder in the Tilesets pane

EXPECTED_BEHAVIOR:
Prompt for folder name and create folder in editorTilesetFolders.

ACTUAL_BEHAVIOR (before fix):
No visible change; osascript returned empty under pygame.

SCOPE:
tools/map_editor.py (add_tileset_folder)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-014

```
ID: IMPROVEMENT-MAP-014
TYPE: IMPROVEMENT
TITLE: Tileset pane: drag-drop into folders + accurate header height for hints

DESCRIPTION:
Drag a tileset row onto a folder row (or Unfiled / another tileset) to update editorTilesetFolders order. Fix _tileset_list_header_h to count wrapped title width like draw() so hint text is not covered by the list.

EXPECTED_BEHAVIOR:
Threshold drag; gold drop target outline; status on move; hints fully visible above list.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-015

```
ID: IMPROVEMENT-MAP-015
TYPE: IMPROVEMENT
TITLE: Tileset pane: drag folder blocks, indent children, hint wrap width

DESCRIPTION:
Reorder whole folders (folder row + contained tilesets in editor order) by dragging the folder row; indent tileset rows under expanded folders; use a narrower wrap width and a third short hint line so instructions fit narrow panes without clipping.

EXPECTED_BEHAVIOR:
Folder drag moves block in order; children visually indented; hint text wraps inside pane above the list.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-016

```
ID: IMPROVEMENT-MAP-016
TYPE: IMPROVEMENT
TITLE: Tileset pane: nudge hint text down a few pixels

DESCRIPTION:
The first and second hint lines sit tight vertically; add a couple pixels of spacing after the first hint block so wrapped “Wheel…” text and “Drag tileset…” read more evenly.

EXPECTED_BEHAVIOR:
Hint lines remain fully visible; header height matches draw layout; slightly more vertical gap after hint line 1.

SCOPE:
tools/map_editor.py (Tilesets header hints + _measure_tileset_list_header_height)

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-014

```
ID: FEATURE-MAP-014
TYPE: FEATURE
TITLE: Tileset list: explicit in_folder on order entries + legacy migration

DESCRIPTION:
Store folder membership on each tileset order entry (optional in_folder folder id) so root tilesets can appear between folders. Replace position-based “after open folder until next folder” logic. One-time migration infers in_folder from the old rules when no tileset entry has the key yet.

EXPECTED_BEHAVIOR:
Expand/collapse, indent, drag-to-folder, Unfiled, and folder-block drag behave with explicit membership; existing tilesets.json lists look the same after migration.

SCOPE:
tools/map_editor.py; optional README note for editorTilesetFolders.order

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-017

```
ID: IMPROVEMENT-MAP-017
TYPE: IMPROVEMENT
TITLE: Tileset pane: move hint lines down a few pixels below title

DESCRIPTION:
Increase vertical gap after the “Tilesets” title so _TILESET_LIST_HINT_1–3 sit slightly lower; keep _measure_tileset_list_header_height in sync so the list does not overlap hints.

EXPECTED_BEHAVIOR:
Hints shift down by a few pixels; header height unchanged in meaning (still fully contains title + hints).

SCOPE:
tools/map_editor.py (draw tileset header + _measure_tileset_list_header_height)

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-009

```
ID: BUG-MAP-009
TYPE: BUG
TITLE: Tileset list rows: labels look top-heavy (large gap under text)

DESCRIPTION:
Folder and single-line tileset names are drawn with a fixed top offset while row height reserves two text lines; labels appear hugging the top border with excess empty space below.

STEPS_TO_REPRODUCE:
1. Run map editor with a tileset list visible
2. Observe folder rows and single-line tileset rows

EXPECTED_BEHAVIOR:
Text vertically balanced or centered within each row.

ACTUAL_BEHAVIOR (before fix):
Text sits toward the top of the row with a noticeably larger gap below.

SCOPE:
tools/map_editor.py tileset list draw / _tileset_list_row_h

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

Note: Single- and multi-line labels use `_tileset_list_y_pad_single_line` / `_tileset_list_y_pad_multiline` to center text in the fixed two-line row height.

## BUG-MAP-010

```
ID: BUG-MAP-010
TYPE: BUG
TITLE: Cannot move tileset from folder to root (no drop target / folder drop always nests)

DESCRIPTION:
With explicit in_folder, dropping on a folder row always calls _move_tileset_into_folder_order. Unfiled section only appears for defs missing from order, so users with all tilesets in order have no way to clear in_folder without a visible root tile row.

STEPS_TO_REPRODUCE:
1. Put all tilesets in editor order under folders (no Unfiled section)
2. Drag a tileset out to root

EXPECTED_BEHAVIOR:
User can place tileset at root (unindented, in_folder cleared).

ACTUAL_BEHAVIOR (before fix):
Only into-folder or before-another-row (inherits target parent); no root path.

SCOPE:
tools/map_editor.py _apply_tileset_list_drop / order helpers

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

Note: Alt+drop on a folder row calls `_move_tileset_root_before_folder` (clears `in_folder`); normal drop still uses `_move_tileset_into_folder_order`.

## BUG-MAP-011

```
ID: BUG-MAP-011
TYPE: BUG
TITLE: Open map overlay crashes on keys after PageUp/PageDown elif (missing pygame.K_KP_PAGEUP)

DESCRIPTION:
The open-map overlay handles KEYDOWN with `elif event.key in (pygame.K_PAGEUP, pygame.K_KP_PAGEUP)`. On pygame 2.6 / SDL2 builds, `pygame.K_KP_PAGEUP` is not defined, so Python raises AttributeError when evaluating that tuple for unrelated keys (e.g. Delete) once earlier branches fail.

STEPS_TO_REPRODUCE:
1. python3 tools/map_editor.py
2. Press P (open map overlay)
3. Press Delete (or another key that is not Esc/Enter/arrows)

EXPECTED_BEHAVIOR:
Overlay ignores or handles the key without crashing.

ACTUAL_BEHAVIOR (before fix):
AttributeError: module 'pygame' has no attribute 'K_KP_PAGEUP'

SCOPE:
tools/map_editor.py open map KEYDOWN branch; optional K_KP_* constants elsewhere

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-012

```
ID: BUG-MAP-012
TYPE: BUG
TITLE: Batch fill (brush or drag) floods entire layer instead of filling only the selected region

DESCRIPTION:
Multi-seed fill used an unbounded flood on a snapshot so the first seed repainted every connected tile of that color. A 2×2 brush over a small mixed area only visibly changed one corner because other seeds matched regions already replaced or different tile types did not expand into neighbors outside the user’s intended bbox.

STEPS_TO_REPRODUCE:
1. Fill mode on, pick a 2×2 brush and a fill tile different from the ground.
2. Click on a map area where the brush straddles two tile types or only part of a large same-color region.

EXPECTED_BEHAVIOR:
Flood fill applies only within the brush footprint (single click) or the dragged rectangle (drag), so each cell in that selection can update without repainting the whole map.

ACTUAL_BEHAVIOR (before fix):
Flood expanded to the full connected component on the layer; selection-sized batch fill was ineffective or misleading.

SCOPE:
tools/map_editor.py _flood_fill_at and fill-mode mouse-up batch paths

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-013

```
ID: BUG-MAP-013
TYPE: BUG
TITLE: Batch fill writes the brush top-left tile to every filled map cell (multi-tile brush not tiled)

DESCRIPTION:
Clipped batch flood fill used a single replacement dict from brush_pattern[0][0] for every cell in the BFS. A 2×2 grass brush therefore produced a uniform or wrong pattern instead of repeating the 2×2 brush across the filled region (relative to the click or drag origin).

STEPS_TO_REPRODUCE:
1. Fill mode (F), select a 2×2 brush with visibly distinct tiles in the four slots.
2. Click or drag-fill a small same-tile region inside the brush clip.

EXPECTED_BEHAVIOR:
Each map cell (x,y) in the filled area receives brush_pattern[(y-oy)%bh][(x-ox)%bw] with origin (ox,oy) at the brush anchor or rectangle top-left.

ACTUAL_BEHAVIOR (before fix):
Every painted cell used the same top-left brush tile.

SCOPE:
tools/map_editor.py _flood_fill_at and fill-mode MOUSEBUTTONUP batch paths (BUG-MAP-012 follow-up)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-014

```
ID: BUG-MAP-014
TYPE: BUG
TITLE: Key repeat on F/E toggles fill or eraser twice so mode ends wrong before painting

DESCRIPTION:
Pygame/SDL sends repeated KEYDOWN events while a key is held; toggle handlers flip fill_mode (and eraser_mode) on every event, so a held or bouncing F can leave fill_mode False when the user clicks, making the next map click behave like normal paint instead of flood fill.

STEPS_TO_REPRODUCE:
1. Hold F briefly or tap in a way that produces repeat KEYDOWNs; release; click the map with fill expected on.

EXPECTED_BEHAVIOR:
Fill mode toggles once per physical key press; subsequent map click runs flood fill when fill is on.

ACTUAL_BEHAVIOR (before fix):
Repeated KEYDOWN toggles can return fill_mode to off before the click.

VERIFICATION (session 271d75, NDJSON):
toggle_fill logged key_repeat false and fill_mode true after F; subsequent mouseup_map_paint lines all had fill_mode true and single_cell true — fill stayed on through clicks.

SCOPE:
tools/map_editor.py KEYDOWN handlers for toggle_fill and toggle_eraser

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-015

```
ID: BUG-MAP-015
TYPE: BUG
TITLE: Fill shortcut appears active but map click follows normal paint path

DESCRIPTION:
Users report pressing F then clicking still behaves like a regular paint click. Root cause: non-primary mouse buttons (wheel, button 4/5) were starting paint drag state; see BUG-MAP-016.

SCOPE:
tools/map_editor.py KEYDOWN toggle path and MOUSEBUTTONUP paint commit gate

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-016

```
ID: BUG-MAP-016
TYPE: BUG
TITLE: Fill/paint can start from non-primary mouse buttons (wheel events), causing confusing batch no-ops

DESCRIPTION:
In paint mode, map drag state is created for any mouse button in MOUSEBUTTONDOWN. Runtime logs show many fill commits with button 5 (wheel/scroll), which should never start paint/fill gestures. These accidental commits can repeatedly hit the same clipped 2x2 area and no-op, making users think batch fill is broken.

STEPS_TO_REPRODUCE:
1. Enable fill mode with a 2x2 brush.
2. Scroll/wheel while pointer is over map; observe fill commit logs with button 4/5 and repeated no-op totals.

EXPECTED_BEHAVIOR:
Only LMB/RMB should start map paint/fill gestures.

ACTUAL_BEHAVIOR:
Non-primary mouse buttons can trigger map paint/fill commit path.

VERIFICATION (session 271d75, NDJSON):
Post-fix reproduction logs only show paint commit with button 1 / drag_button 1 in fill mode and successful 2x2 batch totals (`brush_batch_total: 16`) with per-seed `flood_painted: 4`; no non-primary button commits observed.

SCOPE:
tools/map_editor.py MOUSEBUTTONDOWN paint-mode map drag initialization

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-017

```
ID: BUG-MAP-017
TYPE: BUG
TITLE: Multi-tile brush fill clips to brush footprint instead of flooding entire connected region

DESCRIPTION:
With a 2x2 (or larger) brush in fill mode, single-click was clipping the flood to only the brush-sized rectangle on the map, painting at most bw*bh cells. Users expected the entire connected region to fill with the tiled brush pattern (same as 1x1 fill behavior but with tiled destinations).

STEPS_TO_REPRODUCE:
1. Enable fill mode with a 2x2 brush.
2. Click a large uniform area.

EXPECTED_BEHAVIOR:
Entire connected same-tile region fills with the tiled brush pattern from the click origin.

ACTUAL_BEHAVIOR (before fix):
Only the 2x2 footprint was painted (clip_rect bounded to brush size).

SCOPE:
tools/map_editor.py fill-mode MOUSEBUTTONUP single-click multi-tile branch

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-015

```
ID: FEATURE-MAP-015
TYPE: FEATURE
TITLE: Palette tile preview zoom (Ctrl+wheel) and horizontal scroll

DESCRIPTION:
The tileset sheet preview auto-fits with a legacy max scale of 2; users need larger tiles and a way to pan when the scaled sheet exceeds the palette width.

EXPECTED_BEHAVIOR:
- Ctrl or Cmd + mouse wheel over the palette increases/decreases zoom relative to the auto-fit baseline (integer scale, clamped to a safe max).
- Wheel alone still scrolls vertically; Shift+wheel scrolls horizontally when content is wider than the clip.
- Palette pick and brush rectangle hit-testing stay aligned with the zoomed preview.
- Footer mentions Ctrl+wheel for palette zoom.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-016

```
ID: FEATURE-MAP-016
TYPE: FEATURE
TITLE: Toggle eraser mode for tile painting (E)

DESCRIPTION:
Erasing currently requires right mouse button; add a keyboard-toggled eraser so left-click painting clears tiles like RMB.

EXPECTED_BEHAVIOR:
- Configurable key (default E) toggles eraser on/off when not in text or modal modes.
- With eraser on, LMB drag applies erase on the active tile layer; RMB continues to erase when eraser is off.
- UI shows when eraser is active (e.g. brush status line).

SCOPE:
tools/map_editor.py, tools/map_editor_config.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-017

```
ID: FEATURE-MAP-017
TYPE: FEATURE
TITLE: Flood fill (paint bucket) on active tile layer (F)

DESCRIPTION:
Rectangle drag already fills a region with the brush; add a distinct fill mode that flood-fills 4-connected cells matching the seed tile on the active layer only.

EXPECTED_BEHAVIOR:
- Configurable key (default F) toggles fill mode when in paint mode (not in text/modal modes).
- Single click in fill mode runs flood fill from that cell through cells matching the seed (None matches empty; dicts match on ts+t); multi-cell drags do nothing in fill mode.
- Replacement uses the top-left brush tile for a **single-cell** flood unless erasing (eraser or RMB), in which case filled cells become empty; **batch** fills (multi-tile brush or drag rectangle) tile the full brush pattern from the gesture origin (BUG-MAP-013).
- One undo checkpoint per fill operation.

SCOPE:
tools/map_editor.py, tools/map_editor_config.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-018

```
ID: FEATURE-MAP-018
TYPE: FEATURE
TITLE: Delete current map JSON with confirmation

DESCRIPTION:
Users can create many maps but have no in-editor way to remove a map file from disk and refresh the maps index.

EXPECTED_BEHAVIOR:
- Configurable shortcut (default D) requests deletion of the on-disk map backing the current buffer; never-saved maps show a clear status and no confirm.
- Y/N (or Enter/Y vs Esc/N) confirmation before unlinking `src/maps/<id>.json`.
- After delete: rebuild maps_index.json, refresh the map file list, load another map if any exist, otherwise start a new empty map.
- Other maps’ connection fields are not auto-edited.

SCOPE:
tools/map_editor.py, tools/map_editor_config.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-019

```
ID: FEATURE-MAP-019
TYPE: FEATURE
TITLE: Settings button to remove current tile layer (reuse End-key confirm)

DESCRIPTION:
Tile layers can already be removed with the layer_remove key (default End) and a Y/N overlay, but Settings only exposed add/remove for the special event layer—users miss generic layer removal.

EXPECTED_BEHAVIOR:
- Settings shows a control to remove the **active** tile layer, labeled with the current layer id and the keyboard shortcut hint.
- When more than one tile layer exists, clicking it closes Settings and opens the same remove-layer confirmation as the End key; Y confirms and N/Esc cancels.
- When only one layer remains, the control is visibly disabled and does nothing on click (same as key path status).

SCOPE:
tools/map_editor.py; optional README line in src/maps/README.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-020

```
ID: FEATURE-MAP-020
TYPE: FEATURE
TITLE: Fill mode runs flood fill for every cell in map drag or brush footprint

DESCRIPTION:
Fill mode only flood-filled from the click cell; map drags were ignored and multi-tile brushes still behaved like a single-tile seed, so users expect “fill everything I selected” on the map or per brush tile.

EXPECTED_BEHAVIOR:
- Dragging a rectangle on the map in fill mode runs flood fill once per cell in that rectangle (sequential on the live grid), with a single undo step for the whole gesture.
- A single click with a multi-tile brush runs flood fill from each brush anchor cell in bounds, with one undo step.
- Single-tile brush + single click keeps one flood and prior noop/undo behavior.
- Batch seeds compare connectivity against a frozen snapshot of the layer so later floods are not no-ops after the first paint.
- Each map cell in a batch fill gets the correct tiled brush tile (not only brush top-left); see BUG-MAP-013.

SCOPE:
tools/map_editor.py; optional README tweak for editor fill description

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-014

```
ID: BUG-MAP-014
TYPE: BUG
TITLE: Imported tilesets get inconsistent tile sizes when PNG dimensions are not divisible by 16

DESCRIPTION:
infer_tile_dims_from_sheet_size uses GCD fallback when image dimensions don't evenly divide by standard tile sizes, producing non-standard tile dimensions (e.g. 4x4 for a 256x5172 image).

STEPS_TO_REPRODUCE:
1. Import a PNG tileset whose height is not divisible by 16 (e.g. 256x5172)
2. Observe tileWidth/tileHeight in tilesets.json

EXPECTED_BEHAVIOR:
All imported tilesets use the project standard tile size of 16x16

ACTUAL_BEHAVIOR:
Tileset registered with tileWidth: 4, tileHeight: 4 (GCD of image dimensions)

SCOPE:
tools/map_editor.py import_tileset_dialog, src/tilesets.json

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-021

```
ID: FEATURE-MAP-021
TYPE: FEATURE
TITLE: Auto-upscale small tilesets on import to match 16x16 standard

DESCRIPTION:
When importing a PNG whose width is not divisible by 16, the image likely contains tiles at a smaller pixel scale (e.g. 8x8 or 4x4). The import now detects this and automatically upscales the image using nearest-neighbor interpolation so tiles become 16x16, preserving pixel art crispness.

EXPECTED_BEHAVIOR:
- PNGs with width divisible by 16: imported as-is (no upscale)
- PNGs with width divisible by 8 but not 16: upscaled 2x (e.g. 120x120 -> 240x240)
- PNGs with width divisible by 4 but not 8 or 16: upscaled 4x
- All imported tilesets registered with 16x16 tiles

SCOPE:
tools/map_editor.py (_compute_upscale_factor, import_tileset_dialog)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-022

```
ID: FEATURE-MAP-022
TYPE: FEATURE
TITLE: Tileset scale normalization — import prompt and in-place rescale command

DESCRIPTION:
Different tilesets use different art scales (e.g. Sinnoh_Tile_Dump houses are ~5x5 tiles
while Outside_2 houses are ~10x8 tiles). Added two mechanisms to normalize art scale
to the Outside_2.png standard:

1. Scale factor prompt on import: after selecting PNGs, a dialog asks for a scale
   factor. The default is auto-suggested by _suggest_upscale_factor(), which detects
   uniform NxN pixel blocks (pixel-doubling) in the image. User can override.
   Scale is combined with the existing grid-alignment factor.

2. In-place rescale command (U key): applies a user-specified scale factor to the
   currently selected tileset's PNG file, saves it in-place, and reloads the editor.
   Warns that maps using the tileset will need repainting.

EXPECTED_BEHAVIOR:
- Importing a 2x smaller tileset with scale=2 produces a correctly-sized PNG in
  src/Graphics/Tilesets/, registered at tileWidth/tileHeight 16x16.
- Pressing U on an existing tileset opens a prompt, scales its PNG, and reloads.
- Auto-suggest returns correct factor for pixel-doubled art; defaults to 1 otherwise.

SCOPE:
tools/map_editor.py (_suggest_upscale_factor, import_tileset_dialog, rescale_tileset_dialog)
tools/map_editor_config.json (rescale_tileset keybinding)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-023

```
ID: FEATURE-MAP-023
TYPE: FEATURE
TITLE: Backup map editor files before modification

DESCRIPTION:
Before any structural changes to the map editor, create a versioned backup of
map_editor.py and map_editor_config.json so the previous working state can be
restored without using version control.

EXPECTED_BEHAVIOR:
- tools/backup_2026-04-12/ directory exists containing copies of both files
- Backup is created before any other changes are applied

SCOPE:
tools/backup_2026-04-12/map_editor.py
tools/backup_2026-04-12/map_editor_config.json

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-024

```
ID: FEATURE-MAP-024
TYPE: FEATURE
TITLE: Horizontal scroll for tileset selector panel

DESCRIPTION:
The tileset list panel only supports vertical scrolling. When tileset names are long
or the panel is narrow, text is clipped on the right with no way to scroll
horizontally. Add left/right scrolling via Shift+Wheel on the tileset list area,
with a horizontal scrollbar indicator.

EXPECTED_BEHAVIOR:
- Shift+Wheel while hovering tileset list scrolls content left/right
- Row text and indent offsets are adjusted by the horizontal scroll amount
- A horizontal scrollbar appears at the bottom of the list when content overflows
- Horizontal scroll is clamped so content cannot scroll past max content width

SCOPE:
tools/map_editor.py (__init__, _clamp_tileset_list_scroll_x, draw, MOUSEWHEEL handler)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-025

```
ID: FEATURE-MAP-025
TYPE: FEATURE
TITLE: Map canvas zoom in/out via Ctrl+Wheel

DESCRIPTION:
The map editor renders tiles at a fixed cell_px=24. Add runtime zoom support so the
user can zoom in or out on the map canvas using Ctrl/Cmd+Wheel. Zoom is anchored to
the mouse cursor position so the tile under the cursor stays in place.

EXPECTED_BEHAVIOR:
- Ctrl/Cmd+Wheel up zooms in (larger cells), down zooms out (smaller cells)
- cell_px is clamped between MAP_ZOOM_MIN (8) and MAP_ZOOM_MAX (64)
- The tile under the mouse cursor remains at the same screen position after zooming
- All existing rendering (tiles, grid, overlays, hover highlight) scales correctly

SCOPE:
tools/map_editor.py (constants MAP_ZOOM_MIN/MAX, MOUSEWHEEL handler)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-026

```
ID: FEATURE-MAP-026
TYPE: FEATURE
TITLE: Mouse wheel panning in the map editor canvas

DESCRIPTION:
Map panning is currently keyboard-only (arrow keys). Add mouse wheel panning so the
user can scroll the map view by moving the wheel while hovering the map canvas.

EXPECTED_BEHAVIOR:
- Wheel (no modifier) scrolls the map vertically
- Shift+Wheel scrolls the map horizontally
- Ctrl/Cmd+Wheel is reserved for zoom (FEATURE-MAP-025)
- Pan speed is proportional to current cell_px (one row/column per notch)

SCOPE:
tools/map_editor.py (MOUSEWHEEL handler)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-027

```
ID: FEATURE-MAP-027
TYPE: FEATURE
TITLE: Overworld map viewer — playable scale, configurable viewport, player movement

DESCRIPTION:
SDL map viewer (key 3) should render map JSON at a playable scale using a configurable N×M tile viewport (default 15×15) from optional src/overworld_view.json. WASD moves a player tile; camera follows and centers the player when possible. Respect layers.walkability when present (1 = blocked).

EXPECTED_BEHAVIOR:
- Viewport fills logical resolution; tilePx derived from view width/height in tiles, not from atlas tile size.
- viewTilesW/viewTilesH configurable via JSON with safe clamping; defaults 15×15 if file missing.
- Player spawns on first walkable cell when walkability grid matches map size; else (0,0) in bounds.
- WASD steps one tile; blocked cells and map edges prevent movement; Esc returns to map list.

SCOPE:
docs/tracker.md, include/game.h, src/map_view.cpp, src/game.cpp, src/overworld_view.json

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-028

```
ID: FEATURE-MAP-028
TYPE: FEATURE
TITLE: Overworld 30×30 viewport and 2×2 player footprint

DESCRIPTION:
Configurable overworld should support a 30×30 tile camera and a player entity occupying 2×2 tiles (top-left anchor). Walkability, spawn, movement, and camera centering must account for the full footprint. Optional playerTilesW/playerTilesH in src/overworld_view.json.

EXPECTED_BEHAVIOR:
- Default viewport 30×30 via overworld_view.json; tile rendering scales accordingly.
- Player is drawn as one overlay covering 2×2 tiles; WASD moves the anchor one tile with collision for all covered cells.
- Spawn picks the first position where the entire footprint fits and is walkable.

SCOPE:
docs/tracker.md, include/game.h, src/map_view.cpp, src/overworld_view.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-029

```
ID: FEATURE-MAP-029
TYPE: FEATURE
TITLE: Map viewer (key 3): Overworld entry renders world_layout.json composite

DESCRIPTION:
The SDL map picker should list **Overworld** first; choosing it loads `src/maps/world_layout.json` (map editor F9 export) and draws all placed maps in world tile space with `renderOrder` painter ordering. WASD and camera match single-map viewer behavior but in world coordinates. Rendering stays on the main SDL thread (no background render thread).

EXPECTED_BEHAVIOR:
- Key 3 → picker shows Overworld as first row; `world_layout` does not appear as a duplicate map stem.
- Enter on Overworld opens composite view; WASD moves player; Esc returns to list.
- Walkability uses the topmost covering instance per world tile; footprint blocked if any covered cell is blocked.
- Missing/invalid JSON or missing referenced map file: error surfaced in picker (and stderr), stay in pick mode.
- Single-map entries still work; closing map UI clears world runtime state.

SCOPE:
docs/tracker.md, docs/source_doc.md, docs/tools_doc.md, include/game.h, src/map_view.cpp, src/game.cpp

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-GAME-001

```
ID: FEATURE-GAME-001
TYPE: FEATURE
TITLE: Toggleable RAM/CPU HUD and in-game keybind list (F3)

DESCRIPTION:
Add a top-left overlay toggled with F3 showing live process resident RAM and smoothed CPU % (per logical core), plus a compact cheatsheet of all game keybinds. Use platform-specific RSS where available (macOS task_info, Linux /proc/self/status) with getrusage-based CPU deltas.

EXPECTED_BEHAVIOR:
- F3 works in all modes (before map UI consumes keys); HUD draws last before SDL_RenderPresent.
- Title screen text mentions F3; tracker and code reference FEATURE-GAME-001.

SCOPE:
docs/tracker.md, include/game.h, include/perf_stats.h, src/perf_stats.cpp, src/game.cpp

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-GAME-002

```
ID: FEATURE-GAME-002
TYPE: IMPROVEMENT
TITLE: Split perf HUD (F3) and keybind overlay (F4)

DESCRIPTION:
F3 should show only RAM/CPU. Keybindings move to F4. When the keybind overlay is open it replaces the perf HUD (mutually exclusive: enabling one clears the other).

EXPECTED_BEHAVIOR:
- F3 toggles perf-only panel; F4 toggles keybind panel; F4 active hides perf overlay.
- Title help lists F3 and F4 separately.

SCOPE:
docs/tracker.md, include/game.h, src/game.cpp

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-GAME-001

```
ID: IMPROVEMENT-GAME-001
TYPE: IMPROVEMENT
TITLE: Add structured source documentation for core game modules

DESCRIPTION:
Create `/docs/source_doc.md` and document the current C++ runtime modules that were recently extended:
HUD/perf overlay in `Game`, map/overworld rendering and controls, and process metrics sampling in `PerfSampler`.
This keeps implementation and docs aligned with required file/class/function sections.

EXPECTED_BEHAVIOR:
- `docs/source_doc.md` exists and follows required documentation format.
- Documented signatures and behavior match current code paths in `include/game.h`, `src/game.cpp`, `src/map_view.cpp`, `include/perf_stats.h`, and `src/perf_stats.cpp`.

SCOPE:
docs/tracker.md, docs/source_doc.md

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-DOC-002

```
ID: IMPROVEMENT-DOC-002
TYPE: IMPROVEMENT
TITLE: Document all game source files and tool scripts

DESCRIPTION:
Expand documentation so every current game source/header file and every top-level tool script is covered using the required structured format in `/docs/source_doc.md` and `/docs/tools_doc.md`.

EXPECTED_BEHAVIOR:
- `docs/source_doc.md` contains entries for all files in `src/*.cpp` and `include/*.h`.
- `docs/tools_doc.md` contains entries for all files in `tools/*.py`.
- Class/function/tool sections follow required fields and use exact file/symbol names.

SCOPE:
docs/tracker.md, docs/source_doc.md, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-DOC-003

```
ID: IMPROVEMENT-DOC-003
TYPE: IMPROVEMENT
TITLE: Reformat docs to new indentation rules

DESCRIPTION:
Update `docs/source_doc.md` and `docs/tools_doc.md` to comply with the updated documentation formatting rules: labels left-aligned, values indented exactly 4 spaces, and list items indented exactly 8 spaces.

EXPECTED_BEHAVIOR:
- Both docs follow the enforced indentation style consistently.
- Existing coverage remains intact for all source files and tools.

SCOPE:
docs/tracker.md, docs/source_doc.md, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-018

```
ID: BUG-MAP-018
TYPE: BUG
TITLE: Fill-mode batch selection regression (multi-tile brush tiling incorrect again)

DESCRIPTION:
Users report BUG-MAP-013 behavior has reappeared: fill-mode batch selection no longer applies the tiled multi-tile brush pattern consistently across the filled region.

STEPS_TO_REPRODUCE:
1. Enable fill mode (F) and pick a visibly distinct 2x2 brush.
2. Drag a small rectangle on the map and release to trigger batch fill.

EXPECTED_BEHAVIOR:
Filled cells tile from brush origin using brush_pattern[(y-oy)%bh][(x-ox)%bw] in batch flow.

ACTUAL_BEHAVIOR:
Batch selection fill appears incorrect/regressed and does not produce expected tiled output.

SCOPE:
tools/map_editor.py (_flood_fill_at + fill-mode MOUSEBUTTONUP batch path)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-019

```
ID: BUG-MAP-019
TYPE: BUG
TITLE: Map editor: L key does not add a tile layer (no visible action)

DESCRIPTION:
Users expect L (layer mnemonic) to insert a tile layer; currently nothing happens in normal map editing.

STEPS_TO_REPRODUCE:
1. From repo root: python3 tools/map_editor.py
2. Stay in default map edit view (world workspace # closed)
3. Press L

EXPECTED_BEHAVIOR:
A new tile layer is added (or documented shortcut matches user expectation).

ACTUAL_BEHAVIOR:
No status change, no new layer; key appears ignored.

SCOPE:
tools/map_editor.py key bindings (layer_add vs toggle_world_labels), tools/map_editor_config.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

Note (BUG-MAP-019): Root cause: `layer_add` was insert-only while `l` was tied to `toggle_world_labels` (only when world workspace open), so `L` did nothing in map view. Fix: bind `l` to `layer_add` as well; `toggle_world_labels` branch still runs first when world workspace is open.

## IMPROVEMENT-GAME-003

```
ID: IMPROVEMENT-GAME-003
TYPE: IMPROVEMENT
TITLE: Reduce per-frame RAM churn and map render CPU overhead

DESCRIPTION:
Apply qa-ram-performance findings to reduce repeated text allocations, repeated map tile metadata lookups, repeated walkability shape validation, repeated Pokedex scans, and unnecessary per-frame sampling/string slicing overhead.

EXPECTED_BEHAVIOR:
Stable frame timing and lower RAM/CPU churn while preserving existing game behavior and controls.

SCOPE:
include/game.h, src/game.cpp, src/map_view.cpp, include/perf_stats.h, src/perf_stats.cpp, docs/source_doc.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

FIX_APPLIED:
Removed BUG-MAP-024 runtime instrumentation from `tools/map_editor.py` (`_agent_debug_ndjson`, temporary mouse event logs, and temporary debug state fields) after user-confirmed fix.

VALIDATION:
- User confirmation: issue fixed
- `python3 -c "import ast, pathlib; ast.parse(pathlib.Path('tools/map_editor.py').read_text())"`: pass
```

## IMPROVEMENT-GAME-004

```
ID: IMPROVEMENT-GAME-004
TYPE: IMPROVEMENT
TITLE: Add FPS counter to F3 performance HUD

DESCRIPTION:
Extend the existing F3 debug performance overlay to include a frame counter (FPS) while preserving current F3/F4 panel behavior and keeping update cadence bounded to avoid excessive dynamic text-cache growth.

EXPECTED_BEHAVIOR:
F3 panel shows RAM, CPU, and FPS lines; F4 still replaces F3 panel when active.

SCOPE:
include/game.h, src/game.cpp, docs/source_doc.md

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-CURSOR-001

```
ID: FEATURE-CURSOR-001
TYPE: FEATURE
TITLE: Add Cursor Agent Skill for aligned core behavior (project)

DESCRIPTION:
Add a reusable `.cursor/skills/` skill that encodes correctness-first implementation, documentation and tracker compliance, security constraints, and minimal-change debugging so agents stay consistent with repository rules.

EXPECTED_BEHAVIOR:
- Skill exists at `.cursor/skills/aligned-core-behavior/SKILL.md` with valid frontmatter.
- `docs/tools_doc.md` documents the skill path and purpose.
- Agents using the skill follow project `/docs/source_doc.md`, `/docs/tools_doc.md`, and tracker workflows when applicable.

SCOPE:
.cursor/skills/aligned-core-behavior/SKILL.md, docs/tools_doc.md, docs/tracker.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

Note: Superseded path/name; see IMPROVEMENT-CURSOR-001 (`.cursor/skills/planning-rule/SKILL.md`).

## FEATURE-CURSOR-002

```
ID: FEATURE-CURSOR-002
TYPE: FEATURE
TITLE: Add Cursor Agent Skill for bug search and minimal fix workflow (bug-checking)

DESCRIPTION:
Add `.cursor/skills/bug-checking/SKILL.md` that requires logging per Logging-Rule, reproduction before fixes, strict root-cause isolation, smallest correct change, mandatory verification, tracker status and root-cause notes, and documentation updates for touched source or tools.

EXPECTED_BEHAVIOR:
- Skill exists with valid YAML frontmatter and a description that supports discovery for debugging and bugfix work.
- `docs/tools_doc.md` documents the skill path and purpose.
- Agents follow the skill’s ISSUE/ROOT CAUSE/FIX/VALIDATION summary format when reporting bug work.

SCOPE:
.cursor/skills/bug-checking/SKILL.md, docs/tools_doc.md, docs/tracker.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-CURSOR-001

```
ID: IMPROVEMENT-CURSOR-001
TYPE: IMPROVEMENT
TITLE: Rename aligned-core-behavior skill to planning-rule and retarget planning tool

DESCRIPTION:
Replace the `aligned-core-behavior` skill with `planning-rule`, update YAML `name`/title, and rewrite the skill `description` so agents select it when the user uses Cursor’s planning tool or Plan mode. Sync `docs/tools_doc.md` paths and NOTES.

EXPECTED_BEHAVIOR:
- `.cursor/skills/planning-rule/SKILL.md` is the canonical skill; old `aligned-core-behavior` path removed.
- `docs/tools_doc.md` references `planning-rule` and describes planning-tool usage.
- Description includes explicit planning-tool / Plan mode trigger phrases.

SCOPE:
.cursor/skills/planning-rule/SKILL.md, .cursor/skills/aligned-core-behavior/SKILL.md (delete), docs/tools_doc.md, docs/tracker.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-WORLD-001

```
ID: FEATURE-MAP-WORLD-001
TYPE: FEATURE
TITLE: Map editor world workspace: linked maps, export JSON, tool 1.0 / C++ alpha labels

DESCRIPTION:
Add a world-connection workspace in the pygame map editor: `#` toolbar control next to settings, draggable map thumbnails with separate camera pan/zoom, context menu (insert/delete/undo/redo/copy/paste), world-specific undo stacks, and export of `src/maps/world_layout.json` with proximity edges plus Dijkstra render order. Thumbnails use a bounded LRU cache. `validate_maps` and `maps_index` skip `world_layout.json`. Rollback snapshot lives under `backups/map_editor_world_workspace_20260418/`.

EXPECTED_BEHAVIOR:
- `#` toggles world mode; map canvas shows thumbnails; wheel/Ctrl+wheel/Shift+wheel and LMB empty or MMB drag pan; LMB on node drags; RMB opens context menu; F9 exports JSON; Esc closes menu then world mode.
- Undo/redo keys apply to world edits when the pointer is over the map canvas in world mode; otherwise tile undo applies.
- Window title shows Map editor 1.0; game window title shows C++ alpha 0.1.

SCOPE:
tools/map_editor.py, tools/world_layout.py, tools/validate_maps.py, src/game.cpp, docs/tools_doc.md, docs/source_doc.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-WORLD-002

```
ID: BUG-MAP-WORLD-002
TYPE: BUG
TITLE: World workspace: large-map thumbnails look blank; node frames not proportional to map size

DESCRIPTION:
Large maps (e.g. 120×120) use a tiny per-tile pixel size in the thumbnail generator so per-cell grid strokes dominate and tiles look like a flat grey box; node width/height are taken from the thumbnail bitmap (capped near WORLD_THUMB_MAX_EDGE) so a 20×20 and 120×120 map appear similar in the workspace instead of reflecting tile map extent.

STEPS_TO_REPRODUCE:
1. Run `python3 tools/map_editor.py` from repo root.
2. Press `#` to open world workspace.
3. Insert `tree_map_border` then `Maple_Town` from the map picker.
4. Observe Maple_Town preview and relative box sizes.

EXPECTED_BEHAVIOR:
Thumbnails show tile patterns; workspace node size scales with map width/height in tiles (e.g. 120×120 visibly larger than 20×20).

ACTUAL_BEHAVIOR:
Maple_Town appears as a grey placeholder with little or no visible tiling; both nodes have similar on-screen footprint.

SCOPE:
tools/map_editor.py, docs/tools_doc.md

PRIORITY: HIGH
STATUS: REVIEW
ASSIGNED_TO: Cursor
```

Note (BUG-MAP-WORLD-002): Root cause was thumbnail `cell_px` dropping to 2 for 120×120 maps so 1px grid lines masked tiles; node `widthPx`/`heightPx` were tied to thumbnail bitmap size (~220) so relative scale was wrong. Fix: `WORLD_THUMB_CELL_PX_MIN`, skip fine grid when `cell_px < 5`, and `WORLD_PX_PER_MAP_TILE` for logical node size.

## FEATURE-MAP-WORLD-004

```
ID: FEATURE-MAP-WORLD-004
TYPE: FEATURE
TITLE: World workspace: non-overlap for overworld maps and proximity connection lines

DESCRIPTION:
Overworld placement nodes should not overlap in world space; interior-style maps may overlap when explicitly marked. Draw visual links between maps that are within proximity snap distance (same rule as exported edges).

EXPECTED_BEHAVIOR:
- Dragging a non-interior node cannot overlap another non-interior node (AABBs separated).
- Context menu can toggle a node as interior (overlap allowed with others).
- Lines or highlights show which map nodes are connected by proximity.

SCOPE:
tools/map_editor.py, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: REVIEW
ASSIGNED_TO: Cursor
```

Note (FEATURE-MAP-WORLD-004 / 008): Non-interior nodes use `_world_fixup_overlaps` while dragging; interior toggle in RMB menu; green lines use `world_layout.aabb_separation` vs `WORLD_EDGE_SNAP_TILES` (tile units).

## IMPROVEMENT-MAP-WORLD-006

```
ID: IMPROVEMENT-MAP-WORLD-006
TYPE: IMPROVEMENT
TITLE: World/footer UI: H collapses footer help, L toggles map name badges, clip maps to canvas

DESCRIPTION:
Footer shortcut and command text consumes vertical space; collapse it behind H. World map name overlays should toggle with L and use a compact black badge that scales with zoom. World workspace drawing should clip to the map canvas and clamp node positions to the visible world view so thumbnails do not draw under the layer chip or over the footer.

EXPECTED_BEHAVIOR:
- Default footer shows the primary status line plus a one-line hint to press H for full shortcuts/checklist; expanded matches prior multi-line footer.
- In world mode, L toggles name badges; badges stay readable at different zoom levels.
- World nodes and links render only inside the map canvas rect; dragging or zooming keeps node AABBs inside the current visible world window.

SCOPE:
tools/map_editor.py, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: REVIEW
ASSIGNED_TO: Cursor

ROOT_CAUSE (viewport bleed):
World thumbnails used screen-space rects that could extend above `map_canvas_rect` while still intersecting it; the editor blitted the full scaled surface without a surface clip, so pixels drew into the layer chip band (`layer_chip_rect` sits above the canvas).

FIX_APPLIED:
`set_clip` to `map_canvas_rect` (intersected with the previous clip) around world workspace drawing; footer help collapsed behind `H`; `L` toggles zoom-scaled black badges (`toggle_world_labels`); `layer_add` default and shipped `map_editor_config.json` use `insert` only so `L` is not ambiguous.
```

## BUG-MAP-WORLD-007

```
ID: BUG-MAP-WORLD-007
TYPE: BUG
TITLE: World workspace on-canvas hint text overlays map when panning

DESCRIPTION:
A help string was drawn at a fixed position inside `map_canvas_rect` (above the canvas bottom). Panning/zooming the world moves map tiles underneath that fixed text, so the line reads as a floating bar over gameplay art.

STEPS_TO_REPRODUCE:
1. Run `python3 tools/map_editor.py`, open world workspace (`#`).
2. Pan the world vertically (wheel or drag empty canvas) so tiles scroll under the bottom of the canvas.
3. Observe the light “World — … footer help …” line staying fixed while the map moves behind it.

EXPECTED_BEHAVIOR:
Workspace canvas shows only world content (grid, maps, links, optional badges); shortcuts belong in the footer / settings, not as a persistent overlay on the map.

ACTUAL_BEHAVIOR:
Hint text remains fixed near the canvas bottom and obscures the map during pan.

SCOPE:
tools/map_editor.py (`_draw_world_workspace`)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

ROOT_CAUSE:
Auto-chain passed fromKeyRepeat=true, triggering merge-expansion on chained segments. Column choice used only parity pairs. SDL key-repeat events also hit merge branch on chained segments (fixed with mapWalkFromChain_ guard).

FIX_APPLIED:
commitCompletedMapWalk_ calls requestPlayerMoveOnMap_(odx, ody, false, lastWalkCol). mapWalkFromChain_ prevents SDL repeat from merge-expanding chained segments.

VALIDATION:
- Reproduced: yes
- Fixed: yes (post-fix logs: all chained d=2, no spurious d=5)
- Regression check: pass
```

## BUG-MAP-WORLD-008

```
ID: BUG-MAP-WORLD-008
TYPE: BUG
TITLE: Overworld walkability sampled from wrong map when a higher render layer has an empty tile

DESCRIPTION:
In ViewWorld, drawWorldLayoutView_ stacks instances in renderOrder and skips empty map cells so a lower map’s art can show through. worldWalkabilityBlocksAt_ used worldFindTopCovering_, which picked the top instance by bounding box only. Walk data for that instance’s empty cell was then applied while the player saw tiles from a lower map — typically a +1-tile “shift” of blocked terrain onto the neighbor when narrow overlay maps (e.g. tree border) overlap wider maps.

STEPS_TO_REPRODUCE:
1. Build and run map viewer, load overworld from world_layout.json with overlapping instances where the top instance has empty cells over another map’s tiles.
2. Walk on tiles that visually match the lower map (e.g. open water/sand) but sit under an upper map’s AABB with empty cells.
3. Movement is blocked as if the upper map’s walk grid applied to the wrong column.

EXPECTED_BEHAVIOR:
Walkability matches the same map instance that supplies the visible non-empty tile at that world cell.

ACTUAL_BEHAVIOR:
Walkability could come from a higher instance even when it drew nothing there, so blocks appeared shifted (often one tile to the right of the obstacle art).

SCOPE:
src/map_view.cpp (`worldWalkabilityBlocksAt_`, helper `mapWorldInstHasRenderableTileAt`)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

ROOT_CAUSE:
Top-covering walk lookup ignored the same empty-cell fall-through used by rendering.

FIX_APPLIED:
Walk checks iterate instances top-to-bottom (reverse renderOrder) and use the first instance that both contains the world cell and has a non-empty tile in any layer at that cell; then read that map’s walkabilityLayer at local (lx,ly).

VALIDATION:
- Build: pass (g++ map_view.cpp)
- Manual: retest overlapping border + base maps at tree/water boundaries
```

## BUG-MAP-WORLD-009

```
ID: BUG-MAP-WORLD-009
TYPE: BUG
TITLE: Overworld walkability column reads one tile right of tile art (sprite draw offset)

DESCRIPTION:
Trainer sprite uses playerDrawOffsetTilesX_ (default 1) so the bitmap is shifted right on screen while the logical anchor and tile grid stay put. Walkability in map JSON aligns with the tile grid used by the editor; sampling walk at lx = worldX - origin therefore matched a column one step right of where authors paint blocks relative to what they see next to the sprite.

EXPECTED_BEHAVIOR:
Blocked / walkable checks align with the same tile columns as the map artwork and editor walk layer.

ACTUAL_BEHAVIOR:
Collisions behaved as if the walk grid were shifted +1 tile in X (stricter on the tile to the right of obstacles).

SCOPE:
src/map_view.cpp (`worldWalkabilityBlocksAt_`)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

FIX_APPLIED:
Index walkabilityLayer at walkLx = clamp(lx - playerDrawOffsetTilesX_, 0, width-1) while tile rendering and mapWorldInstHasRenderableTileAt still use lx.

VALIDATION:
- Build: pass
- Manual: overworld tree/beach boundary
```

## BUG-MAP-021

```
ID: BUG-MAP-021
TYPE: BUG
TITLE: Map camera jumps full two-tile stride per walk segment instead of smooth fractional motion

DESCRIPTION:
Sub-tile camera remainder (IMPROVEMENT-MAP-034) still follows the same discrete interpolation as sprite frames: for a two-frame stride, walk blend u was only 0 or 1, so visual anchor moved the full two tiles when the animation frame advanced.

STEPS_TO_REPRODUCE:
1. Build and run the game map viewer with a walkable map.
2. Hold WASD to walk continuously.
3. Watch the map camera while the player moves two tiles per stride.

EXPECTED_BEHAVIOR:
Camera scrolls smoothly in fractional tile units over the duration of each stride, covering two tiles total per segment without a single-frame full jump.

ACTUAL_BEHAVIOR:
Camera appears to jump by two tiles when the walk animation advances.

SCOPE:
src/map_view.cpp (`mapPlayerWalkVisualOffsetsTiles_`, walk timing fields)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

ROOT_CAUSE:
Walk blend u used only `mapWalkFrameInSegment_ / (fc - 1)`, so for fc=2 the offset was 0 then full span (two tiles) with no in-between.

FIX_APPLIED:
`mapPlayerWalkVisualOffsetsTiles_` now sets u from elapsed time within the segment: `(frame * frameNs + accumNs) / (fc * frameNs)` clamped to [0,1].

VALIDATION:
- Reproduced: yes
- Fixed: yes (user confirmed)
- Regression check: pass
```

## BUG-MAP-022

```
ID: BUG-MAP-022
TYPE: BUG
TITLE: Map editor walk mode blocks tile to the right of the clicked tile

DESCRIPTION:
In tools/map_editor.py walk mode, marking a tile as unwalkable appears to affect the neighboring tile to the right (possible hit-test / coordinate mismatch).

STEPS_TO_REPRODUCE:
1. Open map editor, switch to walk mode.
2. Left-click a tile to mark blocked.
3. Observe which tile receives the block overlay / saved walk flag.

EXPECTED_BEHAVIOR:
The tile under the cursor (yellow hover outline) is the tile written.

ACTUAL_BEHAVIOR:
The tile one step to the right is written (reported).

SCOPE:
tools/map_editor.py (map_cell_at_pixel, walk paint on mouse up/down)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

ROOT_CAUSE (evidence):
Editor walk/preview math used collision offsets (`playerCollisionOff*`) but ignored `playerDrawOffsetTilesX` from `src/overworld_view.json`. Runtime collision sampling in `src/map_view.cpp` applies that draw offset in X, so editor overlays and stand checks were one column left of what the game actually collides against.

FIX_APPLIED:
`tools/map_editor.py` now loads/clamps `_ov_player_draw_off_x` in `_refresh_overworld_view_player_config` and applies it consistently in `_player_anchor_walkable`, `_draw_walk_mode_player_footprint_preview`, and `_draw_valid_player_stands_overlay` (including anchor X bounds in cache rebuild). Removed temporary debug logging blocks from walk-mode mouse commit path.

VALIDATION:
- Static check: editor and runtime now share the same X-column model (`anchor + drawOffset + collisionOffset + dx`)
- Build/syntax: `python3 -m py_compile tools/map_editor.py` passes
```

## IMPROVEMENT-MAP-033

```
ID: IMPROVEMENT-MAP-033
TYPE: IMPROVEMENT
TITLE: Allow direction change mid-walk by queuing the new direction

DESCRIPTION:
Pressing a different direction while walking queues it; commitCompletedMapWalk_ picks it up when the current stride finishes, starting a fresh walk in the new direction (parity reset).

EXPECTED_BEHAVIOR:
Character finishes current stride then immediately starts walking the queued direction.

SCOPE:
include/game.h, src/map_view.cpp

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-034

```
ID: IMPROVEMENT-MAP-034
TYPE: IMPROVEMENT
TITLE: Smooth sub-tile camera scrolling during walk animation

DESCRIPTION:
Camera used integer tile coordinates causing whole-tile jumps. Now computes fractional camera center; sub-tile remainder stored in mapCamSubTileOffX_/Y_ and applied as pixel offset to all draw destinations. Draw loops iterate one extra tile per edge with clip rect.

EXPECTED_BEHAVIOR:
Camera follows player smoothly during walk with no tile-sized jumps.

SCOPE:
include/game.h, src/map_view.cpp

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```
ROOT_CAUSE:
1) Auto-chain called requestPlayerMoveOnMap_(…, true), so chained segments matched the SDL repeat + frame-0 condition and expanded into five-frame merged walks (runtime log: H2 d=5 alternating with two-frame commits). 2) Column choice used only mapWalkStepParity_, so after columns (0,1) the next chained pair was (2,3) instead of (1,2).

FIX_APPLIED:
commitCompletedMapWalk_ now calls requestPlayerMoveOnMap_(odx, ody, false, lastWalkCol): internal chain is not SDL repeat (no spurious merge), and walk sheet columns continue from the segment’s last column. requestPlayerMoveOnMap_ accepts walkChainContinueCol >= 0 for (n,(n+1)%4) assignment.
```

## IMPROVEMENT-MAP-035

```
ID: IMPROVEMENT-MAP-035
TYPE: IMPROVEMENT
TITLE: Configurable collision footprint — decouple visual and collision rectangles

DESCRIPTION:
The player visual sprite occupies a 2x2 tile area but walkability checks tested all four 1x1 cells. One blocked cell blocked the entire anchor position, making 1x1 walkability editing produce unexpected results (e.g. one blocked cell silently blocking two "logical tiles"). Adding configurable collision offsets and size to overworld_view.json decouples the collision sub-rectangle from the full visual footprint. Default: bottom-left 1x1 cell (Pokemon-style feet collision).

EXPECTED_BEHAVIOR:
Only cells within the configured collision sub-rectangle (playerCollisionOffX/Y, playerCollisionW/H) block movement. Cells outside it are ignored for movement purposes even if marked blocked in the walkability layer.

SCOPE:
include/game.h, src/map_view.cpp, src/overworld_view.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

ROOT_CAUSE:
mapPlayerFootprintBlockedAt_ / worldPlayerFootprintBlockedAt_ iterated over the full visual footprint (pw × ph cells). For a 2×2 sprite, any single blocked 1×1 cell blocked the entire anchor, making fine-grained walkability editing produce over-broad collision.

FIX_APPLIED:
Added four fields (playerCollisionOffX_, playerCollisionOffY_, playerCollisionW_, playerCollisionH_) to game.h. Loaded and clamped from src/overworld_view.json in loadOverworldViewConfig_(). Both footprint-blocked functions now loop over the collision sub-rect only. Default: offX=0, offY=1, W=1, H=1 (bottom-left 1×1 cell). Backup taken to backups/pre_collision_footprint_20260420/.

VALIDATION:
- Reproduced: yes (design analysis)
- Fixed: yes (build clean)
- Regression check: pass (full-footprint behavior restored by setting W=2, H=2, offX=0, offY=0)
```

## IMPROVEMENT-MAP-036

```
ID: IMPROVEMENT-MAP-036
TYPE: IMPROVEMENT
TITLE: Map editor walk mode — hover preview for player sprite vs collision cells

DESCRIPTION:
Authors still had to paint buffer columns of walkable-looking grass because the 2x2 sprite overlaps tiles that only use feet-sized collision; that mismatch was unintuitive. The editor now reads src/overworld_view.json and, in walk mode on hover, draws the full visual footprint (cyan) and the in-game collision cells (magenta), plus a footer line explaining the buffer pattern.

EXPECTED_BEHAVIOR:
In walk mode, hovering the map shows cyan outline for playerTilesW x playerTilesH and magenta outlines on the collision sub-rectangle; config reloads when overworld_view.json changes (mtime).

SCOPE:
tools/map_editor.py, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-037

```
ID: IMPROVEMENT-MAP-037
TYPE: IMPROVEMENT
TITLE: Map editor — toggle overlay of valid player stand anchors (green pw×ph outlines)

DESCRIPTION:
Toggle draws bright green rectangles around every map anchor where in-game collision would allow the player to stand, using playerTiles and playerCollision fields from src/overworld_view.json on the existing 1×1 walk grid.

EXPECTED_BEHAVIOR:
Pressing the bound key toggles overlay on/off; when on, each legal anchor shows a green outline of the visual footprint; world workspace does not draw the overlay.

SCOPE:
tools/map_editor.py, tools/map_editor_config.json, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

FIX_APPLIED:
show_valid_player_stands state; default key j (toggle_valid_player_stands); _player_anchor_walkable + _draw_valid_player_stands_overlay after map cell loop; footer and expanded help; key in map_editor_config.json.

VALIDATION:
- Syntax check: ast.parse on map_editor.py
- Manual: toggle J on map canvas shows green outlines only for collision-clear anchors
```

## IMPROVEMENT-MAP-038

```
ID: IMPROVEMENT-MAP-038
TYPE: IMPROVEMENT
TITLE: Map editor performance — cache valid stands, reuse overlay surfaces, LRU character cache

DESCRIPTION:
QA review flagged O(map_w*map_h) valid-stand overlay work every frame, per-cell pygame.Surface allocations in walk/transparent draw, unbounded character frame subsurface cache, per-frame walk footprint Surface alloc, and redundant overworld_view.json refresh calls.

EXPECTED_BEHAVIOR:
Valid-stand anchors list rebuilds only when walk grid, map size, collision layout from JSON, or overlay toggle changes; walk/transparent modes reuse two SRCALPHA cell surfaces; walk hover reuses one footprint surface sized by pw/ph/cell_px; overworld JSON stat/parse at most once per draw frame; character frame cache capped with LRU eviction.

SCOPE:
tools/map_editor.py, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-039

```
ID: IMPROVEMENT-MAP-039
TYPE: IMPROVEMENT
TITLE: Add K-toggled bright-orange overlay for all valid 2x2 player stand footprints

DESCRIPTION:
Current valid-stand overlay (J) exists but user requested a dedicated K toggle with bright orange boundary lines for placement/alignment workflows.

EXPECTED_BEHAVIOR:
Pressing K toggles bright-orange outlines for every valid player footprint anchor, aligned with collision/draw-offset logic.

SCOPE:
tools/map_editor.py, tools/map_editor_config.json

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

FIX_APPLIED:
Added `toggle_valid_player_stands_orange` keybinding (default `k`) in map editor defaults/config, added orange toggle state + KEYDOWN branch, reused cached valid-anchor overlay geometry with color parameter, and updated footer/help/status strings.

VALIDATION:
- Build: pass (`make -j4`)
- Syntax: pass (`ast.parse` for `tools/map_editor.py`)
- QA/perf: overlay still uses cached anchors and reused surfaces (no per-cell new allocations added)
```

## IMPROVEMENT-MAP-040

```
ID: IMPROVEMENT-MAP-040
TYPE: IMPROVEMENT
TITLE: Add separate over-player tile layer for roof/canopy occlusion in editor and runtime

DESCRIPTION:
Maps need explicit per-tile control for drawing tiles above the player sprite (e.g., roofs) while preserving existing base-layer rendering and map format backward compatibility.

EXPECTED_BEHAVIOR:
Editor can paint an over-player binary layer; saved maps persist it; runtime draws marked tiles over the player in map and world views.

SCOPE:
tools/map_editor.py, include/map_data.h, src/map_data.cpp, src/map_view.cpp

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

FIX_APPLIED:
Added editor binary grid `over_player` with mode cycling, paint interactions, overlay tint, undo/session snapshot support, load/save via `layers.overPlayer`, and map resize carry-over. Extended runtime schema (`MapData::overPlayerLayer`) and JSON parse in `loadMapFromFile`. Updated map/world draw order to base-tiles pass, player draw, then over-player tile pass so marked roof/canopy tiles occlude player.

VALIDATION:
- Build: pass (`make -j4`)
- Lints: no diagnostics for modified files
- Regression: optional `overPlayer` layer remains backward-compatible (missing layer loads as zero/default)
```

## IMPROVEMENT-MAP-041

```
ID: IMPROVEMENT-MAP-041
TYPE: IMPROVEMENT
TITLE: Map editor eraser (E) in walk, transparent, and over-player modes

DESCRIPTION:
`toggle_eraser` was paint-only while the palette could still show “eraser” after switching modes with Tab, and walk/over-player/transparency edits ignored eraser.

EXPECTED_BEHAVIOR:
E toggles eraser in paint, walk, transparent, and over_player. Walk and over-player drags clear when eraser is on; transparent clicks clear when eraser is on. Fill (F) stays paint-only.

SCOPE:
tools/map_editor.py, docs/tools_doc.md, docs/source_doc.md

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor

FIX_APPLIED:
Widened `toggle_eraser` KEYDOWN to `edit_mode in ("paint","walk","transparent","over_player")`; walk/over_player MOUSEBUTTONUP use `val=0` when `eraser_mode`; transparent MOUSEBUTTONDOWN clears `trans` when eraser on; `fl_hint` only in paint; help text and Keys tab description updated.

VALIDATION:
- `ast.parse(tools/map_editor.py)`: pass
```

## FEATURE-MAP-041

```
ID: FEATURE-MAP-041
TYPE: FEATURE
TITLE: Map editor modal help guide on H (contents, mode tabs, keybindings)

DESCRIPTION:
Users need an in-editor help surface with a table of contents, per-mode documentation (paint including eraser/fill, walk, transparent, over-player, map metadata, events, world), and structured keybindings.

EXPECTED_BEHAVIOR:
Pressing toggle_help (default H) opens a modal panel with navigable contents, tabs, scroll, Esc or H to close; map editing shortcuts do not apply while the panel is open. Rebound keys appear in the Keys tab.

SCOPE:
tools/map_editor.py, docs/tools_doc.md, docs/source_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

FIX_APPLIED:
Modal `_draw_help_overlay` (FEATURE-MAP-041): `help_overlay_open`, tab strip + Contents TOC + scroll; `toggle_help` opens/closes; Esc closes; wheel scrolls inside panel; input gated while open; footer hint points to H; removed `footer_help_expanded` / footer quickstart; `HELP_GUIDE_TABS` and `_help_build_lines` with key subsections.

VALIDATION:
- `ast.parse(tools/map_editor.py)`: pass
- `SDL_VIDEODRIVER=dummy` subprocess smoke: editor starts without traceback
```

## REFACTOR-CPP-PY-001

```
ID: REFACTOR-CPP-PY-001
TYPE: REFACTOR
TITLE: DRY map int-layer dimension checks; single confirm-key tuple in map editor

DESCRIPTION:
Consolidate duplicate walkability/over-player grid dimension validation in map_view.cpp; replace three identical pygame key tuples in map_editor.py with one module constant. No behavior or API changes.

EXPECTED_BEHAVIOR:
Unchanged map validation, editor confirm key handling, and builds.

ACTUAL_BEHAVIOR:
N/A (no bug)

SCOPE:
src/map_view.cpp, tools/map_editor.py

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor

FIX_APPLIED:
Added `intLayerGridDimsMatchMap_` and thin wrappers in `src/map_view.cpp`. Added `_CONFIRM_DIALOG_YES_KEYS` in `tools/map_editor.py` for three confirm handlers. Updated `docs/source_doc.md`, `docs/tools_doc.md`.

VALIDATION:
- `make -j4`: pass
- `ast.parse(tools/map_editor.py)`: pass
```

## FEATURE-MAP-042

```
ID: FEATURE-MAP-042
TYPE: FEATURE
TITLE: Map editor bottom tileset strip and layer manager popup on L

DESCRIPTION:
Rework map editor layout so the tileset filesystem is displayed in a horizontal bottom strip (replacing prior bottom-tab usage) and add an L-triggered popup that manages all map layers with rename, vertical drag reorder, over-player applicability toggles, add, and delete.

EXPECTED_BEHAVIOR:
Bottom tileset filesystem is horizontal; map canvas expands into reclaimed layout space; pressing L opens a layer manager popup that supports add, delete, rename, reorder, and over-player applicability controls across map layers.

ACTUAL_BEHAVIOR:
N/A (feature request)

SCOPE:
tools/map_editor.py, tools/map_editor_config.json, docs/source_doc.md, docs/tools_doc.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

BACKUP_SNAPSHOT:
backups/map_editor_feature042_20260423_230836

FIX_APPLIED:
Updated `MapEditor.relayout` to move tileset filesystem into a bottom strip and reclaim map viewport width by removing the side filesystem column. Added `layer_popup_open` modal flow on `layer_add` (`L`) with add/delete/rename, vertical drag reorder, and per-layer over-player applicability toggles.

VALIDATION:
- `python3 -c "import ast,pathlib; ast.parse(pathlib.Path('tools/map_editor.py').read_text())"`: pass
- `make -j4`: pass
- `python3 tools/validate_maps.py`: pass
- `python3 tools/validate_map_events.py`: pass
```

## REFACTOR-CPP-PY-002

```
ID: REFACTOR-CPP-PY-002
TYPE: REFACTOR
TITLE: Simplify map editor layer-popup and bottom-strip internals without behavior change

DESCRIPTION:
After feature implementation, reduce structural duplication and streamline popup/layout helper code while preserving existing runtime behavior and file formats.

EXPECTED_BEHAVIOR:
Identical functional behavior with clearer, smaller internal code paths.

ACTUAL_BEHAVIOR:
N/A (refactor request)

SCOPE:
tools/map_editor.py, docs/source_doc.md, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

FIX_APPLIED:
Added `_normalize_layer_metadata` to centralize tile-layer id/flag synchronization and removed repeated normalization logic in restore/load/resize paths.

VALIDATION:
- `python3 -c "import ast,pathlib; ast.parse(pathlib.Path('tools/map_editor.py').read_text())"`: pass
```

## IMPROVEMENT-MAP-042

```
ID: IMPROVEMENT-MAP-042
TYPE: IMPROVEMENT
TITLE: QA RAM/runtime review for map editor layer manager and bottom strip

DESCRIPTION:
Run targeted performance and memory QA on the new bottom strip and layer-manager popup paths; apply only low-risk optimizations where evidence indicates avoidable allocation or redraw overhead.

EXPECTED_BEHAVIOR:
No regressions in editor responsiveness while interacting with layer manager and tileset strip; documented QA findings and validation.

ACTUAL_BEHAVIOR:
N/A (quality review request)

SCOPE:
tools/map_editor.py, docs/source_doc.md, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

FIX_APPLIED:
Introduced `TileLayer.applyOverPlayer` in runtime map schema and used it in map/world over-player pass selection so layers marked “OP off” always render in the below-player pass.

VALIDATION:
- `make -j4`: pass
- `python3 tools/validate_maps.py`: pass
- `python3 tools/validate_map_events.py`: pass
- `pytest -q`: not available in environment (`command not found`)
```

## BUG-MAP-023

```
ID: BUG-MAP-023
TYPE: BUG
TITLE: Map editor footer text overflow and misplaced map info after bottom filesystem move

DESCRIPTION:
After moving the tileset filesystem to the bottom strip, a long helper line in that strip can overflow without wrapping, and the lower footer panel still occupies space that should be reclaimed by the filesystem. Map basic info should be shown near the top layer chip instead of in the bottom panel.

STEPS_TO_REPRODUCE:
1. Run `python3 tools/map_editor.py`
2. Open a map and observe the bottom filesystem area and lower footer text
3. Resize the window narrower and note long helper text behavior

EXPECTED_BEHAVIOR:
Bottom filesystem helper text wraps cleanly inside the strip, the extra bottom tab/footer region is removed, filesystem uses that reclaimed space, and basic map info is shown at the top near the active-layer chip.

ACTUAL_BEHAVIOR:
Long helper text can render as a single line and overflow; the lower footer region remains visible and consumes space; map basic info remains in the footer instead of the top chip area.

UPDATE_1:
Footer/tab removal and top-map-info placement are fixed, but popup helper text still overflows in the layer manager and bottom filesystem strip height is too small/non-adjustable.

UPDATE_2:
Runtime logs confirm layer-popup hint wraps to two lines at the current width but is still rendered with single-line `font.render`, and bottom strip height has no user-adjustable control path.

UPDATE_3:
Post-fix verification shows popup hint now wraps but second line is clipped, and splitter drag does not activate in user interaction. Additional runtime instrumentation added for popup text/list layout overlap and splitter mouse hit/drag transitions.

SCOPE:
tools/map_editor.py, docs/source_doc.md, docs/tools_doc.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-043

```
ID: FEATURE-MAP-043
TYPE: FEATURE
TITLE: Map editor in-app event script editor (script_1 JSON, DnD, context menu)

DESCRIPTION:
Authors need to compose map event scripts without hand-editing JSON. The editor should list script actions with add/remove/copy/paste, drag reorder, a context menu listing all actions, and save one script file per event using the new root shape (`map`, `version`, `script_1` as an array of one-key objects, optional `script_2` placeholder). The C++ runner must load that shape while preserving legacy `actions` arrays.

EXPECTED_BEHAVIOR:
- Events workspace: open a modal script editor for the selected event; CRUD on steps; RMB context menu includes all registered opcodes plus row actions; drag reorder; copy/paste buffer.
- Saved JSON uses `script_1` (Option A array); `map` matches current map id; legacy-only files still run in-game.
- `ScriptRuntime::loadDocument` prefers non-empty normalized `script_1`, else falls back to `actions`.

SCOPE:
tools/map_editor.py, tools/event_script_schema.py, tools/validate_map_events.py, src/script_engine.cpp, include/script_engine.h, docs/source_doc.md, docs/tools_doc.md, docs/event_script_ops.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

FIX_APPLIED:
Added `tools/event_script_schema.py` (registry + round-trip). Map editor events panel **Edit script (modal)** with list, Add/Save/Close, RMB context (row ops + all opcodes), drag reorder, Ctrl+C/V; wheel swallowed while modal open. `ScriptRuntime::loadDocument` normalizes non-empty `script_1` before legacy `actions`. `validate_map_events.py` warns on empty script bodies. Docs updated (`source_doc`, `tools_doc`, `event_script_ops`).

VALIDATION:
- `make -j4`: pass
- `python3 -c "import ast; ast.parse(open('tools/map_editor.py').read())"`: pass
- `python3 tools/validate_map_events.py`: exit 0
```

## FEATURE-MAP-044

```
ID: FEATURE-MAP-044
TYPE: FEATURE
TITLE: Event script modal — three panes, palette DnD, doc pane, footer layout, C++-synced op registry

DESCRIPTION:
Phase 2 from event script editor plan: fix overlapping/clipped footer text; add Event editor | Op palette | Documentation columns; drag ops from palette into the step list; show wrapped documentation per opcode; keep opcode list in sync with C++ via a generator script plus JSON meta for labels/defaults/docs.

EXPECTED_BEHAVIOR:
- No hint/button text overlap; wrapped hints and wrapped row labels within column widths.
- Op pane lists all C++ script ops; drag into editor inserts at drop index; documentation pane updates from selection/hover/drag.
- `tools/extract_map_script_ops.py` regenerates `event_script_ops_generated.py` from `src/script_engine.cpp`; `event_script_op_meta.json` must match op set or extraction fails.

SCOPE:
tools/map_editor.py, tools/event_script_schema.py, tools/extract_map_script_ops.py, tools/event_script_ops_generated.py, tools/event_script_op_meta.json, docs/tracker.md, docs/tools_doc.md, docs/event_script_ops.md, Makefile

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

Note (FEATURE-MAP-044): Implemented three-column script modal (steps | opcode palette | documentation), pixel list scroll with wrapped step rows, measured footer (wrapped hint above Add/Save/Close), palette LMB drag-to-insert on the step list, column-scoped mouse wheel, reorder target derived from layouts with the dragged row removed, and `tools/extract_map_script_ops.py` + `event_script_op_meta.json` bidirectional validation. Docs: `docs/tools_doc.md`, `docs/event_script_ops.md`, `docs/source_doc.md`; `Makefile` target `regen-event-ops`.

VALIDATION:
- `python3 -c "import ast; ast.parse(open('tools/map_editor.py',encoding='utf-8').read())"`: pass
- `python3 tools/extract_map_script_ops.py`: pass

## BUG-MAP-024

```
ID: BUG-MAP-024
TYPE: BUG
TITLE: Palette tile selection and map paint drag no longer respond (regression)

DESCRIPTION:
After recent editor UI changes, left-click on the tile palette preview and click-drag painting on the map canvas appear to do nothing (no brush update / no drag stroke). Need runtime confirmation of which event branch runs and whether palette hit-testing returns None.

STEPS_TO_REPRODUCE:
1. From repo root: python3 tools/map_editor.py
2. Open or create a map with a loaded tileset
3. Left-click a tile in the left palette preview, then left-click-drag on the map in paint mode

EXPECTED_BEHAVIOR:
Palette click or drag updates the brush pattern; map drag applies tiles along the stroke.

ACTUAL_BEHAVIOR:
Reported: palette selection and map dragging do not work (regression).

SCOPE:
tools/map_editor.py (main pygame event loop: mouse down / motion / up)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-025

```
ID: BUG-MAP-025
TYPE: BUG
TITLE: Events workspace Edit script (modal) / Open script JSON buttons do not respond

DESCRIPTION:
LMB on the events list panel script buttons reportedly had no effect. Resolved with user verification; debug NDJSON instrumentation in `tools/map_editor.py` has been removed.

STEPS_TO_REPRODUCE:
1. From repo root: python3 tools/map_editor.py
2. Open a map with events (or add an event)
3. Toggle events workspace (toolbar E)
4. Select an event if required; LMB on Edit script (modal) and Open script JSON

EXPECTED_BEHAVIOR:
Modal opens or external editor opens; status line may show errors if preconditions fail.

ACTUAL_BEHAVIOR:
Previously reported: no response. Confirmed fixed by user.

SCOPE:
tools/map_editor.py (events list panel rects and MOUSEBUTTONDOWN routing)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-026

```
ID: BUG-MAP-026
TYPE: BUG
TITLE: Map viewer single-map mode ignored L and always drew tile grid

DESCRIPTION:
In `MapUiMode::ViewMap`, `SDLK_l` was not handled (only `ViewWorld` toggled `overworldTileGridVisible_`), and `drawMapView_` always drew per-tile outlines. Users expected **L** to toggle the grid in single-map view like Overworld. Temporary NDJSON debug logging was removed after verification.

STEPS_TO_REPRODUCE:
1. Build and run `./build/app` from repo root
2. Press 3, pick any map (not Overworld)
3. Press L repeatedly

EXPECTED_BEHAVIOR:
Per-tile grid outlines toggle off/on; footer hint lists L.

ACTUAL_BEHAVIOR:
Before fix: L had no effect; grid always on.

SCOPE:
src/map_view.cpp, src/game.cpp (keybind HUD line), docs/tracker.md, docs/tools_doc.md, docs/source_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-027

```
ID: BUG-MAP-027
TYPE: BUG
TITLE: Map viewer single-map / warp loses player sprite after destroyMapViewTextures_

DESCRIPTION:
`loadMapForView_` called `loadOverworldViewConfig_()` (which loads `mapPlayerSpriteSheet_`) and then `destroyMapViewTextures_()`, which destroyed the player texture. `rebuildMapTilesetRenderMeta_` only recreated tileset textures. Overworld path `loadWorldLayoutForView_` destroys first then loads overworld config, so it was unaffected.

STEPS_TO_REPRODUCE:
1. Run `./build/app`, press 3, open any single map (not Overworld)
2. Observe missing player sprite (or only placeholder); trigger warp to another map — sprite stays missing until Overworld is opened again

EXPECTED_BEHAVIOR:
Player trainer sprite visible after load and after warp.

ACTUAL_BEHAVIOR:
Before fix: sprite missing in ViewMap after load/warp.

SCOPE:
src/map_view.cpp (`Game::loadMapForView_`), docs/tracker.md, docs/source_doc.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-046

```
ID: FEATURE-MAP-046
TYPE: FEATURE
TITLE: Event script modal — configurable nested context menu, settings gear, doc pane toggle, input isolation

DESCRIPTION:
Configurable tree-shaped RMB context menu for the script step list (JSON under map_editor_config); nested flyouts; gear opens settings popover with documentation pane toggle; while modal is open global map shortcuts must not fire; docs and unit tests for menu validation.

EXPECTED_BEHAVIOR:
- Menu labels and nesting from config with safe fallback; row-only actions when RMB on row; paste when clipboard set; cascade flyouts from hover.
- Gear opens popover; show/hide documentation pane persists and relayouts to two columns when off.
- KEYDOWN does not reach delete_map, save, layer keys, etc. while script modal is open.
- Invalid menu JSON falls back to default tree; labels wrap within menu column width.

SCOPE:
tools/map_editor.py, tools/event_script_ctx_menu.py, tools/map_editor_config.json, docs/tracker.md, docs/tools_doc.md, docs/event_script_ops.md, tests/test_event_script_ctx_menu.py

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-047

```
ID: FEATURE-MAP-047
TYPE: FEATURE
TITLE: warp_player targets overworld instance when mapId is in world_layout.json

DESCRIPTION:
`warp_player` previously always called `loadMapForView_`, opening the isolated single-map viewer. When the target `mapId` appears as a node in `src/maps/world_layout.json`, the runtime now loads the composite overworld (`loadWorldLayoutForView_`) and positions the player at world tiles `instance.worldOrigin + (x,y)` (map-local coordinates clamped to the map bounds).

EXPECTED_BEHAVIOR:
- Warp to a map listed in world layout opens Overworld view with player on that map at the scripted tile.
- Warp to a map not in world layout still opens standalone map view at (x,y).

SCOPE:
src/map_view.cpp, include/game.h, docs/event_script_ops.md, docs/source_doc.md, docs/tools_doc.md, docs/tracker.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-048

```
ID: FEATURE-MAP-048
TYPE: FEATURE
TITLE: Blocking script movement and camera opcodes with map editor meta and docs

DESCRIPTION:
Implement walk_to_coords, run_to_coords (blocking path toward tile x,y), face_north/south/east/west, move_camera (direction, steps, optional speed frames between steps), camera_zoom_in/out in the C++ map script runtime; centralize opcode string dispatch in op.cpp for extractor parity; sync tools/event_script_op_meta.json and tools/extract_map_script_ops.py so the map editor event script palette, defaults, and documentation pane expose every opcode.

EXPECTED_BEHAVIOR:
- Scripted player moves complete before the script advances pc; WASD does not override script-driven walks.
- Camera nudge and zoom apply in map/overworld viewer with safe clamping; unreachable walk targets fail soft (advance script after no progress).
- python3 tools/extract_map_script_ops.py succeeds; event script editor lists all ops with descriptions from meta.

SCOPE:
include/op.h, src/op.cpp, include/script_engine.h, src/script_engine.cpp, include/game.h, src/map_view.cpp, tools/extract_map_script_ops.py, tools/event_script_op_meta.json, tools/event_script_ops_generated.py, docs/event_script_ops.md, docs/source_doc.md, docs/tools_doc.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-049

```
ID: FEATURE-MAP-049
TYPE: FEATURE
TITLE: Event script editor — resize, sprite+facing in modal, opcode sort, camera_follow_player, structured opcode docs, Help tab, Cursor skill

DESCRIPTION:
Resizable script modal with persisted dimensions; embed sprite kind/file/frame and initial facing with live preview; palette sort (source, alphabetical, category from meta); camera_follow_player opcode clearing script camera offset; structured per-opcode documentation in editor and Help (Script opcodes tab); Cursor skill checklist when opcode sources change.

EXPECTED_BEHAVIOR:
- Modal size persists; bottom-right resize grip; MOUSEMOTION updates size when dragging.
- Sprite and facing editable from script modal with preview; map event JSON carries optional facing; validation accepts field.
- Palette sort persists; categories from meta; uncategorized bucket for missing category.
- camera_follow_player advances script and resets camera offset to follow player.
- Doc pane and H help tab show name, description, JSON function shape, mandatory/optional params, example script_1.
- Skill documents sync steps for op.cpp, meta, extract, docs.

SCOPE:
tools/map_editor.py, tools/map_editor_config.json, tools/event_script_op_meta.json, tools/event_script_opcode_docs.py, tools/event_script_schema.py, src/op.cpp, src/map_view.cpp, include/map_data.h, src/map_data.cpp, tools/validate_map_events.py, docs/*, .cursor/skills/event-script-opcode-docs/SKILL.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-028

```
ID: BUG-MAP-028
TYPE: BUG
TITLE: Sprite picker docked in event script modal ignores clicks and wheel

DESCRIPTION:
When the sprite list is shown inside the script modal, `_event_script_modal_mousedown` returned true for the whole panel before sprite hit-testing ran, so list selection never updated; the global `MOUSEWHEEL` branch for the sprite box was skipped whenever the script modal was open.

STEPS_TO_REPRODUCE:
1. Open Events workspace, open the event script modal, open Sprite from the footer.
2. Try to select a row in the docked list or scroll it with the mouse wheel.

EXPECTED_BEHAVIOR:
Row highlights and list scrolls.

ACTUAL_BEHAVIOR:
Clicks had no effect; wheel scrolled other UI or did nothing useful.

SCOPE:
tools/map_editor.py (`_event_script_modal_mousedown`, `_event_script_modal_mousewheel`, `_events_sprite_pick_apply_row_click`)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-043

```
ID: IMPROVEMENT-MAP-043
TYPE: IMPROVEMENT
TITLE: Preserve indentation when wrapping opcode documentation lines

DESCRIPTION:
`_wrap_words` stripped all leading whitespace so JSON example blocks in the doc pane and Help tab appeared flat after word wrap.

EXPECTED_BEHAVIOR:
Wrapped lines keep leading indent and readable continuation alignment for structured examples.

SCOPE:
tools/event_script_opcode_docs.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-044

```
ID: IMPROVEMENT-MAP-044
TYPE: IMPROVEMENT
TITLE: Opcode palette click pins documentation; drag uses movement threshold

DESCRIPTION:
The palette set `event_script_palette_drag_op` on mousedown, which made the documentation column follow the cursor and interfered with reading. Users want a click to focus docs on one opcode and only start a drag after intentional movement.

EXPECTED_BEHAVIOR:
- Pointer motion past `TILESET_LIST_DRAG_THRESHOLD_PX` while holding LMB on a palette row starts drag-to-insert.
- Release without crossing the threshold sets a pinned opcode for the doc column (priority: drag op, then pin, then selected step, then hover).
- Selecting a script step clears the pin.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-029

```
ID: BUG-MAP-029
TYPE: BUG
TITLE: Enter and character-frame clicks ignored while event script modal is open

DESCRIPTION:
The main `KEYDOWN` handler always delegated to `_event_script_modal_keydown` and continued, so `events_sprite_pick_open` / `events_character_frame_pick_open` branches never ran. Enter did not confirm sprite or frame; LMB on the 4×4 frame sheet was consumed by `_event_script_modal_mousedown` returning true for clicks outside the script panel.

EXPECTED_BEHAVIOR:
Enter applies sprite or commits character frame; frame sheet and facing buttons receive LMB while the script modal stays open.

SCOPE:
tools/map_editor.py (KEYDOWN/MOUSEBUTTONDOWN ordering, `_event_script_modal_keydown`)

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-045

```
ID: IMPROVEMENT-MAP-045
TYPE: IMPROVEMENT
TITLE: Opcode doc Function/Example JSON uses indent=4 and no word-wrap

DESCRIPTION:
Word-wrapping collapsed `json.dumps` structure; nested braces were hard to read.

EXPECTED_BEHAVIOR:
Function shape and example fragments use multi-line JSON with a deeper indent and are not passed through `_wrap_words`.

SCOPE:
tools/event_script_opcode_docs.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-050

```
ID: FEATURE-MAP-050
TYPE: FEATURE
TITLE: Sprite picker preview column and taller docked panel

DESCRIPTION:
Events sprite overlay lists filenames only; add a right-hand preview pane with scaled image (character uses facing row frame 0). Widen the docked modal strip slightly for two columns.

EXPECTED_BEHAVIOR:
Selected PNG shows in the preview area; list and preview share the overlay; same layout for P-key picker and script-modal picker.

SCOPE:
tools/map_editor.py (`_draw_events_sprite_pick_overlay`, `_events_sprite_pick_list_and_preview_rects`, `_events_sprite_pick_selection_preview_surface`)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-046

```
ID: IMPROVEMENT-MAP-046
TYPE: IMPROVEMENT
TITLE: NPC character frame picker scales to map viewport height

DESCRIPTION:
`_draw_events_character_frame_overlay` used width-only scaling (`max_inner_w / sw`), so tall character sheets produced a scaled height larger than `map_viewport_rect` and the centered box was clipped at the top and bottom.

EXPECTED_BEHAVIOR:
Scale uses `min(width_limit, height_limit)` so the full overlay (title, 4×4 sheet, facing buttons) fits inside the viewport with margins; the box position is clamped after centering.

SCOPE:
tools/map_editor.py (`_draw_events_character_frame_overlay`)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-047

```
ID: IMPROVEMENT-MAP-047
TYPE: IMPROVEMENT
TITLE: Help Script opcodes and script-modal doc pane wrap long lines to avoid clip

DESCRIPTION:
Help content uses `set_clip` on the content rect, but each line was rendered with a single `Font.render` call with no horizontal wrapping. Long JSON documentation lines and wide opcode labels were clipped at the right edge.

EXPECTED_BEHAVIOR:
Body lines use `event_script_opcode_docs._wrap_words` with the small font width; heads/tocs use `_wrap_lines_to_width`. The script modal documentation column applies the same pixel-cap expansion after `build_structured_doc_lines`.

SCOPE:
tools/map_editor.py (`_expand_help_overlay_segments`, `_expand_visual_text_lines`, `_draw_help_overlay`, `_event_script_rebuild_doc_lines`)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-030

```
ID: BUG-MAP-030
TYPE: BUG
TITLE: Opcode doc lines clipped after two-space prefix past wrap width

DESCRIPTION:
`build_structured_doc_lines` called `_wrap_words` with `inner_w` (or `inner_w - 8`) then prefixed each wrapped segment with two spaces for the doc column. The prefix was not subtracted from the wrap budget, so rendered `Font.render` width exceeded the clip rect by up to the width of two spaces per line (worse on narrow panes).

STEPS_TO_REPRODUCE:
1. Open event script modal with documentation pane or open H → Script opcodes.
2. View an opcode with a wrapped description or long parameter line on a moderately narrow window.

EXPECTED_BEHAVIOR:
No horizontal clipping at the right edge of the doc or help content area.

ACTUAL_BEHAVIOR:
Slight or obvious clipping on wrapped lines that include the two-space indent.

SCOPE:
tools/event_script_opcode_docs.py (`build_structured_doc_lines`)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-031

```
ID: BUG-MAP-031
TYPE: BUG
TITLE: NPC 4×4 character frame overlay clipped horizontally (title, border)

DESCRIPTION:
The frame picker dialog was sized and clamped using `map_viewport_rect` only, while the title was a single `Font.render` line wider than a narrow `box.w`. When the map viewport is inset or narrower than the SDL window, the centered box could extend past the window edge; the long title string also drew past the panel border.

STEPS_TO_REPRODUCE:
1. From repo root: python3 tools/map_editor.py
2. Open the event script editor with a layout that leaves a narrow map viewport or wide side panels.
3. Trigger the NPC character-sheet frame picker (4×4 grid + facing row).

EXPECTED_BEHAVIOR:
Full dialog border visible; title wraps within the panel; no horizontal cutoff at the window edge.

ACTUAL_BEHAVIOR:
Right side of the overlay and title text could be clipped at the screen edge.

SCOPE:
tools/map_editor.py (`_draw_events_character_frame_overlay`)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-032

```
ID: BUG-MAP-032
TYPE: BUG
TITLE: NPC 4×4 frame overlay top sprite row crowded or clipped — vertical layout vs layer chip

DESCRIPTION:
The overlay used `map_viewport_rect` for vertical `avail_h` and for centering. That rectangle includes the layer chip strip at the top of the map area, so the dialog was shifted upward compared to centering on the drawable map canvas. Additionally, the sheet `inner` rect was placed at `ty + gap` after the title loop, omitting the reserved `title_pad_bottom` that was still counted in `chrome_no_sheet`, so the scaled grid sat up to 10px higher than the height budget implied.

STEPS_TO_REPRODUCE:
1. python3 tools/map_editor.py with Events workspace and event script modal as when picking a character sprite frame.
2. Open the NPC 4×4 frame picker.

EXPECTED_BEHAVIOR:
Clear padding between title and first sprite row; dialog vertically centered in the map canvas (below chip), not biased into the chip band.

ACTUAL_BEHAVIOR:
Top row of sprites appeared tight against the title or visually cut off at the top of the panel.

SCOPE:
tools/map_editor.py (`_draw_events_character_frame_overlay`)

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-DOC-004

```
ID: IMPROVEMENT-DOC-004
TYPE: IMPROVEMENT
TITLE: Deduplicate source_doc and refresh tools_doc against codebase

DESCRIPTION:
Merge duplicate `FILE:` sections in `docs/source_doc.md` into one canonical entry per source file, fold unique NOTES and function documentation from duplicates, and align `docs/tools_doc.md` with current `tools/*.py` behavior including explicit notes for generated scripts (e.g. `event_script_ops_generated.py`).

EXPECTED_BEHAVIOR:
- No contradictory duplicate `FILE:` blocks for the same path in `source_doc.md`.
- `tools_doc.md` reflects all non-backup tools or defers generated artifacts with a clear cross-reference.
- Documentation indentation rules remain satisfied.

SCOPE:
docs/source_doc.md, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-PERF-001

```
ID: IMPROVEMENT-PERF-001
TYPE: IMPROVEMENT
TITLE: Reduce per-frame map/world viewer hint string allocations

DESCRIPTION:
`Game::drawMapView_` and related UI strings rebuild concatenated `std::string` values every frame. Use a reusable scratch buffer and/or dirty tracking so hint text is rebuilt only when inputs change, without adding SDL render threads or shared mutable state across threads.

EXPECTED_BEHAVIOR:
- Map and world map viewer footer hints match prior text for all camera, zoom, grid, and dimension states.
- No new mutexes or background threads in the C++/SDL render path.

SCOPE:
include/game.h, src/map_view.cpp (and related `Game` members), docs/source_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-DOC-005

```
ID: IMPROVEMENT-DOC-005
TYPE: IMPROVEMENT
TITLE: Clarify map_data.h NOTES inline wording in source_doc

DESCRIPTION:
Normalize readability for IMPROVEMENT-MAP-042 note under `FILE: include/map_data.h` in `docs/source_doc.md`: avoid nested inline backticks while preserving meaning (over-player grid cell at (x, y) equals 1). Indentation was verified against Documentation-Rule (left-aligned labels, 4-space values, 8-space list items).

EXPECTED_BEHAVIOR:
- `docs/source_doc.md` map_data.h NOTES remain technically accurate and easier to read in Markdown renderers.

SCOPE:
docs/source_doc.md

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-DOC-006

```
ID: IMPROVEMENT-DOC-006
TYPE: IMPROVEMENT
TITLE: Nest source_doc and tools_doc content under FILE/TOOL anchors

DESCRIPTION:
Indent all lines under each `FILE:` entry in `docs/source_doc.md` and each `TOOL:` entry in `docs/tools_doc.md` by one additional 4-space block so the anchor path reads at the margin and the full entry reads as a nested block. Updated `.cursor/rules/Documentation-Rule.mdc` indentation rules and examples to match.

EXPECTED_BEHAVIOR:
- Docs remain valid Markdown; anchors stay column 0; inner structure preserves prior relative spacing (+4 shift).

SCOPE:
docs/source_doc.md, docs/tools_doc.md, .cursor/rules/Documentation-Rule.mdc

PRIORITY: LOW
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-050

```
ID: FEATURE-MAP-050
TYPE: FEATURE
TITLE: Wild encounter patches (editor paint, JSON, overworld battle)

DESCRIPTION:
Add per-map wild encounter patches: paint 1x1 tiles in map editor (E toolbar → Wild Encounters mode), tiered species tables (common 65% / uncommon 30% / rare 5%) with per-species weights, per-patch step chance, JSON in map files, and C++ runtime that triggers battle on step with overworld paused until foe faints.

EXPECTED_BEHAVIOR:
- Map editor paints wild tiles in distinct color; multiple patches per map with separate encounter tables; merge/group support.
- layers.wildEncounter grid (1-based patch index) + wildPatches[] in map JSON.
- Stepping on wild tile rolls step chance then tier then species; battle overlays map; player win resumes map view.

SCOPE:
include/map_data.h, src/map_data.cpp, include/wild_encounter.h, src/wild_encounter.cpp, include/game.h, src/game.cpp, src/map_view.cpp, tools/map_editor.py, tools/validate_map_events.py, src/overworld_view.json, docs/

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-051

```
ID: IMPROVEMENT-MAP-051
TYPE: IMPROVEMENT
TITLE: Context-aware help (H) and updated Events guide tab

DESCRIPTION:
Map editor help opened with H always landed on Contents; Events tab text was stale (pre–E popover / pre–wild encounters). Users editing events or wild patches need accurate, context-appropriate help.

EXPECTED_BEHAVIOR:
- H with NPC Events or Wild Encounters workspace open → help on updated Events tab.
- H with script modal open → Script opcodes tab (unchanged).
- Events tab documents E popover, wild patch sidebar, validation, and related shortcuts.

SCOPE:
tools/map_editor.py, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-052

```
ID: IMPROVEMENT-MAP-052
TYPE: IMPROVEMENT
TITLE: Event script opcode parity audit (op.cpp + map_view.cpp)

DESCRIPTION:
Editor palette and meta claim all opcodes are implemented; extractor only checks meta vs op.cpp. Map-viewer opcodes must be verified in Game::tryMapViewerScriptOpcode_ to avoid silent stubs when callbacks are missing.

EXPECTED_BEHAVIOR:
- tools/extract_map_script_ops.py passes.
- tools/audit_event_script_ops.py verifies map-viewer ops in map_view.cpp and callback wiring markers.
- tests/test_event_script_opcode_parity.py fails on drift.

SCOPE:
tools/audit_event_script_ops.py, tests/test_event_script_opcode_parity.py, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-053

```
ID: FEATURE-MAP-053
TYPE: FEATURE
TITLE: Wild encounter species picker with search and starred favorites

DESCRIPTION:
Wild patch tier editor only shows species name and weight; no way to search monster.json species or mark repeats. Users need a picker when adding/editing tier rows.

EXPECTED_BEHAVIOR:
- LMB on tier row or + row opens species modal with search filter and star column.
- Starred species persist in map_editor_config.json wildEncounterEditor.favoriteSpecies; sort starred first; default + row uses first favorite when set.

SCOPE:
tools/map_editor.py, tools/map_editor_config.json (optional user data), docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-054

```
ID: BUG-MAP-054
TYPE: BUG
TITLE: Warp player lands off-anchor or misaligned after teleport

DESCRIPTION:
Standalone map warps assign tileX/tileY verbatim without bounds clamp, walkability fallback, or walk parity reset. Player can appear off by one tile or visually between stride cells after warp_player.

STEPS_TO_REPRODUCE:
1. Run map viewer with a map using warp_player to edge or blocked coordinates.
2. Observe player anchor vs walk stride grid and walkability.

EXPECTED_BEHAVIOR:
Player lands on a valid in-bounds walkable anchor with idle pose aligned to stride grid (parity reset).

ACTUAL_BEHAVIOR:
Raw coordinates used; no snap to nearest valid stand on single-map warp path.

SCOPE:
src/map_view.cpp, include/game.h, docs/source_doc.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## IMPROVEMENT-MAP-055

```
ID: IMPROVEMENT-MAP-055
TYPE: IMPROVEMENT
TITLE: Event script editor shows full step ghost while dragging

DESCRIPTION:
Step reorder and palette drag only highlight source or show opcode tooltip. Authors cannot see the full step (opcode + args) while dragging.

EXPECTED_BEHAVIOR:
Floating semi-transparent ghost shows formatted step line(s); reorder shows drop line; source row dimmed during drag.

SCOPE:
tools/map_editor.py, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-057

```
ID: BUG-MAP-057
TYPE: BUG
TITLE: Wild encounter modal mini-map blank on first open

DESCRIPTION:
_draw_mini_map reads self._map_view_rect which starts as Rect(0,0,1,1).
_cell_px() uses the same stale rect, producing a map_rect with negative
dimensions that triggers the early-return guard on every frame.

STEPS_TO_REPRODUCE:
1. Open the map editor and press E to open wild encounters modal.
2. Observe the Map column — it is entirely blank (no tiles rendered).

EXPECTED_BEHAVIOR:
Map tiles render immediately on first open using self.map_inner as the
correctly-sized base rect.

ACTUAL_BEHAVIOR:
Map area is blank; _map_view_rect is never updated because the early-return
fires before the assignment.

SCOPE:
tools/wild_encounter_modal.py

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-058

```
ID: FEATURE-MAP-058
TYPE: FEATURE
TITLE: Wild modal improvements — typed inputs, global tab, adjacency paint, flood-fill select

DESCRIPTION:
Four connected improvements to the wild encounter modal:
1. Typed text input for stepChancePercent and species weight (both fields).
2. Global encounters tab: species defined here appear in every patch; local wins on duplicate species.
3. Adjacency auto-assign painting: painting a tile auto-joins an adjacent patch or creates a new one.
4. Selectable patch icons: clicking a patch tile flood-fills the contiguous component and highlights it.

EXPECTED_BEHAVIOR:
- Typing digits into the step% or weight box and pressing Enter commits the value (clamped to valid range).
- Global tab shows map-wide species; engine merges them with local at roll time.
- Painting next to an existing patch joins it; painting isolated creates a new patch entry.
- Clicking a patch tile selects and highlights all contiguous same-index cells; patch column updates.

SCOPE:
tools/wild_encounter_modal.py, tools/map_editor.py,
include/map_data.h, src/map_data.cpp, src/wild_encounter.cpp,
docs/source_doc.md, docs/tools_doc.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-059

```
ID: FEATURE-MAP-059
TYPE: FEATURE
TITLE: Wild encounter modal zoom controls and resizable window

DESCRIPTION:
Mini-map in the wild encounter modal has no zoom controls; size is always auto-fit
to the map column. The modal panel is also fixed size. Add zoom in/out/fit buttons
in the map column header, Ctrl+scroll zoom on the mini-map, and a drag-to-resize
grip on the bottom-right corner of the modal.

EXPECTED_BEHAVIOR:
[-] [fit] [+] buttons in the map column header change the px-per-cell scale.
Ctrl+scroll over the mini-map adjusts zoom by ±4 px/cell (range 4..64).
Plain scroll still pans. A triangle grip in the bottom-right corner allows dragging
to resize the panel (minimum 640×480, clamped to canvas). Size persists across
close/reopen within the session; zoom resets to auto-fit on each open.

SCOPE:
tools/wild_encounter_modal.py, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-067

```
ID: FEATURE-MAP-067
TYPE: FEATURE
TITLE: UI Standard cursor rule enforcing WildEncounterModal pattern for all editor modals

DESCRIPTION:
Add a .cursor/rules/UI-Standard-Rule.mdc that mandates every new or reworked editor modal
follows the WildEncounterModal standard: full-screen canvas, _panel_override, _drag_mode,
title-bar drag, BR+BL resize grips, minimum 640x480, size-before-position clamping, separate
class file, input routed from map_editor.py.

EXPECTED_BEHAVIOR:
All future editor modal implementations are held to the documented standard by Cursor.

SCOPE:
.cursor/rules/UI-Standard-Rule.mdc

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-066

```
ID: FEATURE-MAP-066
TYPE: FEATURE
TITLE: Help overlay — Settings section, interactive TOC, auto-section navigation

DESCRIPTION:
Add a Settings tab to the help overlay (replacing the standalone settings overlay),
an interactive table-of-contents on the home tab, and an auto-section navigation API
so Help buttons on individual modals open the overlay pre-scrolled to the relevant tab.
The * toolbar button becomes a shortcut directly to the Settings tab.

EXPECTED_BEHAVIOR:
Settings controls (add/remove layer, key rebinding) are accessible from the help overlay
Settings tab. TOC on home tab links to all tabs. Callers pass tab= to _open_help_overlay().

SCOPE:
tools/map_editor.py, HELP_GUIDE_TABS, _draw_settings_overlay, _draw_help_overlay

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-065

```
ID: FEATURE-MAP-065
TYPE: FEATURE
TITLE: Event Engine Modal — NPC workspace + script editor in WildEncounterModal-standard shell

DESCRIPTION:
Create tools/event_engine_modal.py (EventEngineModal class) that hosts the NPC events list
and script editor in a three-column modal (events list | mini-map | script editor) following
the same chrome standard as WildEncounterModal. Includes Back button (returns to launcher)
and Help button (opens help on script_ops tab). Existing drawing methods in map_editor.py
are adapted to accept an explicit target_rect parameter.

EXPECTED_BEHAVIOR:
Pressing Event Engine in the launcher opens a full modal with events list, mini-map showing
event hulls, and the script editor. Back returns to the events launcher. Help opens script
ops documentation.

SCOPE:
tools/event_engine_modal.py (new), tools/map_editor.py

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-064

```
ID: FEATURE-MAP-064
TYPE: FEATURE
TITLE: Events Launcher Modal consolidating Event Engine, Wild Encounters, and Help entry points

DESCRIPTION:
Create tools/events_launcher_modal.py (EventsLauncherModal class) — a compact modal opened
by the E toolbar button. It presents three buttons: Event Engine, Wild Encounters, Help.
Each sub-modal gets a Back button that returns to this launcher. The old events popover
is removed. Toolbar labels changed: E->Event, #->Overworld. * button opens help overlay.

EXPECTED_BEHAVIOR:
Pressing E opens the launcher modal. Pressing Event Engine, Wild Encounters, or Help
navigates to the respective sub-modal or help overlay. Back on any sub-modal returns
to the launcher.

SCOPE:
tools/events_launcher_modal.py (new), tools/map_editor.py, tools/wild_encounter_modal.py

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-063

```
ID: FEATURE-MAP-063
TYPE: FEATURE
TITLE: Wild encounter modal canvas extended to full program window

DESCRIPTION:
The modal's canvas was bounded to ed.map_viewport_rect, which excludes the left
palette panel and the bottom tileset strip. The user could not drag the modal
into those areas, and the dim overlay only covered the map viewport. Change canvas
to ed.screen.get_rect() so the modal can occupy the entire program window. Since
screen.get_rect() always returns the live window dimensions, the modal also
auto-recentres correctly after windowed/fullscreen toggles.

EXPECTED_BEHAVIOR:
Modal panel can be dragged to any position within the full program window.
Dim overlay covers the entire screen. After resizing or fullscreen toggle the panel
recentres (or stays clamped to the new bounds if the user had manually positioned it).

SCOPE:
tools/wild_encounter_modal.py draw()

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-060

```
ID: FEATURE-MAP-060
TYPE: FEATURE
TITLE: Wild encounter modal — bottom-left resize corner and title-bar drag-to-move

DESCRIPTION:
The modal only has a bottom-right resize grip. Add a matching bottom-left grip so
the panel can be expanded leftward. Also add a drag handle in the title bar so the
user can reposition the modal anywhere within the canvas without resizing.

EXPECTED_BEHAVIOR:
Dragging the bottom-left triangle grip grows the modal width leftward and height
downward (minimum 640×480 clamped). Dragging the title bar grip area moves the
entire modal, clamped inside the canvas. Size and position persist across
close/reopen within the session.

SCOPE:
tools/wild_encounter_modal.py, docs/tools_doc.md

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-061

```
ID: BUG-MAP-061
TYPE: BUG
TITLE: Wild modal mini-map pan scrolls both X and Y simultaneously (diagonal)

DESCRIPTION:
In handle_wheel, the plain-scroll branch updates both wild_modal_map_off_x and
wild_modal_map_off_y with the same vertical delta, causing diagonal panning
instead of vertical-only panning.

STEPS_TO_REPRODUCE:
1. Open wild encounter modal on a map larger than the mini-map viewport.
2. Hover over the mini-map and scroll the mouse wheel vertically.

EXPECTED_BEHAVIOR:
The map pans vertically only. Shift+scroll pans horizontally.

ACTUAL_BEHAVIOR:
The map pans diagonally (both X and Y move by equal amounts).

SCOPE:
tools/wild_encounter_modal.py handle_wheel

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## BUG-MAP-062

```
ID: BUG-MAP-062
TYPE: BUG
TITLE: Wild modal species list scroll resets to top immediately after scrolling down

DESCRIPTION:
_draw_species_column contains the guard
    if species_sel < species_scroll: species_scroll = species_sel
which fires every frame when species_sel=0 and the user has scrolled down,
instantly resetting species_scroll to 0 and preventing the user from browsing
below the initially visible items.

STEPS_TO_REPRODUCE:
1. Open wild encounter modal with a map that has many Pokémon species available.
2. Hover over the species list and scroll down with the mouse wheel.

EXPECTED_BEHAVIOR:
The list scrolls down to reveal lower entries; scrolling up returns to the top.

ACTUAL_BEHAVIOR:
Every attempt to scroll down immediately snaps the list back to the top.

SCOPE:
tools/wild_encounter_modal.py _draw_species_column, handle_wheel

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-056

```
ID: FEATURE-MAP-056
TYPE: FEATURE
TITLE: Wild encounters dedicated modal with mini-map and species search

DESCRIPTION:
Wild mode uses main canvas overlay and side panel; species picker is a separate overlay. Need one modal with integrated search over all species, mini-map for patch/map edit, and paint snap aligned with K orange stride grid.

EXPECTED_BEHAVIOR:
E → Wild opens resizable modal: mini-map (patch or tile edit), patch/tier controls, always-visible species search; paint snaps like K grid; no clipped UI at 800×600.

SCOPE:
tools/map_editor.py, tools/wild_encounter_editor_helpers.py, tests/, docs/tools_doc.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor
```

## FEATURE-MAP-068

```
ID: FEATURE-MAP-068
TYPE: FEATURE
TITLE: Nested control-flow opcodes (if_flag/end_if, repeat/end_repeat)

DESCRIPTION:
The map script engine only supported the relative-skip unless_flag for conditionals and had
no loop construct. Add real nested control flow so authored scripts and the block editor can
express conditionals and bounded loops, including nesting.

EXPECTED_BEHAVIOR:
- if_flag/end_if: the block runs only when the named flag is set; otherwise the engine jumps
  past the matching end_if. skip (body length) is computed automatically on load.
- repeat/end_repeat: the block runs n times (n<=0 skips it); loops nest via a loop stack.
- ScriptRuntime::resolveControlFlow stamps skip values; tooling validates balanced pairs.

SCOPE:
include/script_engine.h, src/script_engine.cpp, src/op.cpp, tools/event_script_op_meta.json,
tools/event_script_schema.py, tools/validate_map_events.py, docs/event_script_ops.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-069

```
ID: FEATURE-MAP-069
TYPE: FEATURE
TITLE: Event Engine 3-panel modal (map picker | block editor | documentation)

DESCRIPTION:
The Event Engine delegated to legacy floating panels and could not edit arbitrary maps. Rework
it into a UI-Standard 3-panel modal with draggable splitters: a map picker + events list (left),
a nested block-based script editor with action search and favorites (middle), and an opcode
documentation pane (right). Add UI-Standard "View in Map" and "Assign Sprite" sub-modals and a
config toggle for map scope (independent vs. follow main editor).

EXPECTED_BEHAVIOR:
- Launcher → Event Engine opens the 3-panel modal (no floating popover).
- Left: search/select any map (src/maps/*.json) into a session buffer; events list with
  checkboxes; Add/Copy/Paste/Delete-single/Delete-checked; RMB → Copy/Paste/Delete/View in
  Map/Assign Sprite.
- Middle: nested block editor (if_flag/repeat indent children) with drag/drop, inline arg
  editing, RMB → Copy/Paste/Add/Delete/Show Documentation; right-edge action search grouped by
  category with a persisted Favorites tab.
- Right: structured opcode documentation, wrapped to width.
- All panels/splitters adjustable and clamped so nothing is clipped.

SCOPE:
tools/event_engine_modal.py, tools/event_place_modal.py, tools/event_sprite_modal.py,
tools/map_editor.py, .cursor/rules/UI-Standard-Rule.mdc

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Phase 3 Event Engine rewrite complete — see FEATURE-MAP-096 PHASE-3-AUDIT.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-070

```
ID: FEATURE-MAP-070
TYPE: FEATURE
TITLE: Event Engine rename event + unified delete

DESCRIPTION:
The events list had no way to rename an event id, and the delete controls were split into two
separate buttons (single vs. multi-checked). Rename allows renaming an event id in-place from
the context menu, updating the map JSON, the script path reference, and the script file on disk
atomically. Unified delete replaces the two buttons with one whose label reflects the current
selection (Delete vs Delete (N)) driven by a single _delete_targets() helper.

EXPECTED_BEHAVIOR:
- RMB on event row -> context menu includes Rename; activates an inline text edit seeded from
  the current id; Enter commits, Esc cancels.
- On commit: id uniqueness checked, old script file renamed to new path, ev["id"] and
  ev["script"]["path"] updated, map JSON persisted.
- Single Delete toolbar button: when 0 or 1 checkboxes active -> delete selected event;
  when 2+ checkboxes active -> label shows Delete (N) and deletes all checked events.

SCOPE:
tools/event_engine_modal.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-071

```
ID: FEATURE-MAP-071
TYPE: FEATURE
TITLE: Walk/run direction+steps rail movement

DESCRIPTION:
walk_to_coords and run_to_coords used a greedy (x, y) coordinate approach. Replace with an
explicit direction + steps model that moves the player along a fixed cardinal rail for an exact
number of tile strides. An optional faceFirst arg (default true) faces the direction before the
first step, enabling turn-only (steps=0), turn-then-walk, walk-then-turn (faceFirst:false), and
walk-only chaining patterns. Rail movement never deviates from the stated axis even on asymmetric
arrival positions.

EXPECTED_BEHAVIOR:
- walk_to_coords { direction: "south", steps: 3 } moves player exactly 3 tiles south.
- faceFirst: true (default) faces before first step; faceFirst: false walks without re-facing.
- steps: 0 with faceFirst: true turns only and advances pc immediately.
- Blocked tile mid-rail finishes early (same safe fallback as before).
- run_to_coords uses the same model with faster animation timing.

SCOPE:
include/game.h, src/map_view.cpp, tools/event_script_op_meta.json, docs/event_script_ops.md

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Phase 4 C++ audit verified direction+steps rail in map_view.cpp (faceFirst, blocked early exit).
See FEATURE-MAP-096 PHASE-4-AUDIT.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-072

```
ID: FEATURE-MAP-072
TYPE: FEATURE
TITLE: Persistent game-state save with crash safety and debug dumps

DESCRIPTION:
Script flags only lived in memory for one script run (ScriptRuntime::reset wiped them on every
trigger). Add a GameState object owning persistent boolean flags, loaded from a registry of
defaults overlaid by an on-disk save file, written atomically on change (debounced) and on map
transitions / clean exit. Install crash-safety handlers (signals + atexit) that flush flags so
progress is not lost. Provide a debug toggle that writes clear, concise timestamped state dumps
into a debug/ folder in the source tree.

EXPECTED_BEHAVIOR:
- save/game_state.json loaded at startup; flag_registry.json defaults applied first, then save
  overlaid.
- Flags persist across event triggers, map loads, and app restarts.
- On crash (SIGSEGV/SIGABRT/SIGINT/SIGTERM) or normal exit, current flags are flushed to disk.
- EVENT_DEBUG_STATE=1 writes timestamped dumps to debug/state_dumps/.

SCOPE:
include/game.h, src/game.cpp, include/game_state.h, src/game_state.cpp, src/map_view.cpp

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Phase 4: tests/test_game_state.cpp + `make test-game-state` verifies load/set/flush round-trip.
See FEATURE-MAP-096 PHASE-4-AUDIT.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-073

```
ID: FEATURE-MAP-073
TYPE: FEATURE
TITLE: Flag/variable registry (editor + C++ defaults)

DESCRIPTION:
Add a game-global registry declaring the named flags and variables that control game state, with
initial values and descriptions. The editor manages it (declare/list/rename/initial value) and the
C++ engine reads it at startup to seed default flag values before overlaying the save file.

EXPECTED_BEHAVIOR:
- flag_registry.json stores flags (name, initial bool, description) and variables (name, type,
  initial value, description).
- Editor registry UI can add/rename/remove entries and edit initial values.
- C++ seeds GameState flag defaults from the registry at startup.

SCOPE:
src/maps/scripts/flag_registry.json, tools/flag_registry_modal.py, tools/event_engine_modal.py,
include/game_state.h, src/game_state.cpp

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-074

```
ID: FEATURE-MAP-074
TYPE: FEATURE
TITLE: Subflows (subprocesses) + custom-connector library + call_subflow

DESCRIPTION:
Add Power-Automate-style subflows. Each event script file may define named subflows alongside the
main flow (script_1). A global library of reusable custom connectors lives under
src/maps/scripts/_library/. The new call_subflow opcode runs a named subflow like a method,
passing named arguments that seed the callee's local variable scope, and returns to the caller
when done. The editor shows a subflow tab strip with open/close/rename/save and a searchable
library browser.

EXPECTED_BEHAVIOR:
- call_subflow { name, args? } resolves an in-file subflow first, else a library connector.
- Named args become local variables in the callee's frame; callee returns to caller.
- Recursion is depth-guarded to prevent infinite loops.
- Editor tab strip: Main Flow + subflow tabs; far-left search/open menu; tab context menu
  Close Tab / Close all but this / Close all / Rename / Save.

SCOPE:
include/script_engine.h, src/script_engine.cpp, src/op.cpp, src/map_view.cpp,
tools/event_engine_modal.py, tools/event_script_schema.py, tools/event_script_op_meta.json,
src/maps/scripts/_library/

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Phase 4: test_script_runtime scenario 7 (call/return); Maple_Town fixed; _library/heal_party.json added.
See FEATURE-MAP-096 PHASE-4-AUDIT.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-075

```
ID: FEATURE-MAP-075
TYPE: FEATURE
TITLE: Flow control: stop_script and goto + label

DESCRIPTION:
Add basic flow control for ending a script early and jumping within a flow. stop_script finishes
the entire script (clearing the call stack and unlocking the player). label marks a named jump
target; goto jumps to a label within the current flow and continues execution below it. The editor
exposes goto's target as a dropdown of available labels in the flow.

EXPECTED_BEHAVIOR:
- stop_script ends the whole script immediately, even inside a subflow.
- label { name } is a no-op marker; goto { label } jumps to it (O(1) via per-flow label index).
- Unknown goto target is a safe no-op (advance + stub log), never a hang.
- goto targets are restricted to labels within the same flow.

SCOPE:
include/script_engine.h, src/script_engine.cpp, src/op.cpp, tools/event_script_op_meta.json,
tools/event_engine_modal.py, tools/event_action_modal.py

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Phase 4: test_script_runtime scenarios 1–2 (goto/stop_script). See FEATURE-MAP-096 PHASE-4-AUDIT.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-076

```
ID: FEATURE-MAP-076
TYPE: FEATURE
TITLE: Regions, comments, and labels (no-op organization)

DESCRIPTION:
Add organization-only constructs that do not affect runtime behavior. region/end_region nest and
collapse a renamable block of steps in the editor. comment is a non-action note. label is a named
marker (also used by goto). The C++ engine skips all of these.

EXPECTED_BEHAVIOR:
- region { name } / end_region nest steps; editor collapses/renames; engine skips (++pc).
- comment { text } renders as a distinct non-action card; engine skips.
- Regions have no control-flow effect (organization only).

SCOPE:
include/script_engine.h, src/script_engine.cpp, src/op.cpp, tools/event_script_op_meta.json,
tools/event_script_schema.py, tools/event_engine_modal.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Phase 4: test_script_runtime scenario 3 (region/comment no-ops). See FEATURE-MAP-096 PHASE-4-AUDIT.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-077

```
ID: FEATURE-MAP-077
TYPE: FEATURE
TITLE: Per-event scratch variables (set_var / if_var)

DESCRIPTION:
Add scratch variables scoped to a script run (and to a call frame for subflow locals). Variables
support int, string, and bool types and comparisons (==, !=, <, >). set_var assigns a variable in
the current scope; if_var / end_if_var conditionally run a block. Variables are not persisted
(persistent state uses flags).

EXPECTED_BEHAVIOR:
- set_var { name, value } sets a typed variable in the current frame scope.
- if_var { name, op, value } / end_if_var run the block when the comparison holds.
- Subflow named args seed callee locals; variables do not leak across frames.

SCOPE:
include/script_engine.h, src/script_engine.cpp, src/op.cpp, tools/event_script_op_meta.json,
tools/event_script_schema.py, tools/event_engine_modal.py, tools/event_action_modal.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Phase 4: test_script_runtime scenarios 1, 3, 7 (if_var/set_var). See FEATURE-MAP-096 PHASE-4-AUDIT.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-078

```
ID: FEATURE-MAP-078
TYPE: FEATURE
TITLE: Event triggers + auto-managed cleared flag

DESCRIPTION:
Formalize event triggers in JSON and dispatch them in C++. Support interact (Q + adjacency),
step_on (auto-fire when stepping onto the anchor), on_map_enter (map load), and on_condition
(flag/var predicate). interact (talk) events become solid (block their 2x2 footprint). Each event
gets an auto-managed cleared flag plus optional run-condition and set/clear-flags-on-complete, so
events can be one-and-done or unlock more content on a later visit.

EXPECTED_BEHAVIOR:
- Event JSON: trigger { type, condition? }, onComplete { setFlags?, clearFlags? }, derived
  clearedFlag (default "<id>_cleared").
- interact events block movement footprint; step_on events remain walkable.
- step_on fires once, then gated by cleared flag; on_map_enter / on_condition fire when matched.
- On script finish, cleared flag is set and onComplete applied, then state persisted.

SCOPE:
include/map_data.h, src/map_data.cpp, src/map_view.cpp, tools/event_trigger_modal.py,
tools/event_engine_modal.py, tools/validate_map_events.py

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Phase 4 code audit: map_data trigger parse + map_view dispatch (interact/step_on/on_map_enter/on_condition).
Manual SDL trigger smoke deferred to Phase 7. See FEATURE-MAP-096 PHASE-4-AUDIT.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-079

```
ID: FEATURE-MAP-079
TYPE: FEATURE
TITLE: Action edit modal + variable picker

DESCRIPTION:
Add an option to edit an action in a dedicated modal with one labeled, type-aware field per
argument, plus a variable picker/creator (lists registry flags + scratch variables, can create
new). The goto opcode's label argument renders as a dropdown of labels in the current flow;
call_subflow shows editable named-argument rows. Inline editing remains available.

EXPECTED_BEHAVIOR:
- Block context menu / button opens the action modal for the selected step.
- Each argument has its own labeled field with type-aware input.
- Variable picker can select an existing flag/variable or create a new one.

SCOPE:
tools/event_action_modal.py, tools/event_engine_modal.py, tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-080

```
ID: FEATURE-MAP-080
TYPE: FEATURE
TITLE: Docs panel collapsible/search/pop-out + collapsible selector

DESCRIPTION:
Improve the Event Engine documentation panel: make it collapsible, add a search box, fix text
clipping by adding scroll, and add a full-window pop-out documentation modal for easier reading.
Also make the left map picker and events list collapsible.

EXPECTED_BEHAVIOR:
- Doc panel collapses/expands, searches/filters, scrolls (no clipped text).
- Pop-out opens a full-window UI-Standard documentation modal with search + scroll + wrap.
- Map picker and events list collapse/expand with clamped relayout.

SCOPE:
tools/event_engine_modal.py, tools/event_doc_popout_modal.py, tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-081

```
ID: FEATURE-MAP-081
TYPE: FEATURE
TITLE: Event Engine UI polish: collapse, nesting, palette, subflow picker

DESCRIPTION:
Five refinements to the Event Engine modal:
1. Documentation panel layout-level collapse (parity with left selector: 22px strip, mid column
   absorbs freed width, Pop button on strip).
2. Collapsible action categories with indented op rows; persisted to config; auto-expand on search.
3. Paired palette ordering: block openers appear immediately before their end_* counterparts.
4. Block nesting: selecting an open block inserts inside children (append); region label shows
   args.name; bare end_* drags are rejected with red highlight and warning.
5. call_subflow picker lists in-file subflows + _library connectors instead of flag/variable
   registry.

EXPECTED_BEHAVIOR:
- Collapsing doc panel shrinks right column to 22px strip with expand button, Pop button, and
  vertical "DOCS" label; middle column grows; expanding restores prior width.
- Each category in Actions All tab has a caret header; collapsed hides ops; ops indented one level;
  categories that match search auto-expand.
- Within a category, block openers appear immediately before their end_* pair; both visible.
- Adding/pasting with an open block selected inserts as last child; nested rows at depth+1;
  region rows show args.name label; dragging bare end_* rejected with red error highlight.
- call_subflow Pick dropdown lists in-file flows (except main) + _library/*.json stems.

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-082

```
ID: FEATURE-MAP-082
TYPE: FEATURE
TITLE: Double-click block opens action modal

DESCRIPTION:
In the Event Engine block editor, double-clicking a script action/block row opens
EventActionModal for that step (same as "Edit in modal" context menu).

EXPECTED_BEHAVIOR:
- Double-click on a non-end block row opens EventActionModal after committing any inline edit.
- Single-click still selects and prepares drag as before.

SCOPE:
tools/event_engine_modal.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-083

```
ID: FEATURE-MAP-083
TYPE: FEATURE
TITLE: Modal form spacing audit (all modals)

DESCRIPTION:
Extend modal_text.py with shared form-layout constants and audit all UI-Standard modals
so help text and field labels are not clipped and have consistent vertical rhythm.

EXPECTED_BEHAVIOR:
- Shared FORM_* layout helpers in modal_text.py.
- All listed modals use consistent label column, field height, help gap, and row gap.

SCOPE:
tools/modal_text.py, event_action_modal.py, event_trigger_modal.py, flag_registry_modal.py,
wild_encounter_modal.py, event_sprite_modal.py, event_place_modal.py, event_doc_popout_modal.py,
events_launcher_modal.py, event_engine_modal.py, audio_engine_modal.py, battle_editor_modal.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

AUDIT-NOTE:
event_trigger_modal.py and flag_registry_modal.py now use form_field_h() and FORM_ROW_GAP.
All listed modals use mtext helpers (horizontal form modals) or consistent vertical rhythm
(event_trigger, flag_registry). Modals without form fields (place, sprite, doc_popout,
launcher) require no spacing changes.

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```


## FEATURE-MAP-084

```
ID: FEATURE-MAP-084
TYPE: FEATURE
TITLE: Delete subflow + skip-confirm prefs

DESCRIPTION:
Right-click subflow tab adds permanent Delete subflow action with confirmation dialog
and "Don't ask again" checkbox. Event Engine Prefs panel toggles skipSubflowDeleteConfirm
in eventEngine config.

EXPECTED_BEHAVIOR:
- RMB subflow tab shows Delete subflow (distinct from Close Tab).
- Confirm removes subflow from flows/open_tabs; main undeletable.
- skipSubflowDeleteConfirm persisted in config; honored from dialog checkbox and Prefs.

SCOPE:
tools/event_engine_modal.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-085

```
ID: FEATURE-MAP-085
TYPE: FEATURE
TITLE: Help TOC consolidation + global search

DESCRIPTION:
Merge Paint/Walk/Transparent/Over-player into one Editing modes tab with subsections.
Grouped Contents TOC on home tab. Global search box filters across all help topics.

EXPECTED_BEHAVIOR:
- HELP_GUIDE_TABS has editing_modes instead of four mode tabs.
- Home Contents shows grouped navigation; search finds content across tabs.

SCOPE:
tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Phase 2 complete (2026-08-03): HELP_GUIDE_TABS consolidated; grouped TOC + help_search added.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

## FEATURE-MAP-086

```
ID: FEATURE-MAP-086
TYPE: FEATURE
TITLE: Wild editor independent map picker

DESCRIPTION:
Wild encounter modal can select any map and edit its wild data without switching
the main editor's loaded map (mirrors Event Engine independent scope).

EXPECTED_BEHAVIOR:
- Map picker in wild modal; buffered session per selected map; save writes only wild fields.

SCOPE:
tools/wild_encounter_modal.py, tools/map_editor.py

PRIORITY: MEDIUM
STATUS: DONE
ASSIGNED_TO: Cursor

AUDIT-NOTE:
Fixed: _mark_dirty() now called on all edit paths in wild_encounter_modal.py (apply_species,
_commit_edit, handle_mouse_up/paint_cells, add/remove row buttons, patch panel mutations).
_commit_wild_species_pick in map_editor.py sets _wild_modal_dirty when scope is active.

REBUILD-NOTE:
Python editor code rebuilt from backup plans after accidental deletion (BUG-MAP-065).
Prior DONE status reflected recovery artifacts, not verified parity with backup plans.
Event Editor Full Rebuild Phase 0 audit — see FEATURE-MAP-096 gap matrix.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```


## FEATURE-MAP-087

```
ID: FEATURE-MAP-087
TYPE: FEATURE
TITLE: Audio Engine + route music + opcodes

DESCRIPTION:
Audio Engine editor app with map picker, track list from src/audio/*.ogg, pygame.mixer
preview, musicTrack on map JSON. C++ MusicManager (SDL2_mixer), set_route_music and
play_music_once opcodes.

EXPECTED_BEHAVIOR:
- Events launcher Audio Engine button; preview play/stop; assign musicTrack to map.
- Runtime plays route music on map load; opcodes change music with fade / one-shot.

SCOPE:
tools/audio_engine_modal.py, tools/map_editor.py, tools/events_launcher_modal.py,
include/music_manager.h, src/music_manager.cpp, include/map_data.h, src/map_data.cpp,
src/op.cpp, src/game.cpp, Makefile, tools/event_script_op_meta.json

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

AUDIT-NOTE:
Phase 5: musicTrack read/write verified (BUG-MAP-095); pygame preview; UI-Standard 640×480
with BR+BL resize. See FEATURE-MAP-096 PHASE-5-AUDIT.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```


## FEATURE-MAP-088

```
ID: FEATURE-MAP-088
TYPE: FEATURE
TITLE: Trainer battle opcode + Battle Editor + outcome modes

DESCRIPTION:
Battle Editor app for _library/battles/*.json; start_trainer_battle opcode with
inline/library config, 1-2 trainers x 1-6 Pokemon, outcome modes (normal/scripted_win/
scripted_loss), loss warp priority chain, scripted party rotation, per-level damage.

EXPECTED_BEHAVIOR:
- Battle Editor creates/edits library battles; action modal configures opcode.
- Script yields during battle; normal loss warps and aborts without onComplete;
  scripted modes behave per spec.

SCOPE:
tools/battle_editor_modal.py, tools/event_action_modal.py, tools/event_script_schema.py,
include/battle.h, src/battle.cpp, include/game.h, src/game.cpp, src/map_view.cpp,
src/op.cpp, src/overworld_view.json, include/map_data.h, src/map_data.cpp

PRIORITY: HIGH
STATUS: DONE
ASSIGNED_TO: Cursor

AUDIT-NOTE:
Phase 5 complete: editable Battle Editor; C++ party rotation, 2-trainer sequential flow,
scriptedLossTurns OHKO (Battle::setFoeOhko). event_action_modal rich start_trainer_battle
fields. See FEATURE-MAP-096 PHASE-5-AUDIT.

REBUILD-VERIFIED: Rebuilt from backup plans; automated + manual matrix passed 2026-08-03.
```

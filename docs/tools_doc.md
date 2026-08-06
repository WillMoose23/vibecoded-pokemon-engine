TOOL: tools/map_editor.py

    PURPOSE:
        Interactive pygame map editor for tiles, layers, walkability, transparency, connections, and tileset organization.

    USAGE:
        python3 tools/map_editor.py

    INPUT:
            - src/tilesets.json
            - src/maps/*.json
            - PNG files selected for import/rescale
            - Runtime keyboard/mouse events

    OUTPUT:
            - Updated src/maps/<map>.json (map `version` 4 from editor saves; includes optional `events[]`, optional `wildPatches[]`, `layers.wildEncounter`)
            - Optional `src/maps/scripts/<mapId>/…` script JSON referenced by events
            - Updated src/maps/world_layout.json (world workspace export via F9 when # mode is on)
            - Updated src/tilesets.json
            - Updated src/maps/maps_index.json
            - Optional `tools/map_editor_config.json` updates for key bindings and `eventScriptEditor` (script modal: doc pane, context menu tree, optional `panelWidth` / `panelBodyHeight`, `opcodePaletteSort`, FEATURE-MAP-049)
            - On-screen and console diagnostics

    DEPENDENCIES:
            - Python 3
            - pygame
            - macOS osascript (optional for native prompts)
            - Standard library modules (json, pathlib, copy, subprocess, etc.)

    SIDE EFFECTS:
        Reads and writes map/tileset JSON files.
        May copy imported image assets into project-managed locations.

    ERROR HANDLING:
        Performs validation before destructive writes and reports recoverable issues in status messages.

    NOTES:
        Contains `MapEditor` class with UI loop, drawing routines, and edit operations (paint/fill/undo/redo/layer ops).

        BUG-MAP-096/097/098 + QA audit (2026): wild canvas loads/persists wild data on open/close/Save; session map cache includes wild fields with LRU cap (`SESSION_MAP_CACHE_MAX`); tile blits use scaled-tile LRU cache; map tile loop skipped under blocking modals; palette thumb, tileset list rows, valid-stands coverage grid, sheet cache, and wild overlay surfaces are cached/reused; world node overlap fixup throttled during drag (`WORLD_FIXUP_THROTTLE_MS`). Tests: `tests/test_map_editor_qa_audit.py`.
        FEATURE-MAP-099/100: collapsible tileset panel + NPC sprite editor modal (`npc_sprite_editor_modal`, launcher NPC Sprites row).
        FEATURE-MAP-103: `tile_layer_locked` parallel to tile layers; lock icon on layer chip and Settings list blocks paint/fill/eraser (editor-only, not in map JSON).
        FEATURE-MAP-104: Help tab **NPC Sprites** documents sprite editor; `npcSpriteEditor` config section for palette/defaultZoom.
        IMPROVEMENT-MAP-098: bottom footer pane removed; vertical space reclaimed for map/palette/tileset list. Map metadata shown in layer chip; transient status messages render as semi-transparent toast bar at the bottom of `map_viewport_rect`; inline prompts (map-id, connection) appear in the same toast overlay.
        REFACTOR-CPP-PY-001: module constant `_CONFIRM_DIALOG_YES_KEYS` (`Return`, `y`) is shared by layer-remove, tileset-delete, and map-delete confirm branches (numpad Enter intentionally not included there; `_ENTER_KEYS` still covers prompts that accept both Return keys).
        FEATURE-MAP-WORLD-001 / BUG-MAP-WORLD-002 / FEATURE-MAP-WORLD-004 / FEATURE-MAP-WORLD-008: toolbar `#` toggles world workspace over the map canvas (thumbnails, pan/zoom, context menu, separate world undo/redo when the cursor is over the canvas). **World units are map tiles:** `widthPx`/`heightPx` on each node equal `mapWidthTiles`/`mapHeightTiles`; `world_cam_zoom` is pixels per world tile (default `8`). Legacy layouts where extents were `8 × tileCount` migrate on load (`WORLD_LEGACY_WORLD_PX_PER_TILE`); camera `x`/`y`/`zoom` rescale accordingly. Node origins snap to integer tile coords (`round` to nearest tile; BUG-MAP-WORLD-009) after add, paste, and drag release. Overlap fixup pushes by exactly the overlap amount (`eps=0`, BUG-MAP-WORLD-009) so adjacent (touching, sep=0) placement is allowed. Proximity **preview** lines include `sep == 0` (touching maps show a green connection); export graph also includes `sep == 0` via `build_proximity_edges`. `WORLD_PX_PER_MAP_TILE` applies only to thumbnail rasterization inside the palette-style thumb builder, not to world node size. Large-map thumbnails clamp per-tile draw size (`WORLD_THUMB_CELL_PX_MIN`) and omit dense cell grids when tiles would be sub-5 px. RMB menu toggles `interior` (overlap allowed); non-interior nodes are pushed to non-overlapping (touching allowed) while dragging. Proximity links (green) draw when AABB separation is within `WORLD_EDGE_SNAP_TILES` (including sep=0) (tile units; export `edgeSnapPx` uses the same). FEATURE-MAP-030: editor **3.0**; toolbar **E** opens popover (**NPC Events** | **Wild Encounters**). NPC Events: 2×2 anchors, scripts under `src/maps/scripts/`, sprites from `src/Graphics/Characters`, Pokemon Icons, Icons shiny. FEATURE-MAP-050 wild mode: `layers.wildEncounter` + `wildPatches[]` sidebar. Snapshot `tools/backup_map_editor_v3/`. Opcodes: `docs/event_script_ops.md`. Validate: `python3 tools/validate_map_events.py`. Version shown in pygame title. `src/maps/world_layout.json` is excluded from the open-map list, `maps_index.json`, and `refresh_map_file_list`.
        FEATURE-MAP-041 / FEATURE-MAP-085 / IMPROVEMENT-MAP-094: **Help** toolbar button and **H** (`toggle_help`) open the modal help guide on a context-appropriate tab (`_help_default_tab_for_context`: Event Engine open → **Script Ops**; events/wild workspace or launcher → **Events**; otherwise **Contents**). **Settings** (gear) opens help directly on the **Settings** tab (layer add/remove, key rebinding; legacy `settings_open` overlay removed). Tabs: Contents, **Editing modes** (merged paint/walk/transparent/over-player), Map & exits, Events, World, Keys, Script Ops, Settings. Contents uses grouped TOC headings; number keys **1–7** jump to topics. Global **search** box below the tab bar filters all help body text; click a result to jump. Scroll with mouse wheel; Esc closes (clears search when the search box is focused).
        BUG-MAP-WORLD-007: world mode does not draw a fixed footer-hint string on the map canvas (panning no longer scrolls art under a static overlay); world shortcuts are documented in the help guide (**H**).
        IMPROVEMENT-MAP-036: in **walk** edit mode, hovering the map draws a semi-transparent cyan rectangle for the player **visual** footprint (`playerTilesW` / `playerTilesH`) and magenta outlines on the **collision** cells (`playerCollisionOffX` / `playerCollisionOffY` / `playerCollisionW` / `playerCollisionH`), loaded from `src/overworld_view.json` (same clamp rules as the game). Config is re-read when the JSON file modification time changes.
        IMPROVEMENT-MAP-037: **`toggle_valid_player_stands`** (default **`j`**) toggles a bright green rectangular outline around every **valid player anchor** on the map canvas (not in world `#` workspace): anchors where all collision sub-cells are in-bounds and walkable (`walk` layer `0`), using the same `overworld_view.json` footprint and collision fields as IMPROVEMENT-MAP-036. Each outline spans `playerTilesW` × `playerTilesH` cells on the existing 1×1 grid. Help lists the shortcut.
        IMPROVEMENT-MAP-038: **Performance:** valid-stand overlay uses a **cached anchor list** rebuilt only when walkability, map dimensions, overworld collision footprint, or overlay toggle changes (not every frame). **Walk**, **transparent**, and **over_player** tint layers reuse preallocated per-cell SRCALPHA surfaces instead of allocating per visible tile per frame. Walk-mode **hover footprint** reuses one surface sized to `(playerTilesW*cell_px, playerTilesH*cell_px)`. `overworld_view.json` is stat/parsed at most **once per draw frame** for consumers that call `_refresh_overworld_view_player_config`. Event character subsurface previews use an **LRU-capped** `OrderedDict` (`CHAR_FRAME_SURFACE_CACHE_MAX`, default 64).
        IMPROVEMENT-MAP-039: **`toggle_valid_player_stands_orange`** (default **`k`**) toggles bright orange valid-footprint outlines using the same cached anchor geometry as the green overlay; this gives a dedicated placement-alignment overlay while preserving the original J toggle.
        IMPROVEMENT-MAP-040: Adds editor mode **`over_player`** (cycled via Tab) with orange per-cell tint editing and JSON persistence as `layers.overPlayer` (binary grid). Runtime rendering uses base pass (all non-overPlayer tiles), then player, then over-player pass (tiles where `overPlayer[y][x] != 0`) in both single-map and world-layout views.
        IMPROVEMENT-MAP-041: **`toggle_eraser`** (default **E**) toggles eraser in **paint**, **walk**, **transparent**, and **over_player** (same modes as Tab cycles). Walk/over-player: drag clears blocked or over-player flags when eraser is on. Transparent: either mouse button clears transparency when eraser is on. **`toggle_fill`** remains paint-only; palette “fill” hint shows only in paint mode.
        FEATURE-MAP-042: `MapEditor.relayout` moves the tileset filesystem pane to a bottom strip and expands map viewport width by removing the old side filesystem column. `layer_add` (default `L`) now opens a layer-manager popup with add/delete, rename, vertical drag reorder, and per-layer over-player applicability toggles.
        IMPROVEMENT-MAP-042: map save now writes optional `layers.tileLayers[].applyOverPlayer` booleans (default true). Runtime map/world viewers treat layers with this flag off as always below-player, even when the `layers.overPlayer` grid marks the tile.
        FEATURE-MAP-043: Events workspace lists **Edit script (modal)** next to **Open script JSON**. The modal edits ordered steps (add, save, close, RMB context menu for every opcode in `tools/event_script_schema.py`, drag reorder, Ctrl+C / Ctrl+V). Saved files use `map`, `version`, `script_1` (array of one-key objects), and `script_2: []`; legacy `actions` arrays are still loaded by the game when `script_1` yields no steps. **IMPROVEMENT-MAP-051**: **H** (`toggle_help`) opens context-appropriate help: script modal → **Script opcodes**; NPC Events or Wild Encounters workspace → updated **Events** tab; otherwise **Contents**. **FEATURE-MAP-053**: Wild Encounters tier editor opens a species modal (search, ★ favorites in `wildEncounterEditor.favoriteSpecies`); LMB row or **+ row**; favorites sort first.
        FEATURE-MAP-044 / FEATURE-MAP-048 / FEATURE-MAP-049: Script modal uses **three columns** when the doc pane is on (steps | opcode palette | structured documentation from `tools/event_script_opcode_docs.py`). Footer **Sprite** opens the sprite picker docked in the modal (**BUG-MAP-028**: list clicks and wheel over the docked picker are handled inside the modal so rows scroll and select). **gear** popover toggles the doc pane, persists size, and sets opcode palette sort (**source** / **alpha** / **category** using `category` + `required_params` in `tools/event_script_op_meta.json`). Bottom-right **resize grip** adjusts `panelWidth` and `panelBodyHeight` (persisted under `eventScriptEditor`). Wheel scrolls hovered column; **IMPROVEMENT-MAP-044**: opcode insert uses **LMB drag after a small movement threshold** (same px constant as tileset list drags); a **click** (below threshold) **pins** the right-hand documentation pane to that opcode until you select a script step or pick another opcode. Opcode order from **`tools/event_script_ops_generated.py`** (`python3 tools/extract_map_script_ops.py`). **IMPROVEMENT-MAP-043**: `event_script_opcode_docs._wrap_words` preserves leading indentation for wrapped prose. **IMPROVEMENT-MAP-045**: Function and Example JSON in docs use `indent=4` and are not word-wrapped. **BUG-MAP-029**: Enter and character-frame picking work while the script modal is open (`_event_script_modal_keydown` and earlier `MOUSEBUTTONDOWN` routing). **FEATURE-MAP-050**: sprite picker shows a **preview pane** to the right of the filename list (`_events_sprite_pick_list_and_preview_rects`, `_events_sprite_pick_selection_preview_surface`). **IMPROVEMENT-MAP-046** / **BUG-MAP-031** / **BUG-MAP-032**: NPC **4×4 frame** overlay fits title (wrapped with `_wrap_lines_to_width`), scaled sheet, and facing bar; horizontal budget from `min(map_viewport_rect.w, window)`, vertical from `map_canvas_rect.h`, center on `map_canvas_rect` with `top_bound = max(margin, canvas.y)`, sheet inner aligned to `title_block_h` (`_draw_events_character_frame_overlay`). **IMPROVEMENT-MAP-047**: long **Script opcodes** help lines and script-modal doc lines are split to the panel pixel width before `Font.render` (`_expand_help_overlay_segments`, `_expand_visual_text_lines`). **BUG-MAP-030**: `event_script_opcode_docs.build_structured_doc_lines` subtracts the pixel width of a two-space prefix from `_wrap_words` budgets for description and parameter rows so wrapped lines are not a few pixels too wide.
        FEATURE-MAP-046: Script modal **RMB** opens a **nested, configurable** context menu (cascade flyouts from `tools/event_script_ctx_menu.py`; JSON under `tools/map_editor_config.json` → `eventScriptEditor.contextMenu`; invalid config falls back to defaults). While the modal is open, **global map shortcuts do not run** except **H** (help) and resize **MOUSEMOTION** updates; **Esc** closes the context menu, then the settings popover, then the modal. Unit tests: `python3 -m unittest discover tests -v` (see `tests/test_event_script_ctx_menu.py`).
        FEATURE-MAP-083: `modal_text.py` FORM_* constants (`FORM_LABEL_COL_W`, `FORM_FIELD_H_PAD`, `FORM_HELP_GAP`, `FORM_ROW_GAP`, `FORM_SECTION_TOP`) and helpers (`form_field_h`, `form_field_x`, `form_field_w`, `form_label_x/y`, `form_help_y`, `form_row_advance`) are used by `event_action_modal.py` (horizontal label+field layout), `event_trigger_modal.py` (field heights + row gaps), `flag_registry_modal.py` (list row field heights), `audio_engine_modal.py`, and `battle_editor_modal.py`.
        FEATURE-MAP-087: `_map_music_track` (str) is loaded from `musicTrack` in `try_load_map_by_id`, persisted in `_write_map_json_to_disk` (only written when non-empty), and included in `_snapshot_session_map_bundle` / `_restore_session_map_bundle` under key `"music_track"`. `read_map_music_track(map_id)` and `write_map_music_track(map_id, track)` expose it to `AudioEngineModal`.
        FEATURE-MAP-086: Wild modal dirty-flag contract. `_commit_wild_species_pick` sets `self._wild_modal_dirty = True` when `wild_modal_scope_id` is active.

    FUNCTION: main

    DESCRIPTION:
        Entry point that creates `MapEditor` and starts the editor loop.

    INPUT:
        None

    OUTPUT:
        Runs until user closes editor.

    SIDE EFFECTS:
        Opens SDL window and persists edits to project files.

    FUNCTION: MapEditor.run

    DESCRIPTION:
        Main event/render loop handling shortcuts, tool modes, edit application, and overlay drawing.

    INPUT:
            - Pygame event stream
            - Current in-memory editor state

    OUTPUT:
        Rendered frames and state transitions.

    SIDE EFFECTS:
        Applies edits, checkpoints undo/redo, triggers file save/load/import actions.

TOOL: tools/audit_event_script_ops.py

    PURPOSE:
        IMPROVEMENT-MAP-052: verify event script opcode parity across `tools/event_script_op_meta.json`, `src/op.cpp`, and `Game::tryMapViewerScriptOpcode_` in `src/map_view.cpp` (plus `onWarp` / `onFacingHint` wiring).

    USAGE:
        python3 tools/audit_event_script_ops.py

    INPUT:
        `src/op.cpp`, `src/map_view.cpp`, `tools/event_script_op_meta.json`; runs `tools/extract_map_script_ops.py` first.

    OUTPUT:
        Prints `audit_event_script_ops: OK` on success; stderr errors and exit 1 on mismatch.

    DEPENDENCIES:
        Python 3 standard library, `tools/extract_map_script_ops.py`

    SIDE EFFECTS:
        Regenerates `tools/event_script_ops_generated.py` via subprocess when extract runs.

    ERROR HANDLING:
        Non-zero exit if extract fails or any opcode/handler check fails.

    NOTES:
        Verifies walk/camera opcodes plus Phase 4 extended opcodes (`set_route_music`,
        `play_music_once`, `start_trainer_battle`) in `tryMapViewerScriptOpcode_`.
        Covered by `tests/test_event_script_opcode_parity.py`.

TOOL: tools/wild_encounter_editor_helpers.py

    PURPOSE:
        FEATURE-MAP-053: pure functions for wild encounter species list ordering (favorites first, search filter) used by `tools/map_editor.py`.

    USAGE:
        Imported by `tools/map_editor.py` (not run standalone).

    INPUT:
        Species key list, favorite set, filter string.

    OUTPUT:
        Filtered/sorted display list and default species for new rows.

    DEPENDENCIES:
        None

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        N/A

    NOTES:
        Unit tests: `tests/test_wild_species_picker.py`.


TOOL: tools/wild_encounter_modal.py

    PURPOSE:
        FEATURE-MAP-056/058: dedicated wild encounter editor modal (mini-map, patch/tier column,
        integrated species search, global encounters tab, adjacency auto-assign painting, and
        flood-fill patch selection with inline typed inputs).

    USAGE:
        Imported by `tools/map_editor.py`; opened from Events launcher → Wild Encounters (LMB).
        FEATURE-MAP-098: "Main map" header button switches to main-canvas wild paint mode;
        Events launcher Wild RMB also opens canvas mode directly.

    INPUT:
        Map editor state: `wild_encounter`, `wild_patches`, `wild_global_encounters`, species keys,
        brush/eraser mode.

    OUTPUT:
        Mutates in-memory wild data (patches, global encounters, encounter cells); modal UI only.
        No disk write until map save.

    DEPENDENCIES:
        pygame, `tools/wild_encounter_editor_helpers.py`

    SIDE EFFECTS:
        None on disk until map save.

    ERROR HANDLING:
        Closes on Esc or Close button; clamps panel to viewport; commits open text edits on close.

    NOTES:
        BUG-MAP-057: mini-map was blank on first open because _draw_mini_map read the stale
        _map_view_rect (0,0,1,1); fixed to derive map_rect from self.map_inner.

        FEATURE-MAP-058 additions:
        - Typed input boxes for stepChancePercent (clamped [0,100]) and species weight (clamped
          [1,999]); Enter commits, Escape cancels, click-away commits.
        - Local / Global tab bar in the patch column. Global tab edits map-wide species that appear
          in every patch at runtime (local always wins on duplicate species). A "!" indicator marks
          any global species that also appears in the current local patch.
        - Adjacency auto-assign paint: painting an empty tile adjacent to an existing patch joins
          that patch; painting an isolated tile creates a new patch entry. Right-click still erases.
        - Flood-fill selection: left-clicking a painted tile BFS-fills the contiguous same-index
          component and highlights it (cyan overlay + bright outline). Clicking empty space clears.
        - Patch index digit rendered in each patch cell when cell_px >= 10.
        - Patch paint uses `snap_cell_to_stride_grid` (same grid as K orange overlay).
        Tests: `tests/test_wild_stride_snap.py`.

        FEATURE-MAP-059 additions (mini-map zoom + resizable modal):
        - `_map_zoom` (int | None): None = auto-fit; int = explicit px-per-cell in [4..64].
          Resets to None on each open; never persisted to disk.
        - `_panel_override` (pygame.Rect | None): last user-chosen panel size/position; persists
          across close/reopen within the session (not persisted to disk). None = default sizing.
        - Zoom controls: [-] [fit] [+] buttons in the map-column header change `_map_zoom` by ±4.
          A small label to the right shows "auto" or "<N>px". Ctrl+scroll over the mini-map also
          zooms ±4.
        - Resize grip (bottom-right): a filled triangle; dragging sets `_panel_override` to at
          least 640×480 and clamps to the canvas bounds.
        - All modal column widths reflow based on the live `panel_rect`, so resizing distributes
          space across all three columns without clipping.

        FEATURE-MAP-060 additions (bottom-left resize + title-bar drag-to-move):
        - `_drag_mode` (str): replaces the old `_resize_drag` bool. Values: "none", "resize_br",
          "resize_bl", "move". Cleared on mouse-up and on open_modal.
        - `_drag_ref` (tuple[int,int]): context-dependent reference point for the active drag:
          top-left anchor for BR resize, top-right anchor for BL resize, mouse offset into panel
          for move.
        - `_resize_corner_bl`: bottom-left triangle grip; dragging expands the modal leftward
          and downward (width min 640, height min 480).
        - `_title_bar`: hit area spanning the full header strip minus the close button. Dragging
          repositions the panel anywhere within the canvas (clamped in draw()). Five grip dots
          drawn in the centre of the bar indicate the drag handle.

        BUG-MAP-061 fix (diagonal mini-map pan):
        - Vertical scroll (plain) now only updates `wild_modal_map_off_y`.
        - Shift+scroll updates `wild_modal_map_off_x` only.

        BUG-MAP-062 fix (species list scroll resets to top):
        - Removed the upward auto-correction `if species_sel < species_scroll` from
          `_draw_species_column`; scroll is now clamped to `[0, len(names)-vis]` each frame.
        - `_species_vis` stores the last-known visible row count for use in the wheel handler.
        - Keyboard navigation still auto-scrolls DOWN to keep the selected item in view.

        FEATURE-MAP-063: canvas changed from ed.map_viewport_rect to ed.screen.get_rect() so
        the modal and dim overlay cover the entire program window. The panel can now be dragged
        into the palette or tileset-strip areas. screen.get_rect() always returns live window
        dimensions, so the modal also auto-recentres after windowed/fullscreen toggles without
        any additional event handling.

        IMPROVEMENT-MAP-055: Event script modal drag shows a floating ghost with full step text.

        FEATURE-MAP-086 (wild independent scope): `_mark_dirty()` is now called on all edit paths
        that mutate wild data while a different-map scope is active — apply_species, _commit_edit
        (step/weight), handle_mouse_up (after paint_cells), add/remove row buttons (local and
        global), and patch-panel delegate (ed._wild_handle_panel_click). This ensures
        `        wild_modal_switch_map` and `wild_modal_end` correctly flush the buffered session.

        FEATURE-MAP-099: left tileset list panel collapses to `TILESET_LIST_COLLAPSED_W` (28px) via
        header chevron; persisted in `map_editor_config.json` → `tilesetList.collapsed`. Unfiled
        section uses `section:unfiled` in `editorTilesetFolders.collapsed`; child tilesets indent
        `TILESET_LIST_CHILD_INDENT_PX` (20).

TOOL: tools/npc_sprite_sheet_helpers.py

    PURPOSE:
        FEATURE-MAP-100: pure helpers for 4×4 NPC character sheet layout, frame indexing,
        horizontal mirror, and PNG filename sanitization.

    USAGE:
        Imported by `tools/npc_sprite_editor_modal.py` and unit tests.

    INPUT:
        Sheet dimensions, direction names, RGBA pixel grids, Characters directory path.

    OUTPUT:
        Validated dimensions, frame indices, mirrored grids, sorted PNG basenames.

    DEPENDENCIES:
        Python 3 standard library (pathlib only).

    SIDE EFFECTS:
        None (pure functions except list_character_pngs reads directory).

    ERROR HANDLING:
        validate_sheet_dimensions returns (False, message) for non-divisible sizes.

    NOTES:
        Default sheet 128×192 (32×48 cells). FEATURE-MAP-102: `flood_fill_surface`,
        `composite_rgba_layers`, `parse_palette_from_config`, `DEFAULT_NPC_PALETTE`.
        Tests: `tests/test_npc_sprite_sheet_helpers.py`.

TOOL: tools/npc_sprite_editor_modal.py

    PURPOSE:
        FEATURE-MAP-100: pygame modal to paint NPC walk sprites on a 4×4 sheet grid and export
        PNGs to `src/Graphics/Characters/` for EventSpriteModal.

    USAGE:
        Opened from Events launcher → NPC Sprites. Back returns to launcher.

    INPUT:
        Mouse (paint/erase, direction/frame tabs, palette), keyboard (Save As filename, Ctrl+Z/Y,
        dimension fields), wheel (zoom on canvas).

    OUTPUT:
        PNG files under Characters/; on-screen preview with optional reference sheet pane.

    DEPENDENCIES:
            - pygame
            - tools/npc_sprite_sheet_helpers.py
            - tools/modal_text.py
            - tools/map_editor.py (MapEditor)

    SIDE EFFECTS:
        Writes PNG to disk on Save / Save As.

    ERROR HANDLING:
        Status messages for invalid dimensions, missing files, save failures.

    NOTES:
        BUG-MAP-101: canvas aspect-correct; per-axis _cell_step_x/y hit-test.
        FEATURE-MAP-102: left rail (P/E/F tools, RGBA sliders, layers with eye/lock/rename),
        composite visible layers on save, flood fill, zoom default 8, matched ref canvas.
        FEATURE-MAP-104: Help button → npc_sprites tab; Edit Swatches → config palette.
        Mirror-lock (default on) copies Left row to mirrored Right row on active layer.
        Walk helpers: Idle→F3, Dup prev. Non-128×192 warns via sheet_dimensions_warning.
        Tests: `tests/test_npc_sprite_editor_modal.py`, `tests/test_npc_sprite_sheet_helpers.py`.

TOOL: tools/validate_map_events.py

    PURPOSE:
        FEATURE-MAP-030 / FEATURE-MAP-043 / FEATURE-MAP-050: validate map JSON `events[]` (2×2 anchors in bounds, non-overlapping, script `path` files exist and parse as JSON) and wild data (`wildPatches`, `layers.wildEncounter` dimensions and indices, species keys vs `src/monster.json`, positive weights, at least one encounter row per patch). Warns when a script file has no non-empty `script_1` or `actions`, or when a wild patch has zero painted tiles. Validates optional `sprite.facing` for `kind: character` (FEATURE-MAP-049). FEATURE-MAP-068: reports unbalanced control-flow blocks (`if_flag`/`end_if`, `repeat`/`end_repeat`) as errors via `event_script_schema.validate_balanced`. FEATURE-MAP-074/075/076/078: `_script_block_error` checks balancing across the main flow and all in-file subflows (incl. `if_var`/`end_if_var`, `region`/`end_region`); `_script_reference_errors` validates `goto` targets (label in same flow) and `call_subflow` references (in-file subflow or existing `_library/<name>.json`, `LIBRARY_DIR`); `_validate_event_trigger` validates `trigger.type` (`TRIGGER_TYPES`), `trigger.condition`, `clearedFlag`, and `onComplete.setFlags`/`clearFlags`.

    USAGE:
        python3 tools/validate_map_events.py

    INPUT:
        `src/maps/*.json` (skips `maps_index.json`, `world_layout.json`)

    OUTPUT:
        Prints warnings then errors to stderr; exit non-zero only when errors exist.

    SAMPLE_MAP:
        `src/maps/event_script_demo.json` with script under `src/maps/scripts/event_script_demo/` (manual game check: load map, stand next to the 2×2 hull, press Q in overworld).

TOOL: tools/event_script_schema.py

    PURPOSE:
        FEATURE-MAP-043: shared opcode registry (`EVENT_ACTION_DEFS`), default args, and load/save helpers for map event script JSON (`document_to_steps`, `steps_to_document`, `read_steps_from_path`, `write_document_to_path`).

    USAGE:
        Imported by `tools/map_editor.py` via `importlib.util.spec_from_file_location` (same pattern as `world_layout.py`).

    INPUT:
        Script JSON objects or filesystem paths under `src/maps/`

    OUTPUT:
        Normalized in-memory steps as `list[dict]` with `op` and `args` for the editor UI.

    DEPENDENCIES:
        Python 3 standard library (`json`, `copy`, `pathlib`, `importlib.util` for generated opcode list).

    SIDE EFFECTS:
        `write_document_to_path` creates parent directories and overwrites the target JSON file.

    ERROR HANDLING:
        `read_steps_from_path` returns a default `show_message` step when the file is missing or invalid JSON.

    NOTES:
        FEATURE-MAP-044: loads sibling **`event_script_ops_generated.py`** (`CPP_SCRIPT_OPS_ORDERED`) and merges **`event_script_op_meta.json`** into `EVENT_ACTION_DEFS`; exposes `op_documentation(op)` (label, description, status, default args, args help, **category**, **required_params**) for UI and `event_action_defs_with_palette_sort(mode)` for palette ordering. Missing generated file or meta/C++ mismatch surfaces at import or when running `tools/extract_map_script_ops.py`.
        FEATURE-MAP-068: control-flow helpers for the block editor — `op_category`, `op_block_role`/`op_block_end`/`is_block_open`/`is_block_close`, `validate_balanced(steps)`, and the nested `steps_to_tree(steps)` / `tree_to_steps(tree)` converters (terminator markers are implicit in the tree; `args.skip` is never written from Python — the C++ engine stamps it on load). `validate_balanced` and the block roles cover the FEATURE-MAP-076/077 pairs `region`/`end_region` and `if_var`/`end_if_var`.
        FEATURE-MAP-074/075: multi-flow helpers — `document_to_flows(doc)` / `flows_to_document(flows, map_id)` (main flow in `script_1`, named subflows under `subflows`), `read_flows_from_path` / `write_flows_to_path`, and `labels_in_steps(steps)` (ordered, de-duplicated label names for the goto dropdown).
        FEATURE-MAP-081: `sort_palette_ops_in_category(ops)` — reorders ops so block openers
        appear immediately before their end_* pair (unpaired closers at end).
        `list_library_subflow_names()` — scans `src/maps/scripts/_library/*.json` and returns
        sorted stem names for the call_subflow picker.
        FEATURE-MAP-096: migration helpers — `TRIGGER_TYPES`, `default_event_trigger()`,
        `trigger_from_legacy_interaction()`, `normalize_map_event(ev)`, `migrate_script_document(doc, map_id)`,
        and `script_documents_equal(a, b)` for `tools/migrate_map_events.py`.

TOOL: docs/cursor_helper_scripts/sync_cursor_plans.py

    PURPOSE:
        IMPROVEMENT-MAP-096: copy Cursor plan files from the global plans directory into the
        repo-backed `.cursor/plans/` folder so they can be committed to `origin/development`.

    USAGE:
        `python3 docs/cursor_helper_scripts/sync_cursor_plans.py`
        Run before every git push (enforced by Git-Push-Development-Rule).

    INPUT:
        Source: `~/.cursor/plans/*.plan.md`

    OUTPUT:
        Destination: `.cursor/plans/*.plan.md` (creates dir if missing). Prints copied/updated/total counts.

    DEPENDENCIES:
        Python 3 standard library (`pathlib`, `shutil`).

    SIDE EFFECTS:
        Creates or updates files under `.cursor/plans/`; newer source mtime overwrites repo copy.

    ERROR HANDLING:
        Exits 1 if `~/.cursor/plans` does not exist; otherwise exit 0.

    NOTES:
        Repo-only plans not present in the global folder are preserved. See `.cursor/plans/README.md`.

TOOL: docs/cursor_helper_scripts/sync_cursor_skills.py

    PURPOSE:
        IMPROVEMENT-MAP-097: copy Cursor skill folders from `~/.cursor/skills/` into
        `.cursor/skills/` for git backup on `origin/development`.

    USAGE:
        `python3 docs/cursor_helper_scripts/sync_cursor_skills.py`
        Prefer `python3 docs/cursor_helper_scripts/sync_cursor_backup.py` (plans + skills together).

    INPUT:
        Source: `~/.cursor/skills/<skill-name>/` (typically contains `SKILL.md`).

    OUTPUT:
        Destination: `.cursor/skills/<skill-name>/`. Prints copied/updated/folder counts.

    DEPENDENCIES:
        Python 3 standard library.

    SIDE EFFECTS:
        Creates/updates skill folders under `.cursor/skills/`; repo-only skills preserved.

    ERROR HANDLING:
        Exits 1 if `~/.cursor/skills` missing; else exit 0.

    NOTES:
        Does not sync `~/.cursor/skills-cursor/` (Cursor built-in skills).

TOOL: docs/cursor_helper_scripts/sync_cursor_backup.py

    PURPOSE:
        IMPROVEMENT-MAP-097: run plan and skill sync in one step before git push.

    USAGE:
        `python3 docs/cursor_helper_scripts/sync_cursor_backup.py`

    INPUT:
        Invokes `docs/cursor_helper_scripts/sync_cursor_plans.py` and
        `docs/cursor_helper_scripts/sync_cursor_skills.py`.

    OUTPUT:
        Combined exit code; stdout from each child script.

    DEPENDENCIES:
        `docs/cursor_helper_scripts/sync_cursor_plans.py`,
        `docs/cursor_helper_scripts/sync_cursor_skills.py`.

    SIDE EFFECTS:
        Updates `.cursor/plans/` and `.cursor/skills/` in the working tree.

    ERROR HANDLING:
        Non-zero if either child script fails.

    NOTES:
        Required by Git-Push-Development-Rule before push to `development`.

TOOL: tools/migrate_map_events.py

    PURPOSE:
        FEATURE-MAP-096 Phase 1: one-time migration of map JSON `events[]` and linked script files
        to the canonical shape used by the Event Engine rebuild (`trigger` objects, `script_1` arrays).

    USAGE:
        Dry-run (default): `python3 tools/migrate_map_events.py`
        Apply changes: `python3 tools/migrate_map_events.py --write`
        Custom maps dir: `python3 tools/migrate_map_events.py --maps-dir path/to/maps`

    INPUT:
        Map JSON files under `src/maps/` (skips `maps_index.json`, `world_layout.json`); script paths
        referenced by each event's `script.path`.

    OUTPUT:
        Stdout log lines per change; stderr mode banner (`DRY-RUN` or `WRITE`). With `--write`, overwrites
        map and script JSON files in place.

    DEPENDENCIES:
        `tools/event_script_schema.py` migration helpers; Python 3 standard library.

    SIDE EFFECTS:
        With `--write`: modifies map JSON and script JSON on disk.

    ERROR HANDLING:
        Skips unreadable maps/scripts with a log line; does not abort the batch.

    NOTES:
        Does not fix validator content errors (e.g. missing library subflow references). Run
        `python3 tools/validate_map_events.py` after migration. Phase 6 of the rebuild plan runs
        `--write` on the repo maps after backup.

TOOL: tools/event_script_opcode_docs.py

    PURPOSE:
        FEATURE-MAP-049: builds structured plain-text opcode documentation (function JSON shape, mandatory/optional parameters, `script_1` example) for the map editor doc column and the **Script opcodes** help tab.

    USAGE:
        Imported lazily by `tools/map_editor.py` via `importlib.util.spec_from_file_location`.

    INPUT:
        Opcode id, merged doc dict from `event_script_schema.op_documentation`, wrap width, and a line-measure callback (pygame font).

    OUTPUT:
        `build_structured_doc_lines` (list of strings) and `build_help_segments_for_op` (typed segments for `_help_build_lines`).

    DEPENDENCIES:
        Python standard library (`json`, `copy`, `typing`).

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        None

    NOTES:
        Keep in sync with `tools/event_script_op_meta.json` and C++ opcode dispatch; see `.cursor/skills/event-script-opcode-docs/SKILL.md`.

TOOL: tools/event_script_ctx_menu.py

    PURPOSE:
        FEATURE-MAP-046 / Phase 3: validate and layout cascade RMB menus for the Event Engine
        block panel and events list (`type` action | submenu, stable `id`, optional `when`).

    USAGE:
        Imported by `tools/event_engine_modal.py` and lazily by legacy script modal paths.

    INPUT:
        Optional `eventEngine.contextMenuEvents` / `contextMenuBlocks` (or
        `eventScriptEditor.contextMenu` for blocks) from `tools/map_editor_config.json`;
        known opcode names; pointer position for cascade layout.

    OUTPUT:
        Filtered menu trees, screen-space panel layouts, and hit-tested action ids for pygame.
        `default_event_menu_tree()` supplies events-list defaults; `default_menu_tree_from_ops()`
        supplies block-panel defaults.

    DEPENDENCIES:
        Python 3 standard library only (`copy`, `typing`).

    SIDE EFFECTS:
        None (pure helpers).

    ERROR HANDLING:
        `parse_menu_from_config` / `parse_event_menu_from_config` return `(None, errors)` when
        invalid; callers fall back to defaults.

    NOTES:
        Depth and node count capped (`MAX_DEPTH`, `MAX_NODES`). Event ids: `ev:rename`, `ev:view`, etc.
        Block ids: `step:delete`, `blk:editmodal`, `blk:doc`, `add:<op>`, etc. Human-readable schema: `docs/event_script_ops.md`.

TOOL: tools/extract_map_script_ops.py

    PURPOSE:
        FEATURE-MAP-044 / FEATURE-MAP-048 / FEATURE-MAP-049: parse `src/op.cpp` for `if (op == "...")` opcode strings in first-seen order and emit `tools/event_script_ops_generated.py`; verify `tools/event_script_op_meta.json` defines the same op keys bidirectionally (meta may add `category`, `required_params`, and opcode doc fields not parsed by this script).

    USAGE:
        python3 tools/extract_map_script_ops.py

    INPUT:
        - `src/op.cpp`
        - `tools/event_script_op_meta.json`

    OUTPUT:
        - Overwrites `tools/event_script_ops_generated.py` (`CPP_SCRIPT_OPS_ORDERED` tuple).

    DEPENDENCIES:
        Python 3 standard library (`json`, `pathlib`, `re`, `sys`).

    SIDE EFFECTS:
        Writes the generated Python module.

    ERROR HANDLING:
        Exits non-zero when C++ file or meta is missing, no ops match the regex, or meta keys differ from extracted ops.

    NOTES:
        `tools/event_script_ops_generated.py` is **generated output only**; edit `src/op.cpp` / `event_script_op_meta.json` and re-run this script. Downstream consumers: `tools/map_editor.py` (opcode ordering), `tools/event_script_ctx_menu.py`, and tests that import `CPP_SCRIPT_OPS_ORDERED`.

TOOL: tools/event_script_ops_generated.py

    PURPOSE:
        Generated Python module exposing `CPP_SCRIPT_OPS_ORDERED` (opcode strings in C++ dispatch order). Produced exclusively by `tools/extract_map_script_ops.py`.

    USAGE:
        Regenerate with `python3 tools/extract_map_script_ops.py` from the repository root; do not hand-edit except via the extractor.

    INPUT:
        None directly; reflects the last successful extractor run over `src/op.cpp` and `tools/event_script_op_meta.json`.

    OUTPUT:
        Tuple constant consumed by the map editor and script tooling for opcode lists and validation.

    DEPENDENCIES:
        Python 3 (module is static data only).

    SIDE EFFECTS:
        File on disk is overwritten when the extractor runs.

    ERROR HANDLING:
        Invalid or stale content is corrected by re-running the extractor; the game runtime does not import this file.

TOOL: tools/world_layout.py

    PURPOSE:
        Pure-Python helpers to build proximity edges, Dijkstra-based `renderOrder`, composite bounds, and read/write `src/maps/world_layout.json` for the map editor world workspace (FEATURE-MAP-WORLD-001).

    USAGE:
        Imported by `tools/map_editor.py` via `importlib` (script is not run as a package).

    INPUT:
            - In-memory node dicts from `MapEditor.world_nodes`
            - Export parameters (`edge_snapPx` threshold in **map-tile / world-tile units** after FEATURE-MAP-WORLD-008; optional camera dict)

    OUTPUT:
            - `dict` payloads suitable for `json.dump`
            - Parsed dict from `read_world_layout_json` when the file exists

    DEPENDENCIES:
            - Python 3 standard library (`json`, `heapq`, `math`, `pathlib`)

    SIDE EFFECTS:
        `write_world_layout_json` creates or overwrites `world_layout.json` under the path passed in.

    ERROR HANDLING:
        `read_world_layout_json` returns `None` on missing file or JSON errors.

    NOTES:
        Edge endpoints use per-node instance ids (`nodeUuid` in the editor, exported as `instanceId`) so duplicate `mapId` placements remain distinct in the graph.
        Field `renderOrder` lists those same instance ids (not bare `mapId` strings).
        FEATURE-MAP-029: the SDL game map viewer (key 3) reads `src/maps/world_layout.json` when the user picks **Overworld** and draws instances in `renderOrder` (back-to-front) into a world-tile viewport.
        FEATURE-MAP-031: `src/overworld_view.json` may set `playerSprite`, `playerWalkFrameMs`, and `playerDrawOffsetTilesX` (integer tile widths; horizontal draw offset, default 1); see `docs/source_doc.md` / `docs/tracker.md`.
        IMPROVEMENT-MAP-032: in the SDL map viewer (**ViewMap** and **ViewWorld**), **L** toggles per-tile grid outlines (`overworldTileGridVisible_`). BUG-MAP-026: **ViewMap** previously always drew outlines and ignored **L**; fixed in `src/map_view.cpp`. BUG-MAP-027: single-map load order in `Game::loadMapForView_` must not destroy the player texture after `loadOverworldViewConfig_`. FEATURE-MAP-047: `warp_player` uses `world_layout.json` when the target `mapId` is listed so the player stays in the overworld composite view.

TOOL: build/app

    PURPOSE:
        SDL runtime binary produced by the project `Makefile` for title screen, battles, and the map / overworld viewer.

    USAGE:
        make && ./build/app
        make test          # C++ runtime smoke (test_script_runtime + test_game_state)

    INPUT:
            - Keyboard (e.g. key 3 map viewer, WASD in map modes)
            - Data files under `src/` (maps, tilesets, `world_layout.json` for Overworld)

    OUTPUT:
            - Rendered frames

    DEPENDENCIES:
            - SDL2, SDL2_ttf, SDL2_image

    SIDE EFFECTS:
            None (read-only for maps unless other modes write).

    ERROR HANDLING:
            Map and Overworld loaders print to stderr and keep the user in the picker when files are missing or invalid.

    NOTES:
        FEATURE-MAP-029: key 3 opens the catalog with **Overworld** first (`world_layout.json` composite); other rows load single `src/maps/<id>.json` maps.

    FUNCTION: build_export_dict

    DESCRIPTION:
        Assembles versioned export payload including nodes, proximity edges, `renderOrder`, optional `compositeBounds`, and optional `editorCamera`.

    INPUT:
            - nodes, edge_snap_px (tile-space distance threshold), origin_map_id, editor_tool_version, optional cam

    OUTPUT:
        dict — JSON-serializable world layout document

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        None

    DEPENDENCIES:
            - build_proximity_edges
            - render_order_by_proximity
            - composite_bounds
            - copy_nodes_for_export

TOOL: tools/validate_maps.py

    PURPOSE:
        Validates map and tileset JSON schemas and regenerates maps index.

    USAGE:
        python3 tools/validate_maps.py

    INPUT:
            - src/tilesets.json
            - src/maps/*.json (excluding maps_index.json and world_layout.json)

    OUTPUT:
            - Exit code 0 on success / non-zero on failure
            - Error messages to stderr
            - Updated src/maps/maps_index.json

    DEPENDENCIES:
            - Python 3 standard library (json, pathlib, sys, os)

    SIDE EFFECTS:
        Rewrites map index file when validation succeeds.

    ERROR HANDLING:
        Uses `fail(...)` to print precise diagnostics and terminate on invalid schema/state.

    NOTES:
        Ignores editor-only keys when validating runtime-required tileset/map data.

    FUNCTION: main

    DESCRIPTION:
        Runs tileset validation, map validation, and map index synchronization.

    INPUT:
            - JSON registry and map files

    OUTPUT:
        Console diagnostics and process exit status.

    SIDE EFFECTS:
        Writes maps index.

    FUNCTION: fail

    DESCRIPTION:
        Emits a fatal error message and exits with status 1.

    INPUT:
            - msg: str

    OUTPUT:
        stderr line prefixed with `error:`.

    SIDE EFFECTS:
        Terminates process execution.

TOOL: tools/migrate_monster_to_nested_forms.py

    PURPOSE:
        Migrates flattened Pokemon keys in monster.json into nested per-species entries with standardized alternate form fields.

    USAGE:
        python3 tools/migrate_monster_to_nested_forms.py

    INPUT:
            - src/monster.json

    OUTPUT:
            - Rewritten src/monster.json with nested Pokemon structure
            - Warnings for ambiguous base-form selection cases

    DEPENDENCIES:
            - Python 3 standard library (json, re, collections, typing, os, sys)

    SIDE EFFECTS:
        Overwrites monster JSON data in place.

    ERROR HANDLING:
        Emits warnings and applies deterministic fallback selection for species missing canonical base rows.

    NOTES:
        Preserves MoveCatalog while restructuring Pokemon entries.

    FUNCTION: main

    DESCRIPTION:
        Loads flattened entries, groups by canonical species, merges forms, sorts by pokedex number, and writes transformed output.

    INPUT:
            - src/monster.json data model

    OUTPUT:
        Updated nested Pokemon JSON payload.

    SIDE EFFECTS:
        Rewrites monster file.

    FUNCTION: merge_group

    DESCRIPTION:
        Constructs one canonical species object by selecting a base entry and attaching form variants.

    INPUT:
            - canonical species key
            - grouped variant members

    OUTPUT:
        Dict containing merged species data and alternate forms.

    SIDE EFFECTS:
        None (pure transform for provided inputs).

TOOL: tools/sync_pokemon_from_graphics.py

    PURPOSE:
        Synchronizes Pokemon species data from sprite folders and PokeAPI, then rewrites Pokemon section of monster.json using nested forms.

    USAGE:
        python3 tools/sync_pokemon_from_graphics.py

    INPUT:
            - src/Graphics/Pokemon/Front/*
            - src/Graphics/Pokemon/Back/*
            - src/monster.json (for MoveCatalog preservation)
            - tools/.pokeapi_cache.json (optional cache)

    OUTPUT:
            - Updated src/monster.json Pokemon section
            - Updated tools/.pokeapi_cache.json cache entries
            - Progress/warning logs

    DEPENDENCIES:
            - Python 3 standard library
            - Network access to pokeapi.co
            - ThreadPoolExecutor for parallel fetches

    SIDE EFFECTS:
        Performs network requests and writes cache/data files.

    ERROR HANDLING:
        Handles HTTP 404 and cache misses gracefully; emits warnings and continues where possible.

    NOTES:
        Normalizes naming and form variants (female/male/shadow/numeric) during merge.

    FUNCTION: main

    DESCRIPTION:
        Discovers sprites, resolves API metadata, merges grouped forms, and writes regenerated Pokemon payload.

    INPUT:
            - Local sprite metadata
            - API/cache records

    OUTPUT:
        Regenerated Pokemon section with preserved MoveCatalog.

    SIDE EFFECTS:
        Concurrent API reads and file writes.

    FUNCTION: fetch_pokemon

    DESCRIPTION:
        Fetches one API Pokemon payload with cache lookup/update behavior.

    INPUT:
            - api_name: str
            - cache: Dict[str, Any]

    OUTPUT:
        Parsed species dict or None when unavailable.

    SIDE EFFECTS:
        Mutates cache and may perform network I/O.

TOOL: tools/events_launcher_modal.py

    PURPOSE:
        EventsLauncherModal — UI-Standard launcher modal (FEATURE-MAP-064/100). Opened by the E
        toolbar button (LMB) or V key (`open_events_launcher`). Presents Event Engine |
        Wild Encounters · Audio Engine | Battle Editor · NPC Sprites (full width) · Help (full width).

    USAGE:
        Instantiated in MapEditor.__init__. Opened via events_btn_rect LMB or V key.
        Calls ed.event_engine_modal.open_modal(), ed.wild_encounter_modal.open_modal(),
        ed.audio_engine_modal.open_modal(), ed.battle_editor_modal.open_modal(),
        ed.npc_sprite_editor_modal.open_modal(), or
        ed._open_help_overlay(tab="home", back_to="launcher") on button press.

    INPUT:
        Mouse events (down/up/motion/wheel) and keyboard events routed from map_editor.py.

    OUTPUT:
        Renders launcher overlay on ed.screen.

    DEPENDENCIES:
            - pygame
            - tools/map_editor.py (MapEditor reference)
            - tools/event_engine_modal.py (EventEngineModal)
            - tools/wild_encounter_modal.py (WildEncounterModal)
            - tools/audio_engine_modal.py (AudioEngineModal)
            - tools/battle_editor_modal.py (BattleEditorModal)
            - tools/npc_sprite_editor_modal.py (NpcSpriteEditorModal)

    SIDE EFFECTS:
        Opens or closes peer modals; updates _panel_override (session-persisted).

    ERROR HANDLING:
        Returns False from handlers when modal is not open.

    NOTES:
        UI-Standard minimum panel 640×480; BR+BL resize grips; title-bar drag-to-move.
        Replaces the old events_tool_popover. FEATURE-MAP-098: Wild Encounters RMB opens
        main-map canvas wild patch paint (`MapEditor._open_wild_canvas_mode`); LMB opens the
        full WildEncounterModal.

TOOL: tools/event_engine_modal.py

    PURPOSE:
        EventEngineModal — UI-Standard 3-panel modal for editing map events and their scripts
        on any map. Left column: map search, clickable mini-map (thumbnail + 2×2 hulls,
        click sets selected event anchor), map list, and events list with cascade RMB menu.
        Middle: nested block editor with subflow tabs and configurable cascade RMB menu via
        event_script_ctx_menu. Right: opcode documentation. Session undo/redo: Ctrl+Z / Ctrl+Y
        (depth 50). FEATURE-MAP-069, FEATURE-MAP-070, Phase 3 rebuild.

    USAGE:
        Instantiated in MapEditor.__init__. Opened via EventsLauncherModal Event Engine button
        or event_engine_modal.open_modal().

    INPUT:
        Mouse (down/up/motion/wheel) and keyboard events routed from map_editor.py.

    OUTPUT:
        Renders the 3-panel overlay on ed.screen. Persists event JSON via ed.write_map_events
        and script JSON via event_script_schema.write_document_to_path. Persists splitter
        fractions, favorites, and optional contextMenuEvents/contextMenuBlocks in eventEngine.

    DEPENDENCIES:
            - pygame
            - tools/event_script_schema.py (steps<->tree, default args, validation, file IO)
            - tools/event_script_opcode_docs.py (structured documentation lines)
            - tools/event_script_ctx_menu.py (cascade RMB menus for events + blocks)
            - tools/map_editor.py (config_get/set_section, list_all_map_ids, read/write_map_events,
              map_dims, _thumbnail_surface_for_map_stem, event_place_modal, event_sprite_modal,
              events_launcher_modal)

    SIDE EFFECTS:
        Writes map JSON, script JSON, and map_editor_config.json. On Rename: renames the script
        file on disk (src/maps/scripts/{map}/{old}.json -> {new}.json) and updates ev["id"] and
        ev["script"]["path"] before persisting. May switch the main editor's loaded map when
        eventEngine.selectSwitchesMainMap is enabled.

    ERROR HANDLING:
        Refuses to save scripts with unbalanced control-flow blocks (validate_balanced) and
        reports via ed.set_status. Rename rejects empty, duplicate, or colliding file targets
        and reports via status. Tree helpers drop stray terminators defensively.

    NOTES:
        Minimum panel 640×480 (UI-Standard). Session undo stacks capped at 50; cleared on modal close
        or map switch. `_begin_submodal_edit()` checkpoints before View in Map / Assign Sprite;
        sub-modals call `engine._undo_checkpoint()` on action/trigger Save. Context menu config:
        eventEngine.contextMenuEvents, eventEngine.contextMenuBlocks (falls back to
        eventScriptEditor.contextMenu for blocks).

    NOTES:
        Four draggable splitters (left|middle, middle|right, map|events, blockeditor|actions).
        All regions are clamped to minimum sizes every frame so nothing is clipped on shrink.
        FEATURE-MAP-070: unified Delete button label changes to Delete (N) when 2+ checkboxes
        are active; _delete_targets() resolves the set of indices to remove. Rename (RMB ->
        Rename) activates an inline text field on the event row; Enter commits, Esc cancels.
        FEATURE-MAP-074: subflow tab strip at the top of the middle panel with a far-left
        library/search menu and a per-tab RMB context menu (Close / Close All But This /
        Close All / Rename / Save). `self.flows` holds main + named subflows; `@property tree`
        proxies the active flow for backward compatibility. Per-event subflows persist under
        the script file's `subflows`; global connectors live in src/maps/scripts/_library/.
        Load/persist round-trip via event_script_schema.read_flows_from_path /
        write_flows_to_path.
        FEATURE-MAP-076: region (collapsible/renamable/nestable), comment, and label palette
        actions and rendering (collapse carets, distinct comment cards). FEATURE-MAP-077:
        set_var/if_var/end_if_var blocks. `labels_in_active_flow()` feeds the goto dropdown.
        FEATURE-MAP-079: documentation panel is collapsible with search + scroll and a pop-out
        button (EventDocPopoutModal); RMB -> "Edit in modal" opens EventActionModal.
        FEATURE-MAP-078: event RMB -> "Change Trigger" opens EventTriggerModal.
        FEATURE-MAP-080: registry button opens EventFlagRegistryModal.
        FEATURE-MAP-079: collapsible map picker and events list (left_collapsed) with relayout
        clamping (_draw_left_collapsed).
        FEATURE-MAP-081: documentation panel layout-level collapse (22px strip with expand + Pop
        buttons, mid_w absorbs freed width, mirrors left_collapsed). Collapsible action categories
        (caret headers, indented op rows, auto-expand on search, persisted in config). Paired
        palette ordering (opener then end_*). Block nesting via _insert_target_for_selection
        (open block selected -> append as last child). Region blocks display args.name. Bare end_*
        drags rejected with red flash + status bar warning. call_subflow picker routes to
        in-file subflows + _library connectors.

TOOL: tools/event_place_modal.py

    PURPOSE:
        EventPlaceModal — UI-Standard "View in Map" sub-modal. Renders the selected map (via the
        map editor thumbnail surface, so it works for any map without disturbing the session) and
        lets the user click a tile to set the selected event's 2x2 anchor. FEATURE-MAP-069.

    USAGE:
        Instantiated in MapEditor.__init__. Opened by EventEngineModal RMB -> View in Map via
        event_place_modal.open_for(map_id, event_index).

    INPUT:
        Mouse (down/up/motion/wheel) and keyboard events routed from map_editor.py.

    OUTPUT:
        On Save, writes events back via ed.write_map_events and calls
        ed.event_engine_modal.refresh_after_submodal(). Returns to the Event Engine on close.

    DEPENDENCIES:
            - pygame
            - tools/map_editor.py (read_map_events, write_map_events, map_dims,
              _thumbnail_surface_for_map_stem, event_engine_modal)

    SIDE EFFECTS:
        Writes map JSON on Save only (Cancel discards). Reopens the Event Engine on close.

    ERROR HANDLING:
        No-ops when the map has no preview or no event is selected; clamps anchor to bounds.

    NOTES:
        Wheel zooms (cursor-anchored), right-drag pans, left-click places. Fit-to-body on open.

TOOL: tools/event_sprite_modal.py

    PURPOSE:
        EventSpriteModal — UI-Standard "Assign Sprite" sub-modal. Assigns a sprite to the
        selected event: kind selector (character / pokemon_icon / pokemon_icon_shiny), a
        searchable PNG list, and for characters a 4x4 frame grid plus facing selection.
        FEATURE-MAP-069.

    USAGE:
        Instantiated in MapEditor.__init__. Opened by EventEngineModal RMB -> Assign Sprite via
        event_sprite_modal.open_for(map_id, event_index).

    INPUT:
        Mouse (down/up/motion/wheel) and keyboard events routed from map_editor.py.

    OUTPUT:
        On Save, writes ev["sprite"] and persists via ed.write_map_events, then calls
        ed.event_engine_modal.refresh_after_submodal().

    DEPENDENCIES:
            - pygame
            - tools/map_editor.py (_graphics_dir_for_kind, _list_png_names_cached,
              _get_character_frame_surface, read/write_map_events, event_engine_modal)

    SIDE EFFECTS:
        Writes map JSON on Save only. Reopens the Event Engine on close.

    ERROR HANDLING:
        Skips preview rendering when an image cannot be loaded; clamps frame index to the sheet.

    NOTES:
        Character sprites use a 4x4 sheet (sheetColumns/sheetRows = 4); facing maps to a row.

TOOL: tools/event_doc_popout_modal.py

    PURPOSE:
        EventDocPopoutModal — FEATURE-MAP-079 UI-Standard full-window opcode documentation
        reader. Left list of opcodes (searchable), right pane with structured docs for the
        selection. Opened from the Event Engine documentation panel "pop out" button for
        easier reading than the narrow in-modal column.

    USAGE:
        Instantiated in MapEditor.__init__. Opened via open() / open_for(op) from
        EventEngineModal.

    INPUT:
        Mouse (down/up/motion/wheel) and keyboard events routed from map_editor.py.

    OUTPUT:
        Renders a full-window overlay on ed.screen. Read-only (no persistence).

    DEPENDENCIES:
            - pygame
            - tools/event_script_opcode_docs.py (structured documentation lines)
            - tools/event_script_schema.py (opcode list)

    SIDE EFFECTS:
        None (read-only viewer).

    ERROR HANDLING:
        Empty search yields the full list; unknown selection shows a placeholder.

    NOTES:
        Search filters the opcode list live; scroll wheel scrolls the active pane.

TOOL: tools/event_action_modal.py

    PURPOSE:
        EventActionModal — FEATURE-MAP-079 UI-Standard editor for a single script action's
        arguments. Per-arg type-aware fields (int/string/bool), a variable/flag picker with
        create option, a `goto` label dropdown (labels in the current flow), and editable
        key/value rows for `call_subflow` `vars`. Inline editing in the block list remains
        available; this modal is the richer alternative ("Edit in modal").

    USAGE:
        Instantiated in MapEditor.__init__. Opened via open_for(engine, flow_name, node_path)
        from EventEngineModal (RMB -> Edit in modal).

    INPUT:
        Mouse (down/up/motion/wheel) and keyboard events routed from map_editor.py.

    OUTPUT:
        On Apply, writes the edited args back into the engine flow node and triggers the
        engine to persist the script.

    DEPENDENCIES:
            - pygame
            - tools/event_script_schema.py (opcode arg metadata, labels_in_steps)
            - tools/event_script_op_meta.json (per-field types/help via opcode docs)
            - tools/flag_registry_modal.py (flag/variable names for the picker)

    SIDE EFFECTS:
        Mutates the target flow node; calls `engine._undo_checkpoint()` before apply; persists script JSON (via the engine).

    ERROR HANDLING:
        Coerces field text to the declared type; invalid ints fall back to 0; unknown labels
        are left as free text.

    NOTES:
        Minimum panel 640×480; BR+BL resize grips; title-bar drag. `call_subflow` arg rows support add/remove; `goto` shows a dropdown of in-flow labels.
        FEATURE-MAP-081: `call_subflow` name picker now lists in-file subflows + _library
        connectors via `ess.list_library_subflow_names()` instead of opening the flag/variable
        registry. Sentinel "(no subflows)" is a no-op on selection.

TOOL: tools/event_trigger_modal.py

    PURPOSE:
        EventTriggerModal — FEATURE-MAP-078 UI-Standard editor for an event's trigger. Selects
        trigger type (interact / step_on / on_map_enter / on_condition), an optional flag
        run-condition, the cleared flag, and on-complete set/clear flag lists.

    USAGE:
        Instantiated in MapEditor.__init__. Opened via open_for(map_id, event_index) from the
        Event Engine event context menu (RMB -> Change Trigger).

    INPUT:
        Mouse (down/up/motion/wheel) and keyboard events routed from map_editor.py.

    OUTPUT:
        On Save, writes ev["trigger"], ev["clearedFlag"], and ev["onComplete"] and persists via
        ed.write_map_events, then calls ed.event_engine_modal.refresh_after_submodal().

    DEPENDENCIES:
            - pygame
            - tools/map_editor.py (read/write_map_events, event_engine_modal)
            - tools/flag_registry_modal.py (flag picker for condition/onComplete)

    SIDE EFFECTS:
        Calls `engine._undo_checkpoint()` before apply; writes map JSON on Save only. Reopens the Event Engine on close.

    ERROR HANDLING:
        Defaults to interact when type is unset; empty condition flag means "always".

    NOTES:
        Minimum panel 640×480; BR+BL resize grips; title-bar drag. Mirrors the C++ MapEventTrigger semantics validated by validate_map_events.py.
        FEATURE-MAP-083: field heights use `mtext.form_field_h(ed.font_small)` and row gaps
        use `mtext.FORM_ROW_GAP` / `mtext.FORM_SECTION_TOP` for consistent vertical rhythm.

TOOL: tools/flag_registry_modal.py

    PURPOSE:
        EventFlagRegistryModal — FEATURE-MAP-080 UI-Standard manager for the global flag and
        variable registry (src/maps/scripts/flag_registry.json). Declare/list/rename flags and
        variables and set initial values. Also exposes shared helpers (load_registry,
        save_registry, ensure_flag, ensure_variable, flag_names, variable_names) used by the
        action/trigger modals to populate pickers.

    USAGE:
        Instantiated in MapEditor.__init__. Opened from the Event Engine (registry button).
        Helper functions are imported by event_action_modal.py and event_trigger_modal.py.

    INPUT:
        Mouse (down/up/motion/wheel) and keyboard events routed from map_editor.py.

    OUTPUT:
        Reads/writes src/maps/scripts/flag_registry.json ({version, flags[], variables[]}).

    DEPENDENCIES:
            - pygame
            - json / pathlib (registry IO)

    SIDE EFFECTS:
        Writes flag_registry.json on save. Flags here define defaults overlaid by the C++
        GameState at load; variables are scratch-only (typed declarations).

    ERROR HANDLING:
        Rejects empty/duplicate names; missing/invalid registry file falls back to empty lists.

    NOTES:
        The registry is the editor-side source of truth for default flag values; the C++
        GameState (FEATURE-MAP-072) reads the same file for initial state.
        FEATURE-MAP-083: list row field heights use `mtext.form_field_h(ed.font_small)`
        (vertically centered in each row); scroll speed uses the same metric.

TOOL: .cursor/rules/UI-Standard-Rule.mdc

    PURPOSE:
        Cursor rule that mandates all new or reworked editor modals follow the
        WildEncounterModal standard: full-screen canvas, _panel_override, _drag_mode,
        draggable title bar, BR+BL resize grips, minimum 640x480, size-before-position
        clamping, standalone class file, input routed from map_editor.py.
        FEATURE-MAP-067.

    USAGE:
        Enforced automatically by Cursor on any PR or agent task that introduces or
        modifies a modal. Reference implementation: tools/wild_encounter_modal.py.

    INPUT:
        N/A (cursor rule instructions).

    OUTPUT:
        Guides Cursor agent to produce UI-standard-compliant modal implementations.

    DEPENDENCIES:
        tools/wild_encounter_modal.py (reference implementation).

    SIDE EFFECTS:
        None by itself; future modal implementations must comply.

    ERROR HANDLING:
        N/A.

    NOTES:
        Added as FEATURE-MAP-067 to enforce consistent UI across all editor modals.

TOOL: .cursor/skills/planning-rule/SKILL.md

    PURPOSE:
        Cursor Agent Skill for the planning tool / Plan mode: minimal complete plans plus repository-wide execution rules (docs, tracker, correctness, security, concise output).

    USAGE:
        Rely on skill discovery when using Cursor’s planning workflow, or attach the skill when asking for a plan before implementation.

    INPUT:
        User task context; repository conventions in `/docs/source_doc.md`, `/docs/tools_doc.md`, and `/docs/tracker.md`.

    OUTPUT:
        Plans and subsequent changes that satisfy the skill’s plan shape and checklist.

    DEPENDENCIES:
        Cursor skills mechanism; Cursor planning UI (planning tool / Plan mode).

    SIDE EFFECTS:
        None by itself; follow-on implementation may modify source, tools, and documentation per project rules.

    ERROR HANDLING:
        N/A (markdown instructions).

    NOTES:
        Introduced as FEATURE-CURSOR-001 (`aligned-core-behavior`); renamed and retargeted in IMPROVEMENT-CURSOR-001.

TOOL: .cursor/skills/bug-checking/SKILL.md

    PURPOSE:
        Cursor Agent Skill for disciplined bug investigation: log-first workflow aligned with Logging-Rule, reproduce before change, trace to a specific root cause, minimal fix, mandatory verification, and tracker/docs follow-up.

    USAGE:
        Rely on skill discovery when debugging or fixing defects, or attach the skill when the user wants strict root-cause and minimal-diff behavior.

    INPUT:
        Failing behavior, reproduction steps, and repository conventions in `/docs/tracker.md`, `.cursor/rules/Logging-Rule.mdc`, `/docs/source_doc.md`, and `/docs/tools_doc.md`.

    OUTPUT:
        Evidence-backed diagnosis, smallest appropriate code or config change, updated tracker entry, doc updates when source/tools change, and the skill’s ISSUE/ROOT CAUSE/FIX/VALIDATION summary block.

    DEPENDENCIES:
        Cursor skills mechanism; project Logging-Rule and documentation layout.

    SIDE EFFECTS:
        None by itself; follow-on work updates tracker entries and may modify source, tools, and documentation.

    ERROR HANDLING:
        N/A (markdown instructions).

    NOTES:
        Added under FEATURE-CURSOR-002; complements `.cursor/skills/planning-rule/SKILL.md` for non-planning bugfix sessions.

TOOL: tools/audio_engine_modal.py

    PURPOSE:
        FEATURE-MAP-087: Audio Engine UI for assigning `musicTrack` on any map with independent scope and pygame.mixer preview.

    USAGE:
        Open from Events launcher → Audio Engine.

    INPUT:
        Map list, track list from `src/audio/*.ogg`, user Play/Stop/Assign/Clear actions.

    OUTPUT:
        Writes `musicTrack` stem to selected map JSON via `MapEditor.write_map_music_track`.

    DEPENDENCIES:
        pygame, modal_text, MapEditor helpers.

    SIDE EFFECTS:
        May init pygame.mixer on open; updates map JSON on disk.

    ERROR HANDLING:
        Preview errors surface via `set_status`; missing files skipped in track list.

    NOTES:
        Minimum panel 640×480; BR+BL resize grips. Back/Help wire `back_to="audio"` on help overlay.

TOOL: tools/battle_editor_modal.py

    PURPOSE:
        FEATURE-MAP-088: CRUD UI for reusable trainer battles under `src/maps/scripts/_library/battles/*.json`.
        Phase 5: full editable detail panel (id, music, background, outcomeMode, scriptedLossTurns,
        trainers 1–2, party 1–6 with species picker and level +/-).

    USAGE:
        Open from Events launcher → Battle Editor; Save persists JSON; list selects battle id.

    INPUT:
        Battle list, inline edits to normalized battle dict.

    OUTPUT:
        `battles/<id>.json` library files consumed by `start_trainer_battle` opcode.

    DEPENDENCIES:
        event_script_schema battle helpers, MapEditor species/audio lists, modal_text.

    SIDE EFFECTS:
        Creates/updates battle JSON files on save.

    ERROR HANDLING:
        Save failures reported via status line; invalid JSON on load falls back to defaults.

    NOTES:
        Minimum panel 640×480; BR+BL resize. `start_trainer_battle` args also editable in EventActionModal.

TOOL: tests/test_phase7_verify.py

    PURPOSE:
        FEATURE-MAP-096 Phase 7: automated verification matrix — subprocess checks for `make`,
        `make test`, opcode extract/audit, validate_map_events, migrate dry-run, AST parse of core
        modals, and headless proxy checks for the manual UI matrix (launcher entry, Event Engine
        symbols, Help/Settings, satellite modals).

    USAGE:
        `python3 -m unittest tests.test_phase7_verify -v`

    INPUT:
        Repository root with built C++ binaries (`make` / `make test`).

    OUTPUT:
        unittest pass/fail; subprocess stdout/stderr on failure.

    DEPENDENCIES:
        Python 3 unittest, subprocess, ast; project Makefile and tools/*.py scripts.

    SIDE EFFECTS:
        None (read-only except invoking build/test commands).

    ERROR HANDLING:
        Asserts non-zero exit codes and missing symbols with assertion messages.

    NOTES:
        Phase 7 SDL/trigger deferrals are closed by tests/test_phase8_verify.py (Phase 8).

TOOL: tests/test_phase8_verify.py

    PURPOSE:
        FEATURE-MAP-096 Phase 8: closes Phase 7 deferrals — headless SDL draw smoke at 800×600
        and 1280×800 for Events satellite modals and Help tabs; map undo regression; world
        workspace draw; runtime audit for trigger/battle handlers in map_view.cpp/game.cpp plus
        `make test`.

    USAGE:
        `SDL_VIDEODRIVER=dummy python3 -m unittest tests.test_phase8_verify -v`

    INPUT:
        Repository root; pygame with dummy video driver (set automatically in the test module).

    OUTPUT:
        unittest pass/fail.

    DEPENDENCIES:
        pygame, MapEditor, subprocess make/audit scripts, src/map_view.cpp, src/game.cpp.

    SIDE EFFECTS:
        Creates pygame display surfaces; runs C++ unit tests via make test.

    ERROR HANDLING:
        Asserts on panel rect clipping, missing C++ symbols, or non-zero subprocess exits.

    NOTES:
        Requires dummy SDL driver for CI/headless environments. Full interactive mouse/keyboard
        matrix still optional for human QA; this phase automates layout and handler contracts.

TOOL: docs/cursor_helper_scripts/generate_github_guide_pdf.py

    PURPOSE:
        Build the printable Git/GitHub workflow and fresh-environment setup guide PDF for this
        repository (`docs/github-and-setup-guide.pdf`).

    USAGE:
        python3 docs/cursor_helper_scripts/generate_github_guide_pdf.py

    INPUT:
        Embedded guide content in the script (branch model, glossary, clone/build/test steps,
        commit/pull/push/merge/reset commands).

    OUTPUT:
        `docs/github-and-setup-guide.pdf` (multi-page reference document).

    DEPENDENCIES:
        Python 3, fpdf2 (`python3 -m pip install --user fpdf2`).

    SIDE EFFECTS:
        Overwrites `docs/github-and-setup-guide.pdf` when run.

    ERROR HANDLING:
        Exits with traceback if fpdf2 is missing or PDF write fails.

    NOTES:
        Regenerate after changing project branch policy or setup steps. Uses ASCII-only text for
        Helvetica/Courier core fonts.

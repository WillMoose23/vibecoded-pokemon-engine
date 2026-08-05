FILE: src/main.cpp

    PURPOSE:
        Program entry point that constructs `Game` and starts the runtime loop.

    DEPENDENCIES:
            - game.h

    KEY COMPONENTS:
            - main()

    NOTES:
        Startup is intentionally minimal; all subsystem setup is delegated to `Game`.

    FUNCTION: main

    SIGNATURE:
        int main()

    DESCRIPTION:
        Creates a `Game` instance, runs the loop, and returns a process exit code.

    PARAMETERS:
        None

    RETURNS:
        int - Process status code (`0` on normal completion).

    SIDE EFFECTS:
        Opens the SDL application through `Game::run()`.

    ERROR HANDLING:
        Uses `Game` internal error reporting; `main` does not catch exceptions itself.

    DEPENDENCIES:
            - Game::run

FILE: include/map_data.h

    PURPOSE:
        Defines map-loading data models consumed by runtime map and overworld renderers.

    DEPENDENCIES:
            - nlohmann::json
            - C++ STL containers

    KEY COMPONENTS:
            - struct TilesetDef
            - struct MapCell
            - struct TileLayer (`applyOverPlayer` + `cells`)
            - struct MapEventSpriteRef (`kind`, `file`, `frame`, sheet dimensions, optional `facing` for character walk rows)
            - struct WildEncounterSpeciesEntry / struct WildEncounterPatch
            - struct MapEventInstance / struct MapData
            - loadTilesetRegistry
            - loadMapFromFile
            - loadMapById

    NOTES:
        FEATURE-MAP-050: optional top-level `wildPatches[]` (id, `stepChancePercent` 0–100, `encounters.{common,uncommon,rare}` arrays of `{species,weight}`) and `layers.wildEncounter` int grid (0 = none, 1..N = 1-based index into `wildPatches`).
        FEATURE-MAP-058: optional `wildGlobalEncounters` top-level JSON field with the same `{common,uncommon,rare}` tier structure. Loaded into `MapData.globalCommon/Uncommon/Rare`. Global species are merged into each patch's tier pool at roll time (local entries win on duplicate species).
        IMPROVEMENT-MAP-042 adds `TileLayer.applyOverPlayer` (default true) to let selected layers bypass over-player rendering even when the `layers.overPlayer` grid cell at (x, y) is 1.
        Supports layered tiles, walkability grid, transparency grid, map exits/connections, and FEATURE-MAP-030 **`events[]`** (2×2 interactable regions, optional `script.path` relative to `src/maps/`, optional `sprite` with `kind`/`file` and for `character` sheets optional `frame` (0-based row-major), `sheetColumns`/`sheetRows`, defaulting to 4×4).
        FEATURE-MAP-078: event triggers. `enum class MapEventTrigger { Interact, StepOn, OnMapEnter, OnCondition }` and `MapEventInstance` gains `trigger` (default `Interact`), `conditionFlag` + `conditionWantSet` (run-gate), `clearedFlag` (auto-derived if absent; "already ran" gate), and `onCompleteSetFlags` / `onCompleteClearFlags` (applied on script completion). Inline helper `mapEventIsSolid(ev)` reports whether an event blocks its footprint (true for `Interact`) so the player bumps into NPCs. `src/map_data.cpp` parses the `trigger` object (`type`, `condition.{flag,set}`), `clearedFlag`, and `onComplete.{setFlags,clearFlags}`.

FILE: src/map_data.cpp

    PURPOSE:
        Loads map JSON into `MapData` structures with schema validation and legacy compatibility; implements tileset registry loading.

    DEPENDENCIES:
            - map_data.h
            - nlohmann::json
            - iostream / filesystem / fstream

    KEY COMPONENTS:
            - readJsonFile
            - parseIntGrid
            - parseGroundCells
            - loadTilesetRegistry
            - loadMapFromFile
            - loadMapById

    NOTES:
        IMPROVEMENT-MAP-042 parses optional `tileLayers[].applyOverPlayer` and stores it in each `TileLayer`; omitted field defaults to true.
        FEATURE-MAP-049: optional `events[].sprite.facing` string is parsed into `MapEventSpriteRef::facing` for character sheets (selects walk row; `frame % sheetColumns` selects the animation column).
        FEATURE-MAP-050: parses `wildPatches` and `layers.wildEncounter`; validates cell indices against patch count; defaults both to empty when omitted.
        Supports modern layered schema, legacy compatibility paths, parsing **`events`** from map JSON (FEATURE-MAP-030), and optional `layers.overPlayer` (0 below player, non-zero above player).

    FUNCTION: loadMapFromFile

    SIGNATURE:
        bool loadMapFromFile(const std::string& path, MapData& out)

    DESCRIPTION:
        Reads map JSON, validates dimensions/layer payloads, and fills runtime map data including tile layers, walkability, transparency, over-player grid, exits, and events.

    PARAMETERS:
        - path: const std::string& - Absolute or relative path to map JSON file.
        - out: MapData& - Output structure populated on success.

    RETURNS:
        bool - True on valid load; false when file I/O or schema validation fails.

    SIDE EFFECTS:
        Writes diagnostics to stderr on invalid data; replaces fields inside `out`.

    ERROR HANDLING:
        Returns false for malformed JSON, missing required sections, invalid layer dimensions, or invalid typed fields.

    DEPENDENCIES:
            - readJsonFile
            - parseGroundCells
            - parseIntGrid
            - intGridToMapCells

    FUNCTION: loadTilesetRegistry

    SIGNATURE:
        bool loadTilesetRegistry(const std::string& path, std::vector<TilesetDef>& out)

    DESCRIPTION:
        Loads and validates tileset definitions from registry JSON into normalized runtime structs.

    PARAMETERS:
        - path: const std::string& - Registry file path.
        - out: std::vector<TilesetDef>& - Destination vector.

    RETURNS:
        bool - True when load/validation succeeds.

    SIDE EFFECTS:
        Clears and repopulates `out`.

    ERROR HANDLING:
        Returns false with stderr diagnostics on missing keys, parse failures, or invalid values.

    DEPENDENCIES:
            - readJsonFile
            - nlohmann::json object/array accessors

FILE: include/wild_encounter.h

    PURPOSE:
        Declares FEATURE-MAP-050 wild encounter roll helpers (step chance, tier 65/30/5, weighted species within tier).

    DEPENDENCIES:
            - map_data.h (WildEncounterPatch)
            - nlohmann::json (pokedex)

    KEY COMPONENTS:
            - rollWildEncounterSpecies

    NOTES:
        Species keys must exist under `Pokemon` in `monster.json` (same key as `kPokemonDbKey` in game.h).

FILE: src/wild_encounter.cpp

    PURPOSE:
        Implements tier and species RNG for wild patches after a successful step-chance roll.

    DEPENDENCIES:
            - wild_encounter.h
            - game.h (`kPokemonDbKey`)
            - helperMethods `random(int,int)` (declared in cpp)

    FUNCTION: rollWildEncounterSpecies

    SIGNATURE:
        std::optional<std::string> rollWildEncounterSpecies(
            const WildEncounterPatch& patch, const MapData& mapData, const nlohmann::json& pokedb)

    DESCRIPTION:
        Rolls 1–100 against `patch.stepChancePercent`; on success picks tier (65% common, 30%
        uncommon, 5% rare). Merges the patch's local tier list with the map-wide global tier list
        from `mapData.globalCommon/Uncommon/Rare` — any global species whose name appears in the
        local list is excluded (local wins). Selects species by weighted random from the merged
        list; invalid or zero-weight species are skipped.

    PARAMETERS:
        - patch: const WildEncounterPatch& — per-patch encounter tables and step rate.
        - mapData: const MapData& — provides global tier lists for FEATURE-MAP-058 merge.
        - pokedb: const nlohmann::json& — full monster DB used for species validation.

    RETURNS:
        std::optional<std::string> — species key or nullopt if any roll fails or merged tier empty.

    SIDE EFFECTS:
        Logs once to stderr when the merged tier table is empty.

    ERROR HANDLING:
        Returns nullopt on failed step roll, empty merged tier, or no positive-weight valid species.

    DEPENDENCIES:
            - random()
            - kPokemonDbKey
            - MapData (globalCommon, globalUncommon, globalRare)

FILE: src/map_view.cpp

    PURPOSE:
        Draws single-map and world-layout map views (split below-player/above-player tile passes), map picker UI, FEATURE-MAP-029 composite **Overworld** from `world_layout.json`, tileset texture caching, player movement, camera follow, and map event scripts in ViewMap/ViewWorld.

    DEPENDENCIES:
            - include/game.h
            - include/map_data.h
            - SDL2 render API, SDL_image, filesystem/ifstream, nlohmann::json (via `game.h`)

    KEY COMPONENTS:
            - finalizeMapCatalogForPicker_
            - loadMapCatalog_
            - loadMapForView_
            - loadWorldLayoutForView_
            - clearWorldLayoutView_
            - loadOverworldViewConfig_
            - resolveWarpPlayerAnchor_
            - executePendingMapWarp_
            - warpPlayerViaWorldLayoutIfPresent_
            - spawnPlayerOnLoadedMap_
            - spawnPlayerOnWorldLayout_
            - requestPlayerMoveOnMap_
            - tickMapPlayerWalk_
            - clearMapScriptDriveAndCameraState_
            - tryMapViewerScriptOpcode_
            - worldWalkabilityBlocksAt_
            - overPlayerGridMatchesMap_
            - drawMapPicker_
            - drawMapView_
            - drawWorldLayoutView_
            - drawMapEventSprites_
            - drawWorldLayoutEventSprites_
            - tryWildEncounterOnStep_
            - intLayerGridDimsMatchMap_ (file-local): shared height/width validation for int grids (`walkabilityLayer`, `overPlayerLayer`); REFACTOR-CPP-PY-001.

    NOTES:
        FEATURE-MAP-050: after a completed walk segment in `commitCompletedMapWalk_`, `tryWildEncounterOnStep_` reads `wildEncounterLayer` at the player anchor tile (ViewMap / world instance under anchor), rolls via `rollWildEncounterSpecies`, and calls `startOverworldWildBattle_`. `loadOverworldViewConfig_` loads optional `playerSpeciesKey` for battle player species.
        IMPROVEMENT-MAP-042 applies `TileLayer.applyOverPlayer` during both single-map and world draw passes: over-player pass draws only layers with flag on; layers flagged off stay in below-player pass.
        BUG-MAP-026: **L** toggles the same `overworldTileGridVisible_` flag in **ViewMap** as in **ViewWorld**; single-map tile outlines are skipped when the flag is false (`Game::drawMapView_` / `Game::handleMapUiKey_`).
        BUG-MAP-027: `Game::loadMapForView_` must call `destroyMapViewTextures_` before `loadOverworldViewConfig_` so `reloadMapPlayerSpriteTexture_` is not immediately invalidated; matches `loadWorldLayoutForView_` ordering.
        BUG-MAP-054: `executePendingMapWarp_` and `warpPlayerViaWorldLayoutIfPresent_` call `resolveWarpPlayerAnchor_` and reset walk parity after warp.
        FEATURE-MAP-047: `warp_player` resolves `mapId` against `world_layout.json` when present so warps target the **overworld** placement (map-local x,y on the placed instance) instead of opening the isolated single-map viewer.
        FEATURE-MAP-049: `Game::tryMapViewerScriptOpcode_` implements `camera_follow_player` (clears scripted camera tile offset and in-progress `move_camera` pan state, then re-syncs camera follow). `drawMapEventSprites_` / `drawWorldLayoutEventSprites_` honor `MapEventSpriteRef::facing` for character sheets when choosing the source cell row.
        Reads viewport/player footprint config from `src/overworld_view.json` (FEATURE-MAP-031: optional `playerSprite`, `playerWalkFrameMs`, `playerDrawOffsetTilesX` horizontal sprite offset in tile widths; 4×4 sheet rows S/A/D/W; walk frames per tracker). IMPROVEMENT-MAP-035: optional `playerCollisionOffX`, `playerCollisionOffY`, `playerCollisionW`, `playerCollisionH` define the collision sub-rectangle relative to the visual anchor top-left (defaults: offX=0, offY=1, W=1, H=1 — bottom-left 1×1 cell); the rect is clamped to fit within the visual footprint on load.
        FEATURE-MAP-029: `finalizeMapCatalogForPicker_` prepends sentinel id `__overworld__` / label **Overworld** and removes duplicate `world_layout` stem; `loadWorldLayoutForView_` parses version `1` JSON, loads one `MapData` per `renderOrder` instance (duplicate `mapId` get separate copies), uses `compositeBounds` when present, and keeps rendering on the main SDL thread (no worker render thread).
        FEATURE-MAP-030: **Q** in map/overworld viewer starts or advances event scripts when not in battle (battle keeps Q as move slot 0). `handleMapUiKey_` / per-frame tick runs `ScriptRuntime`.
        FEATURE-MAP-031: **WASD** call `requestPlayerMoveOnMap_` with SDL key repeat for two-tile merge; `tickMapPlayerWalk_` advances frames and commits tile position at segment end; **Q** only when not mid-walk.
        FEATURE-MAP-048: scripted `walk_to_coords` / `run_to_coords` set `mapScriptBlockingWalk_` so WASD is ignored while the opcode holds `pc`; `requestPlayerMoveOnMap_(…, scriptDrive=true)` bypasses that lock for internal path steps. `move_camera` / zoom adjust `mapScriptCameraOffsetTiles*` and `mapViewDrawZoom_` during draw; state clears when the script ends or map UI reloads.
        FEATURE-MAP-071: `walk_to_coords` / `run_to_coords` now use direction+steps rail movement instead of (x,y) coordinate targeting. `mapScriptDriveTargetX_/Y_` replaced by `mapScriptDriveStepsRemaining_`, `mapScriptDriveStepDx_`, `mapScriptDriveStepDy_`. `computeScriptWalkStrideTowardTarget_` replaced by `parseScriptDirectionToDelta_` (static). On first activation the direction is parsed, `faceFirst` applied if requested, and the step countdown set; each frame one stride is requested along the fixed axis; blocked footprint finishes early. `steps:0` with `faceFirst:true` is a turn-only with no movement.
        FEATURE-MAP-072/073/074: `wireMapScriptCallbacks_` binds `onReadFlag`/`onWriteFlag` to `gameState_` (writes call `flushIfDirty`) and `onLoadLibrarySubflow` to `loadLibrarySubflow_` (reads `src/maps/scripts/_library/<name>.json`). `startMapScript_(path, ev)` records the firing `MapEventInstance` in `mapScriptEvent_`.
        FEATURE-MAP-078: event triggers. `tryStartNearbyMapScript_` only fires `Interact` events whose run-condition holds (`mapEventRunConditionOk_`) and cleared-gate is open (`mapEventClearedGate_`). `commitCompletedMapWalk_` calls `tryStepOnMapEvent_` (StepOn dispatch) before wild-encounter rolls. When idle with no active script, `tryFireAutoMapEvents_` fires eligible `OnMapEnter` / `OnCondition` events. On script finish, `applyMapScriptCompletion_` sets the event's `clearedFlag` and applies `onComplete` set/clear flags (persisted via `GameState`). `mapPlayerFootprintBlockedAt_` treats `mapEventIsSolid(ev)` events as blocking their 2×2 footprint so the player bumps into NPCs.
        BUG-MAP-021: `mapPlayerWalkVisualOffsetsTiles_` interpolates the in-stride anchor offset using elapsed time (`mapWalkFrameInSegment_` × frame duration + `mapWalkAccumNs_`) over the full segment duration (`frameCount` × frame duration), so camera and draw positions move smoothly across the two-tile span instead of jumping when the discrete animation frame index advances (frame-only blend was 0 or 1 for two-frame walks).
        IMPROVEMENT-DOC-004 / IMPROVEMENT-PERF-001: `drawWorldLayoutView_` evaluates each visible world cell by scanning `worldLayoutInstances_` in render order (O(visibleCells × instances × layers)); no profiling-backed world-cell index is implemented yet—see tracker if added later. Footer hint lines are cached via `bumpWorldLayoutViewFooterHintRevision_` / `bumpMapSingleViewFooterHintRevision_` after overworld JSON reload, successful `loadMapForView_`, and successful `loadWorldLayoutForView_`.


    FUNCTION: resolveWarpPlayerAnchor_

    SIGNATURE:
        void Game::resolveWarpPlayerAnchor_(int reqX, int reqY, int mapW, int mapH, int& outX, int& outY, int worldOriginX = 0, int worldOriginY = 0, bool footprintInWorldSpace = false) const

    DESCRIPTION:
        BUG-MAP-054: clamps a warp request to map bounds, then picks the nearest walkable player anchor (Manhattan rings) using map-local or world footprint checks.

    PARAMETERS:
        - reqX: int - requested anchor tile X
        - reqY: int - requested anchor tile Y
        - mapW: int - map width in tiles
        - mapH: int - map height in tiles
        - outX: int& - resolved anchor X
        - outY: int& - resolved anchor Y
        - worldOriginX: int - instance origin when footprintInWorldSpace is true
        - worldOriginY: int - instance origin when footprintInWorldSpace is true
        - footprintInWorldSpace: bool - use world walkability at origin+local coords

    RETURNS:
        void — writes outX/outY

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        Falls back to clamped coords if no walkable anchor is found.

    DEPENDENCIES:
        - mapPlayerFootprintBlockedAt_
        - worldPlayerFootprintBlockedAt_

    FUNCTION: overPlayerGridMatchesMap_

    SIGNATURE:
        bool overPlayerGridMatchesMap_(const MapData& m)

    DESCRIPTION:
        Validates that `m.overPlayerLayer` exactly matches map width/height before over-player draw-pass reads.

    PARAMETERS:
        - m: const MapData& - Map payload to validate.

    RETURNS:
        bool - `true` when grid dimensions match map dimensions.

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        Returns `false` for non-positive dimensions or row/height mismatch.

    DEPENDENCIES:
        `MapData`

    FUNCTION: Game::drawMapView_

    SIGNATURE:
        void Game::drawMapView_()

    DESCRIPTION:
        Draws visible map tiles, grid, player footprint overlay, and footer text for the current viewport. Footer text uses `mapSingleViewFooterHintScratch_` rebuilt when `mapSingleViewFooterHintRevision_` changes (IMPROVEMENT-PERF-001).

    PARAMETERS:
        None

    RETURNS:
        void - No return value.

    SIDE EFFECTS:
        Draws multiple rectangles/textures and updates no persistent data.

    ERROR HANDLING:
        Returns early when renderer unavailable.
        Skips missing layers/tiles/textures without aborting frame.

    DEPENDENCIES:
            - getOrLoadMapTilesetTexture_
            - findMapTilesetDef_

    FUNCTION: Game::loadWorldLayoutForView_

    SIGNATURE:
        bool Game::loadWorldLayoutForView_()

    DESCRIPTION:
        Loads `src/maps/world_layout.json` (schema version 1), builds `worldLayoutInstances_` in JSON `renderOrder`, loads each referenced `mapId` into its own `MapData`, computes world AABB from `compositeBounds` or from node footprints, then enters `MapUiMode::ViewWorld`, spawns the player from `originInstanceId` (fallback first instance), and rebuilds tileset render metadata.

    PARAMETERS:
        None

    RETURNS:
        bool — `true` when the composite is ready to draw; `false` on missing file, parse errors, unknown `renderOrder` ids, or missing map JSON.

    SIDE EFFECTS:
        Clears prior world instances, destroys map-view textures, repopulates `mapTilesetDefs_` / textures, sets `mapPickerLastError_` on failure, mutates `mapUiMode_`, camera, and player world-tile coordinates.

    ERROR HANDLING:
        On failure leaves the game in `PickMap`, clears partially built instances, and sets `mapPickerLastError_` for the picker UI.

    DEPENDENCIES:
            - loadTilesetRegistry
            - loadMapFromFile
            - walkabilityGridMatchesMap_
            - rebuildMapTilesetRenderMeta_
            - spawnPlayerOnWorldLayout_

    FUNCTION: Game::drawWorldLayoutView_

    SIGNATURE:
        void Game::drawWorldLayoutView_()

    DESCRIPTION:
        Draws the world-tile viewport for `ViewWorld`: for each visible cell, paints void color outside `worldBounds*`, then for each `WorldLayoutMapInstance` in `renderOrder` order draws overlapping map tiles from that instance’s `MapData` layers; optional per-tile outline when `overworldTileGridVisible_` is true (**L** toggles in `handleMapUiKey_`); draws the player footprint overlay, **FEATURE-MAP-030** event sprites (2×2 in world space, same sheet/frame rules as single-map view), script message overlay, and a footer hint. Loading overworld resets the grid to visible. Footer text uses `worldLayoutViewFooterHintScratch_` when `worldLayoutViewFooterHintRevision_` changes (IMPROVEMENT-PERF-001).

    PARAMETERS:
        None

    RETURNS:
        void

    SIDE EFFECTS:
        SDL draw calls only.

    ERROR HANDLING:
        Returns early when `renderer` is null; skips missing tileset metadata without aborting the frame.

    DEPENDENCIES:
            - mapTilesetRenderMeta_
            - mapCamTileX_/Y_ and mapPlayerTileX_/Y_ in world tile space

    FUNCTION: Game::requestPlayerMoveOnMap_

    SIGNATURE:
        void Game::requestPlayerMoveOnMap_(
            int deltaX, int deltaY, bool fromKeyRepeat, int walkChainContinueCol = -1, bool scriptDrive = false)

    DESCRIPTION:
        FEATURE-MAP-031: Starts or extends a walk segment along a cardinal direction. Each step moves the 2×2 footprint anchor by **two** map tiles (`kMapWalkAnchorStrideTiles`). The committed `mapPlayerTileX_`/`Y_` update only when the segment completes. Non-chained strides alternate **1,2** then **3,4** (columns 0–1 vs 2–3) via `mapWalkStepParity_`. BUG-MAP-020: When `commitCompletedMapWalk_` auto-chains while the same direction key is held, it calls with `walkChainContinueCol` set to the last sheet column of the finished segment and `fromKeyRepeat == false`, so the walk continues **n, n+1** (wrap mod 4) without treating the chain as an SDL repeat (which had incorrectly triggered the two-tile merge on frame 0 and caused stutter). A merged two-stride segment still applies only for real SDL key repeat on frame 0 (`fromKeyRepeat` true): **1,2,3,4,1** (five frames) when intermediate (+2) and final (+4) anchors are walkable. The sprite is drawn with horizontal offset `playerDrawOffsetTilesX_` × viewport tile pixel width (logical anchor unchanged). FEATURE-MAP-048: when `scriptDrive` is true, ignores `mapScriptBlockingWalk_` and `playerLocked` so scripted path steps can start while input is suppressed.

    PARAMETERS:
            - deltaX: int - Horizontal tile delta (-1, 0, or 1).
            - deltaY: int - Vertical tile delta (-1, 0, or 1).
            - fromKeyRepeat: bool - True for SDL key repeat events only (enables two-tile merge); false for internal auto-chain.
            - walkChainContinueCol: int - If >= 0, first walk column is this index and the second is `(col+1)%4` (continuous hold); default -1 uses parity-based pairs.
            - scriptDrive: bool - When true, allows the call while scripted blocking walk or `playerLocked` is active (internal script path only).

    RETURNS:
        void

    SIDE EFFECTS:
        Mutates walk state; may mutate player tile and camera when a segment completes (via `commitCompletedMapWalk_` / auto-chain).

    ERROR HANDLING:
        Ignores moves when `playerLocked` or `mapScriptBlockingWalk_` (unless `scriptDrive`), when already walking in a different direction, or when the target footprint is blocked.

    DEPENDENCIES:
            - mapPlayerFootprintBlockedAt_
            - syncCameraToFollowPlayer_
            - clampMapCamera_ / clampWorldCamera_

    FUNCTION: Game::tickMapPlayerWalk_

    SIGNATURE:
        void Game::tickMapPlayerWalk_()

    DESCRIPTION:
        Advances walk animation using accumulated time and `playerWalkFrameMs_`; calls `commitCompletedMapWalk_` when the frame sequence ends; keeps camera following the footprint with time-based in-stride interpolation (see BUG-MAP-021 / `mapPlayerWalkVisualOffsetsTiles_`).

    PARAMETERS:
        None

    RETURNS:
        void

    SIDE EFFECTS:
        Walk frame index, optional tile commit, camera clamp.

    DEPENDENCIES:
            - std::chrono::steady_clock (in `map_view.cpp`)

FILE: include/game.h

    PURPOSE:
        Declares core gameplay/runtime types and the public/private API for `Game` and `Pokemon`.

    DEPENDENCIES:
            - SDL/SDL_ttf headers
            - nlohmann::json
            - map_data.h
            - perf_stats.h
            - C++ STL containers and smart pointers

    KEY COMPONENTS:
            - class Game
            - class Pokemon
            - enum Type
            - enum MoveCategory
            - struct MoveTemplate
            - struct PokemonStats

    NOTES:
        `Game` owns runtime state, UI mode state, and most SDL resource handles.
        IMPROVEMENT-PERF-001: map viewer footer strings are rebuilt only when `bumpMapSingleViewFooterHintRevision_` / `bumpWorldLayoutViewFooterHintRevision_` detect changes (map load, overworld JSON reload, world layout load), avoiding per-frame temporary `std::string` concatenations in `drawMapView_` / `drawWorldLayoutView_`.
        FEATURE-MAP-072/078: `#include "game_state.h"`; `Game` adds `GameState gameState_`, `MapEventInstance mapScriptEvent_` + `bool mapScriptHasEvent_` (the event whose script is running), and helper methods `loadLibrarySubflow_(name)`, `tryStepOnMapEvent_()`, `applyMapScriptCompletion_()`, `mapEventRunConditionOk_(ev)`, `mapEventClearedGate_(ev)`, and `tryFireAutoMapEvents_()` (implemented in `src/map_view.cpp`).
        FEATURE-MAP-088: `scriptedTrainerBattleActive_` distinguishes scripted trainer battles from wild encounters; `mapScriptBattleYielding_` yields the script runner during the battle; `mapScriptWasBattleLoss_` skips `applyMapScriptCompletion_` on loss-warp path. `pendingLossWarpMapId_/X_/Y_` store the opcode-level lossWarp for the priority chain: opcode lossWarp > map healPoint > global default. Phase 5: `parseScriptedBattleParties_`, `tryRotateScriptedBattle_` (foe party + sequential trainers), `scriptedBattlePlayerTurnCount_` + `Battle::setFoeOhko` for scripted_loss.

    CLASS: Game

    PURPOSE:
        Coordinates initialization, input handling, rendering, map navigation, battle flow, and overlay HUDs.

    MEMBERS:
            - pokedb: json - Loaded monster/species data.
            - battleCfg_: json - Battle config and backgrounds.
            - window: SDL_Window* - Main SDL window handle.
            - renderer: SDL_Renderer* - Main SDL renderer handle.
            - font_: TTF_Font* - UI font used by text render calls.
            - activeBattle_: std::unique_ptr<Battle> - Active battle state object.
            - mapUiMode_: MapUiMode - Current map UI sub-mode (`None`, `PickMap`, `ViewMap`, or `ViewWorld` for FEATURE-MAP-029).
            - mapPickerLastError_: std::string - Last Overworld / catalog load error shown in the picker.
            - viewMapData_: MapData - Loaded map payload for single-map view (and summary fields for Overworld hint sizing).
            - worldLayoutInstances_: std::vector<WorldLayoutMapInstance> - Placed map copies in `renderOrder` for composite draw.
            - worldBoundsMinX_/Y_/MaxX_/MaxY_: int - World-tile AABB (max exclusive on X/Y) for camera clamp and void tiles.
            - showPerfHud_: bool - F3 RAM/CPU panel toggle.
            - showKeybindHud_: bool - F4 keybind panel toggle.
            - perfSampler_: PerfSampler - Runtime process metrics sampler.
            - overworldTileGridVisible_: bool - Per-tile outline in map/world viewer (**L**).
            - mapSingleViewFooterHintRevision_/BuiltRevision_: std::uint32_t - IMPROVEMENT-PERF-001: invalidate footer hint for `ViewMap`.
            - mapSingleViewFooterHintScratch_: std::string - Cached single-map footer line for `renderText`.
            - worldLayoutViewFooterHintRevision_/BuiltRevision_: std::uint32_t - Same for `ViewWorld`.
            - worldLayoutViewFooterHintScratch_: std::string - Cached overworld footer line.
            - mapScriptDriveStepsRemaining_: int - FEATURE-MAP-071: number of tile strides remaining in the current rail walk/run opcode.
            - mapScriptDriveStepDx_/Dy_: int - FEATURE-MAP-071: fixed cardinal delta per stride (set once on first activation; never changes mid-opcode).

    METHODS:
            - run
            - initVideo
            - initFont
            - initImage
            - drawPerfHud_
            - drawKeybindHud_
            - drawMapView_
            - drawWorldLayoutView_
            - loadMapForView_
            - loadWorldLayoutForView_
            - requestPlayerMoveOnMap_
            - tickMapPlayerWalk_
            - returnToTitle
            - bumpMapSingleViewFooterHintRevision_
            - bumpWorldLayoutViewFooterHintRevision_

    INVARIANTS:
        Renderer/font guarded draw calls must no-op when handles are null.
        Camera/player tile fields are clamped to map bounds (single-map) or world composite bounds (`ViewWorld`) before draw.
        Battle resources are released when returning to title or shutting down.

    CLASS: Pokemon

    PURPOSE:
        Represents one resolved combatant built from species/form data and move catalog entries.

    MEMBERS:
            - iv: PokemonStats - Individual values for battle stats.
            - baseStats: PokemonStats - Base species stats.
            - types: std::vector<Type> - Resolved type list.
            - moves_: std::vector<MoveTemplate> - Resolved move set.
            - spriteFrontPath_: std::string - Front sprite path.
            - spriteBackPath_: std::string - Back sprite path.

    METHODS:
            - Pokemon
            - loadFromSpecies
            - loadMoves
            - ivs
            - bases
            - getTypes
            - moves

    INVARIANTS:
        Accessors return references that remain valid for object lifetime.
        `blankPoke` establishes safe defaults before data load.

    FUNCTION: Game::run

    SIGNATURE:
        void Game::run()

    DESCRIPTION:
        Main SDL loop. Polls events, dispatches mode-specific key handling, updates perf metrics, accumulates FPS over a short sampling window, draws current UI scene, and presents frames.

    PARAMETERS:
        None

    RETURNS:
        void - No return value.

    SIDE EFFECTS:
        Mutates game mode state, map state, battle state, and overlay toggles.
        Performs continuous render commands and frame presentation.

    ERROR HANDLING:
        Returns immediately if renderer initialization failed.
        Mode handlers perform guard checks and skip invalid operations.

    DEPENDENCIES:
            - SDL_PollEvent
            - SDL_RenderPresent
            - PerfSampler::update
            - drawMapView_
            - drawWorldLayoutView_
            - drawPerfHud_
            - drawKeybindHud_

    FUNCTION: Game::drawPerfHud_

    SIGNATURE:
        void Game::drawPerfHud_()

    DESCRIPTION:
        Draws RAM/CPU/FPS metrics in a compact top-left panel when F3 is active and the keybind overlay is not active.

    PARAMETERS:
        None

    RETURNS:
        void - No return value.

    SIDE EFFECTS:
        Draws a blended background rectangle and three metric text lines.

    ERROR HANDLING:
        No-op when HUD disabled or renderer/font unavailable.
        Displays placeholder text when metrics are not yet ready.

    DEPENDENCIES:
            - PerfSampler::rssKnown
            - PerfSampler::cpuPercentReady
            - renderText

    FUNCTION: Game::drawKeybindHud_

    SIGNATURE:
        void Game::drawKeybindHud_()

    DESCRIPTION:
        Draws the F4 keybinding help panel, which replaces the F3 metrics panel when active.

    PARAMETERS:
        None

    RETURNS:
        void - No return value.

    SIDE EFFECTS:
        Draws panel and multi-line keybinding help text.

    ERROR HANDLING:
        No-op when HUD disabled or renderer/font unavailable.

    DEPENDENCIES:
            - renderText
            - TTF_SizeUTF8
            - TTF_FontLineSkip

    FUNCTION: Game::renderText

    SIGNATURE:
        void Game::renderText(const std::string& text, int x, int y, SDL_Color color)

    DESCRIPTION:
        Renders UTF-8 text using a reusable texture cache keyed by text content and RGBA color to avoid per-frame surface/texture churn.

    PARAMETERS:
        - text: const std::string& - Text payload to render.
        - x: int - Destination x coordinate in logical pixels.
        - y: int - Destination y coordinate in logical pixels.
        - color: SDL_Color - Render color.

    RETURNS:
        void - No return value.

    SIDE EFFECTS:
        Allocates and stores new cached text textures on first use.
        Issues SDL texture copy commands each call.

    ERROR HANDLING:
        No-ops when font/renderer are unavailable or text is empty.
        Skips cache insertion if SDL surface/texture creation fails.

    DEPENDENCIES:
            - TTF_RenderUTF8_Blended
            - SDL_CreateTextureFromSurface
            - SDL_RenderCopy

    FUNCTION: Game::drawDisplayText

    SIGNATURE:
        void Game::drawDisplayText()

    DESCRIPTION:
        Draws previously split display lines from `displayTextLines_` to avoid per-frame substring allocations.

    PARAMETERS:
        None

    RETURNS:
        void - No return value.

    SIDE EFFECTS:
        Emits one `renderText` call per cached line.

    ERROR HANDLING:
        Returns immediately when font is unavailable.

    DEPENDENCIES:
            - rebuildDisplayTextLines_
            - renderText

    FUNCTION: Game::rebuildMapTilesetRenderMeta_

    SIGNATURE:
        void Game::rebuildMapTilesetRenderMeta_()

    DESCRIPTION:
        Precomputes map tileset render metadata (texture pointer, tileset definition pointer, and atlas column count) to reduce inner-loop work in map rendering.

    PARAMETERS:
        None

    RETURNS:
        void - No return value.

    SIDE EFFECTS:
        Clears and repopulates `mapTilesetRenderMeta_`.
        Ensures tileset textures are loaded via map texture cache.

    ERROR HANDLING:
        Skips entries whose textures cannot be loaded.

    DEPENDENCIES:
            - getOrLoadMapTilesetTexture_
            - inferColumns
            - SDL_QueryTexture

    FUNCTION: Game::rebuildPokedexIndex_

    SIGNATURE:
        void Game::rebuildPokedexIndex_()

    DESCRIPTION:
        Builds cached lookup structures for Pokedex-number-to-species resolution and random foe selection.

    PARAMETERS:
        None

    RETURNS:
        void - No return value.

    SIDE EFFECTS:
        Rebuilds `pokedexNumToSpecies_` and `speciesKeys_` from loaded pokemon data.

    ERROR HANDLING:
        Leaves caches empty when Pokemon data is missing or malformed.

    DEPENDENCIES:
            - nlohmann::json object iteration
            - kPokemonDbKey

FILE: include/battle.h

    PURPOSE:
        Declares the battle model, damage result structure, and turn-resolution API.

    DEPENDENCIES:
            - game.h
            - C++ STL string/vector

    KEY COMPONENTS:
            - enum BattleOutcome
            - struct BattleDamageResult
            - class Battle

    NOTES:
        Battle encapsulates both combatants, HP state, and per-turn result messages.

    CLASS: Battle

    PURPOSE:
        Executes turn-based battle logic between a player Pokemon and a foe Pokemon.

    MEMBERS:
            - player_: Pokemon - Player combatant.
            - foe_: Pokemon - Enemy combatant.
            - playerHp_: int - Current player HP.
            - foeHp_: int - Current foe HP.
            - outcome_: BattleOutcome - Current battle state.
            - lastTurnMessages_: std::vector<std::string> - Human-readable turn summary lines.

    METHODS:
            - Battle
            - executeTurn
            - onPlayerMoveChosen
            - calculateDamage
            - attackWith

    INVARIANTS:
        HP values are bounded and battle end state is represented by `outcome_`.

    FUNCTION: Battle::executeTurn

    SIGNATURE:
        bool Battle::executeTurn(int playerMoveSlot)

    DESCRIPTION:
        Validates move selection, resolves order and attacks, updates HP/outcome, and appends turn messages.

    PARAMETERS:
            - playerMoveSlot: int - Index of selected player move.

    RETURNS:
        bool - True when a turn executes; false for invalid slot or finished battle.

    SIDE EFFECTS:
        Changes HP, outcome, and `lastTurnMessages_`.

    ERROR HANDLING:
        Rejects invalid move slot and no-op cases when battle has ended.

    DEPENDENCIES:
            - calculateDamage
            - attackWith
            - random (helperMethods.cpp)

FILE: include/perf_stats.h

    PURPOSE:
        Declares process RAM/CPU sampler used by in-game HUD panels.

    DEPENDENCIES:
            - cstdint

    KEY COMPONENTS:
            - class PerfSampler

    NOTES:
        Exposes readiness flags to avoid rendering unstable first-sample values.

    CLASS: PerfSampler

    PURPOSE:
        Samples process memory and CPU deltas and smooths CPU output with EMA.

    MEMBERS:
            - lastCpuSec_: double - Previous process CPU seconds sample.
            - lastWallNs_: int64 - Previous wall-clock nanoseconds sample.
            - haveLastSample_: bool - Baseline sample readiness flag.
            - rssValid_: bool - Whether latest RSS sample succeeded.
            - rssBytes_: uint64_t - Latest resident memory sample.
            - cpuPercentReady_: bool - Whether CPU percent output is initialized.
            - cpuPercentSmoothed_: double - EMA-smoothed CPU percent.

    METHODS:
            - update
            - rssKnown
            - rssBytes
            - cpuPercentReady
            - cpuPercentSmoothed

    INVARIANTS:
        CPU percentage is only marked ready after at least one previous sample exists.

    FUNCTION: PerfSampler::update

    SIGNATURE:
        void PerfSampler::update()

    DESCRIPTION:
        When wall time since the last sample is at least ~250ms, samples RSS and process CPU time, computes delta-based CPU %, applies EMA smoothing, and updates readiness flags. Between intervals returns early without mutating sampled values, reducing per-frame `task_info` / `/proc` overhead.

    PARAMETERS:
        None

    RETURNS:
        void - No return value.

    SIDE EFFECTS:
        On a sample tick, mutates sampler state including RSS bytes, smoothed CPU percent, and `haveLastSample_` progression.

    ERROR HANDLING:
        Marks RSS invalid when sampling fails.
        Skips CPU update for invalid/too-small wall delta or negative CPU delta; keeps prior RSS/CPU display values between interval ticks.

    DEPENDENCIES:
            - sampleRss
            - monotonicCpuSeconds
            - std::chrono::steady_clock

FILE: src/game.cpp

    PURPOSE:
        Implements `Game` lifecycle, rendering, UI flow, battle rendering helpers, and F3/F4 HUD behavior.

    DEPENDENCIES:
            - game.h
            - battle.h
            - SDL2 / SDL_ttf / SDL_image
            - JSON and file I/O for startup data

    KEY COMPONENTS:
            - initVideo
            - initFont
            - initImage
            - run
            - drawPerfHud_
            - drawKeybindHud_
            - returnToTitle
            - startOverworldWildBattle_
            - endOverworldBattle_
            - handleOverworldBattleKey_

    NOTES:
        FEATURE-MAP-050: when `overworldBattleActive_`, `Game::run` skips map walk/script ticks, routes Q/W/E/R to `handleOverworldBattleKey_` (battle moves), and draws battle UI on top of paused ViewMap/ViewWorld; `endOverworldBattle_` clears battle and stays on the map (does not call `returnToTitle`).
        Uses fixed logical render resolution and SDL scaling for display independence.
        The SDL window title string includes `C++ alpha 0.1` so builds are visibly labeled (see `SDL_CreateWindow` in `initVideo`).
        FEATURE-MAP-072: the `Game` constructor calls `gameState_.load("src/maps/scripts/flag_registry.json", "save/game_state.json")`, optionally dumps a debug snapshot (env-gated, see `getenv`), and `gameState_.enableCrashSafety()`. `~Game()` calls `gameState_.flush(true)` for a clean final write. (`#include <cstdlib>` added for `getenv`.)
        FEATURE-MAP-088: `startScriptedTrainerBattleFromOpcode_` loads a library battle JSON via `battleId` arg, merges inline opcode args on top (non-empty/non-zero inline values win), stores `pendingLossWarpMapId_/X_/Y_` for `executeBattleLossWarp_`. `executeBattleLossWarp_` applies priority chain: opcode lossWarp > viewMapData_.healPoint > defaultHealMapId_ global. Pending warp state is cleared after each loss resolution.

    FUNCTION: Game::initVideo

    SIGNATURE:
        bool Game::initVideo()

    DESCRIPTION:
        Initializes SDL video subsystem, creates window/renderer, and configures renderer scaling.
        Window title is set to the user-visible game name including the C++ alpha version label.

    PARAMETERS:
        None

    RETURNS:
        bool - True when window and renderer are ready.

    SIDE EFFECTS:
        Creates SDL handles and updates initialization flags.

    ERROR HANDLING:
        Logs SDL errors and returns false on failure.

    DEPENDENCIES:
            - SDL_Init
            - SDL_CreateWindow
            - SDL_CreateRenderer

    FUNCTION: Game::~Game

    SIGNATURE:
        Game::~Game()

    DESCRIPTION:
        Releases loaded textures, map caches, battle resources, and SDL subsystems in shutdown-safe order.

    PARAMETERS:
        None

    RETURNS:
        None - Destructor.

    SIDE EFFECTS:
        Destroys SDL objects and resets internal pointers/flags.

    ERROR HANDLING:
        Uses null checks before each destroy/quit call.

    DEPENDENCIES:
            - destroyMapViewTextures_
            - destroyBattleBackgroundTextures
            - SDL_DestroyRenderer
            - SDL_DestroyWindow

FILE: src/battle.cpp

    PURPOSE:
        Implements battle constructor, stat-derived damage calculation, turn sequencing, and message output.

    DEPENDENCIES:
            - battle.h
            - cmath/algorithm utilities
            - random helper function

    KEY COMPONENTS:
            - Battle::Battle
            - Battle::calculateDamage
            - Battle::attackWith
            - Battle::executeTurn

    NOTES:
        Uses per-Pokémon level parameters (FEATURE-MAP-088) and probabilistic crit/random variance.
        Phase 5: `setFoeOhko` forces foe attacks to KO the active player Pokémon (scripted_loss after N turns).

    FUNCTION: Battle::calculateDamage

    SIGNATURE:
        BattleDamageResult Battle::calculateDamage(const Pokemon& attacker, const Pokemon& defender, const MoveTemplate& move)

    DESCRIPTION:
        Computes a single move damage value using category stats, STAB, random factor, and crit multiplier.

    PARAMETERS:
            - attacker: const Pokemon& - Attacking combatant.
            - defender: const Pokemon& - Defending combatant.
            - move: const MoveTemplate& - Move metadata and power/category.

    RETURNS:
        BattleDamageResult - Damage and crit flag for this strike.

    SIDE EFFECTS:
        Writes crit debug line to stdout when crit triggers.

    ERROR HANDLING:
        Returns zero damage for status/no-power moves.

    DEPENDENCIES:
            - Battle::hasStab
            - random

FILE: src/pokemon.cpp

    PURPOSE:
        Implements Pokemon data loading and normalization from species/form JSON and move catalog entries.

    DEPENDENCIES:
            - game.h
            - unordered_map, optional, string utilities
            - nlohmann::json API

    KEY COMPONENTS:
            - parseTypeString
            - parseMoveCategory
            - parseMoveFromCatalogEntry
            - Pokemon::loadFromSpecies
            - Pokemon::loadMoves

    NOTES:
        Performs schema-tolerant parsing with warnings/default fallbacks.

    FUNCTION: Pokemon::loadFromSpecies

    SIGNATURE:
        void Pokemon::loadFromSpecies(const nlohmann::json& species, const std::string& speciesKey, const std::string& formKey)

    DESCRIPTION:
        Loads stats/types/sprites and form overrides from one species payload into runtime fields.

    PARAMETERS:
            - species: const nlohmann::json& - Source species object.
            - speciesKey: const std::string& - Canonical species key.
            - formKey: const std::string& - Optional form selector.

    RETURNS:
        void - No return value.

    SIDE EFFECTS:
        Mutates current `Pokemon` fields.

    ERROR HANDLING:
        Uses fallback defaults and validation checks for missing/invalid fields.

    DEPENDENCIES:
            - setTypeValues
            - loadMoves

FILE: include/script_engine.h / src/script_engine.cpp

    PURPOSE:
        FEATURE-MAP-030 / FEATURE-MAP-043 / FEATURE-MAP-048 / FEATURE-MAP-049: JSON script interpreter for map events. `ScriptRuntime::loadDocument` accepts legacy `actions` arrays (`op` + `args`) or FEATURE-MAP-043 files where a non-empty `script_1` array of one-key objects (each object maps one opcode to args) normalizes to the same internal `actions` list; optional `script_1` object form is also accepted. `ScriptRuntime::stepFrame` delegates opcode handling to `mapScriptDispatchOpcode` in `src/op.cpp` (including `camera_follow_player`, which defers map-viewer camera reset to `Game::tryMapViewerScriptOpcode_`). Opcodes and map-editor alignment are documented in `docs/event_script_ops.md`. FEATURE-MAP-044 / FEATURE-MAP-048 / FEATURE-MAP-049: Python map-editor tooling uses `tools/extract_map_script_ops.py` on `src/op.cpp` → `tools/event_script_ops_generated.py` plus `tools/event_script_op_meta.json` and `tools/event_script_opcode_docs.py`.

    DEPENDENCIES:
            - nlohmann::json
            - `mapScriptDispatchOpcode` (`include/op.h`)
            - `ScriptRuntime` drives `Game` map UI (lock movement, messages, warp, scripted walk/camera) when `mapUiMode_` is ViewMap/ViewWorld and `tryMapViewerScriptStep` is wired from `Game::wireMapScriptCallbacks_`.

    NOTES:
        FEATURE-MAP-068: nested control flow. `ScriptRuntime` carries `std::vector<ScriptLoopFrame> loopStack` (struct `ScriptLoopFrame { size_t bodyStartPc; int remaining; }`), cleared in `reset()`. `loadDocument` calls file-local `resolveControlFlow(actions)` after building `actions`: it stack-pairs `if_flag`/`end_if`, `repeat`/`end_repeat`, `if_var`/`end_if_var`, and `region`/`end_region` and stamps each conditional opener's `args.skip` = body action count (exclusive of the terminator), so hand-authored JSON and the editor never set skip manually. Unbalanced markers are left without a skip (safe fallback).
        Phase 4: `tests/test_script_runtime.cpp` (8 scenarios via `make test-script-runtime`) covers nested if_flag/repeat, call_subflow return, goto/stop_script, and if_var blocks.
        FEATURE-MAP-074/075/077: subflows, call stack, scratch variables, and labeled jumps. `ScriptRuntime` adds `std::map<std::string,nlohmann::json> flows` (main + named subflows), `std::string activeFlow`, `std::vector<ScriptCallFrame> callStack` (caller resume context + per-frame `vars`), `std::map<std::string,nlohmann::json> vars` (active-frame scratch vars), and `std::map<std::string,std::size_t> labels` (per-flow label index rebuilt by `rebuildLabels_`). `kMaxCallDepth = 32` guards recursion. `callSubflow(name, seedVars)` resolves in-file flows first, then `onLoadLibrarySubflow` (`_library/<name>.json`), pushes a frame, seeds `vars`, and switches flow; `returnFromCall()` pops back; `stopScript()` clears the stack and finishes. `loadDocument` parses `subflows` into `flows`. All cleared in `reset()`.
        FEATURE-MAP-072: persistent flags. `readFlag`/`writeFlag` route through `onReadFlag`/`onWriteFlag` (into `GameState`) when set; otherwise a local `std::map<std::string,bool> flags` is used (unit-test fallback).

FILE: include/game_state.h / src/game_state.cpp

    PURPOSE:
        FEATURE-MAP-072: persistent game state. `GameState` owns durable boolean flags backed by `save/game_state.json`, overlaying defaults declared in `src/maps/scripts/flag_registry.json`. Scratch variables are intentionally NOT persisted here (they live on the script call frame). Provides crash-safe, debounced, atomic persistence.

    DEPENDENCIES:
            - nlohmann::json
            - <csignal>, <cstdlib> (atexit), <fstream>, <chrono>, <filesystem>

    KEY COMPONENTS:
            - GameState::load — read registry defaults then overlay save file
            - GameState::getFlag / setFlag — accessors; setFlag marks dirty
            - GameState::flush / flushIfDirty — atomic write (temp file + rename), debounced
            - GameState::enableCrashSafety — installs std::signal + std::atexit flush handlers
            - GameState::dumpDebug — writes a snapshot to debug/state_dumps/

    NOTES:
        Writes are atomic (write temp, then rename) to avoid torn saves; flushing is debounced to avoid per-step disk churn (callers use `flushIfDirty`). `enableCrashSafety` registers a process-wide handler that flushes on SIGINT/SIGTERM/SIGSEGV and on normal exit. `flag_registry.json` only supplies initial/default values; the authoritative live state is the save file.
        Phase 4: `tests/test_game_state.cpp` verifies load/set/flush round-trip via `make test-game-state`.

FILE: include/op.h / src/op.cpp

    PURPOSE:
        FEATURE-MAP-048: single entry point for map script opcode string dispatch used by `ScriptRuntime::stepFrame`; keeps `if (op == "...")` literals in one translation unit for `tools/extract_map_script_ops.py`. Built-in opcodes (end_script, flags, messages, warp, facing string) run here; map viewer movement/camera opcodes delegate through `ScriptRuntime::tryMapViewerScriptStep` when set.

    DEPENDENCIES:
            - `script_engine.h` (`ScriptRuntime`, `ScriptStepResult`)
            - nlohmann::json

    KEY COMPONENTS:
            - `mapScriptDispatchOpcode`

    NOTES:
        Unknown opcodes fall through to stub logging after the map-viewer hook returns `std::nullopt`.
        FEATURE-MAP-068: control-flow opcodes handled here — `if_flag` (`++pc`; if flag false `pc += skip`), `end_if` (marker; `++pc`), `repeat` (if `n<=0` skip body via `skip`, else push `{pc, n}` onto `rt.loopStack`), `end_repeat` (decrement loop top; jump to `bodyStartPc` until it drains, then pop and `++pc`). `skip` is precomputed by `ScriptRuntime::resolveControlFlow`.
        FEATURE-MAP-072: flag opcodes (`set_flag`/`clear_flag`/`unless_flag`/`if_flag`) read/write through `rt.readFlag`/`rt.writeFlag` so they hit persistent `GameState` when wired.
        FEATURE-MAP-074/075/077: new opcodes — `call_subflow` (`rt.callSubflow(name, args.vars)`), `stop_script` (`rt.stopScript()`), `goto` (jump to `rt.labels[label]` in the active flow), `label` (no-op marker, kept as its own `if` branch for the extractor), `comment`/`region`/`end_region` (no-ops), `set_var` (writes `rt.vars[name]`), `if_var`/`end_if_var` (compare via file-local `compareVar(a, cmp, b)` — note the parameter is named `cmp`, not `op`, so `extract_map_script_ops.py` does not mistake comparison literals for opcodes).

    FUNCTION: mapScriptDispatchOpcode

    SIGNATURE:
        ScriptStepResult mapScriptDispatchOpcode(ScriptRuntime& rt, const std::string& op, const nlohmann::json& args)

    DESCRIPTION:
        Dispatches the current script step opcode; mutates `rt` (`pc`, flags, wait/message state, finished) per opcode semantics.

    PARAMETERS:
            - rt: ScriptRuntime — active interpreter state.
            - op: string — opcode name from the current step.
            - args: json — args object for the step.

    RETURNS:
        ScriptStepResult — Continue, Yield, Finished, or Error.

    SIDE EFFECTS:
        Invokes `rt` callbacks (`onShowMessage`, `onWarp`, `onLockPlayer`, `onFacingHint`, `tryMapViewerScriptStep`, `onDebugStub`); may advance `rt.pc` or set `rt.finished`.

    ERROR HANDLING:
        Returns Error when the step JSON is invalid (handled in `stepFrame` before dispatch).

    DEPENDENCIES:
            - `tryDispatchMapViewerOpcodes` (file-local in `src/op.cpp`)
            - `truthyFlag`, `stubOp` helpers

FILE: src/helperMethods.cpp

    PURPOSE:
        Provides shared utility helpers: inclusive integer random generation and Pokemon stream formatting.

    DEPENDENCIES:
            - game.h
            - random
            - ostream

    KEY COMPONENTS:
            - random
            - operator<< (Pokemon)

    NOTES:
        Random generator state is static and reused across calls.

    FUNCTION: random

    SIGNATURE:
        int random(int min, int max)

    DESCRIPTION:
        Returns a random integer sampled uniformly from `[min, max]`.

    PARAMETERS:
            - min: int - Inclusive minimum.
            - max: int - Inclusive maximum.

    RETURNS:
        int - Sampled random integer.

    SIDE EFFECTS:
        Advances static PRNG state.

    ERROR HANDLING:
        Assumes caller provides a valid range.

    DEPENDENCIES:
            - std::random_device
            - std::mt19937
            - std::uniform_int_distribution

FILE: src/perf_stats.cpp

    PURPOSE:
        Implements runtime process metrics sampling for RAM and CPU usage.

    DEPENDENCIES:
            - perf_stats.h
            - sys/resource.h
            - macOS mach task APIs (when compiling on Apple)
            - Linux procfs (`/proc/self/status`) parsing
            - chrono and STL file/string helpers

    KEY COMPONENTS:
            - monotonicCpuSeconds
            - sampleRss
            - PerfSampler::update

    NOTES:
        CPU percentage is computed from process CPU delta over wall delta and smoothed via EMA.

    FUNCTION: PerfSampler::update

    SIGNATURE:
        void PerfSampler::update()

    DESCRIPTION:
        Samples RSS and CPU time, computes frame-to-frame CPU %, and updates smoothed output/readiness flags.

    PARAMETERS:
        None

    RETURNS:
        void - No return value.

    SIDE EFFECTS:
        Updates all internal state values in `PerfSampler`.

    ERROR HANDLING:
        Marks RSS invalid when unavailable and skips invalid CPU delta updates.

    DEPENDENCIES:
            - sampleRss
            - monotonicCpuSeconds
            - std::chrono::steady_clock

FILE: tools/event_script_opcode_docs.py

    PURPOSE:
        Builds plain-text and help-tab documentation lines for each map event script opcode (label, description, JSON function shape, parameters, example fragment).

    DEPENDENCIES:
        Python stdlib (`json`, `copy`, `typing`).

    KEY COMPONENTS:
        - `build_structured_doc_lines` — merged meta + schema documentation; **Function** / **Example** sections use `json.dumps(..., indent=4)` line-by-line without `_wrap_words` so nested brackets stay aligned (**IMPROVEMENT-MAP-045**); prose sections still use `_wrap_words` (**IMPROVEMENT-MAP-043**)
        - `_wrap_words` — measures lines with a callback and wraps prose or JSON; IMPROVEMENT-MAP-043 preserves leading spaces on the first wrapped line and uses a continuation prefix so indented JSON examples stay readable

    NOTES:
        Consumed by `MapEditor._event_script_rebuild_doc_lines` and `build_help_segments_for_op` for the **Script opcodes** help tab. **BUG-MAP-030**: `_wrap_words` limits must reserve `measure_line("  ")` pixels when a line is stored with a two-space prefix (`Description` / `Parameters` rows) so rendered width matches the wrap budget.

    FUNCTION: _wrap_words

    SIGNATURE:
        def _wrap_words(text: str, measure_line: MeasureFn, max_w: int) -> list[str]

    DESCRIPTION:
        Splits leading space indent from the remainder, wraps words to `max_w` using `measure_line`, and prefixes continuation lines so wrapped JSON does not lose visual structure.

    PARAMETERS:
        - text: str — single logical line (may include leading spaces from `json.dumps` example lines)
        - measure_line: MeasureFn — pixel width of a string
        - max_w: int — maximum width in pixels

    RETURNS:
        list[str] — one or more physical lines

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        Empty or whitespace-only input yields `[""]`.

    DEPENDENCIES:
        None

FILE: tools/map_editor.py

    PURPOSE:
        Pygame-based map editor: tile painting, layers, walk/transparency flags, connections, tileset folders, and an optional world workspace for arranging map thumbnails with export to `world_layout.json`.

    DEPENDENCIES:
        Python 3, pygame, stdlib (`json`, `pathlib`, `copy`, `uuid`, `importlib`, etc.), lazy-loaded `tools/world_layout.py`.

    KEY COMPONENTS:
        - `MapEditor` UI loop (`run`), layout (`relayout`), drawing (`draw`, `_draw_world_workspace`)
        - World camera helpers (`_world_screen_to_world`, `_world_world_to_screen`)
        - BUG-MAP-028 / IMPROVEMENT-MAP-044 / BUG-MAP-029 / FEATURE-MAP-050 / IMPROVEMENT-MAP-046 / BUG-MAP-031 / BUG-MAP-032: event script modal and sprite UI: sprite list + preview columns; `_draw_events_character_frame_overlay` scales the NPC 4×4 sheet using `min(max_disp_w, max_disp_h)` with horizontal budget from `min(map_viewport_rect.w, window)` and vertical budget from `map_canvas_rect.h`; centers on `map_canvas_rect` and clamps with `top_bound = max(margin, canvas.y)`; title uses `_wrap_lines_to_width` with explicit `title_pad_top` / `title_pad_bottom` and `inner.y = box.y + title_block_h + gap_before_grid`; facing buttons use a width derived from `box.w`; `_events_sprite_pick_apply_row_click` restricted to the list column; `_event_script_modal_mousewheel` scrolls docked sprite list; opcode palette press/threshold/pin; `_event_script_modal_keydown` routes **Enter**, **1–3**, and arrows for docked sprite picker and full NPC frame navigation when the character sheet step runs with the modal open; `MOUSEBUTTONDOWN` runs character-frame and sprite-list hits **before** `_event_script_modal_mousedown` so the 4×4 sheet receives LMB
        - FEATURE-MAP-041: `help_overlay_open` / `_draw_help_overlay` (modal help on `toggle_help`); IMPROVEMENT-MAP-041: `toggle_eraser` applies in paint, walk, transparent, and over_player; IMPROVEMENT-MAP-WORLD-006 world UI: `_world_font_for_label_size`, `_world_blit_map_label`, world canvas clip in `_draw_world_workspace`
        - FEATURE-MAP-WORLD-008: `_world_snap_node_origin_to_grid`, `_world_grid_step_for_zoom`, tile-unit node extents, legacy world JSON migration on load
        - FEATURE-MAP-096 Phase 6: legacy inline Events workspace removed; `_open_events_launcher` / `_toggle_events_launcher` open the Events hub from toolbar E or V; map paint blocked while any event modal is open via `_any_blocking_modal_open()`
        - FEATURE-MAP-096 Phase 8: headless SDL layout smoke (`tests/test_phase8_verify.py`) at 800×600 and 1280×800 verifies satellite modals and Help panels stay within canvas at UI-Standard minimums
        - FEATURE-MAP-064: `EventsLauncherModal` instantiated as `events_launcher_modal`; E toolbar button opens launcher
        - FEATURE-MAP-065: `EventEngineModal` instantiated as `event_engine_modal`; `event_script_editor_open` draw/input gated by `not event_engine_modal.open` at top-level
        - FEATURE-MAP-068: control-flow tooling — `config_get_section`/`config_set_section` (generic config sections), `list_all_map_ids`, `read_map_events`/`write_map_events`/`map_dims` (arbitrary-map event IO), `open_path_external`; help Settings tab adds the "Event Engine: selecting a map switches the main editor" toggle (persisted as `eventEngine.selectSwitchesMainMap`)
        - FEATURE-MAP-069: `EventPlaceModal`/`EventSpriteModal` instantiated as `event_place_modal`/`event_sprite_modal`; the rewritten self-contained `EventEngineModal` replaces the floating events popover; sub-modal input routing added to wheel/motion/mousedown/mouseup/keydown above the launcher/engine; map painting + hover blocked while `event_place_modal`/`event_sprite_modal` are open
        - FEATURE-MAP-066: `HELP_GUIDE_TABS` gains `("settings", "Settings")` entry; `_draw_help_settings_controls` renders interactive layer-management buttons and key-binding rows inside help overlay when settings tab is active; `_open_help_overlay(tab, scroll_to, back_to)` API added; `*` toolbar button opens help on settings tab; `help_settings_key_sel` state for key rebinding inside help overlay; help overlay refactored to full UI Standard — draggable title bar, BR/BL resize grips, Close button, Back button (when `_help_back_to` set), `_help_panel_override` for persistent size/pos (BUG-MAP-064)
        - FEATURE-MAP-067: `.cursor/rules/UI-Standard-Rule.mdc` created; toolbar label `#` renamed "Overworld" and `*` renamed "Help"
        - BUG-MAP-063: KEYDOWN help_overlay Esc check moved BEFORE modal keydown handlers so Esc closes help first; MOUSEBUTTONDOWN help handler moved BEFORE modal handlers and always continues (consumes all clicks while help is open)
        - BUG-MAP-064: `_draw_help_overlay` rewritten to UI standard; `_help_panel_override`, `_help_drag_mode`, `_help_drag_ref`, `_help_resize_corner_br/bl`, `_help_title_bar`, `_help_close_btn`, `_help_back_btn`, `_help_back_to` added; VIDEORESIZE resets `_help_panel_override`

    NOTES:
        World thumbnails and proximity lines are clipped to `map_canvas_rect` (intersected with the previous surface clip) so content does not draw into the layer chip region. Map name badges are optional (`world_map_labels_visible`) and use a small bounded font cache. World node `widthPx`/`heightPx` are map-tile spans; `world_cam_zoom` is screen pixels per world tile (`WORLD_CAM_ZOOM_MAX` raised for zoomed-in editing). **IMPROVEMENT-MAP-047**: `_expand_help_overlay_segments` and `_expand_visual_text_lines` split long strings before `Font.render` so **Script opcodes** help lines and the script-modal documentation column are not clipped by `set_clip` rectangles.     **BUG-MAP-031**: the NPC character-sheet frame overlay must not assume the map viewport equals the drawable window; title wrapping and window clamping avoid horizontal clipping. **BUG-MAP-032**: vertical sizing and centering use `map_canvas_rect` (below the layer chip), not the full `map_viewport_rect`; the sheet inner rect aligns with `title_block_h` including bottom padding. **FEATURE-MAP-064–067**: Events UI Consolidation — launcher modal replaces popover, EventEngineModal hosts NPC workspace, Help overlay absorbs Settings tab with interactive controls, UI Standard cursor rule enforces WildEncounterModal pattern on all future modals. **BUG-MAP-063/064**: Esc and click priority fixed; help overlay upgraded to full UI standard.
        **BUG-MAP-065**: this file was permanently deleted mid-fix in a prior session (no git repo, no exact-match backup). Rebuilt on top of `backups/map_editor_feature042_20260423_230836/map_editor.py` by re-adding: imports/instantiation for `EventsLauncherModal`/`EventEngineModal`/`WildEncounterModal`/`AudioEngineModal`/`BattleEditorModal`/`EventTriggerModal`/`EventActionModal`/`EventFlagRegistryModal`/`EventPlaceModal`/`EventSpriteModal`/`EventDocPopoutModal`; draw/mouse-motion/mouse-down/mouse-up/wheel/keydown dispatch for all eleven in `draw()`/`run()`; `config_get_section`/`config_set_section`/`_load_full_config`/`_save_full_config` (shared `tools/map_editor_config.json`, sections keyed by name, `keys` untouched by `save_key_config` merge fix); `list_all_map_ids`/`map_dims`/`read_map_events`/`write_map_events`/`read_map_music_track`/`write_map_music_track`/`list_audio_track_stems`/`_pokemon_species_keys` (arbitrary-map data IO backing the sub-editor modals; species keys sourced from `src/monster.json`, matching `tools/validate_map_events.py`'s `_pokemon_keys`); and the wild-encounter data model (`wild_patches`/`wild_global_encounters`/`wild_encounter` grid, `wild_modal_begin`/`wild_modal_switch_map`/`wild_modal_end`, `_load_wild_data_for_scope`/`_persist_wild_data_for_scope`, `_wild_active_patch`/`_wild_tier_rows`/`_ensure_default_wild_patch`) persisted as top-level `wildPatches`/`wildGlobalEncounters` and `layers.wildEncounter` per `src/map_data.cpp`'s `parseWildPatches`/`parseWildEncounterSpeciesList` — verified against `tools/validate_map_events.py` with zero errors/warnings on a round-tripped test map. `_open_help_overlay`/`_close_help_overlay` gained `tab`/`back_to` params so each sub-editor's Help button can return to its caller; `HELP_GUIDE_TABS` gained a `script_ops` entry. Known gap: `AudioEngineModal._play_preview` and this rebuild's `list_audio_track_stems` both look under `src/audio/*.ogg` per the modal's own docstring, but the project's real BGM assets live under `src/Audio/BGM/*.ogg` — that mismatch predates this rebuild and was left as-is rather than guessed at. See BUG-MAP-071 for the tile-hover-highlight fix (`is_in_map_editor`, `_any_blocking_modal_open`, `_set_map_editor_state`) that motivated this rebuild.

**Follow-up audit (BUG-MAP-089/090/091/092/095, IMPROVEMENT-MAP-093/094)**: after user feedback that the BUG-MAP-065 rebuild above was incomplete, all `~/.cursor/plans/*.plan.md` files (backed up to `backups/cursor_plans_backup_20260708/`) were cross-checked against the rebuilt file and the intact modal files via four parallel subagent audits (wild encounter, event engine, core map editor, UI consolidation). Confirmed and fixed: three runtime-crashing methods `wild_encounter_modal.py` calls but that did not exist (`_wild_default_patch`/`_toggle_wild_species_favorite`/`_wild_handle_panel_click`, BUG-MAP-089) plus missing favorites persistence; `_events_add_at` writing the legacy `"actions"` shape instead of the canonical `script_1` document (BUG-MAP-090, now delegates to `event_script_schema.write_document_to_path`); the Help overlay being drawn under and blocked by whichever modal opened it (BUG-MAP-091, `_open_help_overlay` now closes the caller); the settings key-rebind UI being a non-functional stub plus a missing `rescale_tileset` default binding (BUG-MAP-092); `read_map_music_track`/`write_map_music_track` writing `"music"` instead of the `"musicTrack"` key `src/map_data.cpp` actually reads (BUG-MAP-095); and the toolbar's single-glyph button labels widened/renamed to "Event"/"Overworld"/"Settings" (IMPROVEMENT-MAP-093 — labelled "Settings" rather than the plan's "Help" since that button still opens the legacy Settings overlay, not the Help overlay). Explicitly deferred rather than attempted in this pass, as larger structural redesigns rather than recovery bugs: migrating the standalone Settings overlay into a Help "Settings" tab (IMPROVEMENT-MAP-094); the layer-manager popup + bottom horizontal tileset strip from `map_editor_layer-ui_upgrade_290143ff.plan.md`; and resize-grip completeness in `events_launcher_modal.py`/`battle_editor_modal.py`/`audio_engine_modal.py` (pre-existing, not touched by the BUG-MAP-065 deletion). All fixes verified via headless pygame smoke tests (`SDL_VIDEODRIVER=dummy`) covering each new/changed code path plus a full draw-loop + all-11-modal open/draw/close integration check.

    FUNCTION: MapEditor._any_blocking_modal_open

    SIGNATURE:
        def _any_blocking_modal_open(self) -> bool

    DESCRIPTION:
        BUG-MAP-071: returns whether any full-screen modal/dialog currently covers the map canvas (settings, size/rename/delete prompts, help overlay, or any of the eleven sub-editor modals). Used by `draw()` each frame to compute `is_in_map_editor` and by the `MOUSEMOTION` handler to suppress `hover_cell` while a modal is open.

    PARAMETERS:
        None

    RETURNS:
        bool — True if the map canvas is currently covered by a modal/dialog

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        None

    DEPENDENCIES:
        `help_overlay_open`, and the `.open` flag of each sub-editor modal instance

    FUNCTION: MapEditor._open_events_launcher

    SIGNATURE:
        def _open_events_launcher(self) -> None

    DESCRIPTION:
        FEATURE-MAP-096 Phase 6: opens the Events hub modal. Closes the world workspace if open,
        then calls `events_launcher_modal.open_modal()` and sets a status hint.

    PARAMETERS:
        None

    RETURNS:
        None

    SIDE EFFECTS:
        Sets `world_workspace_open` False; opens launcher modal; status bar message.

    ERROR HANDLING:
        None

    DEPENDENCIES:
        `EventsLauncherModal.open_modal`, `set_status`

    FUNCTION: MapEditor._toggle_events_launcher

    SIGNATURE:
        def _toggle_events_launcher(self) -> None

    DESCRIPTION:
        FEATURE-MAP-096 Phase 6: toggles the Events hub modal open/closed. Bound to the V key
        (`open_events_launcher` in map_editor_config.json).

    PARAMETERS:
        None

    RETURNS:
        None

    SIDE EFFECTS:
        Opens or closes `events_launcher_modal`.

    ERROR HANDLING:
        None

    DEPENDENCIES:
        `_open_events_launcher`, `EventsLauncherModal.close_modal`

    FUNCTION: MapEditor._set_map_editor_state

    SIGNATURE:
        def _set_map_editor_state(self, in_map_editor: bool) -> None

    DESCRIPTION:
        BUG-MAP-071: explicitly sets `is_in_map_editor`. `draw()` recomputes this flag every frame via `_any_blocking_modal_open()`, so this setter exists for callers/tests that want to force the value without waiting for a frame.

    PARAMETERS:
        - in_map_editor: bool — new value for `self.is_in_map_editor`

    RETURNS:
        None

    SIDE EFFECTS:
        Mutates `self.is_in_map_editor`.

    ERROR HANDLING:
        None

    DEPENDENCIES:
        None

    FUNCTION: MapEditor.config_get_section / MapEditor.config_set_section

    SIGNATURE:
        def config_get_section(self, name: str) -> dict
        def config_set_section(self, name: str, section: dict) -> None

    DESCRIPTION:
        Generic per-feature settings store shared by the sub-editor modals (e.g. `eventEngine` split-pane fractions/favorites). Both read and write the same `tools/map_editor_config.json` file used by `load_key_config`/`save_key_config` for keybindings, storing each named section as its own top-level key so a save from one section never clobbers another (including `keys`).

    PARAMETERS:
        - name: str — top-level section key (e.g. `"eventEngine"`)
        - section: dict — replacement value for that section (config_set_section only)

    RETURNS:
        dict — deep copy of the stored section, or `{}` if absent/invalid (config_get_section only)

    SIDE EFFECTS:
        config_set_section rewrites `tools/map_editor_config.json` on disk.

    ERROR HANDLING:
        Missing/corrupt config file is treated as `{}`; OSError/JSONDecodeError are caught.

    DEPENDENCIES:
        `_load_full_config`, `_save_full_config`, `CONFIG_PATH`

    FUNCTION: MapEditor.read_map_events / MapEditor.write_map_events

    SIGNATURE:
        def read_map_events(self, map_id: str) -> list[dict]
        def write_map_events(self, map_id: str, events: list[dict]) -> bool

    DESCRIPTION:
        Cross-map event data access for the Event Engine / Event Place / Event Sprite modals, which browse maps other than the one currently loaded in the main editor. Reads/writes the `events` array of the target map's on-disk JSON directly; if `map_id` matches the main editor's currently loaded map, also mirrors the change into `self.map_events` so a later `save()` from the main editor cannot clobber it with a stale in-memory copy.

    PARAMETERS:
        - map_id: str — target map id (file stem under `MAPS_DIR`)
        - events: list[dict] — full replacement events array (write_map_events only)

    RETURNS:
        list[dict] — deep-copied events (read_map_events); bool — True on successful write (write_map_events)

    SIDE EFFECTS:
        write_map_events rewrites the map's JSON file, mirrors `self.map_events` when scoped to the loaded map, and evicts `_session_map_cache` for that map id.

    ERROR HANDLING:
        Missing file / JSON errors are caught; write_map_events reports failure via `set_status` and returns False.

    DEPENDENCIES:
        `MAPS_DIR`, `sanitize_map_id`, `set_status`

    FUNCTION: MapEditor.wild_modal_begin / wild_modal_switch_map / wild_modal_end

    SIGNATURE:
        def wild_modal_begin(self) -> None
        def wild_modal_switch_map(self, map_id: str) -> None
        def wild_modal_end(self) -> None

    DESCRIPTION:
        FEATURE-MAP-050/058: the Wild Encounter modal reuses the main editor's own map-rendering/painting state (tile grid, walk grid, dimensions) to let the user paint wild-encounter patches onto arbitrary maps inside its own map-picker panel. `wild_modal_begin` snapshots the main editor's currently loaded map (`_snapshot_session_map_bundle`); `wild_modal_switch_map` persists any dirty wild data for the previous scope, loads the target map into the main editor state via `try_load_map_by_id`, then loads that map's wild data (`_load_wild_data_for_scope`); `wild_modal_end` persists the final scope's wild data and restores the main editor's original map (`_restore_session_map_bundle`).

    PARAMETERS:
        - map_id: str — map id to scope the wild-encounter editing session to (wild_modal_switch_map only)

    RETURNS:
        None

    SIDE EFFECTS:
        Mutates nearly all main-editor map state (map_id/map_w/map_h/tile_layers/walk/...) for the duration of the modal session; may write `wildPatches`/`wildGlobalEncounters`/`layers.wildEncounter` to disk on scope change/close.

    ERROR HANDLING:
        Missing/corrupt target map JSON is treated as an empty wild-data scope; write failures are silently skipped (OSError/JSONDecodeError caught).

    DEPENDENCIES:
        `_snapshot_session_map_bundle`, `_restore_session_map_bundle`, `try_load_map_by_id`, `_load_wild_data_for_scope`, `_persist_wild_data_for_scope`, `_sync_wild_data_for_map`, `_ensure_wild_encounter_grid`

    FUNCTION: MapEditor._resize_wild_encounter_grid / _ensure_wild_encounter_grid / _sync_wild_data_for_map / _apply_wild_fields_to_map_data / _mark_wild_dirty

    SIGNATURE:
        def _resize_wild_encounter_grid(self, nw: int, nh: int) -> None
        def _ensure_wild_encounter_grid(self) -> None
        def _sync_wild_data_for_map(self, map_id: str) -> None
        def _apply_wild_fields_to_map_data(self, data: dict) -> None
        def _mark_wild_dirty(self) -> None

    DESCRIPTION:
        BUG-MAP-096/097/098: wild encounter grid lifecycle integrated with map load, session cache, resize, canvas paint, and Save. `_sync_wild_data_for_map` loads wild fields from disk after cold `try_load_map_by_id`; session bundles now include wild patches/grid/dirty flag. `_apply_wild_fields_to_map_data` merges wild JSON used by `_persist_wild_data_for_scope` and `_write_map_json_to_disk`. `_mark_wild_dirty` sets the persist gate for canvas and panel edits.

    PARAMETERS:
        - nw, nh: int — target map dimensions (_resize_wild_encounter_grid)
        - map_id: str — map stem to load wild data for (_sync_wild_data_for_map)
        - data: dict — map JSON object to mutate in place (_apply_wild_fields_to_map_data)

    RETURNS:
        None

    SIDE EFFECTS:
        Mutates `wild_encounter`, `wild_patches`, `wild_global_encounters`, `_wild_modal_dirty`; may write map JSON when persist/save paths run

    ERROR HANDLING:
        Missing map JSON yields empty wild scope; OSError on persist is skipped

    DEPENDENCIES:
        `_load_wild_data_for_scope`, `sanitize_map_id`, `MAPS_DIR`

    FUNCTION: MapEditor.blit_tile_scaled / blit_wild_encounter_cell_overlay

    SIGNATURE:
        def blit_tile_scaled(self, surf: pygame.Surface, ts_id: str, tile_1based: int, dst_x: int, dst_y: int, dst_wh: int) -> None
        def blit_wild_encounter_cell_overlay(self, surf: pygame.Surface, px: int, py: int, cp: int, *, active: bool, selected: bool = False) -> None

    DESCRIPTION:
        QA audit performance: `blit_tile_scaled` LRU-caches scaled tile surfaces keyed by `(ts_id, tile_1based, dst_wh)` up to `SCALED_TILE_CACHE_MAX`. `blit_wild_encounter_cell_overlay` reuses pre-filled SRCALPHA overlays for active/inactive wild cells (selected cells still allocate a blue highlight). `draw()` skips the main map tile loop when `_any_blocking_modal_open()` to avoid redundant raster work under modals.

    PARAMETERS:
        - surf: pygame.Surface — destination surface
        - ts_id: str — tileset id (blit_tile_scaled)
        - tile_1based: int — 1-based tile index (blit_tile_scaled)
        - dst_x, dst_y, dst_wh: int — destination pixel rect (blit_tile_scaled)
        - px, py, cp: int — cell origin and size (blit_wild_encounter_cell_overlay)
        - active: bool — highlight active wild patch index (blit_wild_encounter_cell_overlay)
        - selected: bool — flood-fill selection tint (blit_wild_encounter_cell_overlay)

    RETURNS:
        None

    SIDE EFFECTS:
        Blits to surf; may populate `_scaled_tile_cache` or `_wild_overlay_*` surfaces

    ERROR HANDLING:
        No-op when tile_1based <= 0 or tileset missing

    DEPENDENCIES:
        `ensure_sheet`, `pygame.transform.scale`, `_ensure_wild_overlay_surfaces`

    FUNCTION: MapEditor._draw_events_character_frame_overlay

    SIGNATURE:
        def _draw_events_character_frame_overlay(self) -> None

    DESCRIPTION:
        Draws the modal 4×4 NPC sheet picker (scaled grid, selection frame, facing row) when `events_character_frame_pick_open` is set. Computes `avail_w` from `min(map_viewport_rect.w, window)` and `avail_h` from `min(map_canvas_rect.h, window)` so the sheet height budget excludes the layer chip strip; wraps the title with `_wrap_lines_to_width`; builds `title_block_h` from `title_pad_top`, rendered lines, and `title_pad_bottom`; places the scaled sheet at `box.y + title_block_h + gap_before_grid`; centers `box` on `map_canvas_rect` and clamps horizontally to the window and vertically to `[max(margin, canvas.y), window - margin]`.

    PARAMETERS:
        None

    RETURNS:
        None

    SIDE EFFECTS:
        Blits to `self.screen`; sets `self._events_character_frame_box`, `self._events_character_sheet_inner`, and `self._events_character_facing_hit`.

    ERROR HANDLING:
        None

    DEPENDENCIES:
        `_wrap_lines_to_width`, `pygame.transform.smoothscale`, `EVENT_CHARACTER_SHEET_COLS`, `EVENT_CHARACTER_SHEET_ROWS`

    FUNCTION: _expand_visual_text_lines

    SIGNATURE:
        def _expand_visual_text_lines(font: pygame.font.Font, lines: list[str], max_pixel_w: int) -> list[str]

    DESCRIPTION:
        Replaces any logical line wider than ``max_pixel_w`` with multiple lines from ``event_script_opcode_docs._wrap_words`` so the event script modal doc column does not clip text.

    PARAMETERS:
        - font: pygame.font.Font — font used for measurement and later rendering
        - lines: list[str] — logical lines from ``build_structured_doc_lines``
        - max_pixel_w: int — maximum pixel width per rendered line

    RETURNS:
        list[str] — possibly longer list with wrapped segments

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        None

    DEPENDENCIES:
        - `_load_event_script_opcode_docs_module`

    FUNCTION: _expand_help_overlay_segments

    SIGNATURE:
        def _expand_help_overlay_segments(font: pygame.font.Font, segments: list[tuple[str, str, str | None]], max_pixel_w: int) -> list[tuple[str, str, str | None]]

    DESCRIPTION:
        Expands help overlay rows whose text is wider than ``max_pixel_w``. ``body`` rows use ``_wrap_words`` (indent-preserving); ``head`` and ``toc`` use ``_wrap_lines_to_width``.

    PARAMETERS:
        - font: pygame.font.Font — small font used in the help panel
        - segments: list[tuple[str, str, str | None]] — (kind, text, extra) from ``_help_build_lines``
        - max_pixel_w: int — content width minus horizontal padding

    RETURNS:
        list[tuple[str, str, str | None]] — expanded segment list for layout and draw

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        None

    DEPENDENCIES:
        - `_load_event_script_opcode_docs_module`
        - `_wrap_lines_to_width`

    FUNCTION: MapEditor._draw_world_workspace

    SIGNATURE:
        def _draw_world_workspace(self) -> None

    DESCRIPTION:
        Fills the map canvas with the world grid, proximity links, scaled map thumbnails, selection borders, and optional name badges (BUG-MAP-WORLD-007: no persistent help text on the canvas; shortcuts are in the **H** help guide and footer hint).

    PARAMETERS:
        None

    RETURNS:
        None

    SIDE EFFECTS:
        Mutates the display surface inside `map_canvas_rect` only (via `set_clip` / restore).

    ERROR HANDLING:
        None

    DEPENDENCIES:
        `_world_world_to_screen`, `_draw_world_proximity_links`, `_ensure_world_thumbnail`, `_world_blit_map_label`, `_world_grid_step_for_zoom`

    FUNCTION: MapEditor._world_snap_node_origin_to_grid

    SIGNATURE:
        def _world_snap_node_origin_to_grid(self, n: dict) -> None

    DESCRIPTION:
        Sets `worldX` and `worldY` to the nearest integer map-tile coordinates using `round()` for consistent snap to grid (BUG-MAP-WORLD-009).

    PARAMETERS:
        - n: dict — in-place world node record

    RETURNS:
        None

    SIDE EFFECTS:
        Mutates `n["worldX"]` and `n["worldY"]`.

    ERROR HANDLING:
        None

    DEPENDENCIES:
        None

    FUNCTION: MapEditor._world_grid_step_for_zoom

    SIGNATURE:
        def _world_grid_step_for_zoom(self, z: float, canvas: pygame.Rect) -> int

    DESCRIPTION:
        Returns world-space grid line spacing in tile units: `1` when zoomed in enough that line count stays bounded; otherwise the smallest power-of-two step (capped) so the background grid stays cheap to draw.

    PARAMETERS:
        - z: float — clamped world zoom (pixels per world tile)
        - canvas: pygame.Rect — map canvas rect (used for visible world span)

    RETURNS:
        int — grid step in world tile units (>= 1)

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        None

    DEPENDENCIES:
        None

    FUNCTION: MapEditor._world_blit_map_label

    SIGNATURE:
        def _world_blit_map_label(self, dst: pygame.Rect, stem: str, z: float) -> None

    DESCRIPTION:
        Renders a truncated map id on a semi-opaque black badge positioned at the top-left of the node’s screen rect, clamped to stay inside `map_canvas_rect`.

    PARAMETERS:
        - dst: pygame.Rect — screen-space bounds of the scaled thumbnail
        - stem: str — map id / file stem text
        - z: float — world zoom factor used to pick font pixel size

    RETURNS:
        None

    SIDE EFFECTS:
        Blits onto `self.screen`.

    ERROR HANDLING:
        None

    DEPENDENCIES:
        `_world_font_for_label_size`, `map_canvas_rect`

    FUNCTION: MapEditor._refresh_overworld_view_player_config

    SIGNATURE:
        def _refresh_overworld_view_player_config(self, force: bool = False) -> None

    DESCRIPTION:
        Loads player visual footprint and collision footprint settings from `src/overworld_view.json`, including `playerDrawOffsetTilesX`, then clamps and caches values used by walk-mode previews and valid-stand calculations.

    PARAMETERS:
        - force: bool - Forces reload even when file mtime is unchanged.

    RETURNS:
        None

    SIDE EFFECTS:
        Updates `_ov_player_tiles_w`, `_ov_player_tiles_h`, `_ov_player_draw_off_x`, `_ov_collision_off_x`, `_ov_collision_off_y`, `_ov_collision_w`, `_ov_collision_h`.
        Invalidates valid-stand cache when any relevant overworld footprint field changes.

    ERROR HANDLING:
        Ignores file/parse/type errors and keeps clamped defaults.

    DEPENDENCIES:
        `OVERWORLD_VIEW_JSON_PATH`, `json.load`, `_invalidate_valid_stands_cache`

    FUNCTION: MapEditor._draw_walk_mode_player_footprint_preview

    SIGNATURE:
        def _draw_walk_mode_player_footprint_preview(self) -> None

    DESCRIPTION:
        In walk mode, draws the visual player footprint box and collision-cell outlines at the hovered anchor using the same X draw-offset (`_ov_player_draw_off_x`) and collision offsets as runtime movement logic.

    PARAMETERS:
        None

    RETURNS:
        None

    SIDE EFFECTS:
        Draws tinted preview surfaces and outline rectangles onto `self.screen` within `map_canvas_rect`.

    ERROR HANDLING:
        Returns early when there is no hover cell.

    DEPENDENCIES:
        `_refresh_overworld_view_player_config`, `map_canvas_rect`, `pygame.draw.rect`

    FUNCTION: MapEditor._player_anchor_walkable

    SIGNATURE:
        def _player_anchor_walkable(self, ax: int, ay: int) -> bool

    DESCRIPTION:
        Returns whether the player collision sub-rectangle at anchor `(ax, ay)` is fully in bounds and all corresponding walk cells are clear, with horizontal sampling shifted by `_ov_player_draw_off_x` to match runtime collision column selection.

    PARAMETERS:
        - ax: int - Anchor X in map tile coordinates.
        - ay: int - Anchor Y in map tile coordinates.

    RETURNS:
        bool - `True` when every collision cell is in-bounds and walk value `0`.

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        Returns `False` when walk grid is missing/empty, dimensions are invalid, or any collision cell goes out of bounds.

    DEPENDENCIES:
        `_ov_player_draw_off_x`, `_ov_collision_off_x`, `_ov_collision_off_y`, `_ov_collision_w`, `_ov_collision_h`, `self.walk`

    FUNCTION: MapEditor._draw_valid_player_stands_overlay

    SIGNATURE:
        def _draw_valid_player_stands_overlay(self, color: tuple[int, int, int] = (40, 255, 90)) -> None

    DESCRIPTION:
        Draws colored outlines for the union of valid visual player footprints, applying `_ov_player_draw_off_x` when mapping anchor cells to covered map columns so overlay tiles align with walk-mode previews and runtime collision.

    PARAMETERS:
        - color: tuple[int, int, int] - RGB line color for the overlay (green for J toggle, orange for K toggle).

    RETURNS:
        None

    SIDE EFFECTS:
        Draws line segments on `self.screen` for visible overlay boundaries.

    ERROR HANDLING:
        Returns early when no cached anchors exist or map dimensions are invalid.

    DEPENDENCIES:
        `_rebuild_valid_stands_cache_if_needed`, `_ov_player_draw_off_x`, `map_canvas_rect`, `pygame.draw.line`

    FUNCTION: MapEditor._alloc_walk_trans

    SIGNATURE:
        def _alloc_walk_trans(self) -> None

    DESCRIPTION:
        Allocates and resets `walk`, `transparent`, and `over_player` binary grids to current map dimensions.

    PARAMETERS:
        None

    RETURNS:
        None

    SIDE EFFECTS:
        Replaces three grid buffers and invalidates valid-stand cache.

    ERROR HANDLING:
        None

    DEPENDENCIES:
        `_invalidate_valid_stands_cache`

    FUNCTION: MapEditor._wild_default_patch

    SIGNATURE:
        def _wild_default_patch(self, n: int) -> dict

    DESCRIPTION:
        BUG-MAP-089: returns a freshly-created default wild-encounter patch dict, id `patch_<n>` (1-based), `stepChancePercent` 10, empty common/uncommon/rare encounter lists. Shared by `_ensure_default_wild_patch` and the "New" patch-panel button (`_wild_handle_panel_click`).

    PARAMETERS:
        - n: int — 1-based patch number used to build the `id` field

    RETURNS:
        dict — new patch dict, not yet appended to `self.wild_patches`

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        None

    DEPENDENCIES:
        None

    FUNCTION: MapEditor._toggle_wild_species_favorite / _load_wild_species_favorites / _save_wild_species_favorites

    SIGNATURE:
        def _toggle_wild_species_favorite(self, species: str) -> None
        def _load_wild_species_favorites(self) -> None
        def _save_wild_species_favorites(self) -> None

    DESCRIPTION:
        BUG-MAP-089: stars/unstars a species name in `self.wild_species_favorites` (used by the wild-encounter species picker's star icon to bubble common picks to the top) and persists the set to `tools/map_editor_config.json` under `wildEncounterEditor.favoriteSpecies`. `_load_wild_species_favorites` restores the set at startup (called once from `__init__`); `_save_wild_species_favorites` is called after every toggle.

    PARAMETERS:
        - species: str — species key/name to toggle (_toggle_wild_species_favorite only)

    RETURNS:
        None

    SIDE EFFECTS:
        Mutates `self.wild_species_favorites`; `_save_wild_species_favorites`/`_toggle_wild_species_favorite` rewrite `tools/map_editor_config.json`.

    ERROR HANDLING:
        None (config_get_section/config_set_section already treat a missing/corrupt config as empty)

    DEPENDENCIES:
        `config_get_section`, `config_set_section`

    FUNCTION: MapEditor._wild_handle_panel_click

    SIGNATURE:
        def _wild_handle_panel_click(self, mx: int, my: int) -> bool

    DESCRIPTION:
        BUG-MAP-089: handles the local patch list's New/Del/Merge buttons (`_wild_new_btn`/`_wild_delete_btn`/`_wild_merge_btn`, set each frame by `WildEncounterModal._draw_local_section`). New appends `_wild_default_patch` and selects it. Del removes the active patch, clears grid cells that referenced it to 0, and shifts down the 1-based patch ids of every grid cell referencing a higher-indexed patch. Merge (no-op with an error status if the active patch is index 0) folds the active patch's common/uncommon/rare encounter rows into the previous patch, remaps the active patch's grid cells onto the previous patch's id, shifts down higher ids, then removes the active patch — mirroring Del's renumbering.

    PARAMETERS:
        - mx: int — mouse x in screen coordinates
        - my: int — mouse y in screen coordinates

    RETURNS:
        bool — True if a button was hit and handled (caller marks the wild-encounter session dirty), False otherwise

    SIDE EFFECTS:
        Mutates `self.wild_patches`, `self.wild_encounter`, `self.active_wild_patch_index`, `self.selected_wild_patch_index`; calls `_undo_checkpoint()` before any mutation; calls `set_status`.

    ERROR HANDLING:
        Out-of-range `active_wild_patch_index` is guarded; Merge on the first patch reports an error status instead of mutating.

    DEPENDENCIES:
        `_wild_default_patch`, `_undo_checkpoint`, `set_status`

    FUNCTION: MapEditor._open_wild_canvas_mode / _close_wild_canvas_mode / _wild_canvas_paint_cells / _draw_wild_patches_panel / _wild_canvas_panel_click

    SIGNATURE:
        def _open_wild_canvas_mode(self) -> None
        def _close_wild_canvas_mode(self) -> None
        def _wild_canvas_paint_cells(self, x0: int, y0: int, x1: int, y1: int, button: int) -> None
        def _draw_wild_patches_panel(self) -> None
        def _wild_canvas_panel_click(self, mx: int, my: int) -> bool

    DESCRIPTION:
        FEATURE-MAP-098: dual-path wild editing on the main map canvas (alongside `WildEncounterModal`). `_open_wild_canvas_mode` sets `wild_canvas_mode_open`, calls `_sync_wild_data_for_map` for the active map, ensures a default patch, and shrinks `map_canvas_rect` by `_WILD_CANVAS_PANEL_W` for a right-side patch panel. LMB/RMB drag on the main map paints or erases `layers.wildEncounter` indices with stride snap (`_wild_snap_cell`); each stroke calls `_mark_wild_dirty`. Esc closes canvas mode via `_close_wild_canvas_mode`, which persists dirty wild data to disk. Ctrl+S includes wild fields through `_write_map_json_to_disk` → `_apply_wild_fields_to_map_data`. The Wild modal "Main map" button and Events launcher Wild RMB call `_open_wild_canvas_mode`; "Full Wild editor…" on the panel reopens the modal.

    PARAMETERS:
        - x0, y0, x1, y1: int — inclusive map cell bounds for a paint stroke (_wild_canvas_paint_cells)
        - button: int — pygame mouse button (1 paint, 3 erase) (_wild_canvas_paint_cells)
        - mx, my: int — screen coordinates (_wild_canvas_panel_click)

    RETURNS:
        bool — True when `_wild_canvas_panel_click` handled a panel hit

    SIDE EFFECTS:
        Mutates `wild_encounter`, `wild_patches`, active/selected patch indices, layout rects; may open/close `WildEncounterModal`

    ERROR HANDLING:
        Out-of-bounds cells are skipped during paint; panel clicks outside the docked rect return False from `_wild_canvas_panel_click`

    DEPENDENCIES:
        `_sync_wild_data_for_map`, `_mark_wild_dirty`, `_persist_wild_data_for_scope`, `_wild_snap_cell`, `_wild_default_patch`, `_wild_handle_panel_click`, `snap_cell_to_stride_grid`, `WildEncounterModal.close_modal(switch_to_canvas=True)`

    FUNCTION: MapEditor._open_help_overlay / _close_help_overlay

    SIGNATURE:
        def _open_help_overlay(self, tab: str = "home", back_to: str | None = None) -> None
        def _close_help_overlay(self) -> None

    DESCRIPTION:
        BUG-MAP-091: `_open_help_overlay` now closes whichever sub-editor modal is named by `back_to` (via that modal's own `close_modal()`, so scoped state like the Wild Encounter modal's map-swap is cleaned up correctly) before showing the help overlay, so help is drawn on top of and receives input instead of being hidden behind a still-open modal. `_close_help_overlay` symmetrically calls `open_modal()` on that same modal when help closes, restoring the caller.

    PARAMETERS:
        - tab: str — help tab id to open on (_open_help_overlay only; falls back to "home" if unknown)
        - back_to: str | None — one of "engine"/"launcher"/"wild"/"audio"/"battle" naming the calling modal (_open_help_overlay only)

    RETURNS:
        None

    SIDE EFFECTS:
        Closes/reopens the named sub-editor modal; mutates `help_overlay_open`, `help_tab`, `help_scroll_y`, `_help_back_to`, `settings_capture`, `help_search_focus`.

    ERROR HANDLING:
        Unknown `back_to` values are ignored (no modal is closed/reopened); unknown `tab` values fall back to "home".

    DEPENDENCIES:
        Each sub-editor modal's `close_modal`/`open_modal`

    FUNCTION: MapEditor._help_default_tab_for_context

    SIGNATURE:
        def _help_default_tab_for_context(self) -> str

    DESCRIPTION:
        FEATURE-MAP-085: returns the help tab id to open when the user presses H or the Help toolbar button without an explicit tab. Event Engine modal open → `script_ops`; events workspace, wild canvas mode, or events/wild launcher modals open → `events`; otherwise `home`.

    RETURNS:
        str — a valid `HELP_GUIDE_TABS` tab id

    SIDE EFFECTS:
        None

    FUNCTION: MapEditor._help_build_search_index / _help_search_results

    SIGNATURE:
        def _help_build_search_index(self, wrap_w: int) -> list[tuple[str, str, str, int]]
        def _help_search_results(self, wrap_w: int) -> list[tuple[str, str, str, int]]

    DESCRIPTION:
        FEATURE-MAP-085: builds a lazy per-wrap-width index of searchable help body lines from all non-home/non-settings tabs; `_help_search_results` filters by `help_search` (case-insensitive substring match on body, section head, or tab id).

    PARAMETERS:
        - wrap_w: int — pixel width used when building wrapped help lines

    RETURNS:
        list of `(tab_id, section_head, body_snippet, scroll_line_px)` tuples

    SIDE EFFECTS:
        Caches index in `_help_search_index_cache` until wrap width changes

    FUNCTION: MapEditor._draw_help_settings_content / _help_handle_settings_click / _help_handle_settings_keydown

    SIGNATURE:
        def _draw_help_settings_content(self, content: pygame.Rect) -> None
        def _help_handle_settings_click(self, mx: int, my: int) -> bool
        def _help_handle_settings_keydown(self, event: pygame.event.Event) -> bool

    DESCRIPTION:
        IMPROVEMENT-MAP-094 / FEATURE-MAP-097: renders and handles interactive settings (event layer add/remove, remove current tile layer, Event Engine map-scope checkbox persisted as `eventEngine.selectSwitchesMainMap`, key rebinding rows) inside the Help overlay when `help_tab == "settings"`. Replaces the removed `_draw_settings_overlay` / `settings_open` flow.

    SIDE EFFECTS:
        May mutate `key_config`, open layer-remove confirm, call `add_event_layer` / `request_remove_event_layer`, or close help when removing a layer

    DEPENDENCIES:
        `save_key_config`, `default_key_config`, `pygame_key_to_name`, `add_event_layer`, `request_remove_event_layer`

    FUNCTION: pygame_key_to_name

    SIGNATURE:
        def pygame_key_to_name(key_code: int) -> str | None

    DESCRIPTION:
        BUG-MAP-092: reverse lookup of `key_name_to_pygame`, built from the shared module-level `_KEY_NAME_TABLE` dict (both functions now read from this single table instead of each declaring its own copy). Used by the settings key-rebind capture flow to translate a pressed `pygame.KEYDOWN` key back into the string name format stored in `key_config`/`default_key_config`.

    PARAMETERS:
        - key_code: int — a `pygame.K_*` constant (`event.key`)

    RETURNS:
        str | None — the config name for that key, or None if the key has no entry in `_KEY_NAME_TABLE`

    SIDE EFFECTS:
        None

    ERROR HANDLING:
        Unrecognized key codes return None; callers show an "Unsupported key" status instead of rebinding.

    DEPENDENCIES:
        `_KEY_NAME_TABLE`

    FUNCTION: MapEditor.read_map_music_track / write_map_music_track (BUG-MAP-095 fix)

    SIGNATURE:
        def read_map_music_track(self, map_id: str) -> str
        def write_map_music_track(self, map_id: str, track: str) -> bool

    DESCRIPTION:
        BUG-MAP-095: now read/write the `"musicTrack"` JSON key (previously `"music"`, which `src/map_data.cpp`'s `MapData::musicTrack` parser never read — tracks assigned via the Audio Engine modal silently never played in-game). Behavior otherwise unchanged: direct read/write of the target map's JSON file, independent of whichever map is currently loaded in the main editor.

    PARAMETERS:
        - map_id: str — target map id (file stem under `MAPS_DIR`)
        - track: str — audio track stem to assign, or "" to clear (write_map_music_track only)

    RETURNS:
        str — assigned track stem or "" (read_map_music_track); bool — True on successful write (write_map_music_track)

    SIDE EFFECTS:
        write_map_music_track rewrites the map's JSON file and evicts `_session_map_cache`; mirrors into `self._map_music_track` when `map_id` matches the currently loaded map.

    ERROR HANDLING:
        Missing file / JSON errors are caught and treated as "" / False.

    DEPENDENCIES:
        `MAPS_DIR`, `sanitize_map_id`

FILE: tools/events_launcher_modal.py

    PURPOSE:
        EventsLauncherModal — UI-Standard launcher modal (FEATURE-MAP-064). Opened from the
        map editor Events toolbar button (RMB) or V key. 2×3 grid: Event Engine, Wild
        Encounters, Audio Engine, Battle Editor, Help. Delegates to sub-editor modals and
        `_open_help_overlay(back_to="launcher")`.

    DEPENDENCIES:
        - pygame
        - tools/map_editor.py (MapEditor)
        - tools/event_engine_modal.py (EventEngineModal)
        - tools/wild_encounter_modal.py (WildEncounterModal)
        - tools/audio_engine_modal.py (AudioEngineModal)
        - tools/battle_editor_modal.py (BattleEditorModal)

    KEY COMPONENTS:
        - `EventsLauncherModal` class with `open_modal`, `close_modal`, `draw`, `handle_*` methods
        - 2×3 button grid in modal body
        - UI Standard: `_panel_override`, `_drag_mode`, `_title_bar`, `_resize_corner_br/bl`, `_clamp_panel`

    NOTES:
        Minimum panel 640×480. BR+BL resize grips and title-bar drag-to-move. Replaces the old events_tool_popover.

FILE: tools/event_engine_modal.py

    PURPOSE:
        EventEngineModal — UI-Standard 3-panel modal for editing events and their scripts on any
        map. Left: map search + clickable mini-map (thumbnail + 2×2 event hulls) + map list +
        events list. Middle: nested block editor with subflow tabs. Right: opcode docs.
        Phase 3: session undo/redo (Ctrl+Z/Ctrl+Y); cascade context menus via
        event_script_ctx_menu for events list and block panel. FEATURE-MAP-069.

    DEPENDENCIES:
        - pygame
        - tools/event_script_schema.py (steps<->tree, defaults, validate_balanced, file IO)
        - tools/event_script_opcode_docs.py (structured doc lines)
        - tools/event_script_ctx_menu.py (configurable cascade RMB menus)
        - tools/map_editor.py (config_get/set_section, list_all_map_ids, read/write_map_events,
          map_dims, _thumbnail_surface_for_map_stem, event_place_modal, event_sprite_modal,
          events_launcher_modal)

    KEY COMPONENTS:
        - `EventEngineModal` class (open_modal/close_modal/draw/handle_*)
        - `_draw_mini_map`, `_set_event_anchor`, `_begin_submodal_edit`, `_undo_checkpoint`, `_undo_session`, `_redo_session`
        - `_block_ctx_tree`, `_event_ctx_tree`, `_draw_ctx_cascade`, `_dispatch_ctx_action_id`
        - Four draggable splitters; session buffer (`sel_map_id`, `events`, `flows`)

    NOTES:
        Minimum panel 640×480. Session undo stacks capped at 50; cleared on modal close or map switch.
        `_begin_submodal_edit()` checkpoints before View in Map / Assign Sprite opens.
        Scripts with unbalanced control-flow blocks are not saved (validate_balanced gate).
        FEATURE-MAP-074/076/077/078/079/080: subflow tab strip + far-left library/search menu + per-tab RMB menu; `self.flows` (main + subflows) with `@property tree` proxy; region/comment/label/set_var/if_var rendering and palette actions; collapsible map/event selectors and documentation panel (search + scroll + pop-out); RMB "Edit in modal" (EventActionModal), "Change Trigger" (EventTriggerModal), and registry button (EventFlagRegistryModal). Flow IO via event_script_schema.read_flows_from_path / write_flows_to_path.
        FEATURE-MAP-081: Documentation panel layout-level collapse (22px strip with expand + Pop
        buttons, mid_w absorbs freed width, mirrors left_collapsed pattern). Collapsible action
        categories with caret headers, indented op rows, auto-expand on search, collapse state
        persisted in eventEngine config section. Paired palette ordering (opener before end_*).
        Block nesting: selecting an open block inserts new steps as last child via
        `_insert_target_for_selection()`; region blocks display args.name. Bare end_* palette
        drags rejected with red highlight and status bar warning.

FILE: tools/event_place_modal.py

    PURPOSE:
        EventPlaceModal — UI-Standard "View in Map" sub-modal. Renders the selected map via the
        map editor thumbnail surface (works for any map without disturbing the session) and sets
        the selected event's 2x2 anchor on click. FEATURE-MAP-069.

    DEPENDENCIES:
        - pygame
        - tools/map_editor.py (read/write_map_events, map_dims, _thumbnail_surface_for_map_stem,
          event_engine_modal)

    KEY COMPONENTS:
        - `EventPlaceModal` class (open_for/close_modal/draw/handle_*)
        - Fit-to-body initial framing; wheel zoom (cursor-anchored), right-drag pan, left-click place

    NOTES:
        Minimum panel 640×480. Save persists events; Cancel discards; both reopen the Event Engine.

FILE: tools/event_sprite_modal.py

    PURPOSE:
        EventSpriteModal — UI-Standard "Assign Sprite" sub-modal. Assigns a sprite to the selected
        event: kind selector, searchable PNG list, and (for characters) a 4x4 frame grid plus
        facing selection. FEATURE-MAP-069.

    DEPENDENCIES:
        - pygame
        - tools/map_editor.py (_graphics_dir_for_kind, _list_png_names_cached,
          _get_character_frame_surface, read/write_map_events, event_engine_modal)

    KEY COMPONENTS:
        - `EventSpriteModal` class (open_for/close_modal/draw/handle_*)
        - Seeds from any existing ev["sprite"]; writes kind/file/frame/facing on Save

    NOTES:
        Minimum panel 640×480. Character sprites use a 4x4 sheet (sheetColumns/sheetRows = 4).

FILE: tools/event_doc_popout_modal.py

    PURPOSE:
        EventDocPopoutModal — FEATURE-MAP-079 UI-Standard full-window opcode documentation
        reader (searchable opcode list + structured detail pane). Opened from the Event Engine
        documentation panel "pop out" button. Read-only.

    DEPENDENCIES:
            - pygame
            - tools/event_script_opcode_docs.py (structured doc lines)
            - tools/event_script_schema.py (opcode list)

    KEY COMPONENTS:
            - `EventDocPopoutModal` class (open/open_for/close_modal/draw/handle_*)

    NOTES:
        Read-only viewer; live search filter; wheel scroll. No persistence.

FILE: tools/event_action_modal.py

    PURPOSE:
        EventActionModal — FEATURE-MAP-079 UI-Standard editor for a single action's args
        (type-aware fields, variable/flag picker+create, goto label dropdown, call_subflow
        vars rows). Complements inline block editing ("Edit in modal").

    DEPENDENCIES:
            - pygame
            - tools/event_script_schema.py (arg metadata, labels_in_steps, list_library_subflow_names)
            - tools/flag_registry_modal.py (flag/variable names)

    KEY COMPONENTS:
            - `EventActionModal` class (open_for(engine, flow_name, node_path)/_apply/draw/handle_*)

    NOTES:
        On Apply calls `engine._undo_checkpoint()` then mutates the target flow node; engine persists script JSON.
        Minimum panel 640×480; BR+BL resize grips. FEATURE-MAP-081: call_subflow name picker lists in-file subflows + _library
        connectors instead of opening the flag/variable registry. Sentinel "(no subflows)"
        ignored on selection.

FILE: tools/event_trigger_modal.py

    PURPOSE:
        EventTriggerModal — FEATURE-MAP-078 UI-Standard editor for an event trigger (type,
        flag run-condition, clearedFlag, onComplete set/clear flag lists). Mirrors C++
        MapEventTrigger semantics.

    DEPENDENCIES:
            - pygame
            - tools/map_editor.py (read/write_map_events, event_engine_modal)
            - tools/flag_registry_modal.py (flag picker)

    KEY COMPONENTS:
            - `EventTriggerModal` class (open_for(map_id, event_index)/draw/handle_*)

    NOTES:
        Save calls `engine._undo_checkpoint()` then writes ev["trigger"]/["clearedFlag"]/["onComplete"]; reopens the Event Engine.
        Minimum panel 640×480; BR+BL resize grips.

FILE: tools/flag_registry_modal.py

    PURPOSE:
        EventFlagRegistryModal — FEATURE-MAP-080 UI-Standard manager for the global flag and
        variable registry (src/maps/scripts/flag_registry.json): declare/list/rename + initial
        values. Exposes shared helpers (load_registry, save_registry, ensure_flag,
        ensure_variable, flag_names, variable_names) used by the action/trigger modals.

    DEPENDENCIES:
            - pygame
            - json / pathlib

    KEY COMPONENTS:
            - `EventFlagRegistryModal` class (draw/handle_*)
            - module helpers: load_registry / save_registry / ensure_flag / ensure_variable /
              flag_names / variable_names

    NOTES:
        Editor-side source of truth for default flag values; the C++ GameState (FEATURE-MAP-072)
        reads the same file for initial state. Variables are typed scratch declarations only.

FILE: include/music_manager.h

    PURPOSE:
        FEATURE-MAP-087: Declares route/battle BGM playback API backed by SDL2_mixer when available.

    DEPENDENCIES:
            - SDL2_mixer (optional at link time)

    KEY COMPONENTS:
            - MusicManager::playRouteMusic
            - MusicManager::playOnce
            - MusicManager::stop

    NOTES:
        When SDL2_mixer is not installed, implementation compiles as a no-op stub.

FILE: src/music_manager.cpp

    PURPOSE:
        Implements MusicManager; loads `src/audio/<stem>.ogg` for looping route music and one-shots.

    DEPENDENCIES:
            - music_manager.h
            - SDL2_mixer when USE_SDL2_MIXER is defined

    FUNCTION: MusicManager::playRouteMusic

    SIGNATURE:
        void playRouteMusic(const std::string& trackStem, int fadeMs = 0)

    DESCRIPTION:
        Starts looping BGM for the given stem; optional crossfade when fadeMs > 0.

    PARAMETERS:
            - trackStem: string — filename without directory or extension
            - fadeMs: int — fade duration in milliseconds

    RETURNS:
        void

    SIDE EFFECTS:
        SDL_mixer music channel state

    ERROR HANDLING:
        Logs to stderr when load/init fails; no throw

    DEPENDENCIES:
            - Mix_LoadMUS, Mix_PlayMusic, Mix_FadeInMusic

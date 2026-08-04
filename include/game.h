#ifndef GAME_H
#define GAME_H

#include <SDL.h>
#include <SDL_ttf.h>

#include <array>
#include <cstdint>
#include <json.hpp>
#include <map>
#include "game_state.h"
#include "map_data.h"
#include "music_manager.h"
#include "perf_stats.h"
#include "script_engine.h"
#include <memory>
#include <optional>
#include <ostream>
#include <string>
#include <vector>

class Battle;

struct BattleBackgroundEntry
{
    std::string id;
    SDL_Texture* texture = nullptr;
};

struct TextCacheKey
{
    std::string text;
    Uint8 r = 0;
    Uint8 g = 0;
    Uint8 b = 0;
    Uint8 a = 0;

    bool operator<(const TextCacheKey& rhs) const
    {
        if (text != rhs.text)
        {
            return text < rhs.text;
        }
        if (r != rhs.r)
        {
            return r < rhs.r;
        }
        if (g != rhs.g)
        {
            return g < rhs.g;
        }
        if (b != rhs.b)
        {
            return b < rhs.b;
        }
        return a < rhs.a;
    }
};

struct TextCacheEntry
{
    SDL_Texture* texture = nullptr;
    int width = 0;
    int height = 0;
};

using json = nlohmann::json;

inline constexpr const char* kPokemonDbKey = "Pokemon";
inline constexpr const char* kMoveCatalogKey = "MoveCatalog";

enum class Type
{
    Normal,
    Fire,
    Water,
    Electric,
    Grass,
    Ice,
    Fighting,
    Poison,
    Ground,
    Flying,
    Psychic,
    Bug,
    Rock,
    Ghost,
    Dragon,
    Dark,
    Steel,
    Fairy,
    COUNT
};

enum class MoveCategory
{
    Physical,
    Special,
    Status
};

struct MoveTemplate
{
    std::string id;
    std::string name;
    Type moveType = Type::Normal;
    MoveCategory category = MoveCategory::Physical;
    int power = 0;
    int accuracy = -1;
    int pp = 0;
};

enum class StatId
{
    Hp,
    Atk,
    Def,
    SpAtk,
    SpDef,
    Spd
};

struct PokemonStats
{
    int hp = 0;
    int atk = 0;
    int def = 0;
    int spAtk = 0;
    int spDef = 0;
    int spd = 0;
};

class Game
{
private:
    struct MapTilesetRenderMeta
    {
        SDL_Texture* texture = nullptr;
        const TilesetDef* def = nullptr;
        int columns = 1;
    };

    /// FEATURE-MAP-029: one placed map instance in world tile space (render list order = painter back-to-front).
    struct WorldLayoutMapInstance
    {
        std::string instanceId;
        std::string mapId;
        int worldOriginX = 0;
        int worldOriginY = 0;
        int widthTiles = 0;
        int heightTiles = 0;
        MapData map;
        bool walkabilityGridValid = false;
        bool overPlayerGridValid = false;
    };

    json pokedb{};
    json battleCfg_{};
    SDL_Window* window = nullptr;
    SDL_Renderer* renderer = nullptr;
    bool sdlInitialized = false;

    std::string displayText_;
    std::vector<std::string> displayTextLines_;
    /// When false, only corner battle sprites are drawn (no main-panel sprite or stats text).
    bool showMainSpriteAndStats_ = true;
    TTF_Font* font_ = nullptr;
    bool ttfInitialized_ = false;

    SDL_Texture* pokemonSprite_ = nullptr;
    SDL_Texture* cornerBL_ = nullptr;
    SDL_Texture* cornerTR_ = nullptr;
    bool imageInitialized_ = false;
    int displayTextTopY_ = 16;
    int displayTextLeftX_ = 16;

    void createPokemon(json& data, const std::string& key);
    void applyBattleView(const Battle& battle);
    void drawBattleHealthBars(const Battle& battle);
    void drawHealthBar(int x, int y, int w, int h, int current, int max, const std::string& label);
    void drawBattleMovePrompt(const Battle& battle);
    void returnToTitle();

    void drawDebugDexModal();
    int maxPokedexNum() const;
    std::optional<std::string> speciesKeyForPokedexNum(int n) const;
    std::optional<std::string> pickRandomFoeKey(const std::string& playerKey) const;
    void tryConfirmDebugDexEntry();

    bool debugDexEntryActive_ = false;
    std::string debugDexInput_;
    std::string debugDexError_;

    std::unique_ptr<Battle> activeBattle_{};

    std::vector<BattleBackgroundEntry> battleBackgrounds_;
    size_t debugBattleBgIndex_ = 0;

    void loadBattleBackgroundTextures();
    void destroyBattleBackgroundTextures();
    void drawBattleBackgroundIfActive();
    void drawBattleBackgroundDebugLabel();

    bool initVideo();
    bool initFont();
    bool initImage();
    void destroyPokemonSprite();
    void destroyCornerSprites();
    bool loadPokemonSprite(const char* relativePath);
    bool loadIntoTexture(SDL_Texture*& target, const std::string& path);
    void drawPokemonSprite();
    void drawCornerSprites();
    void renderText(const std::string& text, int x, int y, SDL_Color color);
    void clearTextCache_();
    void warmStaticTextCache_();
    void setDisplayText_(std::string text);
    void rebuildDisplayTextLines_();
    void drawDisplayText();
    /// FEATURE-GAME-001 / FEATURE-GAME-002: F3 = RAM/CPU; F4 = keybinds (replaces F3 when on).
    void drawPerfHud_();
    void drawKeybindHud_();

    bool showPerfHud_ = false;
    bool showKeybindHud_ = false;
    PerfSampler perfSampler_{};
    std::int64_t fpsWindowStartNs_ = 0;
    int fpsWindowFrames_ = 0;
    int fpsDisplay_ = 0;

    /// FEATURE-MAP-008 / FEATURE-MAP-027 / FEATURE-MAP-029: map list, single-map view, world_layout composite.
    enum class MapUiMode
    {
        None,
        PickMap,
        ViewMap,
        ViewWorld
    };
    MapUiMode mapUiMode_ = MapUiMode::None;
    std::vector<std::pair<std::string, std::string>> mapCatalog_;
    size_t mapCatalogSel_ = 0;
    /// FEATURE-MAP-029: last catalog error (shown under picker title).
    std::string mapPickerLastError_;
    MapData viewMapData_{};
    std::vector<TilesetDef> mapTilesetDefs_;
    std::map<std::string, SDL_Texture*> mapTilesetTextures_;
    /// FEATURE-MAP-030: event NPC / icon textures keyed by resolved filesystem path string.
    std::map<std::string, SDL_Texture*> mapEventSpriteTextures_;
    std::map<std::string, MapTilesetRenderMeta> mapTilesetRenderMeta_;
    bool walkabilityGridValid_ = false;
    int mapCamTileX_ = 0;
    int mapCamTileY_ = 0;
    /// FEATURE-MAP-027 / FEATURE-MAP-028: viewport and player footprint (src/overworld_view.json).
    int mapViewTilesW_ = 30;
    int mapViewTilesH_ = 30;
    int mapPlayerTilesW_ = 2;
    int mapPlayerTilesH_ = 2;
    int mapPlayerTileX_ = 0;
    int mapPlayerTileY_ = 0;
    /// IMPROVEMENT-MAP-035: collision sub-rectangle relative to visual anchor top-left.
    /// Defaults to bottom-left 1x1 cell (offX=0, offY=1, W=1, H=1).
    int playerCollisionOffX_ = 0;
    int playerCollisionOffY_ = 1;
    int playerCollisionW_ = 1;
    int playerCollisionH_ = 1;

    /// FEATURE-MAP-031: 4×4 walk sheet + timed walk segments (committed tile updates at segment end).
    SDL_Texture* mapPlayerSpriteSheet_ = nullptr;
    std::string overworldPlayerSpriteRelPath_;
    /// Horizontal draw offset in tile widths (logical anchor unchanged); from `overworld_view.json`.
    int playerDrawOffsetTilesX_ = 1;
    int playerWalkFrameMs_ = 90;
    bool mapPlayerWalkActive_ = false;
    int mapWalkDx_ = 0;
    int mapWalkDy_ = 0;
    int mapWalkTilesInSegment_ = 1;
    int mapWalkFrameCount_ = 2;
    int mapWalkFrameInSegment_ = 0;
    std::array<int, 9> mapWalkCols_{};
    int mapWalkStepParity_ = 0;
    /// BUG-MAP-020: true when the current segment was started by internal auto-chain (not a fresh key-press). Prevents SDL key-repeat from merge-expanding a chained segment to 5 frames.
    bool mapWalkFromChain_ = false;
    /// IMPROVEMENT-MAP-033: queued direction change — picked up by commitCompletedMapWalk_ so the player can turn while mid-walk.
    bool mapWalkQueuedDirValid_ = false;
    int mapWalkQueuedDx_ = 0;
    int mapWalkQueuedDy_ = 0;
    int mapPlayerFacingRow_ = 0;
    std::int64_t mapWalkAccumNs_ = 0;
    std::int64_t mapWalkLastTickNs_ = 0;
    /// IMPROVEMENT-MAP-034: fractional camera offsets for smooth scrolling during walk interpolation.
    double mapCamSubTileOffX_ = 0.0;
    double mapCamSubTileOffY_ = 0.0;

    /// FEATURE-MAP-029: composite world from `src/maps/world_layout.json` (exclusive max bounds).
    std::vector<WorldLayoutMapInstance> worldLayoutInstances_;
    int worldBoundsMinX_ = 0;
    int worldBoundsMinY_ = 0;
    int worldBoundsMaxX_ = 0;
    int worldBoundsMaxY_ = 0;
    /// Overworld (`ViewWorld`) only: per-tile outline; **L** toggles (see `handleMapUiKey_`).
    bool overworldTileGridVisible_ = true;

    /// IMPROVEMENT-PERF-001: cached map-viewer footer strings (see `drawMapView_` / `drawWorldLayoutView_`).
    std::uint32_t mapSingleViewFooterHintRevision_ = 0;
    std::uint32_t mapSingleViewFooterHintBuiltRevision_ = 0;
    std::string mapSingleViewFooterHintScratch_;
    std::uint32_t worldLayoutViewFooterHintRevision_ = 0;
    std::uint32_t worldLayoutViewFooterHintBuiltRevision_ = 0;
    std::string worldLayoutViewFooterHintScratch_;

    void bumpMapSingleViewFooterHintRevision_() { ++mapSingleViewFooterHintRevision_; }
    void bumpWorldLayoutViewFooterHintRevision_() { ++worldLayoutViewFooterHintRevision_; }

    /// FEATURE-MAP-050: battle started from wild tile step; map view frozen underneath.
    bool overworldBattleActive_ = false;
    /// FEATURE-MAP-088: scripted trainer battle from start_trainer_battle opcode.
    bool scriptedTrainerBattleActive_ = false;
    bool mapScriptBattleYielding_ = false;
    bool mapScriptWasBattleLoss_ = false;
    std::string scriptedBattleOutcomeMode_ = "normal";
    /// Opcode-level lossWarp: highest priority in executeBattleLossWarp_ priority chain.
    std::string pendingLossWarpMapId_;
    int pendingLossWarpX_ = 0;
    int pendingLossWarpY_ = 0;
    struct ScriptedBattleMon
    {
        std::string species;
        int level = 5;
    };
    std::vector<std::vector<ScriptedBattleMon>> scriptedBattleTrainers_;
    std::size_t scriptedBattleTrainerIdx_ = 0;
    std::size_t scriptedBattleFoeMonIdx_ = 0;
    std::vector<ScriptedBattleMon> scriptedBattlePlayerParty_;
    std::size_t scriptedBattlePlayerMonIdx_ = 0;
    int scriptedBattlePlayerTurnCount_ = 0;
    int scriptedBattleScriptedLossTurns_ = 0;
    std::string defaultHealMapId_;
    int defaultHealX_ = 0;
    int defaultHealY_ = 0;
    std::string playerSpeciesKey_ = "Squirtle";
    MusicManager musicManager_;
    void startOverworldWildBattle_(const std::string& foeSpeciesKey);
    void startScriptedTrainerBattleFromOpcode_(const nlohmann::json& args);
    void parseScriptedBattleParties_(const nlohmann::json& effective);
    bool startScriptedBattleEncounter_();
    void updateScriptedBattleOhko_();
    bool tryRotateScriptedBattle_(bool playerWon);
    void setBattleBackgroundById_(const std::string& bgId);
    void clearScriptedBattleState_();
    void resolveScriptedTrainerBattleEnd_(bool playerWon);
    void executeBattleLossWarp_();
    void endOverworldBattle_(bool playerWon);
    bool handleOverworldBattleKey_(SDL_Keycode key);
    void tryWildEncounterOnStep_();

    bool handleMapUiKey_(SDL_Keycode key, Uint32 keyRepeat);
    void openMapPicker_();
    void closeMapUi_();
    void drawMapPicker_();
    void drawMapView_();
    void drawWorldLayoutView_();
    bool loadMapCatalog_();
    void finalizeMapCatalogForPicker_();
    bool loadMapForView_(const std::string& mapId);
    bool loadWorldLayoutForView_();
    /// If `mapId` appears in `src/maps/world_layout.json`, load overworld and place player at map-local
    /// (x,y) within that instance; otherwise returns false so caller can `loadMapForView_` (standalone map).
    bool warpPlayerViaWorldLayoutIfPresent_(const std::string& mapId, int localTileX, int localTileY);
    /// BUG-MAP-054: clamp/snap warp destination to in-bounds walkable anchor (optional world-local footprint check).
    void resolveWarpPlayerAnchor_(
        int reqX,
        int reqY,
        int mapW,
        int mapH,
        int& outX,
        int& outY,
        int worldOriginX = 0,
        int worldOriginY = 0,
        bool footprintInWorldSpace = false) const;
    void executePendingMapWarp_();
    void clearWorldLayoutView_();
    void clampMapCamera_();
    void clampWorldCamera_();
    void loadOverworldViewConfig_();
    void spawnPlayerOnLoadedMap_();
    void spawnPlayerOnWorldLayout_(const std::string& originInstanceId);
    void syncCameraToFollowPlayer_();
    void syncCameraToFollowWorldPlayer_();
    bool mapWalkabilityBlocksAt_(int tileX, int tileY) const;
    bool mapPlayerFootprintBlockedAt_(int topLeftX, int topLeftY) const;
    bool worldWalkabilityBlocksAt_(int worldX, int worldY) const;
    bool worldPlayerFootprintBlockedAt_(int topLeftWorldX, int topLeftWorldY) const;
    /// walkChainContinueCol >= 0: continue walk sheet from that column (cols n, (n+1)%4); used after segment commit when auto-chaining. fromKeyRepeat: SDL repeat only (not internal chain) so two-tile merge does not fire on chained segments.
    void requestPlayerMoveOnMap_(
        int deltaX, int deltaY, bool fromKeyRepeat, int walkChainContinueCol = -1, bool scriptDrive = false);
    void tickMapPlayerWalk_();
    void resetMapPlayerWalkState_();
    void mapPlayerWalkVisualOffsetsTiles_(double& outTx, double& outTy) const;
    static int mapWalkSpriteRowForDelta_(int deltaX, int deltaY);
    void reloadMapPlayerSpriteTexture_();
    void drawMapViewPlayerFootprint_(int ox, int oy, int tilePx, const SDL_Rect& panelRect);
    void advanceMapWalkAnimFrame_();
    void commitCompletedMapWalk_();
    bool shouldAutoChainMapWalk_(int deltaX, int deltaY) const;
    /// FEATURE-MAP-030: true if any tile of the player footprint lies on a cardinally adjacent tile
    /// around the event’s fixed 2×2 anchor (8 tiles: not diagonals of the bounding ring).
    static bool mapEventFootprintsTouch_(
        int playerX, int playerY, int playerW, int playerH, int eventAnchorX, int eventAnchorY);
    void tickMapScript_();
    void wireMapScriptCallbacks_();
    void startMapScript_(const std::string& mapJsonPath, const MapEventInstance& ev);
    bool tryStartNearbyMapScript_();
    /// FEATURE-MAP-074: load a reusable library connector document from src/maps/scripts/_library/.
    nlohmann::json loadLibrarySubflow_(const std::string& name) const;
    /// FEATURE-MAP-078: fire a step_on event when the player's footprint lands on its anchor.
    bool tryStepOnMapEvent_();
    /// FEATURE-MAP-078: apply onComplete flag changes + cleared flag when a script finishes.
    void applyMapScriptCompletion_();
    /// FEATURE-MAP-078: true when an event's run-condition currently holds.
    bool mapEventRunConditionOk_(const MapEventInstance& ev) const;
    /// FEATURE-MAP-078: true when an event may still fire (cleared flag not yet set).
    bool mapEventClearedGate_(const MapEventInstance& ev) const;
    /// FEATURE-MAP-078: fire eligible on_map_enter / on_condition events when idle.
    void tryFireAutoMapEvents_();
    bool handleMapScriptKey_(SDL_Keycode key);
    void drawMapScriptOverlay_();
    void drawMapEventSprites_(int ox, int oy, int tilePx, const SDL_Rect& panelRect);
    void drawWorldLayoutEventSprites_(int ox, int oy, int tilePx, const SDL_Rect& panelRect);
    SDL_Texture* getOrLoadMapEventSpriteTexture_(const std::string& pathKey, const std::string& absPathFs);
    std::optional<ScriptRuntime> mapScript_;
    std::string mapLoadedFromPath_;
    /// FEATURE-MAP-072: persistent game-state flags (loaded at startup, flushed on change/exit).
    GameState gameState_;
    /// FEATURE-MAP-078: event currently driving mapScript_ (for onComplete / cleared flag).
    MapEventInstance mapScriptEvent_;
    bool mapScriptHasEvent_ = false;
    /// FEATURE-MAP-048: scripted blocking walk; camera tween; draw zoom for script opcodes.
    /// FEATURE-MAP-071: walk/run now uses direction+steps rail movement (no coordinate targeting).
    bool mapScriptBlockingWalk_ = false;
    bool mapScriptDriveActive_ = false;
    bool mapScriptDriveIsRun_ = false;
    int mapScriptSavedWalkFrameMs_ = 0;
    /// Rail-step state (FEATURE-MAP-071): fixed dx/dy axis + countdown of remaining strides.
    int mapScriptDriveStepsRemaining_ = 0;
    int mapScriptDriveStepDx_ = 0;
    int mapScriptDriveStepDy_ = 0;
    bool mapScriptCameraActive_ = false;
    int mapScriptCameraRemaining_ = 0;
    int mapScriptCameraDx_ = 0;
    int mapScriptCameraDy_ = 0;
    int mapScriptCameraSpeed_ = 0;
    int mapScriptCameraOffsetTilesX_ = 0;
    int mapScriptCameraOffsetTilesY_ = 0;
    double mapViewDrawZoom_ = 1.0;
    void clearMapScriptDriveAndCameraState_();
    void finishMapScriptWalkDrive_();
    /// FEATURE-MAP-071: parse a direction string into cardinal (dx, dy); returns false on invalid input.
    static bool parseScriptDirectionToDelta_(const std::string& dir, int& outDx, int& outDy);
    void applyScriptPlayerFacingHint_(const std::string& dir);
    std::optional<ScriptStepResult> tryMapViewerScriptOpcode_(
        ScriptRuntime& rt, const std::string& op, const nlohmann::json& args);
    struct PendingMapWarp
    {
        bool pending = false;
        std::string mapId;
        int tileX = 0;
        int tileY = 0;
    } pendingMapWarp_;
    void destroyMapViewTextures_();
    void rebuildMapTilesetRenderMeta_();
    SDL_Texture* getOrLoadMapTilesetTexture_(const std::string& tilesetId);
    const TilesetDef* findMapTilesetDef_(const std::string& tilesetId) const;
    void rebuildPokedexIndex_();

    std::map<int, std::string> pokedexNumToSpecies_;
    std::vector<std::string> speciesKeys_;
    std::map<TextCacheKey, TextCacheEntry> textCache_;

public:
    Game();
    ~Game();

    void run();
};

class Pokemon
{
private:
    PokemonStats iv{};
    PokemonStats baseStats{};
    std::vector<Type> types;
    std::vector<MoveTemplate> moves_;
    std::string spriteFrontPath_;
    std::string spriteBackPath_;

    void blankPoke();
    void loadFromSpecies(
        const nlohmann::json& species, const std::string& speciesKey, const std::string& formKey);
    void setTypeValues(const nlohmann::json& typeArray, const std::string& speciesKey);
    void loadMoves(const nlohmann::json& root, const nlohmann::json& species, const std::string& speciesKey);

public:
    Pokemon(json& data, const std::string& speciesKey, const std::string& formKey = "");
    ~Pokemon();

    const PokemonStats& ivs() const;
    const PokemonStats& bases() const;
    const std::vector<Type>& getTypes() const;
    const std::vector<MoveTemplate>& moves() const;

    const std::string& frontSpritePath() const;
    const std::string& backSpritePath() const;
    void setFrontSpritePath(std::string path);
    void setBackSpritePath(std::string path);
};

int random(int min, int max);
std::ostream& operator<<(std::ostream& os, const Pokemon& p);

#endif // GAME_H

#ifndef MAP_DATA_H
#define MAP_DATA_H

#include <json.hpp>
#include <map>
#include <string>
#include <vector>

struct TilesetDef
{
    std::string id;
    std::string imagePath;
    int tileWidth = 16;
    int tileHeight = 16;
    int margin = 0;
    int spacing = 0;
    int columns = 0;
};

struct MapExitInfo
{
    std::string mapId;
    int entryTileX = 0;
    int entryTileY = 0;
};

struct MapCell
{
    bool empty = true;
    std::string tilesetId;
    int tileIndex = 0;
};

/// One named tile plane; `cells` matches map width × height (bottom-to-top draw order in `tileLayers`).
struct TileLayer
{
    std::string id;
    bool applyOverPlayer = true;
    std::vector<std::vector<MapCell>> cells;
};

struct MapEventSpriteRef
{
    std::string kind;
    std::string file;
    /// Row-major index in a sheet grid (e.g. 0–15 for 4×4 character walk sheets).
    int frame = 0;
    int sheetColumns = 1;
    int sheetRows = 1;
    /// Optional facing (up/down/left/right and aliases); for character sheets, selects walk row and keeps ``frame % sheetColumns`` as the animation column (FEATURE-MAP-049).
    std::string facing;
};

/// FEATURE-MAP-050: one weighted species row in a wild encounter tier table.
struct WildEncounterSpeciesEntry
{
    std::string species;
    int weight = 1;
};

/// FEATURE-MAP-050: per-patch encounter table and step chance (tiers: common / uncommon / rare).
struct WildEncounterPatch
{
    std::string id;
    int stepChancePercent = 10;
    std::vector<WildEncounterSpeciesEntry> common;
    std::vector<WildEncounterSpeciesEntry> uncommon;
    std::vector<WildEncounterSpeciesEntry> rare;
};

/// FEATURE-MAP-078: how an event fires.
enum class MapEventTrigger
{
    Interact,    ///< Q + adjacency (default). Sprite blocks its 2x2 footprint (solid NPC).
    StepOn,      ///< auto-fire when the player footprint lands on the anchor; stays walkable.
    OnMapEnter,  ///< fire once when the map loads (if not yet cleared).
    OnCondition  ///< fire when a flag/var condition holds (if not yet cleared).
};

/// FEATURE-MAP-030: 2×2 interactable region; script via inline JSON or path relative to src/maps/.
/// FEATURE-MAP-078: events carry a trigger type, an optional run-condition, an auto-managed cleared
/// flag, and optional flag mutations applied when the script finishes.
struct MapEventInstance
{
    std::string id;
    int anchorX = 0;
    int anchorY = 0;
    nlohmann::json scriptInline{};
    std::string scriptPathRelative;
    MapEventSpriteRef sprite;
    bool hasSprite = false;

    MapEventTrigger trigger = MapEventTrigger::Interact;
    /// Optional run-condition (a flag name that must be set for the event to be eligible).
    std::string conditionFlag;
    /// Whether conditionFlag must be set (true) or clear (false) for the event to be eligible.
    bool conditionWantSet = true;
    /// Auto-managed "cleared" flag (defaults to "<id>_cleared"); gates one-and-done events.
    std::string clearedFlag;
    /// Flags set / cleared when the script completes (FEATURE-MAP-078 onComplete).
    std::vector<std::string> onCompleteSetFlags;
    std::vector<std::string> onCompleteClearFlags;
};

/// FEATURE-MAP-078: true when this event blocks player movement on its footprint (interact NPCs).
inline bool mapEventIsSolid(const MapEventInstance& ev)
{
    return ev.trigger == MapEventTrigger::Interact && ev.hasSprite;
}

struct MapData
{
    int version = 1;
    std::string id;
    std::string name;
    std::string tilesetId;
    int width = 0;
    int height = 0;
    int tileWidth = 16;
    int tileHeight = 16;
    /// Bottom (index 0) to top; from layers.tileLayers, or one layer from legacy ground / groundCells.
    std::vector<TileLayer> tileLayers;
    /// 0 = legal walk, 1 = blocked (optional layer).
    std::vector<std::vector<int>> walkabilityLayer;
    /// 0 = opaque, 1 = draw as transparent (optional layer).
    std::vector<std::vector<int>> transparentLayer;
    /// 0 = draw below player, 1 = draw above player (optional layer).
    std::vector<std::vector<int>> overPlayerLayer;
    std::map<std::string, MapExitInfo> connections;
    std::vector<MapEventInstance> events;
    /// FEATURE-MAP-050: 0 = none; 1..N = index into `wildPatches` (1-based, matches editor JSON).
    std::vector<std::vector<int>> wildEncounterLayer;
    std::vector<WildEncounterPatch> wildPatches;
    /// FEATURE-MAP-058: map-wide species that appear in every local patch (local wins on duplicate).
    std::vector<WildEncounterSpeciesEntry> globalCommon;
    std::vector<WildEncounterSpeciesEntry> globalUncommon;
    std::vector<WildEncounterSpeciesEntry> globalRare;
    /// FEATURE-MAP-087: route music stem (no extension) under src/audio/.
    std::string musicTrack;
    /// FEATURE-MAP-088: optional map heal point for battle loss warp fallback.
    struct HealPoint
    {
        std::string mapId;
        int x = 0;
        int y = 0;
    };
    HealPoint healPoint;
};

bool loadTilesetRegistry(const std::string& path, std::vector<TilesetDef>& out);
bool loadMapFromFile(const std::string& path, MapData& out);
bool loadMapById(const std::string& mapsDirectory, const std::string& mapId, MapData& out);

/// Merge inline script or load JSON from path next to map file.
nlohmann::json loadEventScriptJson(const std::string& mapJsonPath, const MapEventInstance& ev);

#endif

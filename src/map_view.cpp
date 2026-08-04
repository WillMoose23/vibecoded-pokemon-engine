// FEATURE-MAP-008: map catalog (see docs/tracker.md).
// FEATURE-MAP-027: playable viewport, overworld_view.json, player + camera follow.
// FEATURE-MAP-028: multi-tile player footprint + larger default viewport.
// FEATURE-MAP-029: world_layout.json composite in map viewer (key 3).
// FEATURE-MAP-031: player walk animation + 4×4 trainer sprite (see docs/tracker.md).
// IMPROVEMENT-PERF-001: cached map/world viewer footer hint strings (see docs/tracker.md).

#include "game.h"
#include "wild_encounter.h"

#include <SDL_image.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <cctype>
#include <fstream>
#include <iostream>

namespace
{

constexpr const char* kMapsDir = "src/maps";
constexpr const char* kMapsIndex = "src/maps/maps_index.json";
constexpr const char* kTilesetsJson = "src/tilesets.json";
constexpr const char* kWorldLayoutJson = "src/maps/world_layout.json";
constexpr const char* kOverworldCatalogId = "__overworld__";
constexpr const char* kOverworldViewJson = "src/overworld_view.json";
constexpr int kOverworldViewMin = 3;
constexpr int kOverworldViewMax = 64;
constexpr int kDefaultViewTilesW = 30;
constexpr int kDefaultViewTilesH = 30;
constexpr int kDefaultPlayerTilesW = 2;
constexpr int kDefaultPlayerTilesH = 2;
constexpr int kPlayerFootprintMin = 1;
constexpr int kPlayerFootprintMax = 16;
/// FEATURE-MAP-031: one walk "step" moves the player’s top-left anchor by this many tiles (2×2 footprint).
constexpr int kMapWalkAnchorStrideTiles = 2;

int inferColumns(int sheetW, int tw, int margin, int spacing)
{
    if (tw <= 0)
    {
        return 1;
    }
    const int cell = tw + spacing;
    if (cell <= 0)
    {
        return 1;
    }
    const int usable = sheetW - 2 * margin + spacing;
    return std::max(1, usable / cell);
}

/// Shared dimensions check for int grids stored with map height/width (walkability, over-player).
bool intLayerGridDimsMatchMap_(const MapData& m, const std::vector<std::vector<int>>& g)
{
    const int h = m.height;
    const int w = m.width;
    if (h <= 0 || w <= 0)
    {
        return false;
    }
    if (static_cast<int>(g.size()) != h)
    {
        return false;
    }
    for (const auto& row : g)
    {
        if (static_cast<int>(row.size()) != w)
        {
            return false;
        }
    }
    return true;
}

bool walkabilityGridMatchesMap_(const MapData& m)
{
    return intLayerGridDimsMatchMap_(m, m.walkabilityLayer);
}

bool overPlayerGridMatchesMap_(const MapData& m)
{
    return intLayerGridDimsMatchMap_(m, m.overPlayerLayer);
}

/// BUG-MAP-WORLD-008: must match drawWorldLayoutView_ — upper instances with empty cells fall through to
/// lower maps for rendering, but walk used to read walkability from the first bounding-box hit only.
bool mapWorldInstHasRenderableTileAt(const MapData& md, int mx, int my)
{
    if (mx < 0 || my < 0 || mx >= md.width || my >= md.height)
    {
        return false;
    }
    for (const TileLayer& layer : md.tileLayers)
    {
        if (static_cast<int>(layer.cells.size()) <= my)
        {
            continue;
        }
        const auto& row = layer.cells[static_cast<size_t>(my)];
        if (static_cast<int>(row.size()) <= mx)
        {
            continue;
        }
        const MapCell& c = row[static_cast<size_t>(mx)];
        if (!c.empty && c.tileIndex > 0)
        {
            return true;
        }
    }
    return false;
}

int jsonNumberToInt(const json& j, int defaultValue = 0)
{
    if (j.is_number_integer())
    {
        return j.get<int>();
    }
    if (j.is_number_float())
    {
        return static_cast<int>(std::lround(j.get<double>()));
    }
    return defaultValue;
}

std::string mapEventSpriteRelPath_(const MapEventSpriteRef& sp)
{
    if (sp.kind == "pokemon_icon")
    {
        return std::string("src/Graphics/Pokemon/Icons/") + sp.file;
    }
    if (sp.kind == "pokemon_icon_shiny")
    {
        return std::string("src/Graphics/Pokemon/Icons shiny/") + sp.file;
    }
    return std::string("src/Graphics/Characters/") + sp.file;
}

} // namespace

void Game::loadOverworldViewConfig_()
{
    mapViewTilesW_ = kDefaultViewTilesW;
    mapViewTilesH_ = kDefaultViewTilesH;
    mapPlayerTilesW_ = kDefaultPlayerTilesW;
    mapPlayerTilesH_ = kDefaultPlayerTilesH;
    overworldPlayerSpriteRelPath_.clear();
    playerWalkFrameMs_ = 90;
    playerDrawOffsetTilesX_ = 1;

    json root;
    std::ifstream f(kOverworldViewJson);
    if (!f)
    {
        reloadMapPlayerSpriteTexture_();
        bumpMapSingleViewFooterHintRevision_();
        bumpWorldLayoutViewFooterHintRevision_();
        return;
    }
    try
    {
        f >> root;
    }
    catch (const std::exception& e)
    {
        std::cerr << "overworld_view.json: " << e.what() << '\n';
        reloadMapPlayerSpriteTexture_();
        bumpMapSingleViewFooterHintRevision_();
        bumpWorldLayoutViewFooterHintRevision_();
        return;
    }
    if (root.contains("viewTilesW") && root["viewTilesW"].is_number_integer())
    {
        mapViewTilesW_ = root["viewTilesW"].get<int>();
    }
    if (root.contains("viewTilesH") && root["viewTilesH"].is_number_integer())
    {
        mapViewTilesH_ = root["viewTilesH"].get<int>();
    }
    if (root.contains("playerTilesW") && root["playerTilesW"].is_number_integer())
    {
        mapPlayerTilesW_ = root["playerTilesW"].get<int>();
    }
    if (root.contains("playerTilesH") && root["playerTilesH"].is_number_integer())
    {
        mapPlayerTilesH_ = root["playerTilesH"].get<int>();
    }
    mapViewTilesW_ = std::clamp(mapViewTilesW_, kOverworldViewMin, kOverworldViewMax);
    mapViewTilesH_ = std::clamp(mapViewTilesH_, kOverworldViewMin, kOverworldViewMax);
    mapPlayerTilesW_ = std::clamp(mapPlayerTilesW_, kPlayerFootprintMin, kPlayerFootprintMax);
    mapPlayerTilesH_ = std::clamp(mapPlayerTilesH_, kPlayerFootprintMin, kPlayerFootprintMax);

    if (root.contains("playerSpeciesKey") && root["playerSpeciesKey"].is_string())
    {
        playerSpeciesKey_ = root["playerSpeciesKey"].get<std::string>();
    }
    if (root.contains("playerSprite") && root["playerSprite"].is_string())
    {
        overworldPlayerSpriteRelPath_ = root["playerSprite"].get<std::string>();
    }
    playerWalkFrameMs_ = jsonNumberToInt(root["playerWalkFrameMs"], 90);
    playerWalkFrameMs_ = std::clamp(playerWalkFrameMs_, 16, 500);
    playerDrawOffsetTilesX_ = jsonNumberToInt(root["playerDrawOffsetTilesX"], 1);
    playerDrawOffsetTilesX_ = std::clamp(playerDrawOffsetTilesX_, -8, 8);

    // IMPROVEMENT-MAP-035: load collision sub-rectangle (relative to visual anchor top-left).
    playerCollisionOffX_ = jsonNumberToInt(root["playerCollisionOffX"], 0);
    playerCollisionOffY_ = jsonNumberToInt(root["playerCollisionOffY"], 1);
    playerCollisionW_ = jsonNumberToInt(root["playerCollisionW"], 1);
    playerCollisionH_ = jsonNumberToInt(root["playerCollisionH"], 1);
    // Clamp so the collision rect stays within the visual footprint.
    playerCollisionOffX_ = std::clamp(playerCollisionOffX_, 0, std::max(0, mapPlayerTilesW_ - 1));
    playerCollisionOffY_ = std::clamp(playerCollisionOffY_, 0, std::max(0, mapPlayerTilesH_ - 1));
    playerCollisionW_ = std::clamp(playerCollisionW_, 1, std::max(1, mapPlayerTilesW_ - playerCollisionOffX_));
    playerCollisionH_ = std::clamp(playerCollisionH_, 1, std::max(1, mapPlayerTilesH_ - playerCollisionOffY_));

    if (root.contains("defaultHealPoint") && root["defaultHealPoint"].is_object())
    {
        const auto& hp = root["defaultHealPoint"];
        defaultHealMapId_ = hp.value("mapId", std::string());
        defaultHealX_ = jsonNumberToInt(hp["x"], 0);
        defaultHealY_ = jsonNumberToInt(hp["y"], 0);
    }

    reloadMapPlayerSpriteTexture_();
    bumpMapSingleViewFooterHintRevision_();
    bumpWorldLayoutViewFooterHintRevision_();
}

void Game::reloadMapPlayerSpriteTexture_()
{
    if (mapPlayerSpriteSheet_ != nullptr)
    {
        SDL_DestroyTexture(mapPlayerSpriteSheet_);
        mapPlayerSpriteSheet_ = nullptr;
    }
    if (overworldPlayerSpriteRelPath_.empty() || renderer == nullptr)
    {
        return;
    }
    SDL_Surface* surf = IMG_Load(overworldPlayerSpriteRelPath_.c_str());
    if (surf == nullptr)
    {
        std::cerr << "FEATURE-MAP-031: player sprite IMG_Load(\"" << overworldPlayerSpriteRelPath_
                  << "\"): " << IMG_GetError() << '\n';
        return;
    }
    SDL_SetColorKey(surf, SDL_TRUE, SDL_MapRGB(surf->format, 255, 255, 255));
    mapPlayerSpriteSheet_ = SDL_CreateTextureFromSurface(renderer, surf);
    SDL_FreeSurface(surf);
    if (mapPlayerSpriteSheet_ == nullptr)
    {
        std::cerr << "FEATURE-MAP-031: SDL_CreateTextureFromSurface(player sprite): " << SDL_GetError() << '\n';
        return;
    }
    SDL_SetTextureBlendMode(mapPlayerSpriteSheet_, SDL_BLENDMODE_BLEND);
}

void Game::resetMapPlayerWalkState_()
{
    mapPlayerWalkActive_ = false;
    mapWalkFrameInSegment_ = 0;
    mapWalkAccumNs_ = 0;
    mapWalkLastTickNs_ = 0;
    mapWalkFromChain_ = false;
    mapWalkQueuedDirValid_ = false;
}

void Game::mapPlayerWalkVisualOffsetsTiles_(double& outTx, double& outTy) const
{
    outTx = 0.0;
    outTy = 0.0;
    if (!mapPlayerWalkActive_)
    {
        return;
    }
    const int fc = std::max(1, mapWalkFrameCount_);
    const double span =
        static_cast<double>(std::max(1, mapWalkTilesInSegment_)) * static_cast<double>(kMapWalkAnchorStrideTiles);
    const std::int64_t thresholdNs = static_cast<std::int64_t>(playerWalkFrameMs_) * 1000000LL;
    double u = 1.0;
    if (fc <= 1 || thresholdNs <= 0)
    {
        u = 1.0;
    }
    else
    {
        // BUG-MAP-021: blend using elapsed time within the segment, not only discrete frame index.
        // For fc==2, frame-only u was 0 then 1 (full two-tile jump). Spread motion across fc frame periods.
        const double elapsedNs =
            static_cast<double>(mapWalkFrameInSegment_) * static_cast<double>(thresholdNs) +
            static_cast<double>(mapWalkAccumNs_);
        const double totalNs = static_cast<double>(fc) * static_cast<double>(thresholdNs);
        u = std::clamp(elapsedNs / totalNs, 0.0, 1.0);
    }
    outTx = static_cast<double>(mapWalkDx_) * span * u;
    outTy = static_cast<double>(mapWalkDy_) * span * u;
}

int Game::mapWalkSpriteRowForDelta_(int deltaX, int deltaY)
{
    if (deltaY > 0)
    {
        return 0;
    }
    if (deltaX < 0)
    {
        return 1;
    }
    if (deltaX > 0)
    {
        return 2;
    }
    if (deltaY < 0)
    {
        return 3;
    }
    return 0;
}

void Game::clearWorldLayoutView_()
{
    worldLayoutInstances_.clear();
    worldBoundsMinX_ = 0;
    worldBoundsMinY_ = 0;
    worldBoundsMaxX_ = 0;
    worldBoundsMaxY_ = 0;
}

bool Game::worldWalkabilityBlocksAt_(int worldX, int worldY) const
{
    for (auto it = worldLayoutInstances_.rbegin(); it != worldLayoutInstances_.rend(); ++it)
    {
        const WorldLayoutMapInstance& inst = *it;
        if (worldX < inst.worldOriginX || worldY < inst.worldOriginY)
        {
            continue;
        }
        if (worldX >= inst.worldOriginX + inst.widthTiles || worldY >= inst.worldOriginY + inst.heightTiles)
        {
            continue;
        }
        const int lx = worldX - inst.worldOriginX;
        const int ly = worldY - inst.worldOriginY;
        if (!mapWorldInstHasRenderableTileAt(inst.map, lx, ly))
        {
            continue;
        }
        if (!inst.walkabilityGridValid)
        {
            return false;
        }
        // BUG-MAP-WORLD-009: the trainer sprite is drawn playerDrawOffsetTilesX_ tiles to the RIGHT of the
        // logical anchor (overworld_view.json). Map editors paint walk blocks next to the VISUAL sprite, so
        // the correct walk column is lx + playerDrawOffsetTilesX_, not lx - playerDrawOffsetTilesX_.
        const int mw = std::max(1, inst.map.width);
        const int walkLx = std::clamp(lx + playerDrawOffsetTilesX_, 0, mw - 1);
        const bool blocked = inst.map.walkabilityLayer[static_cast<size_t>(ly)][static_cast<size_t>(walkLx)] != 0;
        return blocked;
    }
    return true;
}

bool Game::worldPlayerFootprintBlockedAt_(int topLeftWorldX, int topLeftWorldY) const
{
    // IMPROVEMENT-MAP-035: only check the collision sub-rectangle, not the full visual footprint.
    for (int dy = 0; dy < playerCollisionH_; ++dy)
    {
        for (int dx = 0; dx < playerCollisionW_; ++dx)
        {
            if (worldWalkabilityBlocksAt_(topLeftWorldX + playerCollisionOffX_ + dx,
                                          topLeftWorldY + playerCollisionOffY_ + dy))
            {
                return true;
            }
        }
    }
    return false;
}

void Game::clampWorldCamera_()
{
    const int vw = std::max(1, mapViewTilesW_);
    const int vh = std::max(1, mapViewTilesH_);
    const int spanW = std::max(0, worldBoundsMaxX_ - worldBoundsMinX_);
    const int spanH = std::max(0, worldBoundsMaxY_ - worldBoundsMinY_);
    const int maxCamX = worldBoundsMinX_ + std::max(0, spanW - vw);
    const int maxCamY = worldBoundsMinY_ + std::max(0, spanH - vh);
    mapCamTileX_ = std::clamp(mapCamTileX_, worldBoundsMinX_, maxCamX);
    mapCamTileY_ = std::clamp(mapCamTileY_, worldBoundsMinY_, maxCamY);
}

void Game::syncCameraToFollowWorldPlayer_()
{
    const int vw = std::max(1, mapViewTilesW_);
    const int vh = std::max(1, mapViewTilesH_);
    const int pw = std::max(1, mapPlayerTilesW_);
    const int ph = std::max(1, mapPlayerTilesH_);
    const int spanW = std::max(0, worldBoundsMaxX_ - worldBoundsMinX_);
    const int spanH = std::max(0, worldBoundsMaxY_ - worldBoundsMinY_);
    double vtx = 0.0;
    double vty = 0.0;
    mapPlayerWalkVisualOffsetsTiles_(vtx, vty);
    const double centerX = static_cast<double>(mapPlayerTileX_) + static_cast<double>(pw) / 2.0 + vtx;
    const double centerY = static_cast<double>(mapPlayerTileY_) + static_cast<double>(ph) / 2.0 + vty;
    const double maxCamX = static_cast<double>(worldBoundsMinX_) + static_cast<double>(std::max(0, spanW - vw));
    const double maxCamY = static_cast<double>(worldBoundsMinY_) + static_cast<double>(std::max(0, spanH - vh));
    const double scriptOffX = static_cast<double>(mapScriptCameraOffsetTilesX_);
    const double scriptOffY = static_cast<double>(mapScriptCameraOffsetTilesY_);
    const double camX = std::clamp(
        centerX - static_cast<double>(vw) / 2.0 + scriptOffX, static_cast<double>(worldBoundsMinX_), maxCamX);
    const double camY = std::clamp(
        centerY - static_cast<double>(vh) / 2.0 + scriptOffY, static_cast<double>(worldBoundsMinY_), maxCamY);
    mapCamTileX_ = static_cast<int>(std::floor(camX));
    mapCamTileY_ = static_cast<int>(std::floor(camY));
    mapCamSubTileOffX_ = camX - static_cast<double>(mapCamTileX_);
    mapCamSubTileOffY_ = camY - static_cast<double>(mapCamTileY_);
}

void Game::spawnPlayerOnWorldLayout_(const std::string& originInstanceId)
{
    loadOverworldViewConfig_();
    const int pw = std::max(1, mapPlayerTilesW_);
    const int ph = std::max(1, mapPlayerTilesH_);

    const WorldLayoutMapInstance* originInst = nullptr;
    for (const WorldLayoutMapInstance& inst : worldLayoutInstances_)
    {
        if (!originInstanceId.empty() && inst.instanceId == originInstanceId)
        {
            originInst = &inst;
            break;
        }
    }
    if (originInst == nullptr && !worldLayoutInstances_.empty())
    {
        originInst = &worldLayoutInstances_.front();
    }
    if (originInst != nullptr)
    {
        const int mw = std::max(1, originInst->map.width);
        const int mh = std::max(1, originInst->map.height);
        const int px = originInst->worldOriginX + mw / 2 - pw / 2;
        const int py = originInst->worldOriginY + mh / 2 - ph / 2;
        if (!worldPlayerFootprintBlockedAt_(px, py))
        {
            mapPlayerTileX_ = px;
            mapPlayerTileY_ = py;
            resetMapPlayerWalkState_();
            mapPlayerFacingRow_ = 0;
            mapWalkStepParity_ = 0;
            syncCameraToFollowWorldPlayer_();
            return;
        }
    }

    for (int y = worldBoundsMinY_; y <= worldBoundsMaxY_ - ph; ++y)
    {
        for (int x = worldBoundsMinX_; x <= worldBoundsMaxX_ - pw; ++x)
        {
            if (!worldPlayerFootprintBlockedAt_(x, y))
            {
                mapPlayerTileX_ = x;
                mapPlayerTileY_ = y;
                resetMapPlayerWalkState_();
                mapPlayerFacingRow_ = 0;
                mapWalkStepParity_ = 0;
                syncCameraToFollowWorldPlayer_();
                return;
            }
        }
    }
    mapPlayerTileX_ = worldBoundsMinX_;
    mapPlayerTileY_ = worldBoundsMinY_;
    resetMapPlayerWalkState_();
    mapPlayerFacingRow_ = 0;
    mapWalkStepParity_ = 0;
    syncCameraToFollowWorldPlayer_();
}

bool Game::loadWorldLayoutForView_()
{
    clearMapScriptDriveAndCameraState_();
    mapScript_.reset();
    mapLoadedFromPath_.clear();
    pendingMapWarp_.pending = false;
    mapPickerLastError_.clear();
    clearWorldLayoutView_();
    destroyMapViewTextures_();
    viewMapData_ = {};
    mapTilesetDefs_.clear();
    walkabilityGridValid_ = false;
    loadOverworldViewConfig_();

    json root;
    {
        std::ifstream f(kWorldLayoutJson);
        if (!f)
        {
            mapPickerLastError_ = "Missing src/maps/world_layout.json (export from map editor with F9).";
            std::cerr << "FEATURE-MAP-029: " << mapPickerLastError_ << '\n';
            return false;
        }
        try
        {
            f >> root;
        }
        catch (const std::exception& e)
        {
            mapPickerLastError_ = std::string("Invalid world_layout.json: ") + e.what();
            std::cerr << "FEATURE-MAP-029: " << mapPickerLastError_ << '\n';
            return false;
        }
    }

    if (!root.contains("version") || !root["version"].is_number_integer() || root["version"].get<int>() != 1)
    {
        mapPickerLastError_ = "world_layout.json: unsupported or missing version (expected 1).";
        std::cerr << "FEATURE-MAP-029: " << mapPickerLastError_ << '\n';
        return false;
    }
    if (!root.contains("nodes") || !root["nodes"].is_array() || root["nodes"].empty())
    {
        mapPickerLastError_ = "world_layout.json: missing or empty nodes array.";
        std::cerr << "FEATURE-MAP-029: " << mapPickerLastError_ << '\n';
        return false;
    }

    std::map<std::string, json> nodeByInstanceId;
    for (const auto& node : root["nodes"])
    {
        if (!node.is_object())
        {
            continue;
        }
        std::string iid = node.value("instanceId", "");
        if (iid.empty())
        {
            continue;
        }
        nodeByInstanceId[iid] = node;
    }
    if (nodeByInstanceId.empty())
    {
        mapPickerLastError_ = "world_layout.json: no nodes with instanceId.";
        std::cerr << "FEATURE-MAP-029: " << mapPickerLastError_ << '\n';
        return false;
    }

    std::vector<std::string> renderOrder;
    if (root.contains("renderOrder") && root["renderOrder"].is_array())
    {
        for (const auto& el : root["renderOrder"])
        {
            if (el.is_string())
            {
                renderOrder.push_back(el.get<std::string>());
            }
        }
    }
    if (renderOrder.empty())
    {
        for (const auto& node : root["nodes"])
        {
            if (!node.is_object())
            {
                continue;
            }
            std::string iid = node.value("instanceId", "");
            if (!iid.empty())
            {
                renderOrder.push_back(iid);
            }
        }
    }

    if (!loadTilesetRegistry(kTilesetsJson, mapTilesetDefs_))
    {
        mapPickerLastError_ = "Failed to load tileset registry for world view.";
        std::cerr << "FEATURE-MAP-029: " << mapPickerLastError_ << '\n';
        return false;
    }

    worldLayoutInstances_.clear();
    worldLayoutInstances_.reserve(renderOrder.size());

    for (const std::string& iid : renderOrder)
    {
        const auto itNode = nodeByInstanceId.find(iid);
        if (itNode == nodeByInstanceId.end())
        {
            std::cerr << "FEATURE-MAP-029: renderOrder references unknown instanceId " << iid << '\n';
            mapPickerLastError_ = "world_layout.json: renderOrder references unknown instanceId.";
            worldLayoutInstances_.clear();
            return false;
        }
        const json& node = itNode->second;
        const std::string mapId = node.value("mapId", "");
        if (mapId.empty())
        {
            mapPickerLastError_ = "world_layout.json: node missing mapId.";
            worldLayoutInstances_.clear();
            return false;
        }
        const std::string path = std::string(kMapsDir) + "/" + mapId + ".json";
        WorldLayoutMapInstance inst;
        inst.instanceId = iid;
        inst.mapId = mapId;
        if (!loadMapFromFile(path, inst.map))
        {
            mapPickerLastError_ = "Failed to load map file for mapId \"" + mapId + "\".";
            std::cerr << "FEATURE-MAP-029: " << mapPickerLastError_ << " path=" << path << '\n';
            worldLayoutInstances_.clear();
            return false;
        }
        inst.worldOriginX = jsonNumberToInt(node["worldX"], 0);
        inst.worldOriginY = jsonNumberToInt(node["worldY"], 0);
        int wFromJson = jsonNumberToInt(node["widthPx"], inst.map.width);
        int hFromJson = jsonNumberToInt(node["heightPx"], inst.map.height);
        inst.widthTiles = std::max(1, std::min(wFromJson, inst.map.width));
        inst.heightTiles = std::max(1, std::min(hFromJson, inst.map.height));
        inst.walkabilityGridValid = walkabilityGridMatchesMap_(inst.map);
        inst.overPlayerGridValid = overPlayerGridMatchesMap_(inst.map);
        worldLayoutInstances_.push_back(std::move(inst));
    }

    bool boundsFromJson = false;
    if (root.contains("compositeBounds") && root["compositeBounds"].is_object())
    {
        const json& cb = root["compositeBounds"];
        worldBoundsMinX_ = static_cast<int>(std::floor(cb.value("minWorldX", 0.0)));
        worldBoundsMinY_ = static_cast<int>(std::floor(cb.value("minWorldY", 0.0)));
        worldBoundsMaxX_ = static_cast<int>(std::ceil(cb.value("maxWorldX", 0.0)));
        worldBoundsMaxY_ = static_cast<int>(std::ceil(cb.value("maxWorldY", 0.0)));
        boundsFromJson = (worldBoundsMaxX_ > worldBoundsMinX_ && worldBoundsMaxY_ > worldBoundsMinY_);
    }
    if (!boundsFromJson && !worldLayoutInstances_.empty())
    {
        const WorldLayoutMapInstance& first = worldLayoutInstances_.front();
        worldBoundsMinX_ = first.worldOriginX;
        worldBoundsMinY_ = first.worldOriginY;
        worldBoundsMaxX_ = first.worldOriginX + first.widthTiles;
        worldBoundsMaxY_ = first.worldOriginY + first.heightTiles;
        for (const WorldLayoutMapInstance& inst : worldLayoutInstances_)
        {
            worldBoundsMinX_ = std::min(worldBoundsMinX_, inst.worldOriginX);
            worldBoundsMinY_ = std::min(worldBoundsMinY_, inst.worldOriginY);
            worldBoundsMaxX_ = std::max(worldBoundsMaxX_, inst.worldOriginX + inst.widthTiles);
            worldBoundsMaxY_ = std::max(worldBoundsMaxY_, inst.worldOriginY + inst.heightTiles);
        }
    }

    rebuildMapTilesetRenderMeta_();

    viewMapData_.name = "Overworld";
    viewMapData_.width = std::max(1, worldBoundsMaxX_ - worldBoundsMinX_);
    viewMapData_.height = std::max(1, worldBoundsMaxY_ - worldBoundsMinY_);

    std::string originInstanceId = root.value("originInstanceId", "");
    mapUiMode_ = MapUiMode::ViewWorld;
    overworldTileGridVisible_ = true;
    spawnPlayerOnWorldLayout_(originInstanceId);
    clampWorldCamera_();
    bumpWorldLayoutViewFooterHintRevision_();
    return true;
}

bool Game::warpPlayerViaWorldLayoutIfPresent_(const std::string& mapId, int localTileX, int localTileY)
{
    if (mapId.empty())
    {
        return false;
    }
    json scan;
    {
        std::ifstream f(kWorldLayoutJson);
        if (!f)
        {
            return false;
        }
        try
        {
            f >> scan;
        }
        catch (const std::exception&)
        {
            return false;
        }
    }
    bool inWorld = false;
    if (scan.contains("nodes") && scan["nodes"].is_array())
    {
        for (const auto& node : scan["nodes"])
        {
            if (!node.is_object())
            {
                continue;
            }
            if (node.value("mapId", std::string()) == mapId)
            {
                inWorld = true;
                break;
            }
        }
    }
    if (!inWorld)
    {
        return false;
    }
    if (!loadWorldLayoutForView_())
    {
        return false;
    }

    const int pw = std::max(1, mapPlayerTilesW_);
    const int ph = std::max(1, mapPlayerTilesH_);
    const WorldLayoutMapInstance* pick = nullptr;
    const WorldLayoutMapInstance* fallback = nullptr;
    for (const WorldLayoutMapInstance& inst : worldLayoutInstances_)
    {
        if (inst.mapId != mapId)
        {
            continue;
        }
        fallback = &inst;
        if (localTileX >= 0 && localTileY >= 0 && localTileX + pw <= inst.map.width && localTileY + ph <= inst.map.height)
        {
            pick = &inst;
            break;
        }
    }
    if (pick == nullptr)
    {
        pick = fallback;
    }
    if (pick == nullptr)
    {
        return false;
    }

    int lx = localTileX;
    int ly = localTileY;
    resolveWarpPlayerAnchor_(
        localTileX,
        localTileY,
        pick->map.width,
        pick->map.height,
        lx,
        ly,
        pick->worldOriginX,
        pick->worldOriginY,
        true);
    int wx = pick->worldOriginX + lx;
    int wy = pick->worldOriginY + ly;
    wx = std::clamp(wx, worldBoundsMinX_, std::max(worldBoundsMinX_, worldBoundsMaxX_ - pw));
    wy = std::clamp(wy, worldBoundsMinY_, std::max(worldBoundsMinY_, worldBoundsMaxY_ - ph));
    mapPlayerTileX_ = wx;
    mapPlayerTileY_ = wy;
    resetMapPlayerWalkState_();
    mapPlayerFacingRow_ = 0;
    mapWalkStepParity_ = 0;
    syncCameraToFollowWorldPlayer_();
    clampWorldCamera_();
    return true;
}


void Game::resolveWarpPlayerAnchor_(
    int reqX,
    int reqY,
    int mapW,
    int mapH,
    int& outX,
    int& outY,
    int worldOriginX,
    int worldOriginY,
    bool footprintInWorldSpace) const
{
    const int pw = std::max(1, mapPlayerTilesW_);
    const int ph = std::max(1, mapPlayerTilesH_);
    const int mw = std::max(1, mapW);
    const int mh = std::max(1, mapH);
    auto blockedAt = [&](int ax, int ay) -> bool {
        if (footprintInWorldSpace)
        {
            return worldPlayerFootprintBlockedAt_(worldOriginX + ax, worldOriginY + ay);
        }
        return mapPlayerFootprintBlockedAt_(ax, ay);
    };
    const int cx = std::clamp(reqX, 0, std::max(0, mw - pw));
    const int cy = std::clamp(reqY, 0, std::max(0, mh - ph));
    if (!blockedAt(cx, cy))
    {
        outX = cx;
        outY = cy;
        return;
    }
    const int maxDist = mw + mh;
    for (int dist = 1; dist <= maxDist; ++dist)
    {
        for (int dy = -dist; dy <= dist; ++dy)
        {
            for (int dx = -dist; dx <= dist; ++dx)
            {
                if (std::abs(dx) + std::abs(dy) != dist)
                {
                    continue;
                }
                const int ax = cx + dx;
                const int ay = cy + dy;
                if (ax < 0 || ay < 0 || ax > mw - pw || ay > mh - ph)
                {
                    continue;
                }
                if (!blockedAt(ax, ay))
                {
                    outX = ax;
                    outY = ay;
                    return;
                }
            }
        }
    }
    outX = cx;
    outY = cy;
}

void Game::executePendingMapWarp_()
{
    if (!pendingMapWarp_.pending)
    {
        return;
    }
    const PendingMapWarp w = pendingMapWarp_;
    pendingMapWarp_.pending = false;
    // FEATURE-MAP-072: persist flag state on map transitions so progress is durable across warps.
    gameState_.flush(false);
    if (warpPlayerViaWorldLayoutIfPresent_(w.mapId, w.tileX, w.tileY))
    {
        return;
    }
    if (!loadMapForView_(w.mapId))
    {
        std::cerr << "map script: warp failed for " << w.mapId << '\n';
        return;
    }
    int ax = w.tileX;
    int ay = w.tileY;
    resolveWarpPlayerAnchor_(w.tileX, w.tileY, viewMapData_.width, viewMapData_.height, ax, ay);
    mapPlayerTileX_ = ax;
    mapPlayerTileY_ = ay;
    resetMapPlayerWalkState_();
    mapPlayerFacingRow_ = 0;
    mapWalkStepParity_ = 0;
    syncCameraToFollowPlayer_();
    clampMapCamera_();
}

bool Game::mapWalkabilityBlocksAt_(int tileX, int tileY) const
{
    if (mapUiMode_ == MapUiMode::ViewWorld)
    {
        return worldWalkabilityBlocksAt_(tileX, tileY);
    }
    const int mw = viewMapData_.width;
    const int mh = viewMapData_.height;
    if (tileX < 0 || tileY < 0 || tileX >= mw || tileY >= mh)
    {
        return true;
    }
    if (!walkabilityGridValid_)
    {
        return false;
    }
    return viewMapData_.walkabilityLayer[static_cast<size_t>(tileY)][static_cast<size_t>(tileX)] != 0;
}

bool Game::mapPlayerFootprintBlockedAt_(int topLeftX, int topLeftY) const
{
    if (mapUiMode_ == MapUiMode::ViewWorld)
    {
        return worldPlayerFootprintBlockedAt_(topLeftX, topLeftY);
    }
    // IMPROVEMENT-MAP-035: only check the collision sub-rectangle, not the full visual footprint.
    for (int dy = 0; dy < playerCollisionH_; ++dy)
    {
        for (int dx = 0; dx < playerCollisionW_; ++dx)
        {
            if (mapWalkabilityBlocksAt_(topLeftX + playerCollisionOffX_ + dx,
                                        topLeftY + playerCollisionOffY_ + dy))
            {
                return true;
            }
        }
    }
    // FEATURE-MAP-078: interact (talk) NPCs are solid; block their 2x2 footprint so the player bumps.
    const int cx0 = topLeftX + playerCollisionOffX_;
    const int cy0 = topLeftY + playerCollisionOffY_;
    const int cx1 = cx0 + playerCollisionW_;
    const int cy1 = cy0 + playerCollisionH_;
    for (const MapEventInstance& ev : viewMapData_.events)
    {
        if (!mapEventIsSolid(ev))
        {
            continue;
        }
        if (cx0 < ev.anchorX + 2 && ev.anchorX < cx1 && cy0 < ev.anchorY + 2 && ev.anchorY < cy1)
        {
            return true;
        }
    }
    return false;
}

void Game::spawnPlayerOnLoadedMap_()
{
    const int mw = std::max(1, viewMapData_.width);
    const int mh = std::max(1, viewMapData_.height);
    const int pw = std::max(1, mapPlayerTilesW_);
    const int ph = std::max(1, mapPlayerTilesH_);

    for (int y = 0; y <= mh - ph; ++y)
    {
        for (int x = 0; x <= mw - pw; ++x)
        {
            if (!mapPlayerFootprintBlockedAt_(x, y))
            {
                mapPlayerTileX_ = x;
                mapPlayerTileY_ = y;
                resetMapPlayerWalkState_();
                mapPlayerFacingRow_ = 0;
                mapWalkStepParity_ = 0;
                return;
            }
        }
    }
    mapPlayerTileX_ = 0;
    mapPlayerTileY_ = 0;
    resetMapPlayerWalkState_();
    mapPlayerFacingRow_ = 0;
    mapWalkStepParity_ = 0;
}

void Game::syncCameraToFollowPlayer_()
{
    if (mapUiMode_ == MapUiMode::ViewWorld)
    {
        syncCameraToFollowWorldPlayer_();
        return;
    }
    const int mw = std::max(1, viewMapData_.width);
    const int mh = std::max(1, viewMapData_.height);
    const int vw = std::max(1, mapViewTilesW_);
    const int vh = std::max(1, mapViewTilesH_);
    const int pw = std::max(1, mapPlayerTilesW_);
    const int ph = std::max(1, mapPlayerTilesH_);
    double vtx = 0.0;
    double vty = 0.0;
    mapPlayerWalkVisualOffsetsTiles_(vtx, vty);
    const double centerX = static_cast<double>(mapPlayerTileX_) + static_cast<double>(pw) / 2.0 + vtx;
    const double centerY = static_cast<double>(mapPlayerTileY_) + static_cast<double>(ph) / 2.0 + vty;
    const double maxCamX = static_cast<double>(std::max(0, mw - vw));
    const double maxCamY = static_cast<double>(std::max(0, mh - vh));
    const double scriptOffX = static_cast<double>(mapScriptCameraOffsetTilesX_);
    const double scriptOffY = static_cast<double>(mapScriptCameraOffsetTilesY_);
    const double camX =
        std::clamp(centerX - static_cast<double>(vw) / 2.0 + scriptOffX, 0.0, maxCamX);
    const double camY =
        std::clamp(centerY - static_cast<double>(vh) / 2.0 + scriptOffY, 0.0, maxCamY);
    mapCamTileX_ = static_cast<int>(std::floor(camX));
    mapCamTileY_ = static_cast<int>(std::floor(camY));
    mapCamSubTileOffX_ = camX - static_cast<double>(mapCamTileX_);
    mapCamSubTileOffY_ = camY - static_cast<double>(mapCamTileY_);
}

void Game::requestPlayerMoveOnMap_(
    int deltaX, int deltaY, bool fromKeyRepeat, int walkChainContinueCol, bool scriptDrive)
{
    if (!scriptDrive)
    {
        if (mapScriptBlockingWalk_)
        {
            return;
        }
        if (mapScript_ && mapScript_->playerLocked)
        {
            return;
        }
    }
    if (deltaX == 0 && deltaY == 0)
    {
        return;
    }
    if (mapUiMode_ != MapUiMode::ViewMap && mapUiMode_ != MapUiMode::ViewWorld)
    {
        return;
    }

    if (mapPlayerWalkActive_)
    {
        if (deltaX == mapWalkDx_ && deltaY == mapWalkDy_)
        {
            if (fromKeyRepeat && !mapWalkFromChain_ && mapWalkTilesInSegment_ == 1 && mapWalkFrameInSegment_ == 0 && mapWalkFrameCount_ == 2)
            {
                const int midX = mapPlayerTileX_ + deltaX * kMapWalkAnchorStrideTiles;
                const int midY = mapPlayerTileY_ + deltaY * kMapWalkAnchorStrideTiles;
                const int tx = mapPlayerTileX_ + deltaX * kMapWalkAnchorStrideTiles * 2;
                const int ty = mapPlayerTileY_ + deltaY * kMapWalkAnchorStrideTiles * 2;
                if (!mapPlayerFootprintBlockedAt_(midX, midY) && !mapPlayerFootprintBlockedAt_(tx, ty))
                {
                    mapWalkTilesInSegment_ = 2;
                    mapWalkFrameCount_ = 5;
                    mapWalkCols_ = {0, 1, 2, 3, 0};
                    mapWalkAccumNs_ = 0;
                    mapWalkLastTickNs_ = 0;
                }
            }
        }
        else
        {
            mapWalkQueuedDirValid_ = true;
            mapWalkQueuedDx_ = deltaX;
            mapWalkQueuedDy_ = deltaY;
        }
        return;
    }

    const int nx = mapPlayerTileX_ + deltaX * kMapWalkAnchorStrideTiles;
    const int ny = mapPlayerTileY_ + deltaY * kMapWalkAnchorStrideTiles;
    if (mapPlayerFootprintBlockedAt_(nx, ny))
    {
        return;
    }

    mapWalkQueuedDirValid_ = false;
    mapWalkDx_ = deltaX;
    mapWalkDy_ = deltaY;
    mapPlayerFacingRow_ = mapWalkSpriteRowForDelta_(deltaX, deltaY);
    mapWalkTilesInSegment_ = 1;
    mapWalkFrameCount_ = 2;
    mapWalkFrameInSegment_ = 0;
    if (walkChainContinueCol >= 0)
    {
        const int s = std::clamp(walkChainContinueCol, 0, 3);
        mapWalkCols_[0] = s;
        mapWalkCols_[1] = (s + 1) % 4;
    }
    else if ((mapWalkStepParity_ & 1) == 0)
    {
        mapWalkCols_[0] = 0;
        mapWalkCols_[1] = 1;
    }
    else
    {
        mapWalkCols_[0] = 2;
        mapWalkCols_[1] = 3;
    }
    mapWalkFromChain_ = (walkChainContinueCol >= 0);
    mapPlayerWalkActive_ = true;
    mapWalkAccumNs_ = 0;
    {
        const auto now = std::chrono::steady_clock::now();
        mapWalkLastTickNs_ =
            std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
    }
    syncCameraToFollowPlayer_();
    if (mapUiMode_ == MapUiMode::ViewMap)
    {
        clampMapCamera_();
    }
    else if (mapUiMode_ == MapUiMode::ViewWorld)
    {
        clampWorldCamera_();
    }
}

void Game::advanceMapWalkAnimFrame_()
{
    if (!mapPlayerWalkActive_)
    {
        return;
    }
    ++mapWalkFrameInSegment_;
    if (mapWalkFrameInSegment_ >= mapWalkFrameCount_)
    {
        commitCompletedMapWalk_();
    }
}

namespace
{

std::string asciiLowerScript(std::string s)
{
    for (char& ch : s)
    {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    return s;
}

/// FEATURE-MAP-049: map event sprite ``facing`` string to sheet row (matches ``Game::mapWalkSpriteRowForDelta_``).
int eventSpriteFacingRowFromString_(const std::string& raw)
{
    const std::string d = asciiLowerScript(raw);
    if (d == "down" || d == "south" || d == "s")
    {
        return 0;
    }
    if (d == "left" || d == "west" || d == "w")
    {
        return 1;
    }
    if (d == "right" || d == "east" || d == "e")
    {
        return 2;
    }
    if (d == "up" || d == "north" || d == "n")
    {
        return 3;
    }
    return -1;
}

bool parseCameraPanDelta(const std::string& raw, int& outDx, int& outDy)
{
    const std::string d = asciiLowerScript(raw);
    if (d == "north" || d == "up" || d == "n")
    {
        outDx = 0;
        outDy = -1;
        return true;
    }
    if (d == "south" || d == "down" || d == "s")
    {
        outDx = 0;
        outDy = 1;
        return true;
    }
    if (d == "west" || d == "left" || d == "w")
    {
        outDx = -1;
        outDy = 0;
        return true;
    }
    if (d == "east" || d == "right" || d == "e")
    {
        outDx = 1;
        outDy = 0;
        return true;
    }
    return false;
}

} // namespace

void Game::clearMapScriptDriveAndCameraState_()
{
    mapScriptBlockingWalk_ = false;
    mapScriptDriveActive_ = false;
    mapScriptDriveIsRun_ = false;
    // FEATURE-MAP-071: clear rail-step state
    mapScriptDriveStepsRemaining_ = 0;
    mapScriptDriveStepDx_ = 0;
    mapScriptDriveStepDy_ = 0;
    mapScriptCameraActive_ = false;
    mapScriptCameraRemaining_ = 0;
    mapScriptCameraDx_ = 0;
    mapScriptCameraDy_ = 0;
    mapScriptCameraSpeed_ = 0;
    mapScriptCameraOffsetTilesX_ = 0;
    mapScriptCameraOffsetTilesY_ = 0;
    mapViewDrawZoom_ = 1.0;
    if (mapScriptSavedWalkFrameMs_ > 0)
    {
        playerWalkFrameMs_ = mapScriptSavedWalkFrameMs_;
        mapScriptSavedWalkFrameMs_ = 0;
    }
}

void Game::finishMapScriptWalkDrive_()
{
    mapScriptBlockingWalk_ = false;
    mapScriptDriveActive_ = false;
    mapScriptDriveIsRun_ = false;
    mapScriptDriveStepsRemaining_ = 0;
    mapScriptDriveStepDx_ = 0;
    mapScriptDriveStepDy_ = 0;
    if (mapScriptSavedWalkFrameMs_ > 0)
    {
        playerWalkFrameMs_ = mapScriptSavedWalkFrameMs_;
        mapScriptSavedWalkFrameMs_ = 0;
    }
}

/// FEATURE-MAP-071: parse direction string to cardinal (dx, dy). Returns false for unknown input.
bool Game::parseScriptDirectionToDelta_(const std::string& dirRaw, int& outDx, int& outDy)
{
    const std::string d = asciiLowerScript(dirRaw);
    if (d == "up" || d == "north" || d == "n")
    {
        outDx = 0;
        outDy = -1;
        return true;
    }
    if (d == "down" || d == "south" || d == "s")
    {
        outDx = 0;
        outDy = 1;
        return true;
    }
    if (d == "left" || d == "west" || d == "w")
    {
        outDx = -1;
        outDy = 0;
        return true;
    }
    if (d == "right" || d == "east" || d == "e")
    {
        outDx = 1;
        outDy = 0;
        return true;
    }
    return false;
}

void Game::applyScriptPlayerFacingHint_(const std::string& dirRaw)
{
    const std::string d = asciiLowerScript(dirRaw);
    int dx = 0;
    int dy = 0;
    if (d == "up" || d == "north" || d == "n")
    {
        dx = 0;
        dy = -1;
    }
    else if (d == "down" || d == "south" || d == "s")
    {
        dx = 0;
        dy = 1;
    }
    else if (d == "left" || d == "west" || d == "w")
    {
        dx = -1;
        dy = 0;
    }
    else if (d == "right" || d == "east" || d == "e")
    {
        dx = 1;
        dy = 0;
    }
    mapPlayerFacingRow_ = mapWalkSpriteRowForDelta_(dx, dy);
}

std::optional<ScriptStepResult> Game::tryMapViewerScriptOpcode_(
    ScriptRuntime& rt, const std::string& op, const nlohmann::json& args)
{
    if (op == "face_north")
    {
        applyScriptPlayerFacingHint_("up");
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "face_south")
    {
        applyScriptPlayerFacingHint_("down");
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "face_east")
    {
        applyScriptPlayerFacingHint_("right");
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "face_west")
    {
        applyScriptPlayerFacingHint_("left");
        ++rt.pc;
        return ScriptStepResult::Continue;
    }

    if (op == "camera_zoom_in")
    {
        mapViewDrawZoom_ = std::min(3.5, mapViewDrawZoom_ * 1.12);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "camera_zoom_out")
    {
        mapViewDrawZoom_ = std::max(0.35, mapViewDrawZoom_ / 1.12);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "camera_follow_player")
    {
        mapScriptCameraActive_ = false;
        mapScriptCameraRemaining_ = 0;
        mapScriptCameraDx_ = 0;
        mapScriptCameraDy_ = 0;
        mapScriptCameraSpeed_ = 0;
        mapScriptCameraOffsetTilesX_ = 0;
        mapScriptCameraOffsetTilesY_ = 0;
        if (mapUiMode_ == MapUiMode::ViewMap)
        {
            syncCameraToFollowPlayer_();
            clampMapCamera_();
        }
        else if (mapUiMode_ == MapUiMode::ViewWorld)
        {
            syncCameraToFollowWorldPlayer_();
            clampWorldCamera_();
        }
        ++rt.pc;
        return ScriptStepResult::Continue;
    }

    if (op == "set_route_music")
    {
        const std::string track = args.value("track", std::string());
        const int fadeMs = std::max(0, args.value("fadeMs", 0));
        if (!track.empty())
        {
            musicManager_.playRouteMusic(track, fadeMs);
        }
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "play_music_once")
    {
        const std::string track = args.value("track", std::string());
        if (!track.empty())
        {
            musicManager_.playOnce(track);
        }
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "start_trainer_battle")
    {
        if (scriptedTrainerBattleActive_ || mapScriptBattleYielding_)
        {
            return ScriptStepResult::Yield;
        }
        startScriptedTrainerBattleFromOpcode_(args);
        if (scriptedTrainerBattleActive_)
        {
            mapScriptBattleYielding_ = true;
            return ScriptStepResult::Yield;
        }
        ++rt.pc;
        return ScriptStepResult::Continue;
    }

    if (op == "move_camera")
    {
        if (!mapScriptCameraActive_)
        {
            const std::string dirStr = args.value("direction", std::string());
            int pdx = 0;
            int pdy = 0;
            if (!parseCameraPanDelta(dirStr, pdx, pdy))
            {
                ++rt.pc;
                return ScriptStepResult::Continue;
            }
            const int steps = std::max(0, args.value("steps", 0));
            mapScriptCameraSpeed_ = std::max(0, args.value("speed", 0));
            mapScriptCameraDx_ = pdx;
            mapScriptCameraDy_ = pdy;
            mapScriptCameraRemaining_ = steps;
            if (steps <= 0)
            {
                ++rt.pc;
                return ScriptStepResult::Continue;
            }
            mapScriptCameraActive_ = true;
        }
        mapScriptCameraOffsetTilesX_ += mapScriptCameraDx_;
        mapScriptCameraOffsetTilesY_ += mapScriptCameraDy_;
        --mapScriptCameraRemaining_;
        if (mapUiMode_ == MapUiMode::ViewMap)
        {
            syncCameraToFollowPlayer_();
            clampMapCamera_();
        }
        else if (mapUiMode_ == MapUiMode::ViewWorld)
        {
            syncCameraToFollowWorldPlayer_();
            clampWorldCamera_();
        }
        if (mapScriptCameraRemaining_ == 0)
        {
            mapScriptCameraActive_ = false;
            ++rt.pc;
            return ScriptStepResult::Continue;
        }
        if (mapScriptCameraSpeed_ > 0)
        {
            rt.waitFrames = mapScriptCameraSpeed_;
        }
        return ScriptStepResult::Yield;
    }

    // FEATURE-MAP-071: walk_to_coords / run_to_coords — direction + steps rail movement.
    if (op == "walk_to_coords" || op == "run_to_coords")
    {
        const bool isRun = (op == "run_to_coords");
        if (mapUiMode_ != MapUiMode::ViewMap && mapUiMode_ != MapUiMode::ViewWorld)
        {
            finishMapScriptWalkDrive_();
            ++rt.pc;
            return ScriptStepResult::Continue;
        }

        if (!mapScriptDriveActive_)
        {
            // First activation: parse direction + steps.
            const std::string dir = args.value("direction", std::string("down"));
            const int steps = std::max(0, args.value("steps", 1));
            const bool faceFirst = args.value("faceFirst", true);

            int sdx = 0;
            int sdy = 0;
            if (!parseScriptDirectionToDelta_(dir, sdx, sdy))
            {
                // Unknown direction — skip opcode safely.
                ++rt.pc;
                return ScriptStepResult::Continue;
            }

            if (faceFirst)
            {
                applyScriptPlayerFacingHint_(dir);
            }

            if (steps == 0)
            {
                // Turn-only: facing applied above, no movement needed.
                ++rt.pc;
                return ScriptStepResult::Continue;
            }

            mapScriptDriveStepDx_ = sdx;
            mapScriptDriveStepDy_ = sdy;
            mapScriptDriveStepsRemaining_ = steps;
            mapScriptDriveActive_ = true;
            mapScriptDriveIsRun_ = isRun;
            mapScriptBlockingWalk_ = true;
            if (isRun && mapScriptSavedWalkFrameMs_ == 0)
            {
                mapScriptSavedWalkFrameMs_ = playerWalkFrameMs_;
                playerWalkFrameMs_ = std::max(16, playerWalkFrameMs_ / 2);
            }
        }

        // Yield while walk animation is in progress.
        if (mapPlayerWalkActive_)
        {
            return ScriptStepResult::Yield;
        }

        // No steps left — done.
        if (mapScriptDriveStepsRemaining_ <= 0)
        {
            finishMapScriptWalkDrive_();
            ++rt.pc;
            return ScriptStepResult::Continue;
        }

        // Attempt next stride along the fixed rail axis.
        const int sdx = mapScriptDriveStepDx_;
        const int sdy = mapScriptDriveStepDy_;
        const int nx = mapPlayerTileX_ + sdx * kMapWalkAnchorStrideTiles;
        const int ny = mapPlayerTileY_ + sdy * kMapWalkAnchorStrideTiles;
        if (mapPlayerFootprintBlockedAt_(nx, ny))
        {
            // Blocked mid-rail — finish early rather than hanging.
            finishMapScriptWalkDrive_();
            ++rt.pc;
            return ScriptStepResult::Continue;
        }
        --mapScriptDriveStepsRemaining_;
        requestPlayerMoveOnMap_(sdx, sdy, false, -1, true);
        return ScriptStepResult::Yield;
    }

    return std::nullopt;
}

bool Game::shouldAutoChainMapWalk_(int deltaX, int deltaY) const
{
    if (mapScriptBlockingWalk_)
    {
        return false;
    }
    if (mapScript_ && mapScript_->playerLocked)
    {
        return false;
    }
    const Uint8* k = SDL_GetKeyboardState(nullptr);
    if (deltaX == 0 && deltaY == -1)
    {
        return k[SDL_SCANCODE_W] != 0;
    }
    if (deltaX == 0 && deltaY == 1)
    {
        return k[SDL_SCANCODE_S] != 0;
    }
    if (deltaX == -1 && deltaY == 0)
    {
        return k[SDL_SCANCODE_A] != 0;
    }
    if (deltaX == 1 && deltaY == 0)
    {
        return k[SDL_SCANCODE_D] != 0;
    }
    return false;
}

void Game::commitCompletedMapWalk_()
{
    if (!mapPlayerWalkActive_)
    {
        return;
    }
    mapPlayerTileX_ += mapWalkDx_ * mapWalkTilesInSegment_ * kMapWalkAnchorStrideTiles;
    mapPlayerTileY_ += mapWalkDy_ * mapWalkTilesInSegment_ * kMapWalkAnchorStrideTiles;
    for (int t = 0; t < mapWalkTilesInSegment_; ++t)
    {
        mapWalkStepParity_ ^= 1;
    }
    const int odx = mapWalkDx_;
    const int ody = mapWalkDy_;
    const int lastWalkCol = mapWalkCols_[static_cast<size_t>(std::max(0, mapWalkFrameCount_ - 1))];
    mapPlayerWalkActive_ = false;
    mapWalkFrameInSegment_ = 0;
    mapWalkAccumNs_ = 0;
    mapWalkLastTickNs_ = 0;
    syncCameraToFollowPlayer_();
    if (mapUiMode_ == MapUiMode::ViewMap)
    {
        clampMapCamera_();
    }
    else if (mapUiMode_ == MapUiMode::ViewWorld)
    {
        clampWorldCamera_();
    }
    if (mapScriptBlockingWalk_)
    {
        mapWalkQueuedDirValid_ = false;
    }
    if (mapWalkQueuedDirValid_)
    {
        const int qdx = mapWalkQueuedDx_;
        const int qdy = mapWalkQueuedDy_;
        mapWalkQueuedDirValid_ = false;
        mapWalkStepParity_ = 0;
        requestPlayerMoveOnMap_(qdx, qdy, false);
    }
    else if (shouldAutoChainMapWalk_(odx, ody))
    {
        requestPlayerMoveOnMap_(odx, ody, false, lastWalkCol);
    }
    else
    {
        // FEATURE-MAP-078: step_on events take priority over a wild encounter on the same tile.
        if (!tryStepOnMapEvent_())
        {
            tryWildEncounterOnStep_();
        }
    }
}

void Game::tryWildEncounterOnStep_()
{
    if (overworldBattleActive_ || activeBattle_ || mapScript_ || mapScriptBlockingWalk_)
    {
        return;
    }
    if (mapUiMode_ != MapUiMode::ViewMap && mapUiMode_ != MapUiMode::ViewWorld)
    {
        return;
    }

    const MapData* md = nullptr;
    int localX = mapPlayerTileX_;
    int localY = mapPlayerTileY_;

    if (mapUiMode_ == MapUiMode::ViewMap)
    {
        md = &viewMapData_;
    }
    else
    {
        for (const WorldLayoutMapInstance& inst : worldLayoutInstances_)
        {
            if (mapPlayerTileX_ >= inst.worldOriginX && mapPlayerTileY_ >= inst.worldOriginY
                && mapPlayerTileX_ < inst.worldOriginX + inst.widthTiles
                && mapPlayerTileY_ < inst.worldOriginY + inst.heightTiles)
            {
                md = &inst.map;
                localX = mapPlayerTileX_ - inst.worldOriginX;
                localY = mapPlayerTileY_ - inst.worldOriginY;
                break;
            }
        }
    }

    if (md == nullptr || md->wildEncounterLayer.empty() || md->wildPatches.empty())
    {
        return;
    }
    if (localY < 0 || localX < 0 || localY >= md->height || localX >= md->width)
    {
        return;
    }
    if (static_cast<int>(md->wildEncounterLayer.size()) <= localY
        || static_cast<int>(md->wildEncounterLayer[static_cast<size_t>(localY)].size()) <= localX)
    {
        return;
    }
    const int patchIndex = md->wildEncounterLayer[static_cast<size_t>(localY)][static_cast<size_t>(localX)];
    if (patchIndex <= 0 || patchIndex > static_cast<int>(md->wildPatches.size()))
    {
        return;
    }
    const WildEncounterPatch& patch = md->wildPatches[static_cast<size_t>(patchIndex - 1)];
    const std::optional<std::string> species = rollWildEncounterSpecies(patch, *md, pokedb);
    if (species.has_value())
    {
        startOverworldWildBattle_(*species);
    }
}

void Game::tickMapPlayerWalk_()
{
    if (!mapPlayerWalkActive_)
    {
        return;
    }
    if (mapUiMode_ != MapUiMode::ViewMap && mapUiMode_ != MapUiMode::ViewWorld)
    {
        return;
    }
    using namespace std::chrono;
    const auto now = steady_clock::now();
    const std::int64_t nowNs = duration_cast<nanoseconds>(now.time_since_epoch()).count();
    if (mapWalkLastTickNs_ == 0)
    {
        mapWalkLastTickNs_ = nowNs;
        return;
    }
    std::int64_t dt = nowNs - mapWalkLastTickNs_;
    mapWalkLastTickNs_ = nowNs;
    constexpr std::int64_t kMaxStepNs = 100000000LL;
    if (dt > kMaxStepNs)
    {
        dt = kMaxStepNs;
    }
    mapWalkAccumNs_ += dt;
    const std::int64_t threshold = static_cast<std::int64_t>(playerWalkFrameMs_) * 1000000LL;
    if (threshold <= 0)
    {
        return;
    }
    while (mapWalkAccumNs_ >= threshold && mapPlayerWalkActive_)
    {
        mapWalkAccumNs_ -= threshold;
        advanceMapWalkAnimFrame_();
    }
    if (mapPlayerWalkActive_)
    {
        syncCameraToFollowPlayer_();
        if (mapUiMode_ == MapUiMode::ViewMap)
        {
            clampMapCamera_();
        }
        else if (mapUiMode_ == MapUiMode::ViewWorld)
        {
            clampWorldCamera_();
        }
    }
}

bool Game::loadMapCatalog_()
{
    mapCatalog_.clear();
    mapCatalogSel_ = 0;

    json root;
    {
        std::ifstream f(kMapsIndex);
        if (f)
        {
            try
            {
                f >> root;
            }
            catch (const std::exception& e)
            {
                std::cerr << "maps_index.json parse: " << e.what() << '\n';
            }
        }
    }

    if (root.contains("maps") && root["maps"].is_array())
    {
        for (const auto& el : root["maps"])
        {
            if (!el.is_object())
            {
                continue;
            }
            std::string id = el.value("id", "");
            if (id.empty())
            {
                continue;
            }
            std::string name = el.value("name", id);
            mapCatalog_.push_back({std::move(id), std::move(name)});
        }
    }

    if (!mapCatalog_.empty())
    {
        finalizeMapCatalogForPicker_();
        return true;
    }

    std::error_code ec;
    if (!std::filesystem::is_directory(kMapsDir, ec))
    {
        return false;
    }
    for (const auto& dir : std::filesystem::directory_iterator(kMapsDir, ec))
    {
        if (!dir.is_regular_file())
        {
            continue;
        }
        const auto p = dir.path();
        if (p.extension() != ".json")
        {
            continue;
        }
        if (p.filename().string() == "maps_index.json")
        {
            continue;
        }
        const std::string stem = p.stem().string();
        mapCatalog_.push_back({stem, stem});
    }
    finalizeMapCatalogForPicker_();
    return true;
}

void Game::openMapPicker_()
{
    destroyMapViewTextures_();
    viewMapData_ = {};
    mapTilesetDefs_.clear();
    clearWorldLayoutView_();
    mapPickerLastError_.clear();
    mapUiMode_ = MapUiMode::PickMap;
    mapCatalogSel_ = 0;
    walkabilityGridValid_ = false;
    loadOverworldViewConfig_();
    loadMapCatalog_();
}

void Game::closeMapUi_()
{
    mapUiMode_ = MapUiMode::None;
    clearMapScriptDriveAndCameraState_();
    mapScript_.reset();
    mapLoadedFromPath_.clear();
    pendingMapWarp_.pending = false;
    destroyMapViewTextures_();
    viewMapData_ = {};
    mapTilesetDefs_.clear();
    mapTilesetRenderMeta_.clear();
    walkabilityGridValid_ = false;
    mapCatalog_.clear();
    clearWorldLayoutView_();
    mapPickerLastError_.clear();
}

void Game::destroyMapViewTextures_()
{
    resetMapPlayerWalkState_();
    if (mapPlayerSpriteSheet_ != nullptr)
    {
        SDL_DestroyTexture(mapPlayerSpriteSheet_);
        mapPlayerSpriteSheet_ = nullptr;
    }
    for (auto& e : mapTilesetTextures_)
    {
        if (e.second != nullptr)
        {
            SDL_DestroyTexture(e.second);
            e.second = nullptr;
        }
    }
    mapTilesetTextures_.clear();
    for (auto& e : mapEventSpriteTextures_)
    {
        if (e.second != nullptr)
        {
            SDL_DestroyTexture(e.second);
            e.second = nullptr;
        }
    }
    mapEventSpriteTextures_.clear();
    mapTilesetRenderMeta_.clear();
}

SDL_Texture* Game::getOrLoadMapEventSpriteTexture_(const std::string& pathKey, const std::string& absPathFs)
{
    auto it = mapEventSpriteTextures_.find(pathKey);
    if (it != mapEventSpriteTextures_.end())
    {
        return it->second;
    }
    if (renderer == nullptr)
    {
        return nullptr;
    }
    SDL_Texture* t = IMG_LoadTexture(renderer, absPathFs.c_str());
    if (t == nullptr)
    {
        std::cerr << "map event sprite: IMG_LoadTexture(\"" << absPathFs << "\"): " << IMG_GetError() << '\n';
        return nullptr;
    }
    mapEventSpriteTextures_[pathKey] = t;
    return t;
}

void Game::drawMapEventSprites_(int ox, int oy, int tilePx, const SDL_Rect& panelRect)
{
    if (renderer == nullptr)
    {
        return;
    }
    const int camX = mapCamTileX_;
    const int camY = mapCamTileY_;
    const int vw = std::max(1, mapViewTilesW_);
    const int vh = std::max(1, mapViewTilesH_);

    SDL_RenderSetClipRect(renderer, &panelRect);
    SDL_BlendMode prevBlend = SDL_BLENDMODE_NONE;
    SDL_GetRenderDrawBlendMode(renderer, &prevBlend);

    for (const MapEventInstance& ev : viewMapData_.events)
    {
        if (!ev.hasSprite || ev.sprite.file.empty())
        {
            continue;
        }
        const std::string rel = mapEventSpriteRelPath_(ev.sprite);
        SDL_Texture* tex = getOrLoadMapEventSpriteTexture_(rel, rel);
        if (tex == nullptr)
        {
            continue;
        }
        int sw = 0;
        int sh = 0;
        SDL_QueryTexture(tex, nullptr, nullptr, &sw, &sh);
        const int cols = std::max(1, ev.sprite.sheetColumns);
        const int rows = std::max(1, ev.sprite.sheetRows);
        const int cw = sw / cols;
        const int ch = sh / rows;
        if (cw <= 0 || ch <= 0)
        {
            continue;
        }
        const int nCells = cols * rows;
        const int fi0 = std::clamp(ev.sprite.frame, 0, std::max(0, nCells - 1));
        int fc = fi0 % cols;
        int fr = fi0 / cols;
        if (!ev.sprite.facing.empty())
        {
            const int frAlt = eventSpriteFacingRowFromString_(ev.sprite.facing);
            if (frAlt >= 0 && frAlt < rows)
            {
                fr = frAlt;
            }
        }
        const int fi = std::clamp(fr * cols + std::clamp(fc, 0, std::max(0, cols - 1)), 0, std::max(0, nCells - 1));
        fc = fi % cols;
        fr = fi / cols;
        const SDL_Rect src{fc * cw, fr * ch, cw, ch};

        const int ax = ev.anchorX;
        const int ay = ev.anchorY;
        if (ax + 2 <= camX || ay + 2 <= camY || ax >= camX + vw || ay >= camY + vh)
        {
            continue;
        }
        const SDL_Rect dst{ox + (ax - camX) * tilePx, oy + (ay - camY) * tilePx, 2 * tilePx, 2 * tilePx};
        SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_BLEND);
        SDL_RenderCopy(renderer, tex, &src, &dst);
    }

    SDL_SetRenderDrawBlendMode(renderer, prevBlend);
    SDL_RenderSetClipRect(renderer, nullptr);
}

void Game::drawWorldLayoutEventSprites_(int ox, int oy, int tilePx, const SDL_Rect& panelRect)
{
    if (renderer == nullptr)
    {
        return;
    }
    const int camX = mapCamTileX_;
    const int camY = mapCamTileY_;
    const int vw = std::max(1, mapViewTilesW_);
    const int vh = std::max(1, mapViewTilesH_);

    SDL_RenderSetClipRect(renderer, &panelRect);
    SDL_BlendMode prevBlend = SDL_BLENDMODE_NONE;
    SDL_GetRenderDrawBlendMode(renderer, &prevBlend);

    for (const WorldLayoutMapInstance& inst : worldLayoutInstances_)
    {
        for (const MapEventInstance& ev : inst.map.events)
        {
            if (!ev.hasSprite || ev.sprite.file.empty())
            {
                continue;
            }
            const std::string rel = mapEventSpriteRelPath_(ev.sprite);
            SDL_Texture* tex = getOrLoadMapEventSpriteTexture_(rel, rel);
            if (tex == nullptr)
            {
                continue;
            }
            int sw = 0;
            int sh = 0;
            SDL_QueryTexture(tex, nullptr, nullptr, &sw, &sh);
            const int cols = std::max(1, ev.sprite.sheetColumns);
            const int rows = std::max(1, ev.sprite.sheetRows);
            const int cw = sw / cols;
            const int ch = sh / rows;
            if (cw <= 0 || ch <= 0)
            {
                continue;
            }
            const int nCells = cols * rows;
            const int fi0 = std::clamp(ev.sprite.frame, 0, std::max(0, nCells - 1));
            int fc = fi0 % cols;
            int fr = fi0 / cols;
            if (!ev.sprite.facing.empty())
            {
                const int frAlt = eventSpriteFacingRowFromString_(ev.sprite.facing);
                if (frAlt >= 0 && frAlt < rows)
                {
                    fr = frAlt;
                }
            }
            const int fi = std::clamp(fr * cols + std::clamp(fc, 0, std::max(0, cols - 1)), 0, std::max(0, nCells - 1));
            fc = fi % cols;
            fr = fi / cols;
            const SDL_Rect src{fc * cw, fr * ch, cw, ch};

            const int ax = inst.worldOriginX + ev.anchorX;
            const int ay = inst.worldOriginY + ev.anchorY;
            if (ax + 2 <= camX || ay + 2 <= camY || ax >= camX + vw || ay >= camY + vh)
            {
                continue;
            }
            const SDL_Rect dst{ox + (ax - camX) * tilePx, oy + (ay - camY) * tilePx, 2 * tilePx, 2 * tilePx};
            SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_BLEND);
            SDL_RenderCopy(renderer, tex, &src, &dst);
        }
    }

    SDL_SetRenderDrawBlendMode(renderer, prevBlend);
    SDL_RenderSetClipRect(renderer, nullptr);
}

void Game::rebuildMapTilesetRenderMeta_()
{
    mapTilesetRenderMeta_.clear();
    for (const TilesetDef& def : mapTilesetDefs_)
    {
        SDL_Texture* tex = getOrLoadMapTilesetTexture_(def.id);
        if (tex == nullptr)
        {
            continue;
        }
        int sheetW = 0;
        int sheetH = 0;
        SDL_QueryTexture(tex, nullptr, nullptr, &sheetW, &sheetH);
        const int columns = def.columns > 0 ? def.columns : inferColumns(sheetW, def.tileWidth, def.margin, def.spacing);
        mapTilesetRenderMeta_[def.id] = MapTilesetRenderMeta{tex, &def, std::max(1, columns)};
    }
}

bool Game::loadMapForView_(const std::string& mapId)
{
    clearMapScriptDriveAndCameraState_();
    mapScript_.reset();
    pendingMapWarp_.pending = false;
    clearWorldLayoutView_();
    // BUG-MAP-027: destroy tile (and prior player) textures before loadOverworldViewConfig_, which
    // calls reloadMapPlayerSpriteTexture_. Previously we destroyed after overworld config, wiping the
    // player sheet so single-map view and warp targets had no sprite until returning to Overworld.
    destroyMapViewTextures_();
    loadOverworldViewConfig_();
    const std::string path = std::string(kMapsDir) + "/" + mapId + ".json";
    if (!loadMapFromFile(path, viewMapData_))
    {
        return false;
    }
    if (!loadTilesetRegistry(kTilesetsJson, mapTilesetDefs_))
    {
        std::cerr << "map viewer: failed tileset registry\n";
        return false;
    }
    rebuildMapTilesetRenderMeta_();
    walkabilityGridValid_ = walkabilityGridMatchesMap_(viewMapData_);
    spawnPlayerOnLoadedMap_();
    syncCameraToFollowPlayer_();
    clampMapCamera_();
    mapUiMode_ = MapUiMode::ViewMap;
    overworldTileGridVisible_ = true;
    mapPickerLastError_.clear();
    mapLoadedFromPath_ = path;
    if (!viewMapData_.musicTrack.empty())
    {
        musicManager_.playRouteMusic(viewMapData_.musicTrack, 500);
    }
    bumpMapSingleViewFooterHintRevision_();
    return true;
}

void Game::finalizeMapCatalogForPicker_()
{
    mapCatalog_.erase(
        std::remove_if(
            mapCatalog_.begin(),
            mapCatalog_.end(),
            [](const std::pair<std::string, std::string>& p) { return p.first == "world_layout"; }),
        mapCatalog_.end());
    std::sort(mapCatalog_.begin(), mapCatalog_.end(), [](const auto& a, const auto& b) {
        return a.first < b.first;
    });
    mapCatalog_.insert(mapCatalog_.begin(), {std::string(kOverworldCatalogId), std::string("Overworld")});
}

void Game::clampMapCamera_()
{
    if (mapUiMode_ == MapUiMode::ViewWorld)
    {
        clampWorldCamera_();
        return;
    }
    const int mw = std::max(1, viewMapData_.width);
    const int mh = std::max(1, viewMapData_.height);
    const int vw = std::max(1, mapViewTilesW_);
    const int vh = std::max(1, mapViewTilesH_);
    const int maxX = std::max(0, mw - vw);
    const int maxY = std::max(0, mh - vh);
    mapCamTileX_ = std::clamp(mapCamTileX_, 0, maxX);
    mapCamTileY_ = std::clamp(mapCamTileY_, 0, maxY);
}

const TilesetDef* Game::findMapTilesetDef_(const std::string& tilesetId) const
{
    for (const TilesetDef& d : mapTilesetDefs_)
    {
        if (d.id == tilesetId)
        {
            return &d;
        }
    }
    return nullptr;
}

SDL_Texture* Game::getOrLoadMapTilesetTexture_(const std::string& tilesetId)
{
    const auto it = mapTilesetTextures_.find(tilesetId);
    if (it != mapTilesetTextures_.end())
    {
        return it->second;
    }
    const TilesetDef* def = findMapTilesetDef_(tilesetId);
    if (def == nullptr)
    {
        return nullptr;
    }
    SDL_Texture* tex = nullptr;
    if (!loadIntoTexture(tex, def->imagePath))
    {
        return nullptr;
    }
    mapTilesetTextures_[tilesetId] = tex;
    return tex;
}

void Game::drawMapViewPlayerFootprint_(int ox, int oy, int tilePx, const SDL_Rect& panelRect)
{
    if (renderer == nullptr)
    {
        return;
    }
    const int pw = std::max(1, mapPlayerTilesW_);
    const int ph = std::max(1, mapPlayerTilesH_);
    double vtx = 0.0;
    double vty = 0.0;
    mapPlayerWalkVisualOffsetsTiles_(vtx, vty);
    const int baseX =
        ox + static_cast<int>(std::lround((static_cast<double>(mapPlayerTileX_) - static_cast<double>(mapCamTileX_) + vtx) *
                                           static_cast<double>(tilePx)))
        + playerDrawOffsetTilesX_ * tilePx;
    const int baseY =
        oy + static_cast<int>(std::lround((static_cast<double>(mapPlayerTileY_) - static_cast<double>(mapCamTileY_) + vty) *
                                           static_cast<double>(tilePx)));
    const int dstW = pw * tilePx;
    const int dstH = ph * tilePx;
    const SDL_Rect playerRect{baseX, baseY, dstW, dstH};

    int sw = 0;
    int sh = 0;
    if (mapPlayerSpriteSheet_ != nullptr && SDL_QueryTexture(mapPlayerSpriteSheet_, nullptr, nullptr, &sw, &sh) == 0 &&
        sw >= 4 && sh >= 4 && sw % 4 == 0 && sh % 4 == 0)
    {
        const int cw = sw / 4;
        const int ch = sh / 4;
        const int colIdx =
            mapPlayerWalkActive_
                ? std::clamp(mapWalkCols_[static_cast<size_t>(std::clamp(mapWalkFrameInSegment_, 0, mapWalkFrameCount_ - 1))], 0, 3)
                : 0;
        const int rowIdx = std::clamp(mapPlayerFacingRow_, 0, 3);
        const SDL_Rect src{colIdx * cw, rowIdx * ch, cw, ch};
        SDL_RenderSetClipRect(renderer, &panelRect);
        SDL_SetTextureBlendMode(mapPlayerSpriteSheet_, SDL_BLENDMODE_BLEND);
        SDL_RenderCopy(renderer, mapPlayerSpriteSheet_, &src, &playerRect);
        SDL_RenderSetClipRect(renderer, nullptr);
        return;
    }

    SDL_RenderSetClipRect(renderer, &panelRect);
    SDL_BlendMode prevBlend = SDL_BLENDMODE_NONE;
    SDL_GetRenderDrawBlendMode(renderer, &prevBlend);
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(renderer, 80, 160, 255, 120);
    SDL_RenderFillRect(renderer, &playerRect);
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_NONE);
    SDL_SetRenderDrawColor(renderer, 255, 220, 80, 255);
    SDL_RenderDrawRect(renderer, &playerRect);
    SDL_SetRenderDrawBlendMode(renderer, prevBlend);
    SDL_RenderSetClipRect(renderer, nullptr);
}

bool Game::handleMapUiKey_(SDL_Keycode key, Uint32 keyRepeat)
{
    if (mapUiMode_ == MapUiMode::PickMap)
    {
        if (key == SDLK_ESCAPE)
        {
            closeMapUi_();
            return true;
        }
        if (key == SDLK_UP)
        {
            if (mapCatalogSel_ > 0)
            {
                --mapCatalogSel_;
            }
            return true;
        }
        if (key == SDLK_DOWN)
        {
            if (mapCatalogSel_ + 1 < mapCatalog_.size())
            {
                ++mapCatalogSel_;
            }
            return true;
        }
        if (key == SDLK_RETURN || key == SDLK_KP_ENTER)
        {
            if (!mapCatalog_.empty())
            {
                const std::string& pickId = mapCatalog_[mapCatalogSel_].first;
                if (pickId == kOverworldCatalogId)
                {
                    loadWorldLayoutForView_();
                }
                else if (!loadMapForView_(pickId))
                {
                    std::cerr << "map viewer: failed to load map\n";
                }
            }
            return true;
        }
        return true;
    }

    if (mapUiMode_ == MapUiMode::ViewWorld)
    {
        if (key == SDLK_ESCAPE)
        {
            mapUiMode_ = MapUiMode::PickMap;
            destroyMapViewTextures_();
            viewMapData_ = {};
            mapTilesetDefs_.clear();
            clearWorldLayoutView_();
            walkabilityGridValid_ = false;
            return true;
        }
        if (key == SDLK_l && keyRepeat == 0)
        {
            overworldTileGridVisible_ = !overworldTileGridVisible_;
            return true;
        }
        if (handleMapScriptKey_(key))
        {
            return true;
        }
        if (mapScript_ && (mapScript_->playerLocked || mapScriptBlockingWalk_))
        {
            if (key == SDLK_w || key == SDLK_s || key == SDLK_a || key == SDLK_d)
            {
                return true;
            }
        }
        if (key == SDLK_q && tryStartNearbyMapScript_())
        {
            return true;
        }
        if (key == SDLK_w)
        {
            requestPlayerMoveOnMap_(0, -1, keyRepeat != 0);
            return true;
        }
        if (key == SDLK_s)
        {
            requestPlayerMoveOnMap_(0, 1, keyRepeat != 0);
            return true;
        }
        if (key == SDLK_a)
        {
            requestPlayerMoveOnMap_(-1, 0, keyRepeat != 0);
            return true;
        }
        if (key == SDLK_d)
        {
            requestPlayerMoveOnMap_(1, 0, keyRepeat != 0);
            return true;
        }
        return true;
    }

    if (mapUiMode_ == MapUiMode::ViewMap)
    {
        if (key == SDLK_ESCAPE)
        {
            mapUiMode_ = MapUiMode::PickMap;
            return true;
        }
        if (key == SDLK_l && keyRepeat == 0)
        {
            overworldTileGridVisible_ = !overworldTileGridVisible_;
            return true;
        }
        if (handleMapScriptKey_(key))
        {
            return true;
        }
        if (mapScript_ && (mapScript_->playerLocked || mapScriptBlockingWalk_))
        {
            if (key == SDLK_w || key == SDLK_s || key == SDLK_a || key == SDLK_d)
            {
                return true;
            }
        }
        if (key == SDLK_q && tryStartNearbyMapScript_())
        {
            return true;
        }
        if (key == SDLK_w)
        {
            requestPlayerMoveOnMap_(0, -1, keyRepeat != 0);
            return true;
        }
        if (key == SDLK_s)
        {
            requestPlayerMoveOnMap_(0, 1, keyRepeat != 0);
            return true;
        }
        if (key == SDLK_a)
        {
            requestPlayerMoveOnMap_(-1, 0, keyRepeat != 0);
            return true;
        }
        if (key == SDLK_d)
        {
            requestPlayerMoveOnMap_(1, 0, keyRepeat != 0);
            return true;
        }
        return true;
    }

    return false;
}

void Game::drawMapPicker_()
{
    if (renderer == nullptr)
    {
        return;
    }
    SDL_SetRenderDrawColor(renderer, 24, 26, 32, 255);
    SDL_RenderFillRect(renderer, nullptr);

    const SDL_Color title{220, 225, 240, 255};
    const SDL_Color hi{255, 230, 120, 255};
    const SDL_Color dim{160, 165, 180, 255};
    renderText("Map / Overworld viewer — Up/Down  Enter  Esc back", 24, 20, title);
    if (!mapPickerLastError_.empty())
    {
        const SDL_Color err{255, 140, 120, 255};
        renderText(mapPickerLastError_, 24, 44, err);
    }

    if (mapCatalog_.empty())
    {
        renderText("No maps found under src/maps (run validate_maps or the map editor).", 24, 56, dim);
        return;
    }

    int y = mapPickerLastError_.empty() ? 56 : 72;
    const int lineSkip = (font_ != nullptr) ? TTF_FontLineSkip(font_) : 20;
    const size_t n = mapCatalog_.size();
    size_t first = 0;
    if (mapCatalogSel_ >= 18 && n > 20)
    {
        first = std::min(mapCatalogSel_ - 8, n - 20);
    }
    const size_t last = std::min(first + 20, n);
    for (size_t i = first; i < last; ++i)
    {
        const std::string& stem = mapCatalog_[i].first;
        const std::string line =
            (i == mapCatalogSel_ ? "> " : "  ")
            + (stem == kOverworldCatalogId ? std::string("Overworld — world_layout.json")
                                           : (stem + " — " + mapCatalog_[i].second));
        renderText(line, 32, y, i == mapCatalogSel_ ? hi : dim);
        y += lineSkip;
    }
}

void Game::drawMapView_()
{
    if (renderer == nullptr)
    {
        return;
    }
    SDL_SetRenderDrawColor(renderer, 18, 20, 26, 255);
    SDL_RenderFillRect(renderer, nullptr);

    constexpr int kLogicalWidth = 1280;
    constexpr int kLogicalHeight = 720;
    const int vw = std::max(1, mapViewTilesW_);
    const int vh = std::max(1, mapViewTilesH_);
    int tilePx = std::min(kLogicalWidth / vw, kLogicalHeight / vh);
    tilePx = std::max(4, tilePx);
    tilePx = std::max(2, static_cast<int>(std::lround(static_cast<double>(tilePx) * mapViewDrawZoom_)));

    const int panelW = vw * tilePx;
    const int panelH = vh * tilePx;
    const int ox = (kLogicalWidth - panelW) / 2;
    const int oy = (kLogicalHeight - panelH) / 2;

    const int mw = viewMapData_.width;
    const int mh = viewMapData_.height;
    const int subPixX = static_cast<int>(std::lround(mapCamSubTileOffX_ * static_cast<double>(tilePx)));
    const int subPixY = static_cast<int>(std::lround(mapCamSubTileOffY_ * static_cast<double>(tilePx)));
    const SDL_Rect panelClip{ox, oy, panelW, panelH};
    SDL_RenderSetClipRect(renderer, &panelClip);

    const bool overPlayerGridValid = overPlayerGridMatchesMap_(viewMapData_);
    auto drawMapTileLayersAt = [&](int mx, int my, const SDL_Rect& dst, bool overPass) {
        for (const TileLayer& layer : viewMapData_.tileLayers)
        {
            if (static_cast<int>(layer.cells.size()) <= my)
            {
                continue;
            }
            const auto& row = layer.cells[static_cast<size_t>(my)];
            if (static_cast<int>(row.size()) <= mx)
            {
                continue;
            }
            const MapCell& c = row[static_cast<size_t>(mx)];
            if (c.empty || c.tileIndex <= 0)
            {
                continue;
            }
            const bool drawOverPlayer = overPlayerGridValid
                && viewMapData_.overPlayerLayer[static_cast<size_t>(my)][static_cast<size_t>(mx)] != 0
                && layer.id != "ground";
            if (overPass)
            {
                if (!drawOverPlayer || !layer.applyOverPlayer)
                {
                    continue;
                }
            }
            else if (drawOverPlayer && layer.applyOverPlayer)
            {
                continue;
            }

            const auto metaIt = mapTilesetRenderMeta_.find(c.tilesetId);
            if (metaIt == mapTilesetRenderMeta_.end() || metaIt->second.texture == nullptr || metaIt->second.def == nullptr)
            {
                continue;
            }
            const MapTilesetRenderMeta& meta = metaIt->second;
            const TilesetDef* def = meta.def;
            const int cols = std::max(1, meta.columns);
            const int t0 = c.tileIndex - 1;
            const int col = t0 % cols;
            const int rowIdx = t0 / cols;
            const int sx = def->margin + col * (def->tileWidth + def->spacing);
            const int sy = def->margin + rowIdx * (def->tileHeight + def->spacing);
            SDL_Rect src{sx, sy, def->tileWidth, def->tileHeight};
            SDL_RenderCopy(renderer, meta.texture, &src, &dst);
        }
    };

    for (int ty = -1; ty <= vh; ++ty)
    {
        for (int tx = -1; tx <= vw; ++tx)
        {
            const int mx = mapCamTileX_ + tx;
            const int my = mapCamTileY_ + ty;
            SDL_Rect dst{ox + tx * tilePx - subPixX, oy + ty * tilePx - subPixY, tilePx, tilePx};
            if (mx < 0 || my < 0 || mx >= mw || my >= mh)
            {
                SDL_SetRenderDrawColor(renderer, 14, 14, 18, 255);
                SDL_RenderFillRect(renderer, &dst);
                continue;
            }
            SDL_SetRenderDrawColor(renderer, 32, 34, 42, 255);
            SDL_RenderFillRect(renderer, &dst);
            drawMapTileLayersAt(mx, my, dst, false);
            if (overworldTileGridVisible_)
            {
                SDL_SetRenderDrawColor(renderer, 48, 50, 58, 255);
                SDL_RenderDrawRect(renderer, &dst);
            }
        }
    }
    SDL_RenderSetClipRect(renderer, nullptr);

    {
        const SDL_Rect panelRect{ox, oy, panelW, panelH};
        drawMapViewPlayerFootprint_(ox - subPixX, oy - subPixY, tilePx, panelRect);
    }

    SDL_RenderSetClipRect(renderer, &panelClip);
    for (int ty = -1; ty <= vh; ++ty)
    {
        for (int tx = -1; tx <= vw; ++tx)
        {
            const int mx = mapCamTileX_ + tx;
            const int my = mapCamTileY_ + ty;
            if (mx < 0 || my < 0 || mx >= mw || my >= mh)
            {
                continue;
            }
            SDL_Rect dst{ox + tx * tilePx - subPixX, oy + ty * tilePx - subPixY, tilePx, tilePx};
            drawMapTileLayersAt(mx, my, dst, true);
        }
    }
    SDL_RenderSetClipRect(renderer, nullptr);

    const SDL_Rect mapPanelRect{ox, oy, panelW, panelH};
    drawMapEventSprites_(ox - subPixX, oy - subPixY, tilePx, mapPanelRect);

    drawMapScriptOverlay_();
    const SDL_Color hint{180, 185, 200, 255};
    if (mapSingleViewFooterHintRevision_ != mapSingleViewFooterHintBuiltRevision_)
    {
        std::string& s = mapSingleViewFooterHintScratch_;
        s.clear();
        s.reserve(static_cast<size_t>(viewMapData_.name.size()) + 96U);
        s.append(viewMapData_.name);
        s.append("  (");
        s.append(std::to_string(mw));
        s.append("x");
        s.append(std::to_string(mh));
        s.append(")  view ");
        s.append(std::to_string(vw));
        s.append("x");
        s.append(std::to_string(vh));
        s.append("  player ");
        s.append(std::to_string(std::max(1, mapPlayerTilesW_)));
        s.append("x");
        s.append(std::to_string(std::max(1, mapPlayerTilesH_)));
        s.append("  WASD  Q talk  L grid  Esc list");
        mapSingleViewFooterHintBuiltRevision_ = mapSingleViewFooterHintRevision_;
    }
    renderText(mapSingleViewFooterHintScratch_, 16, kLogicalHeight - 28, hint);
}

void Game::drawWorldLayoutView_()
{
    if (renderer == nullptr)
    {
        return;
    }
    SDL_SetRenderDrawColor(renderer, 18, 20, 26, 255);
    SDL_RenderFillRect(renderer, nullptr);

    constexpr int kLogicalWidth = 1280;
    constexpr int kLogicalHeight = 720;
    const int vw = std::max(1, mapViewTilesW_);
    const int vh = std::max(1, mapViewTilesH_);
    int tilePx = std::min(kLogicalWidth / vw, kLogicalHeight / vh);
    tilePx = std::max(4, tilePx);
    tilePx = std::max(2, static_cast<int>(std::lround(static_cast<double>(tilePx) * mapViewDrawZoom_)));

    const int panelW = vw * tilePx;
    const int panelH = vh * tilePx;
    const int ox = (kLogicalWidth - panelW) / 2;
    const int oy = (kLogicalHeight - panelH) / 2;

    const int spanW = std::max(1, worldBoundsMaxX_ - worldBoundsMinX_);
    const int spanH = std::max(1, worldBoundsMaxY_ - worldBoundsMinY_);
    const int subPixX = static_cast<int>(std::lround(mapCamSubTileOffX_ * static_cast<double>(tilePx)));
    const int subPixY = static_cast<int>(std::lround(mapCamSubTileOffY_ * static_cast<double>(tilePx)));
    const SDL_Rect worldClip{ox, oy, panelW, panelH};
    SDL_RenderSetClipRect(renderer, &worldClip);

    auto drawWorldTileLayersAt = [&](int wx, int wy, const SDL_Rect& dst, bool overPass) {
        for (const WorldLayoutMapInstance& inst : worldLayoutInstances_)
        {
            if (wx < inst.worldOriginX || wy < inst.worldOriginY)
            {
                continue;
            }
            if (wx >= inst.worldOriginX + inst.widthTiles || wy >= inst.worldOriginY + inst.heightTiles)
            {
                continue;
            }
            const int mx = wx - inst.worldOriginX;
            const int my = wy - inst.worldOriginY;
            const MapData& md = inst.map;

            for (const TileLayer& layer : md.tileLayers)
            {
                if (static_cast<int>(layer.cells.size()) <= my)
                {
                    continue;
                }
                const auto& row = layer.cells[static_cast<size_t>(my)];
                if (static_cast<int>(row.size()) <= mx)
                {
                    continue;
                }
                const MapCell& c = row[static_cast<size_t>(mx)];
                if (c.empty || c.tileIndex <= 0)
                {
                    continue;
                }
                const bool drawOverPlayer = inst.overPlayerGridValid
                    && md.overPlayerLayer[static_cast<size_t>(my)][static_cast<size_t>(mx)] != 0
                    && layer.id != "ground";
                if (overPass)
                {
                    if (!drawOverPlayer || !layer.applyOverPlayer)
                    {
                        continue;
                    }
                }
                else if (drawOverPlayer && layer.applyOverPlayer)
                {
                    continue;
                }

                const auto metaIt = mapTilesetRenderMeta_.find(c.tilesetId);
                if (metaIt == mapTilesetRenderMeta_.end() || metaIt->second.texture == nullptr
                    || metaIt->second.def == nullptr)
                {
                    continue;
                }
                const MapTilesetRenderMeta& meta = metaIt->second;
                const TilesetDef* def = meta.def;
                const int cols = std::max(1, meta.columns);
                const int t0 = c.tileIndex - 1;
                const int col = t0 % cols;
                const int rowIdx = t0 / cols;
                const int sx = def->margin + col * (def->tileWidth + def->spacing);
                const int sy = def->margin + rowIdx * (def->tileHeight + def->spacing);
                SDL_Rect src{sx, sy, def->tileWidth, def->tileHeight};
                SDL_RenderCopy(renderer, meta.texture, &src, &dst);
            }
        }
    };

    for (int ty = -1; ty <= vh; ++ty)
    {
        for (int tx = -1; tx <= vw; ++tx)
        {
            const int wx = mapCamTileX_ + tx;
            const int wy = mapCamTileY_ + ty;
            SDL_Rect dst{ox + tx * tilePx - subPixX, oy + ty * tilePx - subPixY, tilePx, tilePx};

            if (wx < worldBoundsMinX_ || wy < worldBoundsMinY_ || wx >= worldBoundsMaxX_ || wy >= worldBoundsMaxY_)
            {
                SDL_SetRenderDrawColor(renderer, 14, 14, 18, 255);
                SDL_RenderFillRect(renderer, &dst);
                continue;
            }

            SDL_SetRenderDrawColor(renderer, 32, 34, 42, 255);
            SDL_RenderFillRect(renderer, &dst);
            drawWorldTileLayersAt(wx, wy, dst, false);

            if (overworldTileGridVisible_)
            {
                SDL_SetRenderDrawColor(renderer, 48, 50, 58, 255);
                SDL_RenderDrawRect(renderer, &dst);
            }
        }
    }
    SDL_RenderSetClipRect(renderer, nullptr);

    {
        const SDL_Rect panelRect{ox, oy, panelW, panelH};
        drawMapViewPlayerFootprint_(ox - subPixX, oy - subPixY, tilePx, panelRect);
    }

    SDL_RenderSetClipRect(renderer, &worldClip);
    for (int ty = -1; ty <= vh; ++ty)
    {
        for (int tx = -1; tx <= vw; ++tx)
        {
            const int wx = mapCamTileX_ + tx;
            const int wy = mapCamTileY_ + ty;
            if (wx < worldBoundsMinX_ || wy < worldBoundsMinY_ || wx >= worldBoundsMaxX_ || wy >= worldBoundsMaxY_)
            {
                continue;
            }
            SDL_Rect dst{ox + tx * tilePx - subPixX, oy + ty * tilePx - subPixY, tilePx, tilePx};
            drawWorldTileLayersAt(wx, wy, dst, true);
        }
    }
    SDL_RenderSetClipRect(renderer, nullptr);

    const SDL_Rect worldPanelRect{ox, oy, panelW, panelH};
    drawWorldLayoutEventSprites_(ox - subPixX, oy - subPixY, tilePx, worldPanelRect);

    drawMapScriptOverlay_();
    const SDL_Color hint{180, 185, 200, 255};
    if (worldLayoutViewFooterHintRevision_ != worldLayoutViewFooterHintBuiltRevision_)
    {
        std::string& s = worldLayoutViewFooterHintScratch_;
        s.clear();
        s.reserve(96U);
        s.append("Overworld  world ");
        s.append(std::to_string(spanW));
        s.append("x");
        s.append(std::to_string(spanH));
        s.append("  view ");
        s.append(std::to_string(vw));
        s.append("x");
        s.append(std::to_string(vh));
        s.append("  player ");
        s.append(std::to_string(std::max(1, mapPlayerTilesW_)));
        s.append("x");
        s.append(std::to_string(std::max(1, mapPlayerTilesH_)));
        s.append("  WASD  Q talk  L grid  Esc list");
        worldLayoutViewFooterHintBuiltRevision_ = worldLayoutViewFooterHintRevision_;
    }
    renderText(worldLayoutViewFooterHintScratch_, 16, kLogicalHeight - 28, hint);
}

bool Game::mapEventFootprintsTouch_(
    int playerX, int playerY, int playerW, int playerH, int eventAnchorX, int eventAnchorY)
{
    const int ex = eventAnchorX;
    const int ey = eventAnchorY;
    const int px1 = playerX + playerW;
    const int py1 = playerY + playerH;
    for (int ty = playerY; ty < py1; ++ty)
    {
        for (int tx = playerX; tx < px1; ++tx)
        {
            const bool aboveOrBelow = (ty == ey - 1 || ty == ey + 2) && (tx == ex || tx == ex + 1);
            const bool leftOrRight = (tx == ex - 1 || tx == ex + 2) && (ty == ey || ty == ey + 1);
            if (aboveOrBelow || leftOrRight)
            {
                return true;
            }
        }
    }
    return false;
}

void Game::wireMapScriptCallbacks_()
{
    if (!mapScript_)
    {
        return;
    }
    ScriptRuntime& s = *mapScript_;
    s.onShowMessage = [this](const std::string& t) { setDisplayText_(t); };
    s.onCloseMessage = [this]() { setDisplayText_(""); };
    s.onLockPlayer = [](bool) {
    };
    s.onWarp = [this](const std::string& mid, int x, int y) {
        pendingMapWarp_.pending = true;
        pendingMapWarp_.mapId = mid;
        pendingMapWarp_.tileX = x;
        pendingMapWarp_.tileY = y;
    };
    s.onDebugStub = [this](const std::string& op) { setDisplayText_(std::string("Script stub: ") + op); };
    s.onFacingHint = [this](const std::string& d) { applyScriptPlayerFacingHint_(d); };
    // FEATURE-MAP-072: route flag reads/writes through persistent GameState (debounced flush).
    s.onReadFlag = [this](const std::string& n) { return gameState_.getFlag(n); };
    s.onWriteFlag = [this](const std::string& n, bool v) {
        gameState_.setFlag(n, v);
        gameState_.flushIfDirty();
    };
    // FEATURE-MAP-074: resolve reusable library connectors on demand.
    s.onLoadLibrarySubflow = [this](const std::string& n) { return loadLibrarySubflow_(n); };
    s.tryMapViewerScriptStep = [this](ScriptRuntime& rt, const std::string& op, const nlohmann::json& args) {
        return tryMapViewerScriptOpcode_(rt, op, args);
    };
}

nlohmann::json Game::loadLibrarySubflow_(const std::string& name) const
{
    // FEATURE-MAP-074: connectors live under src/maps/scripts/_library/<name>.json.
    if (name.empty() || name.find('/') != std::string::npos || name.find("..") != std::string::npos)
    {
        return json::object();
    }
    const std::string path = std::string(kMapsDir) + "/scripts/_library/" + name + ".json";
    json root;
    std::ifstream f(path);
    if (!f)
    {
        return json::object();
    }
    try
    {
        f >> root;
    }
    catch (const std::exception&)
    {
        return json::object();
    }
    return root.is_object() ? root : json::object();
}

void Game::startMapScript_(const std::string& mapJsonPath, const MapEventInstance& ev)
{
    mapScript_.emplace();
    clearMapScriptDriveAndCameraState_();
    wireMapScriptCallbacks_();
    mapScriptEvent_ = ev;
    mapScriptHasEvent_ = true;
    const json doc = loadEventScriptJson(mapJsonPath, ev);
    mapScript_->loadDocument(doc);
}

void Game::applyMapScriptCompletion_()
{
    // FEATURE-MAP-078: on script finish, set the cleared flag and apply onComplete flag changes.
    if (!mapScriptHasEvent_)
    {
        return;
    }
    mapScriptHasEvent_ = false;
    if (!mapScriptEvent_.clearedFlag.empty())
    {
        gameState_.setFlag(mapScriptEvent_.clearedFlag, true);
    }
    for (const std::string& f : mapScriptEvent_.onCompleteSetFlags)
    {
        gameState_.setFlag(f, true);
    }
    for (const std::string& f : mapScriptEvent_.onCompleteClearFlags)
    {
        gameState_.setFlag(f, false);
    }
    gameState_.flushIfDirty();
}

bool Game::tryStartNearbyMapScript_()
{
    if (mapPlayerWalkActive_)
    {
        return false;
    }
    if (mapScript_)
    {
        return false;
    }
    const int pw = std::max(1, mapPlayerTilesW_);
    const int ph = std::max(1, mapPlayerTilesH_);
    if (mapUiMode_ == MapUiMode::ViewMap)
    {
        if (mapLoadedFromPath_.empty())
        {
            return false;
        }
        for (const MapEventInstance& ev : viewMapData_.events)
        {
            // FEATURE-MAP-078: Q only starts interact-type events whose run-condition holds.
            if (ev.trigger != MapEventTrigger::Interact || !mapEventRunConditionOk_(ev))
            {
                continue;
            }
            if (mapEventFootprintsTouch_(mapPlayerTileX_, mapPlayerTileY_, pw, ph, ev.anchorX, ev.anchorY))
            {
                startMapScript_(mapLoadedFromPath_, ev);
                return true;
            }
        }
    }
    else if (mapUiMode_ == MapUiMode::ViewWorld)
    {
        for (auto it = worldLayoutInstances_.rbegin(); it != worldLayoutInstances_.rend(); ++it)
        {
            const WorldLayoutMapInstance& inst = *it;
            const std::string path = std::string(kMapsDir) + "/" + inst.mapId + ".json";
            for (const MapEventInstance& ev : inst.map.events)
            {
                if (ev.trigger != MapEventTrigger::Interact || !mapEventRunConditionOk_(ev))
                {
                    continue;
                }
                const int wx = inst.worldOriginX + ev.anchorX;
                const int wy = inst.worldOriginY + ev.anchorY;
                if (mapEventFootprintsTouch_(mapPlayerTileX_, mapPlayerTileY_, pw, ph, wx, wy))
                {
                    startMapScript_(path, ev);
                    return true;
                }
            }
        }
    }
    return false;
}

bool Game::mapEventRunConditionOk_(const MapEventInstance& ev) const
{
    // FEATURE-MAP-078: an empty condition is always eligible; otherwise the flag must match.
    if (ev.conditionFlag.empty())
    {
        return true;
    }
    return gameState_.getFlag(ev.conditionFlag) == ev.conditionWantSet;
}

bool Game::mapEventClearedGate_(const MapEventInstance& ev) const
{
    // FEATURE-MAP-078: true when the event may still fire (cleared flag not yet set).
    return ev.clearedFlag.empty() || !gameState_.getFlag(ev.clearedFlag);
}

bool Game::tryStepOnMapEvent_()
{
    // FEATURE-MAP-078: fire a one-shot step_on event when the footprint lands on its anchor.
    if (mapScript_ || mapPlayerWalkActive_)
    {
        return false;
    }
    const int pw = std::max(1, mapPlayerTilesW_);
    const int ph = std::max(1, mapPlayerTilesH_);
    auto onAnchor = [&](int ax, int ay) {
        return mapPlayerTileX_ < ax + 2 && ax < mapPlayerTileX_ + pw
            && mapPlayerTileY_ < ay + 2 && ay < mapPlayerTileY_ + ph;
    };
    if (mapUiMode_ == MapUiMode::ViewMap)
    {
        if (mapLoadedFromPath_.empty())
        {
            return false;
        }
        for (const MapEventInstance& ev : viewMapData_.events)
        {
            if (ev.trigger != MapEventTrigger::StepOn || !mapEventRunConditionOk_(ev) || !mapEventClearedGate_(ev))
            {
                continue;
            }
            if (onAnchor(ev.anchorX, ev.anchorY))
            {
                startMapScript_(mapLoadedFromPath_, ev);
                return true;
            }
        }
    }
    else if (mapUiMode_ == MapUiMode::ViewWorld)
    {
        for (auto it = worldLayoutInstances_.rbegin(); it != worldLayoutInstances_.rend(); ++it)
        {
            const WorldLayoutMapInstance& inst = *it;
            const std::string path = std::string(kMapsDir) + "/" + inst.mapId + ".json";
            for (const MapEventInstance& ev : inst.map.events)
            {
                if (ev.trigger != MapEventTrigger::StepOn || !mapEventRunConditionOk_(ev) || !mapEventClearedGate_(ev))
                {
                    continue;
                }
                if (onAnchor(inst.worldOriginX + ev.anchorX, inst.worldOriginY + ev.anchorY))
                {
                    startMapScript_(path, ev);
                    return true;
                }
            }
        }
    }
    return false;
}

bool Game::handleMapScriptKey_(SDL_Keycode key)
{
    if (!mapScript_)
    {
        return false;
    }
    if (mapScript_->messageBlocking && (key == SDLK_q || key == SDLK_SPACE))
    {
        mapScript_->tryAdvanceMessage();
        return true;
    }
    return false;
}

void Game::drawMapScriptOverlay_()
{
    if (!mapScript_ || renderer == nullptr || font_ == nullptr)
    {
        return;
    }
    if (displayText_.empty())
    {
        return;
    }
    const SDL_Color white{240, 242, 248, 255};
    const int lineSkip = TTF_FontLineSkip(font_);
    int y = 720 - 120;
    for (const std::string& line : displayTextLines_)
    {
        if (!line.empty())
        {
            renderText(line, 24, y, white);
        }
        y += lineSkip;
    }
}

void Game::tryFireAutoMapEvents_()
{
    // FEATURE-MAP-078: when idle, auto-fire the first eligible on_map_enter / on_condition event.
    if (mapScript_ || mapPlayerWalkActive_ || overworldBattleActive_ || activeBattle_)
    {
        return;
    }
    if (mapUiMode_ != MapUiMode::ViewMap && mapUiMode_ != MapUiMode::ViewWorld)
    {
        return;
    }
    auto eligible = [&](const MapEventInstance& ev) {
        return (ev.trigger == MapEventTrigger::OnMapEnter || ev.trigger == MapEventTrigger::OnCondition)
            && mapEventRunConditionOk_(ev) && mapEventClearedGate_(ev);
    };
    if (mapUiMode_ == MapUiMode::ViewMap)
    {
        if (mapLoadedFromPath_.empty())
        {
            return;
        }
        for (const MapEventInstance& ev : viewMapData_.events)
        {
            if (eligible(ev))
            {
                startMapScript_(mapLoadedFromPath_, ev);
                return;
            }
        }
    }
    else
    {
        for (auto it = worldLayoutInstances_.rbegin(); it != worldLayoutInstances_.rend(); ++it)
        {
            const WorldLayoutMapInstance& inst = *it;
            const std::string path = std::string(kMapsDir) + "/" + inst.mapId + ".json";
            for (const MapEventInstance& ev : inst.map.events)
            {
                if (eligible(ev))
                {
                    startMapScript_(path, ev);
                    return;
                }
            }
        }
    }
}

void Game::tickMapScript_()
{
    if (!mapScript_)
    {
        tryFireAutoMapEvents_();
        executePendingMapWarp_();
        return;
    }
    int guard = 64;
    while (guard-- > 0 && mapScript_ && !mapScript_->finished && !mapScript_->messageBlocking && mapScript_->waitFrames == 0)
    {
        const ScriptStepResult r = mapScript_->stepFrame();
        if (r == ScriptStepResult::Yield || r == ScriptStepResult::Finished || r == ScriptStepResult::Error)
        {
            break;
        }
    }
    if (mapScript_ && mapScript_->finished)
    {
        if (!mapScriptWasBattleLoss_)
        {
            applyMapScriptCompletion_();
        }
        else
        {
            mapScriptWasBattleLoss_ = false;
        }
        clearMapScriptDriveAndCameraState_();
        setDisplayText_("");
        mapScript_.reset();
        mapScriptBattleYielding_ = false;
    }
    executePendingMapWarp_();
}

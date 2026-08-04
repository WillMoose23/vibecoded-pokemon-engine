#include "map_data.h"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>

#include <json.hpp>

using json = nlohmann::json;

namespace
{

int intFromJson(const json& j, int defaultValue)
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

bool readJsonFile(const std::string& path, json& out)
{
    std::ifstream file(path);
    if (!file)
    {
        std::cerr << "map_data: failed to open " << path << '\n';
        return false;
    }
    try
    {
        file >> out;
    }
    catch (const std::exception& e)
    {
        std::cerr << "map_data: parse error in " << path << ": " << e.what() << '\n';
        return false;
    }
    return true;
}

bool parseIntGrid(const json& rows, int w, int h, std::vector<std::vector<int>>& out)
{
    out.clear();
    if (!rows.is_array() || static_cast<int>(rows.size()) != h)
    {
        return false;
    }
    for (const auto& row : rows)
    {
        std::vector<int> r;
        if (!row.is_array() || static_cast<int>(row.size()) != w)
        {
            return false;
        }
        for (const auto& cell : row)
        {
            r.push_back(cell.get<int>());
        }
        out.push_back(std::move(r));
    }
    return true;
}

bool parseGroundCells(const json& rows, int w, int h, std::vector<std::vector<MapCell>>& out)
{
    out.clear();
    if (!rows.is_array() || static_cast<int>(rows.size()) != h)
    {
        return false;
    }
    for (const auto& row : rows)
    {
        std::vector<MapCell> r;
        if (!row.is_array() || static_cast<int>(row.size()) != w)
        {
            return false;
        }
        for (const auto& cell : row)
        {
            MapCell mc;
            if (cell.is_null())
            {
                mc.empty = true;
            }
            else if (cell.is_object())
            {
                mc.empty = false;
                if (cell.contains("ts"))
                {
                    mc.tilesetId = cell["ts"].get<std::string>();
                }
                if (cell.contains("t"))
                {
                    mc.tileIndex = cell["t"].get<int>();
                }
            }
            else
            {
                return false;
            }
            r.push_back(std::move(mc));
        }
        out.push_back(std::move(r));
    }
    return true;
}

bool parseWildEncounterSpeciesList(const json& arr, std::vector<WildEncounterSpeciesEntry>& out)
{
    out.clear();
    if (!arr.is_array())
    {
        return false;
    }
    for (const auto& el : arr)
    {
        if (!el.is_object())
        {
            continue;
        }
        WildEncounterSpeciesEntry e;
        e.species = el.value("species", "");
        e.weight = std::max(1, intFromJson(el.contains("weight") ? el["weight"] : json(), 1));
        if (!e.species.empty())
        {
            out.push_back(std::move(e));
        }
    }
    return true;
}

bool parseWildPatches(const json& root, std::vector<WildEncounterPatch>& out)
{
    out.clear();
    if (!root.contains("wildPatches") || !root["wildPatches"].is_array())
    {
        return true;
    }
    for (const auto& wp : root["wildPatches"])
    {
        if (!wp.is_object())
        {
            continue;
        }
        WildEncounterPatch patch;
        patch.id = wp.value("id", "");
        if (patch.id.empty())
        {
            continue;
        }
        patch.stepChancePercent = std::clamp(intFromJson(wp.contains("stepChancePercent") ? wp["stepChancePercent"] : json(), 10), 0, 100);
        if (wp.contains("encounters") && wp["encounters"].is_object())
        {
            const json& enc = wp["encounters"];
            if (enc.contains("common"))
            {
                parseWildEncounterSpeciesList(enc["common"], patch.common);
            }
            if (enc.contains("uncommon"))
            {
                parseWildEncounterSpeciesList(enc["uncommon"], patch.uncommon);
            }
            if (enc.contains("rare"))
            {
                parseWildEncounterSpeciesList(enc["rare"], patch.rare);
            }
        }
        out.push_back(std::move(patch));
    }
    return true;
}

bool intGridToMapCells(
    const json& rows,
    int w,
    int h,
    const std::string& tilesetId,
    std::vector<std::vector<MapCell>>& out)
{
    std::vector<std::vector<int>> tmp;
    if (!parseIntGrid(rows, w, h, tmp))
    {
        return false;
    }
    out.clear();
    out.resize(static_cast<size_t>(h));
    for (int y = 0; y < h; ++y)
    {
        out[static_cast<size_t>(y)].resize(static_cast<size_t>(w));
        for (int x = 0; x < w; ++x)
        {
            const int v = tmp[static_cast<size_t>(y)][static_cast<size_t>(x)];
            MapCell& mc = out[static_cast<size_t>(y)][static_cast<size_t>(x)];
            if (v == 0)
            {
                mc.empty = true;
            }
            else
            {
                mc.empty = false;
                mc.tilesetId = tilesetId;
                mc.tileIndex = v;
            }
        }
    }
    return true;
}

} // namespace

bool loadTilesetRegistry(const std::string& path, std::vector<TilesetDef>& out)
{
    json root;
    if (!readJsonFile(path, root))
    {
        return false;
    }
    if (!root.contains("tilesets") || !root["tilesets"].is_array())
    {
        std::cerr << "map_data: " << path << " missing tilesets array\n";
        return false;
    }
    out.clear();
    for (const auto& el : root["tilesets"])
    {
        if (!el.is_object())
        {
            continue;
        }
        TilesetDef t;
        if (el.contains("id"))
        {
            t.id = el["id"].get<std::string>();
        }
        if (el.contains("image"))
        {
            t.imagePath = el["image"].get<std::string>();
        }
        if (el.contains("tileWidth"))
        {
            t.tileWidth = el["tileWidth"].get<int>();
        }
        if (el.contains("tileHeight"))
        {
            t.tileHeight = el["tileHeight"].get<int>();
        }
        if (el.contains("margin"))
        {
            t.margin = el["margin"].get<int>();
        }
        if (el.contains("spacing"))
        {
            t.spacing = el["spacing"].get<int>();
        }
        if (el.contains("columns"))
        {
            t.columns = el["columns"].get<int>();
        }
        if (!t.id.empty())
        {
            out.push_back(std::move(t));
        }
    }
    return !out.empty();
}

bool loadMapFromFile(const std::string& path, MapData& out)
{
    json root;
    if (!readJsonFile(path, root))
    {
        return false;
    }
    out = MapData{};
    if (root.contains("version"))
    {
        out.version = root["version"].get<int>();
    }
    if (root.contains("id"))
    {
        out.id = root["id"].get<std::string>();
    }
    if (root.contains("name"))
    {
        out.name = root["name"].get<std::string>();
    }
    if (root.contains("tilesetId"))
    {
        out.tilesetId = root["tilesetId"].get<std::string>();
    }
    if (root.contains("width"))
    {
        out.width = root["width"].get<int>();
    }
    if (root.contains("height"))
    {
        out.height = root["height"].get<int>();
    }
    if (root.contains("tileWidth"))
    {
        out.tileWidth = root["tileWidth"].get<int>();
    }
    if (root.contains("tileHeight"))
    {
        out.tileHeight = root["tileHeight"].get<int>();
    }
    if (root.contains("musicTrack"))
    {
        out.musicTrack = root["musicTrack"].get<std::string>();
    }
    if (root.contains("healPoint") && root["healPoint"].is_object())
    {
        const auto& hp = root["healPoint"];
        out.healPoint.mapId = hp.value("mapId", std::string());
        out.healPoint.x = intFromJson(hp["x"], 0);
        out.healPoint.y = intFromJson(hp["y"], 0);
    }

    if (!root.contains("layers") || !root["layers"].is_object())
    {
        std::cerr << "map_data: " << path << " missing layers\n";
        return false;
    }
    const auto& layers = root["layers"];

    const int w = out.width;
    const int h = out.height;

    if (layers.contains("tileLayers") && layers["tileLayers"].is_array())
    {
        const auto& tls = layers["tileLayers"];
        for (const auto& el : tls)
        {
            if (!el.is_object())
            {
                std::cerr << "map_data: " << path << " tileLayers entry must be object\n";
                return false;
            }
            TileLayer tl;
            if (el.contains("id"))
            {
                tl.id = el["id"].get<std::string>();
            }
            if (el.contains("applyOverPlayer"))
            {
                tl.applyOverPlayer = el["applyOverPlayer"].get<bool>();
            }
            if (!el.contains("cells") || !el["cells"].is_array())
            {
                std::cerr << "map_data: " << path << " tileLayers entry missing cells\n";
                return false;
            }
            if (!parseGroundCells(el["cells"], w, h, tl.cells))
            {
                std::cerr << "map_data: " << path << " invalid tileLayers.cells\n";
                return false;
            }
            out.tileLayers.push_back(std::move(tl));
        }
        if (out.tileLayers.empty())
        {
            std::cerr << "map_data: " << path << " tileLayers is empty\n";
            return false;
        }
    }
    else if (layers.contains("groundCells") && layers["groundCells"].is_array())
    {
        TileLayer tl;
        tl.id = "ground";
        if (!parseGroundCells(layers["groundCells"], w, h, tl.cells))
        {
            std::cerr << "map_data: " << path << " invalid layers.groundCells\n";
            return false;
        }
        out.tileLayers.push_back(std::move(tl));
    }
    else if (layers.contains("ground") && layers["ground"].is_array())
    {
        TileLayer tl;
        tl.id = "ground";
        if (!intGridToMapCells(layers["ground"], w, h, out.tilesetId, tl.cells))
        {
            std::cerr << "map_data: " << path << " invalid layers.ground\n";
            return false;
        }
        out.tileLayers.push_back(std::move(tl));
    }
    else
    {
        std::cerr << "map_data: " << path << " need layers.tileLayers or layers.ground or layers.groundCells\n";
        return false;
    }

    if (layers.contains("walkability") && layers["walkability"].is_array())
    {
        if (!parseIntGrid(layers["walkability"], w, h, out.walkabilityLayer))
        {
            std::cerr << "map_data: " << path << " invalid layers.walkability\n";
            return false;
        }
    }
    if (layers.contains("transparent") && layers["transparent"].is_array())
    {
        if (!parseIntGrid(layers["transparent"], w, h, out.transparentLayer))
        {
            std::cerr << "map_data: " << path << " invalid layers.transparent\n";
            return false;
        }
    }
    if (layers.contains("overPlayer") && layers["overPlayer"].is_array())
    {
        if (!parseIntGrid(layers["overPlayer"], w, h, out.overPlayerLayer))
        {
            std::cerr << "map_data: " << path << " invalid layers.overPlayer\n";
            return false;
        }
    }

    if (!parseWildPatches(root, out.wildPatches))
    {
        std::cerr << "map_data: " << path << " invalid wildPatches\n";
        return false;
    }
    // FEATURE-MAP-058: optional map-wide global encounter species
    if (root.contains("wildGlobalEncounters") && root["wildGlobalEncounters"].is_object())
    {
        const auto& ge = root["wildGlobalEncounters"];
        if (ge.contains("common"))
        {
            parseWildEncounterSpeciesList(ge["common"], out.globalCommon);
        }
        if (ge.contains("uncommon"))
        {
            parseWildEncounterSpeciesList(ge["uncommon"], out.globalUncommon);
        }
        if (ge.contains("rare"))
        {
            parseWildEncounterSpeciesList(ge["rare"], out.globalRare);
        }
    }
    const int maxPatchIndex = static_cast<int>(out.wildPatches.size());
    if (layers.contains("wildEncounter") && layers["wildEncounter"].is_array())
    {
        if (!parseIntGrid(layers["wildEncounter"], w, h, out.wildEncounterLayer))
        {
            std::cerr << "map_data: " << path << " invalid layers.wildEncounter\n";
            return false;
        }
        for (const auto& row : out.wildEncounterLayer)
        {
            for (int cell : row)
            {
                if (cell < 0 || cell > maxPatchIndex)
                {
                    std::cerr << "map_data: " << path << " wildEncounter cell out of range (max "
                              << maxPatchIndex << ")\n";
                    return false;
                }
            }
        }
    }

    if (root.contains("connections") && root["connections"].is_object())
    {
        for (const auto& [key, val] : root["connections"].items())
        {
            if (!val.is_object())
            {
                continue;
            }
            MapExitInfo ex;
            if (val.contains("mapId"))
            {
                ex.mapId = val["mapId"].get<std::string>();
            }
            if (val.contains("entryTileX"))
            {
                ex.entryTileX = val["entryTileX"].get<int>();
            }
            if (val.contains("entryTileY"))
            {
                ex.entryTileY = val["entryTileY"].get<int>();
            }
            out.connections[key] = ex;
        }
    }

    out.events.clear();
    if (root.contains("events") && root["events"].is_array())
    {
        for (const auto& ev : root["events"])
        {
            if (!ev.is_object())
            {
                continue;
            }
            MapEventInstance mi;
            mi.id = ev.value("id", "");
            if (mi.id.empty())
            {
                continue;
            }
            if (ev.contains("anchor") && ev["anchor"].is_object())
            {
                const json& an = ev["anchor"];
                if (an.contains("x"))
                {
                    mi.anchorX = an["x"].get<int>();
                }
                if (an.contains("y"))
                {
                    mi.anchorY = an["y"].get<int>();
                }
            }
            if (ev.contains("script") && ev["script"].is_object())
            {
                const json& sc = ev["script"];
                if (sc.contains("path") && sc["path"].is_string())
                {
                    mi.scriptPathRelative = sc["path"].get<std::string>();
                }
                else
                {
                    mi.scriptInline = sc;
                }
            }
            if (ev.contains("sprite") && ev["sprite"].is_object())
            {
                const json& sp = ev["sprite"];
                mi.hasSprite = true;
                mi.sprite.kind = sp.value("kind", "");
                mi.sprite.file = sp.value("file", "");
                mi.sprite.frame = intFromJson(sp.contains("frame") ? sp["frame"] : json(), 0);
                mi.sprite.facing = sp.value("facing", std::string());
                const std::string& sk = mi.sprite.kind;
                const bool isCharacter = (sk == "character");
                if (sp.contains("sheetColumns") && sp["sheetColumns"].is_number())
                {
                    mi.sprite.sheetColumns = std::max(1, intFromJson(sp["sheetColumns"], 1));
                }
                else
                {
                    mi.sprite.sheetColumns = isCharacter ? 4 : 1;
                }
                if (sp.contains("sheetRows") && sp["sheetRows"].is_number())
                {
                    mi.sprite.sheetRows = std::max(1, intFromJson(sp["sheetRows"], 1));
                }
                else
                {
                    mi.sprite.sheetRows = isCharacter ? 4 : 1;
                }
                const int nCells = mi.sprite.sheetColumns * mi.sprite.sheetRows;
                if (nCells > 0)
                {
                    mi.sprite.frame = std::clamp(mi.sprite.frame, 0, nCells - 1);
                }
                else
                {
                    mi.sprite.frame = 0;
                }
            }
            // FEATURE-MAP-078: trigger / run-condition / cleared flag / onComplete.
            mi.trigger = MapEventTrigger::Interact;
            if (ev.contains("trigger") && ev["trigger"].is_object())
            {
                const json& tr = ev["trigger"];
                const std::string type = tr.value("type", std::string("interact"));
                if (type == "step_on")
                {
                    mi.trigger = MapEventTrigger::StepOn;
                }
                else if (type == "on_map_enter")
                {
                    mi.trigger = MapEventTrigger::OnMapEnter;
                }
                else if (type == "on_condition")
                {
                    mi.trigger = MapEventTrigger::OnCondition;
                }
                if (tr.contains("condition") && tr["condition"].is_object())
                {
                    const json& cond = tr["condition"];
                    mi.conditionFlag = cond.value("flag", std::string());
                    mi.conditionWantSet = cond.value("set", true);
                }
            }
            mi.clearedFlag = ev.value("clearedFlag", std::string());
            if (mi.clearedFlag.empty())
            {
                mi.clearedFlag = mi.id + "_cleared";
            }
            if (ev.contains("onComplete") && ev["onComplete"].is_object())
            {
                const json& oc = ev["onComplete"];
                if (oc.contains("setFlags") && oc["setFlags"].is_array())
                {
                    for (const auto& f : oc["setFlags"])
                    {
                        if (f.is_string())
                        {
                            mi.onCompleteSetFlags.push_back(f.get<std::string>());
                        }
                    }
                }
                if (oc.contains("clearFlags") && oc["clearFlags"].is_array())
                {
                    for (const auto& f : oc["clearFlags"])
                    {
                        if (f.is_string())
                        {
                            mi.onCompleteClearFlags.push_back(f.get<std::string>());
                        }
                    }
                }
            }
            out.events.push_back(std::move(mi));
        }
    }

    if (out.id.empty() || out.width < 1 || out.height < 1)
    {
        std::cerr << "map_data: invalid map dimensions or id in " << path << '\n';
        return false;
    }
    return true;
}

json loadEventScriptJson(const std::string& mapJsonPath, const MapEventInstance& ev)
{
    if (!ev.scriptPathRelative.empty())
    {
        namespace fs = std::filesystem;
        const fs::path base(mapJsonPath);
        const fs::path scriptFile = base.parent_path() / ev.scriptPathRelative;
        json root;
        if (readJsonFile(scriptFile.string(), root))
        {
            return root;
        }
        std::cerr << "map_data: event script not found: " << scriptFile << '\n';
    }
    if (ev.scriptInline.is_object())
    {
        return ev.scriptInline;
    }
    return json::object({{"version", 1}, {"actions", json::array()}});
}

bool loadMapById(const std::string& mapsDirectory, const std::string& mapId, MapData& out)
{
    std::string path = mapsDirectory;
    if (!path.empty() && path.back() != '/')
    {
        path += '/';
    }
    path += mapId + ".json";
    return loadMapFromFile(path, out);
}

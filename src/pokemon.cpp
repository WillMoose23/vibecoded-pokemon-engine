#include "game.h"

#include <cctype>
#include <iostream>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>

namespace
{

const std::unordered_map<std::string, Type>& typeStringMap()
{
    static const std::unordered_map<std::string, Type> map = {
        {"normal", Type::Normal},
        {"fire", Type::Fire},
        {"water", Type::Water},
        {"electric", Type::Electric},
        {"grass", Type::Grass},
        {"ice", Type::Ice},
        {"fighting", Type::Fighting},
        {"poison", Type::Poison},
        {"ground", Type::Ground},
        {"flying", Type::Flying},
        {"psychic", Type::Psychic},
        {"bug", Type::Bug},
        {"rock", Type::Rock},
        {"ghost", Type::Ghost},
        {"dragon", Type::Dragon},
        {"dark", Type::Dark},
        {"steel", Type::Steel},
        {"fairy", Type::Fairy},
    };
    return map;
}

void toLowerAsciiInPlace(std::string& s)
{
    for (char& c : s)
    {
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    }
}

std::optional<Type> parseTypeString(std::string_view sv)
{
    std::string key{sv};
    toLowerAsciiInPlace(key);
    const auto& m = typeStringMap();
    const auto it = m.find(key);
    if (it == m.end())
    {
        return std::nullopt;
    }
    return it->second;
}

std::optional<MoveCategory> parseMoveCategory(std::string_view sv)
{
    std::string key{sv};
    toLowerAsciiInPlace(key);
    if (key == "physical")
    {
        return MoveCategory::Physical;
    }
    if (key == "special")
    {
        return MoveCategory::Special;
    }
    if (key == "status")
    {
        return MoveCategory::Status;
    }
    return std::nullopt;
}

std::optional<MoveTemplate> parseMoveFromCatalogEntry(const std::string& moveId, const nlohmann::json& entry)
{
    try
    {
        const std::string name = entry.at("name").get<std::string>();
        const std::optional<Type> mt = parseTypeString(entry.at("type").get<std::string>());
        if (!mt.has_value())
        {
            std::cerr << "Move \"" << moveId << "\": unknown type string\n";
            return std::nullopt;
        }
        const std::optional<MoveCategory> cat = parseMoveCategory(entry.at("category").get<std::string>());
        if (!cat.has_value())
        {
            std::cerr << "Move \"" << moveId << "\": unknown category (use physical, special, status)\n";
            return std::nullopt;
        }
        MoveTemplate m{};
        m.id = moveId;
        m.name = name;
        m.moveType = *mt;
        m.category = *cat;
        m.power = entry.value("power", 0);
        if (entry.contains("accuracy") && !entry["accuracy"].is_null())
        {
            m.accuracy = entry["accuracy"].get<int>();
        }
        else
        {
            m.accuracy = -1;
        }

        m.pp = entry.value("pp", 0);
        return m;
    }
    catch (const nlohmann::json::exception& e)
    {
        std::cerr << "Move \"" << moveId << "\" catalog entry invalid: " << e.what() << '\n';
        return std::nullopt;
    }
}

} // namespace

Pokemon::Pokemon(json& data, const std::string& speciesKey, const std::string& formKey)
{
    blankPoke();
    try
    {
        const auto& species = data.at(kPokemonDbKey).at(speciesKey);

        iv.hp = random(0, 31);
        iv.atk = random(0, 31);
        iv.def = random(0, 31);
        iv.spAtk = random(0, 31);
        iv.spDef = random(0, 31);
        iv.spd = random(0, 31);

        loadFromSpecies(species, speciesKey, formKey);

        const nlohmann::json* typeArray = nullptr;
        if (!formKey.empty() && species.contains(formKey) && species.at(formKey).is_object())
        {
            const auto& form = species.at(formKey);
            if (form.contains("type") && form["type"].is_array())
            {
                typeArray = &form["type"];
            }
        }
        if (typeArray == nullptr && species.contains("type") && species["type"].is_array())
        {
            typeArray = &species["type"];
        }
        if (typeArray != nullptr)
        {
            setTypeValues(*typeArray, speciesKey);
        }
        else
        {
            std::cerr << "Pokemon \"" << speciesKey << "\": missing or invalid \"type\" array\n";
        }

        loadMoves(data, species, speciesKey);
    }
    catch (const nlohmann::json::exception& e)
    {
        std::cerr << "Failed to load Pokemon \"" << speciesKey << "\": " << e.what() << '\n';
        blankPoke();
    }
}

Pokemon::~Pokemon() {}

void Pokemon::blankPoke()
{
    iv = {};
    baseStats = {};
    types.clear();
    moves_.clear();
    spriteFrontPath_.clear();
    spriteBackPath_.clear();
}

void Pokemon::loadFromSpecies(
    const nlohmann::json& species, const std::string& /*speciesKey*/, const std::string& formKey)
{
    // JSON uses spa/spd/spe; map to spAtk/spDef/spd in PokemonStats (see comment in setBaseStats call path).
    const auto& bs = species.at("baseStats");
    baseStats.hp = bs.value("hp", 0);
    baseStats.atk = bs.value("atk", 0);
    baseStats.def = bs.value("def", 0);
    baseStats.spAtk = bs.value("spa", 0);
    baseStats.spDef = bs.value("spd", 0);
    baseStats.spd = bs.value("spe", 0);

    const nlohmann::json* form = nullptr;
    if (!formKey.empty() && species.contains(formKey) && species.at(formKey).is_object())
    {
        form = &species.at(formKey);
    }

    if (form != nullptr)
    {
        if (form->contains("spriteFront"))
        {
            spriteFrontPath_ = form->value("spriteFront", "");
        }
        else
        {
            spriteFrontPath_ = species.value("spriteFront", "");
        }
        if (form->contains("spriteBack"))
        {
            spriteBackPath_ = form->value("spriteBack", "");
        }
        else
        {
            spriteBackPath_ = species.value("spriteBack", "");
        }
    }
    else
    {
        spriteFrontPath_ = species.value("spriteFront", "");
        spriteBackPath_ = species.value("spriteBack", "");
    }
}

void Pokemon::loadMoves(const nlohmann::json& root, const nlohmann::json& species, const std::string& speciesKey)
{
    moves_.clear();
    if (!root.contains(kMoveCatalogKey) || !root[kMoveCatalogKey].is_object())
    {
        return;
    }
    if (!species.contains("moves") || !species["moves"].is_array())
    {
        return;
    }

    const auto& catalog = root.at(kMoveCatalogKey);
    for (const auto& el : species["moves"])
    {
        if (!el.is_string())
        {
            std::cerr << "Pokemon \"" << speciesKey << "\": skipping non-string move id\n";
            continue;
        }
        const std::string moveId = el.get<std::string>();
        if (!catalog.contains(moveId))
        {
            std::cerr << "Pokemon \"" << speciesKey << "\": unknown move id \"" << moveId << "\"\n";
            continue;
        }
        const std::optional<MoveTemplate> parsed = parseMoveFromCatalogEntry(moveId, catalog[moveId]);
        if (parsed.has_value())
        {
            moves_.push_back(*parsed);
        }
    }
}

void Pokemon::setTypeValues(const nlohmann::json& typeArray, const std::string& speciesKey)
{
    types.clear();
    if (!typeArray.is_array())
    {
        std::cerr << "Pokemon \"" << speciesKey << "\": type is not an array\n";
        return;
    }

    for (const auto& el : typeArray)
    {
        if (!el.is_string())
        {
            std::cerr << "Pokemon \"" << speciesKey << "\": skipping non-string type entry\n";
            continue;
        }
        const std::optional<Type> parsed = parseTypeString(el.get<std::string>());
        if (parsed.has_value())
        {
            types.push_back(*parsed);
        }
        else
        {
            std::cerr << "Pokemon \"" << speciesKey << "\": unknown type \"" << el.get<std::string>()
                      << "\"\n";
        }
    }
}

const PokemonStats& Pokemon::ivs() const
{
    return iv;
}

const PokemonStats& Pokemon::bases() const
{
    return baseStats;
}

const std::vector<Type>& Pokemon::getTypes() const
{
    return types;
}

const std::vector<MoveTemplate>& Pokemon::moves() const
{
    return moves_;
}

const std::string& Pokemon::frontSpritePath() const
{
    return spriteFrontPath_;
}

const std::string& Pokemon::backSpritePath() const
{
    return spriteBackPath_;
}

void Pokemon::setFrontSpritePath(std::string path)
{
    spriteFrontPath_ = std::move(path);
}

void Pokemon::setBackSpritePath(std::string path)
{
    spriteBackPath_ = std::move(path);
}

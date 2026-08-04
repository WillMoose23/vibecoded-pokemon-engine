// FEATURE-MAP-050/058: wild encounter tier/species rolls (see docs/tracker.md).

#include "wild_encounter.h"
#include "game.h"

#include <algorithm>
#include <iostream>
#include <unordered_set>

int random(int min, int max);

namespace
{

enum class WildTier
{
    Common,
    Uncommon,
    Rare
};

WildTier rollWildTier()
{
    const int r = random(1, 100);
    if (r <= 65)
    {
        return WildTier::Common;
    }
    if (r <= 95)
    {
        return WildTier::Uncommon;
    }
    return WildTier::Rare;
}

const std::vector<WildEncounterSpeciesEntry>* tierEntries(const WildEncounterPatch& patch, WildTier tier)
{
    switch (tier)
    {
    case WildTier::Common:
        return &patch.common;
    case WildTier::Uncommon:
        return &patch.uncommon;
    case WildTier::Rare:
        return &patch.rare;
    }
    return &patch.common;
}

const std::vector<WildEncounterSpeciesEntry>* globalTierEntries(const MapData& mapData, WildTier tier)
{
    switch (tier)
    {
    case WildTier::Common:
        return &mapData.globalCommon;
    case WildTier::Uncommon:
        return &mapData.globalUncommon;
    case WildTier::Rare:
        return &mapData.globalRare;
    }
    return &mapData.globalCommon;
}

/// Merge local + global entries; local wins for any species that appears in both tiers.
std::vector<WildEncounterSpeciesEntry> mergeTierEntries(
    const std::vector<WildEncounterSpeciesEntry>& local,
    const std::vector<WildEncounterSpeciesEntry>& global)
{
    std::vector<WildEncounterSpeciesEntry> merged = local;
    std::unordered_set<std::string> localNames;
    for (const WildEncounterSpeciesEntry& e : local)
    {
        localNames.insert(e.species);
    }
    for (const WildEncounterSpeciesEntry& e : global)
    {
        if (localNames.find(e.species) == localNames.end())
        {
            merged.push_back(e);
        }
    }
    return merged;
}

std::optional<std::string> pickWeightedSpecies(
    const std::vector<WildEncounterSpeciesEntry>& entries, const nlohmann::json& pokedb)
{
    if (entries.empty() || !pokedb.contains(kPokemonDbKey) || !pokedb[kPokemonDbKey].is_object())
    {
        return std::nullopt;
    }
    const auto& pokemon = pokedb[kPokemonDbKey];
    int total = 0;
    for (const WildEncounterSpeciesEntry& e : entries)
    {
        if (e.weight > 0 && pokemon.contains(e.species))
        {
            total += e.weight;
        }
    }
    if (total <= 0)
    {
        return std::nullopt;
    }
    int roll = random(1, total);
    for (const WildEncounterSpeciesEntry& e : entries)
    {
        if (e.weight <= 0 || !pokemon.contains(e.species))
        {
            continue;
        }
        roll -= e.weight;
        if (roll <= 0)
        {
            return e.species;
        }
    }
    return std::nullopt;
}

} // namespace

std::optional<std::string> rollWildEncounterSpecies(
    const WildEncounterPatch& patch, const MapData& mapData, const nlohmann::json& pokedb)
{
    const int stepChance = std::clamp(patch.stepChancePercent, 0, 100);
    if (stepChance <= 0)
    {
        return std::nullopt;
    }
    if (random(1, 100) > stepChance)
    {
        return std::nullopt;
    }
    const WildTier tier = rollWildTier();
    const std::vector<WildEncounterSpeciesEntry>* localEntries = tierEntries(patch, tier);
    const std::vector<WildEncounterSpeciesEntry>* globalEntries = globalTierEntries(mapData, tier);

    // Merge global species into the local tier pool; local entries win on duplicate species.
    const std::vector<WildEncounterSpeciesEntry> merged = mergeTierEntries(
        localEntries ? *localEntries : std::vector<WildEncounterSpeciesEntry>{},
        globalEntries ? *globalEntries : std::vector<WildEncounterSpeciesEntry>{});

    if (merged.empty())
    {
        static bool warned = false;
        if (!warned)
        {
            std::cerr << "wild_encounter: empty tier table for patch " << patch.id << '\n';
            warned = true;
        }
        return std::nullopt;
    }
    return pickWeightedSpecies(merged, pokedb);
}

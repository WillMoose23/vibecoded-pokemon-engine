#ifndef WILD_ENCOUNTER_H
#define WILD_ENCOUNTER_H

#include "map_data.h"

#include <json.hpp>
#include <optional>
#include <string>

/// FEATURE-MAP-050/058: roll step chance, tier (65/30/5), then weighted species within tier.
/// Global species from mapData (FEATURE-MAP-058) are merged into the tier pool; local patch entries win
/// on duplicate species. Returns species key when all rolls succeed and species exists in pokedb.
std::optional<std::string> rollWildEncounterSpecies(
    const WildEncounterPatch& patch, const MapData& mapData, const nlohmann::json& pokedb);

#endif

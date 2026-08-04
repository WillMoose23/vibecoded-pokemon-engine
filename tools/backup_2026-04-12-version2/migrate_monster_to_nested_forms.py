#!/usr/bin/env python3
"""
Flattened monster.json -> one top-level key per species, nested alternateForme* objects.
Sort Pokemon keys by pokedexNum ascending.

Run: python3 tools/migrate_monster_to_nested_forms.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONSTER_PATH = os.path.join(ROOT, "src", "monster.json")

FORM_ONE = "alternateFormeOne"
FORM_TWO = "alternateFormeTwo"
FORM_SHADOW = "alternateFormeShadow"


def parse_flat_key(key: str) -> Tuple[str, str, Optional[int]]:
    """Return (canonical_species_key, variant_kind, numeric_suffix or None).
    variant_kind: 'base' | 'female' | 'male' | 'shadow' | 'numeric'
    """
    if key.endswith("_Female"):
        return key[: -len("_Female")], "female", None
    if key.endswith("_Male"):
        return key[: -len("_Male")], "male", None
    if key.endswith("_Shadow"):
        return key[: -len("_Shadow")], "shadow", None
    m = re.match(r"^(.+)_(\d+)$", key)
    if m:
        return m.group(1), "numeric", int(m.group(2))
    return key, "base", None


def strip_sprite_fields(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Gender forms: sprites only (stats/types inherited from base)."""
    out: Dict[str, Any] = {}
    for k in ("spriteFront", "spriteBack"):
        if k in entry:
            out[k] = entry[k]
    return out


def strip_numeric_form_fields(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Numbered forms: sprites and optional type override."""
    out: Dict[str, Any] = {}
    for k in ("spriteFront", "spriteBack", "type"):
        if k in entry:
            out[k] = entry[k]
    return out


def full_entry_copy(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pokedexNum": entry.get("pokedexNum", 0),
        "spriteFront": entry.get("spriteFront", ""),
        "spriteBack": entry.get("spriteBack", ""),
        "type": entry.get("type", []),
        "baseStats": entry.get("baseStats", {}),
        "moves": entry.get("moves", []),
    }


def choose_base_flat_key(
    canonical: str, members: Dict[str, Tuple[str, Optional[int], Dict[str, Any]]]
) -> Tuple[str, bool]:
    """Returns (flat_key_for_base, promoted_non_base)."""
    base_kind_keys = [fk for fk, (vk, _, _) in members.items() if vk == "base"]
    if canonical in members and members[canonical][0] == "base":
        return canonical, False
    if base_kind_keys:
        base_kind_keys.sort()
        return base_kind_keys[0], False

    female_only = [fk for fk, (vk, _, _) in members.items() if vk == "female"]
    male_only = [fk for fk, (vk, _, _) in members.items() if vk == "male"]
    numeric_only = [(fk, members[fk][1] or 0) for fk, (vk, n, _) in members.items() if vk == "numeric"]

    if not numeric_only and len(female_only) == len(members):
        print(f"warn: {canonical}: no base key; promoting {female_only[0]} to base", file=sys.stderr)
        return female_only[0], True

    if not female_only and not male_only and numeric_only:
        numeric_only.sort(key=lambda x: x[1])
        print(
            f"warn: {canonical}: no base key; promoting {numeric_only[0][0]} (lowest suffix) to base",
            file=sys.stderr,
        )
        return numeric_only[0][0], True

    if numeric_only:
        numeric_only.sort(key=lambda x: x[1])
        print(f"warn: {canonical}: no base key; using {numeric_only[0][0]} as base", file=sys.stderr)
        return numeric_only[0][0], False

    if female_only:
        print(f"warn: {canonical}: no base key; promoting {female_only[0]} to base", file=sys.stderr)
        return female_only[0], True

    # Fallback: any member
    fk0 = sorted(members.keys())[0]
    print(f"warn: {canonical}: ambiguous base; using {fk0}", file=sys.stderr)
    return fk0, False


def merge_group(canonical: str, members: Dict[str, Tuple[str, Optional[int], Dict[str, Any]]]) -> Dict[str, Any]:
    base_flat, promoted = choose_base_flat_key(canonical, members)
    _, _, base_entry = members[base_flat]
    merged = full_entry_copy(base_entry)

    for flat_k, (vk, num, ent) in members.items():
        if flat_k == base_flat and promoted:
            # Base row was promoted from a variant; do not also nest it as a form.
            continue
        if flat_k == base_flat:
            continue
        if vk == "female":
            merged[FORM_ONE] = strip_sprite_fields(ent)
        elif vk == "male":
            merged[FORM_TWO] = strip_sprite_fields(ent)
        elif vk == "shadow":
            merged[FORM_SHADOW] = strip_sprite_fields(ent)
        elif vk == "numeric" and num is not None:
            merged[f"alternateForme{num}"] = strip_numeric_form_fields(ent)

    return merged


def main() -> None:
    with open(MONSTER_PATH, "r", encoding="utf-8") as f:
        root = json.load(f)

    move_catalog = root.get("MoveCatalog", {})
    flat_pk: Dict[str, Any] = root.get("Pokemon", {})

    groups: Dict[str, Dict[str, Tuple[str, Optional[int], Dict[str, Any]]]] = defaultdict(dict)

    for flat_key, entry in flat_pk.items():
        canonical, vk, num = parse_flat_key(flat_key)
        groups[canonical][flat_key] = (vk, num, dict(entry))

    merged_list: List[Tuple[int, str, Dict[str, Any]]] = []
    for canonical, members in groups.items():
        merged = merge_group(canonical, members)
        dex = int(merged.get("pokedexNum", 0))
        merged_list.append((dex, canonical, merged))

    merged_list.sort(key=lambda x: (x[0], x[1].lower()))

    new_pokemon: Dict[str, Any] = {}
    for _, canonical, merged in merged_list:
        new_pokemon[canonical] = merged

    root["MoveCatalog"] = move_catalog
    root["Pokemon"] = new_pokemon

    with open(MONSTER_PATH, "w", encoding="utf-8") as f:
        json.dump(root, f, indent=2)
        f.write("\n")

    print(f"Wrote {len(new_pokemon)} species (from {len(flat_pk)} flat keys) to {MONSTER_PATH}")


if __name__ == "__main__":
    main()

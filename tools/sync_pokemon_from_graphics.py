#!/usr/bin/env python3
"""
Scan src/Graphics/Pokemon/Front and Back for paired PNGs, fetch typings + stats from
PokeAPI (cached in tools/.pokeapi_cache.json), and rewrite the "Pokemon" section of
src/monster.json as nested species (one JSON key per species, alternateForme* for
variants) while preserving MoveCatalog.

Uses a thread pool for parallel fetches; responses are cached. First run needs network.

Usage: python3 tools/sync_pokemon_from_graphics.py
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import threading
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONT = os.path.join(ROOT, "src", "Graphics", "Pokemon", "Front")
BACK = os.path.join(ROOT, "src", "Graphics", "Pokemon", "Back")
MONSTER_PATH = os.path.join(ROOT, "src", "monster.json")
CACHE_PATH = os.path.join(ROOT, "tools", ".pokeapi_cache.json")

DEFAULT_MOVES = ["tackle", "growl"]
CTX = ssl.create_default_context()
CACHE_LOCK = threading.Lock()

FORM_ONE = "alternateFormeOne"
FORM_TWO = "alternateFormeTwo"
FORM_SHADOW = "alternateFormeShadow"


def stem_to_json_key(stem: str) -> str:
    base, _ = os.path.splitext(stem)

    def cap(p: str) -> str:
        if not p:
            return p
        return p[:1].upper() + p[1:].lower() if len(p) > 1 else p.upper()

    parts = base.split("_")
    return "_".join(cap(p) for p in parts)


def parse_stem_variant(stem: str) -> Tuple[str, str, Optional[int]]:
    """Return (canonical species JSON key, variant_kind, numeric suffix or None)."""
    base, _ = os.path.splitext(stem)
    lb = base.lower()
    if lb.endswith("_female"):
        cstem = base[: -len("_female")]
        return stem_to_json_key(cstem + ".png"), "female", None
    if lb.endswith("_male"):
        cstem = base[: -len("_male")]
        return stem_to_json_key(cstem + ".png"), "male", None
    if lb.endswith("_shadow"):
        cstem = base[: -len("_shadow")]
        return stem_to_json_key(cstem + ".png"), "shadow", None
    m = re.match(r"^(.+)_(\d+)$", base, re.IGNORECASE)
    if m:
        prefix = m.group(1)
        return stem_to_json_key(prefix + ".png"), "numeric", int(m.group(2))
    return stem_to_json_key(stem), "base", None


def stem_to_api_candidates(stem: str) -> List[str]:
    base, _ = os.path.splitext(stem)
    if base == "000":
        return []
    out: List[str] = []
    gender_suffix = ""
    if base.lower().endswith("_female"):
        base = base[: -len("_female")]
        gender_suffix = "-female"
    elif base.lower().endswith("_male"):
        base = base[: -len("_male")]
        gender_suffix = "-male"
    elif base.lower().endswith("_shadow"):
        base = base[: -len("_shadow")]

    parts = base.split("_")
    if len(parts) >= 2 and parts[0].upper() == "ARCEUS" and parts[1].isdigit():
        base = "ARCEUS"
        parts = ["ARCEUS"]

    name = "-".join(p.lower() for p in parts)
    if gender_suffix:
        name = name + gender_suffix
    out.append(name)
    if gender_suffix:
        out.append("-".join(p.lower() for p in parts))
    if len(parts) >= 2 and parts[0].upper() == "ARCEUS" and parts[1].isdigit():
        out.append("arceus")
    out.append("-".join(p.lower() for p in parts))
    seen = set()
    uniq: List[str] = []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def load_cache() -> Dict[str, Any]:
    if not os.path.isfile(CACHE_PATH):
        return {}
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cache(c: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=0)


def fetch_pokemon(api_name: str, cache: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with CACHE_LOCK:
        if api_name in cache:
            hit = cache[api_name]
            if isinstance(hit, dict):
                return hit
            return None
    url = f"https://pokeapi.co/api/v2/pokemon/{api_name}"
    req = urllib.request.Request(url, headers={"User-Agent": "pokemon-rpg-sync/1.0"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            data = None
        else:
            raise
    except Exception:
        data = None
    with CACHE_LOCK:
        if data is not None:
            cache[api_name] = data
        else:
            cache[api_name] = "__404__"
    return data


def resolve_stem(stem: str, cache: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    for cand in stem_to_api_candidates(stem):
        if not cand:
            continue
        data = fetch_pokemon(cand, cache)
        if data:
            return data, cand
    return None, None


def types_from_api(data: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for t in sorted(data.get("types", []), key=lambda x: x.get("slot", 0)):
        name = t.get("type", {}).get("name")
        if name:
            out.append(name)
    return out


def stats_from_api(data: Dict[str, Any]) -> Dict[str, int]:
    mapping = {
        "hp": "hp",
        "attack": "atk",
        "defense": "def",
        "special-attack": "spa",
        "special-defense": "spd",
        "speed": "spe",
    }
    by_stat: Dict[str, int] = {}
    for s in data.get("stats", []):
        sn = s.get("stat", {}).get("name")
        if sn in mapping:
            by_stat[mapping[sn]] = int(s.get("base_stat", 0))
    return {
        "hp": by_stat.get("hp", 50),
        "atk": by_stat.get("atk", 50),
        "def": by_stat.get("def", 50),
        "spa": by_stat.get("spa", 50),
        "spd": by_stat.get("spd", 50),
        "spe": by_stat.get("spe", 50),
    }


def placeholder_entry(stem: str) -> Dict[str, Any]:
    return {
        "pokedexNum": 0,
        "spriteFront": f"src/Graphics/Pokemon/Front/{stem}",
        "spriteBack": f"src/Graphics/Pokemon/Back/{stem}",
        "type": ["normal"],
        "baseStats": {
            "hp": 50,
            "atk": 50,
            "def": 50,
            "spa": 50,
            "spd": 50,
            "spe": 50,
        },
        "moves": list(DEFAULT_MOVES),
    }


def entry_from_api(stem: str, data: Dict[str, Any]) -> Dict[str, Any]:
    dex = int(data.get("id", 0))
    return {
        "pokedexNum": dex,
        "spriteFront": f"src/Graphics/Pokemon/Front/{stem}",
        "spriteBack": f"src/Graphics/Pokemon/Back/{stem}",
        "type": types_from_api(data),
        "baseStats": stats_from_api(data),
        "moves": list(DEFAULT_MOVES),
    }


def full_entry_copy(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pokedexNum": entry.get("pokedexNum", 0),
        "spriteFront": entry.get("spriteFront", ""),
        "spriteBack": entry.get("spriteBack", ""),
        "type": entry.get("type", []),
        "baseStats": entry.get("baseStats", {}),
        "moves": entry.get("moves", []),
    }


def strip_sprite_fields(entry: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in ("spriteFront", "spriteBack"):
        if k in entry:
            out[k] = entry[k]
    return out


def strip_numeric_form_fields(entry: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in ("spriteFront", "spriteBack", "type"):
        if k in entry:
            out[k] = entry[k]
    return out


def choose_base_stem(
    canonical: str, members: Dict[str, Tuple[str, Optional[int], Dict[str, Any]]]
) -> Tuple[str, bool]:
    base_stems = [s for s, (vk, _, _) in members.items() if vk == "base"]
    if base_stems:
        base_stems.sort()
        return base_stems[0], False

    female_stems = [s for s, (vk, _, _) in members.items() if vk == "female"]
    male_stems = [s for s, (vk, _, _) in members.items() if vk == "male"]
    numeric_stems = [(s, members[s][1] or 0) for s, (vk, n, _) in members.items() if vk == "numeric"]

    if not numeric_stems and len(female_stems) == len(members):
        print(f"warn: {canonical}: no base sprite; promoting {female_stems[0]}", file=sys.stderr)
        return female_stems[0], True

    if not female_stems and not male_stems and numeric_stems:
        numeric_stems.sort(key=lambda x: x[1])
        print(
            f"warn: {canonical}: no base sprite; promoting {numeric_stems[0][0]} (lowest suffix)",
            file=sys.stderr,
        )
        return numeric_stems[0][0], True

    if numeric_stems:
        numeric_stems.sort(key=lambda x: x[1])
        print(f"warn: {canonical}: no base sprite; using {numeric_stems[0][0]} as base", file=sys.stderr)
        return numeric_stems[0][0], False

    if female_stems:
        print(f"warn: {canonical}: no base sprite; promoting {female_stems[0]}", file=sys.stderr)
        return female_stems[0], True

    fk0 = sorted(members.keys())[0]
    print(f"warn: {canonical}: ambiguous base; using {fk0}", file=sys.stderr)
    return fk0, False


def merge_group(canonical: str, members: Dict[str, Tuple[str, Optional[int], Dict[str, Any]]]) -> Dict[str, Any]:
    base_stem, promoted = choose_base_stem(canonical, members)
    _, _, base_entry = members[base_stem]
    merged = full_entry_copy(base_entry)

    for stem, (vk, num, ent) in members.items():
        if stem == base_stem and promoted:
            continue
        if stem == base_stem:
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
    if not os.path.isdir(FRONT) or not os.path.isdir(BACK):
        print("Missing Front/Back directories:", FRONT, BACK)
        return

    with open(MONSTER_PATH, "r", encoding="utf-8") as f:
        root = json.load(f)

    move_catalog = root.get("MoveCatalog", {})

    front_files = {f for f in os.listdir(FRONT) if f.lower().endswith(".png")}
    back_files = {f for f in os.listdir(BACK) if f.lower().endswith(".png")}
    paired = sorted(front_files & back_files)

    cache = load_cache()
    missing: List[str] = []

    stems_work: List[str] = []
    for stem in paired:
        if stem.upper().startswith("000."):
            continue
        stems_work.append(stem)

    stem_flat: Dict[str, Dict[str, Any]] = {}

    def job(stem: str) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
        data, used = resolve_stem(stem, cache)
        return stem, data, used

    max_workers = min(12, max(4, len(stems_work) // 20 or 4))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(job, s) for s in stems_work]
        for fut in as_completed(futs):
            stem, data, used = fut.result()
            if not data:
                missing.append(stem)
                stem_flat[stem] = placeholder_entry(stem)
            else:
                stem_flat[stem] = entry_from_api(stem, data)

    save_cache(cache)

    groups: Dict[str, Dict[str, Tuple[str, Optional[int], Dict[str, Any]]]] = defaultdict(dict)
    for stem, flat in stem_flat.items():
        canonical, vk, num = parse_stem_variant(stem)
        groups[canonical][stem] = (vk, num, flat)

    merged_list: List[Tuple[int, str, Dict[str, Any]]] = []
    for canonical, members in groups.items():
        merged = merge_group(canonical, members)
        dex = int(merged.get("pokedexNum", 0))
        merged_list.append((dex, canonical, merged))

    merged_list.sort(key=lambda x: (x[0], x[1].lower()))
    pokemon_out: Dict[str, Any] = {canonical: m for _, canonical, m in merged_list}

    root["MoveCatalog"] = move_catalog
    root["Pokemon"] = pokemon_out

    with open(MONSTER_PATH, "w", encoding="utf-8") as f:
        json.dump(root, f, indent=2)
        f.write("\n")

    print(f"Wrote {len(pokemon_out)} species (nested) to {MONSTER_PATH}")
    if missing:
        print(f"PokeAPI miss (placeholder normal): {len(missing)}")
        print("Examples:", missing[:20])


if __name__ == "__main__":
    main()

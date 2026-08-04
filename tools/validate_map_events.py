#!/usr/bin/env python3
"""FEATURE-MAP-030 / FEATURE-MAP-043 / FEATURE-MAP-050: validate map JSON events[] and wild encounter patches."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPS_DIR = ROOT / "src" / "maps"
MONSTER_JSON = ROOT / "src" / "monster.json"
SKIP_NAMES = frozenset({"maps_index.json", "world_layout.json"})
EVENT_FOOTPRINT = 2
WILD_TIERS = ("common", "uncommon", "rare")
_POKEMON_KEYS: set[str] | None = None


def _pokemon_keys() -> set[str]:
    global _POKEMON_KEYS
    if _POKEMON_KEYS is not None:
        return _POKEMON_KEYS
    keys: set[str] = set()
    if MONSTER_JSON.is_file():
        try:
            with open(MONSTER_JSON, encoding="utf-8") as f:
                data = json.load(f)
            pk = data.get("Pokemon") if isinstance(data, dict) else None
            if isinstance(pk, dict):
                keys = {str(k) for k in pk.keys()}
        except (OSError, json.JSONDecodeError, TypeError):
            keys = set()
    _POKEMON_KEYS = keys
    return keys


def _validate_wild_patches(
    path: Path, m: dict, w: int, h: int, errs: list[str], warns: list[str]
) -> None:
    """FEATURE-MAP-050: wildPatches[] and layers.wildEncounter grid."""
    layers = m.get("layers")
    if not isinstance(layers, dict):
        return
    raw_wp = m.get("wildPatches")
    patches: list[dict] = []
    if raw_wp is not None:
        if not isinstance(raw_wp, list):
            errs.append(f"{path.name}: wildPatches must be an array")
            return
        for i, p in enumerate(raw_wp):
            if not isinstance(p, dict):
                errs.append(f"{path.name}: wildPatches[{i}] not an object")
                continue
            patches.append(p)
    max_idx = len(patches)
    pk = _pokemon_keys()
    for i, p in enumerate(patches):
        pid = str(p.get("id", "")).strip() or f"#{i}"
        try:
            step = int(p.get("stepChancePercent", -1))
        except (TypeError, ValueError):
            errs.append(f"{path.name} wild patch {pid}: stepChancePercent invalid")
            continue
        if step < 0 or step > 100:
            errs.append(f"{path.name} wild patch {pid}: stepChancePercent must be 0–100")
        enc = p.get("encounters")
        if not isinstance(enc, dict):
            errs.append(f"{path.name} wild patch {pid}: encounters must be an object")
            continue
        has_any_row = False
        for tier in WILD_TIERS:
            rows = enc.get(tier)
            if rows is None:
                continue
            if not isinstance(rows, list):
                errs.append(f"{path.name} wild patch {pid}: encounters.{tier} must be an array")
                continue
            if not rows:
                continue
            has_any_row = True
            for j, row in enumerate(rows):
                if not isinstance(row, dict):
                    errs.append(f"{path.name} wild patch {pid}: {tier}[{j}] not an object")
                    continue
                sp = str(row.get("species", "")).strip()
                if not sp:
                    errs.append(f"{path.name} wild patch {pid}: {tier}[{j}] missing species")
                elif pk and sp not in pk:
                    errs.append(
                        f"{path.name} wild patch {pid}: unknown species {sp!r} in {tier}[{j}]"
                    )
                try:
                    wt = int(row.get("weight", 0))
                except (TypeError, ValueError):
                    errs.append(f"{path.name} wild patch {pid}: {tier}[{j}] weight invalid")
                    continue
                if wt <= 0:
                    errs.append(f"{path.name} wild patch {pid}: {tier}[{j}] weight must be > 0")
        if not has_any_row:
            errs.append(f"{path.name} wild patch {pid}: no encounter rows in any tier")
    we = layers.get("wildEncounter")
    if we is None:
        return
    if not isinstance(we, list):
        errs.append(f"{path.name}: layers.wildEncounter must be an array")
        return
    if w > 0 and h > 0:
        if len(we) != h:
            errs.append(f"{path.name}: wildEncounter height {len(we)} != map height {h}")
        for y, row in enumerate(we):
            if not isinstance(row, list):
                errs.append(f"{path.name}: wildEncounter row {y} not an array")
                continue
            if len(row) != w:
                errs.append(f"{path.name}: wildEncounter row {y} width {len(row)} != map width {w}")
            for x, v in enumerate(row):
                try:
                    vi = int(v)
                except (TypeError, ValueError):
                    errs.append(f"{path.name}: wildEncounter[{y}][{x}] not an integer")
                    continue
                if vi < 0 or vi > max_idx:
                    errs.append(
                        f"{path.name}: wildEncounter[{y}][{x}]={vi} out of range [0,{max_idx}]"
                    )
    tile_counts = [0] * max_idx if max_idx > 0 else []
    if isinstance(we, list) and w > 0 and h > 0 and len(we) == h:
        for y, row in enumerate(we):
            if not isinstance(row, list) or len(row) != w:
                continue
            for x, v in enumerate(row):
                try:
                    vi = int(v)
                except (TypeError, ValueError):
                    continue
                if 1 <= vi <= max_idx:
                    tile_counts[vi - 1] += 1
    for i, p in enumerate(patches):
        pid = str(p.get("id", "")).strip() or f"#{i}"
        if i < len(tile_counts) and tile_counts[i] == 0:
            warns.append(f"{path.name} wild patch {pid}: no tiles reference this patch")


def script_path_on_disk(map_path: Path, script_obj: object) -> Path | None:
    if not isinstance(script_obj, dict):
        return None
    if "path" in script_obj:
        rel = str(script_obj["path"]).strip().replace("\\", "/").lstrip("/")
        if ".." in rel.split("/"):
            return None
        return (ROOT / "src" / "maps" / rel).resolve()
    return None


def _script_file_has_executable_steps(doc: object) -> bool:
    if not isinstance(doc, dict):
        return False
    s1 = doc.get("script_1")
    if isinstance(s1, list) and len(s1) > 0:
        return True
    if isinstance(s1, dict) and len(s1) > 0:
        return True
    acts = doc.get("actions")
    return isinstance(acts, list) and len(acts) > 0


TRIGGER_TYPES = frozenset({"interact", "step_on", "on_map_enter", "on_condition"})
LIBRARY_DIR = ROOT / "src" / "maps" / "scripts" / "_library"


def _script_block_error(doc: object) -> str | None:
    """FEATURE-MAP-068 / FEATURE-MAP-076: report unbalanced blocks across the main flow and
    all in-file subflows (if_flag/end_if, repeat/end_repeat, if_var/end_if_var, region/end_region)."""
    try:
        import event_script_schema as _ess  # tools/ is on sys.path when run as a script
    except ImportError:
        return None
    if not isinstance(doc, dict):
        return None
    flows = _ess.document_to_flows(doc)
    for name, steps in flows.items():
        ok, msg = _ess.validate_balanced(steps)
        if not ok:
            return f"flow '{name}': {msg}"
    return None


def _script_reference_errors(doc: object) -> list[str]:
    """FEATURE-MAP-074/075: validate goto targets and call_subflow references.

    - goto must name a label declared in the SAME flow.
    - call_subflow must resolve to an in-file subflow or a library connector file.
    """
    try:
        import event_script_schema as _ess
    except ImportError:
        return []
    if not isinstance(doc, dict):
        return []
    out: list[str] = []
    flows = _ess.document_to_flows(doc)
    flow_names = set(flows.keys())
    for name, steps in flows.items():
        labels = set(_ess.labels_in_steps(steps))
        for st in steps:
            if not isinstance(st, dict):
                continue
            op = str(st.get("op", "")).strip()
            args = st.get("args") if isinstance(st.get("args"), dict) else {}
            if op == "goto":
                target = str(args.get("label", "")).strip()
                if not target:
                    out.append(f"flow '{name}': goto with empty label")
                elif target not in labels:
                    out.append(f"flow '{name}': goto target {target!r} has no matching label")
            elif op == "call_subflow":
                sub = str(args.get("name", "")).strip()
                if not sub:
                    out.append(f"flow '{name}': call_subflow with empty name")
                    continue
                if sub in flow_names:
                    continue
                lib = LIBRARY_DIR / f"{sub}.json"
                if not lib.is_file():
                    out.append(
                        f"flow '{name}': call_subflow {sub!r} is not an in-file subflow "
                        f"or a library connector (src/maps/scripts/_library/{sub}.json)"
                    )
    return out


def _validate_event_trigger(path: Path, eid: str, ev: dict, errs: list[str]) -> None:
    """FEATURE-MAP-078: validate trigger / condition / onComplete / clearedFlag shapes."""
    tr = ev.get("trigger")
    if tr is not None:
        if not isinstance(tr, dict):
            errs.append(f"{path.name} event {eid}: trigger must be an object")
        else:
            ttype = str(tr.get("type", "interact")).strip()
            if ttype not in TRIGGER_TYPES:
                errs.append(
                    f"{path.name} event {eid}: trigger.type {ttype!r} invalid "
                    f"(use interact/step_on/on_map_enter/on_condition)"
                )
            cond = tr.get("condition")
            if cond is not None:
                if not isinstance(cond, dict):
                    errs.append(f"{path.name} event {eid}: trigger.condition must be an object")
                else:
                    if not str(cond.get("flag", "")).strip():
                        errs.append(f"{path.name} event {eid}: trigger.condition.flag must be a non-empty string")
                    if "set" in cond and not isinstance(cond.get("set"), bool):
                        errs.append(f"{path.name} event {eid}: trigger.condition.set must be a boolean")
    cf = ev.get("clearedFlag")
    if cf is not None and not isinstance(cf, str):
        errs.append(f"{path.name} event {eid}: clearedFlag must be a string")
    oc = ev.get("onComplete")
    if oc is not None:
        if not isinstance(oc, dict):
            errs.append(f"{path.name} event {eid}: onComplete must be an object")
        else:
            for key in ("setFlags", "clearFlags"):
                arr = oc.get(key)
                if arr is None:
                    continue
                if not isinstance(arr, list):
                    errs.append(f"{path.name} event {eid}: onComplete.{key} must be an array")
                    continue
                for j, f in enumerate(arr):
                    if not isinstance(f, str) or not f.strip():
                        errs.append(f"{path.name} event {eid}: onComplete.{key}[{j}] must be a non-empty string")


def validate_map(path: Path) -> tuple[list[str], list[str]]:
    errs: list[str] = []
    warns: list[str] = []
    try:
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return ([f"{path.name}: cannot read JSON ({e})"], [])
    if not isinstance(m, dict):
        return ([f"{path.name}: root not an object"], [])
    w = int(m.get("width", 0))
    h = int(m.get("height", 0))
    _validate_wild_patches(path, m, w, h, errs, warns)
    evs = m.get("events")
    if evs is None:
        return errs, warns
    if not isinstance(evs, list):
        return ([f"{path.name}: events must be an array"], [])
    boxes: list[tuple[str, int, int, int, int]] = []
    for i, ev in enumerate(evs):
        if not isinstance(ev, dict):
            errs.append(f"{path.name}: events[{i}] not an object")
            continue
        eid = str(ev.get("id", "")).strip() or f"#{i}"
        anch = ev.get("anchor")
        if not isinstance(anch, dict):
            errs.append(f"{path.name} event {eid}: missing anchor object")
            continue
        try:
            ax = int(anch.get("x", -1))
            ay = int(anch.get("y", -1))
        except (TypeError, ValueError):
            errs.append(f"{path.name} event {eid}: anchor x/y invalid")
            continue
        if w > 0 and h > 0:
            if ax < 0 or ay < 0 or ax + EVENT_FOOTPRINT > w or ay + EVENT_FOOTPRINT > h:
                errs.append(
                    f"{path.name} event {eid}: anchor ({ax},{ay}) 2x2 out of bounds for map {w}x{h}"
                )
        boxes.append((eid, ax, ay, ax + EVENT_FOOTPRINT, ay + EVENT_FOOTPRINT))
        script = ev.get("script")
        p = script_path_on_disk(path, script)
        if p is not None:
            if not p.is_file():
                errs.append(f"{path.name} event {eid}: script file missing: {p.relative_to(ROOT)}")
            else:
                try:
                    with p.open(encoding="utf-8") as sf:
                        sdoc = json.load(sf)
                except (OSError, json.JSONDecodeError, TypeError) as e:
                    errs.append(f"{path.name} event {eid}: script JSON unreadable ({e})")
                else:
                    if not _script_file_has_executable_steps(sdoc):
                        warns.append(
                            f"{path.name} event {eid}: script has no non-empty script_1 or actions "
                            f"({p.relative_to(ROOT)})"
                        )
                    block_err = _script_block_error(sdoc)
                    if block_err:
                        errs.append(
                            f"{path.name} event {eid}: unbalanced control-flow block "
                            f"({block_err}) in {p.relative_to(ROOT)}"
                        )
                    for ref_err in _script_reference_errors(sdoc):
                        errs.append(
                            f"{path.name} event {eid}: {ref_err} in {p.relative_to(ROOT)}"
                        )
        elif isinstance(script, dict) and script.get("path"):
            errs.append(f"{path.name} event {eid}: invalid script path")
        _validate_event_trigger(path, eid, ev, errs)
        sp = ev.get("sprite")
        if sp is not None and isinstance(sp, dict):
            kind = str(sp.get("kind", ""))
            if kind not in ("character", "pokemon_icon", "pokemon_icon_shiny"):
                errs.append(f"{path.name} event {eid}: sprite.kind invalid")
            try:
                frame = int(sp.get("frame", 0))
            except (TypeError, ValueError):
                errs.append(f"{path.name} event {eid}: sprite.frame invalid")
                frame = 0
            is_ch = kind == "character"
            try:
                sc = int(sp.get("sheetColumns", 4 if is_ch else 1))
                sr = int(sp.get("sheetRows", 4 if is_ch else 1))
            except (TypeError, ValueError):
                sc, sr = (4 if is_ch else 1), (4 if is_ch else 1)
            sc = max(1, sc)
            sr = max(1, sr)
            if frame < 0 or frame >= sc * sr:
                errs.append(
                    f"{path.name} event {eid}: sprite.frame {frame} out of range for {sc}×{sr} sheet"
                )
            fac = sp.get("facing")
            if fac is not None and str(fac).strip() != "":
                if not isinstance(fac, str):
                    errs.append(f"{path.name} event {eid}: sprite.facing must be a string when present")
                elif is_ch:
                    allowed = {
                        "up",
                        "down",
                        "left",
                        "right",
                        "north",
                        "south",
                        "east",
                        "west",
                        "n",
                        "s",
                        "e",
                        "w",
                    }
                    if str(fac).strip().lower() not in allowed:
                        errs.append(
                            f"{path.name} event {eid}: sprite.facing invalid for character "
                            "(use up/down/left/right or n/s/e/w aliases)"
                        )
    for i, (id_a, ax0, ay0, ax1, ay1) in enumerate(boxes):
        for id_b, bx0, by0, bx1, by1 in boxes[i + 1 :]:
            if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                errs.append(f"{path.name}: events overlap {id_a} and {id_b}")
    return errs, warns


def main() -> int:
    if not MAPS_DIR.is_dir():
        print("No src/maps directory", file=sys.stderr)
        return 1
    all_errs: list[str] = []
    all_warns: list[str] = []
    for p in sorted(MAPS_DIR.glob("*.json")):
        if p.name in SKIP_NAMES:
            continue
        e, w = validate_map(p)
        all_errs.extend(e)
        all_warns.extend(w)
    for line in all_warns:
        print(line, file=sys.stderr)
    if all_errs:
        for line in all_errs:
            print(line, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# FEATURE-MAP-043 / FEATURE-MAP-044: script file shape, registry from C++ codegen + meta JSON for map_editor.
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

_TOOLS_DIR = Path(__file__).resolve().parent


def _load_cpp_ops_ordered() -> tuple[str, ...]:
    gen = _TOOLS_DIR / "event_script_ops_generated.py"
    if not gen.is_file():
        print(
            f"event_script_schema: missing {gen.name}; run: python3 docs/cursor_helper_scripts/extract_map_script_ops.py",
            file=sys.stderr,
        )
        raise FileNotFoundError(gen)
    spec = importlib.util.spec_from_file_location("_event_script_ops_generated", gen)
    if spec is None or spec.loader is None:
        raise RuntimeError("event_script_ops_generated: bad import spec")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    seq = getattr(mod, "CPP_SCRIPT_OPS_ORDERED", None)
    if not isinstance(seq, tuple) or not seq:
        raise RuntimeError("CPP_SCRIPT_OPS_ORDERED missing or empty")
    return tuple(str(x) for x in seq)


def _load_meta() -> dict[str, Any]:
    p = _TOOLS_DIR / "event_script_op_meta.json"
    if not p.is_file():
        raise FileNotFoundError(p)
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("ops"), dict):
        raise ValueError("event_script_op_meta.json: root must have ops object")
    return data


_CPP_OPS: tuple[str, ...] = _load_cpp_ops_ordered()
_META_ROOT: dict[str, Any] = _load_meta()
_OPS_META: dict[str, Any] = {str(k): v for k, v in _META_ROOT["ops"].items() if isinstance(v, dict)}

_UNCATEGORIZED = "Uncategorized"

# (opcode, menu label, default args) — op order matches C++ stepFrame; labels/docs from meta
EVENT_ACTION_DEFS: tuple[tuple[str, str, dict[str, Any]], ...] = tuple(
    (
        op,
        str(_OPS_META[op].get("label", op)),
        copy.deepcopy(_OPS_META[op].get("default_args") or {}),
    )
    for op in _CPP_OPS
)

_DEFAULT_BY_OP: dict[str, dict[str, Any]] = {op: copy.deepcopy(args) for op, _lbl, args in EVENT_ACTION_DEFS}


def event_action_defs_with_palette_sort(sort_mode: str) -> tuple[tuple[str, str, dict[str, Any]], ...]:
    """FEATURE-MAP-049: palette order — ``source`` (C++ order), ``alpha``, or ``category``."""
    sm = (sort_mode or "source").strip().lower()
    if sm == "alpha":
        defs = list(EVENT_ACTION_DEFS)
        defs.sort(key=lambda t: (str(t[1]).lower(), t[0]))
        return tuple(defs)
    if sm == "category":
        buckets: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
        for row in EVENT_ACTION_DEFS:
            op = row[0]
            raw = _OPS_META.get(op, {})
            cat = str(raw.get("category", _UNCATEGORIZED)).strip() or _UNCATEGORIZED
            buckets.setdefault(cat, []).append(row)
        out: list[tuple[str, str, dict[str, Any]]] = []
        for cat in sorted(buckets.keys(), key=lambda s: s.lower()):
            rows = sorted(buckets[cat], key=lambda t: (str(t[1]).lower(), t[0]))
            out.extend(rows)
        return tuple(out)
    return EVENT_ACTION_DEFS


def default_args_for_op(op: str) -> dict[str, Any]:
    ent = _OPS_META.get(op)
    if ent and isinstance(ent.get("default_args"), dict):
        return copy.deepcopy(ent["default_args"])
    return copy.deepcopy(_DEFAULT_BY_OP.get(op, {}))


def new_step(op: str) -> dict[str, Any]:
    return {"op": str(op), "args": default_args_for_op(op)}


def op_documentation(op: str) -> dict[str, Any]:
    """Return label, description, status, default_args, args_help, category, required_params (FEATURE-MAP-049)."""
    ent = _OPS_META.get(op)
    if not ent:
        return {
            "label": op,
            "description": "Unknown opcode: runs as a stub at runtime (stderr + on-screen debug line).",
            "status": "unknown",
            "default_args": {},
            "args_help": {},
            "category": _UNCATEGORIZED,
            "required_params": [],
        }
    req = ent.get("required_params")
    req_list: list[str] = []
    if isinstance(req, list):
        req_list = [str(x) for x in req if isinstance(x, str) and x.strip()]
    cat = str(ent.get("category", _UNCATEGORIZED)).strip() or _UNCATEGORIZED
    return {
        "label": str(ent.get("label", op)),
        "description": str(ent.get("description", "")).strip(),
        "status": str(ent.get("status", "implemented")),
        "default_args": copy.deepcopy(ent.get("default_args") or {}),
        "args_help": {str(k): str(v) for k, v in (ent.get("args_help") or {}).items()},
        "category": cat,
        "required_params": req_list,
    }


def cpp_script_ops_ordered() -> tuple[str, ...]:
    return _CPP_OPS


# ---------------------------------------------------------------------------
# FEATURE-MAP-068: control-flow block metadata + nested tree <-> flat helpers
# ---------------------------------------------------------------------------

def op_category(op: str) -> str:
    """Category label for an opcode (``Uncategorized`` when missing)."""
    ent = _OPS_META.get(op, {})
    return str(ent.get("category", _UNCATEGORIZED)).strip() or _UNCATEGORIZED


def op_block_role(op: str) -> str | None:
    """Return ``"open"`` for a block opener (if_flag/repeat), ``"close"`` for a terminator
    (end_if/end_repeat), or ``None`` for a plain opcode."""
    ent = _OPS_META.get(op, {})
    role = ent.get("block")
    if role in ("open", "close"):
        return role
    return None


def op_block_end(op: str) -> str | None:
    """For a block opener, the matching terminator op (e.g. if_flag -> end_if)."""
    ent = _OPS_META.get(op, {})
    end = ent.get("end")
    return str(end) if isinstance(end, str) and end.strip() else None


def is_block_open(op: str) -> bool:
    return op_block_role(op) == "open"


def is_block_close(op: str) -> bool:
    return op_block_role(op) == "close"


def sort_palette_ops_in_category(ops: list[str]) -> list[str]:
    """FEATURE-MAP-081: reorder so block openers appear immediately before their end_* pair.

    Non-block ops keep their relative order. Unpaired closers are appended at the end.
    """
    used: set[str] = set()
    out: list[str] = []
    for op in ops:
        if op in used:
            continue
        if is_block_open(op):
            out.append(op)
            used.add(op)
            end = op_block_end(op)
            if end and end in ops:
                out.append(end)
                used.add(end)
        elif not is_block_close(op):
            out.append(op)
            used.add(op)
    for op in ops:
        if op not in used:
            out.append(op)
            used.add(op)
    return out


def validate_balanced(steps: list[dict[str, Any]]) -> tuple[bool, str]:
    """Check that block openers/terminators are balanced and correctly nested.

    Returns (ok, message). On success message is empty.
    """
    stack: list[tuple[str, str]] = []  # (opener_op, expected_end_op)
    for idx, st in enumerate(steps):
        if not isinstance(st, dict):
            continue
        op = str(st.get("op", "")).strip()
        if not op:
            continue
        if is_block_open(op):
            stack.append((op, op_block_end(op) or ""))
        elif is_block_close(op):
            if not stack:
                return False, f"step {idx}: '{op}' without a matching opener"
            opener, expected_end = stack.pop()
            if expected_end and op != expected_end:
                return False, f"step {idx}: '{op}' closes '{opener}' (expected '{expected_end}')"
    if stack:
        opener, expected_end = stack[-1]
        return False, f"unclosed '{opener}' (missing '{expected_end}')"
    return True, ""


def steps_to_tree(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse a flat step list into a nested tree.

    Container nodes (if_flag/repeat) gain a ``children`` list; their terminator marker is implicit.
    Unbalanced terminators are dropped defensively so the editor never crashes on bad data.
    """
    root: list[dict[str, Any]] = []
    stack: list[list[dict[str, Any]]] = [root]
    open_ops: list[str] = []
    for st in steps:
        if not isinstance(st, dict):
            continue
        op = str(st.get("op", "")).strip()
        if not op:
            continue
        args = st.get("args")
        args = copy.deepcopy(args) if isinstance(args, dict) else {}
        if is_block_open(op):
            node: dict[str, Any] = {"op": op, "args": args, "children": []}
            stack[-1].append(node)
            stack.append(node["children"])
            open_ops.append(op)
        elif is_block_close(op):
            if len(stack) > 1:
                stack.pop()
                open_ops.pop()
            # else: stray terminator -> ignore
        else:
            stack[-1].append({"op": op, "args": args})
    return root


def tree_to_steps(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten a nested tree back into a flat step list with explicit terminator markers.

    ``args.skip`` is intentionally NOT written here; the C++ runtime stamps it on load via
    resolveControlFlow. We strip any stale ``skip`` from openers to keep files clean.
    """
    out: list[dict[str, Any]] = []

    def _emit(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            if not isinstance(node, dict):
                continue
            op = str(node.get("op", "")).strip()
            if not op:
                continue
            args = node.get("args")
            args = copy.deepcopy(args) if isinstance(args, dict) else {}
            if is_block_open(op) and "children" in node:
                args.pop("skip", None)
                out.append({"op": op, "args": args})
                _emit(node.get("children") or [])
                end_op = op_block_end(op)
                if end_op:
                    out.append({"op": end_op, "args": {}})
            else:
                out.append({"op": op, "args": args})

    _emit(tree)
    return out


def _args_from_value(v: Any) -> dict[str, Any]:
    if isinstance(v, dict):
        return copy.deepcopy(v)
    return {}


def _append_script1_array_to_steps(out: list[dict[str, Any]], arr: list[Any]) -> None:
    for el in arr:
        if not isinstance(el, dict) or len(el) != 1:
            continue
        k, v = next(iter(el.items()))
        op = str(k).strip()
        if not op:
            continue
        out.append({"op": op, "args": _args_from_value(v)})


def _append_script1_object_to_steps(out: list[dict[str, Any]], obj: dict[str, Any]) -> None:
    for k, v in obj.items():
        op = str(k).strip()
        if not op:
            continue
        out.append({"op": op, "args": _args_from_value(v)})


def document_to_steps(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Load ordered steps from a script JSON object (FEATURE-MAP-043).

    Precedence: non-empty steps built from ``script_1`` (array preferred, then object);
    otherwise legacy ``actions`` array of ``{op, args}``.
    """
    out: list[dict[str, Any]] = []
    s1 = doc.get("script_1")
    if isinstance(s1, list):
        _append_script1_array_to_steps(out, s1)
    elif isinstance(s1, dict):
        _append_script1_object_to_steps(out, s1)
    if out:
        return out
    raw = doc.get("actions")
    if isinstance(raw, list):
        for el in raw:
            if not isinstance(el, dict):
                continue
            op = el.get("op")
            if not isinstance(op, str) or not op.strip():
                continue
            args = el.get("args")
            out.append({"op": op, "args": copy.deepcopy(args) if isinstance(args, dict) else {}})
    return out


def steps_to_document(steps: list[dict[str, Any]], map_id: str) -> dict[str, Any]:
    """Serialize to canonical FEATURE-MAP-043 file shape (script_1 = array of one-key objects)."""
    script_1: list[dict[str, Any]] = []
    for st in steps:
        if not isinstance(st, dict):
            continue
        op = st.get("op")
        if not isinstance(op, str) or not op.strip():
            continue
        args = st.get("args")
        ad = copy.deepcopy(args) if isinstance(args, dict) else {}
        script_1.append({op: ad})
    return {
        "version": 1,
        "map": str(map_id).strip() or "unknown_map",
        "script_1": script_1,
        "script_2": [],
    }


def labels_in_steps(steps: list[dict[str, Any]]) -> list[str]:
    """FEATURE-MAP-075: ordered, de-duplicated list of label names declared in a flow.

    Used by the editor to populate the goto target dropdown.
    """
    out: list[str] = []
    seen: set[str] = set()
    for st in steps:
        if not isinstance(st, dict) or str(st.get("op", "")).strip() != "label":
            continue
        args = st.get("args")
        name = str(args.get("name", "")).strip() if isinstance(args, dict) else ""
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def document_to_flows(doc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """FEATURE-MAP-074: parse the main flow + named in-file subflows into step lists.

    Always returns a dict with at least a ``main`` key. Subflow values accept the same
    script_1-style array (one-key objects) used by the main flow.
    """
    flows: dict[str, list[dict[str, Any]]] = {"main": document_to_steps(doc)}
    subs = doc.get("subflows")
    if isinstance(subs, dict):
        for name, val in subs.items():
            nm = str(name).strip()
            if not nm or nm == "main":
                continue
            steps: list[dict[str, Any]] = []
            if isinstance(val, list):
                _append_script1_array_to_steps(steps, val)
            elif isinstance(val, dict):
                _append_script1_object_to_steps(steps, val)
            flows[nm] = steps
    return flows


def flows_to_document(flows: dict[str, list[dict[str, Any]]], map_id: str) -> dict[str, Any]:
    """FEATURE-MAP-074: serialize main flow + subflows to the canonical file shape.

    The main flow is written to ``script_1``; other flows go under ``subflows`` as arrays of
    one-key objects. Empty subflows are still written so renamed/created tabs round-trip.
    """
    main_steps = flows.get("main") or []
    doc = steps_to_document(main_steps, map_id)
    subflows: dict[str, Any] = {}
    for name, steps in flows.items():
        if name == "main":
            continue
        nm = str(name).strip()
        if not nm:
            continue
        arr: list[dict[str, Any]] = []
        for st in steps or []:
            if not isinstance(st, dict):
                continue
            op = st.get("op")
            if not isinstance(op, str) or not op.strip():
                continue
            args = st.get("args")
            arr.append({op: copy.deepcopy(args) if isinstance(args, dict) else {}})
        subflows[nm] = arr
    if subflows:
        doc["subflows"] = subflows
    return doc


def read_flows_from_path(path: Path) -> dict[str, list[dict[str, Any]]]:
    """FEATURE-MAP-074: read main + subflows; defaults to a single-step main flow."""
    if not path.is_file():
        return {"main": [new_step("show_message")]}
    try:
        with path.open(encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return {"main": [new_step("show_message")]}
    if not isinstance(doc, dict):
        return {"main": [new_step("show_message")]}
    flows = document_to_flows(doc)
    if not flows.get("main"):
        flows["main"] = [new_step("show_message")]
    return flows


def write_flows_to_path(path: Path, flows: dict[str, list[dict[str, Any]]], map_id: str) -> None:
    """FEATURE-MAP-074: write main + subflows to disk (canonical FEATURE-MAP-043 shape)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = flows_to_document(flows, map_id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")


def read_steps_from_path(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return [new_step("show_message")]
    try:
        with path.open(encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return [new_step("show_message")]
    if not isinstance(doc, dict):
        return [new_step("show_message")]
    steps = document_to_steps(doc)
    return steps if steps else [new_step("show_message")]


def write_document_to_path(path: Path, steps: list[dict[str, Any]], map_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = steps_to_document(steps, map_id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# FEATURE-MAP-081: library subflow discovery
# ---------------------------------------------------------------------------

_LIBRARY_DIR = Path(__file__).resolve().parents[1] / "src" / "maps" / "scripts" / "_library"


def list_library_subflow_names() -> list[str]:
    """Return sorted stem names of JSON files in ``src/maps/scripts/_library/``."""
    if not _LIBRARY_DIR.is_dir():
        return []
    return sorted(p.stem for p in _LIBRARY_DIR.glob("*.json") if p.is_file())


# ---------------------------------------------------------------------------
# FEATURE-MAP-088: library battle definitions
# ---------------------------------------------------------------------------

_BATTLES_DIR = _LIBRARY_DIR / "battles"
_BATTLE_JSON = Path(__file__).resolve().parents[1] / "src" / "battle.json"


def list_library_battle_names() -> list[str]:
    """Return sorted battle ids under ``_library/battles/*.json``."""
    if not _BATTLES_DIR.is_dir():
        return []
    return sorted(p.stem for p in _BATTLES_DIR.glob("*.json") if p.is_file())


def list_battle_background_ids() -> list[str]:
    if not _BATTLE_JSON.is_file():
        return ["example"]
    try:
        with open(_BATTLE_JSON, encoding="utf-8") as f:
            data = json.load(f)
        bgs = data.get("backgrounds")
        if isinstance(bgs, list):
            return [str(x.get("id", "")) for x in bgs if isinstance(x, dict) and x.get("id")]
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return ["example"]


def sanitize_battle_id(raw: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(raw or "").strip())
    return out[:48] or "battle"


def normalize_battle_def(raw: dict, fallback_id: str = "battle") -> dict:
    """Coerce a battle JSON object into the editor/runtime shape."""
    bid = sanitize_battle_id(str(raw.get("id") or fallback_id))
    mode = str(raw.get("outcomeMode") or "normal")
    if mode not in ("normal", "scripted_win", "scripted_loss"):
        mode = "normal"
    trainers_in = raw.get("trainers")
    trainers: list[dict] = []
    if isinstance(trainers_in, list):
        for tr in trainers_in[:2]:
            if not isinstance(tr, dict):
                continue
            party_in = tr.get("party")
            party: list[dict] = []
            if isinstance(party_in, list):
                for mon in party_in[:6]:
                    if not isinstance(mon, dict):
                        continue
                    sp = str(mon.get("species") or "Pidgey")
                    try:
                        lv = max(1, min(100, int(mon.get("level", 5))))
                    except (TypeError, ValueError):
                        lv = 5
                    party.append({"species": sp, "level": lv})
            if not party:
                party = [{"species": "Pidgey", "level": 5}]
            trainers.append({"party": party})
    if not trainers:
        trainers = [{"party": [{"species": "Pidgey", "level": 5}]}]
    try:
        loss_turns = max(0, int(raw.get("scriptedLossTurns", 0)))
    except (TypeError, ValueError):
        loss_turns = 0
    out: dict[str, Any] = {
        "id": bid,
        "music": str(raw.get("music") or ""),
        "background": str(raw.get("background") or "example"),
        "outcomeMode": mode,
        "scriptedLossTurns": loss_turns,
        "trainers": trainers,
    }
    lw = raw.get("lossWarp")
    if isinstance(lw, dict) and lw.get("mapId"):
        out["lossWarp"] = {
            "mapId": str(lw.get("mapId")),
            "x": int(lw.get("x", 0)),
            "y": int(lw.get("y", 0)),
        }
    return out


def load_library_battle(battle_id: str) -> dict | None:
    bid = sanitize_battle_id(battle_id)
    p = _BATTLES_DIR / f"{bid}.json"
    if not p.is_file():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return normalize_battle_def(raw, bid)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return None


def merge_battle_config(base: dict, overrides: dict) -> dict:
    """Merge opcode inline overrides onto a library battle definition."""
    merged = copy.deepcopy(base)
    for key in ("music", "background", "outcomeMode", "scriptedLossTurns"):
        if key in overrides and overrides[key] not in (None, ""):
            merged[key] = overrides[key]
    if "lossWarp" in overrides and isinstance(overrides["lossWarp"], dict):
        merged["lossWarp"] = copy.deepcopy(overrides["lossWarp"])
    if "trainers" in overrides and isinstance(overrides["trainers"], list) and overrides["trainers"]:
        merged["trainers"] = copy.deepcopy(overrides["trainers"])
    return normalize_battle_def(merged, str(merged.get("id", "battle")))


# ---------------------------------------------------------------------------
# FEATURE-MAP-096 Phase 1: map/script normalization for migrate_map_events.py
# ---------------------------------------------------------------------------

TRIGGER_TYPES: frozenset[str] = frozenset({"interact", "step_on", "on_map_enter", "on_condition"})

_LEGACY_INTERACTION_TO_TRIGGER: dict[str, str] = {
    "talk": "interact",
    "interact": "interact",
    "step_on": "step_on",
    "step": "step_on",
}


def default_event_trigger() -> dict[str, Any]:
    """Canonical default trigger for newly created or migrated events."""
    return {"type": "interact"}


def trigger_from_legacy_interaction(interaction: Any) -> dict[str, Any]:
    """Map legacy ``interaction`` objects to a ``trigger`` object."""
    if not isinstance(interaction, dict):
        return default_event_trigger()
    raw = str(interaction.get("type", "talk")).strip().lower()
    ttype = _LEGACY_INTERACTION_TO_TRIGGER.get(raw, "interact")
    return {"type": ttype}


def normalize_map_event(ev: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalize one map ``events[]`` entry; returns (copy, human-readable changes)."""
    out = copy.deepcopy(ev)
    changes: list[str] = []
    eid = str(out.get("id", "")).strip() or "(unnamed)"

    if "interaction" in out:
        legacy = out.pop("interaction")
        if "trigger" not in out:
            out["trigger"] = trigger_from_legacy_interaction(legacy)
            changes.append(f"interaction -> trigger.type={out['trigger']['type']!r}")
        else:
            changes.append("removed obsolete interaction")

    if "trigger" not in out:
        out["trigger"] = default_event_trigger()
        changes.append("added default trigger interact")

    tr = out.get("trigger")
    if isinstance(tr, dict):
        ttype = str(tr.get("type", "interact")).strip()
        if ttype not in TRIGGER_TYPES:
            tr["type"] = "interact"
            changes.append("invalid trigger.type -> interact")

    if changes:
        changes = [f"{eid}: {c}" for c in changes]
    return out, changes


def migrate_script_document(doc: dict[str, Any], map_id: str) -> tuple[dict[str, Any], list[str]]:
    """Normalize a script JSON file to canonical ``script_1`` + ``subflows`` shape."""
    changes: list[str] = []
    if not isinstance(doc, dict):
        return {"version": 1, "map": map_id, "script_1": [], "script_2": []}, ["replaced invalid root with empty document"]

    had_actions = isinstance(doc.get("actions"), list) and len(doc.get("actions") or []) > 0
    had_script1 = isinstance(doc.get("script_1"), list) and len(doc.get("script_1") or []) > 0
    flows = document_to_flows(doc)
    if not flows.get("main"):
        flows["main"] = [new_step("show_message")]

    out = flows_to_document(flows, map_id)
    out["version"] = 1

    if had_actions and not had_script1:
        changes.append("converted legacy actions[] -> script_1")
    elif had_actions:
        changes.append("removed legacy actions[] (script_1 is source of truth)")

    if str(doc.get("map", "")).strip() != map_id:
        changes.append(f"set map field to {map_id!r}")

    if had_actions or "actions" in doc:
        changes.append("dropped actions key")

    return out, changes


def script_documents_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Stable JSON equality for dry-run change detection."""
    return json.dumps(a, sort_keys=True, indent=2) == json.dumps(b, sort_keys=True, indent=2)

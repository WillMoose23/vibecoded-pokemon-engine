# FEATURE-MAP-046: configurable nested context menu for map_editor event script modal.
from __future__ import annotations

import copy
from typing import Any

MAX_DEPTH = 12
MAX_NODES = 200
WHEN_VALUES = frozenset({"always", "row", "no_row"})
TYPE_VALUES = frozenset({"action", "submenu"})


def _node_visible(node: dict[str, Any], *, row_i: int | None, has_clipboard: bool) -> bool:
    when = str(node.get("when", "always")).strip()
    if when not in WHEN_VALUES:
        when = "always"
    aid = str(node.get("id", ""))
    if aid == "step:paste_after":
        return bool(has_clipboard and row_i is not None)
    if when == "row":
        return row_i is not None
    if when == "no_row":
        return row_i is None
    return True


def filter_tree(
    nodes: list[dict[str, Any]],
    *,
    row_i: int | None,
    has_clipboard: bool,
    depth: int = 0,
) -> list[dict[str, Any]]:
    if depth > MAX_DEPTH or not isinstance(nodes, list):
        return []
    out: list[dict[str, Any]] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if not _node_visible(n, row_i=row_i, has_clipboard=has_clipboard):
            continue
        typ = str(n.get("type", "action")).strip()
        if typ not in TYPE_VALUES:
            typ = "action"
        child = copy.deepcopy(n)
        child["type"] = typ
        if typ == "submenu":
            ch = n.get("children")
            if isinstance(ch, list):
                child["children"] = filter_tree(ch, row_i=row_i, has_clipboard=has_clipboard, depth=depth + 1)
            else:
                child["children"] = []
        out.append(child)
    return out


def validate_action_id(aid: str, known_ops: frozenset[str]) -> bool:
    if aid in (
        "step:delete",
        "step:copy",
        "step:duplicate",
        "step:paste_after",
        "rename_script",
        "blk:editmodal",
        "blk:doc",
        "blk:delete",
        "blk:copy",
        "blk:paste",
        "blk:add",
    ):
        return True
    if aid.startswith("ev:"):
        return validate_event_action_id(aid)
    if aid.startswith("add:"):
        op = aid[4:].strip()
        return bool(op) and op in known_ops
    return False


def validate_tree(nodes: list[Any], known_ops: frozenset[str], *, depth: int = 0, count: list[int]) -> list[str]:
    errs: list[str] = []
    if depth > MAX_DEPTH:
        return [f"nesting exceeds {MAX_DEPTH}"]
    if not isinstance(nodes, list):
        return ["root must be a JSON array"]
    for i, n in enumerate(nodes):
        count[0] += 1
        if count[0] > MAX_NODES:
            errs.append("too many menu nodes")
            return errs
        if not isinstance(n, dict):
            errs.append(f"item {i} must be an object")
            continue
        typ = str(n.get("type", "action")).strip()
        if typ not in TYPE_VALUES:
            errs.append(f"item {i}: invalid type {typ!r}")
        if typ == "action":
            aid = str(n.get("id", "")).strip()
            if not aid:
                errs.append(f"item {i}: action missing id")
            elif not validate_action_id(aid, known_ops):
                errs.append(f"item {i}: unknown or invalid id {aid!r}")
        elif typ == "submenu":
            if not str(n.get("label", "")).strip():
                errs.append(f"item {i}: submenu missing label")
            ch = n.get("children")
            if not isinstance(ch, list):
                errs.append(f"item {i}: submenu children must be array")
            else:
                errs.extend(validate_tree(ch, known_ops, depth=depth + 1, count=count))
    return errs


def default_menu_tree_from_ops(op_pairs: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """op_pairs: (opcode, label) from EVENT_ACTION_DEFS."""
    row_ops: list[dict[str, Any]] = [
        {"type": "action", "label": "Edit in modal", "id": "blk:editmodal", "when": "row"},
        {"type": "action", "label": "Show documentation", "id": "blk:doc", "when": "row"},
        {"type": "action", "label": "Delete step", "id": "step:delete", "when": "row"},
        {"type": "action", "label": "Copy", "id": "step:copy", "when": "row"},
        {"type": "action", "label": "Duplicate", "id": "step:duplicate", "when": "row"},
        {"type": "action", "label": "Paste after", "id": "step:paste_after", "when": "row"},
    ]
    add_children = [
        {"type": "action", "label": f"Add: {lbl}", "id": f"add:{op}", "when": "always"} for op, lbl in op_pairs
    ]
    return row_ops + [
        {"type": "submenu", "label": "Add step", "when": "always", "children": add_children},
        {"type": "action", "label": "Rename script (open JSON)", "id": "rename_script", "when": "always"},
    ]


def parse_menu_from_config(raw: Any, known_ops: frozenset[str]) -> tuple[list[dict[str, Any]] | None, list[str]]:
    """Returns (tree or None on hard failure, errors). Empty errors means tree is usable."""
    if raw is None:
        return None, []
    if not isinstance(raw, list):
        return None, ["contextMenu must be an array"]
    count = [0]
    errs = validate_tree(raw, known_ops, depth=0, count=count)
    if errs:
        return None, errs
    return copy.deepcopy(raw), []


def validate_event_action_id(aid: str) -> bool:
    return aid in (
        "ev:rename",
        "ev:copy",
        "ev:paste",
        "ev:delete",
        "ev:view",
        "ev:sprite",
        "ev:trigger",
    )


def default_event_menu_tree(*, multi_delete_label: str = "Delete") -> list[dict[str, Any]]:
    """Event list RMB menu (FEATURE-MAP-068 / Phase 3 Event Engine)."""
    return [
        {"type": "action", "label": "Rename", "id": "ev:rename", "when": "row"},
        {"type": "action", "label": "Copy", "id": "ev:copy", "when": "row"},
        {"type": "action", "label": "Paste", "id": "ev:paste", "when": "always"},
        {"type": "action", "label": multi_delete_label, "id": "ev:delete", "when": "row"},
        {"type": "action", "label": "View in Map", "id": "ev:view", "when": "row"},
        {"type": "action", "label": "Assign Sprite", "id": "ev:sprite", "when": "row"},
        {"type": "action", "label": "Change Trigger", "id": "ev:trigger", "when": "row"},
    ]


def parse_event_menu_from_config(raw: Any) -> tuple[list[dict[str, Any]] | None, list[str]]:
    if raw is None:
        return None, []
    if not isinstance(raw, list):
        return None, ["contextMenuEvents must be an array"]
    count = [0]
    errs: list[str] = []
    out: list[dict[str, Any]] = []
    for i, n in enumerate(raw):
        count[0] += 1
        if count[0] > MAX_NODES:
            return None, ["too many menu nodes"]
        if not isinstance(n, dict):
            errs.append(f"item {i} must be an object")
            continue
        typ = str(n.get("type", "action")).strip()
        if typ == "action":
            aid = str(n.get("id", "")).strip()
            if not validate_event_action_id(aid):
                errs.append(f"item {i}: unknown event id {aid!r}")
        elif typ == "submenu":
            ch = n.get("children")
            if not isinstance(ch, list):
                errs.append(f"item {i}: submenu children must be array")
        else:
            errs.append(f"item {i}: invalid type {typ!r}")
        out.append(copy.deepcopy(n))
    if errs:
        return None, errs
    return out, []


def action_id_to_internal(aid: str) -> str | None:
    """Map stable id to legacy _event_script_run_ctx branch key."""
    m = {
        "step:delete": "del",
        "step:copy": "copy",
        "step:duplicate": "dup",
        "step:paste_after": "paste_after",
        "blk:delete": "del",
        "blk:copy": "copy",
        "blk:paste": "paste_after",
    }
    if aid in m:
        return m[aid]
    if aid.startswith("add:") or aid == "rename_script":
        return aid
    if aid.startswith("ev:") or aid.startswith("blk:"):
        return aid
    return None


def wrap_label_text(label: str, max_w: int, measure: Any) -> list[str]:
    """measure(s: str) -> int width in px."""
    words = (label or "").replace("\t", " ").split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip() if cur else w
        if measure(cand) <= max_w:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines if lines else [""]


def layout_cascade_panels(
    filtered_root: list[dict[str, Any]],
    *,
    sx: int,
    sy: int,
    mouse_xy: tuple[int, int],
    screen_w: int,
    screen_h: int,
    row_h: int,
    pad: int,
    measure: Any,
    max_panel_w: int,
) -> list[dict[str, Any]]:
    """
    Build left-to-right cascade panels following hover (flyout when pointer is over a submenu row).
    Each panel: {"x","y","w","h","rows":[{"x","y","w","h","label_lines","node","has_children"}]}
    """
    mx, my = mouse_xy
    panels: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] | None = filtered_root
    x = min(max(8, sx), screen_w - max_panel_w - 8)
    y = min(max(8, sy), screen_h - 40)

    while nodes:
        rows_out: list[dict[str, Any]] = []
        mw = 140
        line_h = max(14, row_h - 2)
        row_specs: list[tuple[dict[str, Any], list[str], int, bool]] = []
        for node in nodes:
            label = str(node.get("label", ""))
            lines = wrap_label_text(label, max_panel_w - 24, measure)
            rh = max(row_h, len(lines) * line_h + 6)
            for ln in lines:
                mw = max(mw, measure(ln) + 28)
            typ = str(node.get("type", "action"))
            ch = node.get("children") if typ == "submenu" else None
            has_ch = isinstance(ch, list) and len(ch) > 0
            row_specs.append((node, lines, rh, has_ch))
        mw = min(max_panel_w, max(140, mw))
        cur_y = y + pad
        for node, lines, rh, has_ch in row_specs:
            rows_out.append(
                {
                    "x": x + 2,
                    "y": cur_y,
                    "w": mw - 4,
                    "h": rh,
                    "label_lines": lines,
                    "node": node,
                    "has_children": has_ch,
                }
            )
            cur_y += rh
        h = min(screen_h - y - 8, cur_y - y + pad)
        panel = {"x": x, "y": y, "w": mw, "h": h, "rows": rows_out}
        panels.append(panel)

        hovered_children: list[dict[str, Any]] | None = None
        for row in rows_out:
            rx, ry, rw, rh2 = row["x"], row["y"], row["w"], row["h"]
            if rx <= mx < rx + rw and ry <= my < ry + rh2 and row.get("has_children"):
                n = row["node"]
                hovered_children = n.get("children") if isinstance(n.get("children"), list) else []
                break
        if not hovered_children:
            break
        nodes = hovered_children
        nx = panel["x"] + panel["w"] + 2
        if nx + mw > screen_w - 8:
            nx = max(8, panel["x"] - mw - 2)
        x = nx
        y = min(max(8, y), screen_h - h - 8)

    return panels


def hit_test_panels(panels: list[dict[str, Any]], pos: tuple[int, int]) -> str | None:
    """Return action id for a leaf row hit (deepest matching panel wins)."""
    mx, my = pos
    for panel in reversed(panels):
        for row in panel.get("rows", []):
            rx, ry, rw, rh = row["x"], row["y"], row["w"], row["h"]
            if rx <= mx < rx + rw and ry <= my < ry + rh:
                node = row.get("node") or {}
                if str(node.get("type")) == "action":
                    return str(node.get("id", "")).strip() or None
    return None

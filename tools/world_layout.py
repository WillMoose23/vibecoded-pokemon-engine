# FEATURE-MAP-WORLD-001: proximity graph + render order for world_layout.json (map editor export).
from __future__ import annotations

import heapq
import json
import math
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def _node_aabb(n: dict[str, Any]) -> tuple[float, float, float, float]:
    """Map-editor world: widthPx/heightPx are map-tile spans (FEATURE-MAP-WORLD-008), not screen pixels."""
    x = float(n.get("worldX", 0))
    y = float(n.get("worldY", 0))
    w = float(n.get("widthPx", 1))
    h = float(n.get("heightPx", 1))
    return (x, y, x + w, y + h)


def aabb_separation(
    ax0: float,
    ay0: float,
    ax1: float,
    ay1: float,
    bx0: float,
    by0: float,
    bx1: float,
    by1: float,
) -> float:
    """Minimum distance between axis-aligned rectangles; 0 if overlapping or touching."""
    dx = 0.0
    if ax1 < bx0:
        dx = bx0 - ax1
    elif bx1 < ax0:
        dx = ax0 - bx1
    dy = 0.0
    if ay1 < by0:
        dy = by0 - ay1
    elif by1 < ay0:
        dy = ay0 - by1
    return float(math.hypot(dx, dy))


def _node_instance_id(n: dict[str, Any], fallback_index: int) -> str:
    u = str(n.get("nodeUuid", "")).strip()
    if u:
        return u
    mid = str(n.get("mapId", "")).strip()
    return f"{mid}__{fallback_index}" if mid else f"node_{fallback_index}"


def build_proximity_edges(nodes: list[dict[str, Any]], edge_snap_px: float) -> list[dict[str, Any]]:
    """O(n^2) spatial adjacency: edges when AABB separation <= edge_snap_px.

    edge_snap_px is a distance in the same units as node AABBs (map tiles in FEATURE-MAP-WORLD-008).
    JSON field distanceWorldPx uses the same unit (name retained for compatibility).
    """
    out: list[dict[str, Any]] = []
    n = len(nodes)
    for i in range(n):
        a = nodes[i]
        aid = _node_instance_id(a, i)
        ax0, ay0, ax1, ay1 = _node_aabb(a)
        for j in range(i + 1, n):
            b = nodes[j]
            bid = _node_instance_id(b, j)
            bx0, by0, bx1, by1 = _node_aabb(b)
            sep = aabb_separation(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1)
            if sep <= edge_snap_px:
                out.append(
                    {
                        "a": aid,
                        "b": bid,
                        "mapIdA": str(a.get("mapId", "")),
                        "mapIdB": str(b.get("mapId", "")),
                        "kind": "proximity",
                        "distanceWorldPx": round(sep, 4),
                    }
                )
    return out


def _adj_from_edges(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, list[tuple[str, float]]]:
    ids = [_node_instance_id(n, i) for i, n in enumerate(nodes)]
    graph: dict[str, list[tuple[str, float]]] = {i: [] for i in ids}
    for e in edges:
        a = str(e.get("a", ""))
        b = str(e.get("b", ""))
        w = float(e.get("distanceWorldPx", 1.0))
        if a in graph and b in graph:
            graph[a].append((b, max(w, 1e-6)))
            graph[b].append((a, max(w, 1e-6)))
    return graph


def dijkstra_distances(graph: dict[str, list[tuple[str, float]]], origin: str) -> dict[str, float]:
    dist: dict[str, float] = {k: math.inf for k in graph}
    if origin not in graph:
        return dist
    dist[origin] = 0.0
    pq: list[tuple[float, str]] = [(0.0, origin)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in graph[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def render_order_by_proximity(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    origin_instance_id: str | None,
) -> list[str]:
    """Deterministic order: instance ids by shortest-path weight from origin, then lexicographic id."""
    ids = [_node_instance_id(n, i) for i, n in enumerate(nodes)]
    if not ids:
        return []
    graph = _adj_from_edges(nodes, edges)
    origin = origin_instance_id if origin_instance_id in graph else ids[0]
    dist = dijkstra_distances(graph, origin)
    return sorted(ids, key=lambda iid: (dist.get(iid, math.inf), iid))


def composite_bounds(nodes: list[dict[str, Any]]) -> dict[str, float] | None:
    if not nodes:
        return None
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for n in nodes:
        ax0, ay0, ax1, ay1 = _node_aabb(n)
        min_x = min(min_x, ax0)
        min_y = min(min_y, ay0)
        max_x = max(max_x, ax1)
        max_y = max(max_y, ay1)
    if min_x == math.inf:
        return None
    return {"minWorldX": min_x, "minWorldY": min_y, "maxWorldX": max_x, "maxWorldY": max_y}


def build_export_dict(
    nodes: list[dict[str, Any]],
    *,
    edge_snap_px: float,
    origin_map_id: str | None,
    editor_tool_version: str,
    cam: dict[str, float] | None = None,
) -> dict[str, Any]:
    edges = build_proximity_edges(nodes, edge_snap_px)
    origin_inst: str | None = None
    if nodes:
        for i, n in enumerate(nodes):
            if origin_map_id and str(n.get("mapId", "")) == origin_map_id:
                origin_inst = _node_instance_id(n, i)
                break
        if origin_inst is None:
            origin_inst = _node_instance_id(nodes[0], 0)
    render_order = render_order_by_proximity(nodes, edges, origin_inst)
    payload: dict[str, Any] = {
        "version": SCHEMA_VERSION,
        "editorTool": editor_tool_version,
        "originMapId": origin_map_id or "",
        "originInstanceId": origin_inst or "",
        "edgeSnapPx": edge_snap_px,  # tile-space threshold (see FEATURE-MAP-WORLD-008)
        "nodes": copy_nodes_for_export(nodes),
        "edges": edges,
        "renderOrder": render_order,
    }
    b = composite_bounds(nodes)
    if b:
        payload["compositeBounds"] = b
    if cam:
        payload["editorCamera"] = dict(cam)
    return payload


def copy_nodes_for_export(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Export stable instanceId (for edges/renderOrder) plus map geometry fields."""
    out: list[dict[str, Any]] = []
    for i, n in enumerate(nodes):
        inst = _node_instance_id(n, i)
        d = {k: v for k, v in n.items() if k != "nodeUuid"}
        d["instanceId"] = inst
        out.append(d)
    return out


def write_world_layout_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def read_world_layout_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

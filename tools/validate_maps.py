#!/usr/bin/env python3
"""
Validate src/tilesets.json and all src/maps/*.json (stdlib only).

Usage: python3 tools/validate_maps.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TILESETS_PATH = ROOT / "src" / "tilesets.json"
MAPS_DIR = ROOT / "src" / "maps"
MAPS_INDEX_NAME = "maps_index.json"


def fail(msg: str) -> None:
    print("error:", msg, file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not TILESETS_PATH.is_file():
        fail(f"missing {TILESETS_PATH}")

    with open(TILESETS_PATH, encoding="utf-8") as f:
        reg = json.load(f)

    # FEATURE-MAP-013: editor-only keys (e.g. editorTilesetFolders) are ignored; only tilesets[] is validated.
    tilesets = reg.get("tilesets")
    if not isinstance(tilesets, list) or not tilesets:
        fail("tilesets.json: need non-empty tilesets array")

    ids = set()
    for i, t in enumerate(tilesets):
        if not isinstance(t, dict):
            fail(f"tilesets[{i}] must be object")
        tid = t.get("id")
        if not tid or not isinstance(tid, str):
            fail(f"tilesets[{i}]: missing string id")
        if tid in ids:
            fail(f"duplicate tileset id: {tid}")
        ids.add(tid)
        for key in ("image", "tileWidth", "tileHeight"):
            if key not in t:
                fail(f"tileset {tid}: missing {key}")
        img = ROOT / t["image"]
        if not img.is_file():
            fail(f"tileset {tid}: image not found: {t['image']}")

    if not MAPS_DIR.is_dir():
        print("no maps directory; tilesets only OK")
        return

    maps = sorted(
        p
        for p in MAPS_DIR.glob("*.json")
        if p.name != MAPS_INDEX_NAME and p.name != "world_layout.json"
    )
    if not maps:
        print("no map json files")
        _write_maps_index()
        return

    for path in maps:
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
        mid = m.get("id")
        if not mid or not isinstance(mid, str):
            fail(f"{path.name}: missing id")
        tsid = m.get("tilesetId")
        if tsid not in ids:
            fail(f"{path.name}: unknown tilesetId {tsid}")
        w, h = m.get("width"), m.get("height")
        if not isinstance(w, int) or not isinstance(h, int) or w < 1 or h < 1:
            fail(f"{path.name}: invalid width/height")
        layers = m.get("layers")
        if not isinstance(layers, dict):
            fail(f"{path.name}: layers must be object")

        has_tl = "tileLayers" in layers and isinstance(layers["tileLayers"], list)
        has_ground = "ground" in layers and isinstance(layers["ground"], list)
        has_cells = "groundCells" in layers and isinstance(layers["groundCells"], list)
        if has_tl and (has_ground or has_cells):
            fail(f"{path.name}: do not mix tileLayers with ground or groundCells")

        def validate_cell_grid(gc: object, label: str) -> None:
            if not isinstance(gc, list) or len(gc) != h:
                fail(f"{path.name}: {label} must have {h} rows")
            for ri, row in enumerate(gc):
                if not isinstance(row, list) or len(row) != w:
                    fail(f"{path.name}: {label} row {ri} width must be {w}")
                for ci, cell in enumerate(row):
                    if cell is None:
                        continue
                    if not isinstance(cell, dict):
                        fail(f"{path.name}: {label}[{ri}][{ci}] must be null or object")
                    cts = cell.get("ts")
                    ct = cell.get("t")
                    if not isinstance(cts, str) or cts not in ids:
                        fail(f"{path.name}: invalid ts in {label} at ({ri},{ci})")
                    if not isinstance(ct, int) or ct < 0:
                        fail(f"{path.name}: invalid t in {label} at ({ri},{ci})")

        if has_tl:
            tls = layers["tileLayers"]
            if len(tls) < 1:
                fail(f"{path.name}: tileLayers must be a non-empty array")
            seen_lids: set[str] = set()
            for ti, entry in enumerate(tls):
                if not isinstance(entry, dict):
                    fail(f"{path.name}: tileLayers[{ti}] must be object")
                lid = entry.get("id")
                if not isinstance(lid, str) or not lid:
                    fail(f"{path.name}: tileLayers[{ti}].id must be non-empty string")
                if lid in seen_lids:
                    fail(f"{path.name}: duplicate tileLayer id {lid!r}")
                seen_lids.add(lid)
                validate_cell_grid(entry.get("cells"), f"tileLayers[{ti}].cells")
        elif not has_ground and not has_cells:
            fail(f"{path.name}: need layers.tileLayers or layers.ground or layers.groundCells")

        if has_cells:
            validate_cell_grid(layers["groundCells"], "groundCells")

        if has_ground:
            g = layers["ground"]
            if len(g) != h:
                fail(f"{path.name}: ground must have {h} rows")
            for ri, row in enumerate(g):
                if not isinstance(row, list) or len(row) != w:
                    fail(f"{path.name}: row {ri} width must be {w}")
                for ci, cell in enumerate(row):
                    if not isinstance(cell, int) or cell < 0:
                        fail(f"{path.name}: invalid tile at ({ri},{ci})")

        def validate_bin_layer(name: str) -> None:
            if name not in layers:
                return
            arr = layers[name]
            if not isinstance(arr, list) or len(arr) != h:
                fail(f"{path.name}: {name} must have {h} rows")
            for ri, row in enumerate(arr):
                if not isinstance(row, list) or len(row) != w:
                    fail(f"{path.name}: {name} row {ri} width must be {w}")
                for ci, cell in enumerate(row):
                    if cell not in (0, 1):
                        fail(f"{path.name}: {name} at ({ri},{ci}) must be 0 or 1")

        validate_bin_layer("walkability")
        validate_bin_layer("transparent")
        conn = m.get("connections", {})
        if conn:
            for d in ("north", "south", "east", "west"):
                if d not in conn:
                    continue
                c = conn[d]
                if not isinstance(c, dict):
                    fail(f"{path.name}: connections.{d} must be object")
                for k in ("mapId", "entryTileX", "entryTileY"):
                    if k not in c:
                        fail(f"{path.name}: connections.{d} missing {k}")
        print("ok", path.relative_to(ROOT))

    _write_maps_index()
    print("validate_maps: all OK")


def _write_maps_index() -> None:
    """FEATURE-MAP-008: sync maps_index.json with validated map files."""
    maps: list[dict[str, str]] = []
    for path in sorted(MAPS_DIR.glob("*.json")):
        if path.name == MAPS_INDEX_NAME or path.name == "world_layout.json":
            continue
        try:
            with open(path, encoding="utf-8") as f:
                m = json.load(f)
            mid = m.get("id", path.stem)
            name = m.get("name", mid)
            maps.append({"id": str(mid), "name": str(name)})
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    out = {"version": 1, "maps": maps}
    idx_path = MAPS_DIR / MAPS_INDEX_NAME
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()

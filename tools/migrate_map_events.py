#!/usr/bin/env python3
"""FEATURE-MAP-096 Phase 1: one-time migration for map events and script JSON.

Normalizes map ``events[]`` (``interaction`` -> ``trigger``, default interact) and script
files (legacy ``actions[]`` -> canonical ``script_1`` array-of-one-key-objects).

Dry-run by default; pass ``--write`` to apply changes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPS_DIR = ROOT / "src" / "maps"
SKIP_MAP_NAMES = frozenset({"maps_index.json", "world_layout.json"})

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import event_script_schema as ess  # noqa: E402


def _script_path_for_event(script_obj: object) -> Path | None:
    if not isinstance(script_obj, dict):
        return None
    rel = str(script_obj.get("path", "")).strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    return (ROOT / "src" / "maps" / rel).resolve()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def migrate_script_file(path: Path, *, map_stem: str, write: bool) -> list[str]:
    """Migrate one script JSON file."""
    lines: list[str] = []
    rel = _display_path(path)
    if not path.is_file():
        lines.append(f"{rel}: skip (missing)")
        return lines
    try:
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return [f"{rel}: skip (cannot read: {e})"]

    if not isinstance(raw, dict):
        return [f"{rel}: skip (root not an object)"]

    mid = str(raw.get("map") or map_stem).strip() or map_stem
    migrated, changes = ess.migrate_script_document(raw, mid)
    if not changes:
        return lines
    for c in changes:
        lines.append(f"{rel}: {c}")

    if ess.script_documents_equal(raw, migrated):
        lines.append(f"{rel}: no structural diff after normalize (skipped write)")
        return lines

    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(migrated, f, indent=2)
            f.write("\n")
        lines.append(f"{rel}: wrote script JSON")
    else:
        lines.append(f"{rel}: would write script JSON (dry-run)")
    return lines


def migrate_map_file(map_path: Path, *, write: bool) -> list[str]:
    """Migrate one map JSON and its linked script files. Returns log lines."""
    lines: list[str] = []
    map_stem = map_path.stem
    try:
        with map_path.open(encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return [f"{map_path.name}: skip (cannot read JSON: {e})"]

    if not isinstance(doc, dict):
        return [f"{map_path.name}: skip (root not an object)"]

    map_changed = False
    evs = doc.get("events")
    if isinstance(evs, list):
        new_evs: list[object] = []
        for i, ev in enumerate(evs):
            if not isinstance(ev, dict):
                new_evs.append(ev)
                continue
            norm, ch = ess.normalize_map_event(ev)
            new_evs.append(norm)
            for c in ch:
                lines.append(f"{map_path.name} events[{i}]: {c}")
                map_changed = True
        if map_changed:
            doc = {**doc, "events": new_evs}

    if map_changed:
        if write:
            with map_path.open("w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2)
                f.write("\n")
            lines.append(f"{map_path.name}: wrote map JSON")
        else:
            lines.append(f"{map_path.name}: would write map JSON (dry-run)")

    if isinstance(evs, list):
        for ev in evs:
            if not isinstance(ev, dict):
                continue
            sp = _script_path_for_event(ev.get("script"))
            if sp is None:
                continue
            lines.extend(migrate_script_file(sp, map_stem=map_stem, write=write))

    return lines


def iter_map_paths(maps_dir: Path) -> list[Path]:
    if not maps_dir.is_dir():
        return []
    return sorted(p for p in maps_dir.glob("*.json") if p.name not in SKIP_MAP_NAMES)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate map events and script JSON to canonical shape.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply changes (default is dry-run only)",
    )
    parser.add_argument(
        "--maps-dir",
        type=Path,
        default=MAPS_DIR,
        help=f"Directory containing map JSON files (default: {MAPS_DIR})",
    )
    args = parser.parse_args(argv)
    write = bool(args.write)
    mode = "WRITE" if write else "DRY-RUN"
    print(f"migrate_map_events: {mode}", file=sys.stderr)

    maps = iter_map_paths(args.maps_dir)
    if not maps:
        print(f"No map JSON files under {args.maps_dir}", file=sys.stderr)
        return 1

    all_lines: list[str] = []
    for mp in maps:
        all_lines.extend(migrate_map_file(mp, write=write))

    if not all_lines:
        print("No migrations needed.", file=sys.stderr)
    else:
        for ln in all_lines:
            print(ln)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

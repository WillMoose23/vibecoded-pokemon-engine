#!/usr/bin/env python3
"""IMPROVEMENT-MAP-052: verify map script opcodes in op.cpp, meta, and map_view.cpp handlers."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OP_CPP = ROOT / "src" / "op.cpp"
MAP_VIEW_CPP = ROOT / "src" / "map_view.cpp"
META = ROOT / "tools" / "event_script_op_meta.json"
EXTRACT = Path(__file__).resolve().parent / "extract_map_script_ops.py"

OP_PATTERN = re.compile(r'if\s*\(\s*op\s*==\s*"([^"]+)"\s*\)')

MAP_VIEWER_OPS = (
    "walk_to_coords",
    "run_to_coords",
    "face_north",
    "face_south",
    "face_east",
    "face_west",
    "move_camera",
    "camera_zoom_in",
    "camera_zoom_out",
    "camera_follow_player",
)

# FEATURE-MAP-Phase-4: music + battle opcodes handled in tryMapViewerScriptOpcode_ (not walk/camera group).
MAP_VIEWER_EXTENDED_OPS = (
    "set_route_music",
    "play_music_once",
    "start_trainer_battle",
)


def _extract_ops_from_cpp(text: str) -> list[str]:
    seen: list[str] = []
    found: set[str] = set()
    for m in OP_PATTERN.finditer(text):
        name = m.group(1)
        if name not in found:
            found.add(name)
            seen.append(name)
    return seen


def _try_map_viewer_function_body(text: str) -> str:
    marker = "Game::tryMapViewerScriptOpcode_"
    idx = text.find(marker)
    if idx < 0:
        return ""
    start = text.find("{", idx)
    if start < 0:
        return ""
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return ""


def audit() -> list[str]:
    errs: list[str] = []
    if not OP_CPP.is_file():
        return [f"Missing {OP_CPP}"]
    if not MAP_VIEW_CPP.is_file():
        return [f"Missing {MAP_VIEW_CPP}"]
    if not META.is_file():
        return [f"Missing {META}"]

    op_text = OP_CPP.read_text(encoding="utf-8")
    mv_text = MAP_VIEW_CPP.read_text(encoding="utf-8")
    meta = json.loads(META.read_text(encoding="utf-8"))
    meta_ops = set(meta.get("ops", {}).keys()) if isinstance(meta.get("ops"), dict) else set()
    cpp_ops = set(_extract_ops_from_cpp(op_text))
    if meta_ops != cpp_ops:
        errs.append(f"meta vs op.cpp mismatch (run extract_map_script_ops.py): meta={len(meta_ops)} cpp={len(cpp_ops)}")

    viewer_body = _try_map_viewer_function_body(mv_text)
    if not viewer_body:
        errs.append("Could not locate Game::tryMapViewerScriptOpcode_ body in map_view.cpp")
    else:
        for op in MAP_VIEWER_OPS:
            if op not in ("walk_to_coords", "run_to_coords"):
                needle = f'if (op == "{op}")'
            else:
                needle = f'op == "{op}"'
            if needle not in viewer_body:
                errs.append(f"map_view.cpp missing handler for viewer opcode: {op}")
        for op in MAP_VIEWER_EXTENDED_OPS:
            if f'if (op == "{op}")' not in viewer_body:
                errs.append(f"map_view.cpp missing handler for viewer opcode: {op}")

    if "onWarp" not in mv_text or "onFacingHint" not in mv_text:
        errs.append("map_view.cpp missing onWarp or onFacingHint script callback wiring")
    if "tryMapViewerScriptStep" not in mv_text:
        errs.append("map_view.cpp missing tryMapViewerScriptStep registration")

    for op, ent in (meta.get("ops") or {}).items():
        if isinstance(ent, dict) and ent.get("status") == "implemented" and op not in cpp_ops:
            errs.append(f"meta marks {op} implemented but op.cpp has no dispatch")

    return errs


def main() -> int:
    r = subprocess.run(
        [sys.executable, str(EXTRACT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stdout or "", file=sys.stderr)
        print(r.stderr or "", file=sys.stderr)
        print("extract_map_script_ops.py failed", file=sys.stderr)
        return r.returncode

    errs = audit()
    if errs:
        for line in errs:
            print(line, file=sys.stderr)
        return 1
    print("audit_event_script_ops: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

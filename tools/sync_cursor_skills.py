#!/usr/bin/env python3
"""IMPROVEMENT-MAP-097: sync Cursor skill folders into the repo for git backup.

Copies ~/.cursor/skills/<name>/ → .cursor/skills/<name>/ (project root).
Repo-only skill folders are preserved; newer source files overwrite by mtime.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST_ROOT = ROOT / ".cursor" / "skills"
SOURCE_ROOT = Path.home() / ".cursor" / "skills"


def _sync_tree(src: Path, dst: Path) -> tuple[int, int]:
    copied = updated = 0
    for item in src.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(item, target)
            copied += 1
        elif item.stat().st_mtime > target.stat().st_mtime:
            shutil.copy2(item, target)
            updated += 1
    return copied, updated


def sync_skills() -> int:
    if not SOURCE_ROOT.is_dir():
        print(f"sync_cursor_skills: source missing: {SOURCE_ROOT}", file=sys.stderr)
        return 1
    DEST_ROOT.mkdir(parents=True, exist_ok=True)
    copied = updated = 0
    skill_dirs = sorted(p for p in SOURCE_ROOT.iterdir() if p.is_dir())
    for src_skill in skill_dirs:
        dst_skill = DEST_ROOT / src_skill.name
        if not dst_skill.exists():
            shutil.copytree(src_skill, dst_skill)
            n_files = sum(1 for f in src_skill.rglob("*") if f.is_file())
            copied += n_files
            continue
        c, u = _sync_tree(src_skill, dst_skill)
        copied += c
        updated += u
    total = sum(1 for _ in DEST_ROOT.iterdir() if _.is_dir())
    print(f"sync_cursor_skills: copied {copied}, updated {updated}, skill folders in repo {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(sync_skills())

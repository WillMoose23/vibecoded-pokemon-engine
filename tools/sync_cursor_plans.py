#!/usr/bin/env python3
"""IMPROVEMENT-MAP-096: sync Cursor plan files into the repo for git backup.

Copies ~/.cursor/plans/*.plan.md → .cursor/plans/ (project root).
Existing repo-only plans are kept; newer source files overwrite by mtime.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".cursor" / "plans"
SOURCE = Path.home() / ".cursor" / "plans"


def sync_plans() -> int:
    if not SOURCE.is_dir():
        print(f"sync_cursor_plans: source missing: {SOURCE}", file=sys.stderr)
        return 1
    DEST.mkdir(parents=True, exist_ok=True)
    copied = 0
    updated = 0
    for src in sorted(SOURCE.glob("*.plan.md")):
        dst = DEST / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
            copied += 1
        elif src.stat().st_mtime > dst.stat().st_mtime:
            shutil.copy2(src, dst)
            updated += 1
    total = len(list(DEST.glob("*.plan.md")))
    print(f"sync_cursor_plans: copied {copied}, updated {updated}, total in repo {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(sync_plans())

#!/usr/bin/env python3
"""Sync Cursor plans and skills from ~/.cursor into the repo before git push."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPERS = Path(__file__).resolve().parent


def main() -> int:
    scripts = ("sync_cursor_plans.py", "sync_cursor_skills.py")
    rc = 0
    for name in scripts:
        path = HELPERS / name
        proc = subprocess.run([sys.executable, str(path)], cwd=ROOT)
        if proc.returncode != 0:
            rc = proc.returncode
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

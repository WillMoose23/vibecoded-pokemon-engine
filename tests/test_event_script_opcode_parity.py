# IMPROVEMENT-MAP-052: opcode parity between meta, op.cpp, and map_view.cpp
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURSOR_SCRIPTS = ROOT / "docs" / "cursor_helper_scripts"


def _load_generated():
    p = ROOT / "tools" / "event_script_ops_generated.py"
    spec = importlib.util.spec_from_file_location("event_script_ops_generated_test", p)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load event_script_ops_generated")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEventScriptOpcodeParity(unittest.TestCase):
    def test_extract_script_ops_exits_zero(self) -> None:
        r = subprocess.run(
            [sys.executable, str(CURSOR_SCRIPTS / "extract_map_script_ops.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)

    def test_audit_event_script_ops_exits_zero(self) -> None:
        r = subprocess.run(
            [sys.executable, str(CURSOR_SCRIPTS / "audit_event_script_ops.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)

    def test_generated_matches_meta_count(self) -> None:
        import json

        gen = _load_generated()
        meta = json.loads((ROOT / "tools" / "event_script_op_meta.json").read_text(encoding="utf-8"))
        meta_ops = set(meta["ops"].keys())
        self.assertEqual(set(gen.CPP_SCRIPT_OPS_ORDERED), meta_ops)


if __name__ == "__main__":
    unittest.main()

# Phase 4: C++ runtime smoke tests wired through Makefile (FEATURE-MAP-096).
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestScriptRuntimeMake(unittest.TestCase):
    def test_make_test_script_runtime(self) -> None:
        r = subprocess.run(
            ["make", "test-script-runtime"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        self.assertIn("all checks passed", r.stdout)

    def test_make_test_game_state(self) -> None:
        r = subprocess.run(
            ["make", "test-game-state"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        self.assertIn("all checks passed", r.stdout)


if __name__ == "__main__":
    unittest.main()

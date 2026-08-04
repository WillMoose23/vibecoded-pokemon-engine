# FEATURE-MAP-056: K stride snap helpers
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    p = ROOT / "tools" / "wild_encounter_editor_helpers.py"
    spec = importlib.util.spec_from_file_location("wild_helpers_test", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


class TestWildStrideSnap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = _load()

    def test_stride_ok_with_draw_offset(self) -> None:
        self.assertTrue(self.h.player_stride_grid_ok(1, 0, 2, 2, 1))
        self.assertFalse(self.h.player_stride_grid_ok(0, 0, 2, 2, 1))

    def test_snap_nearest(self) -> None:
        sx, sy = self.h.snap_cell_to_stride_grid(3, 1, 2, 2, 1)
        self.assertTrue(self.h.player_stride_grid_ok(sx, sy, 2, 2, 1))


if __name__ == "__main__":
    unittest.main()

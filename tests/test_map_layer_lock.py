"""FEATURE-MAP-103: tile layer lock blocks paint edits."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import pygame

pygame.init()


class TestMapLayerLock(unittest.TestCase):
    def _minimal_editor(self):
        from map_editor import MapEditor

        ed = MagicMock(spec=MapEditor)
        ed.map_w = 4
        ed.map_h = 4
        ed.brush_pattern = [["ts1", 1]]
        ed.tile_layers = [[[None for _ in range(4)] for _ in range(4)]]
        ed.tile_layer_ids = ["ground"]
        ed.tile_layer_locked = [False]
        ed.active_layer_index = 0
        ed.set_status = MagicMock()

        def active_grid():
            return ed.tile_layers[ed.active_layer_index]

        def active_locked():
            if not ed.tile_layer_locked:
                return False
            return bool(ed.tile_layer_locked[ed.active_layer_index])

        ed._active_grid = active_grid
        ed._active_layer_locked = active_locked

        def apply_brush_at(cx, cy, erase):
            if ed._active_layer_locked():
                ed.set_status("Layer locked.", kind="info")
                return
            g = ed._active_grid()
            if erase:
                g[cy][cx] = None
            else:
                g[cy][cx] = {"ts": "ts1", "t": 1}

        ed.apply_brush_at = apply_brush_at
        return ed

    def test_locked_layer_blocks_paint(self) -> None:
        ed = self._minimal_editor()
        ed.tile_layer_locked[0] = True
        ed.apply_brush_at(1, 1, False)
        self.assertIsNone(ed.tile_layers[0][1][1])
        ed.set_status.assert_called_with("Layer locked.", kind="info")

    def test_unlocked_layer_paints(self) -> None:
        ed = self._minimal_editor()
        ed.apply_brush_at(1, 1, False)
        self.assertEqual(ed.tile_layers[0][1][1], {"ts": "ts1", "t": 1})


if __name__ == "__main__":
    unittest.main()

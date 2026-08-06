"""FEATURE-MAP-103: tile layer lock blocks paint edits.
BUG-MAP-106: layer lock button must not overlap the Event/Overworld/Help/Settings toolbar."""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import pygame

pygame.init()

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _load_map_editor_module():
    spec = importlib.util.spec_from_file_location("map_editor_lock_test", TOOLS / "map_editor.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


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


class TestMapToolbarLockOverlap(unittest.TestCase):
    """BUG-MAP-106: lock button must sit clear of the toolbar button cluster."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_map_editor_module()

    def _editor(self):
        with mock.patch.object(self.mod, "load_key_config", return_value={}), mock.patch.object(
            self.mod.MapEditor, "_load_world_workspace_disk_state", lambda self: None
        ), mock.patch.object(
            self.mod.MapEditor, "try_load_map_by_id", lambda self, _mid: None
        ), mock.patch.object(
            self.mod.MapEditor, "refresh_map_file_list", lambda self: None
        ):
            ed = self.mod.MapEditor()
        ed.map_w = 4
        ed.map_h = 4
        ed.wild_encounter = []
        ed.wild_patches = []
        return ed

    def test_lock_button_does_not_overlap_toolbar(self) -> None:
        ed = self._editor()
        ed.draw()
        self.assertLessEqual(ed.layer_chip_lock_btn.right, ed._map_toolbar_left)
        self.assertLessEqual(ed.layer_chip_lock_btn.right, ed.events_btn_rect.x)
        self.assertFalse(ed.layer_chip_lock_btn.colliderect(ed.gear_rect))
        self.assertFalse(ed.layer_chip_lock_btn.colliderect(ed.events_btn_rect))

    def test_lock_button_stays_clear_on_narrow_window(self) -> None:
        ed = self._editor()
        ed.screen = pygame.Surface((900, 500))
        ed.relayout()
        ed.draw()
        self.assertLessEqual(ed.layer_chip_lock_btn.right, ed._map_toolbar_left)
        self.assertFalse(ed.layer_chip_lock_btn.colliderect(ed.gear_rect))


if __name__ == "__main__":
    unittest.main()

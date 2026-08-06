"""FEATURE-MAP-111 / BUG-MAP-107: sidebar layer panel and lock session cache."""
from __future__ import annotations

import copy
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
    spec = importlib.util.spec_from_file_location("map_editor_panel_test", TOOLS / "map_editor.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestLayerInsertHelper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_map_editor_module()

    def _editor(self):
        with mock.patch.object(self.mod, "load_key_config", return_value={}), mock.patch.object(
            self.mod.MapEditor, "_load_world_workspace_disk_state", lambda self: None
        ), mock.patch.object(self.mod.MapEditor, "try_load_map_by_id", lambda self, _mid: None), mock.patch.object(
            self.mod.MapEditor, "refresh_map_file_list", lambda self: None
        ):
            ed = self.mod.MapEditor()
        ed.map_w = 4
        ed.map_h = 4
        ed.tile_layers = [
            [[None for _ in range(4)] for _ in range(4)],
            [[None for _ in range(4)] for _ in range(4)],
            [[None for _ in range(4)] for _ in range(4)],
        ]
        ed.tile_layer_ids = ["ground", "decor", "event"]
        ed.tile_layer_locked = [False, False, False]
        ed.active_layer_index = 0
        ed.wild_encounter = []
        ed.wild_patches = []
        ed.set_status = MagicMock()
        ed._undo_checkpoint = MagicMock()
        return ed

    def test_insert_before_event(self) -> None:
        ed = self._editor()
        grid = [[None for _ in range(4)] for _ in range(4)]
        ed._insert_tile_layer_at(2, grid, "new_layer")
        self.assertEqual(ed.tile_layer_ids, ["ground", "decor", "new_layer", "event"])
        self.assertEqual(ed.active_layer_index, 2)

    def test_add_tile_layer_inserts_before_event(self) -> None:
        ed = self._editor()
        ed.add_tile_layer()
        self.assertEqual(ed.tile_layer_ids[-1], "event")
        self.assertEqual(ed.tile_layer_ids[-2], "layer_1")

    def test_paste_inserts_above_ground_minimum(self) -> None:
        ed = self._editor()
        ed.active_layer_index = 0
        ed._layer_clipboard = copy.deepcopy(ed.tile_layers[0])
        ed._paste_tile_layer()
        self.assertEqual(ed.tile_layer_ids[0], "ground")
        self.assertEqual(ed.tile_layer_ids[1], "layer_1")

    def test_ground_delete_blocked(self) -> None:
        ed = self._editor()
        ed.tile_layers = [[[None for _ in range(4)] for _ in range(4)]]
        ed.tile_layer_ids = ["ground"]
        ed.tile_layer_locked = [False]
        ed._remove_tile_layer_at(0)
        ed.set_status.assert_called_with('Cannot remove "ground" layer.', kind="err")

    def test_sidebar_visible_excludes_event(self) -> None:
        ed = self._editor()
        self.assertEqual(ed._sidebar_visible_layer_indices(), [0, 1])


class TestSessionLockCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_map_editor_module()

    def test_session_bundle_roundtrip_lock(self) -> None:
        with mock.patch.object(self.mod, "load_key_config", return_value={}), mock.patch.object(
            self.mod.MapEditor, "_load_world_workspace_disk_state", lambda self: None
        ), mock.patch.object(self.mod.MapEditor, "try_load_map_by_id", lambda self, _mid: None), mock.patch.object(
            self.mod.MapEditor, "refresh_map_file_list", lambda self: None
        ):
            ed = self.mod.MapEditor()
        ed.map_w = 4
        ed.map_h = 4
        ed.tile_layers = [[[None for _ in range(4)] for _ in range(4)]]
        ed.tile_layer_ids = ["ground"]
        ed.tile_layer_locked = [True]
        ed.walk = [[0] * 4 for _ in range(4)]
        ed.trans = [[0] * 4 for _ in range(4)]
        ed.over_player = [[0] * 4 for _ in range(4)]
        ed.wild_encounter = []
        ed.wild_patches = []
        bundle = ed._snapshot_session_map_bundle()
        ed.tile_layer_locked = [False]
        ed._restore_session_map_bundle(bundle)
        self.assertEqual(ed.tile_layer_locked, [True])

    def test_toggle_lock_after_sync(self) -> None:
        ed = MagicMock()
        ed.tile_layers = [[], []]
        ed.tile_layer_ids = ["ground", "layer_1"]
        ed.tile_layer_locked = [False]
        ed.set_status = MagicMock()

        def sync():
            n = len(ed.tile_layers)
            if len(ed.tile_layer_locked) < n:
                ed.tile_layer_locked.extend([False] * (n - len(ed.tile_layer_locked)))

        def toggle(li):
            sync()
            ed.tile_layer_locked[li] = not ed.tile_layer_locked[li]

        ed._sync_tile_layer_locked_len = sync
        ed._toggle_tile_layer_lock = toggle
        ed._toggle_tile_layer_lock(1)
        self.assertTrue(ed.tile_layer_locked[1])


class TestTilesetListHitSubRect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_map_editor_module()

    def test_hit_outside_tilesets_list_is_none(self) -> None:
        with mock.patch.object(self.mod, "load_key_config", return_value={}), mock.patch.object(
            self.mod.MapEditor, "_load_world_workspace_disk_state", lambda self: None
        ), mock.patch.object(self.mod.MapEditor, "try_load_map_by_id", lambda self, _mid: None), mock.patch.object(
            self.mod.MapEditor, "refresh_map_file_list", lambda self: None
        ):
            ed = self.mod.MapEditor()
        ed.relayout()
        ed.draw()
        layout = ed._sidebar_layout
        layers_list = layout["layers_list"]
        hit, _ = ed._tileset_list_hit(layers_list.centerx, layers_list.centery)
        self.assertEqual(hit, "none")


if __name__ == "__main__":
    unittest.main()

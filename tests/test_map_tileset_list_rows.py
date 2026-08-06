"""FEATURE-MAP-111 Phase 2: variable tileset list row heights and cumulative hit-test."""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import pygame

pygame.init()

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _load_map_editor_module():
    spec = importlib.util.spec_from_file_location("map_editor_ts_rows_test", TOOLS / "map_editor.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestTilesetListRowHeights(unittest.TestCase):
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
        ed.wild_encounter = []
        ed.wild_patches = []
        return ed

    def test_child_row_shorter_than_folder(self) -> None:
        ed = self._editor()
        folder = {"row_kind": "folder", "folder_id": "f1", "name": "Folder", "collapsed": False}
        child = {
            "row_kind": "tileset",
            "def_index": 1,
            "id": "child_ts",
            "indent_px": self.mod.TILESET_LIST_CHILD_INDENT_PX,
            "in_folder": "f1",
        }
        full = ed._tileset_list_row_height(folder)
        compact = ed._tileset_list_row_height(child)
        self.assertGreater(full, compact)
        self.assertEqual(compact, ed.font_small.get_linesize() + self.mod.TILESET_LIST_CHILD_ROW_EXTRA)

    def test_cumulative_layout_content_height(self) -> None:
        ed = self._editor()
        folder = {"row_kind": "folder", "folder_id": "f1", "name": "F", "collapsed": False}
        child = {
            "row_kind": "tileset",
            "def_index": 0,
            "id": "a",
            "indent_px": self.mod.TILESET_LIST_CHILD_INDENT_PX,
            "in_folder": "f1",
        }
        rows = [folder, child]
        offsets, heights, content_h = ed._tileset_list_row_layout(rows)
        self.assertEqual(offsets, [0, heights[0]])
        self.assertEqual(content_h, heights[0] + heights[1] + 8)

    def test_hit_test_uses_cumulative_y(self) -> None:
        ed = self._editor()
        ed.relayout()
        layout = ed._measure_tileset_sidebar_layout()
        list_r = layout["tilesets_list"]
        folder = {"row_kind": "folder", "folder_id": "f1", "name": "F", "collapsed": False}
        child = {
            "row_kind": "tileset",
            "def_index": 3,
            "id": "nested_ts",
            "indent_px": self.mod.TILESET_LIST_CHILD_INDENT_PX,
            "in_folder": "f1",
        }
        rows = [folder, child]

        def fake_rows():
            return rows

        ed._build_tileset_list_rows = fake_rows  # type: ignore[method-assign]
        ed.tileset_list_scroll_y = 0
        _, heights, _ = ed._tileset_list_row_layout(rows)
        child_mid_y = list_r.y + heights[0] + heights[1] // 2
        hit, payload = ed._tileset_list_hit(list_r.centerx, child_mid_y)
        self.assertEqual(hit, "tileset")
        self.assertEqual(payload, 3)

    def test_scroll_clamp_uses_variable_content_height(self) -> None:
        ed = self._editor()
        folder = {"row_kind": "folder", "folder_id": "f1", "name": "F", "collapsed": False}
        child = {
            "row_kind": "tileset",
            "def_index": 0,
            "id": "x",
            "indent_px": self.mod.TILESET_LIST_CHILD_INDENT_PX,
            "in_folder": "f1",
        }
        rows = [folder, child]

        def fake_rows():
            return rows

        ed._build_tileset_list_rows = fake_rows  # type: ignore[method-assign]
        ed.relayout()
        _, _, var_h = ed._tileset_list_row_layout(rows)
        uniform_h = len(rows) * ed._tileset_list_row_h() + 8
        self.assertLess(var_h, uniform_h)
        ed.tileset_list_scroll_y = 99999
        ed._clamp_tileset_list_scroll()
        layout = ed._sidebar_layout
        list_r = layout["tilesets_list"]
        max_scroll = max(0, var_h - list_r.h)
        self.assertEqual(ed.tileset_list_scroll_y, max_scroll)


if __name__ == "__main__":
    unittest.main()

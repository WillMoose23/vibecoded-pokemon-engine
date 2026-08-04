# Phase 3 Event Engine: mini-map tile math and session undo snapshot (stdlib unittest).
from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pygame

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eem = _load("event_engine_modal", TOOLS / "event_engine_modal.py")
_FOOTPRINT = eem._FOOTPRINT


class TestMiniMapTileAt(unittest.TestCase):
    def _engine(self) -> eem.EventEngineModal:
        ed = MagicMock()
        ed.set_status = MagicMock()
        ed._thumbnail_surface_for_map_stem = MagicMock(return_value=None)
        ed.map_dims = MagicMock(return_value=(20, 15))
        eng = eem.EventEngineModal(ed)
        eng._mini_draw_rect = pygame.Rect(100, 50, 200, 150)
        eng._mini_map_w = 20
        eng._mini_map_h = 15
        return eng

    def test_center_click_maps_to_tile(self) -> None:
        eng = self._engine()
        cx = eng._mini_draw_rect.centerx
        cy = eng._mini_draw_rect.centery
        tile = eng._mini_map_tile_at(cx, cy)
        self.assertIsNotNone(tile)
        tx, ty = tile  # type: ignore[misc]
        self.assertGreaterEqual(tx, 0)
        self.assertLess(tx, eng._mini_map_w)
        self.assertGreaterEqual(ty, 0)
        self.assertLess(ty, eng._mini_map_h)

    def test_outside_returns_none(self) -> None:
        eng = self._engine()
        self.assertIsNone(eng._mini_map_tile_at(0, 0))

    def test_corner_clamps_footprint(self) -> None:
        eng = self._engine()
        tile = eng._mini_map_tile_at(eng._mini_draw_rect.right - 1, eng._mini_draw_rect.bottom - 1)
        self.assertIsNotNone(tile)
        tx, ty = tile  # type: ignore[misc]
        self.assertLessEqual(tx, eng._mini_map_w - _FOOTPRINT)
        self.assertLessEqual(ty, eng._mini_map_h - _FOOTPRINT)


class TestSessionUndoSnapshot(unittest.TestCase):
    def test_restore_reverts_events_and_flows(self) -> None:
        ed = MagicMock()
        ed.set_status = MagicMock()
        ed._thumbnail_surface_for_map_stem = MagicMock(return_value=None)
        ed.map_dims = MagicMock(return_value=(0, 0))
        eng = eem.EventEngineModal(ed)
        eng.events = [{"id": "a", "anchor": {"x": 0, "y": 0}}]
        eng.flows = {"main": [{"op": "show_message", "args": {"text": "hi"}, "children": []}]}
        eng.active_flow = "main"
        eng.sel_event_index = 0
        eng.sel_map_id = "test_map"
        snap = eng._session_snapshot()
        eng.events[0]["id"] = "b"
        eng.flows["main"][0]["args"]["text"] = "changed"
        eng._session_restore(snap)
        self.assertEqual(eng.events[0]["id"], "a")
        self.assertEqual(eng.flows["main"][0]["args"]["text"], "hi")

    def test_checkpoint_clears_redo(self) -> None:
        ed = MagicMock()
        ed.set_status = MagicMock()
        ed._thumbnail_surface_for_map_stem = MagicMock(return_value=None)
        ed.map_dims = MagicMock(return_value=(0, 0))
        eng = eem.EventEngineModal(ed)
        eng._redo_stack.append({"events": [], "flows": {"main": []}, "active_flow": "main",
                                "open_tabs": ["main"], "sel_event_index": None,
                                "sel_map_id": None, "events_dirty": False, "script_dirty": False})
        eng._undo_checkpoint()
        self.assertEqual(eng._redo_stack, [])


if __name__ == "__main__":
    unittest.main()

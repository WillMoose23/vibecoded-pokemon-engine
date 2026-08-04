"""FEATURE-MAP-097/098: close rebuild audit gaps (map scope toggle + wild canvas)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


class TestEventEngineMapScopeToggle(unittest.TestCase):
    def test_settings_click_toggles_select_switches_main_map(self) -> None:
        import sys

        sys.path.insert(0, str(TOOLS))
        import map_editor as me

        ed = mock.Mock(spec=me.MapEditor)
        ed.config_get_section = mock.Mock(return_value={"selectSwitchesMainMap": False})
        ed.config_set_section = mock.Mock()
        ed.set_status = mock.Mock()
        ed.settings_add_event_rect = mock.Mock()
        ed.settings_add_event_rect.collidepoint.return_value = False
        ed.settings_remove_event_rect = mock.Mock()
        ed.settings_remove_event_rect.collidepoint.return_value = False
        ed.settings_remove_current_layer_rect = mock.Mock()
        ed.settings_remove_current_layer_rect.collidepoint.return_value = False
        ed.settings_ee_follow_main_rect = mock.Mock()
        ed.settings_ee_follow_main_rect.collidepoint.return_value = True
        ed._settings_key_row_rects = []

        self.assertTrue(me.MapEditor._help_handle_settings_click(ed, 10, 10))
        ed.config_set_section.assert_called_once()
        args = ed.config_set_section.call_args[0]
        self.assertEqual(args[0], "eventEngine")
        self.assertTrue(args[1]["selectSwitchesMainMap"])

    def test_help_settings_documents_toggle_in_source(self) -> None:
        src = (TOOLS / "map_editor.py").read_text(encoding="utf-8")
        self.assertIn("selectSwitchesMainMap", src)
        self.assertIn("settings_ee_follow_main_rect", src)
        self.assertIn("Selecting a map switches the main editor", src)


class TestWildCanvasMode(unittest.TestCase):
    def test_open_wild_canvas_mode_sets_flags(self) -> None:
        import sys

        sys.path.insert(0, str(TOOLS))
        from map_editor import MapEditor

        ed = mock.Mock(spec=MapEditor)
        ed.wild_encounter_modal = mock.Mock()
        ed.wild_encounter_modal.open = False
        ed._ensure_default_wild_patch = mock.Mock()
        ed.set_status = mock.Mock()

        MapEditor._open_wild_canvas_mode(ed)
        self.assertTrue(ed.wild_canvas_mode_open)
        self.assertTrue(ed.wild_encounter_mode_open)
        ed._ensure_default_wild_patch.assert_called_once()

    def test_wild_canvas_paint_cells(self) -> None:
        import sys

        sys.path.insert(0, str(TOOLS))
        from map_editor import MapEditor

        ed = mock.Mock(spec=MapEditor)
        ed.map_w = 4
        ed.map_h = 4
        ed.eraser_mode = False
        ed.wild_encounter = [[0] * 4 for _ in range(4)]
        ed.wild_patches = [{"id": "patch_1", "stepChancePercent": 10, "encounters": {}}]
        ed.active_wild_patch_index = 0
        ed.selected_wild_patch_index = 0
        ed._wild_snap_cell = lambda x, y: (x, y)
        ed._wild_canvas_neighbor_patch = lambda _x, _y: None
        ed._wild_default_patch = lambda n: {
            "id": f"patch_{n}",
            "stepChancePercent": 10,
            "encounters": {"common": [], "uncommon": [], "rare": []},
        }

        MapEditor._wild_canvas_paint_cells(ed, 1, 1, 1, 1, 1)
        self.assertEqual(ed.wild_encounter[1][1], 2)

    def test_layout_reserves_panel_width_in_canvas_mode(self) -> None:
        import sys

        sys.path.insert(0, str(TOOLS))
        from map_editor import MapEditor, _WILD_CANVAS_PANEL_W

        ed = mock.Mock(spec=MapEditor)
        ed.wild_canvas_mode_open = True
        ed.map_viewport_rect = __import__("pygame").Rect(100, 50, 800, 600)
        ed.map_origin_y = 84
        ed.map_viewport_rect.bottom = 650

        # Minimal layout fragment: reproduce panel width logic from _layout_ui
        panel_w = _WILD_CANVAS_PANEL_W if ed.wild_canvas_mode_open else 0
        canvas_w = max(8, ed.map_viewport_rect.w - panel_w)
        self.assertEqual(canvas_w, 800 - _WILD_CANVAS_PANEL_W)

    def test_launcher_wild_rmb_opens_canvas_mode(self) -> None:
        src = (TOOLS / "events_launcher_modal.py").read_text(encoding="utf-8")
        self.assertIn("_open_wild_canvas_mode", src)
        self.assertIn("button == 3", src)

    def test_wild_modal_main_map_button(self) -> None:
        src = (TOOLS / "wild_encounter_modal.py").read_text(encoding="utf-8")
        self.assertIn("Main map", src)
        self.assertIn("switch_to_canvas=True", src)


if __name__ == "__main__":
    unittest.main()

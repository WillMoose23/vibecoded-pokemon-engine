"""BUG-MAP-096/097/098 + QA audit regression tests for map_editor.py."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _load_map_editor():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    sys.path.insert(0, str(TOOLS))
    import pygame

    pygame.init()
    spec = importlib.util.spec_from_file_location("map_editor_qa", TOOLS / "map_editor.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestWildCanvasQaAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_map_editor()

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

    def test_open_wild_canvas_allocates_grid(self):
        """BUG-MAP-096: wild canvas open must not leave wild_encounter empty."""
        ed = self._editor()
        with mock.patch.object(ed, "_sync_wild_data_for_map") as sync:
            sync.side_effect = lambda mid: ed._resize_wild_encounter_grid(ed.map_w, ed.map_h)
            ed._open_wild_canvas_mode()
        self.assertTrue(ed.wild_canvas_mode_open)
        sync.assert_called_once()
        ed._ensure_wild_encounter_grid()
        self.assertEqual(len(ed.wild_encounter), 4)
        self.assertEqual(len(ed.wild_encounter[0]), 4)
        ed.draw()

    def test_draw_after_resize_does_not_index_error(self):
        """BUG-MAP-097: wild grid tracks map dimensions."""
        ed = self._editor()
        ed._resize_wild_encounter_grid(4, 4)
        ed.wild_encounter[0][0] = 1
        ed.map_w = 6
        ed.map_h = 6
        ed._resize_wild_encounter_grid(6, 6)
        ed.wild_canvas_mode_open = True
        ed.draw()

    def test_session_snapshot_includes_wild_fields(self):
        """BUG-MAP-097: session cache carries wild encounter state."""
        ed = self._editor()
        ed._resize_wild_encounter_grid(4, 4)
        ed.wild_encounter[1][1] = 2
        ed.wild_patches = [{"id": "p1", "stepChancePercent": 5, "encounters": {}}]
        ed._wild_modal_dirty = True
        snap = ed._snapshot_session_map_bundle()
        self.assertIn("wild_encounter", snap)
        self.assertIn("wild_patches", snap)
        self.assertTrue(snap["wild_modal_dirty"])
        ed.wild_encounter = []
        ed.wild_patches = []
        ed._restore_session_map_bundle(snap)
        self.assertEqual(ed.wild_encounter[1][1], 2)
        self.assertEqual(len(ed.wild_patches), 1)

    def test_canvas_paint_marks_dirty_and_close_persists(self):
        """BUG-MAP-098: canvas edits persist on close."""
        ed = self._editor()
        ed.map_id = "qa_wild_test"
        ed._resize_wild_encounter_grid(4, 4)
        ed.wild_patches = [ed._wild_default_patch(1)]
        ed._wild_modal_dirty = False
        with tempfile.TemporaryDirectory() as tmp:
            maps_dir = Path(tmp) / "maps"
            maps_dir.mkdir()
            map_path = maps_dir / "qa_wild_test.json"
            map_path.write_text(
                json.dumps(
                    {
                        "version": 4,
                        "id": "qa_wild_test",
                        "name": "qa_wild_test",
                        "width": 4,
                        "height": 4,
                        "layers": {},
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(self.mod, "MAPS_DIR", maps_dir), mock.patch.object(
                ed, "_wild_snap_cell", lambda x, y: (x, y)
            ):
                ed._wild_canvas_paint_cells(0, 0, 0, 0, 1)
                self.assertTrue(ed._wild_modal_dirty)
                self.assertGreater(ed.wild_encounter[0][0], 0)
                ed._close_wild_canvas_mode()
            data = json.loads(map_path.read_text(encoding="utf-8"))
        layers = data.get("layers", {})
        self.assertIn("wildEncounter", layers)

    def test_write_map_json_includes_wild(self):
        """BUG-MAP-098: main Save writes wild fields."""
        ed = self._editor()
        ed.map_id = "qa_save_wild"
        ed.map_name = "qa_save_wild"
        ed.saved_once = True
        ed.tile_layers = [[[None for _ in range(4)] for _ in range(4)]]
        ed.tile_layer_ids = ["ground"]
        ed.walk = [[0] * 4 for _ in range(4)]
        ed.trans = [[0] * 4 for _ in range(4)]
        ed.over_player = [[0] * 4 for _ in range(4)]
        ed._resize_wild_encounter_grid(4, 4)
        ed.wild_encounter[0][0] = 1
        ed.wild_patches = [ed._wild_default_patch(1)]
        ed._wild_modal_dirty = True
        with tempfile.TemporaryDirectory() as tmp:
            maps_dir = Path(tmp) / "maps"
            maps_dir.mkdir()
            with mock.patch.object(self.mod, "MAPS_DIR", maps_dir), mock.patch.object(
                self.mod, "ensure_maps_dir", lambda: maps_dir.mkdir(exist_ok=True)
            ), mock.patch.object(self.mod, "write_maps_index", lambda: None):
                ed._write_map_json_to_disk("qa_save_wild")
            data = json.loads((maps_dir / "qa_save_wild.json").read_text(encoding="utf-8"))
        self.assertIn("wildPatches", data)
        self.assertIn("wildEncounter", data.get("layers", {}))

    def test_scaled_tile_cache_reuses_surface(self):
        ed = self._editor()
        ed.cell_px = 16
        fake_sheet = mock.Mock()
        fake_meta = {"columns": 1, "tw": 16, "th": 16, "margin": 0, "spacing": 0}
        tile_surf = mock.Mock()
        scaled = mock.Mock()
        fake_sheet.subsurface.return_value = tile_surf
        with mock.patch.object(ed, "ensure_sheet", return_value=(fake_sheet, fake_meta)), mock.patch.object(
            self.mod.pygame.transform, "scale", return_value=scaled
        ) as scale_fn:
            screen = mock.Mock()
            ed.blit_tile_scaled(screen, "ts1", 1, 0, 0, 16)
            ed.blit_tile_scaled(screen, "ts1", 1, 10, 10, 16)
        self.assertEqual(scale_fn.call_count, 1)


if __name__ == "__main__":
    unittest.main()

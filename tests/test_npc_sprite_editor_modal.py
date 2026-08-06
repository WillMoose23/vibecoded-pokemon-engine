"""Lightweight tests for NpcSpriteEditorModal wiring (FEATURE-MAP-100)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import pygame

pygame.init()


class TestNpcSpriteEditorModal(unittest.TestCase):
    def test_open_close_and_mirror_lock_default(self) -> None:
        from npc_sprite_editor_modal import NpcSpriteEditorModal

        ed = MagicMock()
        ed._graphics_dir_for_kind = MagicMock(return_value=MagicMock(is_dir=lambda: False, iterdir=lambda: iter([])))
        ed.font = pygame.font.SysFont(None, 16)
        ed.font_small = ed.font
        ed.screen = pygame.Surface((800, 600))
        ed.set_status = MagicMock()
        ed.events_launcher_modal = MagicMock()

        modal = NpcSpriteEditorModal(ed)
        self.assertFalse(modal.open)
        self.assertTrue(modal._mirror_lock)
        modal.open_modal()
        self.assertTrue(modal.open)
        self.assertTrue(modal._layer_surfaces)
        modal.close_modal()
        self.assertFalse(modal.open)

    def test_validate_sheet_via_helper(self) -> None:
        from npc_sprite_sheet_helpers import validate_sheet_dimensions

        ok, _ = validate_sheet_dimensions(128, 192)
        self.assertTrue(ok)

    def _make_modal(self) -> "NpcSpriteEditorModal":
        from npc_sprite_editor_modal import NpcSpriteEditorModal

        ed = MagicMock()
        ed._graphics_dir_for_kind = MagicMock(
            return_value=MagicMock(is_dir=lambda: False, iterdir=lambda: iter([]))
        )
        ed.font = pygame.font.SysFont(None, 16)
        ed.font_small = ed.font
        ed.screen = pygame.Surface((800, 600))
        ed.set_status = MagicMock()
        ed.events_launcher_modal = MagicMock()
        return NpcSpriteEditorModal(ed)

    def test_pixel_at_canvas_top_left(self) -> None:
        """Top-left corner of canvas maps to pixel (0, 0)."""
        modal = self._make_modal()
        modal._canvas_rect = pygame.Rect(100, 100, 384, 576)
        modal._cell_step_x = 384 / 32
        modal._cell_step_y = 576 / 48
        result = modal._pixel_at_canvas(100, 100)
        self.assertEqual(result, (0, 0))

    def test_pixel_at_canvas_bottom_right(self) -> None:
        """Bottom-right corner maps to the last pixel (31, 47)."""
        modal = self._make_modal()
        modal._canvas_rect = pygame.Rect(100, 100, 384, 576)
        modal._cell_step_x = 384 / 32
        modal._cell_step_y = 576 / 48
        result = modal._pixel_at_canvas(100 + 383, 100 + 575)
        self.assertEqual(result, (31, 47))

    def test_pixel_at_canvas_mid_row(self) -> None:
        """Middle of the grid returns correct coordinates with per-axis steps."""
        modal = self._make_modal()
        modal._canvas_rect = pygame.Rect(100, 100, 384, 576)
        step_x = 384 / 32  # 12.0
        step_y = 576 / 48  # 12.0
        modal._cell_step_x = step_x
        modal._cell_step_y = step_y
        px = 16
        py = 24
        mx = 100 + int(px * step_x) + 1
        my = 100 + int(py * step_y) + 1
        result = modal._pixel_at_canvas(mx, my)
        self.assertEqual(result, (16, 24))

    def test_pixel_at_canvas_nonsquare_aspect(self) -> None:
        """With a non-square canvas the old bug produced wrong Y; verify correct Y."""
        modal = self._make_modal()
        modal._canvas_rect = pygame.Rect(50, 50, 320, 480)
        modal._cell_step_x = 320 / 32  # 10.0
        modal._cell_step_y = 480 / 48  # 10.0
        mx = 50 + 15   # pixel x=1
        my = 50 + 475  # near bottom, pixel y=47
        result = modal._pixel_at_canvas(mx, my)
        self.assertEqual(result, (1, 47))

    def test_pixel_at_canvas_outside(self) -> None:
        """Click outside the canvas returns None."""
        modal = self._make_modal()
        modal._canvas_rect = pygame.Rect(100, 100, 384, 576)
        modal._cell_step_x = 384 / 32
        modal._cell_step_y = 576 / 48
        self.assertIsNone(modal._pixel_at_canvas(50, 50))
        self.assertIsNone(modal._pixel_at_canvas(100 + 384, 100))

    # FEATURE-MAP-106: default zoom 12, footer tracks canvas/reference height.

    def test_default_zoom_is_twelve(self) -> None:
        modal = self._make_modal()
        self.assertEqual(modal._zoom, 12)

    def test_footer_start_y_decreases_when_zoom_decreases(self) -> None:
        modal = self._make_modal()
        modal.open_modal()
        modal._zoom = 12
        modal.draw()
        y_high_zoom = modal._footer_start_y()
        modal._zoom = 6
        modal.draw()
        y_low_zoom = modal._footer_start_y()
        self.assertLess(y_low_zoom, y_high_zoom)

    # FEATURE-MAP-108: collapsible sprite search panel filtering.

    def test_filtered_sprite_names_no_query_returns_all(self) -> None:
        modal = self._make_modal()
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "player.png").write_bytes(b"")
            (tdp / "rival.png").write_bytes(b"")
            (tdp / "notes.txt").write_bytes(b"")
            modal.ed._graphics_dir_for_kind = MagicMock(return_value=tdp)
            names = modal._filtered_sprite_names()
        self.assertEqual(names, ["player.png", "rival.png"])

    def test_filtered_sprite_names_substring_match(self) -> None:
        modal = self._make_modal()
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "player.png").write_bytes(b"")
            (tdp / "rival.png").write_bytes(b"")
            (tdp / "nurse_joy.png").write_bytes(b"")
            modal.ed._graphics_dir_for_kind = MagicMock(return_value=tdp)
            modal._sprite_search_query = "RIV"
            names = modal._filtered_sprite_names()
        self.assertEqual(names, ["rival.png"])

    # FEATURE-MAP-109: rectangular selector + copy/paste.

    def test_copy_paste_round_trip(self) -> None:
        modal = self._make_modal()
        modal.open_modal()
        cw, ch = modal._cell_size()
        layer = modal._active_layer_surface()
        modal._frame_idx = 0
        modal._direction_idx = 0
        ox, oy = modal._active_cell_origin()
        color = (10, 20, 30, 255)
        for x in range(4):
            for y in range(3):
                layer.set_at((ox + x, oy + y), color)
        modal._selection_rect = (0, 0, 3, 2)
        modal._copy_selection()
        self.assertIsNotNone(modal._clipboard)
        self.assertEqual(modal._clipboard.get_size(), (4, 3))

        modal._frame_idx = 1
        modal._direction_idx = 0
        modal._last_canvas_pixel = (0, 0)
        modal._paste_clipboard()
        tx, ty = modal._active_cell_origin()
        for x in range(4):
            for y in range(3):
                self.assertEqual(layer.get_at((tx + x, ty + y)), color)

    def test_copy_with_no_selection_reports_status(self) -> None:
        modal = self._make_modal()
        modal._selection_rect = None
        modal._copy_selection()
        modal.ed.set_status.assert_called_with("No selection to copy.", kind="info")

    def test_paste_blocked_when_layer_locked(self) -> None:
        modal = self._make_modal()
        modal.open_modal()
        modal._clipboard = pygame.Surface((2, 2), pygame.SRCALPHA)
        modal._layer_locked[modal._active_layer_index] = True
        modal._paste_clipboard()
        modal.ed.set_status.assert_called_with("Layer locked.", kind="info")

    # FEATURE-MAP-110: Z/R undo-redo and Ctrl shortcuts.

    def _key_event(self, key: int, mod: int = 0, unicode: str = "") -> pygame.event.Event:
        return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod, unicode=unicode)

    def test_plain_z_undoes(self) -> None:
        modal = self._make_modal()
        modal.open_modal()
        modal._undo_stack.append(modal._snapshot_layers())
        modal._active_layer_surface().fill((1, 2, 3, 255))
        handled = modal.handle_key(self._key_event(pygame.K_z))
        self.assertTrue(handled)
        self.assertEqual(len(modal._redo_stack), 1)
        self.assertTrue(modal._dirty)

    def test_plain_r_redoes(self) -> None:
        modal = self._make_modal()
        modal.open_modal()
        modal._redo_stack.append(modal._snapshot_layers())
        handled = modal.handle_key(self._key_event(pygame.K_r))
        self.assertTrue(handled)
        self.assertEqual(len(modal._undo_stack), 1)
        self.assertTrue(modal._dirty)

    def test_ctrl_s_saves_without_prompt(self) -> None:
        modal = self._make_modal()
        modal.open = True
        modal._save_sheet = MagicMock()
        modal.handle_key(self._key_event(pygame.K_s, mod=pygame.KMOD_CTRL))
        modal._save_sheet.assert_called_once_with(save_as=False)

    def test_ctrl_shift_s_saves_as(self) -> None:
        modal = self._make_modal()
        modal.open = True
        modal._save_sheet = MagicMock()
        modal.handle_key(self._key_event(pygame.K_s, mod=pygame.KMOD_CTRL | pygame.KMOD_SHIFT))
        modal._save_sheet.assert_called_once_with(save_as=True)

    def test_plain_s_selects_select_tool_ctrl_s_does_not(self) -> None:
        modal = self._make_modal()
        modal.open = True
        modal._save_sheet = MagicMock()
        modal._active_tool = "paint"
        modal.handle_key(self._key_event(pygame.K_s, mod=pygame.KMOD_CTRL))
        self.assertEqual(modal._active_tool, "paint")
        modal.handle_key(self._key_event(pygame.K_s))
        self.assertEqual(modal._active_tool, "select")

    def test_ctrl_c_and_ctrl_v_dispatch_to_selection_helpers(self) -> None:
        modal = self._make_modal()
        modal.open = True
        modal._copy_selection = MagicMock()
        modal._paste_clipboard = MagicMock()
        modal.handle_key(self._key_event(pygame.K_c, mod=pygame.KMOD_CTRL))
        modal._copy_selection.assert_called_once()
        modal.handle_key(self._key_event(pygame.K_v, mod=pygame.KMOD_CTRL))
        modal._paste_clipboard.assert_called_once()


if __name__ == "__main__":
    unittest.main()

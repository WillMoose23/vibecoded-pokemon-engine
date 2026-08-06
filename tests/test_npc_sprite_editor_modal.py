"""Lightweight tests for NpcSpriteEditorModal wiring (FEATURE-MAP-100)."""
from __future__ import annotations

import os
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()

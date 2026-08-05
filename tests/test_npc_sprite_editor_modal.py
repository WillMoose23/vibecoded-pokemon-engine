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
        self.assertIsNotNone(modal._sheet)
        modal.close_modal()
        self.assertFalse(modal.open)

    def test_validate_sheet_via_helper(self) -> None:
        from npc_sprite_sheet_helpers import validate_sheet_dimensions

        ok, _ = validate_sheet_dimensions(128, 192)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()

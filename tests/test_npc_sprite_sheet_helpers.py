"""Unit tests for npc_sprite_sheet_helpers (FEATURE-MAP-100)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from npc_sprite_sheet_helpers import (
    DEFAULT_SHEET_H,
    DEFAULT_SHEET_W,
    blit_frame_into_rgba_sheet,
    cell_size_for_sheet,
    extract_frame_from_rgba_sheet,
    frame_grid_pos,
    frame_index,
    list_character_pngs,
    mirror_pixels_horizontal,
    sanitize_character_filename,
    sheet_dimensions_warning,
    validate_sheet_dimensions,
)


class TestNpcSpriteSheetHelpers(unittest.TestCase):
    def test_default_dimensions_valid(self) -> None:
        ok, msg = validate_sheet_dimensions(DEFAULT_SHEET_W, DEFAULT_SHEET_H)
        self.assertTrue(ok, msg)
        self.assertEqual(cell_size_for_sheet(DEFAULT_SHEET_W, DEFAULT_SHEET_H), (32, 48))

    def test_invalid_dimensions(self) -> None:
        ok, _ = validate_sheet_dimensions(127, 192)
        self.assertFalse(ok)
        ok, _ = validate_sheet_dimensions(0, 192)
        self.assertFalse(ok)

    def test_frame_index_and_grid_pos(self) -> None:
        self.assertEqual(frame_index("down", 0), 0)
        self.assertEqual(frame_index("left", 2), 6)
        self.assertEqual(frame_index("up", 3), 15)
        row, col, drow = frame_grid_pos(6)
        self.assertEqual((row, col, drow), (1, 2, 1))

    def test_mirror_pixels_horizontal(self) -> None:
        grid = [[(1, 0, 0, 255), (2, 0, 0, 255)], [(3, 0, 0, 255), (4, 0, 0, 255)]]
        out = mirror_pixels_horizontal(grid)
        self.assertEqual(out[0][0], (2, 0, 0, 255))
        self.assertEqual(out[1][1], (3, 0, 0, 255))

    def test_extract_and_blit_frame(self) -> None:
        sheet_w, sheet_h = 128, 192
        sheet = [[(0, 0, 0, 0) for _ in range(sheet_w)] for _ in range(sheet_h)]
        frame = [[(9, 9, 9, 255) for _ in range(32)] for _ in range(48)]
        blit_frame_into_rgba_sheet(sheet, frame, "down", 1, sheet_w, sheet_h)
        got = extract_frame_from_rgba_sheet(sheet, "down", 1, sheet_w, sheet_h)
        self.assertEqual(got[0][0], (9, 9, 9, 255))

    def test_sheet_dimensions_warning(self) -> None:
        self.assertIsNone(sheet_dimensions_warning(128, 192))
        self.assertIn("Non-standard", sheet_dimensions_warning(64, 96) or "")

    def test_sanitize_character_filename(self) -> None:
        self.assertTrue(sanitize_character_filename("NPC 19").endswith(".png"))
        self.assertNotIn("/", sanitize_character_filename("../evil.png"))

    def test_list_character_pngs_flat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (root / "b.txt").write_text("x", encoding="utf-8")
            names = list_character_pngs(root)
            self.assertEqual(names, ["a.png"])


if __name__ == "__main__":
    unittest.main()

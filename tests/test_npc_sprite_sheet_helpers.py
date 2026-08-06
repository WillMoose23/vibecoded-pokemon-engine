"""Tests for npc_sprite_sheet_helpers flood fill and composite (FEATURE-MAP-102)."""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import pygame

pygame.init()


class TestNpcSpriteSheetHelpers(unittest.TestCase):
    def test_flood_fill_opaque_region(self) -> None:
        from npc_sprite_sheet_helpers import flood_fill_surface

        surf = pygame.Surface((4, 4), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        for x in range(2):
            for y in range(2):
                surf.set_at((x, y), (100, 50, 50, 255))
        n = flood_fill_surface(surf, 0, 0, (200, 200, 200, 255))
        self.assertEqual(n, 4)
        self.assertEqual(surf.get_at((0, 0)), (200, 200, 200, 255))
        self.assertEqual(surf.get_at((2, 0)), (0, 0, 0, 0))

    def test_flood_fill_transparent_seed_noop(self) -> None:
        from npc_sprite_sheet_helpers import flood_fill_surface

        surf = pygame.Surface((2, 2), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        n = flood_fill_surface(surf, 0, 0, (255, 0, 0, 255))
        self.assertEqual(n, 0)

    def test_composite_visibility_order(self) -> None:
        from npc_sprite_sheet_helpers import composite_rgba_layers

        a = pygame.Surface((2, 2), pygame.SRCALPHA)
        a.fill((255, 0, 0, 128))
        b = pygame.Surface((2, 2), pygame.SRCALPHA)
        b.fill((0, 255, 0, 255))
        out = composite_rgba_layers([a, b], [True, True])
        px = out.get_at((0, 0))
        self.assertGreater(px[1], px[0])

    def test_composite_hides_layer(self) -> None:
        from npc_sprite_sheet_helpers import composite_rgba_layers

        a = pygame.Surface((2, 2), pygame.SRCALPHA)
        a.fill((255, 0, 0, 255))
        b = pygame.Surface((2, 2), pygame.SRCALPHA)
        b.fill((0, 255, 0, 255))
        out = composite_rgba_layers([a, b], [True, False])
        self.assertEqual(out.get_at((0, 0)), (255, 0, 0, 255))


if __name__ == "__main__":
    unittest.main()

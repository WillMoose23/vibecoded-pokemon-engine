"""FEATURE-MAP-096 Phase 8: SDL layout smoke + deferred runtime verification."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

# Must set before pygame / map_editor import.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
SRC = ROOT / "src"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import pygame  # noqa: E402

from map_editor import MapEditor  # noqa: E402

_UI_MIN_W = 640
_UI_MIN_H = 480
_WINDOW_SIZES = ((800, 600), (1280, 800))


def _panel_within_canvas(rect: pygame.Rect, canvas: pygame.Rect, *, min_w: int, min_h: int) -> None:
    """Panel must lie inside the canvas and respect UI-Standard minimums when space allows."""
    assert canvas.colliderect(rect), f"panel {rect} outside canvas {canvas}"
    eff_min_w = min(min_w, max(1, canvas.w - 8))
    eff_min_h = min(min_h, max(1, canvas.h - 8))
    assert rect.w >= eff_min_w, f"panel width {rect.w} < {eff_min_w}"
    assert rect.h >= eff_min_h, f"panel height {rect.h} < {eff_min_h}"


class TestPhase8SDLLayoutSmoke(unittest.TestCase):
    """Headless draw smoke at 800×600 and 1280×800 (Phase 7 manual matrix deferral)."""

    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()

    def _editor(self, w: int, h: int) -> MapEditor:
        ed = MapEditor()
        ed.screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        ed.relayout()
        return ed

    def test_satellite_modals_draw_without_clip(self) -> None:
        for w, h in _WINDOW_SIZES:
            with self.subTest(size=(w, h)):
                ed = self._editor(w, h)
                canvas = ed.screen.get_rect()
                cases: list[tuple[str, object]] = [
                    ("launcher", ed.events_launcher_modal),
                    ("engine", ed.event_engine_modal),
                    ("wild", ed.wild_encounter_modal),
                    ("audio", ed.audio_engine_modal),
                    ("battle", ed.battle_editor_modal),
                ]
                for _name, modal in cases:
                    for m in cases:
                        getattr(m[1], "close_modal", lambda: None)()
                    modal.open_modal()
                    ed.draw()
                    _panel_within_canvas(
                        modal.panel_rect,
                        canvas,
                        min_w=_UI_MIN_W,
                        min_h=_UI_MIN_H,
                    )

    def test_help_overlay_settings_and_home(self) -> None:
        for w, h in _WINDOW_SIZES:
            with self.subTest(size=(w, h)):
                ed = self._editor(w, h)
                canvas = ed.screen.get_rect()
                for tab in ("home", "settings"):
                    ed._close_help_overlay()
                    ed._open_help_overlay(tab=tab)
                    ed.draw()
                    _panel_within_canvas(
                        ed._help_panel_rect,
                        canvas,
                        min_w=min(360, canvas.w - 16),
                        min_h=min(280, canvas.h - 16),
                    )

    def test_map_undo_regression_when_modals_closed(self) -> None:
        ed = self._editor(800, 600)
        before = ed.walk[0][0]
        ed._undo_checkpoint()
        ed.walk[0][0] = 0 if before else 1
        ed.undo_map_edit()
        self.assertEqual(ed.walk[0][0], before)

    def test_world_workspace_draws_at_small_window(self) -> None:
        ed = self._editor(800, 600)
        ed.world_workspace_open = True
        ed.draw()
        self.assertTrue(ed.world_workspace_open)


class TestPhase8RuntimeSmoke(unittest.TestCase):
    """Deferred in-game trigger/battle verification via audit + source contracts."""

    def test_audit_event_script_ops_ok(self) -> None:
        r = subprocess.run(
            [sys.executable, "tools/audit_event_script_ops.py"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)
        self.assertIn("OK", r.stdout + r.stderr)

    def test_start_trainer_battle_handler_present(self) -> None:
        text = (SRC / "map_view.cpp").read_text(encoding="utf-8")
        self.assertIn("start_trainer_battle", text)
        self.assertIn("tryMapViewerScriptOpcode_", text)

    def test_trigger_interact_handlers_present(self) -> None:
        text = (SRC / "map_view.cpp").read_text(encoding="utf-8")
        for sym in ("tryStartNearby", "tryStepOn", "tryFireAuto"):
            self.assertIn(sym, text, msg=f"missing {sym}")

    def test_scripted_battle_rotation_helpers_present(self) -> None:
        text = (SRC / "game.cpp").read_text(encoding="utf-8")
        for sym in (
            "tryRotateScriptedBattle_",
            "updateScriptedBattleOhko_",
            "scriptedBattleTrainerIdx_",
        ):
            self.assertIn(sym, text, msg=f"missing {sym}")

    def test_cpp_runtime_tests_pass(self) -> None:
        r = subprocess.run(["make", "test"], cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)
        self.assertIn("all checks passed", r.stdout)


if __name__ == "__main__":
    unittest.main()

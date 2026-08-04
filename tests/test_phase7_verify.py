"""FEATURE-MAP-096 Phase 7: full automated verification matrix."""
from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _run(cmd: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


class TestPhase7AutomatedMatrix(unittest.TestCase):
    def test_make_build(self) -> None:
        r = _run(["make"])
        self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)

    def test_make_test_cpp(self) -> None:
        r = _run(["make", "test"])
        self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)
        self.assertIn("all checks passed", r.stdout)

    def test_extract_map_script_ops(self) -> None:
        r = _run([sys.executable, "tools/extract_map_script_ops.py"])
        self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)
        self.assertIn("38 ops", r.stdout)

    def test_audit_event_script_ops(self) -> None:
        r = _run([sys.executable, "tools/audit_event_script_ops.py"])
        self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)
        self.assertIn("OK", r.stdout)

    def test_validate_map_events(self) -> None:
        r = _run([sys.executable, "tools/validate_map_events.py"])
        self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)

    def test_migrate_map_events_dry_run(self) -> None:
        r = _run([sys.executable, "tools/migrate_map_events.py"])
        self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)
        combined = (r.stdout or "") + (r.stderr or "")
        self.assertIn("DRY-RUN", combined)

    def test_ast_parse_core_modals(self) -> None:
        for rel in ("tools/event_engine_modal.py", "tools/map_editor.py"):
            ast.parse((ROOT / rel).read_text(encoding="utf-8"))


class TestPhase7ManualMatrixProxy(unittest.TestCase):
    """Headless proxies for the Phase 7 manual UI matrix (interactive SDL deferred)."""

    def test_entry_launcher_symbols(self) -> None:
        src = (TOOLS / "map_editor.py").read_text(encoding="utf-8")
        for sym in ("_open_events_launcher", "_toggle_events_launcher", "open_events_launcher"):
            self.assertIn(sym, src)

    def test_event_engine_core_symbols(self) -> None:
        src = (TOOLS / "event_engine_modal.py").read_text(encoding="utf-8")
        for sym in ("_draw_mini_map", "_undo_stack", "_redo_stack", "event_script_ctx_menu"):
            self.assertIn(sym, src)

    def test_help_settings_and_search(self) -> None:
        src = (TOOLS / "map_editor.py").read_text(encoding="utf-8")
        self.assertIn('"settings"', src)
        self.assertIn("help_search", src)
        self.assertNotIn("settings_open", src)

    def test_satellite_modals_present(self) -> None:
        for name in (
            "events_launcher_modal.py",
            "wild_encounter_modal.py",
            "audio_engine_modal.py",
            "battle_editor_modal.py",
        ):
            self.assertTrue((TOOLS / name).is_file(), msg=name)

    def test_map_paint_gated_by_blocking_modal(self) -> None:
        src = (TOOLS / "map_editor.py").read_text(encoding="utf-8")
        self.assertIn("_any_blocking_modal_open()", src)


if __name__ == "__main__":
    unittest.main()

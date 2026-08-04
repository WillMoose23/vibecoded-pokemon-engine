"""FEATURE-MAP-096 Phase 6: legacy events workspace removal + launcher entry."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


class TestPhase6KeyConfig(unittest.TestCase):
    def test_default_key_is_open_events_launcher(self) -> None:
        import sys

        sys.path.insert(0, str(TOOLS))
        from map_editor import default_key_config

        cfg = default_key_config()
        self.assertIn("open_events_launcher", cfg)
        self.assertNotIn("toggle_events_workspace", cfg)
        self.assertEqual(cfg["open_events_launcher"], ["v"])

    def test_load_key_config_migrates_legacy_toggle(self) -> None:
        import sys

        sys.path.insert(0, str(TOOLS))
        import map_editor as me

        with mock.patch.object(me, "CONFIG_PATH") as cp:
            cp.is_file.return_value = True
            cp.__str__ = lambda _s: "/tmp/fake_config.json"  # type: ignore[method-assign]
            with mock.patch("builtins.open", mock.mock_open(read_data=json.dumps({
                "keys": {"toggle_events_workspace": ["v", "e"]}
            }))):
                cfg = me.load_key_config()
        self.assertEqual(cfg["open_events_launcher"], ["v", "e"])
        self.assertNotIn("toggle_events_workspace", cfg)


class TestPhase6LauncherEntry(unittest.TestCase):
    def test_legacy_workspace_symbols_removed_from_map_editor(self) -> None:
        src = (TOOLS / "map_editor.py").read_text(encoding="utf-8")
        for sym in (
            "events_workspace_open",
            "_draw_events_workspace_overlay",
            "_toggle_events_workspace",
            "_events_add_at",
        ):
            self.assertNotIn(sym, src, msg=f"legacy symbol still present: {sym}")

    def test_open_events_launcher_opens_hub(self) -> None:
        import sys

        sys.path.insert(0, str(TOOLS))
        from map_editor import MapEditor

        ed = mock.Mock(spec=MapEditor)
        ed.world_workspace_open = True
        ed.events_launcher_modal = mock.Mock()
        ed.set_status = mock.Mock()
        MapEditor._open_events_launcher(ed)
        self.assertFalse(ed.world_workspace_open)
        ed.events_launcher_modal.open_modal.assert_called_once()
        ed.set_status.assert_called_once()

    def test_toggle_events_launcher_closes_when_open(self) -> None:
        import sys

        sys.path.insert(0, str(TOOLS))
        from map_editor import MapEditor

        ed = mock.Mock(spec=MapEditor)
        ed.events_launcher_modal = mock.Mock()
        ed.events_launcher_modal.open = True
        ed.world_workspace_open = False
        ed.set_status = mock.Mock()
        MapEditor._toggle_events_launcher(ed)
        ed.events_launcher_modal.close_modal.assert_called_once()


if __name__ == "__main__":
    unittest.main()

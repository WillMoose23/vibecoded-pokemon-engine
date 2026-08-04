# FEATURE-MAP-096 Phase 1: migration helpers and migrate_map_events dry-run tests.
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ess = _load("event_script_schema", TOOLS / "event_script_schema.py")
migrate = _load("migrate_map_events", TOOLS / "migrate_map_events.py")


class TestNormalizeMapEvent(unittest.TestCase):
    def test_interaction_to_trigger(self) -> None:
        ev = {
            "id": "npc_1",
            "anchor": {"x": 0, "y": 0},
            "interaction": {"type": "talk", "keyHint": "Q"},
        }
        out, changes = ess.normalize_map_event(ev)
        self.assertNotIn("interaction", out)
        self.assertEqual(out["trigger"], {"type": "interact"})
        self.assertTrue(any("interaction" in c for c in changes))

    def test_default_trigger_when_missing(self) -> None:
        ev = {"id": "e1", "anchor": {"x": 1, "y": 1}}
        out, changes = ess.normalize_map_event(ev)
        self.assertEqual(out["trigger"], {"type": "interact"})
        self.assertTrue(any("default trigger" in c for c in changes))

    def test_preserves_existing_trigger(self) -> None:
        ev = {
            "id": "e1",
            "trigger": {"type": "step_on"},
            "interaction": {"type": "talk"},
        }
        out, changes = ess.normalize_map_event(ev)
        self.assertEqual(out["trigger"]["type"], "step_on")
        self.assertNotIn("interaction", out)
        self.assertTrue(any("removed obsolete" in c for c in changes))


class TestMigrateScriptDocument(unittest.TestCase):
    def test_actions_to_script1(self) -> None:
        doc = {
            "version": 1,
            "actions": [{"op": "show_message", "args": {"text": "hi"}}],
        }
        out, changes = ess.migrate_script_document(doc, "demo_map")
        self.assertIn("script_1", out)
        self.assertNotIn("actions", out)
        self.assertEqual(out["map"], "demo_map")
        steps = ess.document_to_steps(out)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["op"], "show_message")
        self.assertTrue(any("actions" in c for c in changes))

    def test_preserves_subflows(self) -> None:
        doc = {
            "version": 1,
            "map": "demo",
            "script_1": [{"show_message": {"text": "main"}}],
            "subflows": {"greet": [{"show_message": {"text": "sub"}}]},
        }
        out, _ = ess.migrate_script_document(doc, "demo")
        flows = ess.document_to_flows(out)
        self.assertEqual(len(flows["main"]), 1)
        self.assertEqual(len(flows["greet"]), 1)


class TestMigrateMapEventsCLI(unittest.TestCase):
    def test_dry_run_map_and_script(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            maps_dir = Path(td)
            scripts_dir = maps_dir / "scripts" / "test_map"
            scripts_dir.mkdir(parents=True)
            script_path = scripts_dir / "ev1.json"
            script_path.write_text(
                json.dumps({"version": 1, "actions": [{"op": "wait_frames", "args": {"n": 1}}]}),
                encoding="utf-8",
            )
            map_doc = {
                "version": 4,
                "width": 10,
                "height": 10,
                "events": [
                    {
                        "id": "ev1",
                        "anchor": {"x": 0, "y": 0},
                        "interaction": {"type": "talk"},
                        "script": {"path": "scripts/test_map/ev1.json"},
                    }
                ],
            }
            map_path = maps_dir / "test_map.json"
            map_path.write_text(json.dumps(map_doc), encoding="utf-8")

            lines = migrate.migrate_map_file(map_path, write=False)
            self.assertTrue(any("would write map JSON" in ln for ln in lines))
            self.assertTrue(any("interaction" in ln for ln in lines))
            # Dry-run must not modify files
            raw_map = json.loads(map_path.read_text())
            self.assertIn("interaction", raw_map["events"][0])

    def test_dry_run_script_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sp = Path(td) / "legacy.json"
            sp.write_text(
                json.dumps({"version": 1, "actions": [{"op": "wait_frames", "args": {"n": 1}}]}),
                encoding="utf-8",
            )
            lines = migrate.migrate_script_file(sp, map_stem="demo", write=False)
            self.assertTrue(any("would write script JSON" in ln for ln in lines))
            self.assertIn("actions", sp.read_text())


if __name__ == "__main__":
    unittest.main()

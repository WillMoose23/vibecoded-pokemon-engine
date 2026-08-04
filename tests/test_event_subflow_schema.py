# FEATURE-MAP-074..080: schema/validator tests for subflows, labels, triggers, and references.
from __future__ import annotations

import importlib.util
import sys
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
vme = _load("validate_map_events", TOOLS / "validate_map_events.py")


class TestSubflowSchema(unittest.TestCase):
    def test_flows_round_trip(self) -> None:
        flows = {
            "main": [
                {"op": "label", "args": {"name": "start"}},
                {"op": "region", "args": {"name": "Intro"}},
                {"op": "show_message", "args": {"text": "hi"}},
                {"op": "end_region", "args": {}},
                {"op": "call_subflow", "args": {"name": "greet", "vars": {"who": "Red"}}},
                {"op": "goto", "args": {"label": "start"}},
            ],
            "greet": [{"op": "show_message", "args": {"text": "hello"}}],
        }
        doc = ess.flows_to_document(flows, "demo")
        rt = ess.document_to_flows(doc)
        self.assertEqual(rt["main"], flows["main"])
        self.assertEqual(rt["greet"], flows["greet"])

    def test_labels_in_steps(self) -> None:
        steps = [
            {"op": "label", "args": {"name": "a"}},
            {"op": "label", "args": {"name": "b"}},
            {"op": "label", "args": {"name": "a"}},  # duplicate ignored
        ]
        self.assertEqual(ess.labels_in_steps(steps), ["a", "b"])

    def test_balanced_new_blocks(self) -> None:
        ok, _ = ess.validate_balanced([
            {"op": "if_var", "args": {"name": "x", "op": "==", "value": 1}},
            {"op": "region", "args": {}},
            {"op": "show_message", "args": {}},
            {"op": "end_region", "args": {}},
            {"op": "end_if_var", "args": {}},
        ])
        self.assertTrue(ok)
        bad, _ = ess.validate_balanced([{"op": "if_var", "args": {}}])
        self.assertFalse(bad)


class TestValidatorReferences(unittest.TestCase):
    def test_goto_unknown_label(self) -> None:
        doc = {"script_1": [{"goto": {"label": "missing"}}]}
        errs = vme._script_reference_errors(doc)
        self.assertTrue(any("missing" in e for e in errs), errs)

    def test_goto_known_label_ok(self) -> None:
        doc = {"script_1": [{"label": {"name": "here"}}, {"goto": {"label": "here"}}]}
        self.assertEqual(vme._script_reference_errors(doc), [])

    def test_call_subflow_in_file_ok(self) -> None:
        doc = {"script_1": [{"call_subflow": {"name": "greet"}}],
               "subflows": {"greet": [{"show_message": {"text": "hi"}}]}}
        self.assertEqual(vme._script_reference_errors(doc), [])

    def test_call_subflow_unknown(self) -> None:
        doc = {"script_1": [{"call_subflow": {"name": "nope_xyz"}}]}
        errs = vme._script_reference_errors(doc)
        self.assertTrue(any("nope_xyz" in e for e in errs), errs)


class TestTriggerValidation(unittest.TestCase):
    def test_bad_trigger_type(self) -> None:
        errs: list[str] = []
        vme._validate_event_trigger(Path("m.json"), "e", {"trigger": {"type": "weird"}}, errs)
        self.assertTrue(any("trigger.type" in e for e in errs), errs)

    def test_oncomplete_must_be_strings(self) -> None:
        errs: list[str] = []
        vme._validate_event_trigger(Path("m.json"), "e", {"onComplete": {"setFlags": [1]}}, errs)
        self.assertTrue(any("setFlags" in e for e in errs), errs)

    def test_valid_trigger(self) -> None:
        errs: list[str] = []
        vme._validate_event_trigger(
            Path("m.json"), "e",
            {"trigger": {"type": "on_condition", "condition": {"flag": "f", "set": True}},
             "clearedFlag": "e_cleared", "onComplete": {"setFlags": ["a"], "clearFlags": ["b"]}},
            errs,
        )
        self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main()

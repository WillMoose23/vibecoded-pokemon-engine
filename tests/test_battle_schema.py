"""FEATURE-MAP-088: battle library schema helpers."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import event_script_schema as ess


class TestBattleSchema(unittest.TestCase):
    def test_normalize_battle_def_bounds(self) -> None:
        raw = {
            "id": "test",
            "outcomeMode": "scripted_loss",
            "trainers": [
                {
                    "party": [
                        {"species": "Pikachu", "level": 99},
                        {"species": "X", "level": 0},
                    ]
                }
            ],
        }
        out = ess.normalize_battle_def(raw, "fallback")
        self.assertEqual(out["id"], "test")
        self.assertEqual(out["outcomeMode"], "scripted_loss")
        self.assertEqual(len(out["trainers"]), 1)
        party = out["trainers"][0]["party"]
        self.assertEqual(len(party), 2)
        self.assertEqual(party[0]["level"], 99)
        self.assertEqual(party[1]["level"], 1)

    def test_merge_battle_inline_overrides(self) -> None:
        base = ess.normalize_battle_def({"id": "b1", "music": "route"}, "b1")
        merged = ess.merge_battle_config(base, {"music": "battle_1", "outcomeMode": "scripted_win"})
        self.assertEqual(merged["music"], "battle_1")
        self.assertEqual(merged["outcomeMode"], "scripted_win")

    def test_list_library_battle_names_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            battles = Path(td) / "battles"
            battles.mkdir()
            (battles / "rival.json").write_text(json.dumps({"id": "rival"}), encoding="utf-8")
            orig = ess._BATTLES_DIR
            try:
                ess._BATTLES_DIR = battles
                self.assertEqual(ess.list_library_battle_names(), ["rival"])
            finally:
                ess._BATTLES_DIR = orig


if __name__ == "__main__":
    unittest.main()

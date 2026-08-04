# Phase 5: battle editor schema + normalize helpers.
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import event_script_schema as ess


class TestBattleEditorPhase5(unittest.TestCase):
    def test_two_trainer_normalize(self) -> None:
        raw = {
            "id": "gym",
            "trainers": [
                {"party": [{"species": "Pidgey", "level": 5}]},
                {"party": [{"species": "Rattata", "level": 7}, {"species": "Spearow", "level": 6}]},
            ],
        }
        out = ess.normalize_battle_def(raw, "gym")
        self.assertEqual(len(out["trainers"]), 2)
        self.assertEqual(len(out["trainers"][1]["party"]), 2)

    def test_scripted_loss_turns_preserved(self) -> None:
        raw = {"id": "loss_demo", "outcomeMode": "scripted_loss", "scriptedLossTurns": 3}
        out = ess.normalize_battle_def(raw, "loss_demo")
        self.assertEqual(out["outcomeMode"], "scripted_loss")
        self.assertEqual(out["scriptedLossTurns"], 3)


if __name__ == "__main__":
    unittest.main()

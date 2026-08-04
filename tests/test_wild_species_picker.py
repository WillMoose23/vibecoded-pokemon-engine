# FEATURE-MAP-053: wild encounter species list helpers
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_helpers():
    p = ROOT / "tools" / "wild_encounter_editor_helpers.py"
    spec = importlib.util.spec_from_file_location("wild_encounter_editor_helpers_test", p)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load wild_encounter_editor_helpers")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestWildSpeciesPicker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = _load_helpers()

    def test_favorites_sorted_first(self) -> None:
        keys = ["Zapdos", "Abomasnow", "Bidoof", "Pikachu"]
        fav = {"Pikachu", "Bidoof"}
        out = self.h.wild_species_display_list(keys, fav, "")
        self.assertEqual(out[:2], ["Bidoof", "Pikachu"])
        self.assertEqual(set(out[2:]), {"Abomasnow", "Zapdos"})

    def test_filter_case_insensitive(self) -> None:
        keys = ["Abomasnow", "Pikachu", "Bidoof"]
        out = self.h.wild_species_display_list(keys, set(), "pika")
        self.assertEqual(out, ["Pikachu"])

    def test_default_prefers_favorite(self) -> None:
        keys = ["Abomasnow", "Pikachu"]
        self.assertEqual(
            self.h.wild_species_default_for_new_row(keys, {"Pikachu"}),
            "Pikachu",
        )

    def test_default_fallback_first_key(self) -> None:
        keys = ["Abomasnow", "Pikachu"]
        self.assertEqual(self.h.wild_species_default_for_new_row(keys, set()), "Abomasnow")


if __name__ == "__main__":
    unittest.main()

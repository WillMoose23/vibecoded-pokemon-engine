# FEATURE-MAP-081: unit tests for palette sort, insert target, and library subflow discovery.
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


class TestSortPaletteOpsInCategory(unittest.TestCase):
    def test_opener_before_closer(self) -> None:
        ops = ["end_if", "if_flag", "show_message"]
        result = ess.sort_palette_ops_in_category(ops)
        idx_open = result.index("if_flag")
        idx_close = result.index("end_if")
        self.assertLess(idx_open, idx_close, "opener must come before closer")

    def test_non_block_ops_preserved(self) -> None:
        ops = ["show_message", "warp_player", "play_sound"]
        result = ess.sort_palette_ops_in_category(ops)
        self.assertEqual(result, ops, "non-block ops keep original order")

    def test_multiple_pairs(self) -> None:
        ops = ["end_repeat", "end_if", "if_flag", "repeat", "comment"]
        result = ess.sort_palette_ops_in_category(ops)
        self.assertLess(result.index("if_flag"), result.index("end_if"))
        self.assertLess(result.index("repeat"), result.index("end_repeat"))
        self.assertIn("comment", result)

    def test_unpaired_closer_at_end(self) -> None:
        ops = ["end_if", "show_message"]
        result = ess.sort_palette_ops_in_category(ops)
        self.assertEqual(result[-1], "end_if", "unpaired closer should be at the end")

    def test_empty_list(self) -> None:
        self.assertEqual(ess.sort_palette_ops_in_category([]), [])

    def test_region_pair(self) -> None:
        ops = ["end_region", "region", "label"]
        result = ess.sort_palette_ops_in_category(ops)
        self.assertLess(result.index("region"), result.index("end_region"))


class TestListLibrarySubflowNames(unittest.TestCase):
    def test_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            orig = ess._LIBRARY_DIR
            try:
                ess._LIBRARY_DIR = Path(td)
                self.assertEqual(ess.list_library_subflow_names(), [])
            finally:
                ess._LIBRARY_DIR = orig

    def test_with_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "heal_party.json").write_text("{}")
            (p / "battle_intro.json").write_text("{}")
            (p / "not_json.txt").write_text("x")
            orig = ess._LIBRARY_DIR
            try:
                ess._LIBRARY_DIR = p
                names = ess.list_library_subflow_names()
                self.assertEqual(names, ["battle_intro", "heal_party"])
            finally:
                ess._LIBRARY_DIR = orig

    def test_missing_dir(self) -> None:
        orig = ess._LIBRARY_DIR
        try:
            ess._LIBRARY_DIR = Path("/nonexistent/path")
            self.assertEqual(ess.list_library_subflow_names(), [])
        finally:
            ess._LIBRARY_DIR = orig


if __name__ == "__main__":
    unittest.main()

# FEATURE-MAP-046: unit tests for tools/event_script_ctx_menu.py (stdlib unittest).
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load_ctx_menu():
    p = Path(__file__).resolve().parent.parent / "tools" / "event_script_ctx_menu.py"
    spec = importlib.util.spec_from_file_location("event_script_ctx_menu_test", p)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load event_script_ctx_menu")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEventScriptCtxMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_ctx_menu()

    def test_default_tree_validates(self) -> None:
        known = frozenset({"show_message", "wait_frames", "end_script"})
        tree = self.m.default_menu_tree_from_ops(
            [("show_message", "Msg"), ("wait_frames", "Wait"), ("end_script", "End")]
        )
        count = [0]
        errs = self.m.validate_tree(tree, known, depth=0, count=count)
        self.assertEqual(errs, [])

    def test_parse_invalid_returns_none(self) -> None:
        known = frozenset({"show_message"})
        raw = [{"type": "action", "label": "Bad", "id": "add:nope"}]
        tree, errs = self.m.parse_menu_from_config(raw, known)
        self.assertIsNone(tree)
        self.assertTrue(any("invalid id" in e.lower() or "unknown" in e.lower() for e in errs))

    def test_filter_when_row(self) -> None:
        tree = [
            {"type": "action", "label": "Del", "id": "step:delete", "when": "row"},
            {"type": "action", "label": "Root only", "id": "rename_script", "when": "no_row"},
        ]
        f_row = self.m.filter_tree(tree, row_i=0, has_clipboard=False)
        ids_row = [n["id"] for n in f_row if n.get("type") == "action"]
        self.assertIn("step:delete", ids_row)
        self.assertNotIn("rename_script", ids_row)

        f_none = self.m.filter_tree(tree, row_i=None, has_clipboard=False)
        ids_none = [n["id"] for n in f_none if n.get("type") == "action"]
        self.assertNotIn("step:delete", ids_none)
        self.assertIn("rename_script", ids_none)

    def test_depth_cap_validate(self) -> None:
        known = frozenset({"show_message"})
        deep = {"type": "submenu", "label": "L", "children": []}
        cur = deep
        for _ in range(self.m.MAX_DEPTH + 2):
            nxt = {"type": "submenu", "label": "x", "children": []}
            cur["children"] = [nxt]
            cur = nxt
        cur["children"] = [{"type": "action", "label": "A", "id": "add:show_message"}]
        count = [0]
        errs = self.m.validate_tree([deep], known, depth=0, count=count)
        self.assertTrue(any("nesting" in e.lower() for e in errs))

    def test_default_tree_includes_edit_and_doc(self) -> None:
        known = frozenset({"show_message", "wait_frames", "end_script"})
        tree = self.m.default_menu_tree_from_ops(
            [("show_message", "Msg"), ("wait_frames", "Wait"), ("end_script", "End")]
        )
        row_ids = [
            n["id"]
            for n in self.m.filter_tree(tree, row_i=0, has_clipboard=False)
            if n.get("type") == "action"
        ]
        self.assertIn("blk:editmodal", row_ids)
        self.assertIn("blk:doc", row_ids)

    def test_default_event_menu_tree_validates(self) -> None:
        tree = self.m.default_event_menu_tree()
        count = [0]
        errs = self.m.validate_tree(tree, frozenset({"show_message"}), depth=0, count=count)
        self.assertEqual(errs, [])
        ids = [n["id"] for n in tree if n.get("type") == "action"]
        self.assertIn("ev:view", ids)
        self.assertIn("ev:trigger", ids)

        self.assertEqual(self.m.action_id_to_internal("step:delete"), "del")
        self.assertEqual(self.m.action_id_to_internal("add:show_message"), "add:show_message")
        self.assertEqual(self.m.action_id_to_internal("rename_script"), "rename_script")
        self.assertIsNone(self.m.action_id_to_internal("unknown:id"))

    def test_hit_test_leaf(self) -> None:
        known = frozenset({"show_message"})
        tree = [{"type": "action", "label": "X", "id": "add:show_message"}]
        filt = self.m.filter_tree(tree, row_i=None, has_clipboard=False)

        def measure(s: str) -> int:
            return 7 * len(s)

        panels = self.m.layout_cascade_panels(
            filt,
            sx=10,
            sy=10,
            mouse_xy=(30, 20),
            screen_w=800,
            screen_h=600,
            row_h=22,
            pad=4,
            measure=measure,
            max_panel_w=200,
        )
        self.assertTrue(panels)
        hit = self.m.hit_test_panels(panels, (30, 20))
        self.assertEqual(hit, "add:show_message")


if __name__ == "__main__":
    unittest.main()

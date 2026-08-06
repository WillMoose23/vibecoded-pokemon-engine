"""FEATURE-MAP-085 / IMPROVEMENT-MAP-094: Help overlay tab and search index tests."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tools.map_editor import HELP_GUIDE_TABS, HELP_HOME_JUMP_TABS, MapEditor


class HelpGuideTabsTest(unittest.TestCase):
    def test_editing_modes_replaces_legacy_mode_tabs(self) -> None:
        tab_ids = [t for t, _ in HELP_GUIDE_TABS]
        self.assertIn("editing_modes", tab_ids)
        self.assertIn("settings", tab_ids)
        for legacy in ("paint", "walk", "transparent", "over_player"):
            self.assertNotIn(legacy, tab_ids)

    def test_home_jump_tabs_match_number_keys(self) -> None:
        self.assertEqual(len(HELP_HOME_JUMP_TABS), 8)
        self.assertIn("npc_sprites", HELP_HOME_JUMP_TABS)
        for tid in HELP_HOME_JUMP_TABS:
            self.assertTrue(any(t == tid for t, _ in HELP_GUIDE_TABS))


class HelpSearchIndexTest(unittest.TestCase):
    def test_flood_query_finds_editing_modes(self) -> None:
        ed = MagicMock(spec=MapEditor)
        ed.font_small = MagicMock()
        ed.font_small.get_linesize.return_value = 14
        ed.font_small.size.side_effect = lambda s: (len(s) * 6, 14)
        ed.key_primary = MagicMock(return_value="Tab")
        ed.keys_for = MagicMock(return_value="x")
        ed._help_append_paragraphs = MapEditor._help_append_paragraphs.__get__(ed)
        ed._help_fit_one_line = MapEditor._help_fit_one_line.__get__(ed)
        ed._help_append_key_section = MapEditor._help_append_key_section.__get__(ed)
        ed._help_build_lines = MapEditor._help_build_lines.__get__(ed)
        ed._help_search_index_cache = None
        ed._help_search_index_wrap = 0
        ed.help_search = "flood"
        ed._help_build_search_index = MapEditor._help_build_search_index.__get__(ed)
        ed._help_search_results = MapEditor._help_search_results.__get__(ed)

        hits = ed._help_search_results(400)
        tabs = {h[0] for h in hits}
        self.assertIn("editing_modes", tabs)


if __name__ == "__main__":
    unittest.main()

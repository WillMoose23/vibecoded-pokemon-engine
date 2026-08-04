"""FEATURE-MAP-068: Event Engine — 3-panel UI-Standard modal.

Layout (all regions resizable via draggable splitters):

    +-------------------+-------------------------------+-----------------+
    | map picker (top)  | block editor   | action search | documentation  |
    |-------------------|  (nested,      | (categories,  |  (opcode docs) |
    | events list       |   drag/drop)   |  favorites)   |                |
    +-------------------+-------------------------------+-----------------+

- Left column: map picker (search + list) over events list (checkbox multi-select,
  Add/Copy/Paste/Delete, RMB context menu -> Copy/Paste/Delete/View in Map/Assign Sprite).
- Middle column: nested block editor (if_flag/repeat indent their children) with drag/drop
  and a right-edge action search (grouped by category + a Favorites tab); RMB context menu
  scoped to the editor -> Copy/Paste/Add/Delete/Show Documentation.
- Right column: structured opcode documentation.

The modal follows .cursor/rules/UI-Standard-Rule.mdc (full-window canvas, drag title bar,
BR/BL resize, persisted size/pos). Map scope (independent vs. follow main editor) is a config
toggle read from the eventEngine config section.

Back -> EventsLauncherModal · Help -> documentation overlay (script_ops).
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

import event_script_ctx_menu as ectx
import event_script_opcode_docs as odoc
import event_script_schema as ess
import modal_text as mtext

if TYPE_CHECKING:
    from map_editor import MapEditor

_ROOT = Path(__file__).resolve().parents[1]
_MAPS_DIR = _ROOT / "src" / "maps"
_FOOTPRINT = 2
_DRAG_THRESHOLD = 4
_LIST_CLICK_DOUBLE = 0.45  # FEATURE-MAP-082: same threshold as map_editor.LIST_CLICK_DOUBLE
_PANEL_MIN_W = 640
_PANEL_MIN_H = 480
_UNDO_STACK_MAX = 50

# Theme
_C_PANEL = (20, 24, 20)
_C_BODY = (16, 20, 16)
_C_SUBPANEL = (26, 31, 28)
_C_BORDER = (80, 180, 120)
_C_BORDER_DIM = (60, 78, 66)
_C_SPLIT = (54, 70, 58)
_C_SPLIT_HOT = (110, 200, 150)
_C_TEXT = (210, 224, 214)
_C_TEXT_DIM = (140, 158, 146)
_C_HEAD = (180, 255, 200)
_C_SEL = (54, 92, 70)
_C_SEL_BORDER = (120, 210, 160)


# ---------------------------------------------------------------------------
# Nested-tree helpers (path = tuple of indices into nested children)
# ---------------------------------------------------------------------------

def _node_at(tree: list[dict], path: tuple[int, ...]) -> dict | None:
    nodes = tree
    node: dict | None = None
    for idx in path:
        if not (0 <= idx < len(nodes)):
            return None
        node = nodes[idx]
        nodes = node.get("children") or []
    return node


def _list_for_parent(tree: list[dict], parent_path: tuple[int, ...]) -> list[dict] | None:
    if not parent_path:
        return tree
    node = _node_at(tree, parent_path)
    if node is None:
        return None
    if "children" not in node or not isinstance(node["children"], list):
        node["children"] = []
    return node["children"]


def _pop_at(tree: list[dict], path: tuple[int, ...]) -> dict | None:
    if not path:
        return None
    parent = _list_for_parent(tree, path[:-1])
    if parent is None or not (0 <= path[-1] < len(parent)):
        return None
    return parent.pop(path[-1])


def _insert_at(tree: list[dict], parent_path: tuple[int, ...], index: int, node: dict) -> None:
    parent = _list_for_parent(tree, parent_path)
    if parent is None:
        return
    index = max(0, min(index, len(parent)))
    parent.insert(index, node)


def _is_descendant(candidate_parent: tuple[int, ...], dragged: tuple[int, ...]) -> bool:
    """True when candidate_parent is the dragged node itself or inside it."""
    return candidate_parent[: len(dragged)] == dragged


class EventEngineModal:
    def __init__(self, editor: MapEditor) -> None:
        self.ed = editor
        self.open = False
        self.panel_rect = pygame.Rect(0, 0, 1, 1)

        # UI-Standard chrome state
        self._panel_override: pygame.Rect | None = None
        self._drag_mode: str = "none"
        self._drag_ref: tuple[int, int] = (0, 0)
        self._resize_corner_br = pygame.Rect(0, 0, 16, 16)
        self._resize_corner_bl = pygame.Rect(0, 0, 16, 16)
        self._title_bar = pygame.Rect(0, 0, 1, 1)
        self.close_btn = pygame.Rect(0, 0, 1, 1)
        self._back_btn = pygame.Rect(0, 0, 1, 1)
        self._help_btn = pygame.Rect(0, 0, 1, 1)
        self._registry_btn = pygame.Rect(0, 0, 1, 1)
        self._prefs_btn = pygame.Rect(0, 0, 1, 1)

        # FEATURE-MAP-082: double-click block row opens action modal.
        self._block_dbl_prev_time: float = 0.0
        self._block_dbl_prev_path: tuple[int, ...] | None = None

        # FEATURE-MAP-084: subflow delete confirm + prefs panel.
        self.skip_subflow_delete_confirm = False
        self.prefs_open = False
        self._prefs_panel_rect = pygame.Rect(0, 0, 1, 1)
        self._prefs_skip_chk = pygame.Rect(0, 0, 1, 1)
        self._delete_confirm: dict | None = None  # {name, skip_chk_rect, ok_rect, cancel_rect}

        # Splitter fractions (persisted)
        self.frac_left = 0.30   # left column width / body width
        self.frac_right = 0.34  # right column width / body width
        self.frac_left_h = 0.45  # map picker height / left column height
        self.frac_mid_v = 0.62  # block editor width / middle column width

        # Splitter drag state: ("vsplit_a"|"vsplit_b"|"left_h"|"mid_v") or None
        self._split_drag: str | None = None
        self._split_rects: dict[str, pygame.Rect] = {}

        # Session model
        self.maps: list[str] = []
        self.map_search = ""
        self.map_scroll = 0
        self.sel_map_id: str | None = None
        self.events: list[dict] = []
        self.events_dirty = False
        self.event_scroll = 0
        self.checks: set[int] = set()
        self.sel_event_index: int | None = None
        self.event_clipboard: dict | None = None

        # Script (block) editor state — FEATURE-MAP-074: per-flow trees (main + subflows).
        self.flows: dict[str, list[dict]] = {"main": []}
        self.active_flow: str = "main"
        self.open_tabs: list[str] = ["main"]  # tab strip order (main always present)
        self.collapsed: set[tuple[str, tuple[int, ...]]] = set()  # (flow, path) collapsed regions
        self.script_dirty = False
        self.block_sel: tuple[int, ...] | None = None
        self.block_clipboard: dict | None = None
        self.block_scroll = 0
        self._block_rows: list[dict] = []
        self.doc_op: str | None = None

        # Subflow tab strip / library menu rects (FEATURE-MAP-074)
        self._tab_rects: list[tuple[str, pygame.Rect]] = []
        self._tab_menu_btn = pygame.Rect(0, 0, 1, 1)
        self._tab_new_btn = pygame.Rect(0, 0, 1, 1)
        self.flow_menu_open = False
        self.flow_menu_search = ""
        self._flow_menu_rows: list[tuple[str, pygame.Rect]] = []
        self._flow_menu_rect = pygame.Rect(0, 0, 1, 1)
        self._flow_menu_search_rect = pygame.Rect(0, 0, 1, 1)
        # Subflow rename (tab) state
        self.tab_rename: str | None = None
        self.tab_rename_buf: str = ""

        # Inline arg editing
        self.edit_field: tuple[tuple[int, ...], str] | None = None
        self.edit_buf = ""
        self.edit_is_int = False

        # Action search state
        self.action_tab = "All"  # "Favorites" | "All"
        self.action_search = ""
        self.action_scroll = 0
        self.favorites: list[str] = []
        self.action_cat_collapsed: set[str] = set()  # FEATURE-MAP-081: collapsed category names
        self._action_rows: list[dict] = []
        self._action_header_rows: list[tuple[str, pygame.Rect]] = []

        # Rename state (FEATURE-MAP-070)
        self.rename_index: int | None = None
        self.rename_buf: str = ""
        self._rename_rect = pygame.Rect(0, 0, 1, 1)

        # Documentation panel (FEATURE-MAP-080): collapse / search / scroll
        self.doc_collapsed = False
        self.doc_search = ""
        self.doc_scroll = 0
        self._doc_search_rect = pygame.Rect(0, 0, 1, 1)
        self._doc_collapse_btn = pygame.Rect(0, 0, 1, 1)
        self._doc_popout_btn = pygame.Rect(0, 0, 1, 1)
        self._doc_body_rect = pygame.Rect(0, 0, 1, 1)
        self._doc_total_h = 0

        # Left selector collapse (FEATURE-MAP-080)
        self.left_collapsed = False
        self._left_collapse_btn = pygame.Rect(0, 0, 1, 1)

        # Focus: None|"map_search"|"action_search"|"arg"|"rename"|"tab_rename"|"flow_search"|"doc_search"
        self.focus: str | None = None

        # Drag (action -> editor, or block reorder)
        self.drag: dict | None = None
        self._end_op_reject_flash: int = 0  # FEATURE-MAP-081: frames remaining for red flash

        # Context menu: {"items":[(label,act)], "rows":[(rect,act)], "rect":Rect}
        self.ctx: dict | None = None

        # Cached rects for hit-testing
        self._map_panel = pygame.Rect(0, 0, 1, 1)
        self._events_panel = pygame.Rect(0, 0, 1, 1)
        self._block_panel = pygame.Rect(0, 0, 1, 1)
        self._action_panel = pygame.Rect(0, 0, 1, 1)
        self._doc_panel = pygame.Rect(0, 0, 1, 1)
        self._map_search_rect = pygame.Rect(0, 0, 1, 1)
        self._action_search_rect = pygame.Rect(0, 0, 1, 1)
        self._map_rows: list[tuple[str, pygame.Rect]] = []
        self._event_rows: list[dict] = []
        self._event_btns: dict[str, pygame.Rect] = {}
        self._action_tab_rects: list[tuple[str, pygame.Rect]] = []
        self._doc_lines: list[str] = []

        # Phase 3: mini-map (clickable thumbnail + event hulls in map panel)
        self._mini_map_rect = pygame.Rect(0, 0, 1, 1)
        self._mini_thumb: pygame.Surface | None = None
        self._mini_map_w = 0
        self._mini_map_h = 0
        self._mini_draw_rect = pygame.Rect(0, 0, 1, 1)

        # Phase 3: undo/redo scoped to Event Engine session
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []

    # ------------------------------------------------------------------
    # Active-flow accessor (FEATURE-MAP-074): existing code uses self.tree.
    # ------------------------------------------------------------------

    @property
    def tree(self) -> list[dict]:
        return self.flows.setdefault(self.active_flow, [])

    @tree.setter
    def tree(self, value: list[dict]) -> None:
        self.flows[self.active_flow] = value if isinstance(value, list) else []

    def labels_in_active_flow(self) -> list[str]:
        """FEATURE-MAP-075: label names declared in the active flow (for goto dropdowns)."""
        return ess.labels_in_steps(ess.tree_to_steps(self.tree))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open_modal(self) -> None:
        self.open = True
        self._drag_mode = "none"
        self._split_drag = None
        self.ctx = None
        self.drag = None
        self.rename_index = None
        self.rename_buf = ""
        self.tab_rename = None
        self.tab_rename_buf = ""
        self.flow_menu_open = False
        self.flow_menu_search = ""
        self.doc_collapsed = False
        self.doc_search = ""
        self.doc_scroll = 0
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._load_config()
        self.maps = self.ed.list_all_map_ids()
        # Default-select the main editor's current map when present
        if self.sel_map_id is None or self.sel_map_id not in self.maps:
            cur = self.ed.map_id
            self.sel_map_id = cur if cur in self.maps else (self.maps[0] if self.maps else None)
        if self.sel_map_id is not None:
            self._load_events_for_map(self.sel_map_id)
        self._refresh_mini_map_thumb()

    def _session_snapshot(self) -> dict:
        return {
            "events": copy.deepcopy(self.events),
            "flows": copy.deepcopy(self.flows),
            "active_flow": self.active_flow,
            "open_tabs": list(self.open_tabs),
            "sel_event_index": self.sel_event_index,
            "sel_map_id": self.sel_map_id,
            "events_dirty": self.events_dirty,
            "script_dirty": self.script_dirty,
        }

    def _session_restore(self, snap: dict) -> None:
        self.events = copy.deepcopy(snap["events"])
        self.flows = copy.deepcopy(snap["flows"])
        self.active_flow = str(snap.get("active_flow", "main"))
        self.open_tabs = list(snap.get("open_tabs", ["main"]))
        self.sel_event_index = snap.get("sel_event_index")
        self.events_dirty = bool(snap.get("events_dirty"))
        self.script_dirty = bool(snap.get("script_dirty"))
        self.block_sel = None
        self.edit_field = None
        self._refresh_mini_map_thumb()

    def _undo_checkpoint(self) -> None:
        self._undo_stack.append(self._session_snapshot())
        if len(self._undo_stack) > _UNDO_STACK_MAX:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo_session(self) -> None:
        if not self._undo_stack:
            self.ed.set_status("Nothing to undo.", kind="info")
            return
        self._flush_pending()
        self._redo_stack.append(self._session_snapshot())
        self._session_restore(self._undo_stack.pop())
        self.ed.set_status("Undid last change.", kind="info")

    def _redo_session(self) -> None:
        if not self._redo_stack:
            self.ed.set_status("Nothing to redo.", kind="info")
            return
        self._flush_pending()
        self._undo_stack.append(self._session_snapshot())
        self._session_restore(self._redo_stack.pop())
        self.ed.set_status("Redid change.", kind="info")

    def _refresh_mini_map_thumb(self) -> None:
        if self.sel_map_id:
            self._mini_thumb = self.ed._thumbnail_surface_for_map_stem(self.sel_map_id)
            self._mini_map_w, self._mini_map_h = self.ed.map_dims(self.sel_map_id)
        else:
            self._mini_thumb = None
            self._mini_map_w = 0
            self._mini_map_h = 0

    def _mini_map_tile_at(self, mx: int, my: int) -> tuple[int, int] | None:
        dr = self._mini_draw_rect
        if not dr.collidepoint(mx, my) or self._mini_map_w <= 0 or self._mini_map_h <= 0:
            return None
        tw = self._mini_map_w * _FOOTPRINT
        th = self._mini_map_h * _FOOTPRINT
        if tw <= 0 or th <= 0:
            return None
        rel_x = (mx - dr.x) / max(1, dr.w)
        rel_y = (my - dr.y) / max(1, dr.h)
        tx = int(rel_x * self._mini_map_w)
        ty = int(rel_y * self._mini_map_h)
        tx = max(0, min(tx, self._mini_map_w - _FOOTPRINT))
        ty = max(0, min(ty, self._mini_map_h - _FOOTPRINT))
        return tx, ty

    def _set_event_anchor(self, tx: int, ty: int) -> None:
        if self.sel_event_index is None or not (0 <= self.sel_event_index < len(self.events)):
            return
        self._undo_checkpoint()
        self.events[self.sel_event_index]["anchor"] = {"x": tx, "y": ty}
        self.events_dirty = True
        self.ed.set_status(f"Anchor set to ({tx},{ty}).", kind="ok")

    def _draw_mini_map(self, rect: pygame.Rect) -> None:
        ed = self.ed
        self._mini_map_rect = rect
        pygame.draw.rect(ed.screen, (14, 18, 16), rect)
        pygame.draw.rect(ed.screen, _C_BORDER_DIM, rect, 1)
        if self._mini_thumb is None or self._mini_map_w <= 0:
            ed.screen.blit(
                ed.font_small.render("Select a map", True, _C_TEXT_DIM),
                (rect.x + 6, rect.y + 6),
            )
            self._mini_draw_rect = rect
            return
        pad = 4
        inner = pygame.Rect(rect.x + pad, rect.y + pad, rect.w - 2 * pad, rect.h - 2 * pad)
        tw_px, th_px = self._mini_thumb.get_size()
        scale = min(inner.w / max(1, tw_px), inner.h / max(1, th_px))
        dw = max(1, int(tw_px * scale))
        dh = max(1, int(th_px * scale))
        self._mini_draw_rect = pygame.Rect(
            inner.x + (inner.w - dw) // 2,
            inner.y + (inner.h - dh) // 2,
            dw,
            dh,
        )
        dr = self._mini_draw_rect
        scaled = pygame.transform.smoothscale(self._mini_thumb, (dr.w, dr.h))
        ed.screen.blit(scaled, dr.topleft)
        cp_x = dr.w / max(1, self._mini_map_w)
        cp_y = dr.h / max(1, self._mini_map_h)
        for i, ev in enumerate(self.events):
            a = ev.get("anchor") or {}
            try:
                ax, ay = int(a.get("x", 0)), int(a.get("y", 0))
            except (TypeError, ValueError):
                continue
            hull = pygame.Rect(
                dr.x + int(ax * cp_x),
                dr.y + int(ay * cp_y),
                max(2, int(_FOOTPRINT * cp_x)),
                max(2, int(_FOOTPRINT * cp_y)),
            )
            sel = i == self.sel_event_index
            col = (120, 230, 160) if sel else (230, 160, 80)
            pygame.draw.rect(ed.screen, col, hull, 2 if sel else 1)

    def _known_block_ops(self) -> frozenset[str]:
        return frozenset(ess.cpp_script_ops_ordered())

    def _block_ctx_tree(self) -> list[dict]:
        sec = self.ed.config_get_section("eventEngine")
        raw = sec.get("contextMenuBlocks")
        if raw is None:
            raw = self.ed.config_get_section("eventScriptEditor").get("contextMenu")
        tree, errs = ectx.parse_menu_from_config(raw, self._known_block_ops())
        if tree is None or errs:
            pairs = [
                (op, ess.op_documentation(op).get("label", op))
                for op in ess.cpp_script_ops_ordered()
            ]
            return ectx.default_menu_tree_from_ops(pairs)
        return tree

    def _event_ctx_tree(self) -> list[dict]:
        sec = self.ed.config_get_section("eventEngine")
        raw = sec.get("contextMenuEvents")
        n_checks = len(self.checks)
        del_label = f"Delete ({n_checks})" if n_checks >= 2 else "Delete"
        tree, errs = ectx.parse_event_menu_from_config(raw)
        if tree is None or errs:
            return ectx.default_event_menu_tree(multi_delete_label=del_label)
        return tree

    def close_modal(self) -> None:
        self._flush_pending()
        self.open = False
        self._drag_mode = "none"
        self._split_drag = None
        self.ctx = None
        self.drag = None
        self._undo_stack.clear()
        self._redo_stack.clear()

    # ------------------------------------------------------------------
    # Config persistence (eventEngine section)
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        sec = self.ed.config_get_section("eventEngine")
        favs = sec.get("favorites")
        if isinstance(favs, list):
            valid = set(ess.cpp_script_ops_ordered())
            self.favorites = [str(x) for x in favs if str(x) in valid]
        for key, attr in (
            ("fracLeft", "frac_left"),
            ("fracRight", "frac_right"),
            ("fracLeftH", "frac_left_h"),
            ("fracMidV", "frac_mid_v"),
        ):
            v = sec.get(key)
            if isinstance(v, (int, float)) and 0.05 < float(v) < 0.95:
                setattr(self, attr, float(v))
        # FEATURE-MAP-081: persisted collapsed categories.
        cats = sec.get("collapsedCategories")
        if isinstance(cats, list):
            self.action_cat_collapsed = set(str(c) for c in cats)
        # FEATURE-MAP-084: skip subflow delete confirmation.
        self.skip_subflow_delete_confirm = bool(sec.get("skipSubflowDeleteConfirm", False))

    def _save_config(self) -> None:
        sec = self.ed.config_get_section("eventEngine")
        sec["favorites"] = list(self.favorites)
        sec["fracLeft"] = round(self.frac_left, 4)
        sec["fracRight"] = round(self.frac_right, 4)
        sec["fracLeftH"] = round(self.frac_left_h, 4)
        sec["fracMidV"] = round(self.frac_mid_v, 4)
        sec["collapsedCategories"] = sorted(self.action_cat_collapsed)
        sec["skipSubflowDeleteConfirm"] = bool(self.skip_subflow_delete_confirm)
        self.ed.config_set_section("eventEngine", sec)

    def _map_scope_follows_main(self) -> bool:
        sec = self.ed.config_get_section("eventEngine")
        return bool(sec.get("selectSwitchesMainMap", False))

    # ------------------------------------------------------------------
    # Session data
    # ------------------------------------------------------------------

    def _load_events_for_map(self, map_id: str) -> None:
        self._flush_pending()
        if self._map_scope_follows_main() and map_id != self.ed.map_id:
            self.ed.try_load_map_by_id(map_id)
        self.sel_map_id = map_id
        self.events = self.ed.read_map_events(map_id)
        self.events_dirty = False
        self.checks = set()
        self.sel_event_index = None
        self.event_scroll = 0
        self._reset_flows()
        self.doc_op = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._refresh_mini_map_thumb()

    def _persist_events(self) -> None:
        if self.sel_map_id and self.events_dirty:
            if self.ed.write_map_events(self.sel_map_id, self.events):
                self.events_dirty = False

    def _script_rel_for(self, eid: str) -> str:
        return f"scripts/{self.sel_map_id}/{eid}.json"

    def _script_path_for_event(self, ev: dict) -> Path | None:
        s = ev.get("script")
        if isinstance(s, dict) and isinstance(s.get("path"), str):
            rel = s["path"].strip().replace("\\", "/").lstrip("/")
            if ".." in rel.split("/"):
                return None
            return _MAPS_DIR / rel
        return None

    def _reset_flows(self) -> None:
        self.flows = {"main": []}
        self.active_flow = "main"
        self.open_tabs = ["main"]
        self.collapsed = set()
        self.block_sel = None

    def _load_script_tree(self) -> None:
        self._reset_flows()
        if self.sel_event_index is None:
            return
        if not (0 <= self.sel_event_index < len(self.events)):
            return
        ev = self.events[self.sel_event_index]
        p = self._script_path_for_event(ev)
        if p is None:
            return
        flows = ess.read_flows_from_path(p)
        self.flows = {name: ess.steps_to_tree(steps) for name, steps in flows.items()}
        if "main" not in self.flows:
            self.flows["main"] = []
        self.active_flow = "main"
        self.open_tabs = ["main"]
        self.script_dirty = False

    def _persist_script(self) -> None:
        if not self.script_dirty or self.sel_event_index is None:
            return
        if not (0 <= self.sel_event_index < len(self.events)):
            return
        ev = self.events[self.sel_event_index]
        p = self._script_path_for_event(ev)
        if p is None:
            return
        flow_steps: dict[str, list[dict]] = {}
        for name, tree in self.flows.items():
            steps = ess.tree_to_steps(tree)
            ok, msg = ess.validate_balanced(steps)
            if not ok:
                self.ed.set_status(f"Script not saved (flow '{name}'): {msg}", kind="err")
                return
            flow_steps[name] = steps
        ess.write_flows_to_path(p, flow_steps, self.sel_map_id or "unknown_map")
        self.script_dirty = False

    def _flush_pending(self) -> None:
        self._commit_arg_edit()
        self._commit_rename(cancel=True)
        self._commit_tab_rename(cancel=True)
        self._persist_script()
        self._persist_events()

    # ------------------------------------------------------------------
    # Event CRUD
    # ------------------------------------------------------------------

    def _unique_event_id(self) -> str:
        existing = {str(e.get("id", "")) for e in self.events}
        n = len(self.events) + 1
        while True:
            eid = f"{self.sel_map_id}_event_{n}"
            if eid not in existing:
                return eid
            n += 1

    def _add_event(self) -> None:
        if not self.sel_map_id:
            return
        self._undo_checkpoint()
        eid = self._unique_event_id()
        rel = self._script_rel_for(eid)
        p = _MAPS_DIR / rel
        if not p.is_file():
            ess.write_document_to_path(p, [ess.new_step("show_message")], self.sel_map_id)
        self.events.append({
            "id": eid,
            "anchor": {"x": 0, "y": 0},
            "script": {"path": rel},
            "interaction": {"type": "talk", "keyHint": "Q"},
        })
        self.events_dirty = True
        self._select_event(len(self.events) - 1)
        self.ed.set_status(f"Added {eid}", kind="ok")

    def _copy_event(self, idx: int) -> None:
        if 0 <= idx < len(self.events):
            self.event_clipboard = copy.deepcopy(self.events[idx])
            self.ed.set_status("Event copied.", kind="ok")

    def _paste_event(self) -> None:
        if not self.event_clipboard or not self.sel_map_id:
            return
        self._undo_checkpoint()
        new_ev = copy.deepcopy(self.event_clipboard)
        eid = self._unique_event_id()
        new_ev["id"] = eid
        rel = self._script_rel_for(eid)
        # Copy the source script content to the new event's path
        src_path = self._script_path_for_event(self.event_clipboard)
        steps = ess.read_steps_from_path(src_path) if src_path else [ess.new_step("show_message")]
        ess.write_document_to_path(_MAPS_DIR / rel, steps, self.sel_map_id)
        new_ev["script"] = {"path": rel}
        self.events.append(new_ev)
        self.events_dirty = True
        self._select_event(len(self.events) - 1)
        self.ed.set_status(f"Pasted as {eid}", kind="ok")

    def _delete_indices(self, indices: set[int]) -> None:
        if not indices:
            return
        self._undo_checkpoint()
        for i in sorted(indices, reverse=True):
            if 0 <= i < len(self.events):
                self.events.pop(i)
        self.events_dirty = True
        self.checks = set()
        self.sel_event_index = None
        self._reset_flows()
        self._persist_events()
        self.ed.set_status(f"Deleted {len(indices)} event(s).", kind="ok")

    def _select_event(self, idx: int) -> None:
        self._commit_arg_edit()
        self._commit_rename(cancel=True)
        self._persist_script()
        if 0 <= idx < len(self.events):
            self.sel_event_index = idx
            self._load_script_tree()
        else:
            self.sel_event_index = None
            self._reset_flows()

    def _begin_rename(self, idx: int) -> None:
        """FEATURE-MAP-070: start inline rename for the given event row."""
        self._commit_rename(cancel=True)
        self._commit_arg_edit()
        if not (0 <= idx < len(self.events)):
            return
        self.rename_index = idx
        self.rename_buf = str(self.events[idx].get("id", ""))
        self.focus = "rename"

    def _commit_rename(self, cancel: bool = False) -> None:
        """FEATURE-MAP-070: commit or cancel an in-progress rename."""
        if self.rename_index is None:
            return
        idx = self.rename_index
        self.rename_index = None
        if self.focus == "rename":
            self.focus = None
        if cancel:
            self.rename_buf = ""
            return
        new_id = _sanitize_event_id(self.rename_buf)
        self.rename_buf = ""
        if not new_id:
            self.ed.set_status("Rename cancelled: empty id.", kind="err")
            return
        if not (0 <= idx < len(self.events)):
            return
        old_id = str(self.events[idx].get("id", ""))
        if new_id == old_id:
            return
        # Collision check
        existing = {str(e.get("id", "")) for j, e in enumerate(self.events) if j != idx}
        if new_id in existing:
            self.ed.set_status(f"Rename failed: '{new_id}' already exists.", kind="err")
            return
        if not self.sel_map_id:
            return
        self._undo_checkpoint()
        # Rename script file on disk
        old_rel = f"scripts/{self.sel_map_id}/{old_id}.json"
        new_rel = f"scripts/{self.sel_map_id}/{new_id}.json"
        old_path = _MAPS_DIR / old_rel
        new_path = _MAPS_DIR / new_rel
        if old_path.is_file():
            if new_path.exists():
                self.ed.set_status(f"Rename failed: script file '{new_path.name}' already exists.", kind="err")
                return
            new_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.rename(new_path)
        # Update event data
        ev = self.events[idx]
        ev["id"] = new_id
        ev["script"] = {"path": new_rel}
        self.events_dirty = True
        self._persist_events()
        # Reload script tree since path changed
        self._load_script_tree()
        self.ed.set_status(f"Renamed '{old_id}' → '{new_id}'.", kind="ok")

    # ------------------------------------------------------------------
    # Subflow (tab) management — FEATURE-MAP-074
    # ------------------------------------------------------------------

    def _switch_flow(self, name: str) -> None:
        if name in self.flows and name != self.active_flow:
            self._commit_arg_edit()
            self.active_flow = name
            self.block_sel = None
            self.block_scroll = 0

    def _open_flow_tab(self, name: str) -> None:
        if name not in self.flows:
            return
        if name not in self.open_tabs:
            self.open_tabs.append(name)
        self._switch_flow(name)

    def _unique_subflow_name(self) -> str:
        n = len(self.flows)
        while True:
            cand = f"subflow_{n}"
            if cand not in self.flows:
                return cand
            n += 1

    def _create_subflow(self) -> None:
        if self.sel_event_index is None:
            self.ed.set_status("Select an event before adding a subflow.", kind="err")
            return
        self._undo_checkpoint()
        name = self._unique_subflow_name()
        self.flows[name] = [_new_node("show_message")]
        self.open_tabs.append(name)
        self.active_flow = name
        self.block_sel = None
        self.script_dirty = True
        self.ed.set_status(f"Created subflow '{name}'. Rename via the tab menu.", kind="ok")

    def _open_tab_ctx(self, mx, my, name) -> None:
        items = [("Rename", f"tab:rename:{name}"), ("Save", "tab:save")]
        if name != "main":
            items = [("Delete subflow", f"tab:delete:{name}"), ("Close Tab", f"tab:close:{name}")] + items
        items += [("Close all but this", f"tab:closeothers:{name}"), ("Close all", "tab:closeall")]
        self.ctx = {"kind": "tab", "pos": (mx, my), "items": items}

    def _close_tab(self, name: str) -> None:
        if name == "main":
            return
        if name in self.open_tabs:
            self.open_tabs.remove(name)
        if self.active_flow == name:
            self.active_flow = "main"
            self.block_sel = None

    def _delete_subflow(self, name: str, *, skip_confirm: bool = False) -> None:
        """FEATURE-MAP-084: permanently remove a subflow from the script."""
        if name == "main" or name not in self.flows:
            return
        if not skip_confirm and not self.skip_subflow_delete_confirm:
            self._delete_confirm = {"name": name}
            return
        self._undo_checkpoint()
        self.flows.pop(name, None)
        if name in self.open_tabs:
            self.open_tabs.remove(name)
        self.collapsed = {(f, p) for (f, p) in self.collapsed if f != name}
        if self.active_flow == name:
            self.active_flow = "main"
            self.block_sel = None
        self.script_dirty = True
        self._delete_confirm = None
        self.ed.set_status(f"Deleted subflow '{name}'.", kind="ok")

    def _begin_tab_rename(self, name: str) -> None:
        if name == "main":
            self.ed.set_status("The main flow cannot be renamed.", kind="err")
            return
        self.tab_rename = name
        self.tab_rename_buf = name
        self.focus = "tab_rename"

    def _commit_tab_rename(self, cancel: bool = False) -> None:
        if self.tab_rename is None:
            return
        old = self.tab_rename
        self.tab_rename = None
        if self.focus == "tab_rename":
            self.focus = None
        if cancel:
            self.tab_rename_buf = ""
            return
        new = _sanitize_event_id(self.tab_rename_buf)
        self.tab_rename_buf = ""
        if not new or new == old:
            return
        if new == "main" or new in self.flows:
            self.ed.set_status(f"Rename failed: '{new}' already exists.", kind="err")
            return
        # Rename the flow key, preserving order in open_tabs.
        self.flows[new] = self.flows.pop(old)
        self.open_tabs = [new if t == old else t for t in self.open_tabs]
        if self.active_flow == old:
            self.active_flow = new
        # Migrate collapsed keys for this flow.
        self.collapsed = {(new if f == old else f, p) for (f, p) in self.collapsed}
        self.script_dirty = True
        self.ed.set_status(f"Renamed subflow '{old}' → '{new}'.", kind="ok")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _relayout(self, body: pygame.Rect) -> None:
        sp = 6  # splitter thickness
        min_col = 150
        min_row = 70
        col_h = body.h
        self._split_rects = {}

        # Resolve effective left/right widths based on collapse state.
        left_strip = self.left_collapsed
        right_strip = self.doc_collapsed
        raw_left = 22 if left_strip else int(body.w * self.frac_left)
        raw_right = 22 if right_strip else int(body.w * self.frac_right)

        if not left_strip:
            raw_left = max(min_col, min(raw_left, body.w - 2 * min_col - 2 * sp))
        if not right_strip:
            raw_right = max(min_col, min(raw_right, body.w - raw_left - min_col - 2 * sp))
        mid_w = body.w - raw_left - raw_right - 2 * sp

        lx = body.x
        mx = lx + raw_left + sp
        rx = mx + mid_w + sp

        # Left column
        if left_strip:
            self._map_panel = pygame.Rect(lx, body.y, raw_left, col_h)
            self._events_panel = pygame.Rect(lx, body.y, 0, 0)
        else:
            top_h = int(col_h * self.frac_left_h)
            top_h = max(min_row, min(top_h, col_h - min_row - sp))
            self._map_panel = pygame.Rect(lx, body.y, raw_left, top_h)
            self._events_panel = pygame.Rect(lx, body.y + top_h + sp, raw_left, col_h - top_h - sp)
            self._split_rects["left_h"] = pygame.Rect(lx, body.y + top_h, raw_left, sp)
            self._split_rects["vsplit_a"] = pygame.Rect(lx + raw_left, body.y, sp, col_h)

        # Middle column (block editor | action search)
        be_w = int(mid_w * self.frac_mid_v)
        be_w = max(min_col, min(be_w, mid_w - 120 - sp))
        self._block_panel = pygame.Rect(mx, body.y, be_w, col_h)
        self._action_panel = pygame.Rect(mx + be_w + sp, body.y, mid_w - be_w - sp, col_h)
        self._split_rects["mid_v"] = pygame.Rect(mx + be_w, body.y, sp, col_h)

        # Right column (doc panel)
        self._doc_panel = pygame.Rect(rx, body.y, raw_right, col_h)
        if not right_strip:
            self._split_rects["vsplit_b"] = pygame.Rect(mx + mid_w, body.y, sp, col_h)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self) -> None:
        if not self.open:
            return
        ed = self.ed
        canvas = ed.screen.get_rect()
        dim = pygame.Surface((canvas.w, canvas.h), pygame.SRCALPHA)
        dim.fill((8, 12, 16, 210))
        ed.screen.blit(dim, canvas.topleft)

        if self._panel_override is not None:
            panel = self._panel_override.copy()
        else:
            pw = min(max(960, canvas.w - 48), canvas.w - 24)
            ph = min(max(620, canvas.h - 80), canvas.h - 24)
            panel = pygame.Rect(0, 0, pw, ph)
            panel.center = canvas.center
        panel.w = max(_PANEL_MIN_W, min(panel.w, canvas.w - 8))
        panel.h = max(_PANEL_MIN_H, min(panel.h, canvas.h - 8))
        panel.x = max(canvas.x + 4, min(panel.x, canvas.right - panel.w - 4))
        panel.y = max(canvas.y + 4, min(panel.y, canvas.bottom - panel.h - 4))
        self.panel_rect = panel

        head_h = 36
        foot_h = 22
        pygame.draw.rect(ed.screen, _C_PANEL, panel)
        pygame.draw.rect(ed.screen, _C_BORDER, panel, 2)

        # Title bar
        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 230, head_h)
        ed.screen.blit(ed.font.render("Event Engine", True, _C_HEAD), (panel.x + 12, panel.y + 8))
        for i in range(5):
            gx = panel.centerx - 20 + i * 10
            pygame.draw.circle(ed.screen, (70, 130, 100), (gx, panel.y + head_h // 2), 2)

        self.close_btn = pygame.Rect(panel.right - 72, panel.y + 6, 60, 26)
        _btn(ed, self.close_btn, "Close", (72, 48, 48), (245, 240, 240))
        self._back_btn = pygame.Rect(panel.right - 144, panel.y + 6, 64, 26)
        _btn(ed, self._back_btn, "\u2190 Back", (50, 70, 90), (200, 225, 245))
        self._help_btn = pygame.Rect(panel.right - 216, panel.y + 6, 64, 26)
        _btn(ed, self._help_btn, "Help", (55, 65, 40), (200, 245, 180))
        self._registry_btn = pygame.Rect(panel.right - 296, panel.y + 6, 72, 26)
        _btn(ed, self._registry_btn, "Flags", (45, 55, 75), (200, 215, 245))
        self._prefs_btn = pygame.Rect(panel.right - 368, panel.y + 6, 64, 26)
        _btn(ed, self._prefs_btn, "Prefs", (50, 55, 45), (210, 220, 180))

        pygame.draw.line(ed.screen, _C_BORDER_DIM, (panel.x, panel.y + head_h),
                         (panel.right, panel.y + head_h), 1)

        body = pygame.Rect(panel.x + 6, panel.y + head_h + 4,
                           panel.w - 12, panel.h - head_h - foot_h - 8)
        pygame.draw.rect(ed.screen, _C_BODY, body)
        self._relayout(body)

        if self.left_collapsed:
            self._draw_left_collapsed()
        else:
            self._draw_map_panel()
            self._draw_events_panel()
        self._draw_block_panel()
        self._draw_action_panel()
        if self.doc_collapsed:
            self._draw_doc_collapsed()
        else:
            self._draw_doc_panel()
        self._draw_splitters()

        # Footer hint
        mid = self.sel_map_id or "(no map)"
        scope = "follows main" if self._map_scope_follows_main() else "independent"
        foot = f"Map: {mid} · scope: {scope} · drag splitters to resize · RMB for menus"
        ed.screen.blit(ed.font_small.render(foot, True, _C_TEXT_DIM),
                       (panel.x + 12, panel.bottom - foot_h + 2))

        # Drag ghost
        if self.drag and self.drag.get("active"):
            self._draw_drag_ghost()

        # Subflow library menu (FEATURE-MAP-074)
        if self.flow_menu_open:
            self._draw_flow_menu()

        # Context menu (topmost within modal)
        if self.ctx:
            self._draw_ctx_menu()

        # FEATURE-MAP-084: subflow delete confirm overlay.
        if self._delete_confirm:
            self._draw_delete_confirm()

        # FEATURE-MAP-084: prefs panel overlay.
        if self.prefs_open:
            self._draw_prefs_panel()

        # FEATURE-MAP-081: post-drop red flash for rejected end_* drag.
        if self._end_op_reject_flash > 0:
            r = self._block_panel
            pygame.draw.rect(ed.screen, (140, 40, 40), pygame.Rect(r.x + 4, r.y + 4, r.w - 8, r.h - 8), 2)
            self._end_op_reject_flash -= 1

        # Resize grips
        self._resize_corner_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(ed.screen, (90, 160, 120), [
            (panel.right - 2, panel.bottom - 14), (panel.right - 2, panel.bottom - 2),
            (panel.right - 14, panel.bottom - 2)])
        self._resize_corner_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(ed.screen, (90, 160, 120), [
            (panel.x + 2, panel.bottom - 14), (panel.x + 2, panel.bottom - 2),
            (panel.x + 14, panel.bottom - 2)])

    def _draw_splitters(self) -> None:
        mxp, myp = pygame.mouse.get_pos()
        for rect in self._split_rects.values():
            hot = rect.collidepoint(mxp, myp) or self._split_drag is not None
            pygame.draw.rect(self.ed.screen, _C_SPLIT_HOT if hot else _C_SPLIT, rect)

    def _draw_left_collapsed(self) -> None:
        """FEATURE-MAP-080: thin strip shown when the map/events selector is collapsed."""
        ed = self.ed
        r = self._map_panel
        pygame.draw.rect(ed.screen, _C_SUBPANEL, r)
        pygame.draw.rect(ed.screen, _C_BORDER_DIM, r, 1)
        self._left_collapse_btn = pygame.Rect(r.x + 1, r.y + 1, r.w - 2, 18)
        _btn(ed, self._left_collapse_btn, "\u25B6", (40, 60, 48), _C_HEAD)
        # Vertical "Maps / Events" hint.
        label = "MAPS / EVENTS"
        for i, ch in enumerate(label):
            ed.screen.blit(ed.font_small.render(ch, True, _C_TEXT_DIM),
                           (r.x + 6, r.y + 26 + i * (ed.font_small.get_linesize() - 2)))

    def _draw_doc_collapsed(self) -> None:
        """FEATURE-MAP-081: thin strip shown when the documentation panel is collapsed."""
        ed = self.ed
        r = self._doc_panel
        pygame.draw.rect(ed.screen, _C_SUBPANEL, r)
        pygame.draw.rect(ed.screen, _C_BORDER_DIM, r, 1)
        self._doc_collapse_btn = pygame.Rect(r.x + 1, r.y + 1, r.w - 2, 18)
        _btn(ed, self._doc_collapse_btn, "\u25C0", (40, 60, 48), _C_HEAD)
        self._doc_popout_btn = pygame.Rect(r.x + 1, r.y + 22, r.w - 2, 18)
        _btn(ed, self._doc_popout_btn, "Pop", (50, 70, 90), (200, 225, 245))
        label = "DOCS"
        for i, ch in enumerate(label):
            ed.screen.blit(ed.font_small.render(ch, True, _C_TEXT_DIM),
                           (r.x + 6, r.y + 46 + i * (ed.font_small.get_linesize() - 2)))
        self._doc_search_rect = pygame.Rect(0, 0, 1, 1)
        self._doc_body_rect = pygame.Rect(0, 0, 1, 1)

    def _draw_map_panel(self) -> None:
        ed = self.ed
        r = self._map_panel
        _subpanel(ed, r, "Maps")
        # FEATURE-MAP-080: collapse toggle in the header.
        self._left_collapse_btn = pygame.Rect(r.right - 20, r.y + 1, 18, 18)
        _btn(ed, self._left_collapse_btn, "\u25C0", (40, 60, 48), _C_HEAD)
        inner = pygame.Rect(r.x + 6, r.y + 24, r.w - 12, r.h - 30)
        # Search box
        self._map_search_rect = pygame.Rect(inner.x, inner.y, inner.w, 22)
        _textbox(ed, self._map_search_rect, self.map_search, self.focus == "map_search", "search maps")
        mini_h = max(72, min(140, (inner.h - 26) // 2))
        self._draw_mini_map(pygame.Rect(inner.x, inner.y + 26, inner.w, mini_h))
        list_rect = pygame.Rect(inner.x, inner.y + 26 + mini_h + 4, inner.w, inner.h - 26 - mini_h - 4)
        prev = ed.screen.get_clip()
        ed.screen.set_clip(list_rect)
        q = self.map_search.strip().lower()
        shown = [m for m in self.maps if q in m.lower()] if q else self.maps
        rh = ed.font_small.get_linesize() + 4
        self.map_scroll = max(0, min(self.map_scroll, max(0, len(shown) * rh - list_rect.h)))
        y = list_rect.y - self.map_scroll
        self._map_rows = []
        for m in shown:
            row = pygame.Rect(list_rect.x, y, list_rect.w, rh)
            if row.bottom > list_rect.y and row.top < list_rect.bottom:
                sel = m == self.sel_map_id
                if sel:
                    pygame.draw.rect(ed.screen, _C_SEL, row)
                ed.screen.blit(ed.font_small.render(m[:40], True, _C_HEAD if sel else _C_TEXT),
                               (row.x + 4, row.y + 2))
            self._map_rows.append((m, row))
            y += rh
        ed.screen.set_clip(prev)

    def _draw_events_panel(self) -> None:
        ed = self.ed
        r = self._events_panel
        title = f"Events ({len(self.events)})"
        _subpanel(ed, r, title)
        inner = pygame.Rect(r.x + 6, r.y + 24, r.w - 12, r.h - 30)
        # Button row — FEATURE-MAP-070: single Delete with dynamic label
        n_checks = len(self.checks)
        del_label = f"Delete ({n_checks})" if n_checks >= 2 else "Delete"
        bw = max(50, (inner.w - 3 * 4) // 4)
        by = inner.y
        self._event_btns = {}
        labels = [("add", "Add"), ("copy", "Copy"), ("paste", "Paste"), ("delete", del_label)]
        for i, (key, lbl) in enumerate(labels):
            br = pygame.Rect(inner.x + i * (bw + 4), by, bw, 22)
            self._event_btns[key] = br
            bg = (80, 44, 44) if key == "delete" else (40, 60, 48)
            _btn(ed, br, lbl, bg, _C_TEXT)
        list_rect = pygame.Rect(inner.x, by + 26, inner.w, inner.h - 26)
        prev = ed.screen.get_clip()
        ed.screen.set_clip(list_rect)
        rh = ed.font_small.get_linesize() + 6
        self.event_scroll = max(0, min(self.event_scroll, max(0, len(self.events) * rh - list_rect.h)))
        y = list_rect.y - self.event_scroll
        self._event_rows = []
        for i, ev in enumerate(self.events):
            row = pygame.Rect(list_rect.x, y, list_rect.w, rh)
            chk = pygame.Rect(row.x + 3, row.y + 4, 14, 14)
            if row.bottom > list_rect.y and row.top < list_rect.bottom:
                if i == self.sel_event_index:
                    pygame.draw.rect(ed.screen, _C_SEL, row)
                    pygame.draw.rect(ed.screen, _C_SEL_BORDER, row, 1)
                pygame.draw.rect(ed.screen, (30, 36, 32), chk)
                pygame.draw.rect(ed.screen, _C_BORDER_DIM, chk, 1)
                if i in self.checks:
                    pygame.draw.line(ed.screen, _C_BORDER, (chk.x + 2, chk.centery),
                                     (chk.centerx, chk.bottom - 3), 2)
                    pygame.draw.line(ed.screen, _C_BORDER, (chk.centerx, chk.bottom - 3),
                                     (chk.right - 2, chk.y + 2), 2)
                label_x = chk.right + 6
                label_w = row.right - label_x - 4
                if i == self.rename_index and self.focus == "rename":
                    # Inline rename text field (FEATURE-MAP-070)
                    fr = pygame.Rect(label_x, row.y + 2, label_w, rh - 4)
                    self._rename_rect = fr
                    _textbox(ed, fr, self.rename_buf, True, "new id")
                else:
                    a = ev.get("anchor") or {}
                    label = f"{i + 1}. {str(ev.get('id', '?'))[:22]} ({a.get('x', '?')},{a.get('y', '?')})"
                    ed.screen.blit(ed.font_small.render(label, True, _C_TEXT), (label_x, row.y + 3))
            self._event_rows.append({"index": i, "row": row, "chk": chk})
            y += rh
        ed.screen.set_clip(prev)

    def _draw_block_panel(self) -> None:
        ed = self.ed
        r = self._block_panel
        name = "Block editor"
        if self.sel_event_index is not None and 0 <= self.sel_event_index < len(self.events):
            name = f"Blocks · {self.events[self.sel_event_index].get('id', '')[:24]}"
        _subpanel(ed, r, name)
        self._block_rows = []
        self._tab_rects = []
        if self.sel_event_index is None:
            inner0 = pygame.Rect(r.x + 6, r.y + 24, r.w - 12, r.h - 30)
            ed.screen.blit(ed.font_small.render("Select an event to edit its script.", True, _C_TEXT_DIM),
                           (inner0.x + 2, inner0.y + 4))
            return
        # FEATURE-MAP-074: subflow tab strip (menu | Main Flow | subflow tabs | +)
        strip = pygame.Rect(r.x + 6, r.y + 24, r.w - 12, 22)
        self._draw_tab_strip(strip)
        inner = pygame.Rect(r.x + 6, strip.bottom + 4, r.w - 12, r.h - 30 - strip.h - 4)
        rows = self._visible_rows()
        rh = ed.font_small.get_linesize() + 8
        content_h = len(rows) * rh
        self.block_scroll = max(0, min(self.block_scroll, max(0, content_h - inner.h)))
        prev = ed.screen.get_clip()
        ed.screen.set_clip(inner)
        y = inner.y - self.block_scroll
        for rowinfo in rows:
            path = rowinfo["path"]
            node = rowinfo["node"]
            depth = rowinfo["depth"]
            kind = rowinfo["kind"]
            rect = pygame.Rect(inner.x, y, inner.w, rh)
            rowinfo["rect"] = rect
            if rect.bottom > inner.y and rect.top < inner.bottom:
                self._draw_block_row(rowinfo, rect, depth, node, kind, path, inner)
            self._block_rows.append(rowinfo)
            y += rh
        # Drop indicator
        if self.drag and self.drag.get("active") and self._block_panel.collidepoint(pygame.mouse.get_pos()):
            self._draw_drop_indicator()
        ed.screen.set_clip(prev)

    def _visible_rows(self) -> list[dict]:
        """FEATURE-MAP-074/076: flatten the active flow, hiding children of collapsed regions."""
        rows: list[dict] = []
        flow = self.active_flow

        def rec(nodes: list[dict], prefix: tuple[int, ...], depth: int) -> None:
            for i, node in enumerate(nodes):
                p = prefix + (i,)
                op = str(node.get("op", ""))
                is_open = ess.is_block_open(op) and isinstance(node.get("children"), list)
                collapsed = is_open and (flow, p) in self.collapsed
                rows.append({"path": p, "node": node, "depth": depth,
                             "kind": "open" if is_open else "leaf",
                             "collapsible": is_open, "collapsed": collapsed})
                if is_open and not collapsed:
                    rec(node["children"], p, depth + 1)
                    end_op = ess.op_block_end(op) or "end"
                    rows.append({"path": p, "node": {"op": end_op}, "depth": depth, "kind": "end"})
                elif is_open and collapsed:
                    end_op = ess.op_block_end(op) or "end"
                    rows.append({"path": p, "node": {"op": end_op}, "depth": depth, "kind": "end"})

        rec(self.tree, (), 0)
        return rows

    def _draw_tab_strip(self, strip: pygame.Rect) -> None:
        ed = self.ed
        pygame.draw.rect(ed.screen, (24, 30, 26), strip)
        # Library/search menu button on the far left
        self._tab_menu_btn = pygame.Rect(strip.x, strip.y, 22, strip.h)
        _btn(ed, self._tab_menu_btn, "\u2261", (40, 60, 48), _C_HEAD)
        # New-subflow button on the far right
        self._tab_new_btn = pygame.Rect(strip.right - 22, strip.y, 22, strip.h)
        _btn(ed, self._tab_new_btn, "+", (40, 60, 48), _C_HEAD)
        # Tabs between
        x = self._tab_menu_btn.right + 3
        avail_right = self._tab_new_btn.x - 3
        for name in self.open_tabs:
            if name not in self.flows:
                continue
            label = "Main Flow" if name == "main" else name
            if self.tab_rename == name:
                label = self.tab_rename_buf or name
            tw = min(ed.font_small.size(label)[0] + 16, 160)
            tr = pygame.Rect(x, strip.y, tw, strip.h)
            if tr.right > avail_right:
                break
            on = name == self.active_flow
            pygame.draw.rect(ed.screen, (60, 84, 66) if on else (32, 40, 34), tr)
            pygame.draw.rect(ed.screen, _C_BORDER if on else _C_BORDER_DIM, tr, 1)
            txt = (label + "|") if self.tab_rename == name else label
            ed.screen.blit(ed.font_small.render(txt[:22], True, _C_HEAD if on else _C_TEXT_DIM),
                           (tr.x + 6, tr.y + 2))
            self._tab_rects.append((name, tr))
            x = tr.right + 3

    def _draw_flow_menu(self) -> None:
        """FEATURE-MAP-074: far-left searchable list of all flows (open one as a tab)."""
        ed = self.ed
        w, h = 240, 240
        mx = self._tab_menu_btn.x
        my = self._tab_menu_btn.bottom + 2
        mx = min(mx, self.panel_rect.right - w - 6)
        my = min(my, self.panel_rect.bottom - h - 6)
        rect = pygame.Rect(mx, my, w, h)
        self._flow_menu_rect = rect
        pygame.draw.rect(ed.screen, (26, 32, 28), rect)
        pygame.draw.rect(ed.screen, _C_BORDER, rect, 1)
        sr = pygame.Rect(rect.x + 6, rect.y + 6, rect.w - 12, 22)
        self._flow_menu_search_rect = sr
        _textbox(ed, sr, self.flow_menu_search, self.focus == "flow_search", "search subflows")
        q = self.flow_menu_search.strip().lower()
        names = ["main"] + sorted(n for n in self.flows if n != "main")
        names = [n for n in names if q in (("main flow" if n == "main" else n).lower())] if q else names
        list_rect = pygame.Rect(rect.x + 6, sr.bottom + 4, rect.w - 12, rect.bottom - sr.bottom - 10)
        prev = ed.screen.get_clip()
        ed.screen.set_clip(list_rect)
        rh = ed.font_small.get_linesize() + 4
        y = list_rect.y
        self._flow_menu_rows = []
        for n in names:
            row = pygame.Rect(list_rect.x, y, list_rect.w, rh)
            disp = "Main Flow" if n == "main" else n
            opened = n in self.open_tabs
            ed.screen.blit(ed.font_small.render(("\u2713 " if opened else "  ") + disp[:28], True,
                           _C_HEAD if n == self.active_flow else _C_TEXT), (row.x + 4, row.y + 2))
            self._flow_menu_rows.append((n, row))
            y += rh
        ed.screen.set_clip(prev)

    def _draw_block_row(self, rowinfo, rect, depth, node, kind, path, inner) -> None:
        ed = self.ed
        indent = 8 + depth * 16
        op = str(node.get("op", ""))
        doc = ess.op_documentation(op)
        label = doc.get("label", op)
        if kind == "end":
            ed.screen.blit(ed.font_small.render(f"\u2514 {label}", True, _C_TEXT_DIM),
                           (rect.x + indent, rect.y + 4))
            return
        sel = self.block_sel == path
        is_comment = op == "comment"
        card = pygame.Rect(rect.x + indent, rect.y + 2, rect.w - indent - 6, rect.h - 4)
        if is_comment:
            bg = _C_SEL if sel else (40, 46, 34)
        else:
            bg = _C_SEL if sel else (34, 42, 36) if kind == "open" else (30, 35, 31)
        pygame.draw.rect(ed.screen, bg, card)
        pygame.draw.rect(ed.screen, _C_SEL_BORDER if sel else _C_BORDER_DIM, card, 1)
        text_x = card.x + 6
        # FEATURE-MAP-076: collapse caret for collapsible (region/block) rows.
        rowinfo["caret"] = None
        if rowinfo.get("collapsible"):
            caret = pygame.Rect(card.x + 3, card.y + 2, 14, card.h - 4)
            tri = "\u25B6" if rowinfo.get("collapsed") else "\u25BC"
            ed.screen.blit(ed.font_small.render(tri, True, _C_HEAD), (caret.x, caret.y + 1))
            rowinfo["caret"] = caret
            text_x = caret.right + 4
        if is_comment:
            ctext = str((node.get("args") or {}).get("text", ""))
            ed.screen.blit(ed.font_small.render(("# " + ctext)[:60], True, (200, 210, 150)),
                           (text_x, card.y + 3))
            rowinfo["argfields"] = []
            return
        # FEATURE-MAP-081: show args.name for region blocks (e.g. "Region: Intro").
        disp = label
        if op == "region":
            rname = str((node.get("args") or {}).get("name", "")).strip()
            if rname:
                disp = f"Region: {rname}"
        ed.screen.blit(ed.font_small.render(disp, True, _C_HEAD if kind == "open" else _C_TEXT),
                       (text_x, card.y + 3))
        # Inline args
        args = node.get("args") or {}
        rowinfo["argfields"] = []
        ax = text_x + ed.font_small.size(label)[0] + 14
        for k, v in args.items():
            if k == "skip":
                continue
            editing = self.edit_field == (path, k)
            shown = self.edit_buf if editing else str(v)
            seg = f"{k}={shown}"
            tw = ed.font_small.size(seg)[0] + 8
            fr = pygame.Rect(ax, card.y + 2, min(tw, card.right - ax - 4), card.h - 4)
            if fr.right > card.right - 2:
                break
            pygame.draw.rect(ed.screen, (44, 52, 46) if editing else (24, 30, 26), fr)
            pygame.draw.rect(ed.screen, _C_BORDER if editing else _C_BORDER_DIM, fr, 1)
            ed.screen.blit(ed.font_small.render(seg, True, _C_TEXT), (fr.x + 3, fr.y + 2))
            rowinfo["argfields"].append((k, fr))
            ax = fr.right + 6

    def _draw_drop_indicator(self) -> None:
        # FEATURE-MAP-081: red indicator when dragging a bare end_* op.
        is_end_drag = (self.drag and self.drag.get("type") == "action"
                       and ess.is_block_close(self.drag.get("op", "")))
        if is_end_drag:
            r = self._block_panel
            flash_rect = pygame.Rect(r.x + 4, r.y + 4, r.w - 8, r.h - 8)
            pygame.draw.rect(self.ed.screen, (140, 40, 40), flash_rect, 2)
            self.ed.screen.blit(
                self.ed.font_small.render("No matching opening statement", True, (240, 80, 80)),
                (r.x + 10, r.bottom - 22))
            return
        _, idx_y = self._compute_drop(pygame.mouse.get_pos()[1], want_y=True)
        if idx_y is not None:
            pygame.draw.line(self.ed.screen, _C_SPLIT_HOT,
                             (self._block_panel.x + 6, idx_y),
                             (self._block_panel.right - 8, idx_y), 2)

    def _draw_action_panel(self) -> None:
        ed = self.ed
        r = self._action_panel
        _subpanel(ed, r, "Actions")
        inner = pygame.Rect(r.x + 4, r.y + 24, r.w - 8, r.h - 30)
        # Tabs
        self._action_tab_rects = []
        tabs = ["Favorites", "All"]
        tw = (inner.w - 4) // 2
        for i, t in enumerate(tabs):
            tr = pygame.Rect(inner.x + i * (tw + 4), inner.y, tw, 20)
            self._action_tab_rects.append((t, tr))
            on = self.action_tab == t
            pygame.draw.rect(ed.screen, (60, 84, 66) if on else (32, 40, 34), tr)
            pygame.draw.rect(ed.screen, _C_BORDER if on else _C_BORDER_DIM, tr, 1)
            ed.screen.blit(ed.font_small.render(t, True, _C_HEAD if on else _C_TEXT_DIM),
                           (tr.x + 6, tr.y + 2))
        # Search
        self._action_search_rect = pygame.Rect(inner.x, inner.y + 24, inner.w, 22)
        _textbox(ed, self._action_search_rect, self.action_search,
                 self.focus == "action_search", "search actions")
        list_rect = pygame.Rect(inner.x, inner.y + 50, inner.w, inner.h - 50)
        prev = ed.screen.get_clip()
        ed.screen.set_clip(list_rect)
        self._action_rows = []
        self._action_header_rows = []
        entries = self._action_entries()
        rh = ed.font_small.get_linesize() + 5
        total = sum(rh for kind, _ in entries)
        self.action_scroll = max(0, min(self.action_scroll, max(0, total - list_rect.h)))
        y = list_rect.y - self.action_scroll
        for kind, payload in entries:
            row = pygame.Rect(list_rect.x, y, list_rect.w, rh)
            if row.bottom > list_rect.y and row.top < list_rect.bottom:
                if kind == "header":
                    # FEATURE-MAP-081: collapsible category header with caret.
                    pygame.draw.rect(ed.screen, (28, 34, 30), row)
                    q = self.action_search.strip().lower()
                    is_col = (not q) and (payload in self.action_cat_collapsed)
                    caret = "\u25B6" if is_col else "\u25BC"
                    ed.screen.blit(ed.font_small.render(caret, True, (255, 205, 140)),
                                   (row.x + 3, row.y + 2))
                    ed.screen.blit(ed.font_small.render(payload, True, (255, 205, 140)),
                                   (row.x + 16, row.y + 2))
                    self._action_header_rows.append((payload, row))
                else:
                    # FEATURE-MAP-081: indent op rows under their category header.
                    op = payload
                    lbl = ess.op_documentation(op).get("label", op)
                    star = pygame.Rect(row.right - 20, row.y + 2, 16, 16)
                    fav = op in self.favorites
                    ed.screen.blit(ed.font_small.render(lbl[:28], True, _C_TEXT), (row.x + 16, row.y + 2))
                    ed.screen.blit(ed.font_small.render("\u2605" if fav else "\u2606", True,
                                   (240, 210, 90) if fav else _C_TEXT_DIM), (star.x, star.y))
                    self._action_rows.append({"op": op, "row": row, "star": star})
            else:
                if kind == "op":
                    self._action_rows.append({"op": payload, "row": row,
                                              "star": pygame.Rect(row.right - 20, row.y + 2, 16, 16)})
            y += rh
        ed.screen.set_clip(prev)

    def _action_entries(self) -> list[tuple[str, str]]:
        q = self.action_search.strip().lower()
        ops = list(ess.cpp_script_ops_ordered())

        def match(op: str) -> bool:
            if not q:
                return True
            lbl = ess.op_documentation(op).get("label", op).lower()
            return q in op.lower() or q in lbl

        if self.action_tab == "Favorites":
            return [("op", op) for op in self.favorites if match(op)]
        # All -> grouped by category
        buckets: dict[str, list[str]] = {}
        for op in ops:
            if not match(op):
                continue
            buckets.setdefault(ess.op_category(op), []).append(op)
        out: list[tuple[str, str]] = []
        for cat in sorted(buckets.keys(), key=lambda s: s.lower()):
            # FEATURE-MAP-081: paired palette ordering (opener then end block).
            sorted_ops = ess.sort_palette_ops_in_category(
                sorted(buckets[cat], key=lambda o: ess.op_documentation(o).get("label", o).lower()))
            out.append(("header", cat))
            # FEATURE-MAP-081: auto-expand when searching, respect collapse otherwise.
            collapsed = (not q) and (cat in self.action_cat_collapsed)
            if not collapsed:
                for op in sorted_ops:
                    out.append(("op", op))
        return out

    def _resolved_doc_op(self) -> str | None:
        op = self.doc_op
        if op is None and self.block_sel is not None:
            node = _node_at(self.tree, self.block_sel)
            if node:
                op = str(node.get("op"))
        return op

    def _draw_doc_panel(self) -> None:
        ed = self.ed
        r = self._doc_panel
        _subpanel(ed, r, "Documentation")
        # FEATURE-MAP-081: collapse toggle (layout-level) + pop-out.
        self._doc_collapse_btn = pygame.Rect(r.right - 22, r.y, 20, 18)
        _btn(ed, self._doc_collapse_btn, "\u25B6", (40, 60, 48), _C_HEAD)
        self._doc_popout_btn = pygame.Rect(r.right - 66, r.y, 42, 18)
        _btn(ed, self._doc_popout_btn, "Pop", (50, 70, 90), (200, 225, 245))
        inner = pygame.Rect(r.x + 6, r.y + 24, r.w - 12, r.h - 30)
        # Search box
        self._doc_search_rect = pygame.Rect(inner.x, inner.y, inner.w, 22)
        _textbox(ed, self._doc_search_rect, self.doc_search, self.focus == "doc_search", "search docs")
        body = pygame.Rect(inner.x, inner.y + 26, inner.w, inner.h - 26)
        self._doc_body_rect = body
        op = self._resolved_doc_op()
        if op is None:
            ed.screen.blit(ed.font_small.render("Select a block or click Show", True, _C_TEXT_DIM),
                           (body.x + 2, body.y + 2))
            ed.screen.blit(ed.font_small.render("Documentation for details.", True, _C_TEXT_DIM),
                           (body.x + 2, body.y + 2 + ed.font_small.get_linesize()))
            return
        lines = self._doc_lines_for(op, body.w - 8)
        q = self.doc_search.strip().lower()
        if q:
            lines = [ln for ln in lines if q in ln.lower()]
        lh = ed.font_small.get_linesize()
        self._doc_total_h = len(lines) * lh
        self.doc_scroll = max(0, min(self.doc_scroll, max(0, self._doc_total_h - body.h)))
        prev = ed.screen.get_clip()
        ed.screen.set_clip(body)
        y = body.y - self.doc_scroll
        for ln in lines:
            if y + lh >= body.y and y <= body.bottom:
                ed.screen.blit(ed.font_small.render(ln, True, _C_TEXT), (body.x + 2, y))
            y += lh
        ed.screen.set_clip(prev)

    def _doc_lines_for(self, op: str, width_px: int) -> list[str]:
        doc = ess.op_documentation(op)
        mf = lambda s: self.ed.font_small.size(s)[0]
        return odoc.build_structured_doc_lines(op, doc, width_px, mf)

    def _draw_drag_ghost(self) -> None:
        ed = self.ed
        mx, my = pygame.mouse.get_pos()
        if self.drag["type"] == "action":
            op = self.drag["op"]
            label = ess.op_documentation(op).get("label", op)
        else:
            node = _node_at(self.tree, self.drag["path"])
            label = ess.op_documentation(str(node.get("op"))).get("label", "?") if node else "?"
        surf = ed.font_small.render(f"\u2295 {label}", True, (240, 245, 240))
        bg = pygame.Rect(mx + 10, my + 6, surf.get_width() + 12, surf.get_height() + 6)
        gs = pygame.Surface((bg.w, bg.h), pygame.SRCALPHA)
        gs.fill((40, 70, 50, 220))
        ed.screen.blit(gs, bg.topleft)
        pygame.draw.rect(ed.screen, _C_BORDER, bg, 1)
        ed.screen.blit(surf, (bg.x + 6, bg.y + 3))

    def _draw_ctx_menu(self) -> None:
        ed = self.ed
        if self.ctx.get("panels"):
            self._draw_ctx_cascade()
            return
        items = self.ctx["items"]
        fs = ed.font_small
        w = max(fs.size(lbl)[0] for lbl, _ in items) + 24
        rh = fs.get_linesize() + 8
        h = rh * len(items)
        px, py = self.ctx["pos"]
        px = min(px, self.panel_rect.right - w - 4)
        py = min(py, self.panel_rect.bottom - h - 4)
        rect = pygame.Rect(px, py, w, h)
        self.ctx["rect"] = rect
        pygame.draw.rect(ed.screen, (28, 34, 30), rect)
        pygame.draw.rect(ed.screen, _C_BORDER, rect, 1)
        rows = []
        for i, (lbl, act) in enumerate(items):
            rr = pygame.Rect(rect.x, rect.y + i * rh, w, rh)
            if rr.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(ed.screen, _C_SEL, rr)
            ed.screen.blit(fs.render(lbl, True, _C_TEXT), (rr.x + 10, rr.y + 4))
            rows.append((rr, act))
        self.ctx["rows"] = rows

    def _draw_ctx_cascade(self) -> None:
        ed = self.ed
        fs = ed.font_small
        mx, my = pygame.mouse.get_pos()
        panels = ectx.layout_cascade_panels(
            self.ctx["filtered"],
            sx=self.ctx["pos"][0],
            sy=self.ctx["pos"][1],
            mouse_xy=(mx, my),
            screen_w=ed.screen.get_width(),
            screen_h=ed.screen.get_height(),
            row_h=fs.get_linesize() + 8,
            pad=6,
            measure=lambda s: fs.size(s)[0],
            max_panel_w=min(320, self.panel_rect.w - 16),
        )
        self.ctx["panels"] = panels
        for panel in panels:
            pr = pygame.Rect(panel["x"], panel["y"], panel["w"], panel["h"])
            pygame.draw.rect(ed.screen, (28, 34, 30), pr)
            pygame.draw.rect(ed.screen, _C_BORDER, pr, 1)
            for row in panel.get("rows", []):
                rr = pygame.Rect(row["x"], row["y"], row["w"], row["h"])
                node = row.get("node") or {}
                if rr.collidepoint(mx, my):
                    pygame.draw.rect(ed.screen, _C_SEL, rr)
                y = rr.y + 4
                for ln in row.get("label_lines", [""]):
                    ed.screen.blit(fs.render(ln, True, _C_TEXT), (rr.x + 8, y))
                    y += fs.get_linesize() - 2
                if str(node.get("type")) == "submenu":
                    ed.screen.blit(fs.render("\u25B6", True, _C_TEXT_DIM), (rr.right - 14, rr.y + 4))

    def _draw_delete_confirm(self) -> None:
        """FEATURE-MAP-084: inline confirm before permanently deleting a subflow."""
        ed = self.ed
        name = str(self._delete_confirm.get("name", ""))
        pw, ph = 360, 150
        rect = pygame.Rect(0, 0, pw, ph)
        rect.center = self.panel_rect.center
        pygame.draw.rect(ed.screen, (24, 28, 24), rect)
        pygame.draw.rect(ed.screen, (180, 80, 80), rect, 2)
        ed.screen.blit(ed.font.render("Delete subflow?", True, (255, 200, 200)), (rect.x + 16, rect.y + 14))
        msg = f"Permanently delete '{name}' from this script?"
        for i, ln in enumerate(mtext.wrap_lines_to_width(ed.font_small, msg, rect.w - 32)):
            ed.screen.blit(ed.font_small.render(ln, True, _C_TEXT), (rect.x + 16, rect.y + 40 + i * ed.font_small.get_linesize()))
        chk_y = rect.y + 78
        self._delete_confirm["skip_chk"] = pygame.Rect(rect.x + 16, chk_y, 22, 22)
        pygame.draw.rect(ed.screen, (40, 48, 42), self._delete_confirm["skip_chk"], 1)
        if self._delete_confirm.get("skip_checked"):
            pygame.draw.line(ed.screen, _C_HEAD,
                             (self._delete_confirm["skip_chk"].x + 4, chk_y + 11),
                             (self._delete_confirm["skip_chk"].x + 9, chk_y + 16), 2)
            pygame.draw.line(ed.screen, _C_HEAD,
                             (self._delete_confirm["skip_chk"].x + 9, chk_y + 16),
                             (self._delete_confirm["skip_chk"].right - 4, chk_y + 6), 2)
        ed.screen.blit(ed.font_small.render("Don't ask again", True, _C_TEXT_DIM),
                       (rect.x + 44, chk_y + 3))
        self._delete_confirm["ok"] = pygame.Rect(rect.right - 176, rect.bottom - 38, 76, 26)
        self._delete_confirm["cancel"] = pygame.Rect(rect.right - 90, rect.bottom - 38, 76, 26)
        _btn(ed, self._delete_confirm["ok"], "Delete", (90, 44, 44), (255, 230, 230))
        _btn(ed, self._delete_confirm["cancel"], "Cancel", (55, 60, 55), _C_TEXT)

    def _handle_delete_confirm_click(self, mx: int, my: int) -> bool:
        dc = self._delete_confirm
        if dc is None:
            return False
        if dc.get("skip_chk") and dc["skip_chk"].collidepoint(mx, my):
            dc["skip_checked"] = not bool(dc.get("skip_checked"))
            return True
        if dc.get("cancel") and dc["cancel"].collidepoint(mx, my):
            self._delete_confirm = None
            return True
        if dc.get("ok") and dc["ok"].collidepoint(mx, my):
            name = str(dc.get("name", ""))
            if dc.get("skip_checked"):
                self.skip_subflow_delete_confirm = True
                self._save_config()
            self._delete_subflow(name, skip_confirm=True)
            return True
        return True

    def _draw_prefs_panel(self) -> None:
        """FEATURE-MAP-084: Event Engine preferences overlay."""
        ed = self.ed
        pw, ph = 340, 120
        rect = pygame.Rect(0, 0, pw, ph)
        rect.center = self.panel_rect.center
        self._prefs_panel_rect = rect
        pygame.draw.rect(ed.screen, (24, 28, 24), rect)
        pygame.draw.rect(ed.screen, _C_BORDER, rect, 2)
        ed.screen.blit(ed.font.render("Event Engine Prefs", True, _C_HEAD), (rect.x + 14, rect.y + 12))
        self._prefs_skip_chk = pygame.Rect(rect.x + 14, rect.y + 48, 22, 22)
        pygame.draw.rect(ed.screen, (40, 48, 42), self._prefs_skip_chk, 1)
        if self.skip_subflow_delete_confirm:
            pygame.draw.line(ed.screen, _C_HEAD,
                             (self._prefs_skip_chk.x + 4, self._prefs_skip_chk.y + 11),
                             (self._prefs_skip_chk.x + 9, self._prefs_skip_chk.y + 16), 2)
            pygame.draw.line(ed.screen, _C_HEAD,
                             (self._prefs_skip_chk.x + 9, self._prefs_skip_chk.y + 16),
                             (self._prefs_skip_chk.right - 4, self._prefs_skip_chk.y + 6), 2)
        ed.screen.blit(ed.font_small.render("Skip subflow delete confirmation", True, _C_TEXT),
                       (rect.x + 42, rect.y + 51))
        close_r = pygame.Rect(rect.right - 80, rect.bottom - 34, 66, 24)
        self._prefs_close_btn = close_r
        _btn(ed, close_r, "Close", (55, 60, 55), _C_TEXT)

    def _handle_prefs_click(self, mx: int, my: int) -> bool:
        if self._prefs_skip_chk.collidepoint(mx, my):
            self.skip_subflow_delete_confirm = not self.skip_subflow_delete_confirm
            self._save_config()
            return True
        if getattr(self, "_prefs_close_btn", None) and self._prefs_close_btn.collidepoint(mx, my):
            self.prefs_open = False
            return True
        if self._prefs_panel_rect.collidepoint(mx, my):
            return True
        self.prefs_open = False
        return True

    # ------------------------------------------------------------------
    # Drop computation
    # ------------------------------------------------------------------

    def _compute_drop(self, my: int, want_y: bool = False):
        rows = self._block_rows
        if not rows:
            return (((), 0), self._block_panel.y + 4) if want_y else ((), 0)
        for r in rows:
            rect = r["rect"]
            if rect.top <= my <= rect.bottom:
                mid = rect.centery
                path = r["path"]
                kind = r["kind"]
                if kind == "end":
                    if my < mid:
                        node = _node_at(self.tree, path)
                        target = (path, len(node.get("children") or []))
                    else:
                        target = (path[:-1], path[-1] + 1)
                elif kind == "open":
                    if my < mid:
                        target = (path[:-1], path[-1])
                    else:
                        target = (path, 0)
                else:
                    if my < mid:
                        target = (path[:-1], path[-1])
                    else:
                        target = (path[:-1], path[-1] + 1)
                yline = rect.top if my < mid else rect.bottom
                return (target, yline) if want_y else target
        last = rows[-1]["rect"]
        return (((), len(self.tree)), last.bottom) if want_y else ((), len(self.tree))

    # ------------------------------------------------------------------
    # Input: mouse down
    # ------------------------------------------------------------------

    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False

        # Context menu first
        if self.ctx:
            if self.ctx.get("panels"):
                aid = ectx.hit_test_panels(self.ctx.get("panels", []), (mx, my))
                if aid and button == 1:
                    self.ctx = None
                    self._dispatch_ctx_action_id(aid)
                    return True
            else:
                for rr, act in self.ctx.get("rows", []):
                    if rr.collidepoint(mx, my) and button == 1:
                        self.ctx = None
                        self._run_ctx_action(act)
                        return True
            self.ctx = None
            # fall through so the click can also act

        # Subflow library menu (FEATURE-MAP-074) — modal overlay over panels
        if self.flow_menu_open:
            if self._flow_menu_rect.collidepoint(mx, my):
                if self._flow_menu_search_rect.collidepoint(mx, my):
                    self.focus = "flow_search"
                    return True
                for n, row in self._flow_menu_rows:
                    if row.collidepoint(mx, my) and button == 1:
                        self._open_flow_tab(n)
                        self.flow_menu_open = False
                        self.focus = None
                        return True
                return True
            self.flow_menu_open = False
            self.focus = None
            # fall through

        # Header buttons
        if button == 1 and self.close_btn.collidepoint(mx, my):
            self.close_modal()
            return True
        if button == 1 and self._back_btn.collidepoint(mx, my):
            self.close_modal()
            self.ed.events_launcher_modal.open_modal()
            return True
        if button == 1 and self._help_btn.collidepoint(mx, my):
            self.ed._open_help_overlay(tab="script_ops", back_to="engine")
            return True
        if button == 1 and self._registry_btn.collidepoint(mx, my):
            self._flush_pending()
            self.ed.flag_registry_modal.open_modal()
            return True
        if button == 1 and self._prefs_btn.collidepoint(mx, my):
            self.prefs_open = not self.prefs_open
            return True

        # FEATURE-MAP-084: delete confirm overlay consumes clicks.
        if self._delete_confirm and button == 1:
            if self._handle_delete_confirm_click(mx, my):
                return True

        # FEATURE-MAP-084: prefs panel consumes clicks.
        if self.prefs_open and button == 1:
            if self._handle_prefs_click(mx, my):
                return True

        # Resize / move chrome
        if button == 1 and self._resize_corner_br.collidepoint(mx, my):
            self._drag_mode = "resize_br"
            self._drag_ref = (self.panel_rect.x, self.panel_rect.y)
            return True
        if button == 1 and self._resize_corner_bl.collidepoint(mx, my):
            self._drag_mode = "resize_bl"
            self._drag_ref = (self.panel_rect.right, self.panel_rect.y)
            return True
        if button == 1 and self._title_bar.collidepoint(mx, my):
            self._drag_mode = "move"
            self._drag_ref = (mx - self.panel_rect.x, my - self.panel_rect.y)
            return True

        # Splitters
        if button == 1:
            for key, rect in self._split_rects.items():
                if rect.collidepoint(mx, my):
                    self._split_drag = key
                    return True

        # FEATURE-MAP-080: collapse/expand the left selector
        if button == 1 and self._left_collapse_btn.collidepoint(mx, my):
            self.left_collapsed = not self.left_collapsed
            return True

        # Panels
        if self.left_collapsed and self._map_panel.collidepoint(mx, my):
            return True
        if self._map_panel.collidepoint(mx, my):
            self._commit_rename(cancel=False)
            self._md_map_panel(mx, my, button)
            return True
        if self._events_panel.collidepoint(mx, my):
            # If click landed outside the active rename field, commit it
            if self.focus == "rename" and not self._rename_rect.collidepoint(mx, my):
                self._commit_rename(cancel=False)
            self._md_events_panel(mx, my, button)
            return True
        if self._block_panel.collidepoint(mx, my):
            self._commit_rename(cancel=False)
            self._md_block_panel(mx, my, button)
            return True
        if self._action_panel.collidepoint(mx, my):
            self._commit_rename(cancel=False)
            self._md_action_panel(mx, my, button)
            return True
        if button == 1 and self._doc_collapse_btn.collidepoint(mx, my):
            self.doc_collapsed = not self.doc_collapsed
            return True
        if button == 1 and self._doc_popout_btn.collidepoint(mx, my):
            op = self._resolved_doc_op()
            self.ed.event_doc_popout_modal.open_for(op)
            return True
        # FEATURE-MAP-081: swallow clicks on collapsed doc strip.
        if self.doc_collapsed and self._doc_panel.collidepoint(mx, my):
            return True
        if self._doc_panel.collidepoint(mx, my):
            self._commit_rename(cancel=False)
            if button == 1 and self._doc_search_rect.collidepoint(mx, my):
                self.focus = "doc_search"
                return True
            self.focus = None
            return True
        # Click elsewhere inside panel: drop focus, keep open
        self._commit_rename(cancel=False)
        self.focus = None
        self._commit_arg_edit()
        return True

    def _md_map_panel(self, mx, my, button) -> None:
        if self._map_search_rect.collidepoint(mx, my):
            self.focus = "map_search"
            return
        if button == 1 and self._mini_map_rect.collidepoint(mx, my):
            tile = self._mini_map_tile_at(mx, my)
            if tile is not None:
                if self.sel_event_index is None and self.events:
                    self._select_event(0)
                self._set_event_anchor(tile[0], tile[1])
                return
        self.focus = None
        if button == 1:
            for m, row in self._map_rows:
                if row.collidepoint(mx, my):
                    if m != self.sel_map_id:
                        self._load_events_for_map(m)
                    return

    def _md_events_panel(self, mx, my, button) -> None:
        self.focus = None
        # Buttons
        if button == 1:
            for key, br in self._event_btns.items():
                if br.collidepoint(mx, my):
                    self._events_button(key)
                    return
        for ri in self._event_rows:
            if ri["row"].collidepoint(mx, my):
                idx = ri["index"]
                if button == 1 and ri["chk"].collidepoint(mx, my):
                    self.checks.symmetric_difference_update({idx})
                    return
                if button == 1:
                    self._select_event(idx)
                    return
                if button == 3:
                    self._select_event(idx)
                    self._open_event_ctx(mx, my, idx)
                    return

    def _delete_targets(self) -> set[int]:
        """FEATURE-MAP-070: resolve the set of event indices to delete based on checkbox state."""
        n = len(self.checks)
        if n >= 2:
            return set(self.checks)
        if n == 1:
            return set(self.checks)
        if self.sel_event_index is not None:
            return {self.sel_event_index}
        return set()

    def _events_button(self, key: str) -> None:
        if key == "add":
            self._add_event()
        elif key == "copy":
            if self.sel_event_index is not None:
                self._copy_event(self.sel_event_index)
        elif key == "paste":
            self._paste_event()
        elif key == "delete":
            targets = self._delete_targets()
            if targets:
                self._delete_indices(targets)
            else:
                self.ed.set_status("Select an event or check rows to delete.", kind="err")

    def _md_block_panel(self, mx, my, button) -> None:
        self.focus = None
        # FEATURE-MAP-074: subflow tab strip
        if button == 1 and self._tab_menu_btn.collidepoint(mx, my):
            self.flow_menu_open = not self.flow_menu_open
            self.flow_menu_search = ""
            return
        if button == 1 and self._tab_new_btn.collidepoint(mx, my):
            self._create_subflow()
            return
        for name, tr in self._tab_rects:
            if tr.collidepoint(mx, my):
                if button == 1:
                    self._switch_flow(name)
                elif button == 3:
                    self._open_tab_ctx(mx, my, name)
                return
        # FEATURE-MAP-076: collapse caret toggles a region/block
        for ri in self._block_rows:
            caret = ri.get("caret")
            if caret is not None and caret.collidepoint(mx, my) and button == 1:
                key = (self.active_flow, ri["path"])
                if key in self.collapsed:
                    self.collapsed.discard(key)
                else:
                    self.collapsed.add(key)
                return
        # Arg field click?
        for ri in self._block_rows:
            for k, fr in ri.get("argfields", []):
                if fr.collidepoint(mx, my) and button == 1:
                    self._begin_arg_edit(ri["path"], k)
                    return
        # Row click
        for ri in self._block_rows:
            if ri["rect"].collidepoint(mx, my) and ri["kind"] != "end":
                self._commit_arg_edit()
                path = ri["path"]
                self.block_sel = path
                self.doc_op = str(ri["node"].get("op"))
                if button == 1:
                    now = pygame.time.get_ticks() / 1000.0
                    if (
                        path == self._block_dbl_prev_path
                        and now - self._block_dbl_prev_time < _LIST_CLICK_DOUBLE
                    ):
                        self.ed.event_action_modal.open_for(self, self.active_flow, path)
                        self._block_dbl_prev_path = None
                        self._block_dbl_prev_time = 0.0
                        return
                    self._block_dbl_prev_path = path
                    self._block_dbl_prev_time = now
                    self.drag = {"type": "block", "path": path,
                                 "start": (mx, my), "active": False}
                elif button == 3:
                    self._open_block_ctx(mx, my)
                return
        self.block_sel = None
        if button == 3:
            self._open_block_ctx(mx, my)

    def _md_action_panel(self, mx, my, button) -> None:
        if self._action_search_rect.collidepoint(mx, my):
            self.focus = "action_search"
            return
        self.focus = None
        for t, tr in self._action_tab_rects:
            if tr.collidepoint(mx, my) and button == 1:
                self.action_tab = t
                self.action_scroll = 0
                return
        # FEATURE-MAP-081: category header click toggles collapse.
        for cat, hr in self._action_header_rows:
            if hr.collidepoint(mx, my) and button == 1:
                if cat in self.action_cat_collapsed:
                    self.action_cat_collapsed.discard(cat)
                else:
                    self.action_cat_collapsed.add(cat)
                self._save_config()
                return
        for ri in self._action_rows:
            if ri["star"].collidepoint(mx, my) and button == 1:
                self._toggle_favorite(ri["op"])
                return
            if ri["row"].collidepoint(mx, my):
                if button == 1:
                    self.doc_op = ri["op"]
                    self.drag = {"type": "action", "op": ri["op"],
                                 "start": (mx, my), "active": False}
                elif button == 3:
                    self.doc_op = ri["op"]
                return

    def _toggle_favorite(self, op: str) -> None:
        if op in self.favorites:
            self.favorites.remove(op)
        else:
            self.favorites.append(op)
        self._save_config()

    # ------------------------------------------------------------------
    # Context menus
    # ------------------------------------------------------------------

    def _open_event_ctx(self, mx, my, idx) -> None:
        tree = self._event_ctx_tree()
        filtered = ectx.filter_tree(
            tree,
            row_i=idx,
            has_clipboard=self.event_clipboard is not None,
        )
        self.ctx = {
            "kind": "event",
            "idx": idx,
            "pos": (mx, my),
            "filtered": filtered,
            "panels": [],
        }

    def _open_block_ctx(self, mx, my) -> None:
        row_i = self.block_sel[-1] if self.block_sel else None
        tree = self._block_ctx_tree()
        filtered = ectx.filter_tree(
            tree,
            row_i=row_i,
            has_clipboard=self.block_clipboard is not None,
        )
        self.ctx = {
            "kind": "block",
            "pos": (mx, my),
            "filtered": filtered,
            "panels": [],
        }

    def _dispatch_ctx_action_id(self, aid: str) -> None:
        if aid.startswith("ev:") or aid.startswith("blk:"):
            self._run_ctx_action(aid)
            return
        if aid == "step:delete" or aid == "blk:delete":
            self._delete_block()
        elif aid in ("step:copy", "blk:copy"):
            if self.block_sel is not None:
                node = _node_at(self.tree, self.block_sel)
                if node:
                    self.block_clipboard = copy.deepcopy(node)
        elif aid == "step:duplicate":
            if self.block_sel is not None:
                node = _node_at(self.tree, self.block_sel)
                if node:
                    self._undo_checkpoint()
                    parent, idx = self._insert_target_for_selection()
                    _insert_at(self.tree, parent, idx, copy.deepcopy(node))
                    self.block_sel = parent + (idx,)
                    self.script_dirty = True
        elif aid in ("step:paste_after", "blk:paste"):
            self._paste_block()
        elif aid.startswith("add:"):
            op = aid[4:].strip()
            if op and self.sel_event_index is not None:
                self._undo_checkpoint()
                node = _new_node(op)
                parent, idx = self._insert_target_for_selection()
                _insert_at(self.tree, parent, idx, node)
                self.block_sel = parent + (idx,)
                self.script_dirty = True
        elif aid == "rename_script":
            self.ed.set_status("Rename script via event row Rename.", kind="info")
        elif aid == "blk:editmodal" and self.block_sel is not None:
            self._commit_arg_edit()
            self.ed.event_action_modal.open_for(self, self.active_flow, self.block_sel)
        elif aid == "blk:add":
            self._add_block_default()
        elif aid == "blk:delete":
            self._delete_block()
        elif aid == "blk:doc" and self.block_sel is not None:
            node = _node_at(self.tree, self.block_sel)
            if node:
                self.doc_op = str(node.get("op"))

    def _run_ctx_action(self, act: str) -> None:
        if act.startswith("tab:"):
            self._run_tab_ctx_action(act)
            return
        if act == "ev:rename":
            if self.sel_event_index is not None:
                self._begin_rename(self.sel_event_index)
        elif act == "ev:copy":
            if self.sel_event_index is not None:
                self._copy_event(self.sel_event_index)
        elif act == "ev:paste":
            self._paste_event()
        elif act == "ev:delete":
            targets = self._delete_targets()
            if not targets and self.sel_event_index is not None:
                targets = {self.sel_event_index}
            if targets:
                self._delete_indices(targets)
        elif act == "ev:view":
            self._open_view_in_map()
        elif act == "ev:sprite":
            self._open_assign_sprite()
        elif act == "ev:trigger":
            if self.sel_event_index is not None:
                self._flush_pending()
                self.ed.event_trigger_modal.open_for(self, self.sel_event_index)
        elif act == "blk:copy":
            if self.block_sel is not None:
                node = _node_at(self.tree, self.block_sel)
                if node:
                    self.block_clipboard = copy.deepcopy(node)
        elif act == "blk:paste":
            self._paste_block()
        elif act == "blk:add":
            self._add_block_default()
        elif act == "blk:delete":
            self._delete_block()
        elif act == "blk:doc":
            if self.block_sel is not None:
                node = _node_at(self.tree, self.block_sel)
                if node:
                    self.doc_op = str(node.get("op"))
        elif act == "blk:editmodal":
            if self.block_sel is not None:
                self._commit_arg_edit()
                self.ed.event_action_modal.open_for(self, self.active_flow, self.block_sel)

    def _run_tab_ctx_action(self, act: str) -> None:
        parts = act.split(":", 2)
        verb = parts[1] if len(parts) > 1 else ""
        name = parts[2] if len(parts) > 2 else self.active_flow
        if verb == "close":
            self._close_tab(name)
        elif verb == "delete":
            self._delete_subflow(name)
        elif verb == "closeothers":
            self.open_tabs = ["main"] + ([name] if name != "main" else [])
            self._switch_flow(name if name in self.flows else "main")
        elif verb == "closeall":
            self.open_tabs = ["main"]
            self._switch_flow("main")
        elif verb == "rename":
            self._begin_tab_rename(name)
        elif verb == "save":
            self._persist_script()
            self.ed.set_status("Subflows saved.", kind="ok")

    def _insert_target_for_selection(self) -> tuple[tuple[int, ...], int]:
        """FEATURE-MAP-081: determine where to insert relative to current selection.

        When an open block is selected, inserts as last child (append).
        Otherwise inserts as sibling after selection, or at root end.
        """
        if self.block_sel is None:
            return (), len(self.tree)
        node = _node_at(self.tree, self.block_sel)
        if node is not None and ess.is_block_open(str(node.get("op", ""))) \
                and isinstance(node.get("children"), list):
            return self.block_sel, len(node["children"])
        return self.block_sel[:-1], self.block_sel[-1] + 1

    def _paste_block(self) -> None:
        if not self.block_clipboard or self.sel_event_index is None:
            return
        self._undo_checkpoint()
        node = copy.deepcopy(self.block_clipboard)
        parent, idx = self._insert_target_for_selection()
        _insert_at(self.tree, parent, idx, node)
        self.script_dirty = True

    def _add_block_default(self) -> None:
        if self.sel_event_index is None:
            return
        self._undo_checkpoint()
        node = _new_node("show_message")
        parent, idx = self._insert_target_for_selection()
        _insert_at(self.tree, parent, idx, node)
        self.block_sel = parent + (idx,)
        self.script_dirty = True

    def _delete_block(self) -> None:
        if self.block_sel is None:
            return
        self._undo_checkpoint()
        _pop_at(self.tree, self.block_sel)
        self.block_sel = None
        self.script_dirty = True

    # ------------------------------------------------------------------
    # Sub-modal launches
    # ------------------------------------------------------------------

    def _begin_submodal_edit(self) -> None:
        """Checkpoint session state before a sub-modal may mutate map events."""
        self._flush_pending()
        self._undo_checkpoint()

    def _open_view_in_map(self) -> None:
        if self.sel_event_index is None or self.sel_map_id is None:
            return
        self._begin_submodal_edit()
        self.ed.event_place_modal.open_for(self.sel_map_id, self.sel_event_index)

    def _open_assign_sprite(self) -> None:
        if self.sel_event_index is None or self.sel_map_id is None:
            return
        self._begin_submodal_edit()
        self.ed.event_sprite_modal.open_for(self.sel_map_id, self.sel_event_index)

    def refresh_after_submodal(self) -> None:
        """Called when View in Map / Assign Sprite committed changes."""
        if self.sel_map_id:
            sel = self.sel_event_index
            self.events = self.ed.read_map_events(self.sel_map_id)
            if sel is not None and 0 <= sel < len(self.events):
                self.sel_event_index = sel

    # ------------------------------------------------------------------
    # Arg editing
    # ------------------------------------------------------------------

    def _begin_arg_edit(self, path, key) -> None:
        self._commit_arg_edit()
        node = _node_at(self.tree, path)
        if not node:
            return
        val = (node.get("args") or {}).get(key)
        self.edit_field = (path, key)
        self.edit_buf = str(val)
        self.edit_is_int = isinstance(val, bool) is False and isinstance(val, int)
        self.focus = "arg"

    def _commit_arg_edit(self) -> None:
        if self.edit_field is None:
            return
        path, key = self.edit_field
        node = _node_at(self.tree, path)
        if node is not None:
            self._undo_checkpoint()
            args = node.setdefault("args", {})
            if self.edit_is_int:
                try:
                    args[key] = int(self.edit_buf)
                except ValueError:
                    args[key] = 0
            else:
                args[key] = self.edit_buf
            self.script_dirty = True
        self.edit_field = None
        self.edit_buf = ""
        if self.focus == "arg":
            self.focus = None

    # ------------------------------------------------------------------
    # Input: up / motion / wheel / keys
    # ------------------------------------------------------------------

    def handle_mouse_up(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        if self._split_drag is not None:
            self._save_config()
            self._split_drag = None
            return True
        self._drag_mode = "none"
        if self.drag and self.drag.get("active"):
            self._finish_drag(mx, my)
        self.drag = None
        return True

    def _finish_drag(self, mx, my) -> None:
        if not self._block_panel.collidepoint(mx, my) or self.sel_event_index is None:
            return
        self._undo_checkpoint()
        # FEATURE-MAP-081: reject bare end_* drops.
        if self.drag["type"] == "action" and ess.is_block_close(self.drag["op"]):
            self._end_op_reject_flash = 8
            self.ed.set_status(
                f"Cannot place '{self.drag['op']}' alone — no matching opening statement.",
                kind="err")
            return
        parent, idx = self._compute_drop(my)
        if self.drag["type"] == "action":
            _insert_at(self.tree, parent, idx, _new_node(self.drag["op"]))
            self.block_sel = parent + (idx,)
            self.script_dirty = True
        else:
            src = self.drag["path"]
            if _is_descendant(parent, src):
                return
            # adjust index if removing earlier sibling in same parent
            if parent == src[:-1] and src[-1] < idx:
                idx -= 1
            node = _pop_at(self.tree, src)
            if node is not None:
                _insert_at(self.tree, parent, idx, node)
                self.block_sel = parent + (idx,)
                self.script_dirty = True

    def handle_mouse_motion(self, mx: int, my: int) -> bool:
        if not self.open:
            return False
        if self._drag_mode == "resize_br":
            ax, ay = self._drag_ref
            self._panel_override = pygame.Rect(ax, ay, max(_PANEL_MIN_W, mx - ax), max(_PANEL_MIN_H, my - ay))
            return True
        if self._drag_mode == "resize_bl":
            right, ay = self._drag_ref
            new_x = min(mx, right - _PANEL_MIN_W)
            self._panel_override = pygame.Rect(new_x, ay, right - new_x, max(_PANEL_MIN_H, my - ay))
            return True
        if self._drag_mode == "move":
            ox, oy = self._drag_ref
            self._panel_override = pygame.Rect(mx - ox, my - oy, self.panel_rect.w, self.panel_rect.h)
            return True
        if self._split_drag is not None:
            self._update_split(mx, my)
            return True
        if self.drag and not self.drag.get("active"):
            sx, sy = self.drag["start"]
            if (mx - sx) ** 2 + (my - sy) ** 2 >= _DRAG_THRESHOLD ** 2:
                self.drag["active"] = True
        return True

    def _update_split(self, mx, my) -> None:
        body_w = self.panel_rect.w - 12
        body = pygame.Rect(self.panel_rect.x + 6, 0, body_w, 0)
        key = self._split_drag
        if key == "vsplit_a":
            self.frac_left = _clamp((mx - body.x) / max(1, body_w), 0.1, 0.6)
        elif key == "vsplit_b":
            self.frac_right = _clamp((body.right - mx) / max(1, body_w), 0.12, 0.6)
        elif key == "left_h":
            r = self._map_panel
            col_h = self._map_panel.h + self._events_panel.h
            self.frac_left_h = _clamp((my - r.y) / max(1, col_h), 0.12, 0.85)
        elif key == "mid_v":
            mid = self._block_panel.union(self._action_panel)
            self.frac_mid_v = _clamp((mx - mid.x) / max(1, mid.w), 0.2, 0.85)

    def handle_wheel(self, mx: int, my: int, y: int) -> bool:
        if not self.open:
            return False
        step = 3 * (self.ed.font_small.get_linesize() + 4)
        if self._map_panel.collidepoint(mx, my):
            self.map_scroll = max(0, self.map_scroll - y * step)
        elif self._events_panel.collidepoint(mx, my):
            self.event_scroll = max(0, self.event_scroll - y * step)
        elif self._block_panel.collidepoint(mx, my):
            self.block_scroll = max(0, self.block_scroll - y * step)
        elif self._action_panel.collidepoint(mx, my):
            self.action_scroll = max(0, self.action_scroll - y * step)
        elif self._doc_panel.collidepoint(mx, my) and not self.doc_collapsed:
            self.doc_scroll = max(0, self.doc_scroll - y * step)
        return True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        if self.ctx and event.key == pygame.K_ESCAPE:
            self.ctx = None
            return True
        # Rename field (FEATURE-MAP-070)
        if self.focus == "rename":
            if event.key == pygame.K_ESCAPE:
                self._commit_rename(cancel=True)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit_rename(cancel=False)
            elif event.key == pygame.K_BACKSPACE:
                self.rename_buf = self.rename_buf[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.rename_buf += event.unicode
            return True
        # Subflow tab rename (FEATURE-MAP-074)
        if self.focus == "tab_rename":
            if event.key == pygame.K_ESCAPE:
                self._commit_tab_rename(cancel=True)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit_tab_rename(cancel=False)
            elif event.key == pygame.K_BACKSPACE:
                self.tab_rename_buf = self.tab_rename_buf[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.tab_rename_buf += event.unicode
            return True
        # Documentation search (FEATURE-MAP-080)
        if self.focus == "doc_search":
            if event.key == pygame.K_ESCAPE:
                self.focus = None
            elif event.key == pygame.K_BACKSPACE:
                self.doc_search = self.doc_search[:-1]
                self.doc_scroll = 0
            elif event.unicode and event.unicode.isprintable():
                self.doc_search += event.unicode
                self.doc_scroll = 0
            return True
        # Subflow library search (FEATURE-MAP-074)
        if self.focus == "flow_search":
            if event.key == pygame.K_ESCAPE:
                self.focus = None
                self.flow_menu_open = False
            elif event.key == pygame.K_BACKSPACE:
                self.flow_menu_search = self.flow_menu_search[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.flow_menu_search += event.unicode
            return True
        # Text input fields
        if self.focus in ("map_search", "action_search"):
            buf = self.map_search if self.focus == "map_search" else self.action_search
            if event.key == pygame.K_ESCAPE:
                self.focus = None
            elif event.key == pygame.K_BACKSPACE:
                buf = buf[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.focus = None
            elif event.unicode and event.unicode.isprintable():
                buf += event.unicode
            if self.focus == "map_search":
                self.map_search = buf
                self.map_scroll = 0
            elif self.focus == "action_search":
                self.action_search = buf
                self.action_scroll = 0
            else:
                pass
            return True
        if self.edit_field is not None:
            if event.key == pygame.K_ESCAPE:
                self.edit_field = None
                self.edit_buf = ""
                self.focus = None
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit_arg_edit()
            elif event.key == pygame.K_BACKSPACE:
                self.edit_buf = self.edit_buf[:-1]
            elif event.unicode and event.unicode.isprintable():
                if self.edit_is_int:
                    if event.unicode.isdigit() or (event.unicode == "-" and not self.edit_buf):
                        self.edit_buf += event.unicode
                else:
                    self.edit_buf += event.unicode
            return True
        # Global keys
        if self._delete_confirm:
            if event.key == pygame.K_ESCAPE:
                self._delete_confirm = None
                return True
            return True
        if self.prefs_open and event.key == pygame.K_ESCAPE:
            self.prefs_open = False
            return True
        if event.key == pygame.K_ESCAPE:
            if self.flow_menu_open:
                self.flow_menu_open = False
                return True
            self.close_modal()
            return True
        if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and self.block_sel is not None:
            self._delete_block()
            return True
        mods = pygame.key.get_mods()
        if mods & pygame.KMOD_META or mods & pygame.KMOD_CTRL:
            if event.key == pygame.K_s:
                self._flush_pending()
                self.ed.set_status("Event Engine saved.", kind="ok")
                return True
            if event.key == pygame.K_c and self.block_sel is not None:
                node = _node_at(self.tree, self.block_sel)
                if node:
                    self.block_clipboard = copy.deepcopy(node)
                return True
            if event.key == pygame.K_v and self.block_clipboard is not None:
                self._paste_block()
                return True
            if event.key == pygame.K_z:
                self._undo_session()
                return True
            if event.key == pygame.K_y:
                self._redo_session()
                return True
        return True


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _sanitize_event_id(raw: str) -> str:
    """FEATURE-MAP-070: strip illegal chars; matches map_editor.sanitize_map_id rules."""
    s = "".join(c if c.isalnum() or c in "._-" else "_" for c in raw.strip())[:64]
    return s.strip("._-") or ""


def _new_node(op: str) -> dict:
    args = ess.default_args_for_op(op)
    args.pop("skip", None)
    if ess.is_block_open(op):
        return {"op": op, "args": args, "children": []}
    return {"op": op, "args": args}


def _flatten(tree: list[dict]) -> list[dict]:
    rows: list[dict] = []

    def rec(nodes: list[dict], prefix: tuple[int, ...], depth: int) -> None:
        for i, node in enumerate(nodes):
            p = prefix + (i,)
            op = str(node.get("op", ""))
            is_open = ess.is_block_open(op) and isinstance(node.get("children"), list)
            rows.append({"path": p, "node": node, "depth": depth,
                         "kind": "open" if is_open else "leaf"})
            if is_open:
                rec(node["children"], p, depth + 1)
                end_op = ess.op_block_end(op) or "end"
                rows.append({"path": p, "node": {"op": end_op}, "depth": depth, "kind": "end"})

    rec(tree, (), 0)
    return rows


def _btn(ed, rect: pygame.Rect, label: str, bg, fg) -> None:
    pygame.draw.rect(ed.screen, bg, rect)
    pygame.draw.rect(ed.screen, _C_BORDER_DIM, rect, 1)
    ts = ed.font_small.render(label, True, fg)
    ed.screen.blit(ts, (rect.x + max(4, (rect.w - ts.get_width()) // 2), rect.y + (rect.h - ts.get_height()) // 2))


def _subpanel(ed, rect: pygame.Rect, title: str) -> None:
    pygame.draw.rect(ed.screen, _C_SUBPANEL, rect)
    pygame.draw.rect(ed.screen, _C_BORDER_DIM, rect, 1)
    header = pygame.Rect(rect.x, rect.y, rect.w, 20)
    pygame.draw.rect(ed.screen, (32, 40, 34), header)
    ed.screen.blit(ed.font_small.render(title, True, _C_HEAD), (rect.x + 6, rect.y + 2))


def _textbox(ed, rect: pygame.Rect, text: str, focused: bool, placeholder: str) -> None:
    pygame.draw.rect(ed.screen, (24, 30, 26), rect)
    pygame.draw.rect(ed.screen, _C_BORDER if focused else _C_BORDER_DIM, rect, 1)
    if text:
        ed.screen.blit(
            ed.font_small.render(text + ("|" if focused else ""), True, _C_TEXT),
            (mtext.field_text_x(rect, 5), mtext.field_text_y(ed.font_small, rect)),
        )
    else:
        ed.screen.blit(
            ed.font_small.render(("|" if focused else "") + placeholder, True, _C_TEXT_DIM),
            (mtext.field_text_x(rect, 5), mtext.field_text_y(ed.font_small, rect)),
        )

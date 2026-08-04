"""FEATURE-MAP-079: per-action edit modal with labeled, type-aware argument fields.

Opened from the Event Engine block context menu ("Edit in modal") for the selected step. Each
argument gets its own labeled field whose input type follows the argument's value:
  - bool  -> toggle button
  - int   -> numeric text field
  - str   -> text field
  - goto.label -> dropdown of labels declared in the current flow (FEATURE-MAP-075)
  - call_subflow.vars -> editable named-argument key=value rows (FEATURE-MAP-074)

A variable picker lets the author select an existing registry flag/variable or create a new one
for name-style arguments. Inline editing in the block panel remains available; this is an
alternative, roomier editor.
"""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

import pygame

import event_script_schema as ess
import flag_registry_modal as freg
import modal_text as mtext

if TYPE_CHECKING:
    from event_engine_modal import EventEngineModal
    from map_editor import MapEditor

_C_PANEL = (20, 24, 20)
_C_SUBPANEL = (26, 31, 28)
_C_BORDER = (80, 180, 120)
_C_BORDER_DIM = (60, 78, 66)
_C_TEXT = (210, 224, 214)
_C_TEXT_DIM = (140, 158, 146)
_C_HEAD = (180, 255, 200)
_C_SEL = (54, 92, 70)

# Argument keys (per opcode) that name a flag/variable -> show the variable picker.
_NAME_KEYS = {"name"}


class EventActionModal:
    def __init__(self, editor: MapEditor) -> None:
        self.ed = editor
        self.open = False
        self.panel_rect = pygame.Rect(0, 0, 1, 1)
        self._panel_override: pygame.Rect | None = None
        self._drag_mode = "none"
        self._drag_ref = (0, 0)
        self._title_bar = pygame.Rect(0, 0, 1, 1)
        self._resize_corner_br = pygame.Rect(0, 0, 16, 16)
        self._resize_corner_bl = pygame.Rect(0, 0, 16, 16)
        self.close_btn = pygame.Rect(0, 0, 1, 1)
        self._save_btn = pygame.Rect(0, 0, 1, 1)
        self._cancel_btn = pygame.Rect(0, 0, 1, 1)

        self.engine: EventEngineModal | None = None
        self.flow: str = "main"
        self.path: tuple[int, ...] = ()
        self.op = ""
        self.args: dict[str, Any] = {}
        self.labels: list[str] = []

        self.focus_key: str | None = None
        self.edit_buf = ""
        self._field_rects: dict[str, pygame.Rect] = {}
        self._toggle_rects: dict[str, pygame.Rect] = {}
        self._pick_rects: dict[str, pygame.Rect] = {}
        self._vars_rows: list[tuple[str, pygame.Rect, pygame.Rect, pygame.Rect]] = []
        self._vars_add_btn = pygame.Rect(0, 0, 1, 1)
        # Dropdown overlay: {"key":..., "rect":..., "rows":[(value,rect)]}
        self.dropdown: dict | None = None
        # Pending vars edit (call_subflow): list of [key, value]
        self.vars_pairs: list[list[str]] = []
        self.vars_focus: tuple[int, str] | None = None  # (row index, "k"|"v")
        self.body_scroll = 0
        self._body_content_h = 0
        self._body_rect = pygame.Rect(0, 0, 1, 1)

    def open_for(self, engine: EventEngineModal, flow: str, path: tuple[int, ...]) -> None:
        node = engine.flows.get(flow)
        n = _node_at(node or [], path) if node is not None else None
        if n is None:
            self.ed.set_status("No action selected to edit.", kind="err")
            return
        self.engine = engine
        self.flow = flow
        self.path = path
        self.op = str(n.get("op", ""))
        self.args = copy.deepcopy(n.get("args") or {})
        self.args.pop("skip", None)
        self.labels = ess.labels_in_steps(ess.tree_to_steps(engine.flows.get(flow, [])))
        self.focus_key = None
        self.edit_buf = ""
        self.dropdown = None
        self.vars_pairs = []
        self.vars_focus = None
        if self.op == "call_subflow":
            v = self.args.get("vars")
            if isinstance(v, dict):
                self.vars_pairs = [[str(k), str(val)] for k, val in v.items()]
        self.open = True
        self._drag_mode = "none"
        self.body_scroll = 0

    def close(self, save: bool) -> None:
        if save:
            self._apply()
        self.open = False
        self.engine = None
        self.dropdown = None

    # ------------------------------------------------------------------
    def _merged_keys(self) -> list[str]:
        doc = ess.op_documentation(self.op)
        keys: list[str] = []
        for k in (doc.get("default_args") or {}):
            if k != "skip" and k not in keys:
                keys.append(k)
        for k in self.args:
            if k != "skip" and k not in keys:
                keys.append(k)
        if self.op == "call_subflow" and "vars" in keys:
            keys.remove("vars")  # vars are rendered as dedicated rows
        return keys

    def _kind_for(self, key: str) -> str:
        if self.op == "goto" and key == "label":
            return "label"
        if self.op == "start_trainer_battle" and key == "outcomeMode":
            return "outcome"
        if self.op == "start_trainer_battle" and key == "battleId":
            return "battle_pick"
        v = self.args.get(key, ess.op_documentation(self.op).get("default_args", {}).get(key))
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, int):
            return "int"
        return "str"

    # ------------------------------------------------------------------
    def draw(self) -> None:
        if not self.open:
            return
        ed = self.ed
        canvas = ed.screen.get_rect()
        dim = pygame.Surface((canvas.w, canvas.h), pygame.SRCALPHA)
        dim.fill((8, 12, 16, 220))
        ed.screen.blit(dim, canvas.topleft)
        if self._panel_override is not None:
            panel = self._panel_override.copy()
        else:
            pw = min(560, canvas.w - 40)
            ph = min(520, canvas.h - 60)
            panel = pygame.Rect(0, 0, pw, ph)
            panel.center = canvas.center
        panel.w = max(640, min(panel.w, canvas.w - 8))
        panel.h = max(480, min(panel.h, canvas.h - 8))
        panel.x = max(canvas.x + 4, min(panel.x, canvas.right - panel.w - 4))
        panel.y = max(canvas.y + 4, min(panel.y, canvas.bottom - panel.h - 4))
        self.panel_rect = panel

        head_h = 34
        pygame.draw.rect(ed.screen, _C_PANEL, panel)
        pygame.draw.rect(ed.screen, _C_BORDER, panel, 2)
        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 80, head_h)
        doc = ess.op_documentation(self.op)
        ed.screen.blit(ed.font.render(f"Edit · {doc.get('label', self.op)}", True, _C_HEAD),
                       (panel.x + 12, panel.y + 7))
        self.close_btn = pygame.Rect(panel.right - 28, panel.y + 5, 22, 24)
        _btn(ed, self.close_btn, "\u2715", (72, 48, 48), (245, 240, 240))
        pygame.draw.line(ed.screen, _C_BORDER_DIM, (panel.x, panel.y + head_h),
                         (panel.right, panel.y + head_h), 1)

        body = pygame.Rect(panel.x + 10, panel.y + head_h + 8, panel.w - 20, panel.h - head_h - 52)
        self._body_rect = body
        self._draw_fields(body, doc)

        # Footer buttons
        self._save_btn = pygame.Rect(panel.right - 96, panel.bottom - 34, 84, 24)
        _btn(ed, self._save_btn, "Save", (40, 70, 50), _C_HEAD)
        self._cancel_btn = pygame.Rect(panel.right - 188, panel.bottom - 34, 84, 24)
        _btn(ed, self._cancel_btn, "Cancel", (72, 48, 48), (245, 240, 240))

        self._resize_corner_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        self._resize_corner_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(ed.screen, (90, 160, 120), [
            (panel.right - 2, panel.bottom - 14), (panel.right - 2, panel.bottom - 2),
            (panel.right - 14, panel.bottom - 2)])
        pygame.draw.polygon(ed.screen, (90, 160, 120), [
            (panel.x + 2, panel.bottom - 14), (panel.x + 2, panel.bottom - 2),
            (panel.x + 14, panel.bottom - 2)])

        if self.dropdown:
            self._draw_dropdown()

    def _draw_fields(self, body: pygame.Rect, doc: dict) -> None:
        ed = self.ed
        self._field_rects = {}
        self._toggle_rects = {}
        self._pick_rects = {}
        self._vars_rows = []
        help_map = doc.get("args_help") or {}
        lh = ed.font_small.get_linesize()
        pick_w = 66
        wrap_w = max(40, mtext.form_field_w(body, pick_w))
        y = mtext.FORM_SECTION_TOP
        prev_clip = ed.screen.get_clip()
        ed.screen.set_clip(body)

        def _sy(logical_y: int) -> int:
            return body.y + logical_y - self.body_scroll

        field_h = mtext.form_field_h(ed.font_small)

        for key in self._merged_keys():
            sy = _sy(y)
            fr = pygame.Rect(mtext.form_field_x(body), sy, mtext.form_field_w(body, pick_w), field_h)
            ed.screen.blit(ed.font_small.render(key, True, _C_HEAD),
                           (mtext.form_label_x(body), mtext.form_label_y(ed.font_small, fr)))
            kind = self._kind_for(key)
            if kind == "bool":
                cur = bool(self.args.get(key))
                _btn(ed, fr, "true" if cur else "false", (50, 80, 58) if cur else (40, 48, 42), _C_TEXT)
                self._toggle_rects[key] = fr
            elif kind == "outcome":
                cur = str(self.args.get(key, "normal"))
                label = {"normal": "Normal", "scripted_win": "Scripted win", "scripted_loss": "Scripted loss"}.get(cur, cur)
                _btn(ed, fr, label, (60, 50, 80), _C_HEAD)
                self._toggle_rects[key] = fr
            else:
                editing = self.focus_key == key
                shown = self.edit_buf if editing else str(self.args.get(key, ""))
                _field(ed, fr, shown, editing)
                self._field_rects[key] = fr
                if kind == "label" or key in _NAME_KEYS or kind == "battle_pick":
                    pr = pygame.Rect(fr.right + 6, sy, 60, field_h)
                    _btn(ed, pr, "Pick \u25BE", (50, 70, 90), (200, 225, 245))
                    self._pick_rects[key] = pr
            h = str(help_map.get(key, ""))
            if h:
                help_lines = mtext.wrap_lines_to_width(ed.font_small, h, wrap_w)
                hy = mtext.form_help_y(fr)
                mtext.blit_wrapped_lines(ed.screen, ed.font_small, help_lines, mtext.form_field_x(body), hy, _C_TEXT_DIM)
                y += mtext.form_row_advance(fr, len(help_lines), ed.font_small, has_help=True)
            else:
                y += mtext.form_row_advance(fr, 0, ed.font_small, has_help=False)

        if self.op == "call_subflow":
            sy = _sy(y)
            ed.screen.blit(ed.font_small.render("vars (named args)", True, _C_HEAD), (mtext.form_label_x(body), sy))
            y += field_h + mtext.FORM_HELP_GAP
            for i, (k, v) in enumerate(self.vars_pairs):
                sy = _sy(y)
                kr = pygame.Rect(mtext.form_label_x(body), sy, 130, field_h)
                vr = pygame.Rect(kr.right + 6, sy, body.w - 130 - 6 - 30, field_h)
                dr = pygame.Rect(vr.right + 6, sy, 22, field_h)
                _field(ed, kr, (self.edit_buf if self.vars_focus == (i, "k") else k), self.vars_focus == (i, "k"))
                _field(ed, vr, (self.edit_buf if self.vars_focus == (i, "v") else v), self.vars_focus == (i, "v"))
                _btn(ed, dr, "\u2715", (80, 44, 44), _C_TEXT)
                self._vars_rows.append((f"{i}", kr, vr, dr))
                y += field_h + mtext.FORM_ROW_GAP
            sy = _sy(y)
            self._vars_add_btn = pygame.Rect(mtext.form_label_x(body), sy, 90, field_h)
            _btn(ed, self._vars_add_btn, "+ add var", (40, 70, 50), _C_HEAD)
            y += field_h + mtext.FORM_ROW_GAP

        self._body_content_h = y
        max_scroll = max(0, self._body_content_h - body.h)
        self.body_scroll = max(0, min(self.body_scroll, max_scroll))
        ed.screen.set_clip(prev_clip)

    def _draw_dropdown(self) -> None:
        ed = self.ed
        key = self.dropdown["key"]
        anchor = self._field_rects.get(key) or self._pick_rects.get(key)
        if anchor is None:
            self.dropdown = None
            return
        values = self.dropdown["values"]
        rh = ed.font_small.get_linesize() + 6
        h = min(rh * max(1, len(values)), 200)
        rect = pygame.Rect(anchor.x, anchor.bottom + 2, max(160, anchor.w), h)
        rect.bottom = min(rect.bottom, self.panel_rect.bottom - 4)
        self.dropdown["rect"] = rect
        pygame.draw.rect(ed.screen, (28, 34, 30), rect)
        pygame.draw.rect(ed.screen, _C_BORDER, rect, 1)
        prev = ed.screen.get_clip()
        ed.screen.set_clip(rect)
        rows = []
        y = rect.y
        for val in values:
            rr = pygame.Rect(rect.x, y, rect.w, rh)
            if rr.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(ed.screen, _C_SEL, rr)
            ed.screen.blit(
                ed.font_small.render(
                    mtext.truncate_to_width(ed.font_small, str(val), max(8, rr.w - 12)), True, _C_TEXT),
                (mtext.field_text_x(rr, 6), mtext.field_text_y(ed.font_small, rr)),
            )
            rows.append((val, rr))
            y += rh
        self.dropdown["rows"] = rows
        ed.screen.set_clip(prev)

    # ------------------------------------------------------------------
    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        if self.dropdown:
            for val, rr in self.dropdown.get("rows", []):
                if rr.collidepoint(mx, my) and button == 1:
                    self._apply_dropdown(val)
                    self.dropdown = None
                    return True
            if not self.dropdown["rect"].collidepoint(mx, my):
                self.dropdown = None
            return True
        if button == 1 and self.close_btn.collidepoint(mx, my):
            self.close(save=False)
            return True
        if button == 1 and self._cancel_btn.collidepoint(mx, my):
            self.close(save=False)
            return True
        if button == 1 and self._save_btn.collidepoint(mx, my):
            self._commit_text()
            self.close(save=True)
            return True
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
        # Toggles
        for key, fr in self._toggle_rects.items():
            if fr.collidepoint(mx, my) and button == 1:
                self._commit_text()
                if key == "outcomeMode":
                    modes = ["normal", "scripted_win", "scripted_loss"]
                    cur = str(self.args.get(key, "normal"))
                    try:
                        idx = modes.index(cur)
                    except ValueError:
                        idx = 0
                    self.args[key] = modes[(idx + 1) % len(modes)]
                else:
                    self.args[key] = not bool(self.args.get(key))
                return True
        # Pickers (label dropdown / variable picker)
        for key, pr in self._pick_rects.items():
            if pr.collidepoint(mx, my) and button == 1:
                self._commit_text()
                self._open_picker(key)
                return True
        # Text fields
        for key, fr in self._field_rects.items():
            if fr.collidepoint(mx, my) and button == 1:
                self._commit_text()
                self.focus_key = key
                self.edit_buf = str(self.args.get(key, ""))
                return True
        # call_subflow vars rows
        if self.op == "call_subflow":
            for tag, kr, vr, dr in self._vars_rows:
                i = int(tag)
                if dr.collidepoint(mx, my) and button == 1:
                    self._commit_text()
                    if 0 <= i < len(self.vars_pairs):
                        self.vars_pairs.pop(i)
                    return True
                if kr.collidepoint(mx, my) and button == 1:
                    self._commit_text()
                    self.vars_focus = (i, "k")
                    self.edit_buf = self.vars_pairs[i][0]
                    return True
                if vr.collidepoint(mx, my) and button == 1:
                    self._commit_text()
                    self.vars_focus = (i, "v")
                    self.edit_buf = self.vars_pairs[i][1]
                    return True
            if self._vars_add_btn.collidepoint(mx, my) and button == 1:
                self._commit_text()
                self.vars_pairs.append(["arg", ""])
                return True
        self._commit_text()
        return True

    def _open_picker(self, key: str) -> None:
        if self.op == "goto" and key == "label":
            self.dropdown = {"key": key, "values": list(self.labels) or ["(no labels)"]}
            return
        # FEATURE-MAP-081: call_subflow name -> list in-file flows + library subflows.
        if self.op == "call_subflow" and key == "name":
            names: list[str] = []
            if self.engine is not None:
                names = sorted(k for k in self.engine.flows if k != "main")
            lib = ess.list_library_subflow_names()
            values = names + lib or ["(no subflows)"]
            self.dropdown = {"key": key, "values": values}
            return
        if self.op == "start_trainer_battle" and key == "battleId":
            battles = ess.list_library_battle_names()
            self.dropdown = {"key": key, "values": ["(none)"] + battles if battles else ["(no battles)"]}
            return
        if self.op == "start_trainer_battle" and key == "music":
            stems = self.ed.list_audio_track_stems()
            self.dropdown = {"key": key, "values": ["(none)"] + stems}
            return
        if self.op == "start_trainer_battle" and key == "background":
            self.dropdown = {"key": key, "values": ess.list_battle_background_ids()}
            return
        # Variable picker: registry flags + variables + create new
        reg = freg.load_registry()
        names_fv = freg.flag_names(reg) + freg.variable_names(reg)
        values = names_fv + ["+ New flag…", "+ New variable…"]
        self.dropdown = {"key": key, "values": values}

    def _apply_dropdown(self, val: str) -> None:
        key = self.dropdown["key"]
        if val in ("(no labels)", "(no subflows)", "(no battles)"):
            return
        if val == "(none)":
            self.args[key] = ""
            return
        if val == "+ New flag…":
            base = str(self.args.get(key, "")) or "new_flag"
            freg.ensure_flag(base)
            self.args[key] = freg._sanitize_name(base)
            return
        if val == "+ New variable…":
            base = str(self.args.get(key, "")) or "new_var"
            freg.ensure_variable(base)
            self.args[key] = freg._sanitize_name(base)
            return
        self.args[key] = val

    def handle_mouse_up(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        self._drag_mode = "none"
        return True

    def handle_mouse_motion(self, mx: int, my: int) -> bool:
        if not self.open:
            return False
        if self._drag_mode == "resize_br":
            ax, ay = self._drag_ref
            self._panel_override = pygame.Rect(ax, ay, max(640, mx - ax), max(480, my - ay))
            return True
        if self._drag_mode == "resize_bl":
            right, ay = self._drag_ref
            new_x = min(mx, right - 640)
            self._panel_override = pygame.Rect(new_x, ay, right - new_x, max(480, my - ay))
            return True
        if self._drag_mode == "move":
            ox, oy = self._drag_ref
            self._panel_override = pygame.Rect(mx - ox, my - oy, self.panel_rect.w, self.panel_rect.h)
            return True
        return False

    def handle_wheel(self, mx: int, my: int, y: int) -> bool:
        if not self.open:
            return False
        if self.dropdown:
            return True
        body = self._body_rect
        if body.collidepoint(mx, my) and self._body_content_h > body.h:
            step = 2 * self.ed.font_small.get_linesize()
            max_scroll = max(0, self._body_content_h - body.h)
            self.body_scroll = max(0, min(self.body_scroll - y * step, max_scroll))
        return True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        if self.dropdown and event.key == pygame.K_ESCAPE:
            self.dropdown = None
            return True
        if self.focus_key is not None or self.vars_focus is not None:
            if event.key == pygame.K_ESCAPE:
                self.focus_key = None
                self.vars_focus = None
                self.edit_buf = ""
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit_text()
            elif event.key == pygame.K_BACKSPACE:
                self.edit_buf = self.edit_buf[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.edit_buf += event.unicode
            return True
        if event.key == pygame.K_ESCAPE:
            self.close(save=False)
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.close(save=True)
            return True
        return True

    def _commit_text(self) -> None:
        if self.focus_key is not None:
            key = self.focus_key
            kind = self._kind_for(key)
            if kind == "int":
                try:
                    self.args[key] = int(self.edit_buf)
                except ValueError:
                    self.args[key] = 0
            else:
                self.args[key] = self.edit_buf
            self.focus_key = None
            self.edit_buf = ""
        elif self.vars_focus is not None:
            i, which = self.vars_focus
            if 0 <= i < len(self.vars_pairs):
                self.vars_pairs[i][0 if which == "k" else 1] = self.edit_buf
            self.vars_focus = None
            self.edit_buf = ""

    def _apply(self) -> None:
        if self.engine is None:
            return
        self.engine._undo_checkpoint()
        tree = self.engine.flows.get(self.flow)
        if tree is None:
            return
        node = _node_at(tree, self.path)
        if node is None:
            return
        new_args = copy.deepcopy(self.args)
        if self.op == "call_subflow":
            vars_obj: dict[str, Any] = {}
            for k, v in self.vars_pairs:
                k = k.strip()
                if not k:
                    continue
                vars_obj[k] = _coerce_value(v)
            new_args["vars"] = vars_obj
        node["args"] = new_args
        self.engine.script_dirty = True
        self.ed.set_status("Action updated.", kind="ok")


def _coerce_value(s: str) -> Any:
    t = s.strip()
    low = t.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(t)
    except ValueError:
        return s


def _node_at(tree: list[dict], path: tuple[int, ...]) -> dict | None:
    nodes = tree
    node: dict | None = None
    for idx in path:
        if not (0 <= idx < len(nodes)):
            return None
        node = nodes[idx]
        nodes = node.get("children") or []
    return node


def _btn(ed, rect, label, bg, fg) -> None:
    pygame.draw.rect(ed.screen, bg, rect)
    pygame.draw.rect(ed.screen, _C_BORDER_DIM, rect, 1)
    ts = ed.font_small.render(label, True, fg)
    ed.screen.blit(ts, (rect.x + max(4, (rect.w - ts.get_width()) // 2),
                        rect.y + (rect.h - ts.get_height()) // 2))


def _field(ed, rect, text, focused) -> None:
    pygame.draw.rect(ed.screen, (44, 52, 46) if focused else (24, 30, 26), rect)
    pygame.draw.rect(ed.screen, _C_BORDER if focused else _C_BORDER_DIM, rect, 1)
    shown = str(text) + ("|" if focused else "")
    clipped = mtext.truncate_to_width(ed.font_small, shown, max(8, rect.w - 8))
    ed.screen.blit(
        ed.font_small.render(clipped, True, _C_TEXT),
        (mtext.field_text_x(rect), mtext.field_text_y(ed.font_small, rect)),
    )

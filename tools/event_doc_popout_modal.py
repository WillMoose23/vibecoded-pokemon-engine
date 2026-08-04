"""FEATURE-MAP-080: full-window pop-out documentation modal.

A UI-Standard (full-window canvas, draggable title bar, BR/BL resize) reader for the event-script
opcode documentation. Left column lists opcodes (searchable); the right column shows the selected
opcode's structured docs, word-wrapped and scrollable so text is never clipped.

Opened from the Event Engine documentation panel "Pop" button. Closing returns to the engine modal.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

import event_script_opcode_docs as odoc
import event_script_schema as ess
import modal_text as mtext

if TYPE_CHECKING:
    from map_editor import MapEditor

_C_PANEL = (20, 24, 20)
_C_BODY = (16, 20, 16)
_C_SUBPANEL = (26, 31, 28)
_C_BORDER = (80, 180, 120)
_C_BORDER_DIM = (60, 78, 66)
_C_TEXT = (210, 224, 214)
_C_TEXT_DIM = (140, 158, 146)
_C_HEAD = (180, 255, 200)
_C_SEL = (54, 92, 70)
_C_SEL_BORDER = (120, 210, 160)


class EventDocPopoutModal:
    def __init__(self, editor: MapEditor) -> None:
        self.ed = editor
        self.open = False
        self.panel_rect = pygame.Rect(0, 0, 1, 1)
        self._panel_override: pygame.Rect | None = None
        self._drag_mode = "none"
        self._drag_ref = (0, 0)
        self._resize_br = pygame.Rect(0, 0, 16, 16)
        self._resize_bl = pygame.Rect(0, 0, 16, 16)
        self._title_bar = pygame.Rect(0, 0, 1, 1)
        self.close_btn = pygame.Rect(0, 0, 1, 1)

        self.sel_op: str | None = None
        self.search = ""
        self.focus_search = False
        self.list_scroll = 0
        self.doc_scroll = 0
        self._list_panel = pygame.Rect(0, 0, 1, 1)
        self._doc_panel = pygame.Rect(0, 0, 1, 1)
        self._search_rect = pygame.Rect(0, 0, 1, 1)
        self._op_rows: list[tuple[str, pygame.Rect]] = []
        self._doc_total_h = 0
        self._doc_body = pygame.Rect(0, 0, 1, 1)

    def open_for(self, op: str | None) -> None:
        self.open = True
        self.sel_op = op
        self.search = ""
        self.focus_search = False
        self.list_scroll = 0
        self.doc_scroll = 0
        self._drag_mode = "none"

    def close(self) -> None:
        self.open = False
        self._drag_mode = "none"

    # ------------------------------------------------------------------
    def _ops_filtered(self) -> list[str]:
        q = self.search.strip().lower()
        ops = list(ess.cpp_script_ops_ordered())
        if not q:
            return ops
        out = []
        for op in ops:
            lbl = ess.op_documentation(op).get("label", op).lower()
            if q in op.lower() or q in lbl:
                out.append(op)
        return out

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
            pw = min(max(900, canvas.w - 64), canvas.w - 24)
            ph = min(max(560, canvas.h - 80), canvas.h - 24)
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
        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 90, head_h)
        ed.screen.blit(ed.font.render("Documentation", True, _C_HEAD), (panel.x + 12, panel.y + 7))
        self.close_btn = pygame.Rect(panel.right - 72, panel.y + 5, 60, 24)
        _btn(ed, self.close_btn, "Close", (72, 48, 48), (245, 240, 240))
        pygame.draw.line(ed.screen, _C_BORDER_DIM, (panel.x, panel.y + head_h),
                         (panel.right, panel.y + head_h), 1)

        body = pygame.Rect(panel.x + 6, panel.y + head_h + 4, panel.w - 12, panel.h - head_h - 14)
        pygame.draw.rect(ed.screen, _C_BODY, body)
        list_w = max(200, min(int(body.w * 0.32), 320))
        self._list_panel = pygame.Rect(body.x, body.y, list_w, body.h)
        self._doc_panel = pygame.Rect(body.x + list_w + 6, body.y, body.w - list_w - 6, body.h)
        self._draw_list()
        self._draw_doc()

        self._resize_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(ed.screen, (90, 160, 120), [
            (panel.right - 2, panel.bottom - 14), (panel.right - 2, panel.bottom - 2),
            (panel.right - 14, panel.bottom - 2)])
        self._resize_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(ed.screen, (90, 160, 120), [
            (panel.x + 2, panel.bottom - 14), (panel.x + 2, panel.bottom - 2),
            (panel.x + 14, panel.bottom - 2)])

    def _draw_list(self) -> None:
        ed = self.ed
        r = self._list_panel
        _subpanel(ed, r, "Opcodes")
        inner = pygame.Rect(r.x + 6, r.y + 24, r.w - 12, r.h - 30)
        self._search_rect = pygame.Rect(inner.x, inner.y, inner.w, 22)
        _textbox(ed, self._search_rect, self.search, self.focus_search, "search opcodes")
        list_rect = pygame.Rect(inner.x, inner.y + 26, inner.w, inner.h - 26)
        ops = self._ops_filtered()
        rh = ed.font_small.get_linesize() + 4
        self.list_scroll = max(0, min(self.list_scroll, max(0, len(ops) * rh - list_rect.h)))
        prev = ed.screen.get_clip()
        ed.screen.set_clip(list_rect)
        y = list_rect.y - self.list_scroll
        self._op_rows = []
        for op in ops:
            row = pygame.Rect(list_rect.x, y, list_rect.w, rh)
            if row.bottom > list_rect.y and row.top < list_rect.bottom:
                sel = op == self.sel_op
                if sel:
                    pygame.draw.rect(ed.screen, _C_SEL, row)
                lbl = ess.op_documentation(op).get("label", op)
                ed.screen.blit(ed.font_small.render(lbl[:34], True, _C_HEAD if sel else _C_TEXT),
                               (row.x + 4, row.y + 2))
            self._op_rows.append((op, row))
            y += rh
        ed.screen.set_clip(prev)

    def _draw_doc(self) -> None:
        ed = self.ed
        r = self._doc_panel
        op = self.sel_op
        title = f"Docs · {op}" if op else "Documentation"
        _subpanel(ed, r, title)
        body = pygame.Rect(r.x + 8, r.y + 26, r.w - 16, r.h - 32)
        self._doc_body = body
        if op is None:
            ed.screen.blit(ed.font_small.render("Select an opcode on the left.", True, _C_TEXT_DIM),
                           (body.x + 2, body.y + 2))
            return
        doc = ess.op_documentation(op)
        mf = lambda s: ed.font_small.size(s)[0]
        lines = odoc.build_structured_doc_lines(op, doc, body.w - 8, mf)
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

    # ------------------------------------------------------------------
    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        if button == 1 and self.close_btn.collidepoint(mx, my):
            self.close()
            return True
        if button == 1 and self._resize_br.collidepoint(mx, my):
            self._drag_mode = "resize_br"
            self._drag_ref = (self.panel_rect.x, self.panel_rect.y)
            return True
        if button == 1 and self._resize_bl.collidepoint(mx, my):
            self._drag_mode = "resize_bl"
            self._drag_ref = (self.panel_rect.right, self.panel_rect.y)
            return True
        if button == 1 and self._title_bar.collidepoint(mx, my):
            self._drag_mode = "move"
            self._drag_ref = (mx - self.panel_rect.x, my - self.panel_rect.y)
            return True
        if button == 1 and self._search_rect.collidepoint(mx, my):
            self.focus_search = True
            return True
        for op, row in self._op_rows:
            if row.collidepoint(mx, my) and button == 1:
                self.sel_op = op
                self.doc_scroll = 0
                self.focus_search = False
                return True
        self.focus_search = False
        return True

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
            new_x = min(mx, right - 680)
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
        step = 3 * (self.ed.font_small.get_linesize() + 4)
        if self._list_panel.collidepoint(mx, my):
            self.list_scroll = max(0, self.list_scroll - y * step)
        elif self._doc_panel.collidepoint(mx, my):
            self.doc_scroll = max(0, self.doc_scroll - y * step)
        return True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        if self.focus_search:
            if event.key == pygame.K_ESCAPE:
                self.focus_search = False
            elif event.key == pygame.K_BACKSPACE:
                self.search = self.search[:-1]
                self.list_scroll = 0
            elif event.unicode and event.unicode.isprintable():
                self.search += event.unicode
                self.list_scroll = 0
            return True
        if event.key == pygame.K_ESCAPE:
            self.close()
            return True
        return True


def _btn(ed, rect: pygame.Rect, label: str, bg, fg) -> None:
    pygame.draw.rect(ed.screen, bg, rect)
    pygame.draw.rect(ed.screen, _C_BORDER_DIM, rect, 1)
    ts = ed.font_small.render(label, True, fg)
    ed.screen.blit(ts, (rect.x + max(4, (rect.w - ts.get_width()) // 2),
                        rect.y + (rect.h - ts.get_height()) // 2))


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

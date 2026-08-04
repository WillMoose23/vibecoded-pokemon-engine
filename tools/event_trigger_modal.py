"""FEATURE-MAP-078: event trigger editor modal.

Opened from the Event Engine event context menu ("Change Trigger"). Edits how an event fires and
its game-state side effects:
  - trigger.type: interact | step_on | on_map_enter | on_condition
  - trigger.condition: optional {flag, set} predicate gating eligibility
  - clearedFlag: auto-managed one-and-done flag (defaults to "<id>_cleared")
  - onComplete.setFlags / clearFlags: flags flipped when the script finishes

interact events are solid (the player bumps the sprite); step_on fires on stepping onto the anchor.
Writes back into the event dict and persists via the editor's map-event writer.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pygame

import modal_text as mtext

if TYPE_CHECKING:
    from event_engine_modal import EventEngineModal
    from map_editor import MapEditor

_C_PANEL = (20, 24, 20)
_C_BORDER = (80, 180, 120)
_C_BORDER_DIM = (60, 78, 66)
_C_TEXT = (210, 224, 214)
_C_TEXT_DIM = (140, 158, 146)
_C_HEAD = (180, 255, 200)
_C_SEL = (54, 92, 70)

_TRIGGERS = (
    ("interact", "Interact (talk) — solid NPC, press Q"),
    ("step_on", "Step on tile — fires when stepped on"),
    ("on_map_enter", "On map enter — fires when the map loads"),
    ("on_condition", "On condition — fires when a flag matches"),
)


class EventTriggerModal:
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
        self.ev_index: int | None = None
        self.ttype = "interact"
        self.cond_flag = ""
        self.cond_set = True
        self.cleared_flag = ""
        self.set_flags = ""
        self.clear_flags = ""

        self.focus: str | None = None  # cond_flag|cleared|setflags|clearflags
        self._type_rects: list[tuple[str, pygame.Rect]] = []
        self._cond_flag_rect = pygame.Rect(0, 0, 1, 1)
        self._cond_set_rect = pygame.Rect(0, 0, 1, 1)
        self._cleared_rect = pygame.Rect(0, 0, 1, 1)
        self._setflags_rect = pygame.Rect(0, 0, 1, 1)
        self._clearflags_rect = pygame.Rect(0, 0, 1, 1)

    def open_for(self, engine: EventEngineModal, ev_index: int) -> None:
        if not (0 <= ev_index < len(engine.events)):
            return
        ev = engine.events[ev_index]
        self.engine = engine
        self.ev_index = ev_index
        tr = ev.get("trigger") if isinstance(ev.get("trigger"), dict) else {}
        self.ttype = str(tr.get("type", "interact"))
        if self.ttype not in {t for t, _ in _TRIGGERS}:
            self.ttype = "interact"
        cond = tr.get("condition") if isinstance(tr.get("condition"), dict) else {}
        self.cond_flag = str(cond.get("flag", ""))
        self.cond_set = bool(cond.get("set", True))
        eid = str(ev.get("id", ""))
        self.cleared_flag = str(ev.get("clearedFlag", "") or (f"{eid}_cleared" if eid else ""))
        oc = ev.get("onComplete") if isinstance(ev.get("onComplete"), dict) else {}
        self.set_flags = ", ".join(str(x) for x in oc.get("setFlags", []) if isinstance(x, str))
        self.clear_flags = ", ".join(str(x) for x in oc.get("clearFlags", []) if isinstance(x, str))
        self.focus = None
        self.open = True
        self._drag_mode = "none"

    def close(self, save: bool) -> None:
        if save:
            self._apply()
        self.open = False
        self.engine = None

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
            pw = min(max(640, canvas.w - 80), canvas.w - 24)
            ph = min(max(480, canvas.h - 80), canvas.h - 24)
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
        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 40, head_h)
        eid = ""
        if self.engine and self.ev_index is not None and 0 <= self.ev_index < len(self.engine.events):
            eid = str(self.engine.events[self.ev_index].get("id", ""))
        ed.screen.blit(ed.font.render(f"Trigger · {eid}", True, _C_HEAD), (panel.x + 12, panel.y + 7))
        self.close_btn = pygame.Rect(panel.right - 28, panel.y + 5, 22, 24)
        _btn(ed, self.close_btn, "\u2715", (72, 48, 48), (245, 240, 240))
        pygame.draw.line(ed.screen, _C_BORDER_DIM, (panel.x, panel.y + head_h),
                         (panel.right, panel.y + head_h), 1)

        x = panel.x + 12
        y = panel.y + head_h + 10
        lh = ed.font_small.get_linesize()
        fh = mtext.form_field_h(ed.font_small)
        row_gap = mtext.FORM_ROW_GAP
        ed.screen.blit(ed.font_small.render("Trigger type", True, _C_HEAD), (x, y))
        y += lh + 4
        self._type_rects = []
        for key, label in _TRIGGERS:
            row = pygame.Rect(x, y, panel.w - 24, fh)
            box = pygame.Rect(row.x, row.y + (fh - 14) // 2, 14, 14)
            on = self.ttype == key
            pygame.draw.rect(ed.screen, (30, 36, 32), box)
            pygame.draw.rect(ed.screen, _C_BORDER if on else _C_BORDER_DIM, box, 1)
            if on:
                pygame.draw.circle(ed.screen, _C_HEAD, box.center, 4)
            ed.screen.blit(ed.font_small.render(label, True, _C_TEXT if on else _C_TEXT_DIM),
                           (box.right + 8, mtext.field_text_y(ed.font_small, row)))
            self._type_rects.append((key, row))
            y += fh + 4

        # Condition (relevant for on_condition; allowed as an extra gate otherwise)
        y += mtext.FORM_SECTION_TOP
        ed.screen.blit(ed.font_small.render("Condition flag (optional)", True, _C_HEAD), (x, y))
        y += lh + 2
        self._cond_flag_rect = pygame.Rect(x, y, panel.w - 24 - 90, fh)
        _field(ed, self._cond_flag_rect, self.cond_flag, self.focus == "cond_flag", "flag name")
        self._cond_set_rect = pygame.Rect(self._cond_flag_rect.right + 8, y, 82, fh)
        _btn(ed, self._cond_set_rect, "set" if self.cond_set else "clear",
             (50, 80, 58) if self.cond_set else (70, 56, 44), _C_TEXT)
        y += fh + row_gap

        ed.screen.blit(ed.font_small.render("Cleared flag", True, _C_HEAD), (x, y))
        y += lh + 2
        self._cleared_rect = pygame.Rect(x, y, panel.w - 24, fh)
        _field(ed, self._cleared_rect, self.cleared_flag, self.focus == "cleared", "<id>_cleared")
        y += fh + row_gap

        ed.screen.blit(ed.font_small.render("On complete — set flags (comma separated)", True, _C_HEAD), (x, y))
        y += lh + 2
        self._setflags_rect = pygame.Rect(x, y, panel.w - 24, fh)
        _field(ed, self._setflags_rect, self.set_flags, self.focus == "setflags", "flag_a, flag_b")
        y += fh + row_gap

        ed.screen.blit(ed.font_small.render("On complete — clear flags (comma separated)", True, _C_HEAD), (x, y))
        y += lh + 2
        self._clearflags_rect = pygame.Rect(x, y, panel.w - 24, fh)
        _field(ed, self._clearflags_rect, self.clear_flags, self.focus == "clearflags", "flag_c")

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

    # ------------------------------------------------------------------
    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        if button == 1 and (self.close_btn.collidepoint(mx, my) or self._cancel_btn.collidepoint(mx, my)):
            self.close(save=False)
            return True
        if button == 1 and self._save_btn.collidepoint(mx, my):
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
        for key, row in self._type_rects:
            if row.collidepoint(mx, my) and button == 1:
                self.ttype = key
                return True
        if button == 1 and self._cond_set_rect.collidepoint(mx, my):
            self.cond_set = not self.cond_set
            return True
        for name, rect in (("cond_flag", self._cond_flag_rect), ("cleared", self._cleared_rect),
                           ("setflags", self._setflags_rect), ("clearflags", self._clearflags_rect)):
            if rect.collidepoint(mx, my) and button == 1:
                self.focus = name
                return True
        self.focus = None
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
            new_x = min(mx, right - 640)
            self._panel_override = pygame.Rect(new_x, ay, right - new_x, max(480, my - ay))
            return True
        if self._drag_mode == "move":
            ox, oy = self._drag_ref
            self._panel_override = pygame.Rect(mx - ox, my - oy, self.panel_rect.w, self.panel_rect.h)
            return True
        return False

    def handle_wheel(self, mx: int, my: int, y: int) -> bool:
        return self.open

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        if self.focus is not None:
            cur = getattr(self, self.focus)
            if event.key == pygame.K_ESCAPE:
                self.focus = None
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.focus = None
                return True
            if event.key == pygame.K_BACKSPACE:
                setattr(self, self.focus, cur[:-1])
            elif event.unicode and event.unicode.isprintable():
                setattr(self, self.focus, cur + event.unicode)
            return True
        if event.key == pygame.K_ESCAPE:
            self.close(save=False)
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.close(save=True)
            return True
        return True

    # ------------------------------------------------------------------
    def _apply(self) -> None:
        if self.engine is None or self.ev_index is None:
            return
        if not (0 <= self.ev_index < len(self.engine.events)):
            return
        self.engine._undo_checkpoint()
        ev = self.engine.events[self.ev_index]
        trigger: dict[str, Any] = {"type": self.ttype}
        flag = self.cond_flag.strip()
        if flag:
            trigger["condition"] = {"flag": flag, "set": bool(self.cond_set)}
        ev["trigger"] = trigger
        cleared = self.cleared_flag.strip()
        if cleared:
            ev["clearedFlag"] = cleared
        else:
            ev.pop("clearedFlag", None)
        set_list = [s.strip() for s in self.set_flags.split(",") if s.strip()]
        clear_list = [s.strip() for s in self.clear_flags.split(",") if s.strip()]
        if set_list or clear_list:
            oc: dict[str, Any] = {}
            if set_list:
                oc["setFlags"] = set_list
            if clear_list:
                oc["clearFlags"] = clear_list
            ev["onComplete"] = oc
        else:
            ev.pop("onComplete", None)
        # interact events keep the sprite solid; the engine reads trigger.type at load.
        self.engine.events_dirty = True
        self.engine._persist_events()
        self.ed.set_status(f"Trigger set to '{self.ttype}'.", kind="ok")


def _btn(ed, rect, label, bg, fg) -> None:
    pygame.draw.rect(ed.screen, bg, rect)
    pygame.draw.rect(ed.screen, _C_BORDER_DIM, rect, 1)
    ts = ed.font_small.render(label, True, fg)
    ed.screen.blit(ts, (rect.x + max(4, (rect.w - ts.get_width()) // 2),
                        rect.y + (rect.h - ts.get_height()) // 2))


def _field(ed, rect, text, focused, placeholder="") -> None:
    pygame.draw.rect(ed.screen, (44, 52, 46) if focused else (24, 30, 26), rect)
    pygame.draw.rect(ed.screen, _C_BORDER if focused else _C_BORDER_DIM, rect, 1)
    if text:
        shown = str(text) + ("|" if focused else "")
        clipped = mtext.truncate_to_width(ed.font_small, shown, max(8, rect.w - 8))
        ed.screen.blit(
            ed.font_small.render(clipped, True, _C_TEXT),
            (mtext.field_text_x(rect), mtext.field_text_y(ed.font_small, rect)),
        )
    else:
        ph = ("|" if focused else "") + placeholder
        clipped = mtext.truncate_to_width(ed.font_small, ph, max(8, rect.w - 8))
        ed.screen.blit(
            ed.font_small.render(clipped, True, _C_TEXT_DIM),
            (mtext.field_text_x(rect), mtext.field_text_y(ed.font_small, rect)),
        )

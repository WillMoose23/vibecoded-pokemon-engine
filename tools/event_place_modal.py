"""FEATURE-MAP-068: "View in Map" sub-modal.

A UI-Standard modal (full-window canvas, drag title bar, BR/BL resize, persisted size)
that renders the selected map and lets the user click a tile to set the selected event's
2x2 anchor. Rendering uses the map editor's thumbnail surface so it works for ANY map without
disturbing the main editing session (independent map scope).

Wheel zooms, right-drag pans, left-click places. Save writes events back; Cancel discards.
"""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from map_editor import MapEditor

_FOOTPRINT = 2
_C_BORDER = (90, 150, 200)
_C_BORDER_DIM = (60, 78, 90)
_C_TEXT = (210, 222, 232)
_C_TEXT_DIM = (140, 156, 168)
_C_HEAD = (190, 220, 250)


class EventPlaceModal:
    def __init__(self, editor: MapEditor) -> None:
        self.ed = editor
        self.open = False
        self.panel_rect = pygame.Rect(0, 0, 1, 1)

        self._panel_override: pygame.Rect | None = None
        self._drag_mode = "none"
        self._drag_ref = (0, 0)
        self._resize_corner_br = pygame.Rect(0, 0, 16, 16)
        self._resize_corner_bl = pygame.Rect(0, 0, 16, 16)
        self._title_bar = pygame.Rect(0, 0, 1, 1)
        self.close_btn = pygame.Rect(0, 0, 1, 1)
        self.save_btn = pygame.Rect(0, 0, 1, 1)

        self.map_id: str | None = None
        self.events: list[dict] = []
        self.sel_index: int | None = None
        self.map_w = 0
        self.map_h = 0
        self._thumb: pygame.Surface | None = None
        self._map_area = pygame.Rect(0, 0, 1, 1)
        self.zoom = 1.0
        self.pan = [0, 0]
        self._pan_drag = False
        self._pan_ref = (0, 0)
        self._fit_done = False

    def open_for(self, map_id: str, event_index: int) -> None:
        self.open = True
        self._drag_mode = "none"
        self.map_id = map_id
        self.events = self.ed.read_map_events(map_id)
        self.sel_index = event_index if 0 <= event_index < len(self.events) else None
        self.map_w, self.map_h = self.ed.map_dims(map_id)
        self._thumb = self.ed._thumbnail_surface_for_map_stem(map_id)
        self.zoom = 1.0
        self.pan = [0, 0]
        self._fit_done = False
        self._pan_drag = False

    def close_modal(self, *, save: bool) -> None:
        if save and self.map_id is not None:
            self.ed.write_map_events(self.map_id, self.events)
            self.ed.event_engine_modal.refresh_after_submodal()
        self.open = False
        self._drag_mode = "none"
        self._pan_drag = False
        # Return to Event Engine
        if not self.ed.event_engine_modal.open:
            self.ed.event_engine_modal.open_modal()

    # ------------------------------------------------------------------

    def _fit(self, area: pygame.Rect) -> None:
        if self._thumb is None or self.map_w <= 0 or self.map_h <= 0:
            return
        tw, th = self._thumb.get_size()
        scale = min(area.w / tw, area.h / th) * 0.96
        self.zoom = max(0.05, scale)
        disp_w = tw * self.zoom
        disp_h = th * self.zoom
        self.pan = [int(area.x + (area.w - disp_w) / 2), int(area.y + (area.h - disp_h) / 2)]
        self._fit_done = True

    def _cell_px(self) -> float:
        if self._thumb is None or self.map_w <= 0:
            return 0.0
        return self._thumb.get_width() * self.zoom / self.map_w

    def draw(self) -> None:
        if not self.open:
            return
        ed = self.ed
        canvas = ed.screen.get_rect()
        dim = pygame.Surface((canvas.w, canvas.h), pygame.SRCALPHA)
        dim.fill((8, 12, 18, 220))
        ed.screen.blit(dim, canvas.topleft)

        if self._panel_override is not None:
            panel = self._panel_override.copy()
        else:
            pw = min(max(820, canvas.w - 80), canvas.w - 24)
            ph = min(max(560, canvas.h - 80), canvas.h - 24)
            panel = pygame.Rect(0, 0, pw, ph)
            panel.center = canvas.center
        panel.w = max(640, min(panel.w, canvas.w - 8))
        panel.h = max(480, min(panel.h, canvas.h - 8))
        panel.x = max(canvas.x + 4, min(panel.x, canvas.right - panel.w - 4))
        panel.y = max(canvas.y + 4, min(panel.y, canvas.bottom - panel.h - 4))
        self.panel_rect = panel

        head_h = 36
        foot_h = 24
        pygame.draw.rect(ed.screen, (18, 22, 28), panel)
        pygame.draw.rect(ed.screen, _C_BORDER, panel, 2)

        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 230, head_h)
        eid = ""
        if self.sel_index is not None and 0 <= self.sel_index < len(self.events):
            eid = str(self.events[self.sel_index].get("id", ""))
        ed.screen.blit(ed.font.render(f"View in Map — {self.map_id or ''}", True, _C_HEAD),
                       (panel.x + 12, panel.y + 8))
        for i in range(5):
            gx = panel.centerx - 20 + i * 10
            pygame.draw.circle(ed.screen, (70, 110, 150), (gx, panel.y + head_h // 2), 2)

        self.close_btn = pygame.Rect(panel.right - 84, panel.y + 6, 76, 26)
        _btn(ed, self.close_btn, "Cancel", (72, 48, 48), (245, 240, 240))
        self.save_btn = pygame.Rect(panel.right - 168, panel.y + 6, 78, 26)
        _btn(ed, self.save_btn, "Save", (48, 78, 56), (220, 245, 225))

        pygame.draw.line(ed.screen, _C_BORDER_DIM, (panel.x, panel.y + head_h),
                         (panel.right, panel.y + head_h), 1)

        area = pygame.Rect(panel.x + 6, panel.y + head_h + 4, panel.w - 12, panel.h - head_h - foot_h - 8)
        self._map_area = area
        pygame.draw.rect(ed.screen, (10, 12, 16), area)
        if not self._fit_done:
            self._fit(area)

        prev = ed.screen.get_clip()
        ed.screen.set_clip(area)
        if self._thumb is not None and self.zoom > 0:
            tw, th = self._thumb.get_size()
            disp = pygame.transform.smoothscale(self._thumb, (max(1, int(tw * self.zoom)),
                                                              max(1, int(th * self.zoom))))
            ed.screen.blit(disp, (self.pan[0], self.pan[1]))
            self._draw_event_hulls()
        else:
            ed.screen.blit(ed.font_small.render("No map preview available.", True, _C_TEXT_DIM),
                           (area.x + 8, area.y + 8))
        ed.screen.set_clip(prev)

        hint = "Click a tile to place the event · wheel to zoom · right-drag to pan"
        if eid:
            hint = f"Placing {eid} — " + hint
        ed.screen.blit(ed.font_small.render(hint, True, _C_TEXT_DIM),
                       (panel.x + 12, panel.bottom - foot_h + 4))

        self._resize_corner_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(ed.screen, (90, 140, 190), [
            (panel.right - 2, panel.bottom - 14), (panel.right - 2, panel.bottom - 2),
            (panel.right - 14, panel.bottom - 2)])
        self._resize_corner_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(ed.screen, (90, 140, 190), [
            (panel.x + 2, panel.bottom - 14), (panel.x + 2, panel.bottom - 2),
            (panel.x + 14, panel.bottom - 2)])

    def _draw_event_hulls(self) -> None:
        ed = self.ed
        cp = self._cell_px()
        if cp <= 0:
            return
        for i, ev in enumerate(self.events):
            a = ev.get("anchor") or {}
            try:
                ax = int(a.get("x", 0))
                ay = int(a.get("y", 0))
            except (TypeError, ValueError):
                continue
            rx = int(self.pan[0] + ax * cp)
            ry = int(self.pan[1] + ay * cp)
            rect = pygame.Rect(rx, ry, int(cp * _FOOTPRINT), int(cp * _FOOTPRINT))
            sel = i == self.sel_index
            col = (120, 230, 160) if sel else (230, 160, 80)
            box = pygame.Surface((max(1, rect.w), max(1, rect.h)), pygame.SRCALPHA)
            box.fill((col[0], col[1], col[2], 90 if not sel else 140))
            ed.screen.blit(box, rect.topleft)
            pygame.draw.rect(ed.screen, col, rect, 2)

    # ------------------------------------------------------------------

    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        if button == 1 and self.close_btn.collidepoint(mx, my):
            self.close_modal(save=False)
            return True
        if button == 1 and self.save_btn.collidepoint(mx, my):
            self.close_modal(save=True)
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
        if self._map_area.collidepoint(mx, my):
            if button == 3:
                self._pan_drag = True
                self._pan_ref = (mx - self.pan[0], my - self.pan[1])
                return True
            if button == 1:
                self._place_at(mx, my)
                return True
        return True

    def _place_at(self, mx: int, my: int) -> None:
        if self.sel_index is None or self.map_w <= 0:
            return
        cp = self._cell_px()
        if cp <= 0:
            return
        cx = int((mx - self.pan[0]) // cp)
        cy = int((my - self.pan[1]) // cp)
        cx = max(0, min(cx, self.map_w - _FOOTPRINT))
        cy = max(0, min(cy, self.map_h - _FOOTPRINT))
        ev = self.events[self.sel_index]
        ev["anchor"] = {"x": cx, "y": cy}

    def handle_mouse_up(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        self._drag_mode = "none"
        self._pan_drag = False
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
            new_x = min(mx, right - 560)
            self._panel_override = pygame.Rect(new_x, ay, right - new_x, max(480, my - ay))
            return True
        if self._drag_mode == "move":
            ox, oy = self._drag_ref
            self._panel_override = pygame.Rect(mx - ox, my - oy, self.panel_rect.w, self.panel_rect.h)
            return True
        if self._pan_drag:
            self.pan = [mx - self._pan_ref[0], my - self._pan_ref[1]]
            return True
        return True

    def handle_wheel(self, mx: int, my: int, y: int) -> bool:
        if not self.open:
            return False
        if not self._map_area.collidepoint(mx, my):
            return True
        old = self.zoom
        factor = 1.1 if y > 0 else (1 / 1.1)
        self.zoom = max(0.05, min(8.0, self.zoom * factor))
        # keep cursor anchored
        if old > 0:
            rel_x = (mx - self.pan[0]) / old
            rel_y = (my - self.pan[1]) / old
            self.pan = [int(mx - rel_x * self.zoom), int(my - rel_y * self.zoom)]
        return True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        if event.key == pygame.K_ESCAPE:
            self.close_modal(save=False)
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.close_modal(save=True)
            return True
        return True


def _btn(ed, rect: pygame.Rect, label: str, bg, fg) -> None:
    pygame.draw.rect(ed.screen, bg, rect)
    pygame.draw.rect(ed.screen, _C_BORDER_DIM, rect, 1)
    ts = ed.font_small.render(label, True, fg)
    ed.screen.blit(ts, (rect.x + (rect.w - ts.get_width()) // 2, rect.y + (rect.h - ts.get_height()) // 2))

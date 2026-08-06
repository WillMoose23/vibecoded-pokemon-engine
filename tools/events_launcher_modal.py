"""FEATURE-MAP-064/087/088/100: Events Launcher Modal.

Presents editor apps in a 2×2 grid plus NPC Sprites and Help rows:
  Event Engine | Wild Encounters
  Audio Engine | Battle Editor
  NPC Sprites (full width)
  Help (full width)

UI-Standard: min 640×480, BR+BL resize grips, title-bar drag-to-move.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from map_editor import MapEditor

_LAUNCHER_MIN_W = 640
_LAUNCHER_MIN_H = 480


class EventsLauncherModal:
    def __init__(self, editor: MapEditor) -> None:
        self.ed = editor
        self.open = False
        self.panel_rect = pygame.Rect(0, 0, 1, 1)
        self._panel_override: pygame.Rect | None = None
        self._drag_mode: str = "none"
        self._drag_ref: tuple[int, int, int, int] = (0, 0, 0, 0)
        self._resize_corner_br: pygame.Rect = pygame.Rect(0, 0, 16, 16)
        self._resize_corner_bl: pygame.Rect = pygame.Rect(0, 0, 16, 16)
        self._title_bar: pygame.Rect = pygame.Rect(0, 0, 1, 1)
        self.close_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)
        self._engine_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)
        self._wild_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)
        self._audio_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)
        self._battle_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)
        self._npc_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)
        self._help_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)

    def _clamp_panel(self, panel: pygame.Rect, canvas: pygame.Rect) -> pygame.Rect:
        panel.w = max(_LAUNCHER_MIN_W, min(panel.w, canvas.w - 8))
        panel.h = max(_LAUNCHER_MIN_H, min(panel.h, canvas.h - 8))
        panel.x = max(canvas.x + 4, min(panel.x, canvas.right - panel.w - 4))
        panel.y = max(canvas.y + 4, min(panel.y, canvas.bottom - panel.h - 4))
        return panel

    def open_modal(self) -> None:
        self.open = True
        self._drag_mode = "none"

    def close_modal(self) -> None:
        self.open = False
        self._drag_mode = "none"

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
            pw = min(_LAUNCHER_MIN_W, max(_LAUNCHER_MIN_W, canvas.w - 24))
            ph = min(_LAUNCHER_MIN_H, max(_LAUNCHER_MIN_H, canvas.h - 24))
            panel = pygame.Rect(0, 0, pw, ph)
            panel.center = canvas.center
        panel = self._clamp_panel(panel, canvas)
        self.panel_rect = panel
        head_h = 36
        foot_h = 16
        pygame.draw.rect(ed.screen, (20, 28, 24), panel)
        pygame.draw.rect(ed.screen, (90, 200, 140), panel, 2)
        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 80, head_h)
        ed.screen.blit(ed.font.render("Events", True, (200, 255, 220)), (panel.x + 12, panel.y + 8))
        self.close_btn = pygame.Rect(panel.right - 72, panel.y + 6, 60, 26)
        pygame.draw.rect(ed.screen, (72, 48, 48), self.close_btn)
        ed.screen.blit(
            ed.font_small.render("Close", True, (245, 240, 240)),
            (self.close_btn.x + 10, self.close_btn.y + 6),
        )
        body = pygame.Rect(panel.x + 24, panel.y + head_h + 16, panel.w - 48, panel.h - head_h - foot_h - 16)
        gap = 10
        btn_h = max(40, (body.h - 3 * gap) // 4)
        col_w = (body.w - gap) // 2
        specs = [
            ("_engine_btn", "Event Engine", (50, 100, 80), body.x, body.y),
            ("_wild_btn", "Wild Encounters", (40, 90, 130), body.x + col_w + gap, body.y),
            ("_audio_btn", "Audio Engine", (70, 90, 60), body.x, body.y + btn_h + gap),
            ("_battle_btn", "Battle Editor", (90, 60, 100), body.x + col_w + gap, body.y + btn_h + gap),
            ("_npc_btn", "NPC Sprites", (55, 95, 105), body.x, body.y + 2 * (btn_h + gap)),
            ("_help_btn", "Help", (80, 70, 40), body.x, body.y + 3 * (btn_h + gap)),
        ]
        for attr, label, color, bx, by in specs:
            bw = body.w if attr in ("_help_btn", "_npc_btn") else col_w
            btn = pygame.Rect(bx, by, bw, btn_h)
            setattr(self, attr, btn)
            pygame.draw.rect(ed.screen, color, btn)
            pygame.draw.rect(ed.screen, (100, 160, 130), btn, 1)
            surf = ed.font.render(label, True, (230, 248, 235))
            ed.screen.blit(
                surf,
                (btn.x + (btn.w - surf.get_width()) // 2, btn.y + (btn.h - surf.get_height()) // 2),
            )
        self._resize_corner_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        self._resize_corner_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
        br_col = (100, 180, 130)
        bl_col = (90, 160, 120)
        pygame.draw.polygon(
            ed.screen,
            br_col,
            [
                (panel.right, panel.bottom),
                (panel.right - 14, panel.bottom),
                (panel.right, panel.bottom - 14),
            ],
        )
        pygame.draw.polygon(
            ed.screen,
            bl_col,
            [
                (panel.x, panel.bottom),
                (panel.x + 14, panel.bottom),
                (panel.x, panel.bottom - 14),
            ],
        )

    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        if self._resize_corner_br.collidepoint(mx, my) and button == 1:
            self._drag_mode = "resize_br"
            ax, ay = self.panel_rect.x, self.panel_rect.y
            self._drag_ref = (ax, ay, self.panel_rect.w, self.panel_rect.h)
            return True
        if self._resize_corner_bl.collidepoint(mx, my) and button == 1:
            self._drag_mode = "resize_bl"
            ax, ay = self.panel_rect.x, self.panel_rect.y
            self._drag_ref = (ax, ay, self.panel_rect.w, self.panel_rect.h)
            return True
        if self.close_btn.collidepoint(mx, my) and button == 1:
            self.close_modal()
            return True
        if self._title_bar.collidepoint(mx, my) and button == 1:
            self._drag_mode = "move"
            self._drag_ref = (mx - self.panel_rect.x, my - self.panel_rect.y, 0, 0)
            return True
        if button == 1:
            if self._engine_btn.collidepoint(mx, my):
                self.close_modal()
                self.ed.event_engine_modal.open_modal()
                return True
            if self._wild_btn.collidepoint(mx, my):
                self.close_modal()
                self.ed.wild_encounter_modal.open_modal()
                return True
            if self._audio_btn.collidepoint(mx, my):
                self.close_modal()
                self.ed.audio_engine_modal.open_modal()
                return True
            if self._battle_btn.collidepoint(mx, my):
                self.close_modal()
                self.ed.battle_editor_modal.open_modal()
                return True
            if self._npc_btn.collidepoint(mx, my):
                self.close_modal()
                self.ed.npc_sprite_editor_modal.open_modal()
                return True
            if self._help_btn.collidepoint(mx, my):
                self.ed._open_help_overlay(tab="home", back_to="launcher")
                return True
        if button == 3 and self._wild_btn.collidepoint(mx, my):
            self.close_modal()
            self.ed._open_wild_canvas_mode()
            return True
        if not self.panel_rect.collidepoint(mx, my) and button == 1:
            self.close_modal()
            return True
        return True

    def handle_mouse_up(self, mx: int, my: int, button: int) -> bool:
        if self.open:
            self._drag_mode = "none"
            return True
        return False

    def handle_mouse_motion(self, mx: int, my: int) -> bool:
        if not self.open:
            return False
        canvas = self.ed.screen.get_rect()
        if self._drag_mode == "resize_br":
            ax, ay, _w, _h = self._drag_ref
            self._panel_override = self._clamp_panel(
                pygame.Rect(ax, ay, max(_LAUNCHER_MIN_W, mx - ax), max(_LAUNCHER_MIN_H, my - ay)),
                canvas,
            )
            return True
        if self._drag_mode == "resize_bl":
            ax, ay, _w, _h = self._drag_ref
            right = ax + self.panel_rect.w
            new_x = min(mx, right - _LAUNCHER_MIN_W)
            self._panel_override = self._clamp_panel(
                pygame.Rect(new_x, ay, right - new_x, max(_LAUNCHER_MIN_H, my - ay)),
                canvas,
            )
            return True
        if self._drag_mode == "move":
            ox, oy, _, _ = self._drag_ref
            self._panel_override = self._clamp_panel(
                pygame.Rect(mx - ox, my - oy, self.panel_rect.w, self.panel_rect.h),
                canvas,
            )
            return True
        return True

    def handle_wheel(self, mx: int, my: int, y: int) -> bool:
        return bool(self.open)

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if self.open and event.key == pygame.K_ESCAPE:
            self.close_modal()
            return True
        return False

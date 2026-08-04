"""FEATURE-MAP-087: Audio Engine — route music assignment with preview.

Independent map scope (mirrors Event Engine / Wild editor). Lists tracks from
src/audio/*.ogg, previews via pygame.mixer, writes musicTrack to map JSON.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

import modal_text as mtext

if TYPE_CHECKING:
    from map_editor import MapEditor

_C_PANEL = (20, 28, 24)
_C_BORDER = (90, 200, 140)
_C_TEXT = (210, 224, 214)
_C_HEAD = (200, 255, 220)
_C_SEL = (54, 92, 70)


class AudioEngineModal:
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
        self._back_btn = pygame.Rect(0, 0, 1, 1)
        self._help_btn = pygame.Rect(0, 0, 1, 1)
        self._play_btn = pygame.Rect(0, 0, 1, 1)
        self._stop_btn = pygame.Rect(0, 0, 1, 1)
        self._save_btn = pygame.Rect(0, 0, 1, 1)
        self._clear_btn = pygame.Rect(0, 0, 1, 1)
        self.maps: list[str] = []
        self.map_search = ""
        self.map_scroll = 0
        self.sel_map_id: str | None = None
        self.tracks: list[str] = []
        self.track_scroll = 0
        self.sel_track: str | None = None
        self._map_search_rect = pygame.Rect(0, 0, 1, 1)
        self._map_rows: list[tuple[str, pygame.Rect]] = []
        self._track_rows: list[tuple[str, pygame.Rect]] = []
        self._mixer_ready = False
        self._preview_track: str | None = None

    def open_modal(self) -> None:
        self.open = True
        self._drag_mode = "none"
        self.maps = self.ed.list_all_map_ids()
        self.tracks = self.ed.list_audio_track_stems()
        cur = self.ed.map_id
        if self.sel_map_id is None or self.sel_map_id not in self.maps:
            self.sel_map_id = cur if cur in self.maps else (self.maps[0] if self.maps else None)
        if self.sel_map_id:
            assigned = self.ed.read_map_music_track(self.sel_map_id)
            self.sel_track = assigned if assigned in self.tracks else (self.tracks[0] if self.tracks else None)
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._mixer_ready = True
        except pygame.error:
            self._mixer_ready = False
            self.ed.set_status("pygame.mixer init failed — preview disabled.", kind="err")

    def close_modal(self) -> None:
        self._stop_preview()
        self.open = False
        self._drag_mode = "none"

    def _stop_preview(self) -> None:
        if self._mixer_ready:
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass
        self._preview_track = None

    def _play_preview(self) -> None:
        if not self._mixer_ready or not self.sel_track:
            return
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / "src" / "audio" / f"{self.sel_track}.ogg"
        if not path.is_file():
            self.ed.set_status(f"Missing audio file: {path.name}", kind="err")
            return
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play(-1)
            self._preview_track = self.sel_track
        except pygame.error as e:
            self.ed.set_status(f"Preview failed: {e}", kind="err")

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
            panel = pygame.Rect(0, 0, min(720, canvas.w - 24), min(520, canvas.h - 24))
            panel.center = canvas.center
        panel.w = max(640, min(panel.w, canvas.w - 8))
        panel.h = max(480, min(panel.h, canvas.h - 8))
        panel.x = max(canvas.x + 4, min(panel.x, canvas.right - panel.w - 4))
        panel.y = max(canvas.y + 4, min(panel.y, canvas.bottom - panel.h - 4))
        self.panel_rect = panel
        head_h = 36
        pygame.draw.rect(ed.screen, _C_PANEL, panel)
        pygame.draw.rect(ed.screen, _C_BORDER, panel, 2)
        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 220, head_h)
        ed.screen.blit(ed.font.render("Audio Engine", True, _C_HEAD), (panel.x + 12, panel.y + 8))
        self.close_btn = pygame.Rect(panel.right - 72, panel.y + 6, 60, 26)
        _btn(ed, self.close_btn, "Close", (72, 48, 48), (245, 240, 240))
        self._back_btn = pygame.Rect(panel.right - 144, panel.y + 6, 64, 26)
        _btn(ed, self._back_btn, "\u2190 Back", (50, 70, 90), (200, 225, 245))
        self._help_btn = pygame.Rect(panel.right - 216, panel.y + 6, 64, 26)
        _btn(ed, self._help_btn, "Help", (55, 65, 40), (200, 245, 180))
        body = pygame.Rect(panel.x + 12, panel.y + head_h + 8, panel.w - 24, panel.h - head_h - 52)
        map_col = pygame.Rect(body.x, body.y, body.w // 2 - 6, body.h)
        track_col = pygame.Rect(map_col.right + 12, body.y, body.w - map_col.w - 12, body.h)
        pygame.draw.rect(ed.screen, (16, 22, 20), map_col)
        pygame.draw.rect(ed.screen, (70, 120, 95), map_col, 1)
        ed.screen.blit(ed.font_small.render("Maps", True, _C_HEAD), (map_col.x + 6, map_col.y + 4))
        self._map_search_rect = pygame.Rect(map_col.x + 6, map_col.y + 24, map_col.w - 12, 22)
        _field(ed, self._map_search_rect, self.map_search, False)
        list_r = pygame.Rect(map_col.x + 6, map_col.y + 52, map_col.w - 12, map_col.h - 58)
        self._draw_map_list(list_r)
        pygame.draw.rect(ed.screen, (16, 22, 20), track_col)
        pygame.draw.rect(ed.screen, (70, 120, 95), track_col, 1)
        ed.screen.blit(ed.font_small.render("Tracks (src/audio)", True, _C_HEAD), (track_col.x + 6, track_col.y + 4))
        assigned = self.ed.read_map_music_track(self.sel_map_id or "") if self.sel_map_id else ""
        info = f"Assigned: {assigned or '(none)'}"
        ed.screen.blit(ed.font_small.render(info, True, _C_TEXT), (track_col.x + 6, track_col.y + 24))
        tr = pygame.Rect(track_col.x + 6, track_col.y + 48, track_col.w - 12, track_col.h - 100)
        self._draw_track_list(tr)
        self._play_btn = pygame.Rect(track_col.x + 6, track_col.bottom - 44, 64, 26)
        self._stop_btn = pygame.Rect(self._play_btn.right + 8, track_col.bottom - 44, 64, 26)
        self._save_btn = pygame.Rect(self._stop_btn.right + 8, track_col.bottom - 44, 90, 26)
        self._clear_btn = pygame.Rect(self._save_btn.right + 8, track_col.bottom - 44, 70, 26)
        _btn(ed, self._play_btn, "Play", (40, 70, 50), _C_HEAD)
        _btn(ed, self._stop_btn, "Stop", (55, 60, 55), _C_TEXT)
        _btn(ed, self._save_btn, "Assign", (50, 80, 60), _C_HEAD)
        _btn(ed, self._clear_btn, "Clear", (72, 48, 48), (245, 240, 240))
        self._resize_corner_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        self._resize_corner_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)

    def _draw_map_list(self, rect: pygame.Rect) -> None:
        ed = self.ed
        q = self.map_search.strip().lower()
        shown = [m for m in self.maps if not q or q in m.lower()]
        rh = ed.font_small.get_linesize() + 4
        self.map_scroll = max(0, min(self.map_scroll, max(0, len(shown) * rh - rect.h)))
        prev = ed.screen.get_clip()
        ed.screen.set_clip(rect)
        y = rect.y - self.map_scroll
        self._map_rows = []
        for m in shown:
            row = pygame.Rect(rect.x, y, rect.w, rh)
            if row.bottom > rect.y and row.top < rect.bottom:
                if m == self.sel_map_id:
                    pygame.draw.rect(ed.screen, _C_SEL, row)
                ed.screen.blit(ed.font_small.render(m[:48], True, _C_HEAD if m == self.sel_map_id else _C_TEXT),
                               (row.x + 4, row.y + 2))
            self._map_rows.append((m, row))
            y += rh
        ed.screen.set_clip(prev)

    def _draw_track_list(self, rect: pygame.Rect) -> None:
        ed = self.ed
        rh = ed.font_small.get_linesize() + 4
        self.track_scroll = max(0, min(self.track_scroll, max(0, len(self.tracks) * rh - rect.h)))
        prev = ed.screen.get_clip()
        ed.screen.set_clip(rect)
        y = rect.y - self.track_scroll
        self._track_rows = []
        for t in self.tracks:
            row = pygame.Rect(rect.x, y, rect.w, rh)
            if row.bottom > rect.y and row.top < rect.bottom:
                if t == self.sel_track:
                    pygame.draw.rect(ed.screen, _C_SEL, row)
                ed.screen.blit(ed.font_small.render(t, True, _C_HEAD if t == self.sel_track else _C_TEXT),
                               (row.x + 4, row.y + 2))
            self._track_rows.append((t, row))
            y += rh
        ed.screen.set_clip(prev)

    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        if button == 1 and self.close_btn.collidepoint(mx, my):
            self.close_modal()
            return True
        if button == 1 and self._back_btn.collidepoint(mx, my):
            self.close_modal()
            self.ed.events_launcher_modal.open_modal()
            return True
        if button == 1 and self._help_btn.collidepoint(mx, my):
            self.ed._open_help_overlay(tab="events", back_to="audio")
            return True
        if button == 1 and self._play_btn.collidepoint(mx, my):
            self._play_preview()
            return True
        if button == 1 and self._stop_btn.collidepoint(mx, my):
            self._stop_preview()
            return True
        if button == 1 and self._save_btn.collidepoint(mx, my) and self.sel_map_id and self.sel_track:
            if self.ed.write_map_music_track(self.sel_map_id, self.sel_track):
                self.ed.set_status(f"Assigned '{self.sel_track}' to {self.sel_map_id}.", kind="ok")
            return True
        if button == 1 and self._clear_btn.collidepoint(mx, my) and self.sel_map_id:
            if self.ed.write_map_music_track(self.sel_map_id, ""):
                self.sel_track = None
                self.ed.set_status(f"Cleared music on {self.sel_map_id}.", kind="ok")
            return True
        if button == 1:
            for m, rr in self._map_rows:
                if rr.collidepoint(mx, my):
                    self.sel_map_id = m
                    assigned = self.ed.read_map_music_track(m)
                    self.sel_track = assigned if assigned in self.tracks else self.sel_track
                    return True
            for t, rr in self._track_rows:
                if rr.collidepoint(mx, my):
                    self.sel_track = t
                    return True
        if self._resize_corner_br.collidepoint(mx, my) and button == 1:
            self._drag_mode = "resize_br"
            self._drag_ref = (self.panel_rect.x, self.panel_rect.y)
            return True
        if self._resize_corner_bl.collidepoint(mx, my) and button == 1:
            self._drag_mode = "resize_bl"
            self._drag_ref = (self.panel_rect.right, self.panel_rect.y)
            return True
        if self._title_bar.collidepoint(mx, my) and button == 1:
            self._drag_mode = "move"
            self._drag_ref = (mx - self.panel_rect.x, my - self.panel_rect.y)
            return True
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
        return True

    def handle_mouse_up(self, mx: int, my: int, button: int) -> bool:
        if self.open:
            self._drag_mode = "none"
            return True
        return False

    def handle_wheel(self, mx: int, my: int, y: int) -> bool:
        if not self.open:
            return False
        if y > 0:
            self.map_scroll = max(0, self.map_scroll - 20)
            self.track_scroll = max(0, self.track_scroll - 20)
        elif y < 0:
            self.map_scroll += 20
            self.track_scroll += 20
        return True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        if event.key == pygame.K_ESCAPE:
            self.close_modal()
            return True
        return False


def _btn(ed: MapEditor, rect: pygame.Rect, label: str, bg: tuple, fg: tuple) -> None:
    pygame.draw.rect(ed.screen, bg, rect)
    pygame.draw.rect(ed.screen, (90, 130, 100), rect, 1)
    surf = ed.font_small.render(label, True, fg)
    ed.screen.blit(surf, (rect.x + (rect.w - surf.get_width()) // 2, mtext.field_text_y(ed.font_small, rect)))


def _field(ed: MapEditor, rect: pygame.Rect, text: str, focus: bool) -> None:
    pygame.draw.rect(ed.screen, (28, 34, 30), rect)
    pygame.draw.rect(ed.screen, (120, 180, 130) if focus else (60, 78, 66), rect, 1)
    shown = text or "search maps"
    col = _C_TEXT if text else (120, 130, 125)
    ed.screen.blit(ed.font_small.render(mtext.truncate_to_width(ed.font_small, shown, rect.w - 8), True, col),
                   (mtext.field_text_x(rect), mtext.field_text_y(ed.font_small, rect)))

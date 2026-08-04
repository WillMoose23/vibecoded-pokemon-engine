"""FEATURE-MAP-068: "Assign Sprite" sub-modal.

UI-Standard modal that assigns a sprite to the selected event. Supports the three sprite
kinds (character / pokemon_icon / pokemon_icon_shiny), a searchable PNG list, and for
characters a 4x4 frame grid plus facing selection. Reuses the map editor's graphics
helpers (_graphics_dir_for_kind, _list_png_names_cached, _get_character_frame_surface).

Writes ev["sprite"] for the event and persists via write_map_events, then refreshes the
Event Engine. Works on any map (independent scope).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

import modal_text as mtext

if TYPE_CHECKING:
    from map_editor import MapEditor

_SHEET_COLS = 4
_SHEET_ROWS = 4
_C_BORDER = (170, 140, 200)
_C_BORDER_DIM = (84, 70, 96)
_C_TEXT = (224, 216, 232)
_C_TEXT_DIM = (160, 150, 170)
_C_HEAD = (228, 206, 250)
_C_SEL = (78, 60, 96)
_KINDS = (("character", "Character"), ("pokemon_icon", "Pokemon icon"),
          ("pokemon_icon_shiny", "Shiny icon"))
_FACINGS = (("down", "Down"), ("left", "Left"), ("right", "Right"), ("up", "Up"))


class EventSpriteModal:
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

        self.kind = "character"
        self.search = ""
        self.file_scroll = 0
        self.sel_file: str | None = None
        self.frame_idx = 0
        self.facing = "down"
        self.focus_search = False

        self._kind_rects: list[tuple[str, pygame.Rect]] = []
        self._file_rows: list[tuple[str, pygame.Rect]] = []
        self._facing_rects: list[tuple[str, pygame.Rect]] = []
        self._search_rect = pygame.Rect(0, 0, 1, 1)
        self._grid_rect = pygame.Rect(0, 0, 1, 1)
        self._file_area = pygame.Rect(0, 0, 1, 1)

    def open_for(self, map_id: str, event_index: int) -> None:
        self.open = True
        self._drag_mode = "none"
        self.map_id = map_id
        self.events = self.ed.read_map_events(map_id)
        self.sel_index = event_index if 0 <= event_index < len(self.events) else None
        self.search = ""
        self.file_scroll = 0
        self.focus_search = False
        # Seed from existing sprite
        sp = self.events[self.sel_index].get("sprite") if self.sel_index is not None else None
        if isinstance(sp, dict):
            self.kind = str(sp.get("kind", "character")) or "character"
            self.sel_file = str(sp.get("file", "")) or None
            try:
                self.frame_idx = int(sp.get("frame", 0))
            except (TypeError, ValueError):
                self.frame_idx = 0
            self.facing = str(sp.get("facing", "down")).strip() or "down"
        else:
            self.kind = "character"
            self.sel_file = None
            self.frame_idx = 0
            self.facing = "down"

    def close_modal(self, *, save: bool) -> None:
        if save and self.map_id is not None and self.sel_index is not None and self.sel_file:
            ev = self.events[self.sel_index]
            if self.kind == "character":
                ev["sprite"] = {
                    "kind": "character", "file": self.sel_file,
                    "frame": max(0, min(_SHEET_COLS * _SHEET_ROWS - 1, self.frame_idx)),
                    "facing": self.facing,
                    "sheetColumns": _SHEET_COLS, "sheetRows": _SHEET_ROWS,
                }
            else:
                ev["sprite"] = {"kind": self.kind, "file": self.sel_file}
            self.ed.write_map_events(self.map_id, self.events)
            self.ed.event_engine_modal.refresh_after_submodal()
        self.open = False
        self._drag_mode = "none"
        if not self.ed.event_engine_modal.open:
            self.ed.event_engine_modal.open_modal()

    def _files(self) -> list[str]:
        root = self.ed._graphics_dir_for_kind(self.kind)
        names = self.ed._list_png_names_cached(root, f"sprite_modal::{self.kind}")
        q = self.search.strip().lower()
        return [n for n in names if q in n.lower()] if q else names

    # ------------------------------------------------------------------

    def draw(self) -> None:
        if not self.open:
            return
        ed = self.ed
        canvas = ed.screen.get_rect()
        dim = pygame.Surface((canvas.w, canvas.h), pygame.SRCALPHA)
        dim.fill((10, 8, 14, 220))
        ed.screen.blit(dim, canvas.topleft)

        if self._panel_override is not None:
            panel = self._panel_override.copy()
        else:
            pw = min(max(760, canvas.w - 120), canvas.w - 24)
            ph = min(max(520, canvas.h - 120), canvas.h - 24)
            panel = pygame.Rect(0, 0, pw, ph)
            panel.center = canvas.center
        panel.w = max(640, min(panel.w, canvas.w - 8))
        panel.h = max(480, min(panel.h, canvas.h - 8))
        panel.x = max(canvas.x + 4, min(panel.x, canvas.right - panel.w - 4))
        panel.y = max(canvas.y + 4, min(panel.y, canvas.bottom - panel.h - 4))
        self.panel_rect = panel

        head_h = 36
        foot_h = 22
        pygame.draw.rect(ed.screen, (22, 18, 26), panel)
        pygame.draw.rect(ed.screen, _C_BORDER, panel, 2)

        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 180, head_h)
        ed.screen.blit(ed.font.render("Assign Sprite", True, _C_HEAD), (panel.x + 12, panel.y + 8))
        for i in range(5):
            gx = panel.centerx - 20 + i * 10
            pygame.draw.circle(ed.screen, (120, 100, 150), (gx, panel.y + head_h // 2), 2)

        self.close_btn = pygame.Rect(panel.right - 84, panel.y + 6, 76, 26)
        _btn(ed, self.close_btn, "Cancel", (70, 48, 60), (245, 235, 245))
        self.save_btn = pygame.Rect(panel.right - 168, panel.y + 6, 78, 26)
        _btn(ed, self.save_btn, "Save", (66, 56, 84), (235, 225, 245))

        pygame.draw.line(ed.screen, _C_BORDER_DIM, (panel.x, panel.y + head_h),
                         (panel.right, panel.y + head_h), 1)

        body = pygame.Rect(panel.x + 8, panel.y + head_h + 6, panel.w - 16, panel.h - head_h - foot_h - 10)

        # Left column: kind buttons + search + file list
        left_w = max(220, body.w // 2 - 8)
        left = pygame.Rect(body.x, body.y, left_w, body.h)
        self._kind_rects = []
        kx = left.x
        for kid, klabel in _KINDS:
            kw = (left.w - 8) // 3
            kr = pygame.Rect(kx, left.y, kw, 22)
            on = self.kind == kid
            pygame.draw.rect(ed.screen, _C_SEL if on else (36, 30, 42), kr)
            pygame.draw.rect(ed.screen, _C_BORDER if on else _C_BORDER_DIM, kr, 1)
            ed.screen.blit(ed.font_small.render(klabel, True, _C_HEAD if on else _C_TEXT_DIM),
                           (kr.x + 4, kr.y + 2))
            self._kind_rects.append((kid, kr))
            kx = kr.right + 4
        self._search_rect = pygame.Rect(left.x, left.y + 28, left.w, 22)
        _textbox(ed, self._search_rect, self.search, self.focus_search, "search files")
        self._file_area = pygame.Rect(left.x, left.y + 54, left.w, left.h - 54)
        pygame.draw.rect(ed.screen, (16, 13, 20), self._file_area)
        pygame.draw.rect(ed.screen, _C_BORDER_DIM, self._file_area, 1)
        prev = ed.screen.get_clip()
        ed.screen.set_clip(self._file_area)
        files = self._files()
        rh = ed.font_small.get_linesize() + 4
        self.file_scroll = max(0, min(self.file_scroll, max(0, len(files) * rh - self._file_area.h)))
        y = self._file_area.y - self.file_scroll
        self._file_rows = []
        for fn in files:
            row = pygame.Rect(self._file_area.x, y, self._file_area.w, rh)
            if row.bottom > self._file_area.y and row.top < self._file_area.bottom:
                sel = fn == self.sel_file
                if sel:
                    pygame.draw.rect(ed.screen, _C_SEL, row)
                ed.screen.blit(ed.font_small.render(fn[:38], True, _C_HEAD if sel else _C_TEXT),
                               (row.x + 4, row.y + 2))
            self._file_rows.append((fn, row))
            y += rh
        ed.screen.set_clip(prev)

        # Right column: preview / 4x4 grid / facing
        right = pygame.Rect(left.right + 12, body.y, body.right - left.right - 12, body.h)
        self._draw_right(right)

        hint = "Pick a kind + file; characters choose a frame and facing. Save to apply."
        ed.screen.blit(ed.font_small.render(hint, True, _C_TEXT_DIM),
                       (panel.x + 12, panel.bottom - foot_h + 2))

        self._resize_corner_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(ed.screen, (160, 130, 190), [
            (panel.right - 2, panel.bottom - 14), (panel.right - 2, panel.bottom - 2),
            (panel.right - 14, panel.bottom - 2)])
        self._resize_corner_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(ed.screen, (160, 130, 190), [
            (panel.x + 2, panel.bottom - 14), (panel.x + 2, panel.bottom - 2),
            (panel.x + 14, panel.bottom - 2)])

    def _draw_right(self, right: pygame.Rect) -> None:
        ed = self.ed
        self._facing_rects = []
        self._grid_rect = pygame.Rect(0, 0, 0, 0)
        if not self.sel_file:
            ed.screen.blit(ed.font_small.render("Select a file to preview.", True, _C_TEXT_DIM),
                           (right.x + 4, right.y + 4))
            return
        if self.kind == "character":
            # 4x4 frame grid
            side = min(right.w, right.h - 40)
            grid = pygame.Rect(right.x, right.y, side, side)
            self._grid_rect = grid
            pygame.draw.rect(ed.screen, (16, 13, 20), grid)
            cw = grid.w / _SHEET_COLS
            ch = grid.h / _SHEET_ROWS
            for f in range(_SHEET_COLS * _SHEET_ROWS):
                cx = grid.x + (f % _SHEET_COLS) * cw
                cy = grid.y + (f // _SHEET_COLS) * ch
                cell = pygame.Rect(int(cx), int(cy), int(cw), int(ch))
                surf = ed._get_character_frame_surface(self.sel_file, f, None)
                if surf is not None:
                    sc = pygame.transform.smoothscale(surf, (max(1, cell.w - 4), max(1, cell.h - 4)))
                    ed.screen.blit(sc, (cell.x + 2, cell.y + 2))
                col = (200, 170, 230) if f == self.frame_idx else _C_BORDER_DIM
                pygame.draw.rect(ed.screen, col, cell, 2 if f == self.frame_idx else 1)
            # Facing buttons
            fy = grid.bottom + 6
            fx = right.x
            for fid, flabel in _FACINGS:
                fr = pygame.Rect(fx, fy, 60, 22)
                on = self.facing == fid
                pygame.draw.rect(ed.screen, _C_SEL if on else (36, 30, 42), fr)
                pygame.draw.rect(ed.screen, _C_BORDER if on else _C_BORDER_DIM, fr, 1)
                ed.screen.blit(ed.font_small.render(flabel, True, _C_HEAD if on else _C_TEXT_DIM),
                               (fr.x + 6, fr.y + 2))
                self._facing_rects.append((fid, fr))
                fx = fr.right + 4
        else:
            root = ed._graphics_dir_for_kind(self.kind)
            p = root / self.sel_file
            if p.is_file():
                try:
                    img = pygame.image.load(str(p)).convert_alpha()
                    side = min(right.w, right.h)
                    iw, ih = img.get_size()
                    s = min(side / max(1, iw), side / max(1, ih))
                    sc = pygame.transform.smoothscale(img, (max(1, int(iw * s)), max(1, int(ih * s))))
                    ed.screen.blit(sc, (right.x, right.y))
                except pygame.error:
                    pass

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
        if button == 1:
            if self._search_rect.collidepoint(mx, my):
                self.focus_search = True
                return True
            self.focus_search = False
            for kid, kr in self._kind_rects:
                if kr.collidepoint(mx, my):
                    if kid != self.kind:
                        self.kind = kid
                        self.sel_file = None
                        self.file_scroll = 0
                        self.frame_idx = 0
                    return True
            for fn, row in self._file_rows:
                if row.collidepoint(mx, my):
                    self.sel_file = fn
                    return True
            for fid, fr in self._facing_rects:
                if fr.collidepoint(mx, my):
                    self.facing = fid
                    return True
            if self._grid_rect.w > 0 and self._grid_rect.collidepoint(mx, my):
                cw = self._grid_rect.w / _SHEET_COLS
                ch = self._grid_rect.h / _SHEET_ROWS
                c = int((mx - self._grid_rect.x) / cw)
                r = int((my - self._grid_rect.y) / ch)
                c = max(0, min(_SHEET_COLS - 1, c))
                r = max(0, min(_SHEET_ROWS - 1, r))
                self.frame_idx = r * _SHEET_COLS + c
                return True
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
            new_x = min(mx, right - 620)
            self._panel_override = pygame.Rect(new_x, ay, right - new_x, max(480, my - ay))
            return True
        if self._drag_mode == "move":
            ox, oy = self._drag_ref
            self._panel_override = pygame.Rect(mx - ox, my - oy, self.panel_rect.w, self.panel_rect.h)
            return True
        return True

    def handle_wheel(self, mx: int, my: int, y: int) -> bool:
        if not self.open:
            return False
        if self._file_area.collidepoint(mx, my):
            self.file_scroll = max(0, self.file_scroll - y * 3 * (self.ed.font_small.get_linesize() + 4))
        return True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        if self.focus_search:
            if event.key == pygame.K_ESCAPE:
                self.focus_search = False
            elif event.key == pygame.K_BACKSPACE:
                self.search = self.search[:-1]
                self.file_scroll = 0
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.focus_search = False
            elif event.unicode and event.unicode.isprintable():
                self.search += event.unicode
                self.file_scroll = 0
            return True
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


def _textbox(ed, rect: pygame.Rect, text: str, focused: bool, placeholder: str) -> None:
    pygame.draw.rect(ed.screen, (28, 22, 32), rect)
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

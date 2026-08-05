"""FEATURE-MAP-100: NPC character sprite sheet editor modal for the map editor."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pygame

import modal_text as mtext

from npc_sprite_sheet_helpers import (
    DEFAULT_SHEET_H,
    DEFAULT_SHEET_W,
    DIRECTIONS,
    GRID_COLS,
    cell_size_for_sheet,
    list_character_pngs,
    sanitize_character_filename,
    sheet_dimensions_warning,
    validate_sheet_dimensions,
)

if TYPE_CHECKING:
    from map_editor import MapEditor

_MODAL_MIN_W = 720
_MODAL_MIN_H = 520
_ZOOM_MIN = 4
_ZOOM_MAX = 32


class NpcSpriteEditorModal:
    def __init__(self, editor: MapEditor) -> None:
        self.ed = editor
        self.open = False
        self.panel_rect = pygame.Rect(0, 0, 1, 1)
        self.close_btn = pygame.Rect(0, 0, 1, 1)
        self._back_btn = pygame.Rect(0, 0, 1, 1)
        self._title_bar = pygame.Rect(0, 0, 1, 1)
        self._panel_override: pygame.Rect | None = None
        self._drag_mode: str = "none"
        self._drag_ref: tuple[int, int, int, int] = (0, 0, 0, 0)
        self._resize_corner_br = pygame.Rect(0, 0, 16, 16)
        self._resize_corner_bl = pygame.Rect(0, 0, 16, 16)

        self._sheet_w = DEFAULT_SHEET_W
        self._sheet_h = DEFAULT_SHEET_H
        self._sheet: pygame.Surface | None = None
        self._filename = "npc_sprite.png"
        self._dirty = False

        self._direction_idx = 0
        self._frame_idx = 0
        self._zoom = 12
        self._mirror_lock = True
        self._reference_name: str | None = None
        self._reference_surf: pygame.Surface | None = None
        self._paint_color: tuple[int, int, int, int] = (40, 40, 48, 255)
        self._paint_button: int | None = None
        self._paint_last: tuple[int, int] | None = None
        self._undo_stack: list[pygame.Surface] = []
        self._redo_stack: list[pygame.Surface] = []

        self._save_prompt_active = False
        self._save_prompt_buffer = ""
        self._dim_edit_field: str | None = None
        self._dim_edit_buf = ""

        self._dir_btns: list[pygame.Rect] = []
        self._frame_btns: list[pygame.Rect] = []
        self._palette_btns: list[pygame.Rect] = []
        self._canvas_rect = pygame.Rect(0, 0, 1, 1)
        self._ref_rect = pygame.Rect(0, 0, 1, 1)
        self._mirror_btn = pygame.Rect(0, 0, 1, 1)
        self._copy_idle_btn = pygame.Rect(0, 0, 1, 1)
        self._dup_prev_btn = pygame.Rect(0, 0, 1, 1)
        self._save_btn = pygame.Rect(0, 0, 1, 1)
        self._save_as_btn = pygame.Rect(0, 0, 1, 1)
        self._ref_prev_btn = pygame.Rect(0, 0, 1, 1)
        self._ref_next_btn = pygame.Rect(0, 0, 1, 1)
        self._zoom_in_btn = pygame.Rect(0, 0, 1, 1)
        self._zoom_out_btn = pygame.Rect(0, 0, 1, 1)
        self._new_btn = pygame.Rect(0, 0, 1, 1)
        self._load_btn = pygame.Rect(0, 0, 1, 1)
        self._dim_w_btn = pygame.Rect(0, 0, 1, 1)
        self._dim_h_btn = pygame.Rect(0, 0, 1, 1)

        self._palette_colors: list[tuple[int, int, int, int]] = [
            (0, 0, 0, 0),
            (24, 24, 28, 255),
            (48, 48, 56, 255),
            (96, 96, 112, 255),
            (200, 200, 210, 255),
            (255, 220, 180, 255),
            (220, 160, 120, 255),
            (180, 80, 60, 255),
            (60, 120, 200, 255),
            (80, 180, 100, 255),
            (220, 60, 60, 255),
            (255, 210, 80, 255),
        ]

    def _characters_dir(self) -> Path:
        return self.ed._graphics_dir_for_kind("character")

    def _blank_sheet_surface(self) -> pygame.Surface:
        surf = pygame.Surface((self._sheet_w, self._sheet_h), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        return surf

    def _ensure_sheet(self) -> pygame.Surface:
        if self._sheet is None:
            self._sheet = self._blank_sheet_surface()
        return self._sheet

    def _cell_size(self) -> tuple[int, int]:
        return cell_size_for_sheet(self._sheet_w, self._sheet_h)

    def _active_cell_origin(self) -> tuple[int, int]:
        cw, ch = self._cell_size()
        col = self._frame_idx
        row = self._direction_idx
        return col * cw, row * ch

    def _push_undo(self) -> None:
        sheet = self._ensure_sheet()
        self._undo_stack.append(sheet.copy())
        if len(self._undo_stack) > 32:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _sync_mirror_right_from_left(self) -> None:
        if not self._mirror_lock:
            return
        sheet = self._ensure_sheet()
        cw, ch = self._cell_size()
        left_row, right_row = 1, 2
        for col in range(GRID_COLS):
            lx, rx = col * cw, col * cw
            left = sheet.subsurface((lx, left_row * ch, cw, ch)).copy()
            mirrored = pygame.transform.flip(left, True, False)
            sheet.blit(mirrored, (rx, right_row * ch))

    def _copy_frame(self, src_frame: int, dst_frame: int, src_dir: int | None = None, dst_dir: int | None = None) -> None:
        sheet = self._ensure_sheet()
        cw, ch = self._cell_size()
        sdir = self._direction_idx if src_dir is None else src_dir
        ddir = self._direction_idx if dst_dir is None else dst_dir
        src = sheet.subsurface((src_frame * cw, sdir * ch, cw, ch)).copy()
        sheet.blit(src, (dst_frame * cw, ddir * ch))
        self._dirty = True

    def open_modal(self) -> None:
        self.open = True
        self._drag_mode = "none"
        self._save_prompt_active = False
        self._dim_edit_field = None
        if self._sheet is None:
            self._sheet = self._blank_sheet_surface()
        self._undo_stack.clear()
        self._redo_stack.clear()
        names = list_character_pngs(self._characters_dir())
        if names and self._reference_name is None:
            self._reference_name = names[0]
        self._load_reference_surface()

    def close_modal(self) -> None:
        self.open = False
        self._drag_mode = "none"
        self._paint_button = None
        self._save_prompt_active = False
        self._dim_edit_field = None

    def _load_reference_surface(self) -> None:
        self._reference_surf = None
        if not self._reference_name:
            return
        path = self._characters_dir() / self._reference_name
        if not path.is_file():
            return
        try:
            self._reference_surf = pygame.image.load(str(path)).convert_alpha()
        except pygame.error:
            self._reference_surf = None

    def _cycle_reference(self, delta: int) -> None:
        names = list_character_pngs(self._characters_dir())
        if not names:
            self._reference_name = None
            self._reference_surf = None
            return
        if self._reference_name not in names:
            self._reference_name = names[0]
        else:
            i = names.index(self._reference_name)
            self._reference_name = names[(i + delta) % len(names)]
        self._load_reference_surface()

    def _load_png_from_disk(self, filename: str) -> bool:
        path = self._characters_dir() / filename
        if not path.is_file():
            self.ed.set_status(f"Missing {filename}", kind="err")
            return False
        try:
            img = pygame.image.load(str(path)).convert_alpha()
        except pygame.error:
            self.ed.set_status(f"Could not load {filename}", kind="err")
            return False
        w, h = img.get_size()
        ok, msg = validate_sheet_dimensions(w, h)
        if not ok:
            self.ed.set_status(msg, kind="err")
            return False
        self._push_undo()
        self._sheet_w, self._sheet_h = w, h
        self._sheet = img
        self._filename = filename
        self._dirty = False
        warn = sheet_dimensions_warning(w, h)
        if warn:
            self.ed.set_status(warn, kind="info")
        else:
            self.ed.set_status(f"Loaded {filename}", kind="ok")
        return True

    def _apply_new_sheet_size(self) -> None:
        field = self._dim_edit_field
        if not field:
            return
        try:
            val = int(self._dim_edit_buf)
        except ValueError:
            self.ed.set_status("Invalid dimension.", kind="err")
            return
        w = val if field == "w" else self._sheet_w
        h = val if field == "h" else self._sheet_h
        ok, msg = validate_sheet_dimensions(w, h)
        if not ok:
            self.ed.set_status(msg, kind="err")
            return
        self._push_undo()
        old = self._ensure_sheet()
        self._sheet_w, self._sheet_h = w, h
        new = self._blank_sheet_surface()
        ow, oh = old.get_size()
        blit_w = min(w, ow)
        blit_h = min(h, oh)
        new.blit(old, (0, 0), (0, 0, blit_w, blit_h))
        self._sheet = new
        self._dirty = True
        self._dim_edit_field = None
        warn = sheet_dimensions_warning(w, h)
        if warn:
            self.ed.set_status(warn, kind="info")

    def _save_sheet(self, *, save_as: bool) -> None:
        if save_as:
            self._save_prompt_active = True
            self._save_prompt_buffer = self._filename
            return
        name = sanitize_character_filename(self._filename)
        path = self._characters_dir() / name
        path.parent.mkdir(parents=True, exist_ok=True)
        sheet = self._ensure_sheet()
        try:
            pygame.image.save(sheet, str(path))
        except pygame.error as exc:
            self.ed.set_status(f"Save failed: {exc}", kind="err")
            return
        self._filename = name
        self._dirty = False
        self.ed.set_status(f"Saved {name}", kind="ok")

    def _commit_save_as(self) -> None:
        name = sanitize_character_filename(self._save_prompt_buffer)
        if not name:
            self.ed.set_status("Filename empty.", kind="err")
            return
        path = self._characters_dir() / name
        path.parent.mkdir(parents=True, exist_ok=True)
        sheet = self._ensure_sheet()
        try:
            pygame.image.save(sheet, str(path))
        except pygame.error as exc:
            self.ed.set_status(f"Save failed: {exc}", kind="err")
            return
        self._filename = name
        self._dirty = False
        self._save_prompt_active = False
        self.ed.set_status(f"Saved {name}", kind="ok")

    def _clamp_panel(self, panel: pygame.Rect, canvas: pygame.Rect) -> pygame.Rect:
        panel.w = max(_MODAL_MIN_W, min(panel.w, canvas.w - 8))
        panel.h = max(_MODAL_MIN_H, min(panel.h, canvas.h - 8))
        panel.x = max(canvas.x + 4, min(panel.x, canvas.right - panel.w - 4))
        panel.y = max(canvas.y + 4, min(panel.y, canvas.bottom - panel.h - 4))
        return panel

    def _pixel_at_canvas(self, mx: int, my: int) -> tuple[int, int] | None:
        if not self._canvas_rect.collidepoint(mx, my):
            return None
        cw, ch = self._cell_size()
        lx = mx - self._canvas_rect.x
        ly = my - self._canvas_rect.y
        px = lx // self._zoom
        py = ly // self._zoom
        if px < 0 or py < 0 or px >= cw or py >= ch:
            return None
        return px, py

    def _paint_at(self, mx: int, my: int, button: int) -> None:
        pix = self._pixel_at_canvas(mx, my)
        if pix is None:
            return
        px, py = pix
        if self._paint_last == (px, py):
            return
        self._paint_last = (px, py)
        sheet = self._ensure_sheet()
        cw, ch = self._cell_size()
        ox, oy = self._active_cell_origin()
        color = (0, 0, 0, 0) if button == 3 else self._paint_color
        sheet.set_at((ox + px, oy + py), color)
        self._dirty = True
        if self._direction_idx == 1 and self._mirror_lock:
            self._sync_mirror_right_from_left()

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
            pw = min(max(_MODAL_MIN_W, canvas.w - 40), canvas.w - 16)
            ph = min(max(_MODAL_MIN_H, canvas.h - 40), canvas.h - 16)
            panel = pygame.Rect(0, 0, pw, ph)
            panel.center = canvas.center
        panel = self._clamp_panel(panel, canvas)
        self.panel_rect = panel
        head_h = 36
        pygame.draw.rect(ed.screen, (22, 30, 28), panel)
        pygame.draw.rect(ed.screen, (90, 200, 140), panel, 2)
        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 160, head_h)
        title = "NPC Sprite Editor"
        if self._dirty:
            title += " *"
        ed.screen.blit(ed.font.render(title, True, (200, 255, 220)), (panel.x + 12, panel.y + 8))
        self.close_btn = pygame.Rect(panel.right - 72, panel.y + 6, 60, 26)
        pygame.draw.rect(ed.screen, (72, 48, 48), self.close_btn)
        ed.screen.blit(ed.font_small.render("Close", True, (245, 240, 240)), (self.close_btn.x + 10, self.close_btn.y + 6))
        self._back_btn = pygame.Rect(panel.right - 140, panel.y + 6, 60, 26)
        pygame.draw.rect(ed.screen, (48, 72, 56), self._back_btn)
        ed.screen.blit(ed.font_small.render("Back", True, (230, 245, 235)), (self._back_btn.x + 12, self._back_btn.y + 6))

        body = pygame.Rect(panel.x + 12, panel.y + head_h + 8, panel.w - 24, panel.h - head_h - 24)
        y = body.y
        gap = 6
        btn_h = 26
        dir_w = max(60, (body.w - gap * 3) // 4)
        self._dir_btns = []
        for i, dname in enumerate(DIRECTIONS):
            r = pygame.Rect(body.x + i * (dir_w + gap), y, dir_w, btn_h)
            self._dir_btns.append(r)
            sel = i == self._direction_idx
            pygame.draw.rect(ed.screen, (60, 120, 90) if sel else (40, 56, 48), r)
            pygame.draw.rect(ed.screen, (120, 200, 140), r, 1)
            ed.screen.blit(
                ed.font_small.render(dname.capitalize(), True, (235, 248, 240)),
                (r.x + 8, r.y + 6),
            )
        y += btn_h + gap
        frame_w = max(48, (body.w - gap * 3) // 4)
        self._frame_btns = []
        for fi in range(4):
            r = pygame.Rect(body.x + fi * (frame_w + gap), y, frame_w, btn_h)
            self._frame_btns.append(r)
            sel = fi == self._frame_idx
            pygame.draw.rect(ed.screen, (70, 90, 120) if sel else (40, 48, 60), r)
            ed.screen.blit(ed.font_small.render(f"F{fi}", True, (230, 235, 250)), (r.x + 10, r.y + 6))
        y += btn_h + gap

        tool_y = y
        self._mirror_btn = pygame.Rect(body.x, tool_y, 150, btn_h)
        self._copy_idle_btn = pygame.Rect(body.x + 156, tool_y, 120, btn_h)
        self._dup_prev_btn = pygame.Rect(body.x + 282, tool_y, 130, btn_h)
        self._new_btn = pygame.Rect(body.x + 418, tool_y, 60, btn_h)
        self._load_btn = pygame.Rect(body.x + 484, tool_y, 60, btn_h)
        for rect, label, active in (
            (self._mirror_btn, "Mirror R←L" + (" ✓" if self._mirror_lock else ""), self._mirror_lock),
            (self._copy_idle_btn, "Idle→F3", False),
            (self._dup_prev_btn, "Dup prev", False),
            (self._new_btn, "New", False),
            (self._load_btn, "Load", False),
        ):
            pygame.draw.rect(ed.screen, (50, 80, 70) if active else (44, 52, 58), rect)
            ed.screen.blit(ed.font_small.render(label, True, (220, 235, 225)), (rect.x + 6, rect.y + 6))
        y += btn_h + gap

        self._save_btn = pygame.Rect(body.x, y, 70, btn_h)
        self._save_as_btn = pygame.Rect(body.x + 76, y, 80, btn_h)
        self._zoom_out_btn = pygame.Rect(body.x + 162, y, 28, btn_h)
        self._zoom_in_btn = pygame.Rect(body.x + 194, y, 28, btn_h)
        self._ref_prev_btn = pygame.Rect(body.right - 170, y, 28, btn_h)
        self._ref_next_btn = pygame.Rect(body.right - 136, y, 28, btn_h)
        for rect, label in (
            (self._save_btn, "Save"),
            (self._save_as_btn, "Save As"),
            (self._zoom_out_btn, "-"),
            (self._zoom_in_btn, "+"),
            (self._ref_prev_btn, "<"),
            (self._ref_next_btn, ">"),
        ):
            pygame.draw.rect(ed.screen, (48, 64, 56), rect)
            ed.screen.blit(ed.font_small.render(label, True, (230, 240, 235)), (rect.x + 8, rect.y + 6))
        ed.screen.blit(
            ed.font_small.render(f"Zoom {self._zoom}", True, (180, 190, 200)),
            (body.x + 228, y + 6),
        )
        ref_label = mtext.truncate_to_width(ed.font_small, self._reference_name or "(no ref)", 120)
        ed.screen.blit(ed.font_small.render(f"Ref: {ref_label}", True, (160, 175, 190)), (body.right - 100, y + 6))
        y += btn_h + gap

        cw, ch = self._cell_size()
        canvas_side = min(body.w // 2 - 8, body.bottom - y - 60, cw * self._zoom + 4)
        canvas_side = max(80, canvas_side)
        self._canvas_rect = pygame.Rect(body.x, y, canvas_side, canvas_side)
        self._ref_rect = pygame.Rect(body.x + canvas_side + 12, y, canvas_side, canvas_side)
        pygame.draw.rect(ed.screen, (30, 34, 40), self._canvas_rect)
        pygame.draw.rect(ed.screen, (80, 90, 110), self._canvas_rect, 1)
        sheet = self._ensure_sheet()
        ox, oy = self._active_cell_origin()
        cell = sheet.subsurface((ox, oy, cw, ch))
        scaled = pygame.transform.scale(cell, (self._canvas_rect.w, self._canvas_rect.h))
        ed.screen.blit(scaled, self._canvas_rect.topleft)
        # pixel grid
        step = self._canvas_rect.w / max(1, cw)
        for gx in range(cw + 1):
            lx = int(self._canvas_rect.x + gx * step)
            pygame.draw.line(ed.screen, (50, 55, 65), (lx, self._canvas_rect.y), (lx, self._canvas_rect.bottom))
        for gy in range(ch + 1):
            ly = int(self._canvas_rect.y + gy * step)
            pygame.draw.line(ed.screen, (50, 55, 65), (self._canvas_rect.x, ly), (self._canvas_rect.right, ly))

        pygame.draw.rect(ed.screen, (28, 32, 38), self._ref_rect)
        pygame.draw.rect(ed.screen, (70, 80, 95), self._ref_rect, 1)
        if self._reference_surf is not None:
            rw, rh = self._reference_surf.get_size()
            rcx, rcy = rw // GRID_COLS, rh // 4
            fcol = self._frame_idx
            frow = self._direction_idx
            ref_cell = self._reference_surf.subsurface((fcol * rcx, frow * rcy, rcx, rcy))
            ref_scaled = pygame.transform.scale(ref_cell, (self._ref_rect.w, self._ref_rect.h))
            ed.screen.blit(ref_scaled, self._ref_rect.topleft)
        else:
            ed.screen.blit(ed.font_small.render("Reference", True, (120, 130, 145)), (self._ref_rect.x + 8, self._ref_rect.y + 8))

        pal_y = self._canvas_rect.bottom + 8
        swatch = 22
        self._palette_btns = []
        for i, col in enumerate(self._palette_colors):
            r = pygame.Rect(body.x + i * (swatch + 4), pal_y, swatch, swatch)
            self._palette_btns.append(r)
            if col[3] == 0:
                pygame.draw.rect(ed.screen, (40, 40, 48), r)
                pygame.draw.line(ed.screen, (200, 80, 80), r.topleft, r.bottomright)
            else:
                pygame.draw.rect(ed.screen, col[:3], r)
            if col == self._paint_color:
                pygame.draw.rect(ed.screen, (255, 220, 100), r, 2)

        info_y = pal_y + swatch + 8
        self._dim_w_btn = pygame.Rect(body.x, info_y, 80, btn_h)
        self._dim_h_btn = pygame.Rect(body.x + 86, info_y, 80, btn_h)
        w_label = str(self._dim_edit_buf if self._dim_edit_field == "w" else self._sheet_w)
        h_label = str(self._dim_edit_buf if self._dim_edit_field == "h" else self._sheet_h)
        pygame.draw.rect(ed.screen, (40, 48, 56), self._dim_w_btn)
        pygame.draw.rect(ed.screen, (40, 48, 56), self._dim_h_btn)
        ed.screen.blit(ed.font_small.render(f"W:{w_label}", True, (210, 220, 230)), (self._dim_w_btn.x + 6, self._dim_w_btn.y + 6))
        ed.screen.blit(ed.font_small.render(f"H:{h_label}", True, (210, 220, 230)), (self._dim_h_btn.x + 6, self._dim_h_btn.y + 6))
        ed.screen.blit(
            ed.font_small.render(f"File: {self._filename}", True, (170, 180, 195)),
            (body.x + 180, info_y + 6),
        )

        self._resize_corner_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        self._resize_corner_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(
            ed.screen,
            (100, 180, 130),
            [(panel.right, panel.bottom), (panel.right - 14, panel.bottom), (panel.right, panel.bottom - 14)],
        )
        pygame.draw.polygon(
            ed.screen,
            (90, 160, 120),
            [(panel.x, panel.bottom), (panel.x + 14, panel.bottom), (panel.x, panel.bottom - 14)],
        )

        if self._save_prompt_active:
            ov = pygame.Rect(panel.x + 40, panel.centery - 30, panel.w - 80, 60)
            pygame.draw.rect(ed.screen, (20, 28, 24), ov)
            pygame.draw.rect(ed.screen, (120, 200, 140), ov, 2)
            ed.screen.blit(
                ed.font.render(f"Save as: [{self._save_prompt_buffer}]", True, (255, 255, 200)),
                (ov.x + 10, ov.y + 18),
            )

    def handle_key(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        if self._save_prompt_active:
            if event.key == pygame.K_ESCAPE:
                self._save_prompt_active = False
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit_save_as()
                return True
            if event.key == pygame.K_BACKSPACE:
                self._save_prompt_buffer = self._save_prompt_buffer[:-1]
                return True
            if event.unicode and event.unicode.isprintable():
                self._save_prompt_buffer += event.unicode
                return True
            return True
        if self._dim_edit_field:
            if event.key == pygame.K_ESCAPE:
                self._dim_edit_field = None
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._apply_new_sheet_size()
                return True
            if event.key == pygame.K_BACKSPACE:
                self._dim_edit_buf = self._dim_edit_buf[:-1]
                return True
            if event.unicode and event.unicode.isdigit():
                self._dim_edit_buf += event.unicode
                return True
            return True
        if event.key == pygame.K_z and (event.mod & pygame.KMOD_CTRL):
            if self._undo_stack:
                cur = self._ensure_sheet().copy()
                self._redo_stack.append(cur)
                self._sheet = self._undo_stack.pop()
                self._dirty = True
            return True
        if event.key == pygame.K_y and (event.mod & pygame.KMOD_CTRL):
            if self._redo_stack:
                cur = self._ensure_sheet().copy()
                self._undo_stack.append(cur)
                self._sheet = self._redo_stack.pop()
                self._dirty = True
            return True
        return False

    def handle_wheel(self, mx: int, my: int, dy: int) -> bool:
        if not self.open:
            return False
        if self._canvas_rect.collidepoint(mx, my):
            self._zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self._zoom + dy))
            return True
        return True

    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        if self._save_prompt_active:
            return True
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
        if self._back_btn.collidepoint(mx, my) and button == 1:
            self.close_modal()
            self.ed.events_launcher_modal.open_modal()
            return True
        if self._title_bar.collidepoint(mx, my) and button == 1:
            self._drag_mode = "move"
            self._drag_ref = (mx - self.panel_rect.x, my - self.panel_rect.y, 0, 0)
            return True
        if button == 1:
            for i, r in enumerate(self._dir_btns):
                if r.collidepoint(mx, my):
                    self._direction_idx = i
                    return True
            for i, r in enumerate(self._frame_btns):
                if r.collidepoint(mx, my):
                    self._frame_idx = i
                    return True
            if self._mirror_btn.collidepoint(mx, my):
                self._mirror_lock = not self._mirror_lock
                if self._mirror_lock:
                    self._sync_mirror_right_from_left()
                return True
            if self._copy_idle_btn.collidepoint(mx, my):
                self._push_undo()
                self._copy_frame(0, 3)
                if self._direction_idx == 1 and self._mirror_lock:
                    self._sync_mirror_right_from_left()
                return True
            if self._dup_prev_btn.collidepoint(mx, my) and self._frame_idx > 0:
                self._push_undo()
                self._copy_frame(self._frame_idx - 1, self._frame_idx)
                return True
            if self._new_btn.collidepoint(mx, my):
                self._push_undo()
                self._sheet = self._blank_sheet_surface()
                self._sheet_w, self._sheet_h = DEFAULT_SHEET_W, DEFAULT_SHEET_H
                self._dirty = True
                return True
            if self._load_btn.collidepoint(mx, my):
                names = list_character_pngs(self._characters_dir())
                if names:
                    self._load_png_from_disk(names[0] if self._filename not in names else self._filename)
                else:
                    self.ed.set_status("No PNG files in Characters folder.", kind="err")
                return True
            if self._save_btn.collidepoint(mx, my):
                self._save_sheet(save_as=False)
                return True
            if self._save_as_btn.collidepoint(mx, my):
                self._save_sheet(save_as=True)
                return True
            if self._zoom_in_btn.collidepoint(mx, my):
                self._zoom = min(_ZOOM_MAX, self._zoom + 2)
                return True
            if self._zoom_out_btn.collidepoint(mx, my):
                self._zoom = max(_ZOOM_MIN, self._zoom - 2)
                return True
            if self._ref_prev_btn.collidepoint(mx, my):
                self._cycle_reference(-1)
                return True
            if self._ref_next_btn.collidepoint(mx, my):
                self._cycle_reference(1)
                return True
            if self._dim_w_btn.collidepoint(mx, my):
                self._dim_edit_field = "w"
                self._dim_edit_buf = str(self._sheet_w)
                return True
            if self._dim_h_btn.collidepoint(mx, my):
                self._dim_edit_field = "h"
                self._dim_edit_buf = str(self._sheet_h)
                return True
            for i, r in enumerate(self._palette_btns):
                if r.collidepoint(mx, my):
                    self._paint_color = self._palette_colors[i]
                    return True
        if button in (1, 3) and self._canvas_rect.collidepoint(mx, my):
            self._push_undo()
            self._paint_button = button
            self._paint_last = None
            self._paint_at(mx, my, button)
            return True
        if not self.panel_rect.collidepoint(mx, my) and button == 1:
            self.close_modal()
            return True
        return True

    def handle_mouse_up(self, mx: int, my: int, button: int) -> bool:
        if self.open:
            if button == self._paint_button:
                self._paint_button = None
                self._paint_last = None
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
                pygame.Rect(ax, ay, max(_MODAL_MIN_W, mx - ax), max(_MODAL_MIN_H, my - ay)),
                canvas,
            )
            return True
        if self._drag_mode == "resize_bl":
            ax, ay, _w, _h = self._drag_ref
            right = ax + self.panel_rect.w
            new_x = min(mx, right - _MODAL_MIN_W)
            self._panel_override = self._clamp_panel(
                pygame.Rect(new_x, ay, right - new_x, max(_MODAL_MIN_H, my - ay)),
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
        if self._paint_button is not None:
            self._paint_at(mx, my, self._paint_button)
            return True
        return False

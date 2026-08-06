"""FEATURE-MAP-100 / FEATURE-MAP-102: NPC character sprite sheet editor modal."""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import pygame

import modal_text as mtext

from npc_sprite_sheet_helpers import (
    DEFAULT_SHEET_H,
    DEFAULT_SHEET_W,
    DIRECTIONS,
    GRID_COLS,
    MAX_NPC_LAYERS,
    cell_size_for_sheet,
    composite_rgba_layers,
    flood_fill_surface,
    list_character_pngs,
    normalize_pixel_rect,
    parse_palette_from_config,
    sanitize_character_filename,
    sheet_dimensions_warning,
    validate_sheet_dimensions,
)

if TYPE_CHECKING:
    from map_editor import MapEditor

_MODAL_MIN_W = 840
_MODAL_MIN_H = 520
_ZOOM_MIN = 4
_ZOOM_MAX = 32
_DEFAULT_ZOOM = 12
_RAIL_W = 130
_LAYER_ROW_H = 22
_DBL_CLICK_SEC = 0.4
# FEATURE-MAP-108: collapsible left-side sprite search panel (reference picker).
_SPRITE_PANEL_COLLAPSED_W = 22
_SPRITE_PANEL_EXPANDED_W = 150
_SPRITE_ROW_H = 20
# FEATURE-MAP-107: reference label moved under the picture, in yellow; space reserved
# in the footer calc so it never collides with the palette row.
_REF_LABEL_COLOR = (255, 225, 90)
_REF_LABEL_H = 18

ToolId = Literal["paint", "eraser", "fill", "select"]


class NpcSpriteEditorModal:
    def __init__(self, editor: MapEditor) -> None:
        self.ed = editor
        self.open = False
        self.panel_rect = pygame.Rect(0, 0, 1, 1)
        self.close_btn = pygame.Rect(0, 0, 1, 1)
        self._back_btn = pygame.Rect(0, 0, 1, 1)
        self._help_btn = pygame.Rect(0, 0, 1, 1)
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
        self._zoom = _DEFAULT_ZOOM
        self._mirror_lock = True
        self._reference_name: str | None = None
        self._reference_surf: pygame.Surface | None = None
        self._paint_color: tuple[int, int, int, int] = (40, 40, 48, 255)
        self._active_tool: ToolId = "paint"
        self._paint_button: int | None = None
        self._paint_last: tuple[int, int] | None = None
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []

        self._layer_surfaces: list[pygame.Surface] = []
        self._layer_names: list[str] = []
        self._layer_visible: list[bool] = []
        self._layer_locked: list[bool] = []
        self._active_layer_index = 0
        self._layer_scroll = 0

        self._save_prompt_active = False
        self._save_prompt_buffer = ""
        self._dim_edit_field: str | None = None
        self._dim_edit_buf = ""
        self._layer_rename_idx: int | None = None
        self._layer_rename_buf = ""
        self._last_layer_click: tuple[int, float] = (-1, 0.0)

        self._swatch_edit_open = False
        self._swatch_edit_working: list[tuple[int, int, int, int]] = []
        self._rgba_drag_channel: str | None = None

        # FEATURE-MAP-108: collapsible sprite search panel (reference picker).
        self._sprite_panel_collapsed = True
        self._sprite_search_query = ""
        self._sprite_search_focus = False
        self._sprite_list_scroll = 0
        self._sprite_row_hit: list[tuple[str, pygame.Rect]] = []

        # FEATURE-MAP-107: reference grid overlay toggle (default on).
        self._ref_grid_on = True

        # FEATURE-MAP-109: rectangular marquee selection + clipboard.
        self._selection_start: tuple[int, int] | None = None
        self._selection_rect: tuple[int, int, int, int] | None = None
        self._selecting = False
        self._clipboard: pygame.Surface | None = None
        self._last_canvas_pixel: tuple[int, int] | None = None

        self._dir_btns: list[pygame.Rect] = []
        self._frame_btns: list[pygame.Rect] = []
        self._palette_btns: list[pygame.Rect] = []
        self._canvas_rect = pygame.Rect(0, 0, 1, 1)
        self._cell_step_x: float = 1.0
        self._cell_step_y: float = 1.0
        self._ref_rect = pygame.Rect(0, 0, 1, 1)
        self._tool_rail_rect = pygame.Rect(0, 0, 1, 1)
        self._tool_paint_btn = pygame.Rect(0, 0, 1, 1)
        self._tool_eraser_btn = pygame.Rect(0, 0, 1, 1)
        self._tool_fill_btn = pygame.Rect(0, 0, 1, 1)
        self._tool_select_btn = pygame.Rect(0, 0, 1, 1)
        self._sprite_panel_rect = pygame.Rect(0, 0, 1, 1)
        self._sprite_panel_toggle_btn = pygame.Rect(0, 0, 1, 1)
        self._sprite_search_rect = pygame.Rect(0, 0, 1, 1)
        self._ref_grid_toggle_btn = pygame.Rect(0, 0, 1, 1)
        self._color_preview_rect = pygame.Rect(0, 0, 1, 1)
        self._rgba_slider_rects: dict[str, pygame.Rect] = {}
        self._layer_row_hit: list[tuple[int, pygame.Rect, pygame.Rect, pygame.Rect]] = []
        self._layer_add_btn = pygame.Rect(0, 0, 1, 1)
        self._layer_remove_btn = pygame.Rect(0, 0, 1, 1)
        self._edit_swatches_btn = pygame.Rect(0, 0, 1, 1)
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
        self._swatch_edit_done_btn = pygame.Rect(0, 0, 1, 1)
        self._swatch_edit_cancel_btn = pygame.Rect(0, 0, 1, 1)
        self._swatch_edit_add_btn = pygame.Rect(0, 0, 1, 1)
        self._swatch_edit_remove_rects: list[pygame.Rect] = []

        self._palette_colors: list[tuple[int, int, int, int]] = []

    def _characters_dir(self) -> Path:
        return self.ed._graphics_dir_for_kind("character")

    def _blank_sheet_surface(self) -> pygame.Surface:
        surf = pygame.Surface((self._sheet_w, self._sheet_h), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        return surf

    def _load_editor_config(self) -> None:
        sec = self.ed.config_get_section("npcSpriteEditor")
        self._palette_colors = parse_palette_from_config(sec.get("paletteColors"))
        zoom = sec.get("defaultZoom", _DEFAULT_ZOOM)
        if isinstance(zoom, int):
            self._zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, zoom))

    def _save_palette_config(self) -> None:
        sec = self.ed.config_get_section("npcSpriteEditor")
        sec["paletteColors"] = [list(c) for c in self._palette_colors]
        sec["defaultZoom"] = self._zoom
        self.ed.config_set_section("npcSpriteEditor", sec)

    def _init_layers_from_surface(self, surf: pygame.Surface | None = None) -> None:
        base = surf.copy() if surf is not None else self._blank_sheet_surface()
        self._layer_surfaces = [base]
        self._layer_names = ["Layer 1"]
        self._layer_visible = [True]
        self._layer_locked = [False]
        self._active_layer_index = 0
        self._layer_scroll = 0

    def _snapshot_layers(self) -> dict:
        return {
            "layers": [s.copy() for s in self._layer_surfaces],
            "names": list(self._layer_names),
            "visible": list(self._layer_visible),
            "locked": list(self._layer_locked),
            "active_layer": self._active_layer_index,
            "active_tool": self._active_tool,
            "paint_color": self._paint_color,
        }

    def _restore_layers(self, snap: dict) -> None:
        self._layer_surfaces = [s.copy() for s in snap["layers"]]
        self._layer_names = list(snap["names"])
        self._layer_visible = list(snap["visible"])
        self._layer_locked = list(snap["locked"])
        self._active_layer_index = int(snap["active_layer"])
        self._active_tool = snap["active_tool"]
        self._paint_color = tuple(snap["paint_color"])
        self._sheet = None

    def _ensure_sheet(self) -> pygame.Surface:
        self._sheet = composite_rgba_layers(self._layer_surfaces, self._layer_visible)
        return self._sheet

    def _active_layer_surface(self) -> pygame.Surface:
        return self._layer_surfaces[self._active_layer_index]

    def _cell_size(self) -> tuple[int, int]:
        return cell_size_for_sheet(self._sheet_w, self._sheet_h)

    def _active_cell_origin(self) -> tuple[int, int]:
        cw, ch = self._cell_size()
        return self._frame_idx * cw, self._direction_idx * ch

    def _push_undo(self) -> None:
        self._undo_stack.append(self._snapshot_layers())
        if len(self._undo_stack) > 32:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _layer_edit_blocked(self) -> bool:
        if self._layer_locked[self._active_layer_index]:
            self.ed.set_status("Layer locked.", kind="info")
            return True
        return False

    def _sync_mirror_right_from_left(self) -> None:
        if not self._mirror_lock:
            return
        sheet = self._active_layer_surface()
        cw, ch = self._cell_size()
        left_row, right_row = 1, 2
        for col in range(GRID_COLS):
            lx, rx = col * cw, col * cw
            left = sheet.subsurface((lx, left_row * ch, cw, ch)).copy()
            mirrored = pygame.transform.flip(left, True, False)
            sheet.blit(mirrored, (rx, right_row * ch))

    def _copy_frame(
        self,
        src_frame: int,
        dst_frame: int,
        src_dir: int | None = None,
        dst_dir: int | None = None,
    ) -> None:
        sheet = self._active_layer_surface()
        cw, ch = self._cell_size()
        sdir = self._direction_idx if src_dir is None else src_dir
        ddir = self._direction_idx if dst_dir is None else dst_dir
        src = sheet.subsurface((src_frame * cw, sdir * ch, cw, ch)).copy()
        sheet.blit(src, (dst_frame * cw, ddir * ch))
        self._dirty = True

    def _resize_all_layers(self, new_w: int, new_h: int, old: pygame.Surface) -> None:
        ow, oh = old.get_size()
        for i, layer in enumerate(self._layer_surfaces):
            new = pygame.Surface((new_w, new_h), pygame.SRCALPHA)
            new.fill((0, 0, 0, 0))
            blit_w, blit_h = min(new_w, ow), min(new_h, oh)
            new.blit(layer, (0, 0), (0, 0, blit_w, blit_h))
            self._layer_surfaces[i] = new

    def open_modal(self) -> None:
        self.open = True
        self._drag_mode = "none"
        self._save_prompt_active = False
        self._dim_edit_field = None
        self._swatch_edit_open = False
        self._layer_rename_idx = None
        self._load_editor_config()
        if not self._layer_surfaces:
            if self._sheet is None:
                self._init_layers_from_surface()
            else:
                self._init_layers_from_surface(self._sheet)
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
        self._swatch_edit_open = False
        self._layer_rename_idx = None
        self._rgba_drag_channel = None

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

    def _filtered_sprite_names(self) -> list[str]:
        """FEATURE-MAP-108: case-insensitive substring filter over Characters/*.png."""
        names = list_character_pngs(self._characters_dir())
        q = self._sprite_search_query.strip().lower()
        if not q:
            return names
        return [n for n in names if q in n.lower()]

    def _footer_start_y(self) -> int:
        """FEATURE-MAP-106/107: y position of the palette/dims/file footer row.

        Tracks the lower of the edit canvas and reference box so the footer moves up as
        zoom (and therefore canvas height) decreases. Reserves _REF_LABEL_H below the
        reference box for the yellow reference-name label (FEATURE-MAP-107) so it never
        collides with the palette row.
        """
        ref_bottom = self._ref_rect.bottom + 4 + _REF_LABEL_H
        return max(self._canvas_rect.bottom, ref_bottom) + 8

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
        self._init_layers_from_surface(img)
        self._filename = filename
        self._dirty = False
        self._sheet = None
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
        old_composite = self._ensure_sheet()
        self._sheet_w, self._sheet_h = w, h
        self._resize_all_layers(w, h, old_composite)
        self._dirty = True
        self._sheet = None
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
        px = min(cw - 1, int(lx / self._cell_step_x))
        py = min(ch - 1, int(ly / self._cell_step_y))
        if px < 0 or py < 0:
            return None
        return px, py

    def _apply_pixel(self, px: int, py: int, color: tuple[int, int, int, int]) -> None:
        layer = self._active_layer_surface()
        ox, oy = self._active_cell_origin()
        layer.set_at((ox + px, oy + py), color)
        self._dirty = True
        self._sheet = None
        if self._direction_idx == 1 and self._mirror_lock:
            self._sync_mirror_right_from_left()

    def _paint_at(self, mx: int, my: int, button: int) -> None:
        if self._layer_edit_blocked():
            return
        pix = self._pixel_at_canvas(mx, my)
        if pix is None:
            return
        px, py = pix
        if self._paint_last == (px, py):
            return
        self._paint_last = (px, py)
        if button == 3:
            self._apply_pixel(px, py, (0, 0, 0, 0))
            return
        if self._active_tool == "eraser":
            self._apply_pixel(px, py, (0, 0, 0, 0))
        elif self._active_tool == "paint":
            self._apply_pixel(px, py, self._paint_color)

    def _fill_at(self, mx: int, my: int) -> None:
        if self._layer_edit_blocked():
            return
        pix = self._pixel_at_canvas(mx, my)
        if pix is None:
            return
        px, py = pix
        layer = self._active_layer_surface()
        ox, oy = self._active_cell_origin()
        n = flood_fill_surface(layer, ox + px, oy + py, self._paint_color)
        if n > 0:
            self._dirty = True
            self._sheet = None
            if self._direction_idx == 1 and self._mirror_lock:
                self._sync_mirror_right_from_left()

    def _start_selection(self, px: int, py: int) -> None:
        self._selecting = True
        self._selection_start = (px, py)
        self._selection_rect = (px, py, px, py)

    def _update_selection(self, px: int, py: int) -> None:
        if self._selection_start is None:
            return
        cw, ch = self._cell_size()
        sx, sy = self._selection_start
        self._selection_rect = normalize_pixel_rect(sx, sy, px, py, cw, ch)

    def _finish_selection(self) -> None:
        self._selecting = False

    def _copy_selection(self) -> None:
        """FEATURE-MAP-109: copy the active layer's pixels within the selection rect."""
        if self._selection_rect is None:
            self.ed.set_status("No selection to copy.", kind="info")
            return
        x0, y0, x1, y1 = self._selection_rect
        layer = self._active_layer_surface()
        ox, oy = self._active_cell_origin()
        w, h = x1 - x0 + 1, y1 - y0 + 1
        self._clipboard = layer.subsurface((ox + x0, oy + y0, w, h)).copy()
        self.ed.set_status(f"Copied {w}x{h}.", kind="ok")

    def _paste_clipboard(self) -> None:
        """FEATURE-MAP-109: stamp the clipboard onto the active layer.

        Pastes at the last hovered canvas pixel when available, otherwise at the
        selection's original top-left corner (or the cell origin as a last resort).
        """
        if self._clipboard is None:
            self.ed.set_status("Clipboard empty.", kind="info")
            return
        if self._layer_edit_blocked():
            return
        cw, ch = self._cell_size()
        clip_w, clip_h = self._clipboard.get_size()
        if self._last_canvas_pixel is not None:
            tx, ty = self._last_canvas_pixel
        elif self._selection_rect is not None:
            tx, ty = self._selection_rect[0], self._selection_rect[1]
        else:
            tx, ty = 0, 0
        tx = max(0, min(cw - min(clip_w, cw), tx))
        ty = max(0, min(ch - min(clip_h, ch), ty))
        self._push_undo()
        layer = self._active_layer_surface()
        ox, oy = self._active_cell_origin()
        layer.blit(self._clipboard, (ox + tx, oy + ty))
        self._dirty = True
        self._sheet = None
        if self._direction_idx == 1 and self._mirror_lock:
            self._sync_mirror_right_from_left()
        self.ed.set_status(f"Pasted {clip_w}x{clip_h}.", kind="ok")

    def _add_layer(self) -> None:
        if len(self._layer_surfaces) >= MAX_NPC_LAYERS:
            self.ed.set_status(f"Max {MAX_NPC_LAYERS} layers.", kind="info")
            return
        self._push_undo()
        blank = self._blank_sheet_surface()
        self._layer_surfaces.append(blank)
        n = len(self._layer_surfaces)
        self._layer_names.append(f"Layer {n}")
        self._layer_visible.append(True)
        self._layer_locked.append(False)
        self._active_layer_index = n - 1
        self._dirty = True
        self._sheet = None

    def _remove_layer(self) -> None:
        if len(self._layer_surfaces) <= 1:
            self.ed.set_status("Cannot remove the last layer.", kind="info")
            return
        self._push_undo()
        idx = self._active_layer_index
        del self._layer_surfaces[idx]
        del self._layer_names[idx]
        del self._layer_visible[idx]
        del self._layer_locked[idx]
        self._active_layer_index = min(idx, len(self._layer_surfaces) - 1)
        self._dirty = True
        self._sheet = None

    def _draw_tool_button(
        self,
        ed: object,
        rect: pygame.Rect,
        label: str,
        active: bool,
    ) -> None:
        pygame.draw.rect(ed.screen, (55, 95, 75) if active else (44, 52, 58), rect)
        pygame.draw.rect(ed.screen, (120, 200, 140) if active else (70, 80, 90), rect, 1)
        ed.screen.blit(ed.font_small.render(label, True, (235, 245, 235)), (rect.x + 4, rect.y + 5))

    def _draw_rgba_sliders(self, ed: object, x: int, y: int, w: int) -> int:
        self._rgba_slider_rects = {}
        labels = ("R", "G", "B", "A")
        vals = self._paint_color
        bar_h = 14
        gap = 4
        for i, (ch, val) in enumerate(zip(labels, vals)):
            ly = y + i * (bar_h + gap)
            ed.screen.blit(ed.font_small.render(f"{ch}:{val}", True, (180, 190, 200)), (x, ly))
            bar = pygame.Rect(x + 36, ly, w - 40, bar_h)
            self._rgba_slider_rects[ch] = bar
            pygame.draw.rect(ed.screen, (35, 40, 48), bar)
            fill_w = int((bar.w - 2) * val / 255)
            if ch == "R":
                col = (val, 0, 0)
            elif ch == "G":
                col = (0, val, 0)
            elif ch == "B":
                col = (0, 0, val)
            else:
                col = (val, val, val)
            pygame.draw.rect(ed.screen, col, (bar.x + 1, bar.y + 1, max(1, fill_w), bar_h - 2))
            pygame.draw.rect(ed.screen, (90, 100, 115), bar, 1)
        return y + 4 * (bar_h + gap)

    def _draw_sprite_panel(self, ed: object) -> None:
        """FEATURE-MAP-108: collapsible searchable list of Characters/*.png for the reference picker."""
        r = self._sprite_panel_rect
        pygame.draw.rect(ed.screen, (26, 30, 34), r)
        pygame.draw.rect(ed.screen, (60, 70, 85), r, 1)
        toggle_h = 20
        self._sprite_panel_toggle_btn = pygame.Rect(r.x, r.y, r.w, toggle_h)
        pygame.draw.rect(ed.screen, (40, 48, 56), self._sprite_panel_toggle_btn)
        if self._sprite_panel_collapsed:
            ed.screen.blit(ed.font_small.render("\u25B8", True, (200, 210, 225)), (r.x + 6, r.y + 3))
            self._sprite_row_hit = []
            return
        ed.screen.blit(ed.font_small.render("\u25BE Sprites", True, (200, 210, 225)), (r.x + 4, r.y + 3))
        self._sprite_search_rect = pygame.Rect(r.x + 4, r.y + toggle_h + 4, r.w - 8, 20)
        pygame.draw.rect(ed.screen, (24, 30, 26), self._sprite_search_rect)
        pygame.draw.rect(
            ed.screen,
            (120, 200, 140) if self._sprite_search_focus else (70, 80, 90),
            self._sprite_search_rect,
            1,
        )
        q = self._sprite_search_query
        cursor = "|" if self._sprite_search_focus else ""
        if q:
            txt = mtext.truncate_to_width(ed.font_small, q + cursor, self._sprite_search_rect.w - 8)
            txt_col = (220, 230, 240)
        else:
            txt = f"{cursor}search"
            txt_col = (140, 150, 165)
        ed.screen.blit(ed.font_small.render(txt, True, txt_col), (self._sprite_search_rect.x + 4, self._sprite_search_rect.y + 3))

        list_rect = pygame.Rect(
            r.x + 4, self._sprite_search_rect.bottom + 4, r.w - 8, r.bottom - self._sprite_search_rect.bottom - 8
        )
        names = self._filtered_sprite_names()
        max_rows = max(1, list_rect.h // _SPRITE_ROW_H)
        self._sprite_list_scroll = max(0, min(self._sprite_list_scroll, max(0, len(names) - max_rows)))
        self._sprite_row_hit = []
        ry = list_rect.y
        for name in names[self._sprite_list_scroll : self._sprite_list_scroll + max_rows]:
            row = pygame.Rect(list_rect.x, ry, list_rect.w, _SPRITE_ROW_H - 2)
            if name == self._reference_name:
                pygame.draw.rect(ed.screen, (45, 70, 58), row)
            label = mtext.truncate_to_width(ed.font_small, name, row.w - 4)
            ed.screen.blit(ed.font_small.render(label, True, (220, 230, 240)), (row.x + 2, row.y + 2))
            self._sprite_row_hit.append((name, row))
            ry += _SPRITE_ROW_H

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
        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 280, head_h)
        title = "NPC Sprite Editor"
        if self._dirty:
            title += " *"
        ed.screen.blit(ed.font.render(title, True, (200, 255, 220)), (panel.x + 12, panel.y + 8))
        self.close_btn = pygame.Rect(panel.right - 72, panel.y + 6, 60, 26)
        pygame.draw.rect(ed.screen, (72, 48, 48), self.close_btn)
        ed.screen.blit(ed.font_small.render("Close", True, (245, 240, 240)), (self.close_btn.x + 10, self.close_btn.y + 6))
        self._help_btn = pygame.Rect(panel.right - 216, panel.y + 6, 64, 26)
        pygame.draw.rect(ed.screen, (55, 65, 40), self._help_btn)
        ed.screen.blit(ed.font_small.render("Help", True, (200, 245, 180)), (self._help_btn.x + 16, self._help_btn.y + 6))
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
            ed.screen.blit(ed.font_small.render(dname.capitalize(), True, (235, 248, 240)), (r.x + 8, r.y + 6))
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

        tool_btn_data: list[tuple[str | None, str, int, bool]] = [
            ("_mirror_btn", "Mirror R←L" + (" ✓" if self._mirror_lock else ""), 130, self._mirror_lock),
            ("_copy_idle_btn", "Idle→F3", 70, False),
            ("_dup_prev_btn", "Dup prev", 75, False),
            ("_new_btn", "New", 46, False),
            ("_load_btn", "Load", 46, False),
            ("_save_btn", "Save", 46, False),
            ("_save_as_btn", "Save As", 62, False),
            ("_zoom_out_btn", "-", 28, False),
            ("_zoom_in_btn", "+", 28, False),
            (None, f"Zoom {self._zoom}", 60, False),
            ("_ref_prev_btn", "<", 28, False),
            ("_ref_next_btn", ">", 28, False),
        ]
        tx, ty = body.x, y
        for attr, label, w, active in tool_btn_data:
            if tx + w > body.right and tx > body.x:
                tx = body.x
                ty += btn_h + gap
            if attr:
                r = pygame.Rect(tx, ty, w, btn_h)
                setattr(self, attr, r)
                pygame.draw.rect(ed.screen, (50, 80, 70) if active else (44, 52, 58), r)
                ed.screen.blit(ed.font_small.render(label, True, (220, 235, 225)), (r.x + 6, r.y + 6))
            else:
                ed.screen.blit(ed.font_small.render(label, True, (180, 190, 200)), (tx, ty + 6))
            tx += w + gap
        y = ty + btn_h + gap

        footer_h = 70
        avail_h = body.bottom - y - footer_h
        cw, ch = self._cell_size()
        raw_w, raw_h = cw * self._zoom, ch * self._zoom
        pair_w = raw_w * 2 + 12
        sprite_panel_w = _SPRITE_PANEL_COLLAPSED_W if self._sprite_panel_collapsed else _SPRITE_PANEL_EXPANDED_W
        max_pair_w = body.w - sprite_panel_w - 6 - _RAIL_W - 20
        fit_scale = min(max_pair_w / max(1, pair_w), avail_h / max(1, raw_h), 1.0)
        canvas_w = max(32, int(raw_w * fit_scale))
        canvas_h = max(32, int(raw_h * fit_scale))

        self._sprite_panel_rect = pygame.Rect(body.x, y, sprite_panel_w, avail_h)
        self._draw_sprite_panel(ed)

        rail_x = self._sprite_panel_rect.right + 6
        self._tool_rail_rect = pygame.Rect(rail_x, y, _RAIL_W, avail_h)
        pygame.draw.rect(ed.screen, (28, 32, 36), self._tool_rail_rect)
        pygame.draw.rect(ed.screen, (60, 70, 85), self._tool_rail_rect, 1)
        ry = self._tool_rail_rect.y + 6
        tw = self._tool_rail_rect.w - 12
        self._tool_paint_btn = pygame.Rect(self._tool_rail_rect.x + 6, ry, tw, 24)
        self._draw_tool_button(ed, self._tool_paint_btn, "Paint (P)", self._active_tool == "paint")
        ry += 28
        self._tool_eraser_btn = pygame.Rect(self._tool_rail_rect.x + 6, ry, tw, 24)
        self._draw_tool_button(ed, self._tool_eraser_btn, "Eraser (E)", self._active_tool == "eraser")
        ry += 28
        self._tool_fill_btn = pygame.Rect(self._tool_rail_rect.x + 6, ry, tw, 24)
        self._draw_tool_button(ed, self._tool_fill_btn, "Fill (F)", self._active_tool == "fill")
        ry += 28
        self._tool_select_btn = pygame.Rect(self._tool_rail_rect.x + 6, ry, tw, 24)
        self._draw_tool_button(ed, self._tool_select_btn, "Select (S)", self._active_tool == "select")
        ry += 30
        self._color_preview_rect = pygame.Rect(self._tool_rail_rect.x + 6, ry, tw, 20)
        if self._paint_color[3] == 0:
            pygame.draw.rect(ed.screen, (40, 40, 48), self._color_preview_rect)
            pygame.draw.line(ed.screen, (200, 80, 80), self._color_preview_rect.topleft, self._color_preview_rect.bottomright)
        else:
            pygame.draw.rect(ed.screen, self._paint_color[:3], self._color_preview_rect)
        pygame.draw.rect(ed.screen, (200, 210, 220), self._color_preview_rect, 1)
        ry += 26
        ry = self._draw_rgba_sliders(ed, self._tool_rail_rect.x + 6, ry, tw)
        ry += 6
        ed.screen.blit(ed.font_small.render("Layers", True, (170, 180, 195)), (self._tool_rail_rect.x + 6, ry))
        ry += 18
        layer_view_h = self._tool_rail_rect.bottom - ry - 52
        max_rows = max(1, layer_view_h // _LAYER_ROW_H)
        self._layer_row_hit = []
        start_i = min(self._layer_scroll, max(0, len(self._layer_names) - max_rows))
        for li in range(start_i, min(len(self._layer_names), start_i + max_rows)):
            row = pygame.Rect(self._tool_rail_rect.x + 4, ry, tw + 4, _LAYER_ROW_H - 2)
            eye = pygame.Rect(row.x, row.y + 2, 16, 16)
            lock = pygame.Rect(row.right - 18, row.y + 2, 16, 16)
            if li == self._active_layer_index:
                pygame.draw.rect(ed.screen, (45, 70, 58), row)
            name = mtext.truncate_to_width(ed.font_small, self._layer_names[li], row.w - 44)
            ed.screen.blit(ed.font_small.render(name, True, (220, 230, 240)), (eye.right + 4, row.y + 3))
            eye_txt = "◉" if self._layer_visible[li] else "○"
            lock_txt = "🔒" if self._layer_locked[li] else "🔓"
            ed.screen.blit(ed.font_small.render(eye_txt, True, (180, 220, 200)), (eye.x + 2, eye.y))
            ed.screen.blit(ed.font_small.render(lock_txt, True, (200, 200, 210)), (lock.x, lock.y))
            self._layer_row_hit.append((li, row, eye, lock))
            ry += _LAYER_ROW_H
        self._layer_add_btn = pygame.Rect(self._tool_rail_rect.x + 6, self._tool_rail_rect.bottom - 46, tw // 2 - 2, 22)
        self._layer_remove_btn = pygame.Rect(self._layer_add_btn.right + 4, self._layer_add_btn.y, tw // 2 - 2, 22)
        pygame.draw.rect(ed.screen, (48, 64, 56), self._layer_add_btn)
        pygame.draw.rect(ed.screen, (64, 56, 48), self._layer_remove_btn)
        ed.screen.blit(ed.font_small.render("+", True, (230, 240, 235)), (self._layer_add_btn.x + 8, self._layer_add_btn.y + 3))
        ed.screen.blit(ed.font_small.render("−", True, (230, 240, 235)), (self._layer_remove_btn.x + 8, self._layer_remove_btn.y + 3))
        self._edit_swatches_btn = pygame.Rect(self._tool_rail_rect.x + 6, self._tool_rail_rect.bottom - 22, tw, 20)
        pygame.draw.rect(ed.screen, (50, 55, 68), self._edit_swatches_btn)
        ed.screen.blit(ed.font_small.render("Edit Swatches", True, (200, 210, 225)), (self._edit_swatches_btn.x + 4, self._edit_swatches_btn.y + 3))

        ref_x = body.right - canvas_w
        self._ref_rect = pygame.Rect(ref_x, y, canvas_w, canvas_h)
        work_left = self._tool_rail_rect.right + 8
        work_right = self._ref_rect.left - 8
        canvas_x = work_left + max(0, (work_right - work_left - canvas_w) // 2)
        self._canvas_rect = pygame.Rect(canvas_x, y, canvas_w, canvas_h)
        self._cell_step_x = canvas_w / max(1, cw)
        self._cell_step_y = canvas_h / max(1, ch)

        pygame.draw.rect(ed.screen, (30, 34, 40), self._canvas_rect)
        pygame.draw.rect(ed.screen, (80, 90, 110), self._canvas_rect, 1)
        sheet = self._ensure_sheet()
        ox, oy = self._active_cell_origin()
        cell = sheet.subsurface((ox, oy, cw, ch))
        scaled = pygame.transform.scale(cell, (self._canvas_rect.w, self._canvas_rect.h))
        ed.screen.blit(scaled, self._canvas_rect.topleft)
        for gx in range(cw + 1):
            lx = int(self._canvas_rect.x + gx * self._cell_step_x)
            pygame.draw.line(ed.screen, (50, 55, 65), (lx, self._canvas_rect.y), (lx, self._canvas_rect.bottom))
        for gy in range(ch + 1):
            ly = int(self._canvas_rect.y + gy * self._cell_step_y)
            pygame.draw.line(ed.screen, (50, 55, 65), (self._canvas_rect.x, ly), (self._canvas_rect.right, ly))
        # FEATURE-MAP-109: marquee outline for the active rectangular selection.
        if self._selection_rect is not None:
            sx0, sy0, sx1, sy1 = self._selection_rect
            mrx = int(self._canvas_rect.x + sx0 * self._cell_step_x)
            mry = int(self._canvas_rect.y + sy0 * self._cell_step_y)
            mrw = int((sx1 - sx0 + 1) * self._cell_step_x)
            mrh = int((sy1 - sy0 + 1) * self._cell_step_y)
            pygame.draw.rect(ed.screen, (255, 255, 255), (mrx, mry, mrw, mrh), 2)

        # BUG-MAP-105/FEATURE-MAP-107: label moved below the reference image (was drawn
        # in the ~gap above the canvas, which overlapped the toolbar row on narrow panels).
        pygame.draw.rect(ed.screen, (28, 32, 38), self._ref_rect)
        pygame.draw.rect(ed.screen, (70, 80, 95), self._ref_rect, 1)
        if self._reference_surf is not None:
            rw, rh = self._reference_surf.get_size()
            rcx, rcy = rw // GRID_COLS, rh // 4
            ref_cell = self._reference_surf.subsurface(
                (self._frame_idx * rcx, self._direction_idx * rcy, rcx, rcy)
            )
            ref_scaled = pygame.transform.scale(ref_cell, (self._ref_rect.w, self._ref_rect.h))
            ed.screen.blit(ref_scaled, self._ref_rect.topleft)
            if self._ref_grid_on and rcx > 0 and rcy > 0:
                ref_step_x = self._ref_rect.w / rcx
                ref_step_y = self._ref_rect.h / rcy
                for gx in range(rcx + 1):
                    lx = int(self._ref_rect.x + gx * ref_step_x)
                    pygame.draw.line(ed.screen, (60, 65, 75), (lx, self._ref_rect.y), (lx, self._ref_rect.bottom))
                for gy in range(rcy + 1):
                    ly = int(self._ref_rect.y + gy * ref_step_y)
                    pygame.draw.line(ed.screen, (60, 65, 75), (self._ref_rect.x, ly), (self._ref_rect.right, ly))
        else:
            ed.screen.blit(ed.font_small.render("Reference", True, (120, 130, 145)), (self._ref_rect.x + 8, self._ref_rect.y + 8))
        self._ref_grid_toggle_btn = pygame.Rect(self._ref_rect.right - 50, self._ref_rect.y + 4, 46, 16)
        pygame.draw.rect(ed.screen, (48, 64, 56) if self._ref_grid_on else (48, 48, 56), self._ref_grid_toggle_btn)
        pygame.draw.rect(ed.screen, (140, 150, 170), self._ref_grid_toggle_btn, 1)
        ed.screen.blit(ed.font_small.render("Grid", True, (220, 230, 235)), (self._ref_grid_toggle_btn.x + 4, self._ref_grid_toggle_btn.y + 1))
        ref_label_y = self._ref_rect.bottom + 4
        ref_label = mtext.truncate_to_width(ed.font_small, self._reference_name or "(no ref)", max(20, canvas_w))
        ed.screen.blit(ed.font_small.render(ref_label, True, _REF_LABEL_COLOR), (ref_x, ref_label_y))

        pal_y = self._footer_start_y()
        swatch = 22
        self._palette_btns = []
        for i, col in enumerate(self._palette_colors):
            r = pygame.Rect(body.x + i * (swatch + 4), pal_y, swatch, swatch)
            if r.right > body.right:
                break
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
        file_avail = max(20, body.right - (body.x + 180))
        file_text = mtext.truncate_to_width(ed.font_small, f"File: {self._filename}", file_avail)
        ed.screen.blit(ed.font_small.render(file_text, True, (170, 180, 195)), (body.x + 180, info_y + 6))

        self._resize_corner_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        self._resize_corner_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(
            ed.screen, (100, 180, 130),
            [(panel.right, panel.bottom), (panel.right - 14, panel.bottom), (panel.right, panel.bottom - 14)],
        )
        pygame.draw.polygon(
            ed.screen, (90, 160, 120),
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

        if self._layer_rename_idx is not None:
            ov = pygame.Rect(panel.x + 80, panel.centery - 24, panel.w - 160, 48)
            pygame.draw.rect(ed.screen, (20, 28, 24), ov)
            pygame.draw.rect(ed.screen, (120, 200, 140), ov, 2)
            ed.screen.blit(
                ed.font_small.render(f"Layer name: [{self._layer_rename_buf}]", True, (255, 255, 200)),
                (ov.x + 10, ov.y + 14),
            )

        if self._swatch_edit_open:
            ov = pygame.Rect(panel.x + 60, panel.y + 80, panel.w - 120, panel.h - 160)
            pygame.draw.rect(ed.screen, (18, 24, 22), ov)
            pygame.draw.rect(ed.screen, (100, 180, 130), ov, 2)
            ed.screen.blit(ed.font.render("Edit swatches", True, (200, 255, 220)), (ov.x + 12, ov.y + 8))
            sy = ov.y + 32
            self._swatch_edit_remove_rects = []
            for i, col in enumerate(self._swatch_edit_working):
                sr = pygame.Rect(ov.x + 12 + i * 28, sy, 22, 22)
                self._swatch_edit_remove_rects.append(sr)
                if col[3] == 0:
                    pygame.draw.rect(ed.screen, (40, 40, 48), sr)
                else:
                    pygame.draw.rect(ed.screen, col[:3], sr)
                rm = pygame.Rect(sr.right + 2, sy, 18, 22)
                pygame.draw.rect(ed.screen, (70, 50, 50), rm)
                ed.screen.blit(ed.font_small.render("×", True, (240, 220, 220)), (rm.x + 4, rm.y + 2))
            self._swatch_edit_add_btn = pygame.Rect(ov.x + 12, sy + 30, 80, 24)
            self._swatch_edit_done_btn = pygame.Rect(ov.right - 170, ov.bottom - 32, 72, 26)
            self._swatch_edit_cancel_btn = pygame.Rect(ov.right - 90, ov.bottom - 32, 72, 26)
            pygame.draw.rect(ed.screen, (48, 72, 56), self._swatch_edit_add_btn)
            pygame.draw.rect(ed.screen, (55, 90, 70), self._swatch_edit_done_btn)
            pygame.draw.rect(ed.screen, (72, 48, 48), self._swatch_edit_cancel_btn)
            ed.screen.blit(ed.font_small.render("+ Add", True, (230, 240, 235)), (self._swatch_edit_add_btn.x + 8, self._swatch_edit_add_btn.y + 5))
            ed.screen.blit(ed.font_small.render("Done", True, (230, 245, 235)), (self._swatch_edit_done_btn.x + 16, self._swatch_edit_done_btn.y + 6))
            ed.screen.blit(ed.font_small.render("Cancel", True, (245, 235, 235)), (self._swatch_edit_cancel_btn.x + 10, self._swatch_edit_cancel_btn.y + 6))

    def _rgba_value_from_mx(self, ch: str, mx: int, bar: pygame.Rect) -> int:
        if bar.w <= 2:
            return 0
        t = (mx - bar.x) / (bar.w - 1)
        return max(0, min(255, int(t * 255)))

    def _set_paint_channel(self, ch: str, val: int) -> None:
        idx = {"R": 0, "G": 1, "B": 2, "A": 3}[ch]
        c = list(self._paint_color)
        c[idx] = val
        self._paint_color = (c[0], c[1], c[2], c[3])
        self._active_tool = "paint"

    def handle_key(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        if self._swatch_edit_open:
            return True
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
        if self._layer_rename_idx is not None:
            if event.key == pygame.K_ESCAPE:
                self._layer_rename_idx = None
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                idx = self._layer_rename_idx
                name = self._layer_rename_buf.strip() or self._layer_names[idx]
                self._layer_names[idx] = name[:32]
                self._layer_rename_idx = None
                return True
            if event.key == pygame.K_BACKSPACE:
                self._layer_rename_buf = self._layer_rename_buf[:-1]
                return True
            if event.unicode and event.unicode.isprintable():
                self._layer_rename_buf += event.unicode
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
        # FEATURE-MAP-108: sprite search box captures all typing (high priority, like the
        # other text-entry modes above) so letters such as P/E/F/S/Z/R don't trigger tools.
        if self._sprite_search_focus:
            if event.key == pygame.K_ESCAPE:
                self._sprite_search_focus = False
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._sprite_search_focus = False
                return True
            if event.key == pygame.K_BACKSPACE:
                self._sprite_search_query = self._sprite_search_query[:-1]
                return True
            if event.unicode and event.unicode.isprintable():
                self._sprite_search_query += event.unicode
                return True
            return True

        ctrl = bool(event.mod & pygame.KMOD_CTRL)
        shift = bool(event.mod & pygame.KMOD_SHIFT)

        # FEATURE-MAP-110: Ctrl-combos checked first so plain S still means "select tool".
        if ctrl and shift and event.key == pygame.K_s:
            self._save_sheet(save_as=True)
            return True
        if ctrl and event.key == pygame.K_s:
            self._save_sheet(save_as=False)
            return True
        if ctrl and event.key == pygame.K_c:
            self._copy_selection()
            return True
        if ctrl and event.key == pygame.K_v:
            self._paste_clipboard()
            return True

        if event.key == pygame.K_ESCAPE and self._selection_rect is not None:
            self._selection_rect = None
            self._selection_start = None
            return True
        if event.key == pygame.K_p:
            self._active_tool = "paint"
            return True
        if event.key == pygame.K_e:
            self._active_tool = "eraser"
            return True
        if event.key == pygame.K_f:
            self._active_tool = "fill"
            return True
        if event.key == pygame.K_s:
            self._active_tool = "select"
            return True
        # FEATURE-MAP-110: plain Z/R undo-redo (replacing Ctrl+Z/Ctrl+Y), consistent with
        # the other single-key tool shortcuts (P/E/F/S).
        if event.key == pygame.K_z:
            if self._undo_stack:
                self._redo_stack.append(self._snapshot_layers())
                self._restore_layers(self._undo_stack.pop())
                self._dirty = True
            return True
        if event.key == pygame.K_r:
            if self._redo_stack:
                self._undo_stack.append(self._snapshot_layers())
                self._restore_layers(self._redo_stack.pop())
                self._dirty = True
            return True
        return False

    def handle_wheel(self, mx: int, my: int, dy: int) -> bool:
        if not self.open:
            return False
        if not self._sprite_panel_collapsed and self._sprite_panel_rect.collidepoint(mx, my):
            self._sprite_list_scroll = max(0, self._sprite_list_scroll - dy)
            return True
        if self._tool_rail_rect.collidepoint(mx, my):
            self._layer_scroll = max(0, self._layer_scroll - dy)
            return True
        if self._canvas_rect.collidepoint(mx, my):
            self._zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self._zoom + dy))
            return True
        return True

    def _handle_layer_row_click(self, mx: int, my: int, button: int) -> bool:
        now = time.monotonic()
        for li, row, eye, lock in self._layer_row_hit:
            if lock.collidepoint(mx, my) and button == 1:
                self._layer_locked[li] = not self._layer_locked[li]
                return True
            if eye.collidepoint(mx, my) and button == 1:
                self._layer_visible[li] = not self._layer_visible[li]
                self._sheet = None
                return True
            if row.collidepoint(mx, my) and button == 1:
                self._active_layer_index = li
                if self._last_layer_click[0] == li and now - self._last_layer_click[1] < _DBL_CLICK_SEC:
                    self._layer_rename_idx = li
                    self._layer_rename_buf = self._layer_names[li]
                self._last_layer_click = (li, now)
                return True
        return False

    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        if button == 1 and not self._sprite_search_rect.collidepoint(mx, my):
            self._sprite_search_focus = False
        if self._swatch_edit_open:
            if self._swatch_edit_done_btn.collidepoint(mx, my) and button == 1:
                self._palette_colors = list(self._swatch_edit_working)
                self._save_palette_config()
                self._swatch_edit_open = False
                return True
            if self._swatch_edit_cancel_btn.collidepoint(mx, my) and button == 1:
                self._swatch_edit_open = False
                return True
            if self._swatch_edit_add_btn.collidepoint(mx, my) and button == 1:
                self._swatch_edit_working.append(tuple(self._paint_color))
                return True
            for i, sr in enumerate(self._swatch_edit_remove_rects):
                rm = pygame.Rect(sr.right + 2, sr.y, 18, 22)
                if rm.collidepoint(mx, my) and button == 1:
                    if len(self._swatch_edit_working) > 1:
                        del self._swatch_edit_working[i]
                    return True
            return True
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
        if self._help_btn.collidepoint(mx, my) and button == 1:
            self.ed._open_help_overlay(tab="npc_sprites", back_to="npc")
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
            if self._sprite_panel_toggle_btn.collidepoint(mx, my):
                self._sprite_panel_collapsed = not self._sprite_panel_collapsed
                return True
            if not self._sprite_panel_collapsed:
                if self._sprite_search_rect.collidepoint(mx, my):
                    self._sprite_search_focus = True
                    return True
                for name, row in self._sprite_row_hit:
                    if row.collidepoint(mx, my):
                        self._reference_name = name
                        self._load_reference_surface()
                        self._sprite_search_focus = False
                        return True
            if self._ref_grid_toggle_btn.collidepoint(mx, my):
                self._ref_grid_on = not self._ref_grid_on
                return True
            for ch, bar in self._rgba_slider_rects.items():
                if bar.collidepoint(mx, my):
                    self._rgba_drag_channel = ch
                    self._set_paint_channel(ch, self._rgba_value_from_mx(ch, mx, bar))
                    return True
            if self._tool_paint_btn.collidepoint(mx, my):
                self._active_tool = "paint"
                return True
            if self._tool_eraser_btn.collidepoint(mx, my):
                self._active_tool = "eraser"
                return True
            if self._tool_fill_btn.collidepoint(mx, my):
                self._active_tool = "fill"
                return True
            if self._tool_select_btn.collidepoint(mx, my):
                self._active_tool = "select"
                return True
            if self._layer_add_btn.collidepoint(mx, my):
                self._add_layer()
                return True
            if self._layer_remove_btn.collidepoint(mx, my):
                self._remove_layer()
                return True
            if self._edit_swatches_btn.collidepoint(mx, my):
                self._swatch_edit_working = list(self._palette_colors)
                self._swatch_edit_open = True
                return True
            if self._handle_layer_row_click(mx, my, button):
                return True
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
                self._sheet_w, self._sheet_h = DEFAULT_SHEET_W, DEFAULT_SHEET_H
                self._init_layers_from_surface()
                self._dirty = True
                self._sheet = None
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
                    self._active_tool = "paint"
                    return True
        if self._canvas_rect.collidepoint(mx, my):
            pix = self._pixel_at_canvas(mx, my)
            if pix is not None:
                self._last_canvas_pixel = pix
            if self._active_tool == "select":
                if button == 1 and pix is not None:
                    self._start_selection(*pix)
                    return True
                if button == 3:
                    self._selection_rect = None
                    self._selection_start = None
                    return True
                return True
            if self._active_tool == "fill" and button == 1:
                self._push_undo()
                self._fill_at(mx, my)
                return True
            if button in (1, 3):
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
            if button == 1 and self._selecting:
                self._finish_selection()
            self._rgba_drag_channel = None
            self._drag_mode = "none"
            return True
        return False

    def handle_mouse_motion(self, mx: int, my: int) -> bool:
        if not self.open:
            return False
        if self._rgba_drag_channel:
            ch = self._rgba_drag_channel
            bar = self._rgba_slider_rects.get(ch)
            if bar:
                self._set_paint_channel(ch, self._rgba_value_from_mx(ch, mx, bar))
            return True
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
        pix = self._pixel_at_canvas(mx, my)
        if pix is not None:
            self._last_canvas_pixel = pix
        if self._selecting:
            if pix is not None:
                self._update_selection(*pix)
            return True
        if self._paint_button is not None:
            self._paint_at(mx, my, self._paint_button)
            return True
        return False

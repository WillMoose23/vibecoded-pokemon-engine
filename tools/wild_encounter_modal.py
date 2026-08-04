"""FEATURE-MAP-056 / BUG-MAP-057 / FEATURE-MAP-058: dedicated wild encounter editor modal.

BUG-MAP-057: mini-map blank fixed — _draw_mini_map now derives map_rect from
self.map_inner (set in draw() before this call) instead of the stale _map_view_rect
which started as Rect(0,0,1,1) and caused a perpetual early-return.

FEATURE-MAP-058: typed inputs for stepChancePercent and weight; Global encounters
tab; adjacency auto-assign painting; flood-fill patch selection with highlighting.
"""
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

import pygame

import modal_text as mtext

from wild_encounter_editor_helpers import (
    snap_cell_to_stride_grid,
    wild_species_default_for_new_row,
    wild_species_display_list,
)

if TYPE_CHECKING:
    from map_editor import MapEditor


class WildEncounterModal:
    def __init__(self, editor: MapEditor) -> None:
        self.ed = editor
        self.open = False
        self.panel_rect = pygame.Rect(0, 0, 1, 1)
        self.map_inner = pygame.Rect(0, 0, 1, 1)
        self._map_view_rect = pygame.Rect(0, 0, 1, 1)
        self.species_inner = pygame.Rect(0, 0, 1, 1)
        self.patch_inner = pygame.Rect(0, 0, 1, 1)
        self.close_btn = pygame.Rect(0, 0, 1, 1)
        self._back_btn = pygame.Rect(0, 0, 1, 1)
        self._help_btn = pygame.Rect(0, 0, 1, 1)
        self.mode_patches_btn = pygame.Rect(0, 0, 1, 1)
        self.mode_map_btn = pygame.Rect(0, 0, 1, 1)
        self.edit_mode: str = "patches"

        # Local / Global tab in the patch column (FEATURE-MAP-058)
        self.modal_tab: str = "local"
        self._tab_local_btn = pygame.Rect(0, 0, 1, 1)
        self._tab_global_btn = pygame.Rect(0, 0, 1, 1)

        # Inline text editing state (FEATURE-MAP-058)
        self._edit_field: str | None = None  # "step" | "weight_N"
        self._edit_buf: str = ""
        self._edit_rects: dict[str, pygame.Rect] = {}

        # Flood-fill selection of a contiguous patch component (FEATURE-MAP-058)
        self._selected_cells: set[tuple[int, int]] = set()

        # Zoom and resize/move state (FEATURE-MAP-059 / FEATURE-MAP-060)
        # _map_zoom None = auto-fit; int = explicit px-per-cell [4..64]
        self._map_zoom: int | None = None
        # _panel_override persists across close/reopen so the user's chosen size/pos is remembered
        self._panel_override: pygame.Rect | None = None
        # _drag_mode: "none" | "resize_br" | "resize_bl" | "move"
        self._drag_mode: str = "none"
        self._drag_ref: tuple[int, int] = (0, 0)
        self._resize_corner_br: pygame.Rect = pygame.Rect(0, 0, 16, 16)
        self._resize_corner_bl: pygame.Rect = pygame.Rect(0, 0, 16, 16)
        self._title_bar: pygame.Rect = pygame.Rect(0, 0, 1, 1)
        self._zoom_in_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)
        self._zoom_out_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)
        self._zoom_fit_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)

        # Species list scroll context (BUG-MAP-062)
        self._species_vis: int = 1

        self.filter = ""
        self.species_scroll = 0
        self.species_sel = 0
        self.search_focus = False
        self._species_hits: list[tuple[int, pygame.Rect, pygame.Rect]] = []
        self._patch_row_rects: list[tuple[int, pygame.Rect]] = []
        self._tier_tab_rects: dict[str, pygame.Rect] = {}
        self._enc_row_rects: list[tuple[int, pygame.Rect]] = []
        self._global_enc_row_rects: list[tuple[int, pygame.Rect]] = []
        self.map_drag_start: tuple[int, int] | None = None
        self.map_paint_current: tuple[int, int] | None = None
        # FEATURE-MAP-086: independent map scope picker
        self.sel_map_id: str | None = None
        self.maps: list[str] = []
        self.map_search = ""
        self.map_scroll = 0
        self._map_picker_rect = pygame.Rect(0, 0, 1, 1)
        self._map_search_rect = pygame.Rect(0, 0, 1, 1)
        self._map_rows: list[tuple[str, pygame.Rect]] = []

    def open_modal(self) -> None:
        self.open = True
        self.ed.wild_canvas_mode_open = False
        self.ed.wild_encounter_mode_open = True
        self.ed.wild_species_pick_open = False
        self.ed.wild_modal_begin()
        self.maps = self.ed.list_all_map_ids()
        self.map_search = ""
        self.map_scroll = 0
        if self.sel_map_id is None or self.sel_map_id not in self.maps:
            cur = self.ed.map_id
            self.sel_map_id = cur if cur in self.maps else (self.maps[0] if self.maps else None)
        if self.sel_map_id and self.sel_map_id != getattr(self.ed, "wild_modal_scope_id", None):
            self.ed.wild_modal_switch_map(self.sel_map_id)
        self.filter = ""
        self.species_scroll = 0
        self.species_sel = 0
        self.search_focus = True
        self._selected_cells = set()
        self._edit_field = None
        self._edit_buf = ""
        self._map_zoom = None   # always auto-fit on open; _panel_override intentionally kept
        self._drag_mode = "none"
        self.ed._ensure_default_wild_patch()

    def close_modal(self, *, switch_to_canvas: bool = False) -> None:
        self.open = False
        ed = self.ed
        if switch_to_canvas:
            if ed.wild_modal_scope_id is not None:
                ed._persist_wild_data_for_scope(ed.wild_modal_scope_id)
            if ed._wild_modal_main_backup is not None:
                ed._restore_session_map_bundle(ed._wild_modal_main_backup)
                ed._wild_modal_main_backup = None
            ed.wild_modal_scope_id = None
            ed.refresh_map_file_list()
            ed.wild_canvas_mode_open = True
            ed.wild_encounter_mode_open = True
            ed._ensure_default_wild_patch()
            ed.set_status(
                "Wild patch paint on main map — Esc to exit; RMB erases; open Wild modal for species.",
                kind="info",
            )
        else:
            ed.wild_encounter_mode_open = False
            ed.wild_modal_end()
        self.map_drag_start = None
        self.map_paint_current = None
        self._commit_edit()

    def _mark_dirty(self) -> None:
        self.ed._wild_modal_dirty = True

    def _draw_map_picker(self, rect: pygame.Rect) -> None:
        """FEATURE-MAP-086: compact map list for independent wild scope."""
        ed = self.ed
        self._map_picker_rect = rect
        pygame.draw.rect(ed.screen, (16, 22, 20), rect)
        pygame.draw.rect(ed.screen, (70, 120, 95), rect, 1)
        ed.screen.blit(ed.font_small.render("Maps", True, (190, 220, 200)), (rect.x + 6, rect.y + 4))
        self._map_search_rect = pygame.Rect(rect.x + 6, rect.y + 22, rect.w - 12, 20)
        pygame.draw.rect(ed.screen, (28, 34, 30), self._map_search_rect)
        qshow = self.map_search or "search"
        ed.screen.blit(ed.font_small.render(mtext.truncate_to_width(ed.font_small, qshow, rect.w - 20), True, (180, 190, 185)),
                       (self._map_search_rect.x + 4, self._map_search_rect.y + 3))
        list_r = pygame.Rect(rect.x + 6, rect.y + 46, rect.w - 12, rect.h - 52)
        q = self.map_search.strip().lower()
        shown = [m for m in self.maps if not q or q in m.lower()]
        rh = ed.font_small.get_linesize() + 2
        self.map_scroll = max(0, min(self.map_scroll, max(0, len(shown) * rh - list_r.h)))
        prev = ed.screen.get_clip()
        ed.screen.set_clip(list_r)
        y = list_r.y - self.map_scroll
        self._map_rows = []
        scope = getattr(ed, "wild_modal_scope_id", None) or ed.map_id
        for m in shown:
            row = pygame.Rect(list_r.x, y, list_r.w, rh)
            if row.bottom > list_r.y and row.top < list_r.bottom:
                if m == scope:
                    pygame.draw.rect(ed.screen, (54, 92, 70), row)
                ed.screen.blit(ed.font_small.render(m[:28], True, (200, 255, 220) if m == scope else (170, 190, 175)),
                               (row.x + 2, row.y + 1))
            self._map_rows.append((m, row))
            y += rh
        ed.screen.set_clip(prev)

    # -------------------------------------------------------------------------

    def _player_stride_params(self) -> tuple[int, int, int]:
        self.ed._refresh_overworld_view_player_config()
        return (
            self.ed._ov_player_tiles_w,
            self.ed._ov_player_tiles_h,
            self.ed._ov_player_draw_off_x,
        )

    def snap_cell(self, tx: int, ty: int) -> tuple[int, int]:
        pw, ph, off = self._player_stride_params()
        return snap_cell_to_stride_grid(tx, ty, pw, ph, off)

    def cell_at_pixel(self, mx: int, my: int) -> tuple[int, int] | None:
        r = self._map_view_rect if self._map_view_rect.w > 1 else self.map_inner
        if not r.collidepoint(mx, my):
            return None
        cp = self._cell_px()
        if cp < 1:
            return None
        lx = mx - r.x + self.ed.wild_modal_map_off_x
        ly = my - r.y + self.ed.wild_modal_map_off_y
        if lx < 0 or ly < 0:
            return None
        cx = lx // cp
        cy = ly // cp
        if cx >= self.ed.map_w or cy >= self.ed.map_h:
            return None
        return self.snap_cell(cx, cy)

    def _cell_px(self) -> int:
        # FEATURE-MAP-059: explicit zoom takes priority over auto-fit
        if self._map_zoom is not None:
            return self._map_zoom
        # BUG-MAP-057: use map_inner when _map_view_rect hasn't been sized yet
        r = self._map_view_rect if self._map_view_rect.w > 1 else self.map_inner
        if self.ed.map_w <= 0 or self.ed.map_h <= 0:
            return 8
        return max(4, min(r.w // self.ed.map_w, r.h // self.ed.map_h))

    def _species_names(self) -> list[str]:
        return wild_species_display_list(
            self.ed._pokemon_species_keys(),
            self.ed.wild_species_favorites,
            self.filter,
        )

    def _commit_edit(self) -> None:
        """Validate the text buffer and write back to the data model; then clear state."""
        if self._edit_field is None:
            return
        field = self._edit_field
        buf = self._edit_buf.strip()
        self._edit_field = None
        self._edit_buf = ""
        if not buf:
            return
        try:
            val = int(buf)
        except ValueError:
            return
        if field == "step":
            p = self.ed._wild_active_patch()
            if p is not None:
                self.ed._undo_checkpoint()
                p["stepChancePercent"] = max(0, min(100, val))
                self._mark_dirty()
        elif field.startswith("weight_"):
            try:
                ri = int(field[len("weight_"):])
            except ValueError:
                return
            if self.modal_tab == "global":
                tier = self.ed.wild_tier_tab
                rows = self.ed.wild_global_encounters.get(tier, [])
            else:
                p = self.ed._wild_active_patch()
                rows = self.ed._wild_tier_rows(p) if p else []
            if 0 <= ri < len(rows):
                self.ed._undo_checkpoint()
                rows[ri]["weight"] = max(1, min(999, val))
                self._mark_dirty()

    # -------------------------------------------------------------------------
    # Adjacency paint helpers (FEATURE-MAP-058)
    # -------------------------------------------------------------------------

    def _neighbor_patch_index(self, x: int, y: int) -> int | None:
        """Return the 1-based patch index of the first non-zero 4-neighbor, or None."""
        ed = self.ed
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < ed.map_w and 0 <= ny < ed.map_h:
                v = ed.wild_encounter[ny][nx]
                if v > 0:
                    return v
        return None

    def _create_new_patch_for_cell(self) -> int:
        """Append a new default patch to ed.wild_patches; return its 1-based index."""
        ed = self.ed
        n = len(ed.wild_patches) + 1
        ed.wild_patches.append(ed._wild_default_patch(n))
        ed.active_wild_patch_index = len(ed.wild_patches) - 1
        ed.selected_wild_patch_index = ed.active_wild_patch_index
        return len(ed.wild_patches)

    # -------------------------------------------------------------------------
    # Flood-fill selection (FEATURE-MAP-058)
    # -------------------------------------------------------------------------

    def _flood_fill_component(self, x: int, y: int) -> set[tuple[int, int]]:
        """BFS from (x, y) collecting all 4-connected cells with the same patch index."""
        ed = self.ed
        if not (0 <= x < ed.map_w and 0 <= y < ed.map_h):
            return set()
        target = ed.wild_encounter[y][x]
        if target == 0:
            return set()
        visited: set[tuple[int, int]] = set()
        queue: deque[tuple[int, int]] = deque([(x, y)])
        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) in visited:
                continue
            if not (0 <= cx < ed.map_w and 0 <= cy < ed.map_h):
                continue
            if ed.wild_encounter[cy][cx] != target:
                continue
            visited.add((cx, cy))
            for ddx, ddy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
                nb = (cx + ddx, cy + ddy)
                if nb not in visited:
                    queue.append(nb)
        return visited

    # -------------------------------------------------------------------------
    # Drawing
    # -------------------------------------------------------------------------

    def draw(self) -> None:
        if not self.open:
            return
        ed = self.ed
        # FEATURE-MAP-063: use full screen rect so the modal and dim overlay cover
        # the entire program window, not just the map viewport sub-rect.
        # screen.get_rect() always reflects the live window size, so the modal
        # auto-recentres after windowed/fullscreen toggles.
        canvas = ed.screen.get_rect()
        dim = pygame.Surface((canvas.w, canvas.h), pygame.SRCALPHA)
        dim.fill((8, 12, 16, 210))
        ed.screen.blit(dim, canvas.topleft)

        # FEATURE-MAP-059: use stored size when user has resized the modal
        if self._panel_override is not None:
            panel = self._panel_override.copy()
        else:
            cap_w = max(640, canvas.w - 24)
            cap_h = max(480, canvas.h - 24)
            panel_w = min(1100, cap_w)
            panel_h = min(720, cap_h)
            panel = pygame.Rect(0, 0, panel_w, panel_h)
            panel.center = canvas.center
        # Clamp size first (so position clamping uses the correct, reduced dimensions).
        # This handles the case where _panel_override was set in a larger window/fullscreen
        # and the window has since been made smaller (BUG: overflow_right confirmed by logs).
        panel.w = max(640, min(panel.w, canvas.w - 8))
        panel.h = max(480, min(panel.h, canvas.h - 8))
        # Then clamp position to canvas bounds
        panel.x = max(canvas.x + 4, min(panel.x, canvas.right - panel.w - 4))
        panel.y = max(canvas.y + 4, min(panel.y, canvas.bottom - panel.h - 4))
        self.panel_rect = panel

        gap = 8
        head_h = 36
        foot_h = 28

        pygame.draw.rect(ed.screen, (20, 32, 28), panel)
        pygame.draw.rect(ed.screen, (90, 200, 140), panel, 2)
        # FEATURE-MAP-060: title bar drag handle — covers full header minus close button
        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 80, head_h)
        ed.screen.blit(
            ed.font.render("Wild encounters (FEATURE-MAP-056/058)", True, (200, 255, 220)),
            (panel.x + 12, panel.y + 8),
        )
        # Subtle grip dots to indicate the title bar is draggable
        for i in range(5):
            gx = panel.centerx - 20 + i * 10
            pygame.draw.circle(ed.screen, (70, 130, 100), (gx, panel.y + head_h // 2), 2)
        self.close_btn = pygame.Rect(panel.right - 72, panel.y + 6, 60, 26)
        pygame.draw.rect(ed.screen, (72, 48, 48), self.close_btn)
        ed.screen.blit(
            ed.font_small.render("Close", True, (245, 240, 240)),
            (self.close_btn.x + 10, self.close_btn.y + 6),
        )
        # FEATURE-MAP-064: Back and Help buttons
        self._back_btn = pygame.Rect(panel.right - 144, panel.y + 6, 64, 26)
        pygame.draw.rect(ed.screen, (50, 70, 90), self._back_btn)
        pygame.draw.rect(ed.screen, (90, 130, 170), self._back_btn, 1)
        ed.screen.blit(
            ed.font_small.render("\u2190 Back", True, (200, 225, 245)),
            (self._back_btn.x + 8, self._back_btn.y + 6),
        )
        self._help_btn = pygame.Rect(panel.right - 216, panel.y + 6, 64, 26)
        pygame.draw.rect(ed.screen, (55, 65, 40), self._help_btn)
        pygame.draw.rect(ed.screen, (100, 150, 80), self._help_btn, 1)
        ed.screen.blit(
            ed.font_small.render("Help", True, (200, 245, 180)),
            (self._help_btn.x + 16, self._help_btn.y + 6),
        )
        self._main_map_btn = pygame.Rect(panel.right - 288, panel.y + 6, 64, 26)
        pygame.draw.rect(ed.screen, (45, 85, 70), self._main_map_btn)
        pygame.draw.rect(ed.screen, (90, 160, 120), self._main_map_btn, 1)
        ed.screen.blit(
            ed.font_small.render("Main map", True, (200, 245, 220)),
            (self._main_map_btn.x + 4, self._main_map_btn.y + 6),
        )
        body = pygame.Rect(panel.x + 10, panel.y + head_h, panel.w - 20, panel.h - head_h - foot_h)
        map_pick_h = 72
        pick_r = pygame.Rect(body.x, body.y, min(200, body.w // 3), map_pick_h)
        self._draw_map_picker(pick_r)
        patch_w = min(260, max(180, body.w // 4))
        species_w = min(280, max(200, body.w // 4))
        map_w = max(120, body.w - patch_w - species_w - 2 * gap - pick_r.w - gap)
        y0 = body.y + map_pick_h + gap
        h0 = body.h - map_pick_h - gap
        self.patch_inner = pygame.Rect(body.x, y0, patch_w, h0)
        self.map_inner = pygame.Rect(self.patch_inner.right + gap, y0, map_w, h0)
        self.species_inner = pygame.Rect(self.map_inner.right + gap, y0, species_w, h0)

        for col, title in (
            (self.patch_inner, "Patches"),
            (self.map_inner, "Map"),
            (self.species_inner, "Species"),
        ):
            pygame.draw.rect(ed.screen, (16, 22, 20), col)
            pygame.draw.rect(ed.screen, (70, 120, 95), col, 1)
            ed.screen.blit(ed.font_small.render(title, True, (190, 220, 200)), (col.x + 6, col.y + 4))

        # Map column mode buttons (Patches / Tiles paint target)
        self.mode_patches_btn = pygame.Rect(self.map_inner.x + 6, self.map_inner.y + 22, 72, 22)
        self.mode_map_btn = pygame.Rect(self.mode_patches_btn.right + 6, self.map_inner.y + 22, 72, 22)
        for rect, mid, lab in (
            (self.mode_patches_btn, "patches", "Patches"),
            (self.mode_map_btn, "map", "Tiles"),
        ):
            on = self.edit_mode == mid
            pygame.draw.rect(ed.screen, (50, 100, 75) if on else (34, 44, 40), rect)
            ed.screen.blit(
                ed.font_small.render(lab, True, (240, 255, 245) if on else (170, 190, 175)),
                (rect.x + 8, rect.y + 4),
            )

        # FEATURE-MAP-059: zoom buttons [-] [fit] [+] and zoom level label
        bx = self.mode_map_btn.right + 10
        by = self.map_inner.y + 22
        self._zoom_out_btn = pygame.Rect(bx,      by, 22, 22)
        self._zoom_fit_btn = pygame.Rect(bx + 24, by, 28, 22)
        self._zoom_in_btn  = pygame.Rect(bx + 54, by, 22, 22)
        for rect, label in (
            (self._zoom_out_btn, "-"),
            (self._zoom_fit_btn, "fit"),
            (self._zoom_in_btn,  "+"),
        ):
            pygame.draw.rect(ed.screen, (40, 70, 55), rect)
            ed.screen.blit(
                ed.font_small.render(label, True, (220, 240, 230)),
                (rect.x + 4, rect.y + 4),
            )
        zoom_label = "auto" if self._map_zoom is None else f"{self._map_zoom}px"
        ed.screen.blit(
            ed.font_small.render(zoom_label, True, (160, 190, 170)),
            (self._zoom_in_btn.right + 4, by + 4),
        )

        self._draw_mini_map()
        self._draw_patch_column()
        self._draw_species_column()

        hint = "Click patch tile→select · drag empty→paint · R-click erase · Ctrl+scroll=zoom · Esc close"
        ed.screen.blit(ed.font_small.render(hint, True, (150, 175, 165)), (panel.x + 12, panel.bottom - 22))

        # FEATURE-MAP-059/060: resize grip triangles (drawn last, over all content)
        # Bottom-right grip
        self._resize_corner_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(
            ed.screen,
            (90, 160, 120),
            [
                (panel.right - 2,  panel.bottom - 14),
                (panel.right - 2,  panel.bottom - 2),
                (panel.right - 14, panel.bottom - 2),
            ],
        )
        # FEATURE-MAP-060: Bottom-left grip (mirrored triangle)
        self._resize_corner_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(
            ed.screen,
            (90, 160, 120),
            [
                (panel.x + 2,  panel.bottom - 14),
                (panel.x + 2,  panel.bottom - 2),
                (panel.x + 14, panel.bottom - 2),
            ],
        )

    def _draw_mini_map(self) -> None:
        ed = self.ed
        # BUG-MAP-057: derive map_rect from self.map_inner (always valid after draw()
        # lays out the columns), not from self._map_view_rect which starts as (0,0,1,1)
        # and produces negative dimensions that trigger the early-return guard forever.
        base = self.map_inner
        map_rect = pygame.Rect(base.x + 4, base.y + 48, base.w - 8, base.h - 52)
        if map_rect.w < 8 or map_rect.h < 8:
            return
        self._map_view_rect = map_rect
        cp = self._cell_px()
        total_w = ed.map_w * cp
        total_h = ed.map_h * cp
        ed.wild_modal_map_off_x = max(0, min(ed.wild_modal_map_off_x, max(0, total_w - map_rect.w)))
        ed.wild_modal_map_off_y = max(0, min(ed.wild_modal_map_off_y, max(0, total_h - map_rect.h)))

        clip_prev = ed.screen.get_clip()
        ed.screen.set_clip(map_rect)
        try:
            for y in range(ed.map_h):
                for x in range(ed.map_w):
                    px = map_rect.x + x * cp - ed.wild_modal_map_off_x
                    py = map_rect.y + y * cp - ed.wild_modal_map_off_y
                    if px + cp < map_rect.x or py + cp < map_rect.y or px > map_rect.right or py > map_rect.bottom:
                        continue
                    pygame.draw.rect(ed.screen, (24, 24, 30), (px, py, cp, cp))
                    for grid in ed.tile_layers:
                        c = grid[y][x]
                        if c is not None:
                            ed.blit_tile_scaled(ed.screen, c["ts"], c["t"], px, py, cp)
                    if self.edit_mode == "patches":
                        idx = ed.wild_encounter[y][x]
                        if idx > 0:
                            ov = pygame.Surface((cp, cp), pygame.SRCALPHA)
                            is_selected = (x, y) in self._selected_cells
                            act = idx - 1 == ed.active_wild_patch_index
                            if is_selected:
                                ov.fill((60, 180, 255, 150))
                            elif act:
                                ov.fill((90, 240, 160, 120))
                            else:
                                ov.fill((60, 210, 120, 90))
                            ed.screen.blit(ov, (px, py))
                            # Draw the patch index digit when cells are large enough
                            if cp >= 10:
                                digit_surf = ed.font_small.render(str(idx), True, (255, 255, 255))
                                dr = digit_surf.get_rect(center=(px + cp // 2, py + cp // 2))
                                ed.screen.blit(digit_surf, dr)
                            # Bright outline for flood-fill selection
                            if is_selected:
                                pygame.draw.rect(ed.screen, (100, 220, 255), (px, py, cp, cp), 2)
                    pygame.draw.rect(ed.screen, (50, 50, 60), (px, py, cp, cp), 1)
            if ed.show_valid_player_stands_orange:
                pw, ph, off = self._player_stride_params()
                stride_x = max(1, pw)
                stride_y = max(1, ph)
                phase_x = off % stride_x
                for y in range(ed.map_h):
                    for x in range(ed.map_w):
                        if ((x + phase_x) % stride_x) != 0 or (y % stride_y) != 0:
                            continue
                        px = map_rect.x + x * cp - ed.wild_modal_map_off_x
                        py = map_rect.y + y * cp - ed.wild_modal_map_off_y
                        if map_rect.collidepoint(px, py):
                            pygame.draw.rect(ed.screen, (255, 145, 30), (px, py, cp, cp), 1)
        finally:
            ed.screen.set_clip(clip_prev)

    def _draw_patch_column(self) -> None:
        ed = self.ed
        r = self.patch_inner
        lh = ed.font_small.get_linesize() + 4

        # Local / Global tab bar (FEATURE-MAP-058)
        ty_tab = r.y + 18
        self._tab_local_btn = pygame.Rect(r.x + 4, ty_tab, 70, 18)
        self._tab_global_btn = pygame.Rect(self._tab_local_btn.right + 4, ty_tab, 70, 18)
        for rect, tab, lab in (
            (self._tab_local_btn, "local", "Local"),
            (self._tab_global_btn, "global", "Global"),
        ):
            on = self.modal_tab == tab
            pygame.draw.rect(ed.screen, (50, 100, 75) if on else (34, 44, 40), rect)
            ed.screen.blit(
                ed.font_small.render(lab, True, (240, 255, 245) if on else (170, 190, 175)),
                (rect.x + 8, rect.y + 2),
            )

        ty = ty_tab + 24
        if self.modal_tab == "global":
            self._draw_global_section(ty)
        else:
            self._draw_local_section(ty)

    def _draw_local_section(self, ty: int) -> None:
        ed = self.ed
        r = self.patch_inner
        lh = ed.font_small.get_linesize() + 4
        self._patch_row_rects = []
        n = len(ed.wild_patches)
        for j in range(min(n, 8)):
            p = ed.wild_patches[j]
            pid = str(p.get("id", "?"))[:18]
            line = f"{j + 1}. {pid}"
            rr = pygame.Rect(r.x + 6, ty, r.w - 12, lh)
            self._patch_row_rects.append((j, rr))
            if ed.selected_wild_patch_index == j:
                pygame.draw.rect(ed.screen, (40, 90, 70), rr)
            if ed.active_wild_patch_index == j:
                pygame.draw.rect(ed.screen, (120, 220, 160), rr, 1)
            ed.screen.blit(ed.font_small.render(line, True, (230, 245, 235)), (rr.x + 4, ty + 2))
            ty += lh
        ty += 4

        bw = (r.w - 24) // 3
        ed._wild_new_btn = pygame.Rect(r.x + 6, ty, bw, 20)
        ed._wild_delete_btn = pygame.Rect(r.x + 10 + bw, ty, bw, 20)
        ed._wild_merge_btn = pygame.Rect(r.x + 14 + 2 * bw, ty, bw, 20)
        for rect, label in (
            (ed._wild_new_btn, "New"),
            (ed._wild_delete_btn, "Del"),
            (ed._wild_merge_btn, "Merge"),
        ):
            pygame.draw.rect(ed.screen, (42, 72, 58), rect)
            ed.screen.blit(ed.font_small.render(label, True, (230, 245, 235)), (rect.x + 4, rect.y + 3))
        ty += 24

        p = ed._wild_active_patch()
        if p is not None:
            # stepChancePercent typed input box
            step_val = self._edit_buf if self._edit_field == "step" else str(int(p.get("stepChancePercent", 0)))
            ed.screen.blit(ed.font_small.render("Step%:", True, (200, 235, 210)), (r.x + 8, ty))
            box_r = pygame.Rect(r.x + 60, ty, r.w - 68, lh + 4)
            self._edit_rects["step"] = box_r
            focused = self._edit_field == "step"
            pygame.draw.rect(ed.screen, (28, 40, 34), box_r)
            pygame.draw.rect(ed.screen, (120, 200, 150) if focused else (70, 100, 85), box_r, 1)
            disp = f"{step_val}_" if focused else step_val
            ed.screen.blit(
                ed.font_small.render(disp, True, (240, 255, 240)),
                (mtext.field_text_x(box_r), mtext.field_text_y(ed.font_small, box_r)),
            )
            ty += lh + 2

        ty += 4
        self._draw_tier_and_rows(ty, is_global=False)

    def _draw_global_section(self, ty: int) -> None:
        ed = self.ed
        r = self.patch_inner
        lh = ed.font_small.get_linesize() + 4
        ed.screen.blit(
            ed.font_small.render("Species in every patch", True, (200, 235, 210)),
            (r.x + 6, ty),
        )
        ty += lh + 2
        self._draw_tier_and_rows(ty, is_global=True)

    def _draw_tier_and_rows(self, ty: int, is_global: bool) -> None:
        """Draw tier tabs + encounter row list for local patch or global encounters."""
        ed = self.ed
        r = self.patch_inner
        lh = ed.font_small.get_linesize() + 4

        tier_names = ("common", "uncommon", "rare")
        self._tier_tab_rects = {}
        tx = r.x + 6
        for tier in tier_names:
            tw = ed.font_small.size(tier)[0] + 12
            tr = pygame.Rect(tx, ty, tw, lh)
            self._tier_tab_rects[tier] = tr
            on = ed.wild_tier_tab == tier
            pygame.draw.rect(ed.screen, (50, 100, 75) if on else (35, 55, 45), tr)
            ed.screen.blit(
                ed.font_small.render(tier, True, (240, 255, 245) if on else (170, 200, 180)),
                (tr.x + 4, tr.y + 2),
            )
            tx += tw + 4
        ty += lh + 4

        if is_global:
            rows = list(ed.wild_global_encounters.get(ed.wild_tier_tab, []))
            # Local species set for ⚠ conflict indicator
            p = ed._wild_active_patch()
            local_species: set[str] = set()
            if p:
                for row in ed._wild_tier_rows(p):
                    local_species.add(str(row.get("species", "")))
            target_rows = ed.wild_global_encounters.get(ed.wild_tier_tab, [])
        else:
            p = ed._wild_active_patch()
            rows = ed._wild_tier_rows(p) if p else []
            target_rows = rows
            local_species = set()

        self._enc_row_rects = []
        self._global_enc_row_rects = []
        # Keep the step box rect if it was already set this frame
        step_r = self._edit_rects.get("step", pygame.Rect(0, 0, 1, 1))
        self._edit_rects = {"step": step_r}

        max_visible = 8
        for ri, row in enumerate(rows[:max_visible]):
            sp = str(row.get("species", "?"))[:12]
            rr = pygame.Rect(r.x + 8, ty, r.w - 16, lh - 2)
            if is_global:
                self._global_enc_row_rects.append((ri, rr))
                if sp in local_species:
                    # Warn: global species also present locally (local wins at runtime)
                    ed.screen.blit(ed.font_small.render("!", True, (255, 220, 60)), (rr.x, ty))
                if ed.wild_selected_encounter_row == ri:
                    pygame.draw.rect(ed.screen, (55, 95, 75), rr)
                ed.screen.blit(ed.font_small.render(sp, True, (220, 240, 230)), (rr.x + 12, ty))
            else:
                self._enc_row_rects.append((ri, rr))
                if ed.wild_selected_encounter_row == ri:
                    pygame.draw.rect(ed.screen, (55, 95, 75), rr)
                ed.screen.blit(ed.font_small.render(sp, True, (220, 240, 230)), (rr.x + 4, ty))

            # Weight typed input box (FEATURE-MAP-058)
            w_field_id = f"weight_{ri}"
            w_val = row.get("weight", 1)
            w_str = self._edit_buf if self._edit_field == w_field_id else str(w_val)
            focused_w = self._edit_field == w_field_id
            box_w = 36
            wb = pygame.Rect(rr.right - box_w - 2, ty, box_w, lh)
            self._edit_rects[w_field_id] = wb
            pygame.draw.rect(ed.screen, (28, 40, 34), wb)
            pygame.draw.rect(ed.screen, (120, 200, 150) if focused_w else (60, 80, 70), wb, 1)
            disp_w = f"{w_str}_" if focused_w else w_str
            ed.screen.blit(
                ed.font_small.render(disp_w, True, (240, 255, 240)),
                (mtext.field_text_x(wb, 2), mtext.field_text_y(ed.font_small, wb)),
            )
            ty += lh

        ty += 4
        add_btn_r = pygame.Rect(r.x + 6, ty, (r.w - 16) // 2 - 2, 20)
        rem_btn_r = pygame.Rect(add_btn_r.right + 4, ty, (r.w - 16) // 2 - 2, 20)
        if is_global:
            ed._wild_global_add_row_btn = add_btn_r
            ed._wild_global_remove_row_btn = rem_btn_r
        else:
            ed._wild_add_row_btn = add_btn_r
            ed._wild_remove_row_btn = rem_btn_r
        for rect, label in ((add_btn_r, "+ row"), (rem_btn_r, "- row")):
            pygame.draw.rect(ed.screen, (42, 72, 58), rect)
            ed.screen.blit(ed.font_small.render(label, True, (230, 245, 235)), (rect.x + 4, rect.y + 3))

    def _draw_species_column(self) -> None:
        ed = self.ed
        r = self.species_inner
        lh = ed.font_small.get_linesize() + 2
        ty = r.y + 24
        search_r = pygame.Rect(r.x + 6, ty, r.w - 12, lh + 8)
        ty += lh + 12
        ed.wild_modal_species_search_rect = search_r
        pygame.draw.rect(ed.screen, (28, 38, 34), search_r)
        pygame.draw.rect(ed.screen, (120, 200, 150) if self.search_focus else (90, 100, 110), search_r, 1)
        q = self.filter or ""
        hint = f"Search: {q}_" if self.search_focus else (f"Search: {q}" if q else "Search all Pokémon…")
        ed.screen.blit(
            ed.font_small.render(hint, True, (230, 240, 235)),
            (mtext.field_text_x(search_r, 6), mtext.field_text_y(ed.font_small, search_r)),
        )
        list_inner = pygame.Rect(r.x + 6, ty, r.w - 12, r.bottom - ty - 6)
        names = self._species_names()
        vis = max(1, list_inner.h // lh)
        self._species_vis = vis  # expose for handle_wheel clamp (BUG-MAP-062)
        self.species_sel = max(0, min(self.species_sel, max(0, len(names) - 1)))
        # BUG-MAP-062: clamp scroll to valid range instead of resetting to species_sel
        max_scroll = max(0, len(names) - vis)
        self.species_scroll = max(0, min(self.species_scroll, max_scroll))
        # Only auto-scroll DOWN to keep keyboard-selected item visible
        if self.species_sel >= self.species_scroll + vis:
            self.species_scroll = max(0, self.species_sel - vis + 1)
        self._species_hits = []
        clip_prev = ed.screen.get_clip()
        ed.screen.set_clip(list_inner)
        try:
            y = list_inner.y
            for i in range(self.species_scroll, min(len(names), self.species_scroll + vis + 2)):
                if y > list_inner.bottom:
                    break
                sp = names[i]
                star_rr = pygame.Rect(list_inner.x + 2, y, 20, lh - 1)
                row_rr = pygame.Rect(star_rr.right + 2, y, list_inner.w - 24, lh - 1)
                self._species_hits.append((i, row_rr, star_rr))
                if i == self.species_sel:
                    pygame.draw.rect(ed.screen, (45, 90, 70), row_rr)
                starred = sp in ed.wild_species_favorites
                ed.screen.blit(
                    ed.font_small.render("★" if starred else "☆", True, (255, 220, 80) if starred else (120, 125, 140)),
                    (star_rr.x + 2, y),
                )
                ed.screen.blit(ed.font_small.render(sp, True, (245, 255, 248)), (row_rr.x + 4, y))
                y += lh
        finally:
            ed.screen.set_clip(clip_prev)

    # -------------------------------------------------------------------------
    # Apply species
    # -------------------------------------------------------------------------

    def apply_species(self, species: str) -> None:
        ed = self.ed
        if not species:
            return
        if self.modal_tab == "global":
            tier = ed.wild_tier_tab
            rows = ed.wild_global_encounters.setdefault(tier, [])
            ri = ed.wild_selected_encounter_row
            if ri is None:
                ed._undo_checkpoint()
                rows.append({"species": species, "weight": 10})
                self._mark_dirty()
            elif 0 <= ri < len(rows):
                old = str(rows[ri].get("species", ""))
                if old != species:
                    ed._undo_checkpoint()
                    rows[ri]["species"] = species
                    self._mark_dirty()
            return
        p = ed._wild_active_patch()
        if not p:
            return
        rows = ed._wild_tier_rows(p)
        ri = ed.wild_selected_encounter_row
        if ri is None:
            ed._undo_checkpoint()
            rows.append({"species": species, "weight": 10})
            self._mark_dirty()
        elif 0 <= ri < len(rows):
            old = str(rows[ri].get("species", ""))
            if old != species:
                ed._undo_checkpoint()
                rows[ri]["species"] = species
                self._mark_dirty()

    # -------------------------------------------------------------------------
    # Paint (FEATURE-MAP-058: adjacency auto-assign)
    # -------------------------------------------------------------------------

    def paint_cells(self, x0: int, y0: int, x1: int, y1: int, button: int) -> None:
        ed = self.ed
        ax0, ax1 = sorted((x0, x1))
        ay0, ay1 = sorted((y0, y1))
        if self.edit_mode == "patches":
            erase = ed.eraser_mode or button == 3
            # Process left→right, top→bottom so earlier cells in the stroke can
            # serve as valid neighbors for later cells in the same drag.
            for wy in range(ay0, ay1 + 1):
                for wx in range(ax0, ax1 + 1):
                    sx, sy = self.snap_cell(wx, wy)
                    if not (0 <= sx < ed.map_w and 0 <= sy < ed.map_h):
                        continue
                    if erase:
                        ed.wild_encounter[sy][sx] = 0
                    else:
                        neighbor = self._neighbor_patch_index(sx, sy)
                        if neighbor is not None:
                            val = neighbor
                        else:
                            val = self._create_new_patch_for_cell()
                        ed.wild_encounter[sy][sx] = val
        else:
            erase = ed.eraser_mode or button == 3
            for wy in range(ay0, ay1 + 1):
                for wx in range(ax0, ax1 + 1):
                    if 0 <= wx < ed.map_w and 0 <= wy < ed.map_h:
                        sx, sy = self.snap_cell(wx, wy)
                        if ed.edit_mode == "paint":
                            ed.apply_brush_at(sx, sy, erase)
                        elif ed.edit_mode == "walk":
                            ed.walk[sy][sx] = 0 if erase else 1
                            ed._invalidate_valid_stands_cache()

    # -------------------------------------------------------------------------
    # Input handlers
    # -------------------------------------------------------------------------

    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        ed = self.ed

        # Commit any pending edit when clicking anywhere other than an edit box
        if self._edit_field is not None:
            clicked_edit = any(r.collidepoint(mx, my) for r in self._edit_rects.values())
            if not clicked_edit:
                self._commit_edit()

        if self.close_btn.collidepoint(mx, my) and button == 1:
            self.close_modal()
            return True

        # FEATURE-MAP-064: Back and Help buttons
        if self._back_btn.collidepoint(mx, my) and button == 1:
            self.close_modal()
            ed.events_launcher_modal.open_modal()
            return True
        if self._help_btn.collidepoint(mx, my) and button == 1:
            ed._open_help_overlay(tab="events", back_to="wild")
            return True
        if self._main_map_btn.collidepoint(mx, my) and button == 1:
            self.close_modal(switch_to_canvas=True)
            return True

        if button == 1:
            for m, rr in self._map_rows:
                if rr.collidepoint(mx, my):
                    self.sel_map_id = m
                    ed.wild_modal_switch_map(m)
                    self._map_zoom = None
                    return True

        # FEATURE-MAP-059/060: resize grips and title-bar drag-to-move
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

        # FEATURE-MAP-059: zoom buttons
        if self._zoom_in_btn.collidepoint(mx, my) and button == 1:
            self._map_zoom = min(64, self._cell_px() + 4)
            return True
        if self._zoom_out_btn.collidepoint(mx, my) and button == 1:
            self._map_zoom = max(4, self._cell_px() - 4)
            return True
        if self._zoom_fit_btn.collidepoint(mx, my) and button == 1:
            self._map_zoom = None
            return True

        if self.mode_patches_btn.collidepoint(mx, my) and button == 1:
            self.edit_mode = "patches"
            return True
        if self.mode_map_btn.collidepoint(mx, my) and button == 1:
            self.edit_mode = "map"
            return True

        # Local / Global tab bar
        if self._tab_local_btn.collidepoint(mx, my) and button == 1:
            self._commit_edit()
            self.modal_tab = "local"
            return True
        if self._tab_global_btn.collidepoint(mx, my) and button == 1:
            self._commit_edit()
            self.modal_tab = "global"
            return True

        if ed.wild_modal_species_search_rect.collidepoint(mx, my) and button == 1:
            self.search_focus = True
            return True
        if button == 1:
            self.search_focus = False

        # Species list
        for idx, row_rr, star_rr in self._species_hits:
            if star_rr.collidepoint(mx, my) and button == 1:
                names = self._species_names()
                if 0 <= idx < len(names):
                    ed._toggle_wild_species_favorite(names[idx])
                return True
            if row_rr.collidepoint(mx, my) and button == 1:
                names = self._species_names()
                if 0 <= idx < len(names):
                    self.species_sel = idx
                    self.apply_species(names[idx])
                return True

        # Tier tabs
        for tier, tr in self._tier_tab_rects.items():
            if tr.collidepoint(mx, my) and button == 1:
                ed.wild_tier_tab = tier
                return True

        # Encounter row selection (local)
        for ri, rr in self._enc_row_rects:
            if rr.collidepoint(mx, my) and button == 1:
                ed.wild_selected_encounter_row = ri
                return True

        # Encounter row selection (global)
        for ri, rr in self._global_enc_row_rects:
            if rr.collidepoint(mx, my) and button == 1:
                ed.wild_selected_encounter_row = ri
                return True

        # Patch list rows (local tab)
        for j, rr in self._patch_row_rects:
            if rr.collidepoint(mx, my) and button == 1:
                ed.selected_wild_patch_index = j
                ed.active_wild_patch_index = j
                return True

        # Typed input boxes — focus on click
        for field_id, rect in self._edit_rects.items():
            if rect.collidepoint(mx, my) and button == 1:
                if self._edit_field != field_id:
                    self._commit_edit()
                    if field_id == "step":
                        p = ed._wild_active_patch()
                        self._edit_buf = str(int(p.get("stepChancePercent", 0))) if p else "0"
                    elif field_id.startswith("weight_"):
                        try:
                            ri = int(field_id[len("weight_"):])
                        except ValueError:
                            ri = -1
                        if self.modal_tab == "global":
                            rows = ed.wild_global_encounters.get(ed.wild_tier_tab, [])
                        else:
                            p = ed._wild_active_patch()
                            rows = ed._wild_tier_rows(p) if p else []
                        self._edit_buf = str(rows[ri].get("weight", 1)) if 0 <= ri < len(rows) else "1"
                    self._edit_field = field_id
                return True

        # Mini-map click in patch mode: flood-fill select or start painting
        cell = self.cell_at_pixel(mx, my)
        if cell is not None and self.edit_mode == "patches":
            cx, cy = cell
            idx = ed.wild_encounter[cy][cx] if (0 <= cx < ed.map_w and 0 <= cy < ed.map_h) else 0
            if button == 1:
                if idx > 0:
                    # Select the contiguous component
                    self._selected_cells = self._flood_fill_component(cx, cy)
                    ed.selected_wild_patch_index = idx - 1
                    ed.active_wild_patch_index = idx - 1
                else:
                    # Start painting on empty tile
                    self._selected_cells = set()
                    self.map_drag_start = cell
                    self.map_paint_current = cell
            elif button == 3:
                # Right-click erase always starts drag regardless of tile content
                self._selected_cells = set()
                self.map_drag_start = cell
                self.map_paint_current = cell
            return True
        if cell is not None and self.edit_mode == "map" and button in (1, 3):
            self.map_drag_start = cell
            self.map_paint_current = cell
            return True

        # +/- row buttons (local)
        if getattr(ed, "_wild_add_row_btn", None) and ed._wild_add_row_btn.collidepoint(mx, my) and button == 1:
            p = ed._wild_active_patch()
            if p:
                ed._undo_checkpoint()
                names = self._species_names()
                species = (
                    names[self.species_sel]
                    if names
                    else wild_species_default_for_new_row(ed._pokemon_species_keys(), ed.wild_species_favorites)
                )
                ed._wild_tier_rows(p).append({"species": species, "weight": 10})
                self._mark_dirty()
            return True
        if getattr(ed, "_wild_remove_row_btn", None) and ed._wild_remove_row_btn.collidepoint(mx, my) and button == 1:
            p = ed._wild_active_patch()
            if p:
                rows = ed._wild_tier_rows(p)
                ri = ed.wild_selected_encounter_row
                if ri is not None and 0 <= ri < len(rows):
                    ed._undo_checkpoint()
                    rows.pop(ri)
                    ed.wild_selected_encounter_row = max(0, ri - 1) if rows else None
                    self._mark_dirty()
            return True

        # +/- row buttons (global)
        if getattr(ed, "_wild_global_add_row_btn", None) and ed._wild_global_add_row_btn.collidepoint(mx, my) and button == 1:
            ed._undo_checkpoint()
            tier = ed.wild_tier_tab
            rows = ed.wild_global_encounters.setdefault(tier, [])
            names = self._species_names()
            species = (
                names[self.species_sel]
                if names
                else wild_species_default_for_new_row(ed._pokemon_species_keys(), ed.wild_species_favorites)
            )
            rows.append({"species": species, "weight": 10})
            self._mark_dirty()
            return True
        if getattr(ed, "_wild_global_remove_row_btn", None) and ed._wild_global_remove_row_btn.collidepoint(mx, my) and button == 1:
            tier = ed.wild_tier_tab
            rows = ed.wild_global_encounters.get(tier, [])
            ri = ed.wild_selected_encounter_row
            if ri is not None and 0 <= ri < len(rows):
                ed._undo_checkpoint()
                rows.pop(ri)
                ed.wild_selected_encounter_row = max(0, ri - 1) if rows else None
                self._mark_dirty()
            return True

        # Patch panel legacy buttons (New/Del/Merge) via existing handler
        if self.patch_inner.collidepoint(mx, my) and button == 1:
            if ed._wild_handle_panel_click(mx, my):
                self._mark_dirty()
                return True

        if not self.panel_rect.collidepoint(mx, my) and button == 1:
            self.close_modal()
            return True
        return True

    def handle_mouse_up(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        # FEATURE-MAP-059/060: end any drag mode regardless of button
        self._drag_mode = "none"
        if button not in (1, 3):
            return True
        if self.map_drag_start and self.map_paint_current:
            self.ed._undo_checkpoint()
            self.paint_cells(
                self.map_drag_start[0],
                self.map_drag_start[1],
                self.map_paint_current[0],
                self.map_paint_current[1],
                button,
            )
            self._mark_dirty()
        self.map_drag_start = None
        self.map_paint_current = None
        return True

    def handle_mouse_motion(self, mx: int, my: int) -> bool:
        if not self.open:
            return False
        # FEATURE-MAP-059/060: resize and move drags
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
            # Clamping to canvas happens in draw()
            self._panel_override = pygame.Rect(mx - ox, my - oy,
                                               self.panel_rect.w, self.panel_rect.h)
            return True
        if self.map_drag_start:
            c = self.cell_at_pixel(mx, my)
            if c:
                self.map_paint_current = c
        return True

    def handle_wheel(self, mx: int, my: int, y: int) -> bool:
        if not self.open:
            return False
        ed = self.ed
        if self.species_inner.collidepoint(mx, my):
            # BUG-MAP-062: clamp to valid range using last-known vis count
            names = self._species_names()
            max_sc = max(0, len(names) - self._species_vis)
            self.species_scroll = max(0, min(max_sc, self.species_scroll - y))
            return True
        if self._map_view_rect.collidepoint(mx, my):
            mods = pygame.key.get_mods()
            if mods & pygame.KMOD_CTRL:
                # FEATURE-MAP-059: Ctrl+scroll zooms the mini-map
                if y > 0:
                    self._map_zoom = min(64, self._cell_px() + 4)
                elif y < 0:
                    self._map_zoom = max(4, self._cell_px() - 4)
            else:
                # BUG-MAP-061: plain scroll only pans Y; Shift+scroll pans X
                cp = self._cell_px()
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_SHIFT:
                    total_w = ed.map_w * cp
                    ed.wild_modal_map_off_x = max(
                        0,
                        min(max(0, total_w - self._map_view_rect.w), ed.wild_modal_map_off_x - y * cp),
                    )
                else:
                    total_h = ed.map_h * cp
                    ed.wild_modal_map_off_y = max(
                        0,
                        min(max(0, total_h - self._map_view_rect.h), ed.wild_modal_map_off_y - y * cp),
                    )
            return True
        return True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        enter_keys = (pygame.K_RETURN, getattr(pygame, "K_KP_ENTER", pygame.K_RETURN))

        # Inline text editing takes priority over all other key handling
        if self._edit_field is not None:
            if event.key == pygame.K_ESCAPE:
                self._edit_field = None
                self._edit_buf = ""
                return True
            if event.key in enter_keys:
                self._commit_edit()
                return True
            if event.key == pygame.K_BACKSPACE:
                self._edit_buf = self._edit_buf[:-1]
                return True
            ch = event.unicode
            if ch and ch.isdigit() and len(self._edit_buf) < 6:
                self._edit_buf += ch
                return True
            return True

        names = self._species_names()
        if event.key == pygame.K_ESCAPE:
            self.close_modal()
            return True
        if event.key in enter_keys and names:
            self.apply_species(names[max(0, min(self.species_sel, len(names) - 1))])
            return True
        if self.search_focus:
            if event.key == pygame.K_BACKSPACE:
                self.filter = self.filter[:-1]
                self.species_sel = 0
                self.species_scroll = 0
                return True
            ch = event.unicode
            if ch and ch.isprintable() and len(self.filter) < 48:
                self.filter += ch
                self.species_sel = 0
                self.species_scroll = 0
                return True
        if event.key == pygame.K_UP and names:
            self.species_sel = max(0, self.species_sel - 1)
            return True
        if event.key == pygame.K_DOWN and names:
            self.species_sel = min(len(names) - 1, self.species_sel + 1)
            return True
        return True

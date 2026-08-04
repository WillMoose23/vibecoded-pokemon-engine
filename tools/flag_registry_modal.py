"""FEATURE-MAP-073: flag / variable registry modal + shared registry helpers.

The registry (src/maps/scripts/flag_registry.json) declares the named persistent flags and the
scratch variables used by event scripts, with initial values and descriptions. The C++ engine
reads the flags section at startup to seed GameState defaults; the editor uses both sections to
populate variable pickers and to keep names consistent.

This module exposes:
  - load_registry() / save_registry() / registry mutation helpers (used by other modals too).
  - EventFlagRegistryModal: a UI-Standard modal to declare/list/rename flags + variables.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pygame

import modal_text as mtext

if TYPE_CHECKING:
    from map_editor import MapEditor

_ROOT = Path(__file__).resolve().parents[1]
_REGISTRY_PATH = _ROOT / "src" / "maps" / "scripts" / "flag_registry.json"
VAR_TYPES = ("int", "string", "bool")

_C_PANEL = (20, 24, 20)
_C_BODY = (16, 20, 16)
_C_SUBPANEL = (26, 31, 28)
_C_BORDER = (80, 180, 120)
_C_BORDER_DIM = (60, 78, 66)
_C_TEXT = (210, 224, 214)
_C_TEXT_DIM = (140, 158, 146)
_C_HEAD = (180, 255, 200)
_C_SEL = (54, 92, 70)


# ---------------------------------------------------------------------------
# Shared registry helpers
# ---------------------------------------------------------------------------

def load_registry() -> dict[str, Any]:
    reg: dict[str, Any] = {"version": 1, "flags": [], "variables": []}
    if _REGISTRY_PATH.is_file():
        try:
            with _REGISTRY_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if isinstance(data.get("flags"), list):
                    reg["flags"] = [f for f in data["flags"] if isinstance(f, dict)]
                if isinstance(data.get("variables"), list):
                    reg["variables"] = [v for v in data["variables"] if isinstance(v, dict)]
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return reg


def save_registry(reg: dict[str, Any]) -> bool:
    out = {
        "version": 1,
        "flags": [
            {"name": str(f.get("name", "")), "initial": bool(f.get("initial", False)),
             "description": str(f.get("description", ""))}
            for f in reg.get("flags", []) if str(f.get("name", "")).strip()
        ],
        "variables": [
            {"name": str(v.get("name", "")), "type": str(v.get("type", "int")),
             "initial": v.get("initial", 0), "description": str(v.get("description", ""))}
            for v in reg.get("variables", []) if str(v.get("name", "")).strip()
        ],
    }
    try:
        _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _REGISTRY_PATH.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
            f.write("\n")
        tmp.replace(_REGISTRY_PATH)
        return True
    except OSError:
        return False


def flag_names(reg: dict[str, Any] | None = None) -> list[str]:
    reg = reg or load_registry()
    return [str(f.get("name", "")) for f in reg.get("flags", []) if str(f.get("name", "")).strip()]


def variable_names(reg: dict[str, Any] | None = None) -> list[str]:
    reg = reg or load_registry()
    return [str(v.get("name", "")) for v in reg.get("variables", []) if str(v.get("name", "")).strip()]


def _sanitize_name(raw: str) -> str:
    s = "".join(c if c.isalnum() or c in "._-" else "_" for c in raw.strip())[:64]
    return s.strip("._-")


def ensure_flag(name: str, initial: bool = False) -> bool:
    name = _sanitize_name(name)
    if not name:
        return False
    reg = load_registry()
    if name in flag_names(reg):
        return True
    reg["flags"].append({"name": name, "initial": initial, "description": ""})
    return save_registry(reg)


def ensure_variable(name: str, vtype: str = "int") -> bool:
    name = _sanitize_name(name)
    if not name:
        return False
    if vtype not in VAR_TYPES:
        vtype = "int"
    reg = load_registry()
    if name in variable_names(reg):
        return True
    initial: Any = 0 if vtype == "int" else ("" if vtype == "string" else False)
    reg["variables"].append({"name": name, "type": vtype, "initial": initial, "description": ""})
    return save_registry(reg)


# ---------------------------------------------------------------------------
# Modal
# ---------------------------------------------------------------------------

class EventFlagRegistryModal:
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

        self.reg: dict[str, Any] = {"flags": [], "variables": []}
        self.tab = "flags"  # "flags" | "variables"
        self.sel_index: int | None = None
        self.scroll = 0
        self.focus: str | None = None  # "name" | "initial" | "new"
        self.new_buf = ""
        self._tab_rects: list[tuple[str, pygame.Rect]] = []
        self._rows: list[tuple[int, pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]] = []
        self._new_btn = pygame.Rect(0, 0, 1, 1)
        self._save_btn = pygame.Rect(0, 0, 1, 1)
        self._new_rect = pygame.Rect(0, 0, 1, 1)
        self.edit_field: tuple[int, str] | None = None
        self.edit_buf = ""

    def open_modal(self) -> None:
        self.open = True
        self.reg = load_registry()
        self.tab = "flags"
        self.sel_index = None
        self.scroll = 0
        self.focus = None
        self.new_buf = ""
        self.edit_field = None
        self._drag_mode = "none"

    def close_modal(self) -> None:
        self._commit_edit()
        save_registry(self.reg)
        self.open = False

    def _entries(self) -> list[dict]:
        return self.reg["flags"] if self.tab == "flags" else self.reg["variables"]

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
            pw = min(max(720, canvas.w - 200), canvas.w - 24)
            ph = min(max(520, canvas.h - 140), canvas.h - 24)
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
        ed.screen.blit(ed.font.render("Flag / Variable Registry", True, _C_HEAD), (panel.x + 12, panel.y + 7))
        self.close_btn = pygame.Rect(panel.right - 72, panel.y + 5, 60, 24)
        _btn(ed, self.close_btn, "Close", (72, 48, 48), (245, 240, 240))
        pygame.draw.line(ed.screen, _C_BORDER_DIM, (panel.x, panel.y + head_h),
                         (panel.right, panel.y + head_h), 1)

        body = pygame.Rect(panel.x + 8, panel.y + head_h + 6, panel.w - 16, panel.h - head_h - 16)
        # Tabs
        self._tab_rects = []
        for i, (key, lbl) in enumerate((("flags", "Flags"), ("variables", "Variables"))):
            tr = pygame.Rect(body.x + i * 110, body.y, 104, 22)
            on = self.tab == key
            pygame.draw.rect(ed.screen, _C_SEL if on else (32, 40, 34), tr)
            pygame.draw.rect(ed.screen, _C_BORDER if on else _C_BORDER_DIM, tr, 1)
            ed.screen.blit(ed.font_small.render(lbl, True, _C_HEAD if on else _C_TEXT_DIM), (tr.x + 8, tr.y + 3))
            self._tab_rects.append((key, tr))
        # New entry row
        new_y = body.y + 28
        self._new_rect = pygame.Rect(body.x, new_y, body.w - 200, 22)
        _textbox(ed, self._new_rect, self.new_buf, self.focus == "new",
                 "new flag name" if self.tab == "flags" else "new variable name")
        self._new_btn = pygame.Rect(self._new_rect.right + 6, new_y, 90, 22)
        _btn(ed, self._new_btn, "Add", (40, 70, 50), _C_HEAD)
        self._save_btn = pygame.Rect(self._new_btn.right + 6, new_y, 90, 22)
        _btn(ed, self._save_btn, "Save", (50, 70, 90), (200, 225, 245))

        list_rect = pygame.Rect(body.x, new_y + 28, body.w, body.bottom - (new_y + 28))
        self._draw_list(list_rect)

        self._resize_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(ed.screen, (90, 160, 120), [
            (panel.right - 2, panel.bottom - 14), (panel.right - 2, panel.bottom - 2),
            (panel.right - 14, panel.bottom - 2)])
        self._resize_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
        pygame.draw.polygon(ed.screen, (90, 160, 120), [
            (panel.x + 2, panel.bottom - 14), (panel.x + 2, panel.bottom - 2),
            (panel.x + 14, panel.bottom - 2)])

    def _draw_list(self, r: pygame.Rect) -> None:
        ed = self.ed
        pygame.draw.rect(ed.screen, _C_SUBPANEL, r)
        pygame.draw.rect(ed.screen, _C_BORDER_DIM, r, 1)
        entries = self._entries()
        fh = mtext.form_field_h(ed.font_small)
        rh = fh + 8
        self.scroll = max(0, min(self.scroll, max(0, len(entries) * rh - r.h + 4)))
        prev = ed.screen.get_clip()
        ed.screen.set_clip(r)
        y = r.y + 2 - self.scroll
        self._rows = []
        for i, e in enumerate(entries):
            row = pygame.Rect(r.x + 2, y, r.w - 4, rh - 2)
            if row.bottom > r.y and row.top < r.bottom:
                if i == self.sel_index:
                    pygame.draw.rect(ed.screen, _C_SEL, row)
                name = str(e.get("name", ""))
                field_y = row.y + (rh - 2 - fh) // 2
                name_rect = pygame.Rect(row.x + 4, field_y, 200, fh)
                _field(ed, name_rect, self._fv(i, "name", name), self.edit_field == (i, "name"))
                # initial value
                init_rect = pygame.Rect(name_rect.right + 8, field_y, 120, fh)
                if self.tab == "flags":
                    cur = "true" if e.get("initial") else "false"
                    _field(ed, init_rect, cur, False)
                    type_rect = pygame.Rect(init_rect.right + 8, field_y, 0, 0)
                else:
                    init_val = str(e.get("initial", ""))
                    _field(ed, init_rect, self._fv(i, "initial", init_val), self.edit_field == (i, "initial"))
                    type_rect = pygame.Rect(init_rect.right + 8, field_y, 80, fh)
                    _field(ed, type_rect, str(e.get("type", "int")), False)
                del_rect = pygame.Rect(row.right - 26, field_y, 22, fh)
                _btn(ed, del_rect, "\u2715", (80, 44, 44), _C_TEXT)
                self._rows.append((i, name_rect, init_rect, type_rect, del_rect))
            y += rh
        ed.screen.set_clip(prev)

    def _fv(self, i: int, key: str, fallback: str) -> str:
        if self.edit_field == (i, key):
            return self.edit_buf
        return fallback

    # ------------------------------------------------------------------
    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        if button == 1 and self.close_btn.collidepoint(mx, my):
            self.close_modal()
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
        for key, tr in self._tab_rects:
            if tr.collidepoint(mx, my) and button == 1:
                self._commit_edit()
                self.tab = key
                self.sel_index = None
                self.scroll = 0
                return True
        if button == 1 and self._new_rect.collidepoint(mx, my):
            self.focus = "new"
            return True
        if button == 1 and self._new_btn.collidepoint(mx, my):
            self._add_new()
            return True
        if button == 1 and self._save_btn.collidepoint(mx, my):
            self._commit_edit()
            if save_registry(self.reg):
                self.ed.set_status("Registry saved.", kind="ok")
            return True
        for i, name_rect, init_rect, type_rect, del_rect in self._rows:
            if del_rect.collidepoint(mx, my) and button == 1:
                self._commit_edit()
                self._entries().pop(i)
                self.sel_index = None
                return True
            if name_rect.collidepoint(mx, my) and button == 1:
                self._begin_edit(i, "name")
                return True
            if self.tab == "flags" and init_rect.collidepoint(mx, my) and button == 1:
                e = self._entries()[i]
                e["initial"] = not bool(e.get("initial"))
                return True
            if self.tab == "variables" and init_rect.collidepoint(mx, my) and button == 1:
                self._begin_edit(i, "initial")
                return True
            if self.tab == "variables" and type_rect.collidepoint(mx, my) and button == 1:
                e = self._entries()[i]
                cur = str(e.get("type", "int"))
                e["type"] = VAR_TYPES[(VAR_TYPES.index(cur) + 1) % len(VAR_TYPES)] if cur in VAR_TYPES else "int"
                return True
        self._commit_edit()
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
            new_x = min(mx, right - 560)
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
        self.scroll = max(0, self.scroll - y * 3 * (mtext.form_field_h(self.ed.font_small) + 8))
        return True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        if self.focus == "new":
            if event.key == pygame.K_ESCAPE:
                self.focus = None
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._add_new()
            elif event.key == pygame.K_BACKSPACE:
                self.new_buf = self.new_buf[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.new_buf += event.unicode
            return True
        if self.edit_field is not None:
            if event.key == pygame.K_ESCAPE:
                self.edit_field = None
                self.edit_buf = ""
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit_edit()
            elif event.key == pygame.K_BACKSPACE:
                self.edit_buf = self.edit_buf[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.edit_buf += event.unicode
            return True
        if event.key == pygame.K_ESCAPE:
            self.close_modal()
            return True
        return True

    # ------------------------------------------------------------------
    def _add_new(self) -> None:
        name = _sanitize_name(self.new_buf)
        self.new_buf = ""
        self.focus = None
        if not name:
            self.ed.set_status("Enter a name first.", kind="err")
            return
        entries = self._entries()
        if any(str(e.get("name", "")) == name for e in entries):
            self.ed.set_status(f"'{name}' already exists.", kind="err")
            return
        if self.tab == "flags":
            entries.append({"name": name, "initial": False, "description": ""})
        else:
            entries.append({"name": name, "type": "int", "initial": 0, "description": ""})
        self.sel_index = len(entries) - 1

    def _begin_edit(self, i: int, key: str) -> None:
        self._commit_edit()
        entries = self._entries()
        if not (0 <= i < len(entries)):
            return
        self.sel_index = i
        self.edit_field = (i, key)
        self.edit_buf = str(entries[i].get(key, ""))

    def _commit_edit(self) -> None:
        if self.edit_field is None:
            return
        i, key = self.edit_field
        entries = self._entries()
        if 0 <= i < len(entries):
            if key == "name":
                nm = _sanitize_name(self.edit_buf)
                if nm:
                    entries[i]["name"] = nm
            elif key == "initial":
                e = entries[i]
                vtype = str(e.get("type", "int"))
                if vtype == "int":
                    try:
                        e["initial"] = int(self.edit_buf)
                    except ValueError:
                        e["initial"] = 0
                elif vtype == "bool":
                    e["initial"] = self.edit_buf.strip().lower() in ("1", "true", "yes")
                else:
                    e["initial"] = self.edit_buf
        self.edit_field = None
        self.edit_buf = ""


def _btn(ed, rect, label, bg, fg) -> None:
    pygame.draw.rect(ed.screen, bg, rect)
    pygame.draw.rect(ed.screen, _C_BORDER_DIM, rect, 1)
    ts = ed.font_small.render(label, True, fg)
    ed.screen.blit(ts, (rect.x + max(4, (rect.w - ts.get_width()) // 2),
                        rect.y + (rect.h - ts.get_height()) // 2))


def _field(ed, rect, text, focused) -> None:
    pygame.draw.rect(ed.screen, (44, 52, 46) if focused else (24, 30, 26), rect)
    pygame.draw.rect(ed.screen, _C_BORDER if focused else _C_BORDER_DIM, rect, 1)
    shown = text + ("|" if focused else "")
    clipped = mtext.truncate_to_width(ed.font_small, shown, max(8, rect.w - 8))
    ed.screen.blit(
        ed.font_small.render(clipped, True, _C_TEXT),
        (mtext.field_text_x(rect), mtext.field_text_y(ed.font_small, rect)),
    )


def _textbox(ed, rect, text, focused, placeholder) -> None:
    pygame.draw.rect(ed.screen, (24, 30, 26), rect)
    pygame.draw.rect(ed.screen, _C_BORDER if focused else _C_BORDER_DIM, rect, 1)
    if text:
        shown = text + ("|" if focused else "")
        ed.screen.blit(
            ed.font_small.render(shown, True, _C_TEXT),
            (mtext.field_text_x(rect, 5), mtext.field_text_y(ed.font_small, rect)),
        )
    else:
        ph = ("|" if focused else "") + placeholder
        ed.screen.blit(
            ed.font_small.render(ph, True, _C_TEXT_DIM),
            (mtext.field_text_x(rect, 5), mtext.field_text_y(ed.font_small, rect)),
        )

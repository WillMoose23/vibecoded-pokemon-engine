"""FEATURE-MAP-088: Battle Editor — editable trainer battle library definitions.

Manages src/maps/scripts/_library/battles/*.json. Each battle defines music,
background, outcome mode, trainers (1-2) with party (1-6 Pokemon each).
Phase 5: full editable UI (no read-only JSON footnote).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pygame

import event_script_schema as ess
import modal_text as mtext

if TYPE_CHECKING:
    from map_editor import MapEditor

_ROOT = Path(__file__).resolve().parents[1]
_BATTLES_DIR = _ROOT / "src" / "maps" / "scripts" / "_library" / "battles"

_C_PANEL = (24, 20, 28)
_C_BORDER = (170, 140, 200)
_C_TEXT = (224, 216, 232)
_C_HEAD = (228, 206, 250)
_C_SEL = (78, 60, 96)

_OUTCOME_MODES = (
    ("normal", "Normal"),
    ("scripted_win", "Scripted win"),
    ("scripted_loss", "Scripted loss"),
)


def _default_battle(bid: str) -> dict:
    return {
        "id": bid,
        "music": "",
        "background": "example",
        "outcomeMode": "normal",
        "scriptedLossTurns": 0,
        "trainers": [{"party": [{"species": "Pidgey", "level": 5}]}],
    }


class BattleEditorModal:
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
        self._save_btn = pygame.Rect(0, 0, 1, 1)
        self._new_btn = pygame.Rect(0, 0, 1, 1)
        self.battle_ids: list[str] = []
        self.sel_id: str | None = None
        self.data: dict[str, Any] = _default_battle("new_battle")
        self.dirty = False
        self._list_rows: list[tuple[str, pygame.Rect]] = []
        self._bg_ids: list[str] = []
        self._audio_stems: list[str] = []
        self._species: list[str] = []
        self.focus: str | None = None
        self.edit_buf = ""
        self.sel_trainer = 0
        self.sel_mon = 0
        self.detail_scroll = 0
        self._detail_body = pygame.Rect(0, 0, 1, 1)
        self._detail_content_h = 0
        self._field_rects: dict[str, pygame.Rect] = {}
        self._pick_rects: dict[str, pygame.Rect] = {}
        self._mon_rects: list[tuple[int, int, pygame.Rect, pygame.Rect, pygame.Rect]] = []
        self._btn_rects: list[tuple[str, pygame.Rect]] = []
        self.dropdown: dict | None = None

    def open_modal(self) -> None:
        self.open = True
        self._drag_mode = "none"
        self.dropdown = None
        self.focus = None
        _BATTLES_DIR.mkdir(parents=True, exist_ok=True)
        self.battle_ids = ess.list_library_battle_names()
        self._bg_ids = ess.list_battle_background_ids()
        self._audio_stems = self.ed.list_audio_track_stems()
        self._species = self.ed._pokemon_species_keys()
        if not self.sel_id or self.sel_id not in self.battle_ids:
            self.sel_id = self.battle_ids[0] if self.battle_ids else None
        if self.sel_id:
            self._load_battle(self.sel_id)
        else:
            self.data = _default_battle("new_battle")
            self.dirty = False
        self.sel_trainer = 0
        self.sel_mon = 0
        self.detail_scroll = 0

    def close_modal(self) -> None:
        if self.dirty and self.sel_id:
            self._save_current()
        self.open = False
        self.dropdown = None

    def _battle_path(self, bid: str) -> Path:
        return _BATTLES_DIR / f"{bid}.json"

    def _load_battle(self, bid: str) -> None:
        p = self._battle_path(bid)
        if p.is_file():
            try:
                with open(p, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    self.data = ess.normalize_battle_def(raw, bid)
                    self.sel_id = bid
                    self.dirty = False
                    self.sel_trainer = 0
                    self.sel_mon = 0
                    return
            except (OSError, json.JSONDecodeError, TypeError):
                pass
        self.data = _default_battle(bid)
        self.sel_id = bid
        self.dirty = False

    def _save_current(self) -> bool:
        self._commit_field()
        self.data = ess.normalize_battle_def(self.data, str(self.data.get("id") or self.sel_id or "battle"))
        bid = str(self.data.get("id"))
        p = self._battle_path(bid)
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
                f.write("\n")
        except OSError:
            self.ed.set_status("Failed to save battle.", kind="err")
            return False
        if bid not in self.battle_ids:
            self.battle_ids = sorted(set(self.battle_ids + [bid]))
        self.sel_id = bid
        self.dirty = False
        self.ed.set_status(f"Saved battle '{bid}'.", kind="ok")
        return True

    def _trainers(self) -> list[dict]:
        tr = self.data.get("trainers")
        if not isinstance(tr, list):
            tr = [{"party": [{"species": "Pidgey", "level": 5}]}]
            self.data["trainers"] = tr
        return tr

    def _party(self, ti: int) -> list[dict]:
        tr = self._trainers()
        if not (0 <= ti < len(tr)):
            return []
        party = tr[ti].get("party")
        if not isinstance(party, list):
            party = [{"species": "Pidgey", "level": 5}]
            tr[ti]["party"] = party
        return party

    def _commit_field(self) -> None:
        if self.focus is None:
            return
        key = self.focus
        if key == "id":
            self.data["id"] = ess.sanitize_battle_id(self.edit_buf)
        elif key == "scriptedLossTurns":
            try:
                self.data["scriptedLossTurns"] = max(0, int(self.edit_buf))
            except ValueError:
                self.data["scriptedLossTurns"] = 0
        elif key.startswith("mon:"):
            parts = key.split(":")
            if len(parts) == 4:
                ti, pi, field = int(parts[1]), int(parts[2]), parts[3]
                party = self._party(ti)
                if 0 <= pi < len(party):
                    if field == "level":
                        try:
                            party[pi]["level"] = max(1, min(100, int(self.edit_buf)))
                        except ValueError:
                            party[pi]["level"] = 5
        self.focus = None
        self.edit_buf = ""
        self.dirty = True

    def _cycle_outcome(self) -> None:
        cur = str(self.data.get("outcomeMode") or "normal")
        modes = [m[0] for m in _OUTCOME_MODES]
        try:
            i = modes.index(cur)
        except ValueError:
            i = 0
        self.data["outcomeMode"] = modes[(i + 1) % len(modes)]
        self.dirty = True

    def _add_trainer(self) -> None:
        tr = self._trainers()
        if len(tr) >= 2:
            return
        tr.append({"party": [{"species": "Pidgey", "level": 5}]})
        self.sel_trainer = len(tr) - 1
        self.sel_mon = 0
        self.dirty = True

    def _remove_trainer(self) -> None:
        tr = self._trainers()
        if len(tr) <= 1:
            return
        tr.pop(self.sel_trainer)
        self.sel_trainer = min(self.sel_trainer, len(tr) - 1)
        self.sel_mon = 0
        self.dirty = True

    def _add_mon(self, ti: int) -> None:
        party = self._party(ti)
        if len(party) >= 6:
            return
        party.append({"species": "Pidgey", "level": 5})
        self.sel_trainer = ti
        self.sel_mon = len(party) - 1
        self.dirty = True

    def _remove_mon(self, ti: int, pi: int) -> None:
        party = self._party(ti)
        if len(party) <= 1 or not (0 <= pi < len(party)):
            return
        party.pop(pi)
        if self.sel_trainer == ti:
            self.sel_mon = min(self.sel_mon, len(party) - 1)
        self.dirty = True

    def _adjust_level(self, ti: int, pi: int, delta: int) -> None:
        party = self._party(ti)
        if 0 <= pi < len(party):
            lv = int(party[pi].get("level", 5))
            party[pi]["level"] = max(1, min(100, lv + delta))
            self.dirty = True

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
            panel = pygame.Rect(0, 0, min(960, canvas.w - 24), min(640, canvas.h - 24))
            panel.center = canvas.center
        panel.w = max(640, min(panel.w, canvas.w - 8))
        panel.h = max(480, min(panel.h, canvas.h - 8))
        panel.x = max(canvas.x + 4, min(panel.x, canvas.right - panel.w - 4))
        panel.y = max(canvas.y + 4, min(panel.y, canvas.bottom - panel.h - 4))
        self.panel_rect = panel
        head_h = 36
        pygame.draw.rect(ed.screen, _C_PANEL, panel)
        pygame.draw.rect(ed.screen, _C_BORDER, panel, 2)
        self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 280, head_h)
        ed.screen.blit(ed.font.render("Battle Editor", True, _C_HEAD), (panel.x + 12, panel.y + 8))
        self.close_btn = pygame.Rect(panel.right - 72, panel.y + 6, 60, 26)
        _btn(ed, self.close_btn, "Close", (72, 48, 48), (245, 240, 240))
        self._back_btn = pygame.Rect(panel.right - 144, panel.y + 6, 64, 26)
        _btn(ed, self._back_btn, "\u2190 Back", (50, 70, 90), (200, 225, 245))
        self._help_btn = pygame.Rect(panel.right - 216, panel.y + 6, 64, 26)
        _btn(ed, self._help_btn, "Help", (55, 65, 40), (200, 245, 180))
        self._new_btn = pygame.Rect(panel.right - 300, panel.y + 6, 72, 26)
        _btn(ed, self._new_btn, "+ New", (60, 50, 80), _C_HEAD)
        self._save_btn = pygame.Rect(panel.right - 384, panel.y + 6, 72, 26)
        _btn(ed, self._save_btn, "Save", (50, 70, 50), _C_HEAD)
        body = pygame.Rect(panel.x + 12, panel.y + head_h + 8, panel.w - 24, panel.h - head_h - 20)
        list_col = pygame.Rect(body.x, body.y, 160, body.h)
        detail = pygame.Rect(list_col.right + 10, body.y, body.w - list_col.w - 10, body.h)
        pygame.draw.rect(ed.screen, (18, 16, 24), list_col)
        pygame.draw.rect(ed.screen, _C_BORDER, list_col, 1)
        ed.screen.blit(ed.font_small.render("Battles", True, _C_HEAD), (list_col.x + 6, list_col.y + 4))
        lr = pygame.Rect(list_col.x + 4, list_col.y + 24, list_col.w - 8, list_col.h - 28)
        rh = ed.font_small.get_linesize() + 4
        y = lr.y
        self._list_rows = []
        for bid in self.battle_ids:
            row = pygame.Rect(lr.x, y, lr.w, rh)
            if bid == self.sel_id:
                pygame.draw.rect(ed.screen, _C_SEL, row)
            ed.screen.blit(ed.font_small.render(bid[:22], True, _C_HEAD if bid == self.sel_id else _C_TEXT),
                           (row.x + 4, row.y + 2))
            self._list_rows.append((bid, row))
            y += rh
        pygame.draw.rect(ed.screen, (18, 16, 24), detail)
        pygame.draw.rect(ed.screen, _C_BORDER, detail, 1)
        self._detail_body = detail
        self._draw_detail(detail)
        self._resize_corner_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
        self._resize_corner_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
        if self.dropdown:
            self._draw_dropdown()

    def _draw_detail(self, rect: pygame.Rect) -> None:
        ed = self.ed
        x = rect.x + 8
        y = 0
        lh = ed.font_small.get_linesize()
        fh = mtext.form_field_h(ed.font_small)
        self._field_rects = {}
        self._pick_rects = {}
        self._mon_rects = []
        self._btn_rects = []
        prev = ed.screen.get_clip()
        ed.screen.set_clip(rect)

        def sy(logical: int) -> int:
            return rect.y + logical - self.detail_scroll

        def row_field(key: str, label: str, val: str, *, pick: bool = False) -> None:
            nonlocal y
            ly = sy(y)
            ed.screen.blit(ed.font_small.render(label, True, _C_HEAD), (x, ly + 2))
            fr = pygame.Rect(x + 118, ly, rect.w - 126, fh)
            editing = self.focus == key
            shown = self.edit_buf if editing else val
            _field(ed, fr, shown, editing)
            self._field_rects[key] = fr
            if pick:
                pr = pygame.Rect(fr.right + 4, ly, 52, fh)
                _btn(ed, pr, "Pick", (50, 70, 90), (200, 225, 245))
                self._pick_rects[key] = pr
            y += fh + mtext.FORM_ROW_GAP

        row_field("id", "id", str(self.data.get("id", "")))
        row_field("music", "music", str(self.data.get("music", "")), pick=True)
        row_field("background", "background", str(self.data.get("background", "")), pick=True)
        mode = str(self.data.get("outcomeMode", "normal"))
        mode_label = next((lbl for k, lbl in _OUTCOME_MODES if k == mode), mode)
        ly = sy(y)
        ed.screen.blit(ed.font_small.render("outcomeMode", True, _C_HEAD), (x, ly + 2))
        mr = pygame.Rect(x + 118, ly, rect.w - 126, fh)
        _btn(ed, mr, mode_label, (60, 50, 80), _C_HEAD)
        self._btn_rects.append(("outcome", mr))
        y += fh + mtext.FORM_ROW_GAP
        if mode == "scripted_loss":
            row_field("scriptedLossTurns", "loss turns", str(self.data.get("scriptedLossTurns", 0)))

        y += 4
        ly = sy(y)
        ed.screen.blit(ed.font_small.render("Trainers", True, _C_HEAD), (x, ly))
        atr = pygame.Rect(x + 80, ly - 2, 56, fh)
        rtr = pygame.Rect(atr.right + 6, ly - 2, 56, fh)
        _btn(ed, atr, "+ Trainer", (40, 70, 50), _C_HEAD)
        _btn(ed, rtr, "- Trainer", (72, 48, 48), (245, 240, 240))
        self._btn_rects.append(("add_trainer", atr))
        self._btn_rects.append(("del_trainer", rtr))
        y += fh + 8

        trainers = self._trainers()
        for ti in range(min(2, len(trainers))):
            ly = sy(y)
            tab = pygame.Rect(x, ly, 90, fh)
            on = ti == self.sel_trainer
            pygame.draw.rect(ed.screen, _C_SEL if on else (36, 30, 42), tab)
            ed.screen.blit(ed.font_small.render(f"Trainer {ti + 1}", True, _C_HEAD if on else _C_TEXT),
                           (tab.x + 6, tab.y + 2))
            self._btn_rects.append((f"sel_tr:{ti}", tab))
            y += fh + 4
            if ti != self.sel_trainer:
                continue
            party = self._party(ti)
            ly = sy(y)
            am = pygame.Rect(x, ly, 70, fh)
            rm = pygame.Rect(am.right + 6, ly, 70, fh)
            _btn(ed, am, "+ Mon", (40, 70, 50), _C_HEAD)
            _btn(ed, rm, "- Mon", (72, 48, 48), (245, 240, 240))
            self._btn_rects.append((f"add_mon:{ti}", am))
            self._btn_rects.append((f"del_mon:{ti}", rm))
            y += fh + 4
            for pi, mon in enumerate(party[:6]):
                if not isinstance(mon, dict):
                    continue
                ly = sy(y)
                sp = str(mon.get("species", "Pidgey"))
                lv = int(mon.get("level", 5))
                sel = pi == self.sel_mon
                row = pygame.Rect(x, ly, rect.w - 16, fh)
                if sel:
                    pygame.draw.rect(ed.screen, (48, 40, 58), row)
                spr = pygame.Rect(x + 4, ly, rect.w - 180, fh)
                lvd = pygame.Rect(spr.right + 4, ly, 28, fh)
                lvp = pygame.Rect(lvd.right + 2, ly, 28, fh)
                lvtxt = pygame.Rect(lvp.right + 4, ly, 36, fh)
                _field(ed, spr, sp, False)
                _btn(ed, lvd, "-", (55, 50, 65), _C_TEXT)
                _btn(ed, lvp, "+", (55, 50, 65), _C_TEXT)
                _field(ed, lvtxt, str(lv), self.focus == f"mon:{ti}:{pi}:level")
                self._mon_rects.append((ti, pi, spr, lvd, lvp))
                self._field_rects[f"mon:{ti}:{pi}:level"] = lvtxt
                self._btn_rects.append((f"sel_mon:{ti}:{pi}", row))
                y += fh + 2
            y += 4

        self._detail_content_h = y + 8
        max_scroll = max(0, self._detail_content_h - rect.h)
        self.detail_scroll = max(0, min(self.detail_scroll, max_scroll))
        ed.screen.set_clip(prev)

    def _draw_dropdown(self) -> None:
        if not self.dropdown:
            return
        ed = self.ed
        key = self.dropdown["key"]
        vals = self.dropdown["values"]
        rh = ed.font_small.get_linesize() + 4
        pw = 220
        base = self._pick_rects.get(key) or self._field_rects.get(key)
        if base is None:
            return
        panel = pygame.Rect(base.x, base.bottom + 2, pw, min(len(vals), 12) * rh + 4)
        pygame.draw.rect(ed.screen, (28, 24, 34), panel)
        pygame.draw.rect(ed.screen, _C_BORDER, panel, 1)
        self.dropdown["rows"] = []
        y = panel.y + 2
        for v in vals[:24]:
            row = pygame.Rect(panel.x + 2, y, panel.w - 4, rh)
            ed.screen.blit(ed.font_small.render(mtext.truncate_to_width(ed.font_small, v, row.w - 6), True, _C_TEXT),
                           (row.x + 4, row.y + 2))
            self.dropdown["rows"].append((v, row))
            y += rh

    def handle_mouse_down(self, mx: int, my: int, button: int) -> bool:
        if not self.open:
            return False
        if self.dropdown and button == 1:
            for val, rr in self.dropdown.get("rows", []):
                if rr.collidepoint(mx, my):
                    key = self.dropdown["key"]
                    if key == "_species":
                        ti, pi = self.dropdown["target"]
                        party = self._party(ti)
                        if 0 <= pi < len(party):
                            party[pi]["species"] = val
                            self.dirty = True
                    elif val == "(none)":
                        self.data[key] = ""
                        self.dirty = True
                    elif val not in ("(none)", "(no battles)"):
                        self.data[key] = val
                        self.dirty = True
                    self.dropdown = None
                    return True
            self.dropdown = None
        if button == 1 and self.close_btn.collidepoint(mx, my):
            self.close_modal()
            return True
        if button == 1 and self._back_btn.collidepoint(mx, my):
            self.close_modal()
            self.ed.events_launcher_modal.open_modal()
            return True
        if button == 1 and self._help_btn.collidepoint(mx, my):
            self.ed._open_help_overlay(tab="script_ops", back_to="battle")
            return True
        if button == 1 and self._save_btn.collidepoint(mx, my):
            self._save_current()
            return True
        if button == 1 and self._new_btn.collidepoint(mx, my):
            self._commit_field()
            n = len(self.battle_ids) + 1
            bid = f"battle_{n}"
            self.data = _default_battle(bid)
            self.sel_id = bid
            self.dirty = True
            return True
        if button == 1 and self._resize_corner_br.collidepoint(mx, my):
            self._drag_mode = "resize_br"
            self._drag_ref = (self.panel_rect.x, self.panel_rect.y)
            return True
        if button == 1 and self._resize_corner_bl.collidepoint(mx, my):
            self._drag_mode = "resize_bl"
            self._drag_ref = (self.panel_rect.right, self.panel_rect.y)
            return True
        for bid, rr in self._list_rows:
            if rr.collidepoint(mx, my) and button == 1:
                self._commit_field()
                if self.dirty and self.sel_id:
                    self._save_current()
                self._load_battle(bid)
                return True
        if self._detail_body.collidepoint(mx, my) and button == 1:
            self._commit_field()
            for act, rr in self._btn_rects:
                if not rr.collidepoint(mx, my):
                    continue
                if act == "outcome":
                    self._cycle_outcome()
                elif act == "add_trainer":
                    self._add_trainer()
                elif act == "del_trainer":
                    self._remove_trainer()
                elif act.startswith("add_mon:"):
                    self._add_mon(int(act.split(":")[1]))
                elif act.startswith("del_mon:"):
                    self._remove_mon(self.sel_trainer, self.sel_mon)
                elif act.startswith("sel_tr:"):
                    self.sel_trainer = int(act.split(":")[1])
                    self.sel_mon = 0
                elif act.startswith("sel_mon:"):
                    _, ti, pi = act.split(":")
                    self.sel_trainer = int(ti)
                    self.sel_mon = int(pi)
                return True
            for ti, pi, spr, lvd, lvp in self._mon_rects:
                if lvd.collidepoint(mx, my):
                    self._adjust_level(ti, pi, -1)
                    return True
                if lvp.collidepoint(mx, my):
                    self._adjust_level(ti, pi, 1)
                    return True
                if spr.collidepoint(mx, my):
                    self.sel_trainer = ti
                    self.sel_mon = pi
                    self.dropdown = {"key": "_species", "values": self._species or ["Pidgey"], "target": (ti, pi)}
                    return True
            for key, pr in self._pick_rects.items():
                if pr.collidepoint(mx, my):
                    if key == "music":
                        self.dropdown = {"key": key, "values": ["(none)"] + self._audio_stems}
                    elif key == "background":
                        self.dropdown = {"key": key, "values": self._bg_ids or ["example"]}
                    return True
            for key, fr in self._field_rects.items():
                if fr.collidepoint(mx, my):
                    self.focus = key
                    if key == "id":
                        self.edit_buf = str(self.data.get("id", ""))
                    elif key == "scriptedLossTurns":
                        self.edit_buf = str(self.data.get("scriptedLossTurns", 0))
                    elif key.startswith("mon:"):
                        parts = key.split(":")
                        ti, pi = int(parts[1]), int(parts[2])
                        party = self._party(ti)
                        if 0 <= pi < len(party):
                            self.edit_buf = str(party[pi].get("level", 5))
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
            if self.dropdown and self.dropdown.get("key") == "_species":
                for val, rr in self.dropdown.get("rows", []):
                    if rr.collidepoint(mx, my):
                        ti, pi = self.dropdown["target"]
                        party = self._party(ti)
                        if 0 <= pi < len(party):
                            party[pi]["species"] = val
                            self.dirty = True
                        self.dropdown = None
                        return True
            return True
        return False

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if not self.open:
            return False
        if event.key == pygame.K_ESCAPE:
            if self.dropdown:
                self.dropdown = None
                return True
            self._commit_field()
            self.close_modal()
            return True
        if self.focus and event.key == pygame.K_RETURN:
            self._commit_field()
            return True
        if self.focus and event.key == pygame.K_BACKSPACE:
            self.edit_buf = self.edit_buf[:-1]
            return True
        if self.focus and event.unicode and event.unicode.isprintable():
            if self.focus == "scriptedLossTurns" or (self.focus or "").startswith("mon:"):
                if event.unicode.isdigit():
                    self.edit_buf += event.unicode
            else:
                self.edit_buf += event.unicode
            return True
        return True

    def handle_wheel(self, mx: int, my: int, y: int) -> bool:
        if self.open and self._detail_body.collidepoint(mx, my):
            step = (mtext.form_field_h(self.ed.font_small) + 4) * 3
            self.detail_scroll = max(0, self.detail_scroll - int(y) * step)
            return True
        return bool(self.open)


def _btn(ed: MapEditor, rect: pygame.Rect, label: str, bg: tuple, fg: tuple) -> None:
    pygame.draw.rect(ed.screen, bg, rect)
    pygame.draw.rect(ed.screen, (120, 100, 140), rect, 1)
    surf = ed.font_small.render(label, True, fg)
    ed.screen.blit(surf, (rect.x + max(4, (rect.w - surf.get_width()) // 2),
                          mtext.field_text_y(ed.font_small, rect)))


def _field(ed: MapEditor, rect: pygame.Rect, text: str, focused: bool) -> None:
    pygame.draw.rect(ed.screen, (32, 28, 38), rect)
    pygame.draw.rect(ed.screen, (180, 160, 220) if focused else (100, 90, 120), rect, 1)
    shown = mtext.truncate_to_width(ed.font_small, text, rect.w - 8)
    ed.screen.blit(ed.font_small.render(shown, True, _C_TEXT),
                   (mtext.field_text_x(rect), mtext.field_text_y(ed.font_small, rect)))

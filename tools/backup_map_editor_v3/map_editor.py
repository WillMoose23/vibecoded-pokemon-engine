#!/usr/bin/env python3
# Interactive tile map editor. Dependency: pygame
#   Install: python3 -m pip install pygame
# Run from repo root: python3 tools/map_editor.py

from __future__ import annotations

import contextlib
import copy
import importlib.util
import json
import math
from collections import OrderedDict, deque
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path


def _applescript_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _macos_run_osascript(script: str) -> str:
    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=600,
    )
    return (r.stdout or "").strip()


def _macos_choose_png_paths_multi() -> list[str]:
    """Native multi-file picker; avoids Tk (incompatible with SDL on macOS)."""
    script = r"""
    try
        set theFiles to choose file with prompt "Import PNG tileset(s). To open a map .json, cancel then press P." of type {"png"} with multiple selections allowed
        if (class of theFiles) is not list then set theFiles to {theFiles}
        set out to ""
        repeat with f in theFiles
            set out to out & POSIX path of f & linefeed
        end repeat
        return out
    on error
        return ""
    end try
    """
    out = _macos_run_osascript(script)
    return [p.strip() for p in out.splitlines() if p.strip()]


def _macos_dialog_text(prompt: str, default: str) -> str | None:
    p = _applescript_escape(prompt).replace("\n", '" & return & "')
    d = _applescript_escape(default)
    script = f"""
    set _result to "__CANCEL__"
    try
        set r to display dialog "{p}" default answer "{d}" with title "Map editor"
        set _result to text returned of r
    on error
        set _result to "__CANCEL__"
    end try
    _result
    """
    out = _macos_run_osascript(script)
    if out == "__CANCEL__":
        return None
    return out


def _macos_dialog_int(prompt: str, default: int) -> int | None:
    # AppleScript string literals cannot contain raw newlines; replace with AppleScript's return character.
    p = _applescript_escape(prompt).replace("\n", '" & return & "')
    d = str(int(default))
    script = f"""
    set _result to ""
    try
        set r to display dialog "{p}" default answer "{d}" with title "Map editor"
        set _result to text returned of r
    on error
        set _result to "__CANCEL__"
    end try
    _result
    """
    out = _macos_run_osascript(script)
    if out in ("__CANCEL__", ""):
        return None
    try:
        return int(out.strip())
    except ValueError:
        return None


try:
    import pygame
except ImportError:
    print("Install pygame: python3 -m pip install pygame", file=sys.stderr)
    sys.exit(1)


def _pg_key_tuple(*attr_names: str) -> tuple[int, ...]:
    """BUG-MAP-011: build key tuples without missing pygame.K_KP_* (varies by SDL/pygame build)."""
    keys: list[int] = []
    for name in attr_names:
        k = getattr(pygame, name, None)
        if isinstance(k, int):
            keys.append(k)
    return tuple(keys)


@contextlib.contextmanager
def _silence_stderr_fd() -> None:
    """Block C libraries (e.g. libpng iCCP) from spamming stderr during image decode."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    old = os.dup(2)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(old, 2)
        os.close(old)
        os.close(devnull)


def load_pygame_image(path: str) -> pygame.Surface:
    with _silence_stderr_fd():
        return pygame.image.load(path)

ROOT = Path(__file__).resolve().parents[1]
TILESETS_JSON = ROOT / "src" / "tilesets.json"
MAPS_DIR = ROOT / "src" / "maps"
MAPS_INDEX_NAME = "maps_index.json"
WORLD_LAYOUT_JSON_NAME = "world_layout.json"
TILESETS_DIR = ROOT / "src" / "Graphics" / "Tilesets"
CONFIG_PATH = ROOT / "tools" / "map_editor_config.json"

_ENTER_KEYS = _pg_key_tuple("K_RETURN", "K_KP_ENTER")
_OPEN_MAP_PGUP_KEYS = _pg_key_tuple("K_PAGEUP", "K_KP_PAGEUP")
_OPEN_MAP_PGDN_KEYS = _pg_key_tuple("K_PAGEDOWN", "K_KP_PAGEDOWN")

SIDES = ("north", "south", "east", "west")

MIN_WINDOW_W = 1020
MIN_WINDOW_H = 600
INITIAL_W = 1360
INITIAL_H = 720
LAYOUT_MARGIN = 8
PALETTE_MAP_GAP = 12
MAP_SIZE_MAX = 512
PALETTE_SCALE_MAX = 12  # FEATURE-MAP-015
MAP_ZOOM_MIN = 8   # FEATURE-MAP-025
MAP_ZOOM_MAX = 64  # FEATURE-MAP-025
TILESET_LIST_W = 292
LIST_CLICK_DOUBLE = 0.45
TILESET_LIST_DRAG_THRESHOLD_PX = 4
TILESET_LIST_ROW_LINES = 2
TILESET_LIST_CHILD_INDENT_PX = 14  # IMPROVEMENT-MAP-015
UNDO_STACK_MAX = 80
MAP_EDITOR_TOOL_VERSION = "1.0"
WORLD_LAYOUT_JSON_PATH = MAPS_DIR / WORLD_LAYOUT_JSON_NAME
WORLD_UNDO_STACK_MAX = 80
WORLD_THUMB_CACHE_MAX = 32
WORLD_THUMB_MAX_EDGE = 220
WORLD_THUMB_CELL_PX_MIN = 4
# Thumbnail rasterization only: logical world size is map tiles (FEATURE-MAP-WORLD-008).
WORLD_PX_PER_MAP_TILE = 8
WORLD_LEGACY_WORLD_PX_PER_TILE = 8
WORLD_EDGE_SNAP_TILES = 6.0
WORLD_WHEEL_PAN_TILES = 6.0
WORLD_CAM_ZOOM_MIN = 0.12
WORLD_CAM_ZOOM_MAX = 40.0
_WORLD_LAYOUT_MODULE = None


def _load_world_layout_py_module():
    """Lazy import of tools/world_layout.py (script is not always run as a package)."""
    global _WORLD_LAYOUT_MODULE
    if _WORLD_LAYOUT_MODULE is None:
        p = Path(__file__).resolve().parent / "world_layout.py"
        spec = importlib.util.spec_from_file_location("_map_editor_world_layout", p)
        if spec is None or spec.loader is None:
            raise RuntimeError("world_layout: invalid import spec")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _WORLD_LAYOUT_MODULE = mod
    return _WORLD_LAYOUT_MODULE


# FEATURE-MAP-013 / IMPROVEMENT-MAP-015–017: hints + gap after title; keep draw + _measure_tileset_list_header_height in sync
_TILESET_LIST_HINT_1 = "Wheel · +Folder · dbl-click rename"
_TILESET_LIST_HINT_2 = "Drag tileset/folder · Alt+drop on folder: root · R-click: color"
_TILESET_LIST_HINT_3 = "Alt+,/. move · Del delete"
_TILESET_LIST_HINT_GAP_AFTER_TITLE = 6  # IMPROVEMENT-MAP-017: px below "Tilesets" before hints (was 2)
TILESET_ORDER_IN_FOLDER = "in_folder"  # FEATURE-MAP-014: parent folder id on tileset order entries


def _order_tileset_parent_folder(ent: dict) -> str | None:
    if not isinstance(ent, dict) or ent.get("kind") != "tileset":
        return None
    v = ent.get(TILESET_ORDER_IN_FOLDER)
    if v is None or v == "":
        return None
    return str(v)


def _order_set_tileset_parent(ent: dict, folder_id: str | None) -> None:
    if folder_id:
        ent[TILESET_ORDER_IN_FOLDER] = folder_id
    else:
        ent.pop(TILESET_ORDER_IN_FOLDER, None)


def _migrate_implicit_in_folder_on_order(order: list) -> bool:
    """If no tileset entry has in_folder, infer from legacy position-based grouping. Returns True if mutated."""
    if not isinstance(order, list):
        return False
    for ent in order:
        if isinstance(ent, dict) and ent.get("kind") == "tileset" and TILESET_ORDER_IN_FOLDER in ent:
            return False
    active: str | None = None
    changed = False
    for ent in order:
        if not isinstance(ent, dict):
            continue
        k = ent.get("kind")
        eid = str(ent.get("id", "")) if ent.get("id") is not None else ""
        if k == "folder" and eid:
            active = eid
        elif k == "tileset" and eid:
            if active:
                if _order_tileset_parent_folder(ent) != active:
                    _order_set_tileset_parent(ent, active)
                    changed = True
            elif TILESET_ORDER_IN_FOLDER in ent:
                ent.pop(TILESET_ORDER_IN_FOLDER)
                changed = True
    return changed


def key_name_to_pygame(name: str) -> int | None:
    n = name.strip().lower()
    table: dict[str, int] = {
        "equals": pygame.K_EQUALS,
        "plus": pygame.K_PLUS,
        "minus": pygame.K_MINUS,
        "kp_plus": pygame.K_KP_PLUS,
        "kp_minus": pygame.K_KP_MINUS,
        "pageup": pygame.K_PAGEUP,
        "pagedown": pygame.K_PAGEDOWN,
        "s": pygame.K_s,
        "n": pygame.K_n,
        "leftbracket": pygame.K_LEFTBRACKET,
        "rightbracket": pygame.K_RIGHTBRACKET,
        "up": pygame.K_UP,
        "down": pygame.K_DOWN,
        "left": pygame.K_LEFT,
        "right": pygame.K_RIGHT,
        "tab": pygame.K_TAB,
        "g": pygame.K_g,
        "h": pygame.K_h,
        "o": pygame.K_o,
        "p": pygame.K_p,  # BUG-MAP-005: open_map default binding
        "i": pygame.K_i,
        "c": pygame.K_c,
        "t": pygame.K_t,
        "l": pygame.K_l,
        "u": pygame.K_u,
        "comma": pygame.K_COMMA,
        "period": pygame.K_PERIOD,
        "insert": pygame.K_INSERT,
        "delete": pygame.K_DELETE,
        "end": pygame.K_END,
        "escape": pygame.K_ESCAPE,
        "return": pygame.K_RETURN,
        "backspace": pygame.K_BACKSPACE,
        "z": pygame.K_z,
        "r": pygame.K_r,
        "e": pygame.K_e,
        "f": pygame.K_f,
        "d": pygame.K_d,
    }
    return table.get(n)


def default_key_config() -> dict[str, list[str]]:
    return {
        "tileset_prev": ["equals", "plus", "kp_plus", "pageup"],
        "tileset_next": ["minus", "kp_minus", "pagedown"],
        "save": ["s"],
        "new_map": ["n"],
        "map_prev_file": ["leftbracket"],
        "map_next_file": ["rightbracket"],
        "pan_up": ["up"],
        "pan_down": ["down"],
        "pan_left": ["left"],
        "pan_right": ["right"],
        "cycle_mode": ["tab"],
        "set_map_size": ["g"],
        "import_tileset": ["o"],
        "toggle_help": ["h"],
        "toggle_world_labels": ["l"],
        "layer_prev": ["comma"],
        "layer_next": ["period"],
        "layer_add": ["insert", "l"],  # BUG-MAP-019: l adds layer; world open → toggle_world_labels wins (earlier branch)
        "layer_remove": ["end"],
        "undo": ["z"],
        "redo": ["r"],
        "open_map": ["p"],
        "save_as": [],
        "toggle_eraser": ["e"],
        "toggle_fill": ["f"],
        "delete_map": ["d"],
    }


def load_key_config() -> dict[str, list[str]]:
    defaults = default_key_config()
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            keys = data.get("keys")
            if isinstance(keys, dict) and keys:
                merged = {str(k): list(v) if isinstance(v, list) else [str(v)] for k, v in keys.items()}
                for k, v in defaults.items():
                    if k not in merged:
                        merged[k] = v
                return merged
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


def save_key_config(keys: dict[str, list[str]]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"keys": keys}, f, indent=2)
        f.write("\n")


def event_matches_key(event: pygame.event.Event, names: list[str]) -> bool:
    if event.type != pygame.KEYDOWN:
        return False
    for name in names:
        k = key_name_to_pygame(name)
        if k is not None and event.key == k:
            return True
    return False


def blit_wrapped_text(
    surf: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    rect: pygame.Rect,
    color: tuple[int, int, int],
) -> int:
    words = text.split()
    x0, y = rect.x, rect.y
    max_w = rect.w
    max_y = rect.bottom
    lh = font.get_linesize()
    line: list[str] = []
    for word in words:
        cand = " ".join(line + [word])
        tw, _ = font.size(cand)
        if tw <= max_w or not line:
            line.append(word)
        else:
            if y + lh > max_y:
                break
            surf.blit(font.render(" ".join(line), True, color), (x0, y))
            y += lh
            line = [word]
    if line and y + lh <= max_y:
        surf.blit(font.render(" ".join(line), True, color), (x0, y))
        y += lh
    return y


def _truncate_delete_title(font: pygame.font.Font, tid: str, max_w: int) -> str:
    left = 'Delete tileset "'
    right = '"?'
    full = left + tid + right
    if font.size(full)[0] <= max_w:
        return full
    ell = "…"
    t = tid
    while len(t) > 0:
        s = left + t + ell + right
        if font.size(s)[0] <= max_w:
            return s
        t = t[:-1]
    return left + ell + right


def _wrap_lines_to_width(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line: list[str] = []
    for word in words:
        cand = " ".join(line + [word])
        tw, _ = font.size(cand)
        if tw <= max_w or not line:
            line.append(word)
        else:
            lines.append(" ".join(line))
            line = [word]
    if line:
        lines.append(" ".join(line))
    out: list[str] = []
    for ln in lines:
        if font.size(ln)[0] <= max_w:
            out.append(ln)
            continue
        chunk = ""
        for ch in ln:
            test = chunk + ch
            if font.size(test)[0] <= max_w:
                chunk = test
            else:
                if chunk:
                    out.append(chunk)
                chunk = ch
        if chunk:
            out.append(chunk)
    return out


def _truncate_with_ellipsis(font: pygame.font.Font, text: str, max_w: int) -> str:
    ell = "…"
    if font.size(text)[0] <= max_w:
        return text
    t = text
    while len(t) > 0 and font.size(t + ell)[0] > max_w:
        t = t[:-1]
    return t + ell


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ensure_maps_dir() -> None:
    MAPS_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_map_id(raw: str) -> str:
    s = "".join(c if c.isalnum() or c in "._-" else "_" for c in raw.strip())[:64]
    s = s.strip("._-")
    return s if s else "map"


def write_tilesets_registry(path: Path, reg: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)
        f.write("\n")


def write_maps_index() -> None:
    """FEATURE-MAP-008: Refresh src/maps/maps_index.json from map JSON files."""
    ensure_maps_dir()
    maps: list[dict[str, str]] = []
    for path in sorted(MAPS_DIR.glob("*.json")):
        if path.name == MAPS_INDEX_NAME or path.name == WORLD_LAYOUT_JSON_NAME:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                m = json.load(f)
            mid = m.get("id", path.stem)
            name = m.get("name", mid)
            maps.append({"id": str(mid), "name": str(name)})
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    out = {"version": 1, "maps": maps}
    idx_path = MAPS_DIR / MAPS_INDEX_NAME
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
        f.write("\n")


def empty_connections() -> dict:
    return {s: {"mapId": "", "entryTileX": 0, "entryTileY": 0} for s in SIDES}


def _unique_dest_path(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suf = dest.stem, dest.suffix
    n = 2
    while True:
        cand = dest.parent / f"{stem}_{n}{suf}"
        if not cand.exists():
            return cand
        n += 1


def infer_tile_dims_from_sheet_size(w: int, h: int) -> tuple[int, int]:
    """Guess square tile pixel size for a sheet bitmap. Falls back to whole image or gcd."""
    if w <= 0 or h <= 0:
        return (16, 16)
    for s in (16, 8, 32, 24, 48, 64, 12, 20, 128, 256):
        if s <= min(w, h) and w % s == 0 and h % s == 0:
            return (s, s)

    g = math.gcd(w, h)
    g = max(1, min(256, g))
    if g >= 4 and w % g == 0 and h % g == 0:
        return (g, g)
    tw, th = min(w, 256), min(h, 256)
    return (max(1, tw), max(1, th))


def load_png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        surf = load_pygame_image(str(path))
        return surf.get_size()
    except (pygame.error, OSError, ValueError):
        return None


def _refold_to_standard_width(surf: pygame.Surface, original_width: int = 256) -> pygame.Surface:
    """After nearest-neighbor upscale, refold a wider-than-standard sheet back to standard width.

    Splits the image into vertical strips of ``original_width`` pixels each
    and stacks them top-to-bottom.  Each upscaled tile's NxN block stays
    intact because strip boundaries align with original tile column boundaries.
    Returns the surface unchanged if it is already <= original_width.
    """
    sw, sh = surf.get_size()
    if sw <= original_width:
        return surf
    strips = sw // original_width
    if strips <= 1:
        return surf
    out = pygame.Surface((original_width, sh * strips), pygame.SRCALPHA)
    for i in range(strips):
        out.blit(surf, (0, sh * i), (original_width * i, 0, original_width, sh))
    return out


def _compute_upscale_factor(w: int, h: int, target: int = 16) -> int:
    """Return the integer scale factor needed so that sub-target tiles become target-sized.

    Only upscales when the image width clearly indicates a smaller tile grid
    (i.e. width is NOT divisible by target). Returns 1 when no upscale is needed.
    """
    if w <= 0 or h <= 0 or w % target == 0:
        return 1
    for candidate in (8, 4):
        if candidate < target and target % candidate == 0 and w % candidate == 0 and h % candidate == 0:
            return target // candidate
    return 1


def _suggest_upscale_factor(surf: pygame.Surface, max_scale: int = 4) -> int:
    """Detect if the image was drawn at a lower pixel resolution than its grid.

    Samples pixels across the image and checks what fraction of NxN blocks are
    uniform (all pixels identical). If 85%+ of blocks are uniform for a given N,
    the art was likely created at 1/N scale and the function suggests N as the
    upscale factor. Returns 1 if no clear pixel-doubling is detected.
    Uses get_at() so numpy/surfarray is not required.
    """
    w, h = surf.get_width(), surf.get_height()
    if w <= 0 or h <= 0:
        return 1

    for n in range(max_scale, 1, -1):
        if w % n != 0 or h % n != 0:
            continue
        cols = w // n
        rows = h // n
        sample_step = max(1, min(cols, rows) // 32)
        total = 0
        uniform = 0
        for col in range(0, cols, sample_step):
            for row in range(0, rows, sample_step):
                bx = col * n
                by = row * n
                ref = surf.get_at((bx, by))
                is_uniform = True
                for dx in range(n):
                    for dy in range(n):
                        if surf.get_at((bx + dx, by + dy)) != ref:
                            is_uniform = False
                            break
                    if not is_uniform:
                        break
                total += 1
                if is_uniform:
                    uniform += 1
        if total > 0 and uniform / total >= 0.85:
            return n

    return 1


def infer_columns(img_w: int, tw: int, margin: int, spacing: int) -> int:
    if tw <= 0:
        return 1
    usable = img_w - 2 * margin + spacing
    cell = tw + spacing
    if cell <= 0:
        return 1
    return max(1, usable // cell)


class MapEditor:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(f"Map editor {MAP_EDITOR_TOOL_VERSION}")
        self.screen = pygame.display.set_mode((INITIAL_W, INITIAL_H), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("menlo", 14)
        self.font_small = pygame.font.SysFont("menlo", 12)

        self.key_config = load_key_config()

        self.registry = load_json(TILESETS_JSON)
        self.tileset_defs = list(self.registry.get("tilesets", []))
        if not self.tileset_defs:
            raise SystemExit("No tilesets in tilesets.json")

        self.tileset_index = 0
        self.active_tileset_id = self.current_tileset_id()
        self.sheet: pygame.Surface | None = None
        self.sheet_cache: dict[str, pygame.Surface] = {}
        self.meta_cache: dict[str, dict] = {}
        self.columns = 1
        self.map_id = "sample_room"
        self.map_name = "Untitled"
        self.map_w = 12
        self.map_h = 10
        self.tw = 16
        self.th = 16
        self.margin = 0
        self.spacing = 0
        self.tile_layers: list[list[list[dict | None]]] = []
        self.tile_layer_ids: list[str] = []
        self.active_layer_index = 0
        self.layer_remove_confirm_idx: int | None = None
        self.walk: list[list[int]] = []
        self.trans: list[list[int]] = []
        self.connections = empty_connections()

        self.brush_pattern: list[list[tuple[str, int]]] = [[(self.active_tileset_id, 1)]]
        self.selected_tile = 1

        self.paint_button = 1
        self.window_w = INITIAL_W
        self.window_h = INITIAL_H
        self.palette_rect = pygame.Rect(0, 0, 1, 1)
        self.tileset_list_rect = pygame.Rect(0, 0, 1, 1)
        self.map_viewport_rect = pygame.Rect(0, 0, 1, 1)
        self.footer_rect = pygame.Rect(0, 0, 1, 1)
        self.gear_rect = pygame.Rect(0, 0, 32, 32)
        self.world_btn_rect = pygame.Rect(0, 0, 32, 32)
        self.layer_chip_rect = pygame.Rect(0, 0, 1, 1)
        self.map_canvas_rect = pygame.Rect(0, 0, 1, 1)
        self.settings_add_event_rect = pygame.Rect(0, 0, 1, 1)
        self.settings_remove_event_rect = pygame.Rect(0, 0, 1, 1)
        self.settings_remove_current_layer_rect = pygame.Rect(0, 0, 1, 1)  # FEATURE-MAP-019
        self.palette_sel_h = self.font.get_linesize() + 6
        self.map_origin_x = 0
        self.map_origin_y = 0
        self.cell_px = 24
        self.map_view_off_x = 0
        self.map_view_off_y = 0

        self.hover_cell: tuple[int, int] | None = None
        self.palette_drag_start: tuple[int, int] | None = None
        self.palette_drag_end: tuple[int, int] | None = None
        # FEATURE-MAP-006: inclusive sheet tile coords (col0, row0, col1, row1) for active tileset brush
        self.palette_brush_tile_rect: tuple[int, int, int, int] | None = None
        self.map_drag_start: tuple[int, int] | None = None
        self.map_paint_current: tuple[int, int] | None = None
        self.map_drag_button = 1

        self.conn_field_index = 0
        self.conn_field_names = ("mapId", "entryTileX", "entryTileY")
        self.text_buffer = ""
        self.edit_mode = "paint"
        self.map_files: list[Path] = []
        self.map_file_index = 0
        self.palette_scale = 1
        self.palette_zoom_offset = 0  # FEATURE-MAP-015
        self.palette_scroll_x = 0
        self.palette_scroll_y = 0
        self.eraser_mode = False  # FEATURE-MAP-016
        self.fill_mode = False  # FEATURE-MAP-017
        self.tileset_list_scroll_y = 0
        self.tileset_list_scroll_x = 0  # FEATURE-MAP-024
        self._tileset_list_header_h = 52
        self.tileset_rename_index: int | None = None
        self.tileset_rename_buffer = ""
        self._list_click_prev_time = 0.0
        self._list_click_prev_index = -1

        self.status_message: str | None = None
        self.status_msg_until = 0.0
        self.status_kind: str = "info"

        self.tileset_delete_confirm_id: str | None = None
        self.map_delete_confirm_stem: str | None = None  # FEATURE-MAP-018

        self.settings_open = False
        self.settings_capture: str | None = None
        self.size_prompt_active = False
        self.tileset_tab_rects: list[pygame.Rect] = []  # unused; list is in tileset_list_rect
        self.footer_help_expanded: bool = False
        self.saved_once = False

        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []

        self.map_file_prompt_mode: str | None = None
        self.map_file_prompt_buffer: str = ""
        self.map_overwrite_candidate_id: str | None = None

        self.open_map_overlay: bool = False
        self.open_map_purpose: str = "load"
        self.open_map_stems: list[str] = []
        self.open_map_sel: int = 0
        self.open_map_scroll: int = 0

        self.folder_rename_id: str | None = None
        self.folder_rename_buffer: str = ""
        self.new_folder_btn_rect = pygame.Rect(0, 0, 1, 1)
        self.folder_new_prompt_active: bool = False
        self.folder_new_prompt_buffer: str = ""
        self.folder_color_prompt_id: str | None = None
        self.folder_color_prompt_buffer: str = ""
        self._folder_click_prev_id: str | None = None
        self._folder_click_prev_time: float = 0.0
        self._open_map_box_rect: pygame.Rect = pygame.Rect(0, 0, 1, 1)
        self._map_disk_backing_id: str | None = None
        self._map_save_pending_is_save_as: bool = False
        self._session_map_cache: dict[str, dict] = {}

        self.world_workspace_open: bool = False
        self.world_nodes: list[dict] = []
        self.world_cam_x: float = 0.0
        self.world_cam_y: float = 0.0
        self.world_cam_zoom: float = 8.0
        self._world_undo_stack: list[dict] = []
        self._world_redo_stack: list[dict] = []
        self._world_thumb_surfaces: OrderedDict[str, pygame.Surface] = OrderedDict()
        self.world_drag_node_i: int | None = None
        self._world_drag_off_x: float = 0.0
        self._world_drag_off_y: float = 0.0
        self.world_ctx_menu: dict | None = None
        self.world_clipboard: dict | None = None
        self._world_panning: bool = False
        self._world_pan_last: tuple[int, int] | None = None
        self.world_map_labels_visible: bool = True
        self._world_label_font_cache: OrderedDict[int, pygame.font.Font] = OrderedDict()

        self._tileset_drag_def_index: int | None = None
        self._tileset_drag_start: tuple[int, int] | None = None
        self._tileset_drag_moved: bool = False
        self._folder_drag_id: str | None = None
        self._folder_drag_start: tuple[int, int] | None = None
        self._folder_drag_moved: bool = False

        self.reload_tileset_sheet()
        self.new_map(reset_connections=True)
        self.refresh_map_file_list()
        self.try_load_map_by_id(self.map_id)
        self.relayout()
        self._refresh_brush_palette_outline()
        self._load_world_workspace_disk_state()

    def current_tileset_id(self) -> str:
        return str(self.tileset_defs[self.tileset_index].get("id", ""))

    def get_tileset_meta(self, ts_id: str) -> dict | None:
        for d in self.tileset_defs:
            if d.get("id") == ts_id:
                return d
        return None

    def ensure_sheet(self, ts_id: str) -> tuple[pygame.Surface, dict] | None:
        if ts_id in self.sheet_cache and ts_id in self.meta_cache:
            return self.sheet_cache[ts_id], self.meta_cache[ts_id]
        meta = self.get_tileset_meta(ts_id)
        if not meta:
            return None
        path = ROOT / meta["image"]
        if not path.is_file():
            return None
        with _silence_stderr_fd():
            surf = pygame.image.load(str(path)).convert_alpha()
        sw, sh = surf.get_size()
        tw = int(meta.get("tileWidth", 16))
        th = int(meta.get("tileHeight", 16))
        margin = int(meta.get("margin", 0))
        spacing = int(meta.get("spacing", 0))
        cols = int(meta.get("columns", 0) or 0)
        if cols <= 0:
            cols = infer_columns(sw, tw, margin, spacing)
        m = {
            "tw": tw,
            "th": th,
            "margin": margin,
            "spacing": spacing,
            "columns": cols,
            "w": sw,
            "h": sh,
        }
        self.sheet_cache[ts_id] = surf
        self.meta_cache[ts_id] = m
        return surf, m

    def reload_tileset_sheet(self) -> None:
        self.active_tileset_id = self.current_tileset_id()
        out = self.ensure_sheet(self.active_tileset_id)
        if not out:
            raise SystemExit(f"Missing tileset: {self.active_tileset_id}")
        self.sheet, meta = out
        self.tw = meta["tw"]
        self.th = meta["th"]
        self.margin = meta["margin"]
        self.spacing = meta["spacing"]
        self.columns = meta["columns"]
        self.palette_scroll_y = 0
        self.palette_scroll_x = 0
        self.palette_zoom_offset = 0
        self._refresh_brush_palette_outline()

    def _refresh_brush_palette_outline(self) -> None:
        """FEATURE-MAP-006: bbox in sheet tile coords for brush cells on the active tileset."""
        ts = self.active_tileset_id
        cols = max(1, self.columns)
        min_c = min_r = 10**9
        max_c = max_r = -1
        if self.brush_pattern:
            for row in self.brush_pattern:
                for cell_ts, t in row:
                    if cell_ts != ts or t < 1:
                        continue
                    ti = t - 1
                    c = ti % cols
                    r = ti // cols
                    min_c = min(min_c, c)
                    min_r = min(min_r, r)
                    max_c = max(max_c, c)
                    max_r = max(max_r, r)
        if max_c < 0:
            self.palette_brush_tile_rect = None
        else:
            self.palette_brush_tile_rect = (min_c, min_r, max_c, max_r)

    def relayout(self) -> None:
        w, h = self.screen.get_size()
        self.window_w, self.window_h = w, h
        m = LAYOUT_MARGIN
        footer_h = max(150, min(int(h * 0.24), 280))
        footer_h = min(footer_h, max(120, h - 100))
        self.footer_rect = pygame.Rect(0, h - footer_h, w, footer_h)
        content_bottom = self.footer_rect.y
        available_h = max(60, content_bottom - 2 * m)
        palette_w = int(max(220, min(w * 0.22, 400)))
        self.palette_rect = pygame.Rect(m, m, palette_w, available_h)
        list_x = self.palette_rect.right + PALETTE_MAP_GAP
        self.tileset_list_rect = pygame.Rect(list_x, m, TILESET_LIST_W, available_h)
        map_x = self.tileset_list_rect.right + PALETTE_MAP_GAP
        map_w = max(80, w - map_x - m)
        self.map_viewport_rect = pygame.Rect(map_x, m, map_w, available_h)
        chip_h = 28
        chip_gap = 6
        self.layer_chip_rect = pygame.Rect(self.map_viewport_rect.x, self.map_viewport_rect.y, self.map_viewport_rect.w, chip_h)
        self.map_origin_x = self.map_viewport_rect.x
        self.map_origin_y = self.map_viewport_rect.y + chip_h + chip_gap
        self.map_canvas_rect = pygame.Rect(
            self.map_viewport_rect.x,
            self.map_origin_y,
            self.map_viewport_rect.w,
            max(8, self.map_viewport_rect.bottom - self.map_origin_y),
        )
        self.palette_sel_h = self.font.get_linesize() + 6
        btn_w = 32
        btn_gap = 4
        self.gear_rect = pygame.Rect(self.map_viewport_rect.right - btn_w, self.map_viewport_rect.y + 2, btn_w, chip_h - 4)
        self.world_btn_rect = pygame.Rect(self.gear_rect.x - btn_gap - btn_w, self.gear_rect.y, btn_w, self.gear_rect.h)
        self._clamp_palette_scroll()
        self._tileset_list_header_h = self._measure_tileset_list_header_height()
        self._clamp_tileset_list_scroll()

    def set_status(self, msg: str, seconds: float = 8.0, kind: str = "info") -> None:
        """kind: info (neutral), ok (success), err (error)."""
        self.status_message = msg
        self.status_msg_until = time.time() + seconds
        self.status_kind = kind if kind in ("info", "ok", "err") else "info"

    def _clear_undo_stacks(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    def _snapshot_map_state(self) -> dict:
        return {
            "tile_layers": copy.deepcopy(self.tile_layers),
            "tile_layer_ids": list(self.tile_layer_ids),
            "walk": [row[:] for row in self.walk],
            "trans": [row[:] for row in self.trans],
            "active_layer_index": self.active_layer_index,
        }

    def _restore_map_state(self, s: dict) -> None:
        self.tile_layers = copy.deepcopy(s["tile_layers"])
        self.tile_layer_ids = list(s["tile_layer_ids"])
        self.walk = [row[:] for row in s["walk"]]
        self.trans = [row[:] for row in s["trans"]]
        self.active_layer_index = int(s["active_layer_index"])

    def _undo_checkpoint(self) -> None:
        """FEATURE-MAP-009: push pre-edit snapshot; clears redo."""
        self._undo_stack.append(self._snapshot_map_state())
        if len(self._undo_stack) > UNDO_STACK_MAX:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo_map_edit(self) -> None:
        if not self._undo_stack:
            self.set_status("Nothing to undo.", kind="info")
            return
        self._redo_stack.append(self._snapshot_map_state())
        self._restore_map_state(self._undo_stack.pop())

    def redo_map_edit(self) -> None:
        if not self._redo_stack:
            self.set_status("Nothing to redo.", kind="info")
            return
        self._undo_stack.append(self._snapshot_map_state())
        self._restore_map_state(self._redo_stack.pop())

    def _world_snapshot(self) -> dict:
        return {
            "nodes": copy.deepcopy(self.world_nodes),
            "cam_x": float(self.world_cam_x),
            "cam_y": float(self.world_cam_y),
            "cam_z": float(self.world_cam_zoom),
        }

    def _world_restore(self, s: dict) -> None:
        self.world_nodes = copy.deepcopy(s["nodes"])
        self.world_cam_x = float(s["cam_x"])
        self.world_cam_y = float(s["cam_y"])
        self.world_cam_zoom = float(s["cam_z"])

    def _world_undo_checkpoint(self) -> None:
        self._world_undo_stack.append(self._world_snapshot())
        if len(self._world_undo_stack) > WORLD_UNDO_STACK_MAX:
            self._world_undo_stack.pop(0)
        self._world_redo_stack.clear()

    def _clear_world_undo_stacks(self) -> None:
        self._world_undo_stack.clear()
        self._world_redo_stack.clear()

    def undo_world_edit(self) -> None:
        if not self._world_undo_stack:
            self.set_status("Nothing to undo (world).", kind="info")
            return
        self._world_redo_stack.append(self._world_snapshot())
        self._world_restore(self._world_undo_stack.pop())

    def redo_world_edit(self) -> None:
        if not self._world_redo_stack:
            self.set_status("Nothing to redo (world).", kind="info")
            return
        self._world_undo_stack.append(self._world_snapshot())
        self._world_restore(self._world_redo_stack.pop())

    def _world_thumb_touch(self, map_id: str) -> None:
        if map_id in self._world_thumb_surfaces:
            self._world_thumb_surfaces.move_to_end(map_id)

    def _world_thumb_store(self, map_id: str, surf: pygame.Surface) -> None:
        self._world_thumb_surfaces[map_id] = surf
        self._world_thumb_surfaces.move_to_end(map_id)
        while len(self._world_thumb_surfaces) > WORLD_THUMB_CACHE_MAX:
            self._world_thumb_surfaces.popitem(last=False)

    def _parse_map_json_into_tile_layers(self, m: dict) -> tuple[list[list[list[dict | None]]], int, int, int, int, str] | None:
        """Build in-memory tile layer grids from map JSON (read-only; does not mutate editor map)."""
        tid = str(m.get("tilesetId", "boat"))
        mw = int(m.get("width", 12))
        mh = int(m.get("height", 10))
        tw = int(m.get("tileWidth", 16))
        th = int(m.get("tileHeight", 16))
        layers = m.get("layers", {})
        tile_layers: list[list[list[dict | None]]] = []
        if not isinstance(layers, dict):
            return None
        tls = layers.get("tileLayers")
        if isinstance(tls, list) and len(tls) > 0:
            seen_ids: set[str] = set()

            def _uniq_lid(base: str) -> str:
                lid = base
                n = 2
                while lid in seen_ids:
                    lid = f"{base}_{n}"
                    n += 1
                seen_ids.add(lid)
                return lid

            for entry in tls:
                if not isinstance(entry, dict):
                    continue
                _uniq_lid(str(entry.get("id", "layer")))
                cells_data = entry.get("cells")
                grid = [[None for _ in range(mw)] for _ in range(mh)]
                if isinstance(cells_data, list):
                    for y, row in enumerate(cells_data):
                        if y >= mh:
                            break
                        if not isinstance(row, list):
                            continue
                        for x, cell in enumerate(row):
                            if x >= mw:
                                break
                            if cell is None:
                                grid[y][x] = None
                            elif isinstance(cell, dict):
                                grid[y][x] = {
                                    "ts": str(cell.get("ts", tid)),
                                    "t": int(cell.get("t", 0)),
                                }
                tile_layers.append(grid)
        if not tile_layers:
            grid = [[None for _ in range(mw)] for _ in range(mh)]
            gcells = layers.get("groundCells")
            if isinstance(gcells, list):
                for y, row in enumerate(gcells):
                    if y >= mh:
                        break
                    if not isinstance(row, list):
                        continue
                    for x, cell in enumerate(row):
                        if x >= mw:
                            break
                        if cell is None:
                            grid[y][x] = None
                        elif isinstance(cell, dict):
                            grid[y][x] = {
                                "ts": str(cell.get("ts", tid)),
                                "t": int(cell.get("t", 0)),
                            }
            else:
                gr = layers.get("ground", [])
                for y, row in enumerate(gr):
                    if y >= mh:
                        break
                    for x, v in enumerate(row):
                        if x >= mw:
                            break
                        vi = int(v)
                        grid[y][x] = None if vi == 0 else {"ts": tid, "t": vi}
            tile_layers = [grid]
        return tile_layers, mw, mh, tw, th, tid

    def _thumbnail_surface_for_map_stem(self, stem: str) -> pygame.Surface | None:
        path = MAPS_DIR / f"{stem}.json"
        if not path.is_file():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        parsed = self._parse_map_json_into_tile_layers(m)
        if not parsed:
            return None
        tile_layers, mw, mh, tw, th, _tid = parsed
        full_pw = max(1, mw * tw)
        full_ph = max(1, mh * th)
        scale = min(1.0, WORLD_THUMB_MAX_EDGE / max(full_pw, full_ph))
        cell_px = max(WORLD_THUMB_CELL_PX_MIN, int(min(tw, th) * scale))
        surf_w = max(2, mw * cell_px)
        surf_h = max(2, mh * cell_px)
        surf = pygame.Surface((surf_w, surf_h))
        surf.fill((22, 24, 30))
        draw_cell_grid = cell_px >= 5
        for y in range(mh):
            for x in range(mw):
                px = x * cell_px
                py = y * cell_px
                for grid in tile_layers:
                    c = grid[y][x]
                    if c is not None:
                        self.blit_tile_scaled(surf, c["ts"], c["t"], px, py, cell_px)
                if draw_cell_grid:
                    pygame.draw.rect(surf, (48, 50, 58), (px, py, cell_px, cell_px), 1)
        return surf

    def _ensure_world_thumbnail(self, stem: str) -> pygame.Surface | None:
        self._world_thumb_touch(stem)
        if stem in self._world_thumb_surfaces:
            return self._world_thumb_surfaces[stem]
        thumb = self._thumbnail_surface_for_map_stem(stem)
        if thumb is None:
            return None
        self._world_thumb_store(stem, thumb)
        return thumb

    def _load_world_workspace_disk_state(self) -> None:
        wl = _load_world_layout_py_module()
        raw = wl.read_world_layout_json(WORLD_LAYOUT_JSON_PATH)
        if not raw or not isinstance(raw.get("nodes"), list):
            return
        nodes_in = raw["nodes"]
        out: list[dict] = []
        any_legacy = False
        leg = WORLD_LEGACY_WORLD_PX_PER_TILE
        for n in nodes_in:
            if not isinstance(n, dict):
                continue
            mid = str(n.get("mapId", ""))
            if not mid:
                continue
            uid = str(n.get("nodeUuid", n.get("instanceId", ""))).strip() or str(uuid.uuid4())
            mw_t = int(n.get("mapWidthTiles", 0))
            mh_t = int(n.get("mapHeightTiles", 0))
            wx = float(n.get("worldX", 0))
            wy = float(n.get("worldY", 0))
            wp_file = int(n.get("widthPx", 0))
            hp_file = int(n.get("heightPx", 0))
            if mw_t > 0 and mh_t > 0:
                if wp_file == mw_t * leg and hp_file == mh_t * leg:
                    any_legacy = True
                    wx /= leg
                    wy /= leg
                wp, hp = mw_t, mh_t
            elif wp_file > 0 and hp_file > 0 and wp_file % leg == 0 and hp_file % leg == 0:
                any_legacy = True
                wx /= leg
                wy /= leg
                wp = max(1, wp_file // leg)
                hp = max(1, hp_file // leg)
                mw_t, mh_t = wp, hp
            else:
                wp = max(1, wp_file or 20)
                hp = max(1, hp_file or 15)
            out.append(
                {
                    "nodeUuid": uid,
                    "mapId": mid,
                    "worldX": wx,
                    "worldY": wy,
                    "widthPx": wp,
                    "heightPx": hp,
                    "mapWidthTiles": mw_t,
                    "mapHeightTiles": mh_t,
                    "tileWidth": int(n.get("tileWidth", 16)),
                    "tileHeight": int(n.get("tileHeight", 16)),
                    "interior": bool(n.get("interior", False)),
                }
            )
        self.world_nodes = out
        for node in self.world_nodes:
            self._world_snap_node_origin_to_grid(node)
        cam = raw.get("editorCamera")
        if isinstance(cam, dict):
            if any_legacy:
                self.world_cam_x = float(cam.get("x", self.world_cam_x)) / leg
                self.world_cam_y = float(cam.get("y", self.world_cam_y)) / leg
                z = float(cam.get("zoom", 1.0)) * leg
                self.world_cam_zoom = max(WORLD_CAM_ZOOM_MIN, min(WORLD_CAM_ZOOM_MAX, z))
            else:
                self.world_cam_x = float(cam.get("x", self.world_cam_x))
                self.world_cam_y = float(cam.get("y", self.world_cam_y))
                self.world_cam_zoom = max(
                    WORLD_CAM_ZOOM_MIN,
                    min(WORLD_CAM_ZOOM_MAX, float(cam.get("zoom", self.world_cam_zoom))),
                )
        self._clear_world_undo_stacks()

    def _world_screen_to_world(self, sx: int, sy: int) -> tuple[float, float]:
        r = self.map_canvas_rect
        z = max(WORLD_CAM_ZOOM_MIN, min(WORLD_CAM_ZOOM_MAX, self.world_cam_zoom))
        lx = sx - r.x
        ly = sy - r.y
        return (lx / z + self.world_cam_x, ly / z + self.world_cam_y)

    def _world_world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        r = self.map_canvas_rect
        z = max(WORLD_CAM_ZOOM_MIN, min(WORLD_CAM_ZOOM_MAX, self.world_cam_zoom))
        sx = int(r.x + (wx - self.world_cam_x) * z)
        sy = int(r.y + (wy - self.world_cam_y) * z)
        return sx, sy

    def _world_hit_node_index(self, sx: int, sy: int) -> int | None:
        for i in range(len(self.world_nodes) - 1, -1, -1):
            n = self.world_nodes[i]
            x0, y0 = self._world_world_to_screen(float(n["worldX"]), float(n["worldY"]))
            w = int(float(n["widthPx"]) * max(WORLD_CAM_ZOOM_MIN, min(WORLD_CAM_ZOOM_MAX, self.world_cam_zoom)))
            h = int(float(n["heightPx"]) * max(WORLD_CAM_ZOOM_MIN, min(WORLD_CAM_ZOOM_MAX, self.world_cam_zoom)))
            rr = pygame.Rect(x0, y0, max(4, w), max(4, h))
            if rr.collidepoint(sx, sy):
                return i
        return None

    def _world_node_bounds(self, n: dict) -> tuple[float, float, float, float]:
        return (
            float(n["worldX"]),
            float(n["worldY"]),
            float(n["worldX"]) + float(n["widthPx"]),
            float(n["worldY"]) + float(n["heightPx"]),
        )

    def _world_snap_node_origin_to_grid(self, n: dict) -> None:
        """BUG-MAP-WORLD-009: nearest integer world tile (round), not floor — floor biased sub-tile drags into touching."""
        n["worldX"] = float(round(float(n["worldX"])))
        n["worldY"] = float(round(float(n["worldY"])))

    def _world_aabbs_overlap(self, ax0: float, ay0: float, ax1: float, ay1: float, bx0: float, by0: float, bx1: float, by1: float) -> bool:
        return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1

    def _world_fixup_overlaps(self, idx: int) -> None:
        """FEATURE-MAP-WORLD-004: push non-interior nodes apart (minimal axis separation)."""
        n = self.world_nodes[idx]
        if n.get("interior"):
            return
        for _ in range(32):
            moved = False
            ax0, ay0, ax1, ay1 = self._world_node_bounds(n)
            for j, o in enumerate(self.world_nodes):
                if j == idx or o.get("interior"):
                    continue
                bx0, by0, bx1, by1 = self._world_node_bounds(o)
                if not self._world_aabbs_overlap(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1):
                    continue
                ox = min(ax1, bx1) - max(ax0, bx0)
                oy = min(ay1, by1) - max(ay0, by0)
                if ox <= 0 or oy <= 0:
                    continue
                cxn = (ax0 + ax1) * 0.5
                cyn = (ay0 + ay1) * 0.5
                cxo = (bx0 + bx1) * 0.5
                cyo = (by0 + by1) * 0.5
                eps = 0
                if ox < oy:
                    if cxn < cxo:
                        n["worldX"] = float(n["worldX"]) - (ox + eps)
                    else:
                        n["worldX"] = float(n["worldX"]) + (ox + eps)
                else:
                    if cyn < cyo:
                        n["worldY"] = float(n["worldY"]) - (oy + eps)
                    else:
                        n["worldY"] = float(n["worldY"]) + (oy + eps)
                ax0, ay0, ax1, ay1 = self._world_node_bounds(n)
                moved = True
            if not moved:
                break

    def _world_font_for_label_size(self, px_height: int) -> pygame.font.Font:
        """IMPROVEMENT-MAP-WORLD-006: cached SysFont for world name badges (avoids per-frame SysFont churn)."""
        fz = max(10, min(20, int(px_height)))
        c = self._world_label_font_cache
        if fz in c:
            c.move_to_end(fz)
            return c[fz]
        c[fz] = pygame.font.SysFont("menlo", fz)
        while len(c) > 12:
            c.popitem(last=False)
        return c[fz]

    def _world_blit_map_label(self, dst: pygame.Rect, stem: str, z: float) -> None:
        """IMPROVEMENT-MAP-WORLD-006: small black badge with white text; font scales with world zoom."""
        label = stem[:36]
        fz = max(10, min(20, int(11 * min(max(z, 0.15), 2.5))))
        font = self._world_font_for_label_size(fz)
        t = font.render(label, True, (248, 248, 252))
        pad = max(3, fz // 4)
        bw, bh = t.get_width() + 2 * pad, t.get_height() + 2 * pad
        bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 235))
        bg.blit(t, (pad, pad))
        r = self.map_canvas_rect
        bx = min(dst.x + 4, r.right - bw - 2)
        by = min(dst.y + 4, r.bottom - bh - 2)
        bx = max(r.x + 2, bx)
        by = max(r.y + 2, by)
        self.screen.blit(bg, (bx, by))

    def _world_default_node_position(self) -> tuple[float, float]:
        n = len(self.world_nodes)
        return (float((n % 8) * 32), float((n // 8) * 24))

    def _world_add_node_from_map_id(self, stem: str, *, skip_checkpoint: bool = False) -> bool:
        path = MAPS_DIR / f"{stem}.json"
        if not path.is_file():
            self.set_status(f"No map file for '{stem}'.", kind="err")
            return False
        thumb = self._ensure_world_thumbnail(stem)
        if thumb is None:
            self.set_status(f"Could not build thumbnail for '{stem}'.", kind="err")
            return False
        try:
            with open(path, encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self.set_status(f"Read error {stem}: {e}", kind="err")
            return False
        mw = int(m.get("width", 1))
        mh = int(m.get("height", 1))
        tw = int(m.get("tileWidth", 16))
        th = int(m.get("tileHeight", 16))
        wx, wy = self._world_default_node_position()
        if not skip_checkpoint:
            self._world_undo_checkpoint()
        self.world_nodes.append(
            {
                "nodeUuid": str(uuid.uuid4()),
                "mapId": stem,
                "worldX": wx,
                "worldY": wy,
                "widthPx": mw,
                "heightPx": mh,
                "mapWidthTiles": mw,
                "mapHeightTiles": mh,
                "tileWidth": tw,
                "tileHeight": th,
                "interior": False,
            }
        )
        self._world_snap_node_origin_to_grid(self.world_nodes[-1])
        return True

    def _world_remove_node_index(self, idx: int) -> None:
        if not (0 <= idx < len(self.world_nodes)):
            return
        self._world_undo_checkpoint()
        del self.world_nodes[idx]

    def open_map_for_world_insert(self) -> None:
        self.open_map_interactive()
        self.open_map_purpose = "world"
        self.set_status("World: pick a map to add (↑↓ Enter · Esc)", kind="info")

    def _world_export_layout_file(self) -> None:
        wl = _load_world_layout_py_module()
        origin = self.map_id if any(n.get("mapId") == self.map_id for n in self.world_nodes) else None
        if origin is None and self.world_nodes:
            origin = str(self.world_nodes[0].get("mapId", ""))
        cam = {
            "x": self.world_cam_x,
            "y": self.world_cam_y,
            "zoom": self.world_cam_zoom,
        }
        payload = wl.build_export_dict(
            self.world_nodes,
            edge_snap_px=WORLD_EDGE_SNAP_TILES,
            origin_map_id=origin,
            editor_tool_version=MAP_EDITOR_TOOL_VERSION,
            cam=cam,
        )
        wl.write_world_layout_json(WORLD_LAYOUT_JSON_PATH, payload)
        self.set_status(f"Exported {WORLD_LAYOUT_JSON_PATH.relative_to(ROOT)}", kind="ok")

    def _world_open_context_menu(self, sx: int, sy: int, node_i: int | None) -> None:
        items: list[tuple[str, str]] = [
            ("Insert map…", "insert"),
            ("Undo", "undo"),
            ("Redo", "redo"),
            ("Copy", "copy"),
            ("Paste", "paste"),
        ]
        if node_i is not None:
            items.insert(1, ("Delete from workspace", "delete"))
            ni = self.world_nodes[node_i]
            ilbl = "Interior: ON (overlap OK)" if ni.get("interior") else "Interior: OFF (overworld snap)"
            items.insert(2, (ilbl, "interior"))
        rects: list[pygame.Rect] = []
        mw = 200
        mh = 4 + len(items) * 24
        x = min(sx, self.window_w - mw - 8)
        y = min(sy, self.window_h - mh - 8)
        for i, (_label, _aid) in enumerate(items):
            rects.append(pygame.Rect(x + 2, y + 2 + i * 24, mw - 4, 22))
        self.world_ctx_menu = {
            "x": x,
            "y": y,
            "w": mw,
            "h": mh,
            "node_i": node_i,
            "items": items,
            "rects": rects,
        }

    def _world_ctx_hit_action(self, pos: tuple[int, int]) -> str | None:
        m = self.world_ctx_menu
        if not m:
            return None
        for rect, (_lab, aid) in zip(m["rects"], m["items"]):
            if rect.collidepoint(pos):
                return aid
        return None

    def _world_run_ctx_action(self, action: str) -> None:
        m = self.world_ctx_menu
        node_i = m.get("node_i") if m else None
        self.world_ctx_menu = None
        if action == "insert":
            self.open_map_for_world_insert()
        elif action == "delete" and node_i is not None:
            self._world_remove_node_index(node_i)
        elif action == "interior" and node_i is not None:
            self._world_undo_checkpoint()
            nn = self.world_nodes[node_i]
            nn["interior"] = not bool(nn.get("interior"))
            self.set_status(
                "World: interior ON (maps may overlap)." if nn["interior"] else "World: interior OFF (overworld snap).",
                kind="ok",
            )
        elif action == "undo":
            self.undo_world_edit()
        elif action == "redo":
            self.redo_world_edit()
        elif action == "copy" and node_i is not None:
            n = self.world_nodes[node_i]
            self.world_clipboard = {
                "mapId": str(n.get("mapId", "")),
                "widthPx": int(n.get("widthPx", 0)),
                "heightPx": int(n.get("heightPx", 0)),
                "interior": bool(n.get("interior", False)),
            }
            self.set_status("World: copied map node.", kind="ok")
        elif action == "paste":
            cb = self.world_clipboard
            if not cb or not cb.get("mapId"):
                self.set_status("World: nothing to paste.", kind="info")
                return
            stem = str(cb["mapId"])
            self._world_undo_checkpoint()
            if not self._world_add_node_from_map_id(stem, skip_checkpoint=True):
                return
            last = self.world_nodes[-1]
            last["worldX"] = float(last["worldX"]) + 2.0
            last["worldY"] = float(last["worldY"]) + 2.0
            last["interior"] = bool(cb.get("interior", False))
            self._world_snap_node_origin_to_grid(last)
            self.set_status(f"World: pasted '{stem}'.", kind="ok")

    def _draw_world_context_menu(self) -> None:
        m = self.world_ctx_menu
        if not m:
            return
        box = pygame.Rect(m["x"], m["y"], m["w"], m["h"])
        pygame.draw.rect(self.screen, (42, 44, 54), box)
        pygame.draw.rect(self.screen, (130, 130, 155), box, 1)
        for (_label, aid), rect in zip(m["items"], m["rects"]):
            txt = _label if aid != "insert" else "Insert map…"
            self.screen.blit(self.font_small.render(txt, True, (235, 235, 242)), (rect.x + 8, rect.y + 4))

    def _world_grid_step_for_zoom(self, z: float, canvas: pygame.Rect) -> int:
        """FEATURE-MAP-WORLD-008: show 1-tile grid when zoomed in; coarser step when zoomed out (line cap)."""
        z = max(WORLD_CAM_ZOOM_MIN, min(WORLD_CAM_ZOOM_MAX, z))
        visible = max(canvas.w, canvas.h) / max(z, 1e-9)
        max_lines = 96
        if visible <= max_lines:
            return 1
        raw = max(1, int(math.ceil(visible / max_lines)))
        p = 1
        while p < raw:
            p <<= 1
        return min(p, 256)

    def _draw_world_proximity_links(self) -> None:
        """FEATURE-MAP-WORLD-004/008: draw lines between node centers within WORLD_EDGE_SNAP_TILES (same rule as export)."""
        wl = _load_world_layout_py_module()
        z = max(WORLD_CAM_ZOOM_MIN, min(WORLD_CAM_ZOOM_MAX, self.world_cam_zoom))
        nodes = self.world_nodes
        for i in range(len(nodes)):
            a = nodes[i]
            ax0, ay0, ax1, ay1 = self._world_node_bounds(a)
            for j in range(i + 1, len(nodes)):
                b = nodes[j]
                bx0, by0, bx1, by1 = self._world_node_bounds(b)
                sep = float(wl.aabb_separation(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1))
                if sep <= WORLD_EDGE_SNAP_TILES:
                    cxa = (ax0 + ax1) * 0.5
                    cya = (ay0 + ay1) * 0.5
                    cxb = (bx0 + bx1) * 0.5
                    cyb = (by0 + by1) * 0.5
                    s1x, s1y = self._world_world_to_screen(cxa, cya)
                    s2x, s2y = self._world_world_to_screen(cxb, cyb)
                    lw = max(1, min(3, max(2, int(z))))
                    pygame.draw.line(self.screen, (70, 220, 140), (s1x, s1y), (s2x, s2y), lw)

    def _draw_world_workspace(self) -> None:
        r = self.map_canvas_rect
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(r.clip(prev_clip))
        try:
            pygame.draw.rect(self.screen, (26, 28, 34), r)
            pygame.draw.rect(self.screen, (70, 72, 88), r, 1)
            z = max(WORLD_CAM_ZOOM_MIN, min(WORLD_CAM_ZOOM_MAX, self.world_cam_zoom))
            step = self._world_grid_step_for_zoom(z, r)
            gx0 = int(self.world_cam_x // step) * step
            gy0 = int(self.world_cam_y // step) * step
            for wx in range(int(gx0 - step), int(gx0 + (r.w / z) + step * 2), step):
                sx0, sy0 = self._world_world_to_screen(wx, self.world_cam_y)
                sx1, sy1 = self._world_world_to_screen(wx, self.world_cam_y + r.h / z + 8)
                pygame.draw.line(self.screen, (44, 46, 56), (sx0, sy0), (sx1, sy1), 1)
            for wy in range(int(gy0 - step), int(gy0 + (r.h / z) + step * 2), step):
                sx0, sy0 = self._world_world_to_screen(self.world_cam_x, wy)
                sx1, sy1 = self._world_world_to_screen(self.world_cam_x + r.w / z + 8, wy)
                pygame.draw.line(self.screen, (44, 46, 56), (sx0, sy0), (sx1, sy1), 1)
            self._draw_world_proximity_links()
            for i, n in enumerate(self.world_nodes):
                stem = str(n.get("mapId", ""))
                thumb = self._ensure_world_thumbnail(stem)
                if thumb is None:
                    continue
                x0, y0 = self._world_world_to_screen(float(n["worldX"]), float(n["worldY"]))
                w = int(float(n["widthPx"]) * z)
                h = int(float(n["heightPx"]) * z)
                w = max(4, w)
                h = max(4, h)
                dst = pygame.Rect(x0, y0, w, h)
                if not r.colliderect(dst):
                    continue
                scaled = pygame.transform.scale(thumb, (w, h)) if (w, h) != thumb.get_size() else thumb
                self.screen.blit(scaled, dst.topleft)
                if n.get("interior"):
                    bcol = (255, 170, 90)
                elif i == self.world_drag_node_i:
                    bcol = (120, 200, 255)
                else:
                    bcol = (90, 95, 115)
                pygame.draw.rect(self.screen, bcol, dst, 2)
                if self.world_map_labels_visible:
                    self._world_blit_map_label(dst, stem, z)
        finally:
            self.screen.set_clip(prev_clip)

    def keys_for(self, action: str) -> str:
        vals = self.key_config.get(action, [])
        return "/".join(vals) if vals else "-"

    def key_primary(self, action: str) -> str:
        """IMPROVEMENT-MAP-004: first binding for help text only."""
        vals = self.key_config.get(action, [])
        return vals[0] if vals else "—"

    def quickstart_steps(self) -> list[tuple[bool, str]]:
        has_tileset = len(self.tileset_defs) > 0
        has_brush = bool(self.brush_pattern and self.brush_pattern[0])
        has_paint = any(
            cell is not None
            for grid in self.tile_layers
            for row in grid
            for cell in row
        )
        has_flags = any(v == 1 for row in self.walk for v in row) or any(v == 1 for row in self.trans for v in row)
        tab_k = self.key_primary("cycle_mode")
        return [
            (has_tileset, f"1) Import tileset ({self.key_primary('import_tileset')})"),
            (has_brush, "2) Make brush (drag on palette)"),
            (has_paint, "3) Paint room (left/right drag on map)"),
            (
                has_flags,
                f"4) Walk (click/drag) / transparency ({tab_k}) — Undo {self.key_primary('undo')} Redo {self.key_primary('redo')}",
            ),
            (
                self.saved_once,
                f"5) Save ({self.key_primary('save')}/Ctrl+S), Save As Shift+S, Open {self.key_primary('open_map')}",
            ),
        ]

    def refresh_map_file_list(self) -> None:
        ensure_maps_dir()
        self.map_files = sorted(
            p
            for p in MAPS_DIR.glob("*.json")
            if p.name != MAPS_INDEX_NAME and p.name != WORLD_LAYOUT_JSON_NAME
        )
        if not self.map_files:
            self.map_file_index = 0
            return
        for i, p in enumerate(self.map_files):
            if p.stem == self.map_id:
                self.map_file_index = i
                return
        self.map_file_index = 0

    def _alloc_walk_trans(self) -> None:
        w, h = self.map_w, self.map_h
        self.walk = [[0 for _ in range(w)] for _ in range(h)]
        self.trans = [[0 for _ in range(w)] for _ in range(h)]

    def _reset_tile_layers_single(self) -> None:
        w, h = self.map_w, self.map_h
        self.tile_layers = [[[None for _ in range(w)] for _ in range(h)]]
        self.tile_layer_ids = ["ground"]
        self.active_layer_index = 0

    def _alloc_layers(self) -> None:
        self._alloc_walk_trans()
        self._reset_tile_layers_single()

    def _active_grid(self) -> list[list[dict | None]]:
        return self.tile_layers[self.active_layer_index]

    def _unique_layer_id(self) -> str:
        n = 1
        while True:
            cand = f"layer_{n}"
            if cand not in self.tile_layer_ids:
                return cand
            n += 1

    def new_map(self, reset_connections: bool) -> None:
        self._alloc_layers()
        self.brush_pattern = [[(self.active_tileset_id, 1)]]
        self._refresh_brush_palette_outline()
        if reset_connections:
            self.connections = empty_connections()
        self._clear_undo_stacks()
        self._map_disk_backing_id = None
        self.saved_once = False

    def resize_map(self, nw: int, nh: int) -> None:
        nw, nh = max(1, min(MAP_SIZE_MAX, nw)), max(1, min(MAP_SIZE_MAX, nh))
        old_tls = self.tile_layers
        old_ids = list(self.tile_layer_ids)
        old_ai = self.active_layer_index
        old_w = self.walk
        old_t = self.trans
        self.map_w, self.map_h = nw, nh
        self._alloc_walk_trans()
        new_tls: list[list[list[dict | None]]] = []
        if not old_tls:
            self._reset_tile_layers_single()
        else:
            for old_g in old_tls:
                g = [[None for _ in range(nw)] for _ in range(nh)]
                for y in range(min(nh, len(old_g))):
                    for x in range(min(nw, len(old_g[y]))):
                        g[y][x] = old_g[y][x]
                new_tls.append(g)
            self.tile_layers = new_tls
            self.tile_layer_ids = old_ids[: len(self.tile_layers)]
            while len(self.tile_layer_ids) < len(self.tile_layers):
                self.tile_layer_ids.append(self._unique_layer_id())
            self.active_layer_index = min(max(0, old_ai), len(self.tile_layers) - 1)
        for y in range(min(nh, len(old_w))):
            for x in range(min(nw, len(old_w[y]))):
                self.walk[y][x] = old_w[y][x]
                self.trans[y][x] = old_t[y][x]
        self._clear_undo_stacks()

    def parse_size_and_apply(self) -> None:
        """Apply WIDTHxHEIGHT from the map size prompt (see set_map_size key). BUG-MAP-003."""
        s = self.text_buffer.strip().lower().replace(" ", "")
        self.text_buffer = ""
        self.size_prompt_active = False
        if "x" not in s:
            return
        try:
            a, b = s.split("x", 1)
            nw, nh = int(a), int(b)
            self.resize_map(nw, nh)
        except ValueError:
            pass

    def _session_editor_cache_key(self) -> str:
        if self._map_disk_backing_id:
            return sanitize_map_id(str(self._map_disk_backing_id))
        return sanitize_map_id(self.map_id)

    def _snapshot_session_map_bundle(self) -> dict:
        return {
            "map_id": self.map_id,
            "map_name": self.map_name,
            "tileset_index": self.tileset_index,
            "map_w": self.map_w,
            "map_h": self.map_h,
            "tw": self.tw,
            "th": self.th,
            "tile_layers": copy.deepcopy(self.tile_layers),
            "tile_layer_ids": list(self.tile_layer_ids),
            "walk": [row[:] for row in self.walk],
            "trans": [row[:] for row in self.trans],
            "active_layer_index": self.active_layer_index,
            "connections": copy.deepcopy(self.connections),
            "brush_pattern": copy.deepcopy(self.brush_pattern),
            "saved_once": self.saved_once,
            "disk_backing": self._map_disk_backing_id,
        }

    def _restore_session_map_bundle(self, s: dict) -> None:
        self.map_id = str(s["map_id"])
        self.map_name = str(s["map_name"])
        n_ts = len(self.tileset_defs)
        self.tileset_index = int(s["tileset_index"]) % n_ts if n_ts else 0
        self.map_w = int(s["map_w"])
        self.map_h = int(s["map_h"])
        self.tw = int(s["tw"])
        self.th = int(s["th"])
        self.tile_layers = copy.deepcopy(s["tile_layers"])
        self.tile_layer_ids = list(s["tile_layer_ids"])
        self.walk = [row[:] for row in s["walk"]]
        self.trans = [row[:] for row in s["trans"]]
        self.active_layer_index = int(s["active_layer_index"])
        self.connections = copy.deepcopy(s.get("connections", empty_connections()))
        self.brush_pattern = copy.deepcopy(s.get("brush_pattern", [[(self.current_tileset_id(), 1)]]))
        self.saved_once = bool(s.get("saved_once", False))
        self._map_disk_backing_id = s.get("disk_backing")
        self.reload_tileset_sheet()
        self._clear_undo_stacks()
        self._refresh_brush_palette_outline()

    def _stash_current_map_for_session_switch(self, target_cache_key: str) -> None:
        cur = self._session_editor_cache_key()
        if cur == target_cache_key:
            return
        self._session_map_cache[cur] = self._snapshot_session_map_bundle()

    def try_load_map_by_id(self, map_id: str) -> None:
        path = MAPS_DIR / f"{map_id}.json"
        if not path.is_file():
            return
        target_key = sanitize_map_id(path.stem)
        self._stash_current_map_for_session_switch(target_key)
        if target_key in self._session_map_cache:
            self._restore_session_map_bundle(self._session_map_cache[target_key])
            return
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
        self.map_id = m.get("id", path.stem)
        self.map_name = m.get("name", self.map_id)
        tid = m.get("tilesetId")
        for i, d in enumerate(self.tileset_defs):
            if d.get("id") == tid:
                self.tileset_index = i
                break
        self.reload_tileset_sheet()
        self.map_w = int(m.get("width", 12))
        self.map_h = int(m.get("height", 10))
        self.tw = int(m.get("tileWidth", self.tw))
        self.th = int(m.get("tileHeight", self.th))
        layers = m.get("layers", {})
        self._alloc_walk_trans()
        self.tile_layers = []
        self.tile_layer_ids = []
        self.active_layer_index = 0
        tls = layers.get("tileLayers")
        if isinstance(tls, list) and len(tls) > 0:
            seen_ids: set[str] = set()

            def _uniq_lid(base: str) -> str:
                lid = base
                n = 2
                while lid in seen_ids:
                    lid = f"{base}_{n}"
                    n += 1
                seen_ids.add(lid)
                return lid

            for entry in tls:
                if not isinstance(entry, dict):
                    continue
                lid = _uniq_lid(str(entry.get("id", "layer")))
                cells_data = entry.get("cells")
                grid = [[None for _ in range(self.map_w)] for _ in range(self.map_h)]
                if isinstance(cells_data, list):
                    for y, row in enumerate(cells_data):
                        if y >= self.map_h:
                            break
                        if not isinstance(row, list):
                            continue
                        for x, cell in enumerate(row):
                            if x >= self.map_w:
                                break
                            if cell is None:
                                grid[y][x] = None
                            elif isinstance(cell, dict):
                                grid[y][x] = {
                                    "ts": str(cell.get("ts", tid)),
                                    "t": int(cell.get("t", 0)),
                                }
                self.tile_layers.append(grid)
                self.tile_layer_ids.append(lid)
            if not self.tile_layers:
                self._reset_tile_layers_single()
            else:
                self.active_layer_index = min(self.active_layer_index, len(self.tile_layers) - 1)
        else:
            self._reset_tile_layers_single()
            g = self._active_grid()
            if "groundCells" in layers and layers["groundCells"]:
                for y, row in enumerate(layers["groundCells"]):
                    if y >= self.map_h:
                        break
                    for x, cell in enumerate(row):
                        if x >= self.map_w:
                            break
                        if cell is None:
                            g[y][x] = None
                        elif isinstance(cell, dict):
                            g[y][x] = {
                                "ts": str(cell.get("ts", tid)),
                                "t": int(cell.get("t", 0)),
                            }
            else:
                gr = layers.get("ground", [])
                for y, row in enumerate(gr):
                    if y >= self.map_h:
                        break
                    for x, v in enumerate(row):
                        if x >= self.map_w:
                            break
                        vi = int(v)
                        g[y][x] = None if vi == 0 else {"ts": tid, "t": vi}
        for name, tgt in (("walkability", self.walk), ("transparent", self.trans)):
            arr = layers.get(name)
            if isinstance(arr, list):
                for y, row in enumerate(arr):
                    if y >= self.map_h:
                        break
                    for x, v in enumerate(row):
                        if x >= self.map_w:
                            break
                        tgt[y][x] = int(v) & 1
        self.connections = empty_connections()
        for s in SIDES:
            c = m.get("connections", {}).get(s, {})
            if isinstance(c, dict):
                self.connections[s] = {
                    "mapId": str(c.get("mapId", "")),
                    "entryTileX": int(c.get("entryTileX", 0)),
                    "entryTileY": int(c.get("entryTileY", 0)),
                }
        self._clear_undo_stacks()
        self._map_disk_backing_id = path.stem
        self.saved_once = True

    def _write_map_json_to_disk(self, map_id: str) -> None:
        ensure_maps_dir()
        path = MAPS_DIR / f"{map_id}.json"
        tid = self.tileset_defs[self.tileset_index].get("id", "boat")
        tile_layers_out: list[dict] = []
        for li, grid in enumerate(self.tile_layers):
            lid = (
                self.tile_layer_ids[li]
                if li < len(self.tile_layer_ids)
                else f"layer_{li + 1}"
            )
            cells = [
                [
                    None
                    if grid[y][x] is None
                    else {"ts": str(grid[y][x]["ts"]), "t": int(grid[y][x]["t"])}
                    for x in range(self.map_w)
                ]
                for y in range(self.map_h)
            ]
            tile_layers_out.append({"id": lid, "cells": cells})
        layers: dict = {
            "tileLayers": tile_layers_out,
            "walkability": self.walk,
            "transparent": self.trans,
        }
        data = {
            "version": 3,
            "id": map_id,
            "name": self.map_name,
            "tilesetId": tid,
            "width": self.map_w,
            "height": self.map_h,
            "tileWidth": self.tw,
            "tileHeight": self.th,
            "layers": layers,
            "connections": dict(self.connections),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        print(f"Saved {path}")
        self.saved_once = True
        self._map_disk_backing_id = map_id
        write_maps_index()
        self._session_map_cache.pop(sanitize_map_id(map_id), None)

    def save(self) -> None:
        if not self.saved_once:
            self.map_file_prompt_mode = "first_save"
            self.map_file_prompt_buffer = self.map_id
            self._map_save_pending_is_save_as = False
            return
        mid = sanitize_map_id(self.map_id)
        self.map_id = mid
        self._write_map_json_to_disk(mid)

    def save_as(self) -> None:
        self.map_file_prompt_mode = "save_as"
        self.map_file_prompt_buffer = f"{self.map_id}_copy"
        self._map_save_pending_is_save_as = True

    def _try_commit_map_prompt(self) -> None:
        if self.map_file_prompt_mode != "first_save" and self.map_file_prompt_mode != "save_as":
            return
        cand = sanitize_map_id(self.map_file_prompt_buffer)
        if not cand:
            self.set_status("Invalid map id.", kind="err")
            return
        path = MAPS_DIR / f"{cand}.json"
        is_save_as = self._map_save_pending_is_save_as
        if path.is_file():
            if (
                not is_save_as
                and cand == self._map_disk_backing_id
                and self.map_file_prompt_mode == "first_save"
            ):
                self._finalize_map_save(cand, False)
                return
            if is_save_as or cand != self.map_id or not self.saved_once:
                self.map_overwrite_candidate_id = cand
                self.map_file_prompt_mode = "overwrite"
                return
        self._finalize_map_save(cand, is_save_as)

    def _confirm_map_overwrite(self) -> None:
        cid = self.map_overwrite_candidate_id
        if not cid:
            return
        was_save_as = self._map_save_pending_is_save_as
        self.map_overwrite_candidate_id = None
        self.map_file_prompt_mode = None
        self.map_file_prompt_buffer = ""
        self._finalize_map_save(cid, was_save_as)

    def _cancel_map_prompt(self) -> None:
        self.map_file_prompt_mode = None
        self.map_file_prompt_buffer = ""
        self.map_overwrite_candidate_id = None
        self._map_save_pending_is_save_as = False

    def _finalize_map_save(self, cand: str, is_save_as: bool) -> None:
        if is_save_as:
            self._clear_undo_stacks()
        prev_map_id = self.map_id
        prev_backing = self._map_disk_backing_id
        self.map_id = cand
        self.map_name = cand
        self._write_map_json_to_disk(cand)
        if is_save_as:
            old_k = sanitize_map_id(str(prev_backing or prev_map_id))
            if old_k != sanitize_map_id(cand):
                self._session_map_cache.pop(old_k, None)
        self.map_file_prompt_mode = None
        self.map_overwrite_candidate_id = None
        self.map_file_prompt_buffer = ""
        self._map_save_pending_is_save_as = False
        self.refresh_map_file_list()
        self.set_status(f"Saved map as {cand}", kind="ok")

    def open_map_interactive(self) -> None:
        # BUG-MAP-008: osascript choose file from pygame often returns no path on macOS; use overlay everywhere (like Linux/Windows).
        ensure_maps_dir()
        stems = sorted(
            p.stem for p in MAPS_DIR.glob("*.json") if p.name != MAPS_INDEX_NAME and p.name != WORLD_LAYOUT_JSON_NAME
        )
        if not stems:
            self.set_status("No maps in src/maps.", kind="err")
            return
        self.open_map_stems = stems
        self.open_map_sel = 0
        for i, s in enumerate(stems):
            if s == self.map_id:
                self.open_map_sel = i
                break
        self.open_map_scroll = 0
        self.open_map_overlay = True
        self.open_map_purpose = "load"
        self.set_status("Open map: ↑↓ Enter to load · Esc cancel", kind="info")

    def _open_map_load_selected(self) -> None:
        if not self.open_map_stems or not (0 <= self.open_map_sel < len(self.open_map_stems)):
            self.open_map_overlay = False
            self.open_map_purpose = "load"
            return
        stem = self.open_map_stems[self.open_map_sel]
        purpose = self.open_map_purpose
        self.open_map_overlay = False
        self.open_map_purpose = "load"
        if purpose == "world":
            if self._world_add_node_from_map_id(stem):
                self.set_status(f"World: added map '{stem}'", kind="ok")
            return
        self.try_load_map_by_id(stem)
        self.refresh_map_file_list()
        self.set_status(f"Opened {stem}", kind="ok")

    def _open_map_visible_rows(self) -> int:
        h = self.screen.get_height()
        bh = min(480, h - 80)
        lh = self.font_small.get_linesize() + 4
        return max(1, (bh - 44 - 14) // lh)

    def _sync_open_map_scroll(self) -> None:
        visible = self._open_map_visible_rows()
        n = len(self.open_map_stems)
        self.open_map_scroll = max(0, min(self.open_map_scroll, max(0, n - visible)))
        self.open_map_sel = max(0, min(self.open_map_sel, max(0, n - 1)))
        if self.open_map_sel < self.open_map_scroll:
            self.open_map_scroll = self.open_map_sel
        if n > 0 and self.open_map_sel >= self.open_map_scroll + visible:
            self.open_map_scroll = self.open_map_sel - visible + 1

    def _ensure_editor_tileset_order(self) -> None:
        ed = self.registry.get("editorTilesetFolders")
        if not isinstance(ed, dict):
            self.registry["editorTilesetFolders"] = {
                "version": 1,
                "folders": [],
                "order": [{"kind": "tileset", "id": str(t.get("id"))} for t in self.tileset_defs if t.get("id")],
                "collapsed": [],
            }
            return
        if not ed.get("order"):
            ed["order"] = [{"kind": "tileset", "id": str(t.get("id"))} for t in self.tileset_defs if t.get("id")]
        if "collapsed" not in ed:
            ed["collapsed"] = []
        if "folders" not in ed:
            ed["folders"] = []
        ord_list = ed.get("order")
        if isinstance(ord_list, list) and _migrate_implicit_in_folder_on_order(ord_list):
            write_tilesets_registry(TILESETS_JSON, self.registry)

    def _editor_folder_blob(self) -> dict:
        self._ensure_editor_tileset_order()
        ed = self.registry["editorTilesetFolders"]
        assert isinstance(ed, dict)
        return ed

    def _build_tileset_list_rows(self) -> list[dict]:
        ed = self._editor_folder_blob()
        order = list(ed.get("order") or [])
        collapsed: set[str] = set(str(x) for x in (ed.get("collapsed") or []))
        folder_meta: dict[str, dict] = {}
        for f in ed.get("folders") or []:
            if isinstance(f, dict) and f.get("id"):
                folder_meta[str(f["id"])] = f
        folder_ids = set(folder_meta.keys())
        in_order_ts: set[str] = set()
        rows: list[dict] = []
        for ent in order:
            if not isinstance(ent, dict):
                continue
            k = ent.get("kind")
            eid = str(ent.get("id", "")) if ent.get("id") is not None else ""
            if k == "folder" and eid:
                fm = folder_meta.get(eid, {"name": eid, "color": [70, 90, 120]})
                name = str(fm.get("name", eid))
                col = fm.get("color")
                if not isinstance(col, list) or len(col) < 3:
                    col = [70, 90, 120]
                color = (int(col[0]) % 256, int(col[1]) % 256, int(col[2]) % 256)
                is_collapsed = eid in collapsed
                rows.append(
                    {
                        "row_kind": "folder",
                        "folder_id": eid,
                        "name": name,
                        "color": color,
                        "collapsed": is_collapsed,
                        "indent_px": 0,
                    }
                )
            elif k == "tileset" and eid:
                in_order_ts.add(eid)
                parent = _order_tileset_parent_folder(ent)
                indent_px = 0
                hide = False
                if parent:
                    if parent not in folder_ids:
                        indent_px = 0
                    elif parent in collapsed:
                        hide = True
                    else:
                        indent_px = TILESET_LIST_CHILD_INDENT_PX
                if hide:
                    continue
                idx = next(
                    (i for i, d in enumerate(self.tileset_defs) if str(d.get("id")) == eid),
                    None,
                )
                if idx is not None:
                    rows.append(
                        {
                            "row_kind": "tileset",
                            "def_index": idx,
                            "id": eid,
                            "indent_px": indent_px,
                            "in_folder": parent,
                        }
                    )
        unfiled = [
            i
            for i, d in enumerate(self.tileset_defs)
            if str(d.get("id", "")) not in in_order_ts
        ]
        if unfiled:
            rows.append({"row_kind": "section", "name": "Unfiled", "indent_px": 0})
            for idx in unfiled:
                tid = str(self.tileset_defs[idx].get("id", ""))
                rows.append(
                    {
                        "row_kind": "tileset",
                        "def_index": idx,
                        "id": tid,
                        "indent_px": 0,
                        "in_folder": None,
                    }
                )
        return rows

    def _folder_order_replace_tileset_id(self, old_id: str, new_id: str) -> None:
        ed = self._editor_folder_blob()
        for ent in ed.get("order") or []:
            if isinstance(ent, dict) and ent.get("kind") == "tileset" and str(ent.get("id")) == old_id:
                ent["id"] = new_id
        write_tilesets_registry(TILESETS_JSON, self.registry)

    def _folder_order_remove_tileset_id(self, ts_id: str) -> None:
        ed = self._editor_folder_blob()
        order = [e for e in (ed.get("order") or []) if not (isinstance(e, dict) and e.get("kind") == "tileset" and str(e.get("id")) == ts_id)]
        ed["order"] = order
        write_tilesets_registry(TILESETS_JSON, self.registry)

    def _tileset_order_index_for_def_index(self, def_index: int) -> int | None:
        if not (0 <= def_index < len(self.tileset_defs)):
            return None
        tid = str(self.tileset_defs[def_index].get("id", ""))
        ed = self._editor_folder_blob()
        for i, ent in enumerate(ed.get("order") or []):
            if isinstance(ent, dict) and ent.get("kind") == "tileset" and str(ent.get("id")) == tid:
                return i
        return None

    def _move_tileset_in_order(self, def_index: int, delta: int) -> None:
        oi = self._tileset_order_index_for_def_index(def_index)
        if oi is None:
            return
        ed = self._editor_folder_blob()
        order = list(ed.get("order") or [])
        if not (0 <= oi < len(order)):
            return
        ni = oi + delta
        if not (0 <= ni < len(order)):
            return
        if order[oi].get("kind") != "tileset" or order[ni].get("kind") != "tileset":
            return
        order[oi], order[ni] = order[ni], order[oi]
        ed["order"] = order
        write_tilesets_registry(TILESETS_JSON, self.registry)

    def add_tileset_folder(self) -> None:
        # BUG-FOLDER-001: display dialog via osascript returned "" under pygame on macOS (~instant);
        # use the same pygame overlay as other platforms (FEATURE-MAP-013).
        self.folder_new_prompt_active = True
        self.folder_new_prompt_buffer = ""

    def _commit_tileset_folder(self, name: str) -> None:
        label = name.strip()[:64] or "Folder"
        ed = self._editor_folder_blob()
        folders = list(ed.get("folders") or [])
        fid = uuid.uuid4().hex[:12]
        folders.append({"id": fid, "name": label, "color": [80, 110, 140]})
        order = list(ed.get("order") or [])
        order.append({"kind": "folder", "id": fid})
        ed["folders"] = folders
        ed["order"] = order
        write_tilesets_registry(TILESETS_JSON, self.registry)
        self.set_status(f"Folder '{label}' created.", kind="ok")

    def _apply_folder_rename(self) -> None:
        fid = self.folder_rename_id
        if not fid:
            return
        name = self.folder_rename_buffer.strip()[:64]
        if not name:
            self.set_status("Folder name empty.", kind="err")
            return
        ed = self._editor_folder_blob()
        for f in ed.get("folders") or []:
            if isinstance(f, dict) and str(f.get("id")) == fid:
                f["name"] = name
                write_tilesets_registry(TILESETS_JSON, self.registry)
                self.folder_rename_id = None
                self.folder_rename_buffer = ""
                self.set_status(f"Renamed folder to '{name}'.", kind="ok")
                return
        self.folder_rename_id = None
        self.folder_rename_buffer = ""

    def _apply_folder_color_prompt(self) -> None:
        fid = self.folder_color_prompt_id
        if not fid:
            return
        raw = self.folder_color_prompt_buffer.strip()
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) != 3:
            self.set_status("Need three numbers R,G,B.", kind="err")
            return
        try:
            rgb = [max(0, min(255, int(parts[i]))) for i in range(3)]
        except ValueError:
            self.set_status("Invalid RGB.", kind="err")
            return
        ed = self._editor_folder_blob()
        for f in ed.get("folders") or []:
            if isinstance(f, dict) and str(f.get("id")) == fid:
                f["color"] = rgb
                write_tilesets_registry(TILESETS_JSON, self.registry)
                self.folder_color_prompt_id = None
                self.folder_color_prompt_buffer = ""
                self.set_status("Folder color updated.", kind="ok")
                return
        self.folder_color_prompt_id = None
        self.folder_color_prompt_buffer = ""

    def _toggle_folder_collapse(self, folder_id: str) -> None:
        ed = self._editor_folder_blob()
        col = list(ed.get("collapsed") or [])
        s = set(str(x) for x in col)
        if folder_id in s:
            s.remove(folder_id)
        else:
            s.add(folder_id)
        ed["collapsed"] = sorted(s)
        write_tilesets_registry(TILESETS_JSON, self.registry)

    def _prompt_folder_color(self, folder_id: str) -> None:
        ed = self._editor_folder_blob()
        fm = None
        for f in ed.get("folders") or []:
            if isinstance(f, dict) and str(f.get("id")) == folder_id:
                fm = f
                break
        if not fm:
            return
        col = fm.get("color", [80, 110, 140])
        default = f"{col[0]},{col[1]},{col[2]}" if isinstance(col, list) and len(col) >= 3 else "80,110,140"
        if sys.platform == "darwin":
            raw = _macos_dialog_text("Folder color R,G,B (0-255):", default)
            if raw is None:
                return
            parts = [p.strip() for p in raw.split(",")]
            if len(parts) != 3:
                self.set_status("Need three numbers R,G,B.", kind="err")
                return
            try:
                rgb = [max(0, min(255, int(parts[i]))) for i in range(3)]
            except ValueError:
                self.set_status("Invalid RGB.", kind="err")
                return
            fm["color"] = rgb
            write_tilesets_registry(TILESETS_JSON, self.registry)
            return
        self.folder_color_prompt_id = folder_id
        self.folder_color_prompt_buffer = default

    def _tileset_list_hit(self, px: int, py: int) -> tuple[str, object | None]:
        if not self.tileset_list_rect.collidepoint(px, py):
            return ("none", None)
        rows = self._build_tileset_list_rows()
        rh = self._tileset_list_row_h()
        top = self.tileset_list_rect.y + 4 + self._tileset_list_header_h
        bottom = self.tileset_list_rect.bottom - 4
        if py < top or py >= bottom:
            return ("none", None)
        rel_y = py - top + self.tileset_list_scroll_y
        if rel_y < 0:
            return ("none", None)
        ridx = int(rel_y // rh)
        if not (0 <= ridx < len(rows)):
            return ("none", None)
        row = rows[ridx]
        rk = row["row_kind"]
        if rk == "section":
            return ("section", None)
        if rk == "folder":
            chevron = px < self.tileset_list_rect.x + 24
            return ("folder", (row["folder_id"], chevron))
        return ("tileset", row["def_index"])

    def _tileset_list_row_index_at_pixel(self, px: int, py: int) -> int | None:
        if not self.tileset_list_rect.collidepoint(px, py):
            return None
        rows = self._build_tileset_list_rows()
        rh = self._tileset_list_row_h()
        top = self.tileset_list_rect.y + 4 + self._tileset_list_header_h
        bottom = self.tileset_list_rect.bottom - 4
        if py < top or py >= bottom:
            return None
        rel_y = py - top + self.tileset_list_scroll_y
        if rel_y < 0:
            return None
        ridx = int(rel_y // rh)
        if 0 <= ridx < len(rows):
            return ridx
        return None

    def _measure_tileset_list_header_height(self) -> int:
        """Must match tileset header block in draw() (including wrapped title width)."""
        pad = 6
        list_r = self.tileset_list_rect
        hx = list_r.x + 6
        hw = max(80, list_r.w - 12)
        hint_w = max(40, list_r.w - 28)
        btn_left = list_r.right - 86
        title_w = max(40, min(hw, btn_left - hx - 8))
        lh_title = self.font.get_linesize()
        lsh = self.font_small.get_linesize()
        n_title = len(_wrap_lines_to_width(self.font, "Tilesets", title_w))
        n1 = len(_wrap_lines_to_width(self.font_small, _TILESET_LIST_HINT_1, hint_w))
        n2 = len(_wrap_lines_to_width(self.font_small, _TILESET_LIST_HINT_2, hint_w))
        n3 = len(_wrap_lines_to_width(self.font_small, _TILESET_LIST_HINT_3, hint_w))
        return (
            pad
            + n_title * lh_title
            + _TILESET_LIST_HINT_GAP_AFTER_TITLE
            + n1 * lsh
            + 4
            + n2 * lsh
            + 2
            + n3 * lsh
            + 4
        )

    def _clear_tileset_list_drag(self) -> None:
        self._tileset_drag_def_index = None
        self._tileset_drag_start = None
        self._tileset_drag_moved = False

    def _clear_folder_list_drag(self) -> None:
        self._folder_drag_id = None
        self._folder_drag_start = None
        self._folder_drag_moved = False

    def _clear_all_list_drags(self) -> None:
        self._clear_tileset_list_drag()
        self._clear_folder_list_drag()

    def _move_tileset_into_folder_order(self, ts_id: str, folder_id: str) -> None:
        ed = self._editor_folder_blob()
        order = [e for e in (ed.get("order") or []) if isinstance(e, dict)]
        order = [e for e in order if not (e.get("kind") == "tileset" and str(e.get("id")) == ts_id)]
        fi = None
        for i, e in enumerate(order):
            if e.get("kind") == "folder" and str(e.get("id")) == folder_id:
                fi = i
                break
        if fi is None:
            self.set_status("Folder not in list order.", kind="err")
            return
        ni = len(order)
        for j in range(fi + 1, len(order)):
            if order[j].get("kind") == "folder":
                ni = j
                break
        new_ent = {"kind": "tileset", "id": ts_id}
        _order_set_tileset_parent(new_ent, folder_id)
        order.insert(ni, new_ent)
        ed["order"] = order
        write_tilesets_registry(TILESETS_JSON, self.registry)
        self.set_status(f"Moved '{ts_id}' into folder.", kind="ok")

    def _append_tileset_to_order_end(self, ts_id: str) -> None:
        ed = self._editor_folder_blob()
        order = [e for e in (ed.get("order") or []) if isinstance(e, dict)]
        order = [e for e in order if not (e.get("kind") == "tileset" and str(e.get("id")) == ts_id)]
        root_ent = {"kind": "tileset", "id": ts_id}
        _order_set_tileset_parent(root_ent, None)
        order.append(root_ent)
        ed["order"] = order
        write_tilesets_registry(TILESETS_JSON, self.registry)
        self.set_status(f"Moved '{ts_id}' to list end.", kind="ok")

    def _move_tileset_root_before_folder(self, ts_id: str, folder_id: str) -> None:
        """BUG-MAP-010: Insert tileset as root (no in_folder) immediately before the folder row."""
        ed = self._editor_folder_blob()
        order = [e for e in (ed.get("order") or []) if isinstance(e, dict)]
        order = [e for e in order if not (e.get("kind") == "tileset" and str(e.get("id")) == ts_id)]
        fi = None
        for i, e in enumerate(order):
            if e.get("kind") == "folder" and str(e.get("id")) == folder_id:
                fi = i
                break
        if fi is None:
            self.set_status("Folder not in list order.", kind="err")
            return
        new_ent = {"kind": "tileset", "id": ts_id}
        _order_set_tileset_parent(new_ent, None)
        order.insert(fi, new_ent)
        ed["order"] = order
        write_tilesets_registry(TILESETS_JSON, self.registry)
        self.set_status(f"Moved '{ts_id}' to root (before folder).", kind="ok")

    def _move_tileset_before_in_order(self, ts_id: str, before_ts_id: str) -> None:
        ed = self._editor_folder_blob()
        order = [e for e in (ed.get("order") or []) if isinstance(e, dict)]
        order = [e for e in order if not (e.get("kind") == "tileset" and str(e.get("id")) == ts_id)]
        bi = None
        tgt_parent: str | None = None
        for i, e in enumerate(order):
            if e.get("kind") == "tileset" and str(e.get("id")) == before_ts_id:
                bi = i
                if isinstance(e, dict):
                    tgt_parent = _order_tileset_parent_folder(e)
                break
        if bi is None:
            self.set_status("Drop target not in ordered list.", kind="err")
            return
        new_ent = {"kind": "tileset", "id": ts_id}
        _order_set_tileset_parent(new_ent, tgt_parent)
        order.insert(bi, new_ent)
        ed["order"] = order
        write_tilesets_registry(TILESETS_JSON, self.registry)
        self.set_status(f"Moved '{ts_id}'.", kind="ok")

    def _apply_tileset_list_drop(self, from_def_idx: int, px: int, py: int, mods: int = 0) -> None:
        if not (0 <= from_def_idx < len(self.tileset_defs)):
            return
        ts_id = str(self.tileset_defs[from_def_idx].get("id", ""))
        if not ts_id:
            return
        ridx = self._tileset_list_row_index_at_pixel(px, py)
        if ridx is None:
            return
        rows = self._build_tileset_list_rows()
        row = rows[ridx]
        rk = row["row_kind"]
        if rk == "tileset" and str(row["id"]) == ts_id:
            return
        alt = bool(mods & pygame.KMOD_ALT)
        if rk == "folder":
            fid = str(row["folder_id"])
            if alt:
                self._move_tileset_root_before_folder(ts_id, fid)
            else:
                self._move_tileset_into_folder_order(ts_id, fid)
        elif rk == "section":
            self._append_tileset_to_order_end(ts_id)
        elif rk == "tileset":
            self._move_tileset_before_in_order(ts_id, str(row["id"]))

    def _order_extract_folder_block(
        self, order: list[dict], folder_id: str
    ) -> tuple[list[dict], list[dict]]:
        """FEATURE-MAP-014: folder row + all tilesets with in_folder == folder_id (any positions)."""
        fid = str(folder_id)
        folder_slot: tuple[int, dict] | None = None
        child_slots: list[tuple[int, dict]] = []
        for i, e in enumerate(order):
            if not isinstance(e, dict):
                continue
            if e.get("kind") == "folder" and str(e.get("id")) == fid:
                folder_slot = (i, e)
            elif e.get("kind") == "tileset" and _order_tileset_parent_folder(e) == fid:
                child_slots.append((i, e))
        if folder_slot is None:
            return [], order
        _, folder_ent = folder_slot
        child_slots.sort(key=lambda x: x[0])
        remove_idx = {folder_slot[0]} | {i for i, _ in child_slots}
        block = [folder_ent] + [e for _, e in child_slots]
        rest = [e for i, e in enumerate(order) if i not in remove_idx]
        return block, rest

    def _row_in_dragged_folder_block(self, rows: list[dict], ridx: int, folder_id: str) -> bool:
        if not (0 <= ridx < len(rows)):
            return False
        row = rows[ridx]
        fk = str(folder_id)
        if row["row_kind"] == "folder" and str(row["folder_id"]) == fk:
            return True
        if row["row_kind"] == "tileset":
            return str(row.get("in_folder") or "") == fk
        return False

    def _order_insert_index_from_drop_row(
        self, rest: list[dict], rows: list[dict], ridx: int, dragged_folder_id: str
    ) -> int | None:
        if not (0 <= ridx < len(rows)):
            return None
        row = rows[ridx]
        rk = row["row_kind"]
        if rk == "folder":
            fid = str(row["folder_id"])
            if fid == dragged_folder_id:
                return None
            for i, e in enumerate(rest):
                if e.get("kind") == "folder" and str(e.get("id")) == fid:
                    return i
            return None
        if rk == "section":
            return len(rest)
        if rk == "tileset":
            tid = str(row["id"])
            for i, e in enumerate(rest):
                if e.get("kind") == "tileset" and str(e.get("id")) == tid:
                    return i
            return len(rest)
        return None

    def _apply_folder_block_drop(self, folder_id: str, px: int, py: int) -> None:
        ridx = self._tileset_list_row_index_at_pixel(px, py)
        if ridx is None:
            return
        rows = self._build_tileset_list_rows()
        if self._row_in_dragged_folder_block(rows, ridx, folder_id):
            return
        ed = self._editor_folder_blob()
        order = [e for e in (ed.get("order") or []) if isinstance(e, dict)]
        block, rest = self._order_extract_folder_block(order, folder_id)
        if not block:
            return
        ins = self._order_insert_index_from_drop_row(rest, rows, ridx, folder_id)
        if ins is None:
            return
        ed["order"] = rest[:ins] + block + rest[ins:]
        write_tilesets_registry(TILESETS_JSON, self.registry)
        self.set_status("Moved folder.", kind="ok")

    def _tileset_list_row_h(self) -> int:
        return self.font_small.get_linesize() * TILESET_LIST_ROW_LINES + 8

    def _tileset_list_row_inner_h(self) -> int:
        return self._tileset_list_row_h() - 2

    def _tileset_list_y_pad_single_line(self) -> int:
        """BUG-MAP-009: vertical center one line in row (row height fits TILESET_LIST_ROW_LINES)."""
        lh = self.font_small.get_linesize()
        inner = self._tileset_list_row_inner_h()
        return max(2, (inner - lh) // 2)

    def _tileset_list_y_pad_multiline(self, num_lines: int) -> int:
        lh = self.font_small.get_linesize()
        inner = self._tileset_list_row_inner_h()
        return max(2, (inner - num_lines * lh) // 2)

    def _tileset_id_lines(self, tid: str, indent_px: int = 0) -> list[str]:
        max_w = max(40, self.tileset_list_rect.w - 36 - indent_px)
        lines = _wrap_lines_to_width(self.font_small, tid, max_w)
        if not lines:
            return [""]
        if len(lines) <= TILESET_LIST_ROW_LINES:
            return lines
        first = lines[0]
        rest = " ".join(lines[1:])
        second = _truncate_with_ellipsis(self.font_small, rest, max_w)
        return [first, second]

    def _clamp_tileset_list_scroll(self) -> None:
        rh = self._tileset_list_row_h()
        n = len(self._build_tileset_list_rows())
        content_h = n * rh + 8
        visible = max(1, self.tileset_list_rect.h - 8 - self._tileset_list_header_h)
        max_scroll = max(0, content_h - visible)
        self.tileset_list_scroll_y = max(0, min(self.tileset_list_scroll_y, max_scroll))

    def _clamp_tileset_list_scroll_x(self) -> None:  # FEATURE-MAP-024
        inner_w = max(1, self.tileset_list_rect.w - 22)
        content_w = TILESET_LIST_W + TILESET_LIST_CHILD_INDENT_PX * 4
        max_scroll = max(0, content_w - inner_w)
        self.tileset_list_scroll_x = max(0, min(self.tileset_list_scroll_x, max_scroll))

    def apply_rename_tileset(self, old_id: str, new_id: str) -> bool:
        new_id = "".join(c if c.isalnum() or c in "._-" else "_" for c in new_id.strip())[:64]
        if not new_id:
            self.set_status("Rename: empty id", kind="err")
            return False
        if new_id == old_id:
            return True
        for t in self.tileset_defs:
            if t.get("id") == new_id:
                self.set_status("Rename: that id already exists", kind="err")
                return False
        reg = load_json(TILESETS_JSON)
        tss = reg.get("tilesets", [])
        found = False
        for t in tss:
            if t.get("id") == old_id:
                t["id"] = new_id
                found = True
                break
        if not found:
            return False
        self.registry = reg
        self._folder_order_replace_tileset_id(old_id, new_id)
        for grid in self.tile_layers:
            for y in range(self.map_h):
                for x in range(self.map_w):
                    c = grid[y][x]
                    if c is not None and c.get("ts") == old_id:
                        c["ts"] = new_id
        if self.brush_pattern:
            h = len(self.brush_pattern)
            bw = len(self.brush_pattern[0]) if h else 0
            for j in range(h):
                for i in range(bw):
                    ts, ti = self.brush_pattern[j][i]
                    if ts == old_id:
                        self.brush_pattern[j][i] = (new_id, ti)
        if old_id in self.sheet_cache:
            self.sheet_cache[new_id] = self.sheet_cache.pop(old_id)
        if old_id in self.meta_cache:
            self.meta_cache[new_id] = self.meta_cache.pop(old_id)
        self.registry = reg
        self.tileset_defs = list(reg.get("tilesets", []))
        for i, d in enumerate(self.tileset_defs):
            if d.get("id") == new_id:
                self.tileset_index = i
                break
        self.reload_tileset_sheet()
        self.set_status(f"Renamed tileset to {new_id}", kind="ok")
        return True

    def _tileset_image_path_safe(self, img_rel: str) -> Path | None:
        p = (ROOT / img_rel).resolve()
        try:
            p.relative_to(TILESETS_DIR.resolve())
        except ValueError:
            return None
        return p if p.is_file() else None

    def delete_tileset(self, ts_id: str) -> bool:
        if len(self.tileset_defs) <= 1:
            self.set_status("Cannot delete the last tileset.", kind="err")
            return False
        meta = self.get_tileset_meta(ts_id)
        if not meta:
            self.set_status("Tileset not found.", kind="err")
            return False
        img_rel = str(meta.get("image", ""))
        del_idx = -1
        for i, t in enumerate(self.tileset_defs):
            if t.get("id") == ts_id:
                del_idx = i
                break
        if del_idx < 0:
            return False
        was_idx = self.tileset_index

        reg = load_json(TILESETS_JSON)
        tss = [t for t in reg.get("tilesets", []) if t.get("id") != ts_id]
        reg["tilesets"] = tss
        others_same = sum(1 for t in tss if t.get("image") == img_rel)
        self.registry = reg
        self._folder_order_remove_tileset_id(ts_id)

        if others_same == 0:
            safe_p = self._tileset_image_path_safe(img_rel)
            if safe_p is not None:
                try:
                    safe_p.unlink()
                except OSError:
                    pass

        if ts_id in self.sheet_cache:
            del self.sheet_cache[ts_id]
        if ts_id in self.meta_cache:
            del self.meta_cache[ts_id]

        for grid in self.tile_layers:
            for y in range(self.map_h):
                for x in range(self.map_w):
                    c = grid[y][x]
                    if c is not None and c.get("ts") == ts_id:
                        grid[y][x] = None

        self.registry = reg
        self.tileset_defs = list(reg.get("tilesets", []))
        if was_idx == del_idx:
            self.tileset_index = min(del_idx, len(self.tileset_defs) - 1)
        elif was_idx > del_idx:
            self.tileset_index = was_idx - 1
        else:
            self.tileset_index = was_idx

        ts = self.current_tileset_id()
        if self.brush_pattern:
            h = len(self.brush_pattern)
            bw = len(self.brush_pattern[0]) if h else 0
            for j in range(h):
                for i in range(bw):
                    ots, oti = self.brush_pattern[j][i]
                    if ots == ts_id:
                        self.brush_pattern[j][i] = (ts, 1)
        if not self.brush_pattern or not self.brush_pattern[0]:
            self.brush_pattern = [[(ts, 1)]]

        self.reload_tileset_sheet()
        self._clamp_tileset_list_scroll()
        self.set_status(f"Deleted tileset '{ts_id}'.", kind="ok")
        return True

    def _palette_viewport_metrics(self) -> tuple[int, int, int, int, int, int]:
        """FEATURE-MAP-015: ox, oy, max_w, max_h, sw, sh (sheet px). sw=0 if no sheet."""
        title_h = 24
        ox = self.palette_rect.x + 4
        oy = self.palette_rect.y + 4 + title_h
        if self.sheet is None:
            return ox, oy, 1, 100, 0, 0
        sw, sh = self.sheet.get_size()
        max_w = self.palette_rect.w - 8
        thumb_bottom = self.palette_rect.bottom - self.palette_sel_h - 6
        max_h = max(16, thumb_bottom - oy)
        return ox, oy, max_w, max_h, sw, sh

    def _clamp_palette_zoom_offset(self) -> None:
        if self.sheet is None:
            self.palette_zoom_offset = 0
            return
        _, _, max_w, max_h, sw, sh = self._palette_viewport_metrics()
        if sw <= 0 or sh <= 0:
            self.palette_zoom_offset = 0
            return
        fit_auto = min(max_w // max(sw, 1), max_h // max(sh, 1))
        fit_base = min(fit_auto, 2)
        max_off = PALETTE_SCALE_MAX - fit_base
        min_off = 1 - fit_base
        self.palette_zoom_offset = max(min_off, min(max_off, self.palette_zoom_offset))

    def _palette_thumb_metrics(self) -> tuple[int, int, int, int]:
        """Returns ox, oy, scale, visible_h (viewport height for the sheet preview)."""
        ox, oy, max_w, max_h, sw, sh = self._palette_viewport_metrics()
        if self.sheet is None or sw <= 0:
            return ox, oy, 1, max_h
        self._clamp_palette_zoom_offset()
        fit_auto = min(max_w // max(sw, 1), max_h // max(sh, 1))
        fit_base = min(fit_auto, 2)
        scale = max(1, min(PALETTE_SCALE_MAX, fit_base + self.palette_zoom_offset))
        return ox, oy, scale, max_h

    def _clamp_palette_scroll(self) -> None:
        if self.sheet is None:
            self.palette_scroll_y = 0
            self.palette_scroll_x = 0
            return
        ox, oy, scale, visible_h = self._palette_thumb_metrics()
        sh = self.sheet.get_height()
        sw = self.sheet.get_width()
        max_w = self.palette_rect.w - 8
        content_h = sh * scale
        content_w = sw * scale
        max_scroll_y = max(0, content_h - visible_h)
        max_scroll_x = max(0, content_w - max_w)
        self.palette_scroll_y = max(0, min(self.palette_scroll_y, max_scroll_y))
        self.palette_scroll_x = max(0, min(self.palette_scroll_x, max_scroll_x))

    def palette_tile_at_pixel(self, px: int, py: int) -> int | None:
        if self.sheet is None:
            return None
        ox, oy, scale, visible_h = self._palette_thumb_metrics()
        thumb_bottom = oy + visible_h
        max_w = self.palette_rect.w - 8
        if px < ox or py < oy or px >= ox + max_w or py >= thumb_bottom:
            return None
        lx = px - ox + self.palette_scroll_x
        ly = py - oy + self.palette_scroll_y
        if lx < 0 or ly < 0:
            return None
        sw, sh = self.sheet.get_size()
        if lx >= sw * scale or ly >= sh * scale:
            return None
        sx = lx // scale
        sy = ly // scale
        if sx < self.margin or sy < self.margin:
            return None
        col = (sx - self.margin) // (self.tw + self.spacing)
        row = (sy - self.margin) // (self.th + self.spacing)
        max_row = (sh - 2 * self.margin + self.spacing) // (self.th + self.spacing)
        if col < 0 or row < 0 or col >= self.columns or row >= max_row:
            return None
        return row * self.columns + col + 1

    def palette_tile_xy_from_pixel(self, px: int, py: int) -> tuple[int, int] | None:
        idx = self.palette_tile_at_pixel(px, py)
        if idx is None or idx < 1:
            return None
        ti = idx - 1
        return ti % self.columns, ti // self.columns

    def has_event_layer(self) -> bool:
        return "event" in self.tile_layer_ids

    def event_layer_index(self) -> int | None:
        try:
            return self.tile_layer_ids.index("event")
        except ValueError:
            return None

    def add_event_layer(self) -> None:
        """FEATURE-MAP-007: append a tile layer with id `event` if missing."""
        if self.has_event_layer():
            self.set_status("Map already has an event layer.", kind="info")
            return
        w, h = self.map_w, self.map_h
        empty = [[None for _ in range(w)] for _ in range(h)]
        self.tile_layers.append(empty)
        self.tile_layer_ids.append("event")
        self.active_layer_index = len(self.tile_layers) - 1
        self.set_status("Added event layer.", kind="ok")

    def request_remove_event_layer(self) -> None:
        idx = self.event_layer_index()
        if idx is None:
            self.set_status("No event layer to remove.", kind="info")
            return
        self.layer_remove_confirm_idx = idx

    def map_cell_at_pixel(self, px: int, py: int) -> tuple[int, int] | None:
        if not self.map_viewport_rect.collidepoint(px, py):
            return None
        lx = px - self.map_origin_x + self.map_view_off_x
        ly = py - self.map_origin_y + self.map_view_off_y
        if lx < 0 or ly < 0:
            return None
        cx = lx // self.cell_px
        cy = ly // self.cell_px
        if cx >= self.map_w or cy >= self.map_h:
            return None
        return cx, cy

    def blit_tile_scaled(
        self,
        surf: pygame.Surface,
        ts_id: str,
        tile_1based: int,
        dst_x: int,
        dst_y: int,
        dst_wh: int,
    ) -> None:
        if tile_1based <= 0:
            return
        out = self.ensure_sheet(ts_id)
        if not out:
            return
        sheet, meta = out
        cols = meta["columns"]
        tw, th = meta["tw"], meta["th"]
        margin, spacing = meta["margin"], meta["spacing"]
        ti = tile_1based - 1
        col = ti % cols
        row = ti // cols
        sx = margin + col * (tw + spacing)
        sy = margin + row * (th + spacing)
        rect = pygame.Rect(sx, sy, tw, th)
        tile = sheet.subsurface(rect)
        scaled = pygame.transform.scale(tile, (dst_wh, dst_wh))
        surf.blit(scaled, (dst_x, dst_y))

    def draw(self) -> None:
        self.screen.fill((28, 28, 32))
        pygame.draw.rect(self.screen, (50, 50, 58), self.palette_rect, 1)
        ptitle = self.font.render("Preview", True, (220, 220, 220))
        self.screen.blit(ptitle, (self.palette_rect.x + 4, self.palette_rect.y + 4))
        pygame.draw.rect(self.screen, (48, 48, 56), self.tileset_list_rect, 1)
        hx = self.tileset_list_rect.x + 6
        hw = max(80, self.tileset_list_rect.w - 12)
        hy = self.tileset_list_rect.y + 6
        self.new_folder_btn_rect = pygame.Rect(self.tileset_list_rect.right - 86, hy, 78, 22)
        pygame.draw.rect(self.screen, (56, 92, 72), self.new_folder_btn_rect)
        pygame.draw.rect(self.screen, (100, 140, 110), self.new_folder_btn_rect, 1)
        self.screen.blit(
            self.font_small.render("+ Folder", True, (235, 245, 235)),
            (self.new_folder_btn_rect.x + 10, self.new_folder_btn_rect.y + 5),
        )
        title_w = max(40, min(hw, self.new_folder_btn_rect.x - hx - 8))
        hint_w = max(40, self.tileset_list_rect.w - 28)
        hint_h = 220
        hy = blit_wrapped_text(
            self.screen,
            self.font,
            "Tilesets",
            pygame.Rect(hx, hy, title_w, hint_h),
            (220, 220, 220),
        )
        hy += _TILESET_LIST_HINT_GAP_AFTER_TITLE
        hy = blit_wrapped_text(
            self.screen,
            self.font_small,
            _TILESET_LIST_HINT_1,
            pygame.Rect(hx, hy, hint_w, hint_h),
            (145, 145, 160),
        )
        hy += 4  # IMPROVEMENT-MAP-016: extra gap before hint 2
        hy = blit_wrapped_text(
            self.screen,
            self.font_small,
            _TILESET_LIST_HINT_2,
            pygame.Rect(hx, hy, hint_w, hint_h),
            (135, 135, 150),
        )
        hy += 2
        blit_wrapped_text(
            self.screen,
            self.font_small,
            _TILESET_LIST_HINT_3,
            pygame.Rect(hx, hy, hint_w, hint_h),
            (125, 125, 140),
        )
        rh = self._tileset_list_row_h()
        list_inner = pygame.Rect(
            self.tileset_list_rect.x + 4,
            self.tileset_list_rect.y + 4 + self._tileset_list_header_h,
            self.tileset_list_rect.w - 22,
            self.tileset_list_rect.h - 8 - self._tileset_list_header_h,
        )
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(list_inner)
        y0 = list_inner.y
        lh = self.font_small.get_linesize()
        rows = self._build_tileset_list_rows()
        drop_ridx: int | None = None
        if (self._tileset_drag_moved and self._tileset_drag_def_index is not None) or (
            self._folder_drag_moved and self._folder_drag_id is not None
        ):
            mx, my = pygame.mouse.get_pos()
            drop_ridx = self._tileset_list_row_index_at_pixel(mx, my)
        ts_ypad1 = self._tileset_list_y_pad_single_line()
        hsx = self.tileset_list_scroll_x  # FEATURE-MAP-024: horizontal scroll offset
        for ridx, row in enumerate(rows):
            ry = y0 + ridx * rh - self.tileset_list_scroll_y
            if ry + rh < list_inner.y - 2 or ry > list_inner.bottom + 2:
                continue
            row_r = pygame.Rect(list_inner.x, ry, list_inner.w, rh - 2)
            rk = row["row_kind"]
            if rk == "section":
                pygame.draw.rect(self.screen, (48, 46, 56), row_r)
                sec_b = 2 if drop_ridx == ridx else 1
                sec_c = (255, 210, 80) if drop_ridx == ridx else (68, 66, 78)
                pygame.draw.rect(self.screen, sec_c, row_r, sec_b)
                self.screen.blit(
                    self.font_small.render(str(row.get("name", "")), True, (160, 165, 185)),
                    (list_inner.x + 8 - hsx, ry + ts_ypad1),
                )
            elif rk == "folder":
                fc = row["color"]
                folder_drag_here = (
                    self._folder_drag_moved
                    and self._folder_drag_id is not None
                    and str(row.get("folder_id")) == self._folder_drag_id
                )
                base = (fc[0] // 3 + 20, fc[1] // 3 + 20, fc[2] // 3 + 24)
                if folder_drag_here:
                    base = (min(255, base[0] + 25), min(255, base[1] + 25), min(255, base[2] + 28))
                pygame.draw.rect(self.screen, base, row_r)
                fb = 2 if drop_ridx == ridx or folder_drag_here else 1
                fcol = (255, 210, 80) if drop_ridx == ridx else (
                    min(255, fc[0] + 40),
                    min(255, fc[1] + 40),
                    min(255, fc[2] + 50),
                )
                pygame.draw.rect(self.screen, fcol, row_r, fb)
                chev = ">" if row["collapsed"] else "v"
                self.screen.blit(
                    self.font_small.render(chev, True, (220, 225, 235)),
                    (list_inner.x + 8 - hsx, ry + ts_ypad1),
                )
                fname = str(row.get("name", ""))
                col = (245, 250, 255)
                if self.folder_rename_id == row["folder_id"]:
                    buf = self.folder_rename_buffer or ""
                    self.screen.blit(
                        self.font_small.render(f"[{buf}]", True, col),
                        (list_inner.x + 28 - hsx, ry + ts_ypad1),
                    )
                else:
                    self.screen.blit(
                        self.font_small.render(fname, True, col),
                        (list_inner.x + 28 - hsx, ry + ts_ypad1),
                    )
            else:
                i = int(row["def_index"])
                tid = str(row.get("id", "?"))
                ipx = int(row.get("indent_px", 0))
                tx = list_inner.x + 8 + ipx - hsx
                sel = i == self.tileset_index
                drag_here = self._tileset_drag_moved and self._tileset_drag_def_index == i
                bg = (68, 72, 90) if drag_here else ((58, 62, 78) if sel else (40, 42, 50))
                pygame.draw.rect(self.screen, bg, row_r)
                br_col = (255, 210, 80) if drop_ridx == ridx else ((70, 74, 88) if sel else (52, 54, 62))
                pygame.draw.rect(self.screen, br_col, row_r, 2 if drop_ridx == ridx else 1)
                col = (255, 225, 120) if sel else (185, 188, 205)
                if self.tileset_rename_index == i:
                    buf = self.tileset_rename_buffer or ""
                    line = f"[{buf}]"
                    self.screen.blit(self.font_small.render(line, True, col), (tx, ry + ts_ypad1))
                else:
                    lines = self._tileset_id_lines(tid, ipx)
                    ts_ypn = self._tileset_list_y_pad_multiline(len(lines))
                    for li, part in enumerate(lines):
                        self.screen.blit(
                            self.font_small.render(part, True, col),
                            (tx, ry + ts_ypn + li * lh),
                        )
        self.screen.set_clip(prev_clip)
        content_h = max(1, len(rows)) * rh + 8
        visible_h = list_inner.h
        max_scroll = max(0, content_h - visible_h)
        if max_scroll > 0 and list_inner.h > 40:
            thumb_h = max(28, int(visible_h * visible_h / content_h))
            t_y = list_inner.y + int(
                (self.tileset_list_scroll_y / max_scroll) * max(1, visible_h - thumb_h)
            )
            sbar = pygame.Rect(list_inner.right + 4, list_inner.y, 5, visible_h)
            pygame.draw.rect(self.screen, (35, 35, 42), sbar)
            pygame.draw.rect(self.screen, (95, 98, 115), (sbar.x, t_y, 5, thumb_h))
        # FEATURE-MAP-024: horizontal scrollbar for tileset list
        content_w = TILESET_LIST_W + TILESET_LIST_CHILD_INDENT_PX * 4
        inner_w = list_inner.w
        max_scroll_x = max(0, content_w - inner_w)
        if max_scroll_x > 0 and list_inner.w > 40:
            thumb_w = max(28, int(inner_w * inner_w / content_w))
            t_x = list_inner.x + int(
                (self.tileset_list_scroll_x / max_scroll_x) * max(1, inner_w - thumb_w)
            )
            hbar = pygame.Rect(list_inner.x, list_inner.bottom + 2, inner_w, 5)
            pygame.draw.rect(self.screen, (35, 35, 42), hbar)
            pygame.draw.rect(self.screen, (95, 98, 115), (t_x, hbar.y, thumb_w, 5))
        if self.sheet:
            self._clamp_palette_scroll()
            ox, oy, scale, visible_h = self._palette_thumb_metrics()
            self.palette_scale = scale
            sw, sh = self.sheet.get_size()
            thumb = pygame.transform.scale(self.sheet, (sw * scale, sh * scale))
            max_w = self.palette_rect.w - 8
            clip_rect = pygame.Rect(ox, oy, max_w, visible_h)
            prev_clip = self.screen.get_clip()
            self.screen.set_clip(clip_rect)
            self.screen.blit(thumb, (ox - self.palette_scroll_x, oy - self.palette_scroll_y))
            if self.palette_drag_start and self.palette_drag_end:
                x0, y0 = self.palette_drag_start
                x1, y1 = self.palette_drag_end
                cx0, cx1 = sorted((x0, x1))
                cy0, cy1 = sorted((y0, y1))
                rx = ox + cx0 * self.tw * scale - self.palette_scroll_x
                ry = oy + cy0 * self.th * scale - self.palette_scroll_y
                rw = (cx1 - cx0 + 1) * self.tw * scale
                rh = (cy1 - cy0 + 1) * self.th * scale
                s = pygame.Surface((rw, rh), pygame.SRCALPHA)
                s.fill((100, 200, 255, 80))
                self.screen.blit(s, (rx, ry))
            if self.palette_brush_tile_rect and self.sheet:
                c0, r0, c1, r1 = self.palette_brush_tile_rect
                brx = ox + c0 * self.tw * scale - self.palette_scroll_x
                bry = oy + r0 * self.th * scale - self.palette_scroll_y
                brw = (c1 - c0 + 1) * self.tw * scale
                brh = (r1 - r0 + 1) * self.th * scale
                pygame.draw.rect(self.screen, (255, 235, 60), (brx, bry, brw, brh), 2)
            self.screen.set_clip(prev_clip)
        er_hint = " eraser" if self.eraser_mode else ""
        fl_hint = " fill" if self.fill_mode else ""
        sel = self.font.render(
            f"Brush: {len(self.brush_pattern[0])}x{len(self.brush_pattern)}  "
            f"mode={self.edit_mode}{er_hint}{fl_hint}",
            True,
            (180, 255, 180),
        )
        self.screen.blit(sel, (self.palette_rect.x + 4, self.palette_rect.bottom - self.palette_sel_h + 2))

        map_rect = self.map_viewport_rect
        pygame.draw.rect(self.screen, (40, 40, 48), map_rect, 1)
        ln_chip = (
            self.tile_layer_ids[self.active_layer_index]
            if self.tile_layer_ids and self.active_layer_index < len(self.tile_layer_ids)
            else "?"
        )
        ev_layer = ln_chip.lower() == "event"
        chip_bg = (78, 52, 102) if ev_layer else (38, 88, 72)
        pygame.draw.rect(self.screen, chip_bg, self.layer_chip_rect)
        pygame.draw.rect(self.screen, (120, 120, 140), self.layer_chip_rect, 1)
        chip_txt = (
            f"EDITING: {ln_chip.upper()}   "
            f"(layers {self.key_primary('layer_prev')}/{self.key_primary('layer_next')})"
        )
        self.screen.blit(
            self.font_small.render(chip_txt, True, (248, 248, 252)),
            (self.layer_chip_rect.x + 8, self.layer_chip_rect.y + 7),
        )
        pygame.draw.rect(self.screen, (90, 90, 110), self.world_btn_rect, 1)
        wcol = (130, 200, 255) if self.world_workspace_open else (200, 200, 220)
        self.screen.blit(self.font.render("#", True, wcol), (self.world_btn_rect.x + 10, self.world_btn_rect.y + 4))
        pygame.draw.rect(self.screen, (90, 90, 110), self.gear_rect, 1)
        gear_txt = self.font.render("*", True, (200, 200, 220))
        self.screen.blit(gear_txt, (self.gear_rect.x + 10, self.gear_rect.y + 4))

        if self.world_workspace_open:
            self._draw_world_workspace()
        if not self.world_workspace_open:
            for y in range(self.map_h):
                for x in range(self.map_w):
                    px = self.map_origin_x + x * self.cell_px - self.map_view_off_x
                    py = self.map_origin_y + y * self.cell_px - self.map_view_off_y
                    if not self.map_canvas_rect.collidepoint(px + 1, py + 1):
                        continue
                    pygame.draw.rect(self.screen, (24, 24, 30), (px, py, self.cell_px, self.cell_px))
                    for grid in self.tile_layers:
                        c = grid[y][x]
                        if c is not None:
                            self.blit_tile_scaled(self.screen, c["ts"], c["t"], px, py, self.cell_px)
                    if self.edit_mode == "walk":
                        a = 70 if self.walk[y][x] else 50
                        col = (200, 60, 60, a) if self.walk[y][x] else (60, 200, 80, a)
                        ov = pygame.Surface((self.cell_px, self.cell_px), pygame.SRCALPHA)
                        ov.fill(col)
                        self.screen.blit(ov, (px, py))
                    elif self.edit_mode == "transparent":
                        a = 70 if self.trans[y][x] else 40
                        col = (80, 120, 255, a) if self.trans[y][x] else (200, 200, 200, 25)
                        ov = pygame.Surface((self.cell_px, self.cell_px), pygame.SRCALPHA)
                        ov.fill(col)
                        self.screen.blit(ov, (px, py))
                    pygame.draw.rect(self.screen, (60, 60, 70), (px, py, self.cell_px, self.cell_px), 1)

        if not self.world_workspace_open and self.map_drag_start and self.map_paint_current and self.edit_mode == "paint":
            x0, y0 = self.map_drag_start
            x1, y1 = self.map_paint_current
            ax0, ax1 = sorted((x0, x1))
            ay0, ay1 = sorted((y0, y1))
            rx = self.map_origin_x + ax0 * self.cell_px - self.map_view_off_x
            ry = self.map_origin_y + ay0 * self.cell_px - self.map_view_off_y
            rw = (ax1 - ax0 + 1) * self.cell_px
            rh = (ay1 - ay0 + 1) * self.cell_px
            if self.map_canvas_rect.colliderect(pygame.Rect(rx, ry, rw, rh)):
                pygame.draw.rect(self.screen, (255, 220, 100), (rx, ry, rw, rh), 2)

        if not self.world_workspace_open and self.map_drag_start and self.map_paint_current and self.edit_mode == "walk":
            x0, y0 = self.map_drag_start
            x1, y1 = self.map_paint_current
            ax0, ax1 = sorted((x0, x1))
            ay0, ay1 = sorted((y0, y1))
            rx = self.map_origin_x + ax0 * self.cell_px - self.map_view_off_x
            ry = self.map_origin_y + ay0 * self.cell_px - self.map_view_off_y
            rw = (ax1 - ax0 + 1) * self.cell_px
            rh = (ay1 - ay0 + 1) * self.cell_px
            if self.map_canvas_rect.colliderect(pygame.Rect(rx, ry, rw, rh)):
                col = (255, 140, 90) if self.map_drag_button == 1 else (120, 200, 255)
                pygame.draw.rect(self.screen, col, (rx, ry, rw, rh), 2)

        if not self.world_workspace_open and self.hover_cell:
            hx, hy = self.hover_cell
            hpx = self.map_origin_x + hx * self.cell_px - self.map_view_off_x
            hpy = self.map_origin_y + hy * self.cell_px - self.map_view_off_y
            hr = pygame.Rect(hpx, hpy, self.cell_px, self.cell_px)
            if self.map_canvas_rect.colliderect(hr):
                pygame.draw.rect(self.screen, (255, 255, 80), hr, 2)

        pygame.draw.rect(self.screen, (34, 34, 42), self.footer_rect)
        pygame.draw.line(
            self.screen,
            (65, 65, 78),
            self.footer_rect.topleft,
            (self.footer_rect.right - 1, self.footer_rect.top),
            1,
        )
        pad = 14
        inner = pygame.Rect(
            self.footer_rect.x + pad,
            self.footer_rect.y + pad,
            self.footer_rect.w - 2 * pad,
            self.footer_rect.h - 2 * pad,
        )
        yc = inner.y
        ln = (
            self.tile_layer_ids[self.active_layer_index]
            if self.tile_layer_ids and self.active_layer_index < len(self.tile_layer_ids)
            else "?"
        )
        lt = max(1, len(self.tile_layers))
        li = min(self.active_layer_index + 1, lt)
        line_a = (
            f"Map “{self.map_id}”  ·  {self.map_w}×{self.map_h}  ·  "
            f"Layer {li}/{lt} ({ln})  ·  Mode: {self.edit_mode}  ·  "
            f"Modes: {self.key_primary('cycle_mode')}  ·  Size: {self.key_primary('set_map_size')}"
        )
        yc = blit_wrapped_text(self.screen, self.font, line_a, pygame.Rect(inner.x, yc, inner.w, inner.bottom - yc), (215, 215, 225))
        yc += 8
        if not self.footer_help_expanded:
            hint_col = (165, 170, 185)
            hint = (
                f"Shortcuts & quickstart: press {self.key_primary('toggle_help')} to expand this footer.  "
                f"World workspace (#): {self.key_primary('toggle_world_labels')} toggles map name badges."
            )
            yc = blit_wrapped_text(
                self.screen, self.font_small, hint, pygame.Rect(inner.x, yc, inner.w, inner.bottom - yc), hint_col
            )
            yc += 10
        else:
            line_b = (
                f"Tileset: {self.key_primary('tileset_prev')}/{self.key_primary('tileset_next')}  ·  "
                f"Layer: {self.key_primary('layer_prev')}/{self.key_primary('layer_next')} · "
                f"+{self.key_primary('layer_add')} · −{self.key_primary('layer_remove')}  ·  "
                f"Open map: {self.key_primary('open_map')}  ·  Import PNG: {self.key_primary('import_tileset')}  ·  Rescale tileset: {self.key_primary('rescale_tileset')}  ·  "
                f"Save As: Shift+S  ·  Collapse help: {self.key_primary('toggle_help')}  ·  "
                f"World: #  ·  Settings: *  ·  Scroll: wheel  ·  "
                f"Palette: Ctrl+wheel zoom · Shift+wheel pan H"
            )
            yc = blit_wrapped_text(
                self.screen, self.font_small, line_b, pygame.Rect(inner.x, yc, inner.w, inner.bottom - yc), (165, 170, 185)
            )
            yc += 10
        if self.status_message and time.time() < self.status_msg_until:
            st_colors = {"ok": (120, 215, 165), "err": (255, 140, 125), "info": (195, 200, 215)}
            st_col = st_colors.get(self.status_kind, st_colors["info"])
            yc = blit_wrapped_text(
                self.screen,
                self.font_small,
                self.status_message,
                pygame.Rect(inner.x, yc, inner.w, inner.bottom - yc),
                st_col,
            )
            yc += 8
        rest = pygame.Rect(inner.x, yc, inner.w, inner.bottom - yc)
        if self.footer_help_expanded and rest.h > self.font_small.get_linesize():
            yc = blit_wrapped_text(
                self.screen,
                self.font_small,
                (
                    f"Save: {self.key_primary('save')} · New: {self.key_primary('new_map')} · "
                    f"Maps: {self.key_primary('map_prev_file')}/{self.key_primary('map_next_file')} · "
                    f"Undo: {self.key_primary('undo')} · Redo: {self.key_primary('redo')} · "
                    f"Eraser: {self.key_primary('toggle_eraser')} · "
                    f"Fill: {self.key_primary('toggle_fill')} (active layer) · "
                    f"Del map: {self.key_primary('delete_map')} · "
                    f"Id: I · Conn: C · Pan: arrows · Esc"
                ),
                rest,
                (150, 155, 165),
            )
            yc += 4
        if self.footer_help_expanded and yc < inner.bottom and self.world_workspace_open:
            wline = (
                f"World: wheel pan · Ctrl/Cmd+wheel zoom · mid-drag/LMB empty pan · "
                f"LMB drag maps · RMB menu (interior) · green=proximity · F9 export · "
                f"{self.key_primary('toggle_world_labels')} name badges"
            )
            yc = blit_wrapped_text(
                self.screen, self.font_small, wline, pygame.Rect(inner.x, yc, inner.w, inner.bottom - yc), (140, 200, 170)
            )
            yc += 6
        if self.footer_help_expanded and yc < inner.bottom:
            steps = self.quickstart_steps()
            for done, txt in steps:
                if yc >= inner.bottom:
                    break
                marker = "[x]" if done else "[ ]"
                line = f"{marker} {txt}"
                yc = blit_wrapped_text(
                    self.screen,
                    self.font_small,
                    line,
                    pygame.Rect(inner.x, yc, inner.w, inner.bottom - yc),
                    (130, 220, 130) if done else (220, 220, 220),
                )
                yc += 2
        if self.edit_mode == "map_id" and yc < inner.bottom:
            blit_wrapped_text(
                self.screen,
                self.font,
                f"Map id (Enter): [{self.text_buffer}]",
                pygame.Rect(inner.x, yc, inner.w, inner.bottom - yc),
                (255, 220, 120),
            )
        elif self.edit_mode == "conn" and yc < inner.bottom:
            fi = self.conn_field_index
            side_i, sub_i = fi // 3, fi % 3
            side = SIDES[side_i]
            sub = self.conn_field_names[sub_i]
            val = self.connections[side][sub if sub != "mapId" else "mapId"]
            show = self.text_buffer if self.text_buffer else str(val)
            conn_line = f"{side} {sub}: [{show}]"
            blit_wrapped_text(self.screen, self.font, conn_line, pygame.Rect(inner.x, yc, inner.w, inner.bottom - yc), (255, 255, 160))

        if self.settings_open:
            self._draw_settings_overlay()
        if self.size_prompt_active:
            self._draw_size_overlay()
        if self.layer_remove_confirm_idx is not None:
            self._draw_layer_remove_confirm_overlay()
        if self.tileset_delete_confirm_id:
            self._draw_delete_confirm_overlay()
        if self.map_delete_confirm_stem:
            self._draw_map_delete_confirm_overlay()
        if self.map_file_prompt_mode in ("first_save", "save_as", "overwrite"):
            self._draw_map_file_prompt_overlay()
        if self.open_map_overlay:
            self._draw_open_map_overlay()
        if self.folder_new_prompt_active:
            self._draw_folder_new_prompt_overlay()
        if self.folder_color_prompt_id:
            self._draw_folder_color_prompt_overlay()
        if self.world_ctx_menu:
            self._draw_world_context_menu()

        pygame.display.flip()

    def _draw_settings_overlay(self) -> None:
        w, h = self.screen.get_size()
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        self.screen.blit(ov, (0, 0))
        box = pygame.Rect(w // 2 - 240, h // 2 - 228, 480, 456)
        pygame.draw.rect(self.screen, (48, 48, 56), box)
        pygame.draw.rect(self.screen, (120, 120, 140), box, 2)
        t = self.font.render("Settings", True, (240, 240, 240))
        self.screen.blit(t, (box.x + 12, box.y + 10))
        y = box.y + 36
        self.screen.blit(self.font_small.render("Map layers", True, (190, 200, 220)), (box.x + 12, y))
        y += 22
        self.settings_add_event_rect = pygame.Rect(box.x + 12, y, 200, 28)
        self.settings_remove_event_rect = pygame.Rect(box.x + 220, y, 200, 28)
        add_col = (70, 120, 90) if not self.has_event_layer() else (55, 55, 62)
        rem_col = (120, 70, 70) if self.has_event_layer() else (55, 55, 62)
        pygame.draw.rect(self.screen, add_col, self.settings_add_event_rect)
        pygame.draw.rect(self.screen, (100, 140, 110), self.settings_add_event_rect, 1)
        pygame.draw.rect(self.screen, rem_col, self.settings_remove_event_rect)
        pygame.draw.rect(self.screen, (140, 100, 100), self.settings_remove_event_rect, 1)
        self.screen.blit(
            self.font_small.render("Add event layer", True, (240, 240, 245)),
            (self.settings_add_event_rect.x + 10, self.settings_add_event_rect.y + 7),
        )
        self.screen.blit(
            self.font_small.render("Remove event layer", True, (240, 240, 245)),
            (self.settings_remove_event_rect.x + 10, self.settings_remove_event_rect.y + 7),
        )
        y += 36
        can_remove_layer = len(self.tile_layers) > 1
        ln = (
            self.tile_layer_ids[self.active_layer_index]
            if self.tile_layer_ids and self.active_layer_index < len(self.tile_layer_ids)
            else "?"
        )
        self.settings_remove_current_layer_rect = pygame.Rect(box.x + 12, y, box.w - 24, 42)
        rl_bg = (95, 55, 55) if can_remove_layer else (52, 52, 58)
        rl_br = (140, 85, 85) if can_remove_layer else (70, 70, 78)
        pygame.draw.rect(self.screen, rl_bg, self.settings_remove_current_layer_rect)
        pygame.draw.rect(self.screen, rl_br, self.settings_remove_current_layer_rect, 1)
        self.screen.blit(
            self.font_small.render("Remove current tile layer…", True, (245, 245, 250)),
            (self.settings_remove_current_layer_rect.x + 10, self.settings_remove_current_layer_rect.y + 5),
        )
        self.screen.blit(
            self.font_small.render(
                f'Active: "{ln}"  ·  keyboard: {self.key_primary("layer_remove")}',
                True,
                (200, 200, 210) if can_remove_layer else (130, 130, 138),
            ),
            (self.settings_remove_current_layer_rect.x + 10, self.settings_remove_current_layer_rect.y + 22),
        )
        y += 48
        self.screen.blit(
            self.font_small.render("Keys — click row then press a key to rebind", True, (170, 175, 190)),
            (box.x + 12, y),
        )
        y += 22
        for act in sorted(self.key_config.keys()):
            keys = ", ".join(self.key_config[act])
            line = f"{act}: [{keys}]"
            self.screen.blit(self.font_small.render(line, True, (200, 200, 210)), (box.x + 12, y))
            y += 18
            if y > box.bottom - 48:
                break
        self.screen.blit(
            self.font.render("S: save config  R: reset defaults  Esc: close", True, (180, 220, 180)),
            (box.x + 12, box.bottom - 36),
        )

    def _draw_size_overlay(self) -> None:
        w, h = self.screen.get_size()
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140))
        self.screen.blit(ov, (0, 0))
        t = self.font.render(f"Map size WIDTHxHEIGHT (e.g. 32x24)  [{self.text_buffer}]", True, (255, 255, 200))
        self.screen.blit(t, (w // 2 - 200, h // 2))

    def _draw_map_file_prompt_overlay(self) -> None:
        """FEATURE-MAP-011: first save / Save As / overwrite prompts."""
        mode = self.map_file_prompt_mode
        if mode not in ("first_save", "save_as", "overwrite"):
            return
        w, h = self.screen.get_size()
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        self.screen.blit(ov, (0, 0))
        y = h // 2 - 36
        x0 = w // 2 - 300
        if mode == "overwrite":
            cid = self.map_overwrite_candidate_id or "?"
            self.screen.blit(
                self.font.render(f"Map file '{cid}' already exists on disk.", True, (255, 230, 200)),
                (x0, y),
            )
            self.screen.blit(
                self.font.render("Overwrite?  Y / Enter  —  N / Esc", True, (200, 255, 200)),
                (x0, y + 26),
            )
        else:
            title = "First save: choose map id (file name)" if mode == "first_save" else "Save As: new map id"
            self.screen.blit(self.font.render(title, True, (255, 245, 200)), (x0, y))
            buf = self.map_file_prompt_buffer or ""
            self.screen.blit(self.font.render(f"[{buf}]", True, (255, 255, 240)), (x0, y + 26))
            self.screen.blit(
                self.font_small.render("Enter = save  ·  Esc = cancel ·  allowed: letters, digits, _ - .", True, (180, 185, 200)),
                (x0, y + 52),
            )

    def _draw_open_map_overlay(self) -> None:
        """FEATURE-MAP-012: pick a map JSON when not using macOS file dialog."""
        if not self.open_map_overlay:
            return
        stems = self.open_map_stems
        w, h = self.screen.get_size()
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        self.screen.blit(ov, (0, 0))
        bw, bh = 440, min(480, h - 80)
        box = pygame.Rect(w // 2 - bw // 2, h // 2 - bh // 2, bw, bh)
        self._open_map_box_rect = box
        pygame.draw.rect(self.screen, (44, 44, 52), box)
        pygame.draw.rect(self.screen, (120, 120, 140), box, 2)
        title = (
            "World: pick map to insert  —  ↑↓ Enter · Esc · wheel"
            if self.open_map_purpose == "world"
            else "Open map  —  ↑↓ Enter ·  Esc close ·  wheel scroll"
        )
        self.screen.blit(self.font.render(title, True, (240, 240, 245)), (box.x + 12, box.y + 10))
        lh = self.font_small.get_linesize() + 4
        top_y = box.y + 44
        visible = self._open_map_visible_rows()
        n = len(stems)
        self._sync_open_map_scroll()
        for i in range(visible):
            si = self.open_map_scroll + i
            if si >= n:
                break
            ry = top_y + i * lh
            stem = stems[si]
            sel = si == self.open_map_sel
            rr = pygame.Rect(box.x + 10, ry, box.w - 20, lh - 2)
            pygame.draw.rect(self.screen, (72, 78, 98) if sel else (52, 54, 62), rr)
            self.screen.blit(self.font_small.render(stem, True, (235, 235, 240)), (rr.x + 8, rr.y + 2))

    def _draw_folder_new_prompt_overlay(self) -> None:
        if not self.folder_new_prompt_active:
            return
        w, h = self.screen.get_size()
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140))
        self.screen.blit(ov, (0, 0))
        t = self.font.render(f"New folder name  [{self.folder_new_prompt_buffer}]", True, (255, 255, 200))
        self.screen.blit(t, (w // 2 - 220, h // 2))

    def _draw_folder_color_prompt_overlay(self) -> None:
        if not self.folder_color_prompt_id:
            return
        w, h = self.screen.get_size()
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140))
        self.screen.blit(ov, (0, 0))
        t = self.font.render(f"Folder color R,G,B (0–255)  [{self.folder_color_prompt_buffer}]", True, (255, 255, 200))
        self.screen.blit(t, (w // 2 - 280, h // 2))

    def _draw_layer_remove_confirm_overlay(self) -> None:
        idx = self.layer_remove_confirm_idx
        if idx is None:
            return
        lid = self.tile_layer_ids[idx] if 0 <= idx < len(self.tile_layer_ids) else "?"
        w, h = self.screen.get_size()
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        self.screen.blit(ov, (0, 0))
        margin = 12
        pad_top = 16
        pad_bottom = 22
        gap_title_desc = 10
        gap_desc_keys = 10
        title_str = f'Remove layer "{lid}"?'
        sub_desc = "All tiles on this layer are discarded. Other layers are unchanged."
        key_lines = ("Y = confirm", "N / Esc = cancel")
        box_w = min(720, w - 2 * margin)
        inner_w = max(120, box_w - 2 * pad_top)
        title_lines = _wrap_lines_to_width(self.font, title_str, inner_w)
        desc_lines = _wrap_lines_to_width(self.font_small, sub_desc, inner_w)
        lh_t = self.font.get_linesize()
        lh_s = self.font_small.get_linesize()
        title_h = len(title_lines) * lh_t
        desc_h = len(desc_lines) * lh_s
        keys_h = len(key_lines) * lh_s
        box_h = (
            pad_top
            + title_h
            + gap_title_desc
            + desc_h
            + gap_desc_keys
            + keys_h
            + pad_bottom
        )
        box = pygame.Rect((w - box_w) // 2, (h - box_h) // 2, box_w, box_h)
        pygame.draw.rect(self.screen, (44, 48, 52), box)
        pygame.draw.rect(self.screen, (100, 120, 140), box, 2)
        y = box.y + pad_top
        tx = box.x + pad_top
        for tl in title_lines:
            self.screen.blit(self.font.render(tl, True, (220, 235, 255)), (tx, y))
            y += lh_t
        y += gap_title_desc
        for dl in desc_lines:
            self.screen.blit(self.font_small.render(dl, True, (190, 190, 200)), (tx, y))
            y += lh_s
        y += gap_desc_keys
        for kl in key_lines:
            self.screen.blit(self.font_small.render(kl, True, (210, 210, 225)), (tx, y))
            y += lh_s

    def _draw_delete_confirm_overlay(self) -> None:
        w, h = self.screen.get_size()
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        self.screen.blit(ov, (0, 0))
        tid = self.tileset_delete_confirm_id or ""
        margin = 12
        pad_top = 16
        pad_bottom = 22
        gap_title_desc = 10
        gap_desc_keys = 10
        sub_desc = (
            "Removes it from tilesets.json and deletes its PNG if unused. "
            "Map tiles cleared."
        )
        key_lines = ("Y = confirm", "N / Esc = cancel")
        box_w = min(720, w - 2 * margin)
        inner_w = max(120, box_w - 2 * pad_top)
        title_str = _truncate_delete_title(self.font, tid, inner_w)
        title_lines = _wrap_lines_to_width(self.font, title_str, inner_w)
        desc_lines = _wrap_lines_to_width(self.font_small, sub_desc, inner_w)
        lh_t = self.font.get_linesize()
        lh_s = self.font_small.get_linesize()
        title_h = len(title_lines) * lh_t
        desc_h = len(desc_lines) * lh_s
        keys_h = len(key_lines) * lh_s
        box_h = (
            pad_top
            + title_h
            + gap_title_desc
            + desc_h
            + gap_desc_keys
            + keys_h
            + pad_bottom
        )
        box = pygame.Rect((w - box_w) // 2, (h - box_h) // 2, box_w, box_h)
        pygame.draw.rect(self.screen, (48, 44, 52), box)
        pygame.draw.rect(self.screen, (140, 90, 90), box, 2)
        y = box.y + pad_top
        tx = box.x + pad_top
        for tl in title_lines:
            self.screen.blit(self.font.render(tl, True, (255, 230, 220)), (tx, y))
            y += lh_t
        y += gap_title_desc
        for dl in desc_lines:
            self.screen.blit(self.font_small.render(dl, True, (190, 190, 200)), (tx, y))
            y += lh_s
        y += gap_desc_keys
        for kl in key_lines:
            self.screen.blit(self.font_small.render(kl, True, (210, 210, 225)), (tx, y))
            y += lh_s

    def _draw_map_delete_confirm_overlay(self) -> None:
        w, h = self.screen.get_size()
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        self.screen.blit(ov, (0, 0))
        stem = self.map_delete_confirm_stem or ""
        margin = 12
        pad_top = 16
        pad_bottom = 22
        gap_title_desc = 10
        gap_desc_keys = 10
        sub_desc = (
            "Permanently removes the map JSON from src/maps and updates maps_index.json. "
            "Other maps are not changed."
        )
        key_lines = ("Y = confirm", "N / Esc = cancel")
        box_w = min(720, w - 2 * margin)
        inner_w = max(120, box_w - 2 * pad_top)
        title_str = f'Delete map "{stem}.json"?'
        title_lines = _wrap_lines_to_width(self.font, title_str, inner_w)
        desc_lines = _wrap_lines_to_width(self.font_small, sub_desc, inner_w)
        lh_t = self.font.get_linesize()
        lh_s = self.font_small.get_linesize()
        title_h = len(title_lines) * lh_t
        desc_h = len(desc_lines) * lh_s
        keys_h = len(key_lines) * lh_s
        box_h = (
            pad_top
            + title_h
            + gap_title_desc
            + desc_h
            + gap_desc_keys
            + keys_h
            + pad_bottom
        )
        box = pygame.Rect((w - box_w) // 2, (h - box_h) // 2, box_w, box_h)
        pygame.draw.rect(self.screen, (48, 44, 52), box)
        pygame.draw.rect(self.screen, (140, 90, 90), box, 2)
        y = box.y + pad_top
        tx = box.x + pad_top
        for tl in title_lines:
            self.screen.blit(self.font.render(tl, True, (255, 230, 220)), (tx, y))
            y += lh_t
        y += gap_title_desc
        for dl in desc_lines:
            self.screen.blit(self.font_small.render(dl, True, (190, 190, 200)), (tx, y))
            y += lh_s
        y += gap_desc_keys
        for kl in key_lines:
            self.screen.blit(self.font_small.render(kl, True, (210, 210, 225)), (tx, y))
            y += lh_s

    def apply_text_buffer_to_connection(self) -> None:
        fi = self.conn_field_index
        side_i, sub_i = fi // 3, fi % 3
        side = SIDES[side_i]
        sub = self.conn_field_names[sub_i]
        raw = self.text_buffer.strip()
        if sub == "mapId":
            self.connections[side]["mapId"] = raw
        else:
            try:
                n = int(raw) if raw else 0
            except ValueError:
                n = self.connections[side][sub]  # type: ignore
            self.connections[side][sub] = n
        self.text_buffer = ""

    @staticmethod
    def _tile_cell_same(a: dict | None, b: dict | None) -> bool:
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        return str(a.get("ts")) == str(b.get("ts")) and int(a.get("t", 0)) == int(b.get("t", 0))

    @staticmethod
    def _flood_clip_contains(clip: tuple[int, int, int, int] | None, x: int, y: int) -> bool:
        """Inclusive clip rect (x0, y0, x1, y1). None = unbounded."""
        if clip is None:
            return True
        x0, y0, x1, y1 = clip
        return x0 <= x <= x1 and y0 <= y <= y1

    def _fill_dest_for_brush_tile(
        self, brush_ox: int, brush_oy: int, mx: int, my: int
    ) -> dict | None:
        """Map cell (mx,my) gets brush_pattern tile tiled from anchor (brush_ox, brush_oy)."""
        if not self.brush_pattern or not self.brush_pattern[0]:
            return None
        bh = len(self.brush_pattern)
        bw = len(self.brush_pattern[0])
        i = (mx - brush_ox) % bw
        j = (my - brush_oy) % bh
        ts, ti = self.brush_pattern[j][i]
        return {"ts": str(ts), "t": int(ti)}

    def _flood_fill_at(
        self,
        sx: int,
        sy: int,
        erase: bool,
        *,
        record_undo: bool = True,
        match_grid: list[list[dict | None]] | None = None,
        clip_rect: tuple[int, int, int, int] | None = None,
        brush_origin: tuple[int, int] | None = None,
    ) -> int:
        """FEATURE-MAP-017 / FEATURE-MAP-020 / BUG-MAP-012: flood fill on active tile layer.
        When match_grid is set, connectivity matches that frozen grid (batch seeds); writes go to g.
        When clip_rect is set, BFS stays inside that inclusive map rectangle (batch fill region).
        When brush_origin is set, each painted cell uses the tiled multi-tile brush (not only [0][0]).
        Returns count of cells written to fill (0 if no-op).
        """
        g = self._active_grid()
        ref = match_grid if match_grid is not None else g
        if not (0 <= sx < self.map_w and 0 <= sy < self.map_h):
            return 0
        if not MapEditor._flood_clip_contains(clip_rect, sx, sy):
            return 0
        seed = ref[sy][sx]
        if erase:
            fill: dict | None = None
            fill_at_seed: dict | None = None
        else:
            if not self.brush_pattern or not self.brush_pattern[0]:
                return 0
            if brush_origin is not None:
                bx, by = brush_origin
                fill_at_seed = self._fill_dest_for_brush_tile(bx, by, sx, sy)
                fill = fill_at_seed
            else:
                ts, ti = self.brush_pattern[0][0]
                fill = {"ts": str(ts), "t": int(ti)}
                fill_at_seed = fill
        if MapEditor._tile_cell_same(seed, fill_at_seed):
            return 0
        if record_undo:
            self._undo_checkpoint()
        q: deque[tuple[int, int]] = deque([(sx, sy)])
        seen: set[tuple[int, int]] = set()
        painted = 0
        while q:
            x, y = q.popleft()
            if (x, y) in seen:
                continue
            if not (0 <= x < self.map_w and 0 <= y < self.map_h):
                continue
            if not MapEditor._flood_clip_contains(clip_rect, x, y):
                continue
            if not MapEditor._tile_cell_same(ref[y][x], seed):
                continue
            seen.add((x, y))
            if erase:
                g[y][x] = None
            elif brush_origin is not None:
                bx, by = brush_origin
                dest = self._fill_dest_for_brush_tile(bx, by, x, y)
                if dest is not None:
                    g[y][x] = dest
            else:
                g[y][x] = fill
            painted += 1
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if not (0 <= nx < self.map_w and 0 <= ny < self.map_h):
                    continue
                if not MapEditor._flood_clip_contains(clip_rect, nx, ny):
                    continue
                q.append((nx, ny))
        return painted

    def _map_json_path_for_delete(self) -> Path | None:
        stem = self._map_disk_backing_id
        if stem:
            p = MAPS_DIR / f"{stem}.json"
            if p.is_file() and p.name != MAPS_INDEX_NAME:
                return p
        cand = sanitize_map_id(self.map_id)
        p2 = MAPS_DIR / f"{cand}.json"
        if p2.is_file() and p2.name != MAPS_INDEX_NAME:
            return p2
        return None

    def request_delete_map_file(self) -> None:
        p = self._map_json_path_for_delete()
        if p is None:
            self.set_status("No saved map file to delete", kind="err")
            return
        self.map_delete_confirm_stem = p.stem

    def _confirm_delete_map_file(self) -> None:
        stem = self.map_delete_confirm_stem
        self.map_delete_confirm_stem = None
        if not stem:
            return
        path = MAPS_DIR / f"{stem}.json"
        if path.name == MAPS_INDEX_NAME or not path.is_file():
            return
        try:
            path.unlink()
        except OSError as e:
            self.set_status(f"Could not delete map: {e}", kind="err")
            return
        write_maps_index()
        self.refresh_map_file_list()
        self._session_map_cache.pop(sanitize_map_id(stem), None)
        if self.map_files:
            self.try_load_map_by_id(self.map_files[self.map_file_index].stem)
            self.set_status(f"Deleted map; opened {self.map_id}", kind="ok")
        else:
            self.map_id = "untitled"
            self.map_name = "Untitled"
            self.new_map(reset_connections=True)
            self.saved_once = False
            self._map_disk_backing_id = None
            self.set_status("Deleted map; started new empty map", kind="ok")

    def apply_brush_at(self, cx: int, cy: int, erase: bool) -> None:
        bh = len(self.brush_pattern)
        bw = len(self.brush_pattern[0]) if bh else 1
        for j in range(bh):
            for i in range(bw):
                tx, ty = cx + i, cy + j
                if tx >= self.map_w or ty >= self.map_h:
                    continue
                ts, ti = self.brush_pattern[j][i]
                g = self._active_grid()
                if erase:
                    g[ty][tx] = None
                else:
                    g[ty][tx] = {"ts": ts, "t": ti}

    def fill_rect_with_brush(self, x0: int, y0: int, x1: int, y1: int, erase: bool) -> None:
        ax0, ax1 = sorted((x0, x1))
        ay0, ay1 = sorted((y0, y1))
        g = self._active_grid()
        for cy in range(ay0, ay1 + 1):
            for cx in range(ax0, ax1 + 1):
                off_x = (cx - ax0) % len(self.brush_pattern[0])
                off_y = (cy - ay0) % len(self.brush_pattern)
                ts, ti = self.brush_pattern[off_y][off_x]
                if erase:
                    g[cy][cx] = None
                else:
                    g[cy][cx] = {"ts": ts, "t": ti}

    def cycle_edit_mode(self) -> None:
        self.map_drag_start = None
        self.map_paint_current = None
        order = ("paint", "walk", "transparent")
        i = order.index(self.edit_mode) if self.edit_mode in order else 0
        self.edit_mode = order[(i + 1) % len(order)]

    def _make_unique_tileset_id(self, base: str, used: set[str]) -> str:
        b = "".join(c if c.isalnum() or c in "._-" else "_" for c in base)[:64]
        if not b:
            b = "tileset"
        if b not in used:
            return b
        n = 2
        while f"{b}_{n}" in used:
            n += 1
        return f"{b}_{n}"

    def _append_tileset_entries(self, entries: list[tuple[str, str, int, int]]) -> int:
        """Register tilesets as (dest_filename, id, tw, th). Returns count added."""
        if not entries:
            return 0
        reg = load_json(TILESETS_JSON)
        tss = reg.setdefault("tilesets", [])
        existing_ids = {str(t.get("id")) for t in tss if t.get("id")}
        added = 0
        new_ids: list[str] = []
        for safe_name, tid, tw, th in entries:
            if tid in existing_ids:
                continue
            existing_ids.add(tid)
            tss.append(
                {
                    "id": tid,
                    "image": f"src/Graphics/Tilesets/{safe_name}",
                    "tileWidth": tw,
                    "tileHeight": th,
                    "margin": 0,
                    "spacing": 0,
                    "columns": 0,
                }
            )
            new_ids.append(tid)
            added += 1
        if added == 0:
            return 0
        self.registry = reg
        ed = self._editor_folder_blob()
        order = list(ed.get("order") or [])
        for tid in new_ids:
            order.append({"kind": "tileset", "id": tid})
        ed["order"] = order
        write_tilesets_registry(TILESETS_JSON, self.registry)
        self.tileset_defs = list(reg.get("tilesets", []))
        self.sheet_cache.clear()
        self.meta_cache.clear()
        self.tileset_index = len(self.tileset_defs) - 1
        self.reload_tileset_sheet()
        self.brush_pattern = [[(self.active_tileset_id, 1)]]
        self._clamp_tileset_list_scroll()
        print(f"Imported {added} tileset(s)")
        return added

    def import_tileset_dialog(self) -> None:
        self.set_status(
            "Import: PNG images only. To open a map, use Open map (P).",
            kind="info",
        )
        try:
            paths: list[str] = []
            if sys.platform == "darwin":
                paths = _macos_choose_png_paths_multi()
            else:
                import tkinter as tk
                from tkinter import filedialog

                root = tk.Tk()
                root.withdraw()
                paths = list(
                    filedialog.askopenfilenames(filetypes=[("PNG", "*.png"), ("All", "*.*")])
                )
                root.destroy()
            if not paths:
                self.set_status("Import: no files selected", kind="info")
                return

            # Auto-suggest scale factor from the first selected file and prompt user.
            suggested = 1
            first_surf = None
            try:
                first_surf = load_pygame_image(paths[0]).convert_alpha()
                suggested = _suggest_upscale_factor(first_surf)
            except Exception:
                pass

            user_scale: int | None = None
            if sys.platform == "darwin":
                user_scale = _macos_dialog_int(
                    f"Scale factor for import (1 = no change, 2 = double size, etc.).\n"
                    f"Auto-detected suggestion: {suggested}x",
                    suggested,
                )
            else:
                try:
                    import tkinter as tk
                    import tkinter.simpledialog as sd
                    root2 = tk.Tk()
                    root2.withdraw()
                    user_scale = sd.askinteger(
                        "Scale factor",
                        f"Scale factor (1=none, 2=double, …). Suggested: {suggested}x",
                        initialvalue=suggested,
                        minvalue=1,
                        maxvalue=8,
                        parent=root2,
                    )
                    root2.destroy()
                except Exception:
                    user_scale = suggested
            if user_scale is None:
                self.set_status("Import: cancelled", kind="info")
                return
            user_scale = max(1, min(8, int(user_scale)))

            reg = load_json(TILESETS_JSON)
            used_ids: set[str] = {str(t.get("id")) for t in reg.get("tilesets", []) if t.get("id")}
            entries: list[tuple[str, str, int, int]] = []
            skipped: list[str] = []
            TILESETS_DIR.mkdir(parents=True, exist_ok=True)
            for path_str in paths:
                src = Path(path_str)
                if not src.is_file():
                    skipped.append(str(src.name))
                    continue
                dims = load_png_dimensions(src)
                if dims is None:
                    skipped.append(src.name)
                    continue
                iw, ih = dims
                tw, th = 16, 16
                grid_scale = _compute_upscale_factor(iw, ih, 16)
                total_scale = grid_scale * user_scale
                safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in src.name)
                dest = _unique_dest_path(TILESETS_DIR / safe)
                if total_scale > 1:
                    if path_str == paths[0] and first_surf is not None:
                        surf = first_surf
                    else:
                        surf = load_pygame_image(str(src)).convert_alpha()
                    upscaled = pygame.transform.scale(surf, (iw * total_scale, ih * total_scale))
                    upscaled = _refold_to_standard_width(upscaled, 256)
                    pygame.image.save(upscaled, str(dest))
                else:
                    shutil.copy2(src, dest)
                tid = self._make_unique_tileset_id(Path(dest.name).stem, used_ids)
                used_ids.add(tid)
                entries.append((dest.name, tid, tw, th))

            if not entries:
                sk = f" (skipped: {', '.join(skipped[:5])})" if skipped else ""
                self.set_status(f"Import: no readable PNGs{sk}", kind="err")
                return
            n = self._append_tileset_entries(entries)
            sk = f" Skipped: {', '.join(skipped[:4])}." if skipped else ""
            if n > 0:
                names = ", ".join(f"{e[1]} ({e[2]}×{e[3]})" for e in entries[:4])
                extra = f" (+{len(entries) - 4} more)" if len(entries) > 4 else ""
                self.set_status(
                    f"Imported {n} tileset(s): {names}{extra}.{sk}",
                    kind="ok",
                )
            else:
                self.set_status("Import: nothing added (duplicate ids in registry?)", kind="err")
        except Exception as e:
            print(f"Import failed: {e}", file=sys.stderr)
            self.set_status(f"Import error: {e}", kind="err")

    def rescale_tileset_dialog(self) -> None:
        """FEATURE-MAP-022: Rescale an already-imported tileset in-place."""
        if not self.tileset_defs:
            self.set_status("No tilesets loaded.", kind="err")
            return
        ts_id = self.current_tileset_id()
        meta = self.get_tileset_meta(ts_id)
        if not meta:
            self.set_status(f"Tileset '{ts_id}' not found in registry.", kind="err")
            return
        img_path = ROOT / meta.get("image", "")
        if not img_path.is_file():
            self.set_status(f"Tileset image not found: {img_path}", kind="err")
            return

        try:
            surf = load_pygame_image(str(img_path)).convert_alpha()
        except Exception as e:
            self.set_status(f"Could not load tileset image: {e}", kind="err")
            return

        suggested = _suggest_upscale_factor(surf)

        user_scale: int | None = None
        if sys.platform == "darwin":
            user_scale = _macos_dialog_int(
                f"Rescale '{ts_id}' in-place.\n"
                f"Scale factor (1 = no change, 2 = double, etc.).\n"
                f"Auto-detected suggestion: {suggested}x\n\n"
                f"Warning: maps already using this tileset will need repainting.",
                suggested,
            )
        else:
            try:
                import tkinter as tk
                import tkinter.simpledialog as sd
                root3 = tk.Tk()
                root3.withdraw()
                user_scale = sd.askinteger(
                    "Rescale tileset",
                    f"Scale factor for '{ts_id}' (1=none, 2=double, …). Suggested: {suggested}x",
                    initialvalue=suggested,
                    minvalue=1,
                    maxvalue=8,
                    parent=root3,
                )
                root3.destroy()
            except Exception:
                user_scale = suggested

        if user_scale is None:
            self.set_status("Rescale: cancelled", kind="info")
            return
        user_scale = max(1, min(8, int(user_scale)))
        iw, ih = surf.get_size()
        needs_refold = iw > 256
        if user_scale == 1 and not needs_refold:
            self.set_status("Rescale: scale factor is 1, nothing to do.", kind="info")
            return

        try:
            if user_scale > 1:
                upscaled = pygame.transform.scale(surf, (iw * user_scale, ih * user_scale))
            else:
                upscaled = surf
            upscaled = _refold_to_standard_width(upscaled, 256)
            pygame.image.save(upscaled, str(img_path))
        except Exception as e:
            self.set_status(f"Rescale failed: {e}", kind="err")
            return

        # Invalidate caches so the editor reloads the new image immediately.
        self.sheet_cache.pop(ts_id, None)
        self.meta_cache.pop(ts_id, None)
        self.reload_tileset_sheet()
        self.set_status(
            f"Rescaled '{ts_id}' {user_scale}x. Maps using this tileset will need repainting.",
            kind="ok",
        )

    def run(self) -> None:
        running = True
        mouse_down = False
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    nw, nh = event.size
                    nw = max(MIN_WINDOW_W, nw)
                    nh = max(MIN_WINDOW_H, nh)
                    self.screen = pygame.display.set_mode((nw, nh), pygame.RESIZABLE)
                    self.relayout()
                elif hasattr(pygame, "MOUSEWHEEL") and event.type == pygame.MOUSEWHEEL:
                    mx, my = pygame.mouse.get_pos()
                    if self.open_map_overlay and self._open_map_box_rect.collidepoint(mx, my):
                        self.open_map_scroll = max(0, self.open_map_scroll - int(event.y) * 2)
                        self._sync_open_map_scroll()
                    elif self.world_workspace_open and self.map_canvas_rect.collidepoint(mx, my):
                        r = self.map_canvas_rect
                        z0 = max(WORLD_CAM_ZOOM_MIN, min(WORLD_CAM_ZOOM_MAX, self.world_cam_zoom))
                        mods = pygame.key.get_mods()
                        ctrl_or_meta = bool(mods & pygame.KMOD_CTRL) or bool(mods & pygame.KMOD_META)
                        if ctrl_or_meta:
                            dy = int(event.y)
                            z1 = max(WORLD_CAM_ZOOM_MIN, min(WORLD_CAM_ZOOM_MAX, z0 * (1.1**dy)))
                            lx = float(mx - r.x)
                            ly = float(my - r.y)
                            self.world_cam_x += lx * (1.0 / z0 - 1.0 / z1)
                            self.world_cam_y += ly * (1.0 / z0 - 1.0 / z1)
                            self.world_cam_zoom = z1
                        elif mods & pygame.KMOD_SHIFT:
                            self.world_cam_x -= int(event.y) * WORLD_WHEEL_PAN_TILES / z0
                        else:
                            self.world_cam_y -= int(event.y) * WORLD_WHEEL_PAN_TILES / z0
                    elif (
                        not self.tileset_delete_confirm_id
                        and not self.map_delete_confirm_stem
                        and self.layer_remove_confirm_idx is None
                        and not self.settings_open
                        and not self.size_prompt_active
                        and not self.map_file_prompt_mode
                        and not self.folder_new_prompt_active
                        and not self.folder_color_prompt_id
                    ):
                        if self.tileset_list_rect.collidepoint(mx, my):
                            mods = pygame.key.get_mods()
                            if mods & pygame.KMOD_SHIFT:
                                # FEATURE-MAP-024: horizontal scroll for tileset list
                                self.tileset_list_scroll_x -= int(event.y) * 14
                                self._clamp_tileset_list_scroll_x()
                            else:
                                self.tileset_list_scroll_y -= int(event.y) * 14
                                self._clamp_tileset_list_scroll()
                        elif self.palette_rect.collidepoint(mx, my):
                            mods = pygame.key.get_mods()
                            ctrl_or_meta = bool(mods & pygame.KMOD_CTRL) or bool(mods & pygame.KMOD_META)
                            if ctrl_or_meta:
                                self.palette_zoom_offset += int(event.y)
                                self._clamp_palette_scroll()
                            elif mods & pygame.KMOD_SHIFT:
                                self.palette_scroll_x -= int(event.y) * 18
                                self._clamp_palette_scroll()
                            else:
                                self.palette_scroll_y -= int(event.y) * 18
                                self._clamp_palette_scroll()
                        elif self.map_canvas_rect.collidepoint(mx, my) and not self.world_workspace_open:
                            mods = pygame.key.get_mods()
                            ctrl_or_meta = bool(mods & pygame.KMOD_CTRL) or bool(mods & pygame.KMOD_META)
                            if ctrl_or_meta:
                                # FEATURE-MAP-025: zoom anchored to mouse cursor
                                old_px = self.cell_px
                                step = max(1, old_px // 4)
                                new_px = max(MAP_ZOOM_MIN, min(MAP_ZOOM_MAX, old_px + int(event.y) * step))
                                if new_px != old_px:
                                    # Keep the map coordinate under the cursor fixed
                                    local_x = mx - self.map_origin_x + self.map_view_off_x
                                    local_y = my - self.map_origin_y + self.map_view_off_y
                                    self.cell_px = new_px
                                    self.map_view_off_x = int(local_x * new_px / old_px) - (mx - self.map_origin_x)
                                    self.map_view_off_y = int(local_y * new_px / old_px) - (my - self.map_origin_y)
                            elif mods & pygame.KMOD_SHIFT:
                                # FEATURE-MAP-026: horizontal pan
                                self.map_view_off_x -= int(event.y) * self.cell_px
                            else:
                                # FEATURE-MAP-026: vertical pan
                                self.map_view_off_y -= int(event.y) * self.cell_px
                elif event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    self.hover_cell = (
                        self.map_cell_at_pixel(mx, my)
                        if self.map_canvas_rect.collidepoint(mx, my) and not self.world_workspace_open
                        else None
                    )
                    if self.world_workspace_open and self.world_drag_node_i is not None and mouse_down:
                        wwx, wwy = self._world_screen_to_world(mx, my)
                        n = self.world_nodes[self.world_drag_node_i]
                        n["worldX"] = float(wwx - self._world_drag_off_x)
                        n["worldY"] = float(wwy - self._world_drag_off_y)
                        self._world_fixup_overlaps(self.world_drag_node_i)
                    if self.world_workspace_open and self._world_panning and mouse_down and self._world_pan_last:
                        px, py = self._world_pan_last
                        z = max(WORLD_CAM_ZOOM_MIN, min(WORLD_CAM_ZOOM_MAX, self.world_cam_zoom))
                        self.world_cam_x -= (mx - px) / z
                        self.world_cam_y -= (my - py) / z
                        self._world_pan_last = (mx, my)
                    if mouse_down and self.palette_drag_start and self.palette_rect.collidepoint(event.pos):
                        xy = self.palette_tile_xy_from_pixel(*event.pos)
                        if xy:
                            self.palette_drag_end = xy
                    if (
                        mouse_down
                        and self.map_canvas_rect.collidepoint(event.pos)
                        and not self.world_workspace_open
                        and self.edit_mode in (
                            "paint",
                            "walk",
                        )
                    ):
                        c = self.map_cell_at_pixel(*event.pos)
                        if c:
                            self.map_paint_current = c
                    if (
                        mouse_down
                        and self._tileset_drag_def_index is not None
                        and self._tileset_drag_start is not None
                    ):
                        dx = event.pos[0] - self._tileset_drag_start[0]
                        dy = event.pos[1] - self._tileset_drag_start[1]
                        if dx * dx + dy * dy >= TILESET_LIST_DRAG_THRESHOLD_PX * TILESET_LIST_DRAG_THRESHOLD_PX:
                            self._tileset_drag_moved = True
                    if (
                        mouse_down
                        and self._folder_drag_id is not None
                        and self._folder_drag_start is not None
                    ):
                        dx = event.pos[0] - self._folder_drag_start[0]
                        dy = event.pos[1] - self._folder_drag_start[1]
                        if dx * dx + dy * dy >= TILESET_LIST_DRAG_THRESHOLD_PX * TILESET_LIST_DRAG_THRESHOLD_PX:
                            self._folder_drag_moved = True
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_down = True
                    if self.world_ctx_menu and event.button == 1:
                        hit = self._world_ctx_hit_action(event.pos)
                        if hit is not None:
                            self._world_run_ctx_action(hit)
                        else:
                            self.world_ctx_menu = None
                        continue
                    if self.layer_remove_confirm_idx is not None:
                        self.layer_remove_confirm_idx = None
                        continue
                    if self.tileset_delete_confirm_id:
                        self.tileset_delete_confirm_id = None
                        continue
                    if self.map_delete_confirm_stem:
                        self.map_delete_confirm_stem = None
                        continue
                    if self.world_btn_rect.collidepoint(event.pos):
                        self._clear_all_list_drags()
                        self.world_workspace_open = not self.world_workspace_open
                        self.world_ctx_menu = None
                        self.world_drag_node_i = None
                        self._world_panning = False
                        self._world_pan_last = None
                        continue
                    if self.gear_rect.collidepoint(event.pos):
                        self._clear_all_list_drags()
                        self.settings_open = not self.settings_open
                        continue
                    if self.settings_open:
                        self._clear_all_list_drags()
                        if self.settings_add_event_rect.collidepoint(event.pos):
                            self.add_event_layer()
                        elif self.settings_remove_event_rect.collidepoint(event.pos):
                            self.request_remove_event_layer()
                        elif (
                            event.button == 1
                            and self.settings_remove_current_layer_rect.collidepoint(event.pos)
                        ):
                            if len(self.tile_layers) > 1:
                                self.layer_remove_confirm_idx = self.active_layer_index
                                self.settings_open = False
                        continue
                    if self.open_map_overlay and self._open_map_box_rect.collidepoint(event.pos) and event.button == 1:
                        self._clear_all_list_drags()
                        mx, my = event.pos
                        h = self.screen.get_height()
                        bh = min(480, h - 80)
                        lh = self.font_small.get_linesize() + 4
                        top_y = h // 2 - bh // 2 + 44
                        rel = my - top_y
                        if rel >= 0:
                            row = int(rel // lh)
                            si = self.open_map_scroll + row
                            if 0 <= si < len(self.open_map_stems):
                                self.open_map_sel = si
                                self._sync_open_map_scroll()
                        continue
                    if self.new_folder_btn_rect.collidepoint(event.pos) and event.button == 1:
                        self._clear_all_list_drags()
                        self.add_tileset_folder()
                        continue
                    if self.tileset_list_rect.collidepoint(event.pos):
                        hit, payload = self._tileset_list_hit(*event.pos)
                        if event.button == 3 and hit == "folder" and payload:
                            fid, _chev = payload
                            self._prompt_folder_color(str(fid))
                            continue
                        if event.button != 1:
                            continue
                        if hit == "folder" and payload:
                            fid, is_chevron = payload
                            if is_chevron:
                                self._clear_all_list_drags()
                                self._toggle_folder_collapse(str(fid))
                                self._folder_click_prev_time = 0.0
                            else:
                                now = time.time()
                                if (
                                    str(fid) == self._folder_click_prev_id
                                    and self._folder_click_prev_time > 0
                                    and now - self._folder_click_prev_time < LIST_CLICK_DOUBLE
                                ):
                                    self._clear_all_list_drags()
                                    rows = self._build_tileset_list_rows()
                                    name = ""
                                    for r in rows:
                                        if r.get("row_kind") == "folder" and str(r.get("folder_id")) == str(fid):
                                            name = str(r.get("name", ""))
                                            break
                                    self.folder_rename_id = str(fid)
                                    self.folder_rename_buffer = name
                                    self._folder_click_prev_time = 0.0
                                else:
                                    self._clear_tileset_list_drag()
                                    self._folder_drag_id = str(fid)
                                    self._folder_drag_start = event.pos
                                    self._folder_drag_moved = False
                                    self._folder_click_prev_time = now
                                    self._folder_click_prev_id = str(fid)
                            continue
                        if hit == "tileset" and payload is not None:
                            self._clear_folder_list_drag()
                            idx = int(payload)
                            self._tileset_drag_def_index = idx
                            self._tileset_drag_start = event.pos
                            self._tileset_drag_moved = False
                            now = time.time()
                            if (
                                idx == self._list_click_prev_index
                                and self._list_click_prev_time > 0
                                and now - self._list_click_prev_time < LIST_CLICK_DOUBLE
                            ):
                                self.tileset_rename_index = idx
                                self.tileset_rename_buffer = str(self.tileset_defs[idx].get("id", ""))
                                self._list_click_prev_time = 0.0
                                self._list_click_prev_index = -1
                            else:
                                self.tileset_index = idx
                                self.reload_tileset_sheet()
                                self._sync_brush_tileset()
                                self._list_click_prev_time = now
                                self._list_click_prev_index = idx
                        continue
                    if self.palette_rect.collidepoint(event.pos) and event.button == 1:
                        self._clear_all_list_drags()
                        self.tileset_rename_index = None
                        self.tileset_rename_buffer = ""
                        self.folder_rename_id = None
                        self.folder_rename_buffer = ""
                        xy = self.palette_tile_xy_from_pixel(*event.pos)
                        if xy:
                            self.palette_drag_start = xy
                            self.palette_drag_end = xy
                    elif self.map_canvas_rect.collidepoint(event.pos):
                        self._clear_all_list_drags()
                        self.tileset_rename_index = None
                        self.tileset_rename_buffer = ""
                        self.folder_rename_id = None
                        self.folder_rename_buffer = ""
                        if self.world_workspace_open:
                            mx, my = event.pos
                            if event.button == 3:
                                ni = self._world_hit_node_index(mx, my)
                                self._world_open_context_menu(mx, my, ni)
                                continue
                            if event.button == 2:
                                self._world_undo_checkpoint()
                                self.world_drag_node_i = None
                                self._world_panning = True
                                self._world_pan_last = (mx, my)
                                continue
                            if event.button == 1:
                                ni = self._world_hit_node_index(mx, my)
                                if ni is not None:
                                    self._world_undo_checkpoint()
                                    wx, wy = self._world_screen_to_world(mx, my)
                                    n = self.world_nodes[ni]
                                    self._world_drag_off_x = wx - float(n["worldX"])
                                    self._world_drag_off_y = wy - float(n["worldY"])
                                    self.world_drag_node_i = ni
                                    self._world_panning = False
                                    self._world_pan_last = None
                                else:
                                    self._world_undo_checkpoint()
                                    self.world_drag_node_i = None
                                    self._world_panning = True
                                    self._world_pan_last = (mx, my)
                                continue
                            continue
                        cell = self.map_cell_at_pixel(*event.pos)
                        if not cell:
                            continue
                        cx, cy = cell
                        if self.edit_mode == "paint" and event.button in (1, 3):
                            self.map_drag_start = (cx, cy)
                            self.map_paint_current = (cx, cy)
                            self.map_drag_button = event.button
                        elif self.edit_mode == "walk" and event.button in (1, 3):
                            self.map_drag_start = (cx, cy)
                            self.map_paint_current = (cx, cy)
                            self.map_drag_button = event.button
                        elif self.edit_mode == "transparent":
                            self._undo_checkpoint()
                            self.trans[cy][cx] = 1 if event.button == 1 else 0
                elif event.type == pygame.MOUSEBUTTONUP:
                    mouse_down = False
                    if self.world_workspace_open:
                        snap_i = self.world_drag_node_i
                        self.world_drag_node_i = None
                        self._world_panning = False
                        self._world_pan_last = None
                        if snap_i is not None and 0 <= snap_i < len(self.world_nodes):
                            nn = self.world_nodes[snap_i]
                            self._world_snap_node_origin_to_grid(nn)
                            if not nn.get("interior"):
                                self._world_fixup_overlaps(snap_i)
                            self._world_snap_node_origin_to_grid(nn)
                    if event.button == 1 and self._tileset_drag_def_index is not None:
                        # Drag end: pygame may omit MOUSEMOTION while the button is held; use release vs press delta.
                        drag_commit = self._tileset_drag_moved
                        if self._tileset_drag_start is not None:
                            sx, sy = self._tileset_drag_start
                            px, py = event.pos
                            ddx, ddy = px - sx, py - sy
                            if ddx * ddx + ddy * ddy >= TILESET_LIST_DRAG_THRESHOLD_PX * TILESET_LIST_DRAG_THRESHOLD_PX:
                                drag_commit = True
                        if drag_commit:
                            self._apply_tileset_list_drop(
                                self._tileset_drag_def_index,
                                *event.pos,
                                pygame.key.get_mods(),
                            )
                            self._clamp_tileset_list_scroll()
                        self._clear_tileset_list_drag()
                    elif event.button == 1 and self._folder_drag_id is not None:
                        drag_commit = self._folder_drag_moved
                        if self._folder_drag_start is not None:
                            sx, sy = self._folder_drag_start
                            px, py = event.pos
                            ddx, ddy = px - sx, py - sy
                            if ddx * ddx + ddy * ddy >= TILESET_LIST_DRAG_THRESHOLD_PX * TILESET_LIST_DRAG_THRESHOLD_PX:
                                drag_commit = True
                        if drag_commit:
                            self._apply_folder_block_drop(self._folder_drag_id, *event.pos)
                            self._clamp_tileset_list_scroll()
                        self._clear_folder_list_drag()
                    if self.palette_drag_start and self.palette_drag_end and self.sheet:
                        c0 = self.palette_drag_start
                        c1 = self.palette_drag_end or c0
                        x0, x1 = sorted((c0[0], c1[0]))
                        y0, y1 = sorted((c0[1], c1[1]))
                        ts = self.active_tileset_id
                        pat: list[list[tuple[str, int]]] = []
                        for row in range(y0, y1 + 1):
                            r = []
                            for col in range(x0, x1 + 1):
                                idx = row * self.columns + col + 1
                                r.append((ts, idx))
                            pat.append(r)
                        if pat:
                            self.brush_pattern = pat
                            self._refresh_brush_palette_outline()
                    self.palette_drag_start = None
                    self.palette_drag_end = None
                    if (
                        self.map_drag_start
                        and self.map_paint_current
                        and self.edit_mode == "paint"
                        and event.button == self.map_drag_button
                    ):
                        x0, y0 = self.map_drag_start
                        x1, y1 = self.map_paint_current
                        erase_paint = self.map_drag_button == 3 or self.eraser_mode
                        if self.fill_mode:
                            ax0, ax1 = sorted((x0, x1))
                            ay0, ay1 = sorted((y0, y1))
                            if (x0, y0) == (x1, y1):
                                bh = len(self.brush_pattern)
                                bw = len(self.brush_pattern[0]) if bh else 1
                                if bw * bh <= 1:
                                    self._flood_fill_at(x0, y0, erase_paint)
                                else:
                                    bo = (x0, y0)
                                    snap = copy.deepcopy(self._active_grid())
                                    self._undo_checkpoint()
                                    tot = 0
                                    for _fj in range(bh):
                                        for _fi in range(bw):
                                            _sx = x0 + _fi
                                            _sy = y0 + _fj
                                            if 0 <= _sx < self.map_w and 0 <= _sy < self.map_h:
                                                tot += self._flood_fill_at(
                                                    _sx, _sy, erase_paint,
                                                    record_undo=False,
                                                    match_grid=snap,
                                                    brush_origin=bo,
                                                )
                            else:
                                snap = copy.deepcopy(self._active_grid())
                                clip_rect = (ax0, ay0, ax1, ay1)
                                self._undo_checkpoint()
                                tot = 0
                                ro = (ax0, ay0)
                                for cy in range(ay0, ay1 + 1):
                                    for cx in range(ax0, ax1 + 1):
                                        tot += self._flood_fill_at(
                                            cx,
                                            cy,
                                            erase_paint,
                                            record_undo=False,
                                            match_grid=snap,
                                            clip_rect=clip_rect,
                                            brush_origin=ro,
                                        )
                        else:
                            self._undo_checkpoint()
                            if (x0, y0) == (x1, y1):
                                self.apply_brush_at(x0, y0, erase_paint)
                            else:
                                self.fill_rect_with_brush(x0, y0, x1, y1, erase_paint)
                    elif (
                        self.map_drag_start
                        and self.map_paint_current
                        and self.edit_mode == "walk"
                        and event.button == self.map_drag_button
                    ):
                        x0, y0 = self.map_drag_start
                        x1, y1 = self.map_paint_current
                        ax0, ax1 = sorted((x0, x1))
                        ay0, ay1 = sorted((y0, y1))
                        val = 1 if self.map_drag_button == 1 else 0
                        self._undo_checkpoint()
                        for wy in range(ay0, ay1 + 1):
                            for wx in range(ax0, ax1 + 1):
                                if 0 <= wx < self.map_w and 0 <= wy < self.map_h:
                                    self.walk[wy][wx] = val
                    self.map_drag_start = None
                    self.map_paint_current = None
                elif event.type == pygame.KEYDOWN:
                    if self.layer_remove_confirm_idx is not None:
                        if event.key in (pygame.K_ESCAPE, pygame.K_n, pygame.K_BACKSPACE):
                            self.layer_remove_confirm_idx = None
                        elif event.key in (pygame.K_RETURN, pygame.K_y) or (
                            event.unicode and event.unicode.lower() == "y"
                        ):
                            idx = self.layer_remove_confirm_idx
                            self.layer_remove_confirm_idx = None
                            if idx is not None:
                                self._remove_tile_layer_at(idx)
                        continue
                    if self.tileset_delete_confirm_id:
                        if event.key in (pygame.K_ESCAPE, pygame.K_n, pygame.K_BACKSPACE):
                            self.tileset_delete_confirm_id = None
                        elif event.key in (pygame.K_RETURN, pygame.K_y) or (
                            event.unicode and event.unicode.lower() == "y"
                        ):
                            tid = self.tileset_delete_confirm_id
                            self.tileset_delete_confirm_id = None
                            if tid:
                                self.delete_tileset(tid)
                        continue
                    if self.map_delete_confirm_stem:
                        if event.key in (pygame.K_ESCAPE, pygame.K_n, pygame.K_BACKSPACE):
                            self.map_delete_confirm_stem = None
                        elif event.key in (pygame.K_RETURN, pygame.K_y) or (
                            event.unicode and event.unicode.lower() == "y"
                        ):
                            self._confirm_delete_map_file()
                        continue
                    if self.map_file_prompt_mode in ("first_save", "save_as"):
                        if event.key == pygame.K_ESCAPE:
                            self._cancel_map_prompt()
                        elif event.key in _ENTER_KEYS:
                            self._try_commit_map_prompt()
                        elif event.key == pygame.K_BACKSPACE:
                            self.map_file_prompt_buffer = self.map_file_prompt_buffer[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            if event.unicode.isalnum() or event.unicode in "._-":
                                self.map_file_prompt_buffer += event.unicode
                        continue
                    if self.map_file_prompt_mode == "overwrite":
                        if event.key in (pygame.K_ESCAPE, pygame.K_n) or (
                            event.unicode and event.unicode.lower() == "n"
                        ):
                            buf = self.map_overwrite_candidate_id or ""
                            self.map_overwrite_candidate_id = None
                            self.map_file_prompt_mode = (
                                "save_as" if self._map_save_pending_is_save_as else "first_save"
                            )
                            self.map_file_prompt_buffer = buf
                        elif event.key in _ENTER_KEYS or event.key == pygame.K_y or (
                            event.unicode and event.unicode.lower() == "y"
                        ):
                            self._confirm_map_overwrite()
                        continue
                    if self.open_map_overlay:
                        if self.edit_mode not in ("map_id", "conn") and event_matches_key(
                            event, self.key_config.get("open_map", [])
                        ):
                            self.open_map_interactive()
                            continue
                        n = len(self.open_map_stems)
                        visible = self._open_map_visible_rows()
                        if event.key == pygame.K_ESCAPE:
                            self.open_map_overlay = False
                        elif event.key in _ENTER_KEYS:
                            self._open_map_load_selected()
                        elif event.key == pygame.K_UP:
                            self.open_map_sel = max(0, self.open_map_sel - 1)
                            self._sync_open_map_scroll()
                        elif event.key == pygame.K_DOWN:
                            self.open_map_sel = min(max(0, n - 1), self.open_map_sel + 1)
                            self._sync_open_map_scroll()
                        elif event.key in _OPEN_MAP_PGUP_KEYS:
                            self.open_map_sel = max(0, self.open_map_sel - visible)
                            self._sync_open_map_scroll()
                        elif event.key in _OPEN_MAP_PGDN_KEYS:
                            self.open_map_sel = min(max(0, n - 1), self.open_map_sel + visible)
                            self._sync_open_map_scroll()
                        continue
                    if self.folder_new_prompt_active:
                        if event.key == pygame.K_ESCAPE:
                            self.folder_new_prompt_active = False
                            self.folder_new_prompt_buffer = ""
                        elif event.key in _ENTER_KEYS:
                            self._commit_tileset_folder(self.folder_new_prompt_buffer or "Folder")
                            self.folder_new_prompt_active = False
                            self.folder_new_prompt_buffer = ""
                        elif event.key == pygame.K_BACKSPACE:
                            self.folder_new_prompt_buffer = self.folder_new_prompt_buffer[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            self.folder_new_prompt_buffer += event.unicode
                        continue
                    if self.folder_color_prompt_id:
                        if event.key == pygame.K_ESCAPE:
                            self.folder_color_prompt_id = None
                            self.folder_color_prompt_buffer = ""
                        elif event.key in _ENTER_KEYS:
                            self._apply_folder_color_prompt()
                        elif event.key == pygame.K_BACKSPACE:
                            self.folder_color_prompt_buffer = self.folder_color_prompt_buffer[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            if event.unicode.isdigit() or event.unicode in ",-":
                                self.folder_color_prompt_buffer += event.unicode
                        continue
                    if self.folder_rename_id is not None:
                        if event.key == pygame.K_ESCAPE:
                            self.folder_rename_id = None
                            self.folder_rename_buffer = ""
                        elif event.key in _ENTER_KEYS:
                            self._apply_folder_rename()
                        elif event.key == pygame.K_BACKSPACE:
                            self.folder_rename_buffer = self.folder_rename_buffer[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            self.folder_rename_buffer += event.unicode
                        continue
                    if self.tileset_rename_index is not None:
                        if event.key == pygame.K_ESCAPE:
                            self.tileset_rename_index = None
                            self.tileset_rename_buffer = ""
                        elif event.key in _ENTER_KEYS:
                            ri = self.tileset_rename_index
                            if ri is not None and 0 <= ri < len(self.tileset_defs):
                                old = str(self.tileset_defs[ri].get("id", ""))
                                if self.apply_rename_tileset(old, self.tileset_rename_buffer):
                                    self.tileset_rename_index = None
                                    self.tileset_rename_buffer = ""
                            else:
                                self.tileset_rename_index = None
                                self.tileset_rename_buffer = ""
                        elif event.key == pygame.K_BACKSPACE:
                            self.tileset_rename_buffer = self.tileset_rename_buffer[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            if event.unicode.isalnum() or event.unicode in "._-":
                                self.tileset_rename_buffer += event.unicode
                        continue
                    if self.settings_open:
                        if event.key == pygame.K_ESCAPE:
                            self.settings_open = False
                        elif event.key == pygame.K_s:
                            save_key_config(self.key_config)
                        elif event.key == pygame.K_r:
                            self.key_config = default_key_config()
                        continue
                    if self.size_prompt_active:
                        if event.key == pygame.K_ESCAPE:
                            self.size_prompt_active = False
                            self.text_buffer = ""
                        elif event.key in _ENTER_KEYS:
                            self.parse_size_and_apply()
                        elif event.key == pygame.K_BACKSPACE:
                            self.text_buffer = self.text_buffer[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            self.text_buffer += event.unicode
                        continue
                    del_key = event.key == pygame.K_DELETE
                    # macOS: the key labeled Delete (⌫) sends BACKSPACE, not DELETE.
                    del_like = del_key or (
                        event.key == pygame.K_BACKSPACE
                        and self.edit_mode == "paint"
                        and self.tileset_rename_index is None
                        and self.folder_rename_id is None
                    )
                    if del_like:
                        if self.tileset_rename_index is None and len(self.tileset_defs) > 1:
                            self.tileset_delete_confirm_id = self.current_tileset_id()
                        continue
                    elif event.key == pygame.K_ESCAPE:
                        if self.open_map_overlay:
                            self.open_map_overlay = False
                            self.open_map_purpose = "load"
                        elif self.world_ctx_menu:
                            self.world_ctx_menu = None
                        elif self.world_workspace_open:
                            self.world_workspace_open = False
                            self.world_ctx_menu = None
                            self.world_drag_node_i = None
                            self._world_panning = False
                            self._world_pan_last = None
                        elif self.folder_new_prompt_active:
                            self.folder_new_prompt_active = False
                            self.folder_new_prompt_buffer = ""
                        elif self.folder_color_prompt_id:
                            self.folder_color_prompt_id = None
                            self.folder_color_prompt_buffer = ""
                        else:
                            running = False
                    elif self.edit_mode not in ("map_id", "conn") and event.key == pygame.K_s:
                        mods = pygame.key.get_mods()
                        if mods & pygame.KMOD_CTRL:
                            self.save()
                        elif mods & pygame.KMOD_SHIFT or event_matches_key(
                            event, self.key_config.get("save_as", [])
                        ):
                            self.save_as()
                        elif event_matches_key(event, self.key_config.get("save", [])):
                            self.save()
                    elif self.edit_mode not in ("map_id", "conn") and event_matches_key(
                        event, self.key_config.get("new_map", [])
                    ):
                        self.new_map(reset_connections=True)
                    elif self.edit_mode not in ("map_id", "conn") and event_matches_key(
                        event, self.key_config.get("import_tileset", [])
                    ):
                        self.import_tileset_dialog()
                    elif self.edit_mode not in ("map_id", "conn") and event_matches_key(
                        event, self.key_config.get("rescale_tileset", [])
                    ):
                        self.rescale_tileset_dialog()
                    elif self.edit_mode not in ("map_id", "conn") and event_matches_key(
                        event, self.key_config.get("set_map_size", [])
                    ):
                        self.size_prompt_active = True
                        self.text_buffer = ""
                    elif self.edit_mode not in ("map_id", "conn") and event_matches_key(
                        event, self.key_config.get("cycle_mode", [])
                    ):
                        self.cycle_edit_mode()
                    elif self.edit_mode not in ("map_id", "conn") and event_matches_key(
                        event, self.key_config.get("toggle_help", [])
                    ):
                        self.footer_help_expanded = not self.footer_help_expanded
                    elif (
                        self.world_workspace_open
                        and self.edit_mode not in ("map_id", "conn")
                        and event_matches_key(event, self.key_config.get("toggle_world_labels", []))
                    ):
                        self.world_map_labels_visible = not self.world_map_labels_visible
                        self.set_status(
                            "World map name badges "
                            + ("on" if self.world_map_labels_visible else "off"),
                            kind="info",
                        )
                    elif (
                        self.tileset_rename_index is None
                        and self.folder_rename_id is None
                        and self.edit_mode == "paint"
                        and not getattr(event, "repeat", False)
                        and event_matches_key(event, self.key_config.get("toggle_eraser", []))
                    ):
                        # BUG-MAP-014: ignore key-repeat KEYDOWNs so toggles flip once per physical press
                        self.eraser_mode = not self.eraser_mode
                    elif (
                        self.tileset_rename_index is None
                        and self.folder_rename_id is None
                        and self.edit_mode == "paint"
                        and not getattr(event, "repeat", False)
                        and event_matches_key(event, self.key_config.get("toggle_fill", []))
                    ):
                        self.fill_mode = not self.fill_mode
                    elif (
                        self.tileset_rename_index is None
                        and self.folder_rename_id is None
                        and self.edit_mode not in ("map_id", "conn")
                        and event_matches_key(event, self.key_config.get("delete_map", []))
                    ):
                        self.request_delete_map_file()
                    elif (
                        self.tileset_rename_index is None
                        and self.edit_mode not in ("map_id", "conn")
                        and event_matches_key(event, self.key_config.get("undo", []))
                    ):
                        mx, my = pygame.mouse.get_pos()
                        if self.world_workspace_open and self.map_canvas_rect.collidepoint(mx, my):
                            self.undo_world_edit()
                        else:
                            self.undo_map_edit()
                    elif (
                        self.tileset_rename_index is None
                        and self.edit_mode not in ("map_id", "conn")
                        and event_matches_key(event, self.key_config.get("redo", []))
                    ):
                        mx, my = pygame.mouse.get_pos()
                        if self.world_workspace_open and self.map_canvas_rect.collidepoint(mx, my):
                            self.redo_world_edit()
                        else:
                            self.redo_map_edit()
                    elif (
                        self.world_workspace_open
                        and self.edit_mode not in ("map_id", "conn")
                        and not self.open_map_overlay
                        and not self.settings_open
                        and event.key == pygame.K_F9
                    ):
                        self._world_export_layout_file()
                    elif self.edit_mode not in ("map_id", "conn") and event_matches_key(
                        event, self.key_config.get("layer_prev", [])
                    ):
                        if pygame.key.get_mods() & pygame.KMOD_ALT:
                            self._move_tileset_in_order(self.tileset_index, -1)
                        elif self.tile_layers:
                            self.active_layer_index = (self.active_layer_index - 1) % len(
                                self.tile_layers
                            )
                    elif self.edit_mode not in ("map_id", "conn") and event_matches_key(
                        event, self.key_config.get("layer_next", [])
                    ):
                        if pygame.key.get_mods() & pygame.KMOD_ALT:
                            self._move_tileset_in_order(self.tileset_index, 1)
                        elif self.tile_layers:
                            self.active_layer_index = (self.active_layer_index + 1) % len(
                                self.tile_layers
                            )
                    elif self.edit_mode not in ("map_id", "conn") and event_matches_key(
                        event, self.key_config.get("layer_add", [])
                    ):
                        self.add_tile_layer()
                    elif self.edit_mode not in ("map_id", "conn") and event_matches_key(
                        event, self.key_config.get("layer_remove", [])
                    ):
                        if len(self.tile_layers) <= 1:
                            self.set_status("Cannot remove the last tile layer.", kind="err")
                        else:
                            self.layer_remove_confirm_idx = self.active_layer_index
                    elif event.key == pygame.K_i:
                        self.edit_mode = "map_id" if self.edit_mode != "map_id" else "paint"
                        self.text_buffer = ""
                    elif event.key == pygame.K_c:
                        self.edit_mode = "conn"
                        self.conn_field_index = (self.conn_field_index + 1) % 12
                        self.text_buffer = ""
                    elif event.key in _ENTER_KEYS:
                        if self.edit_mode == "map_id":
                            nid = self.text_buffer.strip()
                            if nid:
                                self.map_id = nid
                            self.text_buffer = ""
                            self.edit_mode = "paint"
                        elif self.edit_mode == "conn":
                            self.apply_text_buffer_to_connection()
                    elif event.key == pygame.K_BACKSPACE and self.edit_mode in ("map_id", "conn"):
                        self.text_buffer = self.text_buffer[:-1]
                    elif event_matches_key(event, self.key_config.get("map_prev_file", [])):
                        if self.map_files:
                            self.map_file_index = (self.map_file_index - 1) % len(self.map_files)
                            self.try_load_map_by_id(self.map_files[self.map_file_index].stem)
                    elif event_matches_key(event, self.key_config.get("map_next_file", [])):
                        if self.map_files:
                            self.map_file_index = (self.map_file_index + 1) % len(self.map_files)
                            self.try_load_map_by_id(self.map_files[self.map_file_index].stem)
                    elif event_matches_key(event, self.key_config.get("tileset_prev", [])):
                        self.tileset_index = (self.tileset_index - 1) % len(self.tileset_defs)
                        self.reload_tileset_sheet()
                        self._sync_brush_tileset()
                    elif event_matches_key(event, self.key_config.get("tileset_next", [])):
                        self.tileset_index = (self.tileset_index + 1) % len(self.tileset_defs)
                        self.reload_tileset_sheet()
                        self._sync_brush_tileset()
                    elif event.key == pygame.K_t:
                        self.tileset_index = (self.tileset_index + 1) % len(self.tileset_defs)
                        self.reload_tileset_sheet()
                        self._sync_brush_tileset()
                    elif self.edit_mode not in ("map_id", "conn") and event_matches_key(
                        event, self.key_config.get("open_map", [])
                    ):
                        self.open_map_interactive()
                    elif event.unicode and event.unicode.isprintable():
                        ch = event.unicode
                        if self.edit_mode == "map_id":
                            if ch.isalnum() or ch in ("_", "-"):
                                self.text_buffer += ch
                        elif self.edit_mode == "conn":
                            fi = self.conn_field_index
                            sub_i = fi % 3
                            sub = self.conn_field_names[sub_i]
                            if sub in ("entryTileX", "entryTileY"):
                                if ch.isdigit() or ch == "-":
                                    self.text_buffer += ch
                            else:
                                self.text_buffer += ch
                    elif event_matches_key(event, self.key_config.get("pan_up", [])):
                        self.map_view_off_y -= self.cell_px * 2
                    elif event_matches_key(event, self.key_config.get("pan_down", [])):
                        self.map_view_off_y += self.cell_px * 2
                    elif event_matches_key(event, self.key_config.get("pan_left", [])):
                        self.map_view_off_x -= self.cell_px * 2
                    elif event_matches_key(event, self.key_config.get("pan_right", [])):
                        self.map_view_off_x += self.cell_px * 2

            self.draw()
            self.clock.tick(60)

        pygame.quit()

    def add_tile_layer(self) -> None:
        w, h = self.map_w, self.map_h
        empty = [[None for _ in range(w)] for _ in range(h)]
        lid = self._unique_layer_id()
        self.tile_layers.append(empty)
        self.tile_layer_ids.append(lid)
        self.active_layer_index = len(self.tile_layers) - 1
        self.set_status(f"Added tile layer '{lid}'.", kind="ok")

    def _remove_tile_layer_at(self, idx: int) -> None:
        if len(self.tile_layers) <= 1:
            self.set_status("Cannot remove the last tile layer.", kind="err")
            return
        if not (0 <= idx < len(self.tile_layers)):
            return
        del self.tile_layers[idx]
        del self.tile_layer_ids[idx]
        if self.active_layer_index >= len(self.tile_layers):
            self.active_layer_index = len(self.tile_layers) - 1
        elif idx < self.active_layer_index:
            self.active_layer_index -= 1
        self.set_status("Removed tile layer.", kind="ok")

    def _sync_brush_tileset(self) -> None:
        ts = self.active_tileset_id
        if not self.brush_pattern or not self.brush_pattern[0]:
            self.brush_pattern = [[(ts, 1)]]
            return
        h = len(self.brush_pattern)
        w = len(self.brush_pattern[0])
        self.brush_pattern = [[(ts, self.brush_pattern[j][i][1]) for i in range(w)] for j in range(h)]
        self._refresh_brush_palette_outline()


def main() -> None:
    if not TILESETS_JSON.is_file():
        raise SystemExit(f"Missing {TILESETS_JSON}")
    ensure_maps_dir()
    write_maps_index()
    MapEditor().run()


if __name__ == "__main__":
    main()

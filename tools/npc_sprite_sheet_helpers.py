"""FEATURE-MAP-100: pure helpers for 4×4 NPC character sheet layout and pixel ops."""
from __future__ import annotations

from pathlib import Path

DEFAULT_SHEET_W = 128
DEFAULT_SHEET_H = 192
GRID_COLS = 4
GRID_ROWS = 4

DIRECTIONS = ("down", "left", "right", "up")
DIRECTION_ROW = {name: idx for idx, name in enumerate(DIRECTIONS)}

RGBA = tuple[int, int, int, int]
PixelGrid = list[list[RGBA]]


def validate_sheet_dimensions(w: int, h: int) -> tuple[bool, str]:
    """Return (ok, message). Sheet must divide evenly into a 4×4 grid with positive cells."""
    if w <= 0 or h <= 0:
        return False, "Width and height must be positive."
    if w % GRID_COLS != 0 or h % GRID_ROWS != 0:
        return False, f"Sheet must divide evenly into {GRID_COLS}×{GRID_ROWS} cells."
    cw, ch = w // GRID_COLS, h // GRID_ROWS
    if cw < 1 or ch < 1:
        return False, "Cell size must be at least 1×1."
    return True, ""


def cell_size_for_sheet(w: int, h: int) -> tuple[int, int]:
    return w // GRID_COLS, h // GRID_ROWS


def frame_index(direction: str, frame_col: int) -> int:
    """Linear index into the 4×4 sheet (row-major). *frame_col* is 0..3 within the direction row."""
    row = DIRECTION_ROW.get(direction, 0)
    col = max(0, min(GRID_COLS - 1, int(frame_col)))
    return row * GRID_COLS + col


def frame_grid_pos(frame_idx: int) -> tuple[int, int, int]:
    """Return (sheet_row, sheet_col, direction_row_index) for *frame_idx*."""
    idx = max(0, min(GRID_COLS * GRID_ROWS - 1, int(frame_idx)))
    row = idx // GRID_COLS
    col = idx % GRID_COLS
    return row, col, row


def direction_name_for_row(row: int) -> str:
    r = max(0, min(len(DIRECTIONS) - 1, int(row)))
    return DIRECTIONS[r]


def mirror_pixels_horizontal(pixels: PixelGrid) -> PixelGrid:
    """Return a new grid with each row mirrored left↔right."""
    if not pixels:
        return []
    out: PixelGrid = []
    for row in pixels:
        out.append(list(reversed(row)))
    return out


def blank_rgba_frame(w: int, h: int, fill: RGBA = (0, 0, 0, 0)) -> PixelGrid:
    w = max(1, int(w))
    h = max(1, int(h))
    return [[fill for _ in range(w)] for _ in range(h)]


def copy_pixel_grid(pixels: PixelGrid) -> PixelGrid:
    return [list(row) for row in pixels]


def extract_frame_from_rgba_sheet(
    sheet: PixelGrid,
    direction: str,
    frame_col: int,
    sheet_w: int,
    sheet_h: int,
) -> PixelGrid:
    """Copy one cell from a full-sheet RGBA grid."""
    cw, ch = cell_size_for_sheet(sheet_w, sheet_h)
    row = DIRECTION_ROW.get(direction, 0)
    col = max(0, min(GRID_COLS - 1, int(frame_col)))
    x0 = col * cw
    y0 = row * ch
    out: PixelGrid = []
    for dy in range(ch):
        src_y = y0 + dy
        if src_y >= len(sheet):
            out.append([(0, 0, 0, 0) for _ in range(cw)])
            continue
        src_row = sheet[src_y]
        out.append([src_row[x0 + dx] if x0 + dx < len(src_row) else (0, 0, 0, 0) for dx in range(cw)])
    return out


def blit_frame_into_rgba_sheet(
    sheet: PixelGrid,
    frame: PixelGrid,
    direction: str,
    frame_col: int,
    sheet_w: int,
    sheet_h: int,
) -> None:
    """Write *frame* pixels into *sheet* (mutates *sheet*)."""
    cw, ch = cell_size_for_sheet(sheet_w, sheet_h)
    row = DIRECTION_ROW.get(direction, 0)
    col = max(0, min(GRID_COLS - 1, int(frame_col)))
    x0 = col * cw
    y0 = row * ch
    for dy in range(ch):
        dst_y = y0 + dy
        while len(sheet) <= dst_y:
            sheet.append([(0, 0, 0, 0) for _ in range(sheet_w)])
        dst_row = sheet[dst_y]
        while len(dst_row) < sheet_w:
            dst_row.append((0, 0, 0, 0))
        src_row = frame[dy] if dy < len(frame) else []
        for dx in range(cw):
            dst_row[x0 + dx] = src_row[dx] if dx < len(src_row) else (0, 0, 0, 0)


def sheet_dimensions_warning(w: int, h: int) -> str | None:
    if w != DEFAULT_SHEET_W or h != DEFAULT_SHEET_H:
        return f"Non-standard size {w}×{h}; engine default is {DEFAULT_SHEET_W}×{DEFAULT_SHEET_H}."
    return None


def list_character_pngs(characters_dir: Path) -> list[str]:
    """Flat *.png filenames under *characters_dir* (non-recursive), sorted."""
    if not characters_dir.is_dir():
        return []
    names = [p.name for p in characters_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png"]
    return sorted(names, key=str.lower)


def sanitize_character_filename(name: str) -> str:
    """Basename safe for src/Graphics/Characters/."""
    base = Path(name.strip()).name
    if not base.lower().endswith(".png"):
        base = f"{base}.png"
    safe = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in base)
    return safe.strip() or "npc_sprite.png"

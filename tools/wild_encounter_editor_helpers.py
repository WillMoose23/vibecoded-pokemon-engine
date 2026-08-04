"""FEATURE-MAP-053 / FEATURE-MAP-056: wild encounter species list and stride-grid snap."""
from __future__ import annotations


def wild_species_display_list(
    all_keys: list[str],
    favorites: set[str] | frozenset[str],
    filter_text: str,
) -> list[str]:
    """Starred species first (alpha), then others (alpha); optional case-insensitive filter."""
    key_set = set(all_keys)
    fav_sorted = sorted(k for k in favorites if k in key_set)
    rest_sorted = sorted(k for k in all_keys if k not in favorites)
    q = (filter_text or "").strip().lower()
    if q:
        fav_sorted = [k for k in fav_sorted if q in k.lower()]
        rest_sorted = [k for k in rest_sorted if q in k.lower()]
    return fav_sorted + rest_sorted


def wild_species_default_for_new_row(
    all_keys: list[str],
    favorites: set[str] | frozenset[str],
) -> str:
    """First favorite in sorted order, else first species key, else Bidoof."""
    if favorites:
        ordered = wild_species_display_list(all_keys, favorites, "")
        if ordered:
            return ordered[0]
    if all_keys:
        return all_keys[0]
    return "Bidoof"


def player_stride_grid_ok(tile_x: int, tile_y: int, pw: int, ph: int, draw_off_x: int) -> bool:
    """True when (tile_x, tile_y) is a K-orange stride anchor (same rules as map editor overlay)."""
    stride_x = max(1, pw)
    stride_y = max(1, ph)
    phase_x = draw_off_x % stride_x
    return (tile_x + phase_x) % stride_x == 0 and tile_y % stride_y == 0


def snap_cell_to_stride_grid(tile_x: int, tile_y: int, pw: int, ph: int, draw_off_x: int) -> tuple[int, int]:
    """FEATURE-MAP-056: snap to nearest stride anchor (Manhattan) matching K overlay grid."""
    stride_x = max(1, pw)
    stride_y = max(1, ph)
    phase_x = draw_off_x % stride_x
    if player_stride_grid_ok(tile_x, tile_y, pw, ph, draw_off_x):
        return tile_x, tile_y

    def align_base(v: int, phase: int, stride: int) -> int:
        return v - ((v + phase) % stride)

    bx = align_base(tile_x, phase_x, stride_x)
    by = align_base(tile_y, 0, stride_y)
    candidates: list[tuple[int, int]] = []
    for dx in (0, stride_x):
        for dy in (0, stride_y):
            candidates.append((bx + dx, by + dy))
    best: tuple[int, int] | None = None
    best_d = 10**9
    for cx, cy in candidates:
        d = abs(cx - tile_x) + abs(cy - tile_y)
        if d < best_d:
            best_d = d
            best = (cx, cy)
    return best if best is not None else (tile_x, tile_y)

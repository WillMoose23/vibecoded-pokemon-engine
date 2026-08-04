"""Shared word-wrap and width-aware text helpers for UI-Standard modals."""
from __future__ import annotations

import pygame


def wrap_lines_to_width(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    """Break *text* into lines that fit within *max_w* pixels (word wrap + char break fallback)."""
    if not text:
        return []
    max_w = max(8, max_w)
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


def truncate_to_width(font: pygame.font.Font, text: str, max_w: int) -> str:
    """Single-line ellipsis truncation to fit *max_w* pixels."""
    if not text or font.size(text)[0] <= max_w:
        return text
    ell = "\u2026"
    t = text
    while len(t) > 0 and font.size(t + ell)[0] > max_w:
        t = t[:-1]
    return t + ell if t else ell


def field_text_y(font: pygame.font.Font, rect: pygame.Rect, min_pad: int = 2) -> int:
    """Y coordinate that vertically centers single-line text inside a field rect."""
    return rect.y + max(min_pad, (rect.h - font.get_height()) // 2)


def field_text_x(rect: pygame.Rect, pad: int = 4) -> int:
    return rect.x + pad


# Shared form-layout metrics for UI-Standard modals (FEATURE-MAP-083).
FORM_LABEL_COL_W = 100
FORM_FIELD_PAD_X = 6
FORM_FIELD_H_PAD = 10
FORM_HELP_GAP = 6
FORM_ROW_GAP = 14
FORM_SECTION_TOP = 8


def form_label_x(body: pygame.Rect) -> int:
    return body.x


def form_field_x(body: pygame.Rect) -> int:
    return body.x + FORM_LABEL_COL_W + 8


def form_field_w(body: pygame.Rect, pick_w: int = 0) -> int:
    return max(40, body.w - FORM_LABEL_COL_W - 8 - pick_w)


def form_field_h(font: pygame.font.Font) -> int:
    return font.get_linesize() + FORM_FIELD_H_PAD


def form_label_y(font: pygame.font.Font, field_rect: pygame.Rect) -> int:
    return field_text_y(font, field_rect)


def form_help_y(field_rect: pygame.Rect) -> int:
    return field_rect.bottom + FORM_HELP_GAP


def form_row_advance(
    field_rect: pygame.Rect,
    help_line_count: int,
    font: pygame.font.Font,
    *,
    has_help: bool,
) -> int:
    """Return logical Y delta after one form row (field + optional wrapped help)."""
    if has_help and help_line_count > 0:
        return (field_rect.bottom - field_rect.y) + FORM_HELP_GAP + help_line_count * font.get_linesize() + FORM_ROW_GAP
    return (field_rect.bottom - field_rect.y) + FORM_ROW_GAP


def blit_wrapped_lines(
    surf: pygame.Surface,
    font: pygame.font.Font,
    lines: list[str],
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> int:
    """Draw *lines* starting at (x, y). Returns the Y coordinate below the last line."""
    lh = font.get_linesize()
    cy = y
    for ln in lines:
        surf.blit(font.render(ln, True, color), (x, cy))
        cy += lh
    return cy

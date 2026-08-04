---
name: Wild Modal QA Fixes
overview: Fix two modal bugs (diagonal pan, species scroll reset) and add bottom-left resize corner plus title-bar drag-to-move. Orange tiles are confirmed NOT a bug.
todos:
  - id: tracker-060-062
    content: Log FEATURE-MAP-060, BUG-MAP-061, BUG-MAP-062 in docs/tracker.md
    status: completed
  - id: state-drag-mode
    content: Replace _resize_drag bool with _drag_mode str + _drag_ref; add _resize_corner_br/bl + _title_bar rects to __init__ and open_modal
    status: completed
  - id: draw-titlebar-grips
    content: Draw title-bar grip dots and bottom-left triangle; update _resize_corner_br/bl positions in draw()
    status: completed
  - id: input-drag-modes
    content: Update handle_mouse_down/motion/up for resize_br, resize_bl, and move drag modes
    status: completed
  - id: fix-pan-diagonal
    content: "BUG-MAP-061: fix handle_wheel to only pan Y on plain scroll; Shift+scroll pans X"
    status: completed
  - id: fix-species-scroll
    content: "BUG-MAP-062: add _species_vis, remove upward auto-correction in _draw_species_column, clamp in handle_wheel"
    status: completed
  - id: docs-060-062
    content: Update docs/tools_doc.md; mark tracker entries DONE
    status: completed
isProject: false
---

# Wild Modal QA Fixes

## Orange tiles — NOT a bug

The orange overlay is the K-key stride-grid (`ed.show_valid_player_stands_orange`), shared with the main editor by design (FEATURE-MAP-056). No code change needed.

---

## Tracker entries (log before implementation)

- `FEATURE-MAP-060` — Bottom-left resize corner + title-bar drag-to-move
- `BUG-MAP-061` — Mini-map pan scrolls both X and Y simultaneously (diagonal)
- `BUG-MAP-062` — Species list scroll resets to top immediately

---

## Files changed

- [`tools/wild_encounter_modal.py`](tools/wild_encounter_modal.py) — all code changes
- [`docs/tracker.md`](docs/tracker.md) — three new entries
- [`docs/tools_doc.md`](docs/tools_doc.md) — update wild_encounter_modal.py notes

---

## FEATURE-MAP-060 — Bottom-left resize + title-bar drag-to-move

### State changes in `__init__`

Replace the bool flag with a mode string; add two new rects:

```python
# replace: self._resize_drag: bool = False
# replace: self._resize_anchor: tuple[int, int] = (0, 0)
# replace: self._resize_corner: pygame.Rect = ...
self._drag_mode: str = "none"          # "none" | "resize_br" | "resize_bl" | "move"
self._drag_ref: tuple[int, int] = (0, 0)
self._resize_corner_br: pygame.Rect = pygame.Rect(0, 0, 16, 16)
self._resize_corner_bl: pygame.Rect = pygame.Rect(0, 0, 16, 16)
self._title_bar: pygame.Rect = pygame.Rect(0, 0, 1, 1)
```

### `open_modal` — reset drag mode

```python
self._drag_mode = "none"   # was: self._resize_drag = False
```

### `draw()` — define rects and draw new affordances

After computing `panel` and `head_h = 36`:

```python
# Title-bar drag handle (full header strip minus close button)
self._title_bar = pygame.Rect(panel.x, panel.y, panel.w - 80, head_h)
# Draw subtle grip dots in the centre of the title bar
for i in range(5):
    gx = panel.centerx - 20 + i * 10
    pygame.draw.circle(ed.screen, (70, 130, 100), (gx, panel.y + head_h // 2), 2)
```

At the end of `draw()`, alongside the existing BR triangle:

```python
# Bottom-right grip (rename from _resize_corner)
self._resize_corner_br = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
pygame.draw.polygon(ed.screen, (90, 160, 120), [
    (panel.right - 2, panel.bottom - 14),
    (panel.right - 2, panel.bottom - 2),
    (panel.right - 14, panel.bottom - 2),
])
# Bottom-left grip
self._resize_corner_bl = pygame.Rect(panel.x, panel.bottom - 16, 16, 16)
pygame.draw.polygon(ed.screen, (90, 160, 120), [
    (panel.x + 2,  panel.bottom - 14),
    (panel.x + 2,  panel.bottom - 2),
    (panel.x + 14, panel.bottom - 2),
])
```

### `handle_mouse_down` — hit-test new grips and title bar

Replace existing `_resize_corner` block:

```python
if self._resize_corner_br.collidepoint(mx, my) and button == 1:
    self._drag_mode = "resize_br"
    self._drag_ref = (self.panel_rect.x, self.panel_rect.y)   # top-left anchor
    return True
if self._resize_corner_bl.collidepoint(mx, my) and button == 1:
    self._drag_mode = "resize_bl"
    self._drag_ref = (self.panel_rect.right, self.panel_rect.y)  # top-right anchor
    return True
if self._title_bar.collidepoint(mx, my) and button == 1:
    self._drag_mode = "move"
    self._drag_ref = (mx - self.panel_rect.x, my - self.panel_rect.y)  # offset into panel
    return True
```

### `handle_mouse_motion` — three drag modes

Replace existing `_resize_drag` block:

```python
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
```

### `handle_mouse_up`

```python
self._drag_mode = "none"   # was: self._resize_drag = False
```

---

## BUG-MAP-061 — Diagonal map pan

Root cause: `handle_wheel` updates both `wild_modal_map_off_x` and `wild_modal_map_off_y` with the same vertical `y` delta.

Fix in `handle_wheel`, plain-scroll branch:

```python
# Remove the X update; vertical scroll only pans Y
cp = self._cell_px()
total_h = ed.map_h * cp
ed.wild_modal_map_off_y = max(
    0, min(max(0, total_h - self._map_view_rect.h),
           ed.wild_modal_map_off_y - y * cp))
# Horizontal pan via Shift+scroll
mods = pygame.key.get_mods()
if mods & pygame.KMOD_SHIFT:
    total_w = ed.map_w * cp
    ed.wild_modal_map_off_x = max(
        0, min(max(0, total_w - self._map_view_rect.w),
               ed.wild_modal_map_off_x - y * cp))
```

No changes to [`tools/map_editor.py`](tools/map_editor.py) needed (call site unchanged).

---

## BUG-MAP-062 — Species scroll resets to top

Root cause: `_draw_species_column` runs `if species_sel < species_scroll: species_scroll = species_sel` every frame, which resets scroll whenever `species_sel=0` and the user has scrolled down.

Fix — add `_species_vis: int = 1` to `__init__`, then in `_draw_species_column`:

```python
vis = max(1, list_inner.h // lh)
self._species_vis = vis                              # expose for clamp in handle_wheel
max_scroll = max(0, len(names) - vis)
self.species_scroll = max(0, min(self.species_scroll, max_scroll))
# REMOVE: if self.species_sel < self.species_scroll: self.species_scroll = self.species_sel
# KEEP: downward correction (keyboard navigation scrolls list into view)
if self.species_sel >= self.species_scroll + vis:
    self.species_scroll = max(0, self.species_sel - vis + 1)
```

In `handle_wheel`, species branch:

```python
if self.species_inner.collidepoint(mx, my):
    names = self._species_names()
    max_sc = max(0, len(names) - self._species_vis)
    self.species_scroll = max(0, min(max_sc, self.species_scroll - y))
    return True
```

---

## Verification

**Automated:**
```bash
python3 -m ast tools/wild_encounter_modal.py
python3 -m unittest discover -s tests
```

**Manual UI test matrix:**

- Title bar drag: drag the header grip → modal moves, stays clamped inside canvas
- BR resize (existing): drag bottom-right → modal grows right and down; min 640×480
- BL resize (new): drag bottom-left → modal grows left and down; min 640×480
- Min size clamp BL: cannot shrink width below 640 or height below 480
- Panel move + reopen: size/position persists; zoom resets to auto-fit
- Scroll map up: only Y pans (no X drift)
- Scroll map up + Shift: only X pans
- Species list scroll down: list reveals lower items; does not reset to top
- Species list scroll up: list scrolls back to top; stops at 0
- Other input (paint, zoom, tier tabs, text edit): unaffected
- Resize to very large then close and reopen: persists, clamps to canvas


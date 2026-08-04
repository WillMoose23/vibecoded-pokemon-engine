---
name: Wild Modal Zoom+Resize
overview: Add explicit zoom controls (buttons + Ctrl+scroll) to the mini-map in the wild encounter modal, and add a drag-to-resize grip on the modal window's bottom-right corner.
todos:
  - id: tracker-059
    content: Log FEATURE-MAP-059 in docs/tracker.md
    status: completed
  - id: state-init
    content: Add _map_zoom, _panel_override, _resize_drag/anchor/corner, zoom button rects to __init__ and open_modal
    status: completed
  - id: cell-px-zoom
    content: Update _cell_px() to honour explicit _map_zoom
    status: completed
  - id: draw-panel
    content: "Update draw(): resizable panel computation using _panel_override"
    status: completed
  - id: draw-zoom-btns
    content: Add zoom [-][fit][+] buttons and zoom level label in map column header
    status: completed
  - id: draw-resize-grip
    content: Draw resize grip triangle in panel bottom-right corner
    status: completed
  - id: input-zoom-resize
    content: Update handle_mouse_down, handle_mouse_motion, handle_mouse_up, handle_wheel for zoom and resize
    status: completed
  - id: docs-059
    content: Update docs/tools_doc.md with new controls; mark tracker DONE
    status: completed
isProject: false
---

# Wild Modal Zoom + Resize

## Goal / Acceptance Criteria

- `[-] [fit] [+]` zoom buttons appear in the map column header; `fit` resets to auto-fit.
- Ctrl+scroll wheel over the map area zooms in or out.
- The modal has a visible resize grip in the bottom-right corner.
- Dragging the grip changes the modal size; it persists between close/re-open within the session.
- All panels remain visible and not clipped at minimum size (640×480) and at zoom extremes.
- Other input (painting, species scroll, text edit) is unaffected.

---

## Tracker entry

Add to [`docs/tracker.md`](docs/tracker.md) before implementation:
- `FEATURE-MAP-059` — mini-map zoom controls and resizable modal window

---

## New state in `WildEncounterModal.__init__`

```python
self._map_zoom: int | None = None          # None = auto-fit; int = px per cell [4..64]
self._panel_override: pygame.Rect | None = None  # user-resized panel; persists across opens
self._resize_drag: bool = False
self._resize_anchor: tuple[int, int] = (0, 0)   # panel top-left at start of drag
self._resize_corner: pygame.Rect = pygame.Rect(0, 0, 14, 14)
self._zoom_in_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)
self._zoom_out_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)
self._zoom_fit_btn: pygame.Rect = pygame.Rect(0, 0, 1, 1)
```

Reset `_map_zoom = None` on `open_modal` (so modal always opens at auto-fit).
Do NOT reset `_panel_override` on open (size persists within session).

---

## 1. `_cell_px()` — honour explicit zoom

```python
def _cell_px(self) -> int:
    if self._map_zoom is not None:
        return self._map_zoom
    r = self._map_view_rect if self._map_view_rect.w > 1 else self.map_inner
    if self.ed.map_w <= 0 or self.ed.map_h <= 0:
        return 8
    return max(4, min(r.w // self.ed.map_w, r.h // self.ed.map_h))
```

Zoom range: **[4, 64]** px per cell. Zoom step (buttons): **+4 / -4**.

---

## 2. `draw()` — resizable panel + zoom buttons + resize grip

### Panel computation

Replace the fixed panel block:

```python
if self._panel_override is not None:
    panel = self._panel_override.copy()
else:
    cap_w = max(640, canvas.w - 24)
    cap_h = max(480, canvas.h - 24)
    panel_w = min(1100, cap_w)
    panel_h = min(720, cap_h)
    panel = pygame.Rect(0, 0, panel_w, panel_h)
    panel.center = canvas.center
# Clamp to canvas bounds in both branches
panel.x = max(canvas.x + 4, min(panel.x, canvas.right  - panel.w - 4))
panel.y = max(canvas.y + 4, min(panel.y, canvas.bottom - panel.h - 4))
self.panel_rect = panel
```

### Zoom buttons (map column header, after the Patches/Tiles mode buttons)

```python
bx = self.mode_map_btn.right + 10
by = self.map_inner.y + 22
self._zoom_out_btn = pygame.Rect(bx,      by, 22, 22)
self._zoom_fit_btn = pygame.Rect(bx + 24, by, 28, 22)
self._zoom_in_btn  = pygame.Rect(bx + 54, by, 22, 22)
for rect, label in [
    (self._zoom_out_btn, "-"),
    (self._zoom_fit_btn, "fit"),
    (self._zoom_in_btn,  "+"),
]:
    pygame.draw.rect(ed.screen, (40, 70, 55), rect)
    ed.screen.blit(ed.font_small.render(label, True, (220, 240, 230)), (rect.x + 4, rect.y + 4))
```

Show current zoom level as a small label (e.g. `"8px"` or `"auto"`) to the right of the `+` button, truncated if it doesn't fit.

### Resize grip (drawn last, over everything)

```python
self._resize_corner = pygame.Rect(panel.right - 16, panel.bottom - 16, 16, 16)
# Filled triangle pointing toward the corner
pygame.draw.polygon(ed.screen, (90, 160, 120), [
    (panel.right - 2,  panel.bottom - 14),
    (panel.right - 2,  panel.bottom - 2),
    (panel.right - 14, panel.bottom - 2),
])
```

---

## 3. `handle_mouse_down` additions

Add before the mini-map cell check, after existing button checks:

```python
# Resize grip
if self._resize_corner.collidepoint(mx, my) and button == 1:
    self._resize_drag = True
    self._resize_anchor = (self.panel_rect.x, self.panel_rect.y)
    return True

# Zoom buttons
if self._zoom_in_btn.collidepoint(mx, my) and button == 1:
    self._map_zoom = min(64, self._cell_px() + 4)
    return True
if self._zoom_out_btn.collidepoint(mx, my) and button == 1:
    self._map_zoom = max(4, self._cell_px() - 4)
    return True
if self._zoom_fit_btn.collidepoint(mx, my) and button == 1:
    self._map_zoom = None
    return True
```

---

## 4. `handle_mouse_motion` addition

Add before the existing map-drag motion logic:

```python
if self._resize_drag:
    ax, ay = self._resize_anchor
    self._panel_override = pygame.Rect(ax, ay, max(640, mx - ax), max(480, my - ay))
    return True
```

---

## 5. `handle_mouse_up` addition

```python
self._resize_drag = False
```

---

## 6. `handle_wheel` — add Ctrl+scroll zoom branch

Modify the `_map_view_rect.collidepoint` branch:

```python
if self._map_view_rect.collidepoint(mx, my):
    mods = pygame.key.get_mods()
    if mods & pygame.KMOD_CTRL:
        if y > 0:
            self._map_zoom = min(64, self._cell_px() + 4)
        elif y < 0:
            self._map_zoom = max(4, self._cell_px() - 4)
    else:
        # existing pan logic (unchanged)
        cp = self._cell_px()
        ...
    return True
```

---

## Files changed

- [`tools/wild_encounter_modal.py`](tools/wild_encounter_modal.py) — all changes above
- [`docs/tracker.md`](docs/tracker.md) — FEATURE-MAP-059 entry
- [`docs/tools_doc.md`](docs/tools_doc.md) — update wild_encounter_modal.py notes

---

## Verification

**Automated:**
```bash
python3 -m ast tools/wild_encounter_modal.py
python3 -m unittest discover -s tests
make
```

**Manual UI test matrix:**

| Scenario | Pass criteria |
|---|---|
| Open modal (auto-fit) | Map fills map column; zoom label shows "auto" |
| Click `+` zoom button | Cells grow; label updates; pan clamped |
| Click `-` zoom button | Cells shrink; stops at 4 px |
| Click `fit` button | Zoom resets to auto-fit |
| Ctrl+scroll over map | Zoom in/out; plain scroll still pans |
| Plain scroll over map | Pans vertically; no zoom change |
| Drag resize grip | Modal grows; columns reflow; panels not clipped |
| Resize to minimum (640×480) | Cannot shrink smaller; columns still visible |
| Resize to very large | Modal clamps inside canvas; no overflow |
| Close and reopen modal | Panel size persists; zoom resets to auto-fit |
| Other modals after close | Still receive input correctly |
---
name: Modal Full-Screen Canvas
overview: Change the wild encounter modal's canvas from the map viewport sub-rect to the full program window, and ensure the dim overlay and movement clamping follow suit so the panel can occupy the entire screen and auto-fits after windowed/fullscreen toggles.
todos:
  - id: tracker-063
    content: Log FEATURE-MAP-063 in docs/tracker.md
    status: completed
  - id: canvas-fullscreen
    content: Change canvas = ed.map_viewport_rect → ed.screen.get_rect() in draw()
    status: completed
  - id: docs-063
    content: Update docs/tools_doc.md; mark FEATURE-MAP-063 DONE
    status: completed
isProject: false
---

# Modal Full-Screen Canvas

## Root cause

In [`tools/wild_encounter_modal.py`](tools/wild_encounter_modal.py) `draw()`, line:

```python
canvas = ed.map_viewport_rect
```

`map_viewport_rect` is a sub-rect that excludes the left palette panel and bottom tileset strip. Everything — the dim overlay, panel sizing, and movement clamping — is bounded to this sub-region. `ed.screen.get_rect()` always reflects the true current window size and updates automatically after `VIDEORESIZE` (which already calls `relayout()`).

## Tracker entry

Log `FEATURE-MAP-063` — Wild encounter modal canvas extended to full program window.

## Change — one logical site, two lines in `draw()`

### [`tools/wild_encounter_modal.py`](tools/wild_encounter_modal.py)

Replace the canvas assignment and the dim-surface blit:

```python
# Before
canvas = ed.map_viewport_rect
dim = pygame.Surface((canvas.w, canvas.h), pygame.SRCALPHA)
dim.fill((8, 12, 16, 210))
ed.screen.blit(dim, canvas.topleft)

# After
canvas = ed.screen.get_rect()
dim = pygame.Surface((canvas.w, canvas.h), pygame.SRCALPHA)
dim.fill((8, 12, 16, 210))
ed.screen.blit(dim, canvas.topleft)
```

Everything downstream (`panel` sizing, clamping, column layout, grip positions) already references `canvas`, so no further changes are needed.

**Auto-resize behavior:** When `_panel_override` is `None` (no manual resize), the default panel logic centres in the new `canvas` automatically each frame — windowed→fullscreen just recentres the modal. When `_panel_override` is set, the existing clamp lines keep the panel within the new screen bounds.

## Tracker + docs

- Add `FEATURE-MAP-063` to [`docs/tracker.md`](docs/tracker.md) (OPEN → DONE after implementation).
- Update `tools/wild_encounter_modal.py` entry in [`docs/tools_doc.md`](docs/tools_doc.md).

---

## Verification

**Automated:**
```bash
python3 -m ast tools/wild_encounter_modal.py
python3 -m unittest discover -s tests
```

**Manual UI test matrix:**
- Open modal in windowed mode: dim covers full window including palette and tileset strip; panel centred over full window
- Drag modal over the left palette area: moves freely, not blocked at map_viewport_rect edge
- Drag modal over the bottom tileset strip: moves freely
- Resize window while modal is open (drag window edge): panel auto-recentres (or stays clamped if user has moved it)
- Toggle fullscreen (Cmd+Ctrl+F on macOS) with modal open: panel recentres in the new full screen; no overflow
- Close and reopen modal after fullscreen toggle: panel centres correctly
- Other modals / editor panels still receive correct input when wild modal is closed

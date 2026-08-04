---
name: Map editor undo redo
overview: Add undo (Z) and redo (R) to the Pygame map editor, plus rectangular drag in walk mode to paint blocked/walkable over many tiles at once; snapshot/restore for tile layers, walk, and transparency; tracker entries for both features.
todos:
  - id: tracker-undo
    content: Add FEATURE-MAP-009 to docs/tracker.md for undo/redo
    status: pending
  - id: tracker-walk-rect
    content: Add FEATURE-MAP-010 (or next) to docs/tracker.md for walk drag-rectangle
    status: pending
  - id: undo-impl
    content: Implement snapshot/restore, stacks, checkpoints, Z/R in map_editor.py + config.json + footer
    status: pending
  - id: walk-rect-impl
    content: Walk mode drag selection + fill on mouseup + preview rect (mirror paint pattern)
    status: pending
isProject: false
---

# Map editor undo / redo (Z / R)

## Tracker (workspace rule)

Add **two** FEATURE entries to [`docs/tracker.md`](docs/tracker.md) (one issue = one responsibility):

1. **`FEATURE-MAP-009`** — Undo/redo for paint / walk / transparent (keys Z and R), stack limit, clear stacks on new/load/resize map. **STATUS: DONE** after implementation.

2. **`FEATURE-MAP-010`** — Walk mode: drag to select a rectangle and apply blocked (left) or walkable (right) to all cells in the rect on mouseup; optional rubber-band preview while dragging. **STATUS: DONE** after implementation.

---

## State to snapshot

Each checkpoint must **deep-copy** enough data to restore the editable map:

- `tile_layers` (nested lists + cell dicts): `copy.deepcopy`
- `tile_layer_ids` (shallow copy of list)
- `walk`, `trans`: copy rows with `row[:]`
- `active_layer_index` (int)

Omit `connections`, brush, tileset selection, camera pan, etc. for v1 (keeps scope small; matches “map grid” undo).

---

## Stack behavior

- `undo_stack: list[dict]` and `redo_stack: list[dict]` on [`MapEditor`](tools/map_editor.py) (or small dataclass).
- **Before** applying a change: append current snapshot to `undo_stack`, then `redo_stack.clear()`.
- **Undo (Z):** if `undo_stack` empty, no-op (optional status message). Else push current snapshot to `redo_stack`, `pop()` previous from `undo_stack` and `_restore_map_state(...)`.
- **Redo (R):** symmetric with stacks swapped.
- **Cap** stack depth (e.g. **50** or **100**) by dropping oldest `undo_stack` entries when pushing.
- **Clear both stacks** on [`new_map`](tools/map_editor.py), [`try_load_map_by_id`](tools/map_editor.py), and [`resize_map`](tools/map_editor.py) so undo does not cross unrelated maps or dimensions.

---

## When to checkpoint (mutation sites)

| Edit | Location | When to `_undo_checkpoint()` |
|------|----------|------------------------------|
| Paint (stroke) | `MOUSEBUTTONUP` block before `apply_brush_at` / `fill_rect_with_brush` | Once per release that actually runs those calls (only if `map_drag_start` / paint path is active). |
| Walk (rect) | `MOUSEBUTTONUP` before filling the rectangle | Once per release (see **Walk mode: multi-tile selection** below). |
| Transparent | `MOUSEBUTTONDOWN` on map | Immediately **before** `self.trans[cy][cx] = ...` (unchanged: single-cell clicks only unless you later extend the same drag pattern). |

Do **not** checkpoint palette brush selection, layer add/remove, tileset changes, or settings.

---

## Walk mode: multi-tile selection

**Goal:** Match **paint** behavior: left-drag on the map canvas sets an anchor; motion updates the opposite corner; **mouseup** applies to the **axis-aligned bounding box** (inclusive). **Left button** = set all cells in the rect to **blocked** (`walk[y][x] = 1`); **right button** = **walkable** (`0`).

**Implementation** in [`tools/map_editor.py`](tools/map_editor.py):

- Reuse the same drag state used for paint (`map_drag_start`, `map_paint_current`, `map_drag_button`) **only while** `edit_mode == "walk"`, **or** add parallel fields `walk_drag_start` / `walk_drag_current` / `walk_drag_button` if sharing proves awkward (prefer reuse to avoid duplicate reset logic).

- **`MOUSEBUTTONDOWN`** (walk, map canvas): set drag anchor and current cell to `(cx, cy)`, store `walk_drag_button` / `map_drag_button` (1 vs 3), **do not** mutate `walk` yet.

- **`MOUSEMOTION`** (walk, `mouse_down`, canvas): update `map_paint_current` (or walk current) like paint so the rectangle tracks the cursor.

- **`MOUSEBUTTONUP`**: if walk mode and drag was active, `_undo_checkpoint()` once, then for every `(x, y)` in the sorted rect `x0..x1`, `y0..y1`, set `walk[y][x]` from button (1=left blocked, 0=right clear). Clear drag state. If `(x0,y0)==(x1,y1)`, behavior matches today’s single click.

- **Draw loop:** while dragging in walk mode, draw a **preview outline** (reuse the same yellow rectangle style as paint drag in [`draw`](tools/map_editor.py)) so the selection is visible.

- **Quickstart / footer:** one line noting walk supports **click or drag** (left/right same semantics as today).

**Transparent mode:** Out of scope for this iteration unless you want identical drag-fill later (would be a third FEATURE).

---

## Key bindings

- Add `"undo": ["z"]` and `"redo": ["r"]` to [`default_key_config()`](tools/map_editor.py) and [`tools/map_editor_config.json`](tools/map_editor_config.json).
- Extend [`key_name_to_pygame`](tools/map_editor.py) with `z` → `pygame.K_z`, `r` → `pygame.K_r`.
- In the main [`KEYDOWN`](tools/map_editor.py) handler (after overlays: layer delete confirm, tileset delete, rename, **settings**, size prompt):

  - **Settings** already uses `R` for reset defaults—**keep that**; redo must **not** run while `settings_open` (already `continue` before general keys).
  - Handle undo/redo only when **not** in `map_id`, `conn`, or `tileset_rename_index is not None` (so `Z`/`R` are not stolen while typing rename / connection fields). Same guard pattern as other editor shortcuts.

- Use [`event_matches_key`](tools/map_editor.py) with full key lists (like other actions) and add **`key_primary`** strings to the footer line (e.g. `Undo: z · Redo: r`) for discoverability.

---

## Helper methods on `MapEditor`

- `_snapshot_map_state() -> dict` — build the snapshot dict described above.
- `_restore_map_state(state: dict) -> None` — assign fields back (replace list contents / replace references).
- `_undo_checkpoint() -> None` — push snapshot, trim stack, clear redo (call only immediately before a mutating operation).

---

## Files to touch

| File | Change |
|------|--------|
| [`tools/map_editor.py`](tools/map_editor.py) | Stacks, helpers, checkpoint calls, KEYDOWN handlers, footer hint |
| [`tools/map_editor_config.json`](tools/map_editor_config.json) | `undo` / `redo` keys |
| [`docs/tracker.md`](docs/tracker.md) | Two FEATURE log entries (undo/redo + walk rectangle) |

No C++ or schema changes.

---

## Order of work

1. Implement walk drag-rectangle + preview (FEATURE-MAP-010) so undo can treat each walk stroke as one step.
2. Implement undo/redo stacks and wire Z/R (FEATURE-MAP-009), with walk checkpoint on **mouseup** before rect fill (not on mousedown per cell).

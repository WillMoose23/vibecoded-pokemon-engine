---
name: Eraser all edit modes
overview: "Extend `toggle_eraser` and map-edit commit logic so eraser applies to all Tab-cycled modes (paint, walk, transparent, over_player): same key, consistent semantics (clear tiles / clear flags / clear transparency), update in-app help copy, and log a small tracker follow-up plus `docs/tools_doc.md` if behavior is user-visible."
todos:
  - id: key-walk-trans
    content: Widen toggle_eraser KEYDOWN; apply eraser_mode in walk/over_player MOUSEBUTTONUP and transparent MOUSEBUTTONDOWN
    status: completed
  - id: help-docs
    content: Update _help_build_lines (+ optional fl_hint); docs/tools_doc.md + tracker note
    status: completed
  - id: verify-manual
    content: "Manual pass: Tab through modes with E and LMB/RMB as above"
    status: completed
isProject: false
---

# Eraser for all Tab-cycled edit modes

## Review (ordered by severity)

1. **Behavior / UX (medium)** — [`tools/map_editor.py`](tools/map_editor.py): The palette line always shows `mode=… eraser` when `eraser_mode` is true ([~3858–3862](tools/map_editor.py)), but **`toggle_eraser` only runs when `edit_mode == "paint"`** ([~6242–6250](tools/map_editor.py)). So users can leave eraser on in paint, switch to walk with **Tab**, and the UI still says “eraser” while **E** does nothing and walk drags still use LMB=blocked / RMB=clear only ([~5864](tools/map_editor.py)). That is inconsistent and matches your report.

2. **Feature gap (medium)** — **Walk** and **over_player** commit on `MOUSEBUTTONUP` with `val = 1 if self.map_drag_button == 1 else 0` ([~5864](tools/map_editor.py), [~5881](tools/map_editor.py)); **`eraser_mode` is never read** there. **Transparent** only handles `MOUSEBUTTONDOWN` with LMB→1 / RMB→0 ([~5733–5735](tools/map_editor.py)); no eraser branch.

3. **Docs drift (low)** — In-app help still says eraser is “in paint mode” only ([`_help_build_lines` paint / Eraser section ~5020–5027](tools/map_editor.py)). **Walk / Transparent / Over-player** tabs do not mention **E** once eraser is shared.

4. **Tests (low)** — No automated tests for editor mouse paths; verification remains manual (paint / walk / transparent / over_player + **E**).

**Security:** No concerns for this change.

---

## Goal

- **E** (`toggle_eraser`) toggles eraser in **paint, walk, transparent, and over_player** (same set as [`cycle_edit_mode`](tools/map_editor.py) ~4642–4647).
- While eraser is on:
  - **Paint**: unchanged (already uses `erase_paint = … or self.eraser_mode` at [~5806](tools/map_editor.py)).
  - **Walk / over_player**: dragging (either button) writes the **cleared** value (`0` — walkable / not over-player), i.e. treat both LMB and RMB as erase when `eraser_mode` is true.
  - **Transparent**: clicks set **transparency off** (`trans[cy][cx] = 0`) when eraser is on, regardless of button; when eraser is off, keep current LMB=1 / RMB=0.

**Explicitly out of scope:** **F** / `fill_mode` stays **paint-only** (no change to [~6251–6258](tools/map_editor.py)). No change to `map_id` / `conn`.

---

## Implementation (single file unless docs required)

1. **KEYDOWN** — Widen the `toggle_eraser` branch condition from `edit_mode == "paint"` to `edit_mode in ("paint", "walk", "transparent", "over_player")` (same guards: no rename, no repeat). Leave `toggle_fill` paint-only.

2. **MOUSEBUTTONUP — walk** — After computing `ax0`…`ay1`, set `val = 0 if self.eraser_mode else (1 if self.map_drag_button == 1 else 0)` (then existing loop writes `walk`).

3. **MOUSEBUTTONUP — over_player** — Same pattern for `over_player`.

4. **MOUSEBUTTONDOWN — transparent** — Replace the single assignment with: if `self.eraser_mode`: `self.trans[cy][cx] = 0`; else: keep `1 if event.button == 1 else 0`. Still single-cell per click (existing behavior); no drag refactor unless you ask later.

5. **Optional polish** — Only show `fl_hint` when `edit_mode == "paint"` so “fill” is not shown in walk/transparent (tiny UX win; optional).

6. **Help strings** — Update [`_help_build_lines`](tools/map_editor.py): Paint “Eraser” subsection: state **E** works in all four modes and summarize per-mode effect in one short paragraph or split one line into walk/transparent/over_player tabs.

7. **Repo integration** ([`planning-rule`](.cursor/skills/planning-rule/SKILL.md)) — Add a short **tracker** note (e.g. under **FEATURE-MAP-041** or a small **IMPROVEMENT-MAP-*** entry) describing eraser scope expansion; add one line to [`docs/tools_doc.md`](docs/tools_doc.md) **NOTES** for `map_editor.py` if you document editor shortcuts there.

---

## Verification

- Paint: eraser + fill unchanged.
- Walk: **E** on → LMB drag clears blocked cells to walkable; **E** off → LMB blocks, RMB clears.
- Over-player: same as walk for the `over_player` grid.
- Transparent: **E** on → LMB and RMB both clear transparency flag; **E** off → LMB set, RMB clear.
- Footer / help text matches behavior.

---
name: Wild Modal Overhaul
overview: "Fix the mini-map blank bug in the wild encounter modal, then add four new features: typed percentage inputs, global encounters tab, adjacency-based auto patch assignment, and selectable patch icons with flood-fill selection."
todos:
  - id: tracker
    content: Log BUG-MAP-057 and FEATURE-MAP-058 in docs/tracker.md
    status: completed
  - id: fix-minimap
    content: "Fix _draw_mini_map blank bug: use self.map_inner as base rect, fix _cell_px fallback"
    status: completed
  - id: typed-inputs
    content: Add _edit_field/_edit_buf state; replace +/- for stepChancePercent and weight with typed text inputs
    status: completed
  - id: global-tab
    content: "Add Global tab to modal: wild_global_encounters state in MapEditor, save/load, Global tab UI"
    status: completed
  - id: cpp-global
    content: "C++: add globalCommon/Uncommon/Rare to MapData, parse wildGlobalEncounters, merge in rollWildEncounterSpecies"
    status: completed
  - id: adjacency-paint
    content: "Refactor paint_cells: adjacency auto-assign (join neighbor or create new patch)"
    status: completed
  - id: flood-select
    content: Add flood-fill patch selection on mini-map click; render patch index digit in cell; _selected_cells highlight
    status: completed
  - id: docs-update
    content: Update source_doc.md, tools_doc.md, and tracker status to DONE after implementation
    status: completed
isProject: false
---

# Wild Encounter Modal Overhaul

## Goal / Acceptance Criteria

- Mini-map renders tiles correctly on first open.
- `stepChancePercent` and species `weight` are editable by typing.
- A **Global** tab lets you define species that appear across all patches; engine merges them with local (local wins per species).
- Painting a tile auto-joins an adjacent patch or creates a new one; non-adjacent merge still via Merge button.
- Clicking a patch tile on the mini-map flood-fills and highlights its connected component.
- All fields validate and clamp; no clipped UI elements at 800×600 or typical size.

---

## Tracker entries (log before work)

Add to [`docs/tracker.md`](docs/tracker.md):

- `BUG-MAP-057` — mini-map blank: `_map_view_rect` stale on first draw
- `FEATURE-MAP-058` — typed inputs, global tab, adjacency paint, selectable patch icons

---

## 1. Fix mini-map blank (BUG-MAP-057)

**Root cause**: `_draw_mini_map` opens with `r = self._map_view_rect` (initially `Rect(0,0,1,1)`). `_cell_px()` also reads the same stale rect. `map_rect` gets negative dimensions and the function early-returns forever.

**Fix** in [`tools/wild_encounter_modal.py`](tools/wild_encounter_modal.py):

```python
# _draw_mini_map — use self.map_inner (set in draw() before this call)
def _draw_mini_map(self) -> None:
    base = self.map_inner          # always valid after draw() layouts columns
    map_rect = pygame.Rect(base.x + 4, base.y + 48, base.w - 8, base.h - 52)
    if map_rect.w < 8 or map_rect.h < 8:
        return
    self._map_view_rect = map_rect  # stored for hit-testing
    ...

# _cell_px — use self.map_inner as fallback when _map_view_rect not yet set
def _cell_px(self) -> int:
    r = self._map_view_rect if self._map_view_rect.w > 1 else self.map_inner
    ...
```

---

## 2. Typed percentage inputs (FEATURE-MAP-058)

Add text-edit state to `WildEncounterModal.__init__`:

```python
self._edit_field: str | None = None   # "step" | "weight_N"
self._edit_buf:   str = ""
```

- **`stepChancePercent`**: replace the `- / +` row with a small framed text box. Clicking focuses it; typing appends digits; Enter/click-away commits (clamp to [0,100]).
- **species `weight`**: each encounter row shows a small inline numeric box (same focus/commit model, clamp to [1,999]).
- `handle_keydown`: when `_edit_field` is set, route printable digits and Backspace to `_edit_buf`; Enter commits. Escape cancels.
- `handle_mouse_down`: clicking outside any edit rect commits the current buffer.
- Helper `_commit_edit()` validates and writes back into the patch/row dict.

---

## 3. Global encounters tab (FEATURE-MAP-058)

### Data model

**Python** — add to [`tools/map_editor.py`](tools/map_editor.py):

```python
self.wild_global_encounters: dict = {"common": [], "uncommon": [], "rare": []}
```

Include in map save/load under key `"wildGlobalEncounters"`.

**C++**:

- [`include/map_data.h`](include/map_data.h) — add to `MapData`:

```cpp
std::vector<WildEncounterSpeciesEntry> globalCommon;
std::vector<WildEncounterSpeciesEntry> globalUncommon;
std::vector<WildEncounterSpeciesEntry> globalRare;
```

- [`src/map_data.cpp`](src/map_data.cpp) — after `parseWildPatches`, parse optional `"wildGlobalEncounters"` the same way as per-patch encounters.

- [`src/wild_encounter.cpp`](src/wild_encounter.cpp) — update `rollWildEncounterSpecies` signature to accept `const MapData& mapData` and pass it from the call site. Before calling `pickWeightedSpecies`, merge global tier entries whose `species` is **not** already present in the patch tier → merged list used for rolling (local wins per species).

### UI

Add a tab bar in the modal (above the patch column):

```
[ Local Patches ] [ Global ]
```

- **Local tab** (default): current patch list + step % + tier rows UI.
- **Global tab**: replaces patch list with global species editor for each tier (common/uncommon/rare). Same `+row` / `-row` controls. No `stepChancePercent` (global rate is per-patch; only species are global). Show a small `⚠` indicator next to any global species that is also listed in the currently selected local patch.
- Tab state: `self.modal_tab: str = "local"` (`"local"` | `"global"`).

---

## 4. Adjacency auto-assign painting (FEATURE-MAP-058)

Refactor `paint_cells` in `wild_encounter_modal.py`:

```python
def _neighbor_patch_index(self, x: int, y: int) -> int | None:
    """Return the patch index (1-based) of the first non-zero 4-neighbor, or None."""
    for dx, dy in ((0,-1),(-1,0),(1,0),(0,1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < self.ed.map_w and 0 <= ny < self.ed.map_h:
            v = self.ed.wild_encounter[ny][nx]
            if v > 0:
                return v
    return None
```

- Erase (right-click): set cell to 0 as before.
- Paint: for each cell in the drag rect, call `_neighbor_patch_index`. If found, use that index; otherwise call `_create_new_patch_for_cell()` which appends a new default patch to `ed.wild_patches` and returns its 1-based index.
- Process cells left→right, top→bottom within the drag rect so that earlier cells in the stroke can serve as neighbors for later ones in the same stroke.
- Do not auto-merge when two different patches become adjacent; the existing Merge button handles non-adjacent and non-adjacent merges.

---

## 5. Selectable patch icons and flood-fill selection (FEATURE-MAP-058)

Add to `WildEncounterModal`:

```python
self._selected_cells: set[tuple[int, int]] = set()
```

**Mini-map rendering**: for each patch tile, if `cell_px >= 8`, draw the 1-based index digit centered. Active/selected patch cells use a brighter overlay color; `_selected_cells` cells get a distinct outline.

**Click on mini-map (patch mode)**:
1. Determine the clicked tile.
2. If the tile has a non-zero patch index, BFS/flood-fill to collect all contiguous cells with the same index → store in `_selected_cells`.
3. Set `ed.selected_wild_patch_index = patch_index - 1` and `ed.active_wild_patch_index = patch_index - 1`.
4. If the tile is empty, clear `_selected_cells`.

---

## Files changed

- [`tools/wild_encounter_modal.py`](tools/wild_encounter_modal.py) — BUG fix, typed inputs, global tab UI, adjacency paint, flood-fill selection
- [`tools/map_editor.py`](tools/map_editor.py) — `wild_global_encounters` state, save/load, pass to modal
- [`include/map_data.h`](include/map_data.h) — global tier fields on `MapData`
- [`src/map_data.cpp`](src/map_data.cpp) — parse `wildGlobalEncounters`
- [`src/wild_encounter.cpp`](src/wild_encounter.cpp) — merge global into patch at roll time
- [`docs/tracker.md`](docs/tracker.md) — BUG-MAP-057, FEATURE-MAP-058
- [`docs/source_doc.md`](docs/source_doc.md) — document new MapData fields and wild_encounter merge
- [`docs/tools_doc.md`](docs/tools_doc.md) — document modal changes

---

## Verification

**Automated:**
```bash
make                                    # C++ builds clean
python3 -m ast tools/wild_encounter_modal.py
python3 -m ast tools/map_editor.py
python3 -m unittest discover -s tests
python3 tools/validate_map_events.py src/maps/route_2.json
```

**Manual UI test matrix:**

| Scenario | Pass criteria |
|---|---|
| Open modal at 800×600 | Map renders tiles; no blank area; all 3 columns visible, not clipped |
| Open modal at 1440×900 | Same as above |
| Resize window mid-modal | Map and column layout reflows; patch list not clipped |
| Click tile in mini-map | Contiguous patch region highlighted; patch column updates |
| Paint new region (no adjacent patch) | New patch row appears in patch list |
| Paint adjacent to existing patch | Tile joins existing patch; no new patch created |
| Merge button (non-adjacent patches) | Two patches merge into one; grid indices updated |
| Type into step% box | Value commits on Enter, clamped to [0,100] |
| Type into weight box | Value commits on click-away, clamped to [1,999] |
| Global tab → add species | Shows in global list; `⚠` if also in local patch |
| Engine (runtime) | Global species appear alongside local; local wins for duplicates |
| Other modals (events, NPC) | Still receive input correctly after wild modal is closed |
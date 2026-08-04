---
name: Remove layer UI
overview: Tile layers can already be removed with the bound `layer_remove` key (default **End**) and the existing Y/N overlay. This plan adds a **Settings** button to remove the **current** tile layer using that same flow, plus tracker logging—so the capability is obvious without memorizing shortcuts.
todos:
  - id: log-feature-019
    content: Add FEATURE-MAP-019 to docs/tracker.md (remove current tile layer from Settings)
    status: completed
  - id: settings-ui-rect
    content: Draw Remove current tile layer button + rect; adjust settings box height/spacing in map_editor.py
    status: completed
  - id: settings-click
    content: "Handle MOUSEBUTTONDOWN on new rect: confirm idx + close settings if len(tile_layers) > 1"
    status: completed
  - id: readme-optional
    content: "Optional: one sentence in src/maps/README.md about Settings remove layer"
    status: completed
isProject: false
---

# Remove tile layer (UI affordance)

## Current behavior (no duplicate logic)

- [`_remove_tile_layer_at`](tools/map_editor.py) deletes a layer by index; refuses when only one layer remains.
- [`layer_remove` / `layer_remove_confirm_idx`](tools/map_editor.py): **End** (configurable) sets confirm on the **active** layer; [`_draw_layer_remove_confirm_overlay`](tools/map_editor.py) + KEYDOWN Y/N handles completion.
- Settings ([`_draw_settings_overlay`](tools/map_editor.py)) only has **Add event layer** / **Remove event layer**—not generic tile-layer removal.

## What to add

1. **Tracker** — Add one `FEATURE` entry (e.g. **FEATURE-MAP-019**) in [docs/tracker.md](docs/tracker.md) per [.cursor/rules/Logging-Rule.mdc](.cursor/rules/Logging-Rule.mdc) before code changes: success criteria = user can remove the active tile layer from Settings with confirmation; cannot remove the last layer; reuses existing confirm overlay and `_remove_tile_layer_at`.

2. **Settings UI** — In [`_draw_settings_overlay`](tools/map_editor.py), below the event-layer row:
   - Add a new `pygame.Rect` (e.g. `settings_remove_current_layer_rect`) spanning the panel width (or two-column width matching existing buttons).
   - Label such as **Remove current tile layer…** with small hint text including the active layer id and the existing shortcut (`key_primary('layer_remove')`).
   - **Disable** visually (grey) when `len(self.tile_layers) <= 1`, matching the status message used for the key path.

3. **Input** — In `MOUSEBUTTONDOWN` where settings clicks are handled (~3088–3095), if the new rect is hit with button 1: if more than one layer, set `self.layer_remove_confirm_idx = self.active_layer_index` and **`self.settings_open = False`** so the confirm overlay is unobstructed (same pattern as other modals).

4. **Layout** — Slightly increase the settings `box` height (currently `400`) so the new row plus key list still fits, or tighten vertical spacing so nothing clips.

5. **Docs (optional)** — One line in [src/maps/README.md](src/maps/README.md) editor section: tile layers can be removed with **End** (or rebound key) **or** Settings → remove current tile layer—only if you want README parity; footer already mentions `layer_remove`.

## Out of scope

- Removing walkability/transparency as “layers” (they are global grids, not `tileLayers` entries).
- Changing save format or C++ loader (unchanged).

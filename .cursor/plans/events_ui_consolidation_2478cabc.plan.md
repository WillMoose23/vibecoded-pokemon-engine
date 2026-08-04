---
name: Events UI Consolidation
overview: Consolidate the E toolbar into a launcher modal that spawns Event Engine and Wild Encounters sub-modals; add Help/Back navigation; absorb Settings into the Help overlay with an interactive TOC; rename toolbar labels; enforce a new UI Standard cursor rule.
todos:
  - id: tracker-064-067
    content: Log FEATURE-MAP-064 through 067 in docs/tracker.md
    status: completed
  - id: ui-rule
    content: Create .cursor/rules/UI-Standard-Rule.mdc
    status: completed
  - id: toolbar-labels
    content: "Rename E→Event, #→Overworld; adjust btn_w; * opens help overlay"
    status: completed
  - id: launcher-modal
    content: Create tools/events_launcher_modal.py (EventsLauncherModal)
    status: completed
  - id: launcher-wiring
    content: Wire EventsLauncherModal into map_editor.py; replace popover; route input
    status: completed
  - id: event-engine-modal
    content: Create tools/event_engine_modal.py (EventEngineModal) with Back/Help buttons and delegated columns
    status: completed
  - id: event-engine-wiring
    content: Wire EventEngineModal into map_editor.py; adapt _draw_events_list_panel and _draw_event_script_editor to accept target_rect
    status: completed
  - id: wild-back-help
    content: Add Back and Help buttons to WildEncounterModal
    status: completed
  - id: help-settings
    content: Migrate settings controls to help overlay settings tab; remove _draw_settings_overlay; update * and Esc flows
    status: completed
  - id: help-toc-autoscroll
    content: Add interactive TOC to help home tab; add _open_help_overlay(tab, scroll_to) API
    status: completed
  - id: docs-064-067
    content: Update docs/tools_doc.md with new files; mark tracker entries DONE
    status: completed
isProject: false
---

# Events UI Consolidation

## Scope overview

```
E button
  └─ EventsLauncherModal           ← new file: tools/events_launcher_modal.py
       ├─ [Event Engine] button  → EventEngineModal  ← new file: tools/event_engine_modal.py
       ├─ [Wild Encounters] button → existing WildEncounterModal (add Back + Help)
       └─ [Help] button          → opens existing help overlay (home tab)

H key  →  help overlay (unchanged shortcut)
*       →  help overlay (shortcut, same as H — settings relocated)
```

---

## Tracker entries (log before implementation)

- `FEATURE-MAP-064` — Events Launcher Modal
- `FEATURE-MAP-065` — Event Engine Modal (NPC workspace + script editor in wild-encounter standard shell)
- `FEATURE-MAP-066` — Help overlay: settings section, interactive TOC, auto-section navigation
- `FEATURE-MAP-067` — UI Standard cursor rule

---

## 1. New Cursor rule — UI Standard

File: [`.cursor/rules/UI-Standard-Rule.mdc`](.cursor/rules/UI-Standard-Rule.mdc)

Every new or reworked editor modal MUST follow the `WildEncounterModal` standard:
- Full-screen canvas via `ed.screen.get_rect()`, semi-transparent dim over full window.
- `_panel_override` (persisted within session), default auto-centred sizing.
- `_drag_mode` ("none" | "resize_br" | "resize_bl" | "move"), `_drag_ref`.
- Title bar with drag-grip dots + close button + Help button.
- Bottom-right AND bottom-left resize grip triangles.
- Minimum panel size 640×480; size clamp before position clamp.
- Separate class file in `tools/`; `ed` reference passed at construction.
- Input routed from `map_editor.py` via `handle_mouse_down/up/motion/wheel/keydown`.

---

## 2. Toolbar label changes — [`tools/map_editor.py`](tools/map_editor.py)

Change the render text for the two relabelled buttons (search `"E"` / `"#"` render near `events_btn_rect` / `world_btn_rect`):

```python
# Before
ed.font_small.render("E", ...)
ed.font_small.render("#", ...)

# After
ed.font_small.render("Event", ...)    # events_btn_rect  — widen btn_w to fit
ed.font_small.render("Overworld", ...)  # world_btn_rect
```

Adjust `btn_w` in `relayout()` to accommodate longer labels (measure string width via `font_small.size()`).

The `*` button click now calls `_open_help_overlay()` instead of toggling `settings_open` (settings moves to help overlay — see §5).

---

## 3. `EventsLauncherModal` — [`tools/events_launcher_modal.py`](tools/events_launcher_modal.py)

New standalone class following the UI Standard rule exactly.

### Panel layout

Compact centred panel (~480×320 default). Three large buttons stacked vertically in the body:

```
┌──────────────────────────────────────────────────┐
│ · · · · ·  Events  · · · · ·           [Close]   │  ← draggable title bar
├──────────────────────────────────────────────────┤
│                                                  │
│              [ Event Engine ]                    │
│                                                  │
│              [ Wild Encounters ]                 │
│                                                  │
│              [ Help ]                            │
│                                                  │
└──────────────────────────────────────────────────┘
```

### State

Same fields as the UI Standard: `_panel_override`, `_drag_mode`, `_drag_ref`, `_resize_corner_br/bl`, `_title_bar`, `open`, `panel_rect`.

### Button actions

- **Event Engine** → `self.close_modal(); ed.event_engine_modal.open_modal()`
- **Wild Encounters** → `self.close_modal(); ed.wild_encounter_modal.open_modal()`
- **Help** → `ed._open_help_overlay(); ed.help_tab = "home"`

### Wiring in [`tools/map_editor.py`](tools/map_editor.py)

- Instantiate: `self.events_launcher_modal = EventsLauncherModal(self)`
- E button click: replace popover toggle with `events_launcher_modal.open_modal()` (remove `_draw_events_tool_popover`)
- Route all input events identically to `wild_encounter_modal`

---

## 4. `EventEngineModal` — [`tools/event_engine_modal.py`](tools/event_engine_modal.py)

New class. Follows UI Standard. Delegates inner content to existing `map_editor.py` draw methods by passing explicit rect parameters (no internal logic duplication).

### Panel layout — three columns

```
┌─────────────────────────────────────────────────────────────────┐
│ · · ·  Event Engine  · · ·     [Help]  [← Back]   [Close]      │
├──────────┬───────────────────┬──────────────────────────────────┤
│  Events  │       Map         │         Script Editor            │
│  list    │   (mini-map with  │  (steps list + opcode palette)   │
│  panel   │    event hulls)   │                                  │
└──────────┴───────────────────┴──────────────────────────────────┘
```

### Delegation strategy

`EventEngineModal.draw()` computes `event_list_col`, `map_col`, `script_col` rects within its panel body, then calls:

```python
ed._draw_events_list_panel_in_col(event_list_col)   # adapted version
ed._draw_event_mini_map(map_col)                    # new method (event hulls on mini-map)
ed._draw_event_script_editor_in_col(script_col)     # adapted version
```

The existing `_draw_events_list_panel()` and `_draw_event_script_editor_modal()` will be refactored to accept an explicit `target_rect` parameter instead of computing position from `map_canvas_rect`.

### Back and Help buttons

- **Back** → `self.close_modal(); ed.events_launcher_modal.open_modal()`
- **Help** → `ed._open_help_overlay(); ed.help_tab = "script_ops"`

### Input routing

Exactly mirrors `wild_encounter_modal` routing in `map_editor.py`. While `event_engine_modal.open` is True, block map editor input, route to `event_engine_modal.handle_*`.

### State migration

`event_script_editor_open` flag: when `EventEngineModal` is open, the inner script editor content is always visible (no separate "open" toggle); the flag is preserved for backward-compat but the modal `open` flag is the primary gate.

---

## 5. Wild Encounters modal — [`tools/wild_encounter_modal.py`](tools/wild_encounter_modal.py)

Two additions to `draw()` and `handle_mouse_down()`:

```python
# In draw() title bar area — right of close button:
self._help_btn  = pygame.Rect(panel.right - 136, panel.y + 6, 56, 26)  # "Help"
self._back_btn  = pygame.Rect(panel.right - 200, panel.y + 6, 56, 26)  # "← Back"
```

Mouse-down handlers:
```python
if self._help_btn.collidepoint(mx, my) and button == 1:
    ed._open_help_overlay(); ed.help_tab = "events"
    return True
if self._back_btn.collidepoint(mx, my) and button == 1:
    self.close_modal(); ed.events_launcher_modal.open_modal()
    return True
```

---

## 6. Help overlay — [`tools/map_editor.py`](tools/map_editor.py)

### a) Settings section inside help overlay

Add a `"settings"` tab to `HELP_GUIDE_TABS`:

```python
HELP_GUIDE_TABS = (
    ...existing tabs...
    ("settings", "Settings"),
)
```

Move all settings controls (add/remove layer, event defaults, etc.) out of `_draw_settings_overlay()` and into `_help_build_lines("settings", ...)` and a new `_draw_help_settings_section()` interactive method.

Remove `settings_open` flag and `_draw_settings_overlay()`. The `*` button and Esc-from-settings flows now open the help overlay on the settings tab.

### b) Interactive Table of Contents

In `_help_build_lines("home", ...)`, render one clickable row per tab. Store `help_toc_hit_rects: list[tuple[str, pygame.Rect]]`. On click: `self.help_tab = tid; self.help_scroll_y = 0`.

### c) Auto-section navigation API

```python
def _open_help_overlay(self, tab: str = "home", scroll_to: str | None = None) -> None:
    self.help_overlay_open = True
    self.help_tab = tab
    self.help_scroll_y = 0
    if scroll_to:
        self._help_pending_scroll_to = scroll_to   # resolved in _draw_help_overlay on first render
```

Callers pass `tab="script_ops"` from Event Engine Help button, `tab="events"` from Wild Encounters Help button, `tab="settings"` from * button.

---

## Files changed

- [`.cursor/rules/UI-Standard-Rule.mdc`](.cursor/rules/UI-Standard-Rule.mdc) — new cursor rule
- [`tools/events_launcher_modal.py`](tools/events_launcher_modal.py) — new
- [`tools/event_engine_modal.py`](tools/event_engine_modal.py) — new
- [`tools/wild_encounter_modal.py`](tools/wild_encounter_modal.py) — Back + Help buttons
- [`tools/map_editor.py`](tools/map_editor.py) — toolbar labels, wiring, help overlay updates, settings migration
- [`docs/tracker.md`](docs/tracker.md) — four new tracker entries
- [`docs/tools_doc.md`](docs/tools_doc.md) — new tool entries

---

## Verification

**Automated:**
```bash
python3 -m ast tools/events_launcher_modal.py
python3 -m ast tools/event_engine_modal.py
python3 -m ast tools/wild_encounter_modal.py
python3 -m ast tools/map_editor.py
python3 -m unittest discover -s tests
```

**Manual UI test matrix:**
- E button opens Events Launcher modal; dim covers full screen
- Launcher: all 3 buttons work; Close closes the launcher
- Launcher → Event Engine: Event Engine modal opens; Back returns to launcher
- Launcher → Wild Encounters: Wild Encounters modal opens; Back returns to launcher; Help opens docs on events tab
- H key still opens help overlay directly (any context)
- * button opens help overlay on Settings tab; settings controls are functional
- Settings tab: add/remove layer still works from within the help overlay
- Help TOC on home tab: clicking each entry navigates to that tab
- Event Engine: events list, mini-map, script editor all visible and functional; resize/drag/zoom work
- Minimum 640×480 enforced on all three modals; no content clipping at minimum size
- Windowed ↔ fullscreen toggle: all modals clamp/recentre correctly
- Other input (tile paint, overworld) unaffected when no modal is open

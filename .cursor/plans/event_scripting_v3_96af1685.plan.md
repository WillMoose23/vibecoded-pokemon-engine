---
name: Event scripting v3
overview: Snapshot the map editor as “version 3”, extend map/event data and the pygame editor with a dedicated Events workflow synced to the existing `event` tile layer, define JSON script format and asset references, then add a C++ script engine and action registry integrated with the game loop—delivered in vertical slices because the action catalog exceeds current engine subsystems (no inventory/flags/dialogue stack yet).
todos:
  - id: tracker-docs
    content: Add FEATURE entry to docs/tracker.md; plan updates to docs/tools_doc.md, docs/source_doc.md, and optional docs/event_script_ops.md (opcode registry).
    status: completed
  - id: backup-v3
    content: Create tools/backup_map_editor_v3/ snapshot + README; bump MAP_EDITOR_TOOL_VERSION to 3.0 in map_editor.py.
    status: completed
  - id: schema-map-json
    content: "Define map JSON v4 fields: events[] (2x2 anchor, script ref, sprite ref, interaction). Extend validate_maps or add validate_map_events.py."
    status: completed
  - id: editor-events-mode
    content: "Implement Events workspace UI in map_editor.py: list, 2x2 placement, script link/edit, sprite picker from three Graphics roots; extend session cache bundle."
    status: completed
  - id: cpp-map-load
    content: Extend MapData + map_data.cpp to parse events; resolve script paths; document layout in source_doc.md.
    status: completed
  - id: cpp-script-engine
    content: Add ScriptEngine + action registry + overworld Q hook (battle mode excluded); implement MVP ops then stubs for remainder.
    status: completed
  - id: qa-pass
    content: "RAM/perf pass: directory scan caching, cache snapshot size, single active script; add minimal repro map + manual test checklist."
    status: completed
isProject: false
---

# Event scripting and map editor v3

## Context from the repo

- Map editor today ([`tools/map_editor.py`](tools/map_editor.py)): `MAP_EDITOR_TOOL_VERSION` is `"1.0"`; “event layer” is **FEATURE-MAP-007**—a normal **tile layer** whose id is `event` (paint tiles like any other layer). There is **no** event object model, script asset, or 2×2 placement semantics yet.
- Map runtime ([`include/map_data.h`](include/map_data.h), [`src/map_data.cpp`](src/map_data.cpp)): loads `version`, geometry, `layers.tileLayers`, walkability/transparent, `connections`. **No `events` or script fields.**
- SDL game: has battle flow, map viewer (`map_view.cpp`), `displayTextLines_` for simple text—not a Pokémon-style message box, flag store, inventory, or overworld “interact” loop. **`SDLK_q` is already used in battle** for move slot 0 ([`src/game.cpp`](src/game.cpp) ~933–947); overworld event binding to **Q** must be **mode-gated** (battle vs field) or battle keys must be remapped.

**Implication:** “Editor + broad runtime” is a **multi-phase program**: the plan defines the **full JSON schema and action opcode registry up front**, then implements handlers incrementally behind a stable interpreter API so the editor does not churn.

---

## 1) Backup “tool editor as version 3”

- Create a dated snapshot directory consistent with existing patterns, e.g. [`tools/backup_2026-04-12/`](tools/backup_2026-04-12/) style: **`tools/backup_map_editor_v3/`** (or `tools/backup_<date>_map_editor_v3/`) containing at least:
  - `map_editor.py` (copy of current pre-feature baseline **before** large edits, or copy at time of branch—document which in a one-line `README.txt` in that folder).
  - [`tools/map_editor_config.json`](tools/map_editor_config.json) copy if keybindings change for the new Events mode.
- Bump the **live** editor version string **`MAP_EDITOR_TOOL_VERSION` to `"3.0"`** (or `"3.0.0"`) in [`tools/map_editor.py`](tools/map_editor.py) and window title so “v3” is unambiguous.

**Tracker / docs (planning-rule):** Add a **FEATURE** entry in [`docs/tracker.md`](docs/tracker.md) *before* substantive work; reference that ID in PR/commit notes. Update [`docs/tools_doc.md`](docs/tools_doc.md) for backup path, version bump, new Events UI, and new outputs. If C++ map loading changes, update [`docs/source_doc.md`](docs/source_doc.md) per repo rules.

---

## 2) Data model: maps, 2×2 events, scripts, sprites

### 2.1 Map JSON (`src/maps/<map>.json`)

Extend top-level map JSON (bump map `version` field as needed, e.g. **4**, with migration notes) with an **`events`** array. Each **event instance**:

- **`id`**: stable string (unique within the map; used for script file name or `scriptId`).
- **`anchor`**: `{ "x": int, "y": int }` — **top-left tile** of a **fixed 2×2** footprint (enforce in editor: clamp to `0..width-2`, `0..height-2`).
- **`script`**: either **inline JSON object** (small scripts) or **`{ "path": "relative/path.json" }`** (preferred for non-trivial scripts per your requirement).
- **`sprite`** (optional): structured reference, e.g. `{ "kind": "character"|"pokemon_icon"|"pokemon_icon_shiny", "file": "foo.png" }` where resolution rules map to:
  - `src/Graphics/Characters/`
  - `src/Graphics/Pokemon/Icons/`
  - `src/Graphics/Pokemon/Icons shiny/`  
  Store **file name or stem only** plus `kind`; resolve paths in editor preview and in game loader—**never** embed absolute `/Users/...` paths in committed JSON.
- **Interaction**: e.g. `{ "key": "talk", "bind": "Q" }` (logical bind; actual SDL key comes from config).
- **Flags** (optional): `oneShotFlag`, `requiresFlag`, etc. (align with script `check_flag` / `set_flag`).

### 2.2 Script JSON (per event)

Single document per script file, e.g.:

```json
{
  "version": 1,
  "actions": [
    { "op": "lock_player", "args": {} },
    { "op": "show_message", "args": { "text": "Hello!" } }
  ]
}
```

- **Execution model:** ordered list for v1; **`branch` / `call` / `parallel`** expressed as structured ops (not free-form text like the mini-example) so the C++ interpreter stays validateable.
- **Catalog:** maintain a **single source of truth** list: `docs/event_script_ops.md` (or a JSON schema file under `docs/` / `tools/`) mapping each `op` → args schema, implementation status (**implemented | stub**), and engine dependency (e.g. “needs inventory subsystem”).

### 2.3 Sync with the `event` tile layer

**Recommended approach (clear UX, minimal ambiguity):**

- Keep the **`event` tile layer** as the **visual/marking layer** (optional patterns).
- Add an **Events authoring mode** (see §3): placing or selecting a 2×2 **hull** writes/updates **`events[]`**; optionally **auto-stamp** four cells on the `event` layer with a reserved “event marker” tile **or** draw a 2×2 overlay in the editor only (less map churn).  
- On save, **validate**: 2×2 regions **do not overlap** (or define merge rules); event anchors in bounds.

**Session cache:** extend [`MapEditor._snapshot_session_map_bundle`](tools/map_editor.py) (and restore) to include `events` (and any new top-level map fields) so the existing v2 session-switch behavior does not drop event data.

---

## 3) Editor UI: “new tab” in pygame

Pygame has no native tabs; mirror existing patterns:

- **World workspace** uses `#` to toggle a mode over the canvas ([`tools/map_editor.py`](tools/map_editor.py)).
- Add **`Events` workspace** (e.g. toggle with **`E`** or a toolbar button next to `#` / `*`), with:
  - List of events for the current map; **Add / Delete / Select**.
  - Canvas: **2×2 ghost rect** at anchor; drag to move (with undo checkpoint).
  - **Script panel**: open/edit linked JSON (structured form + “open as JSON” text); validate unknown `op` against registry.
  - **Sprite picker**: scan the three Graphics folders (read-only), filter by extension, store relative `kind` + `file`.
- **Gear / settings** remain separate; Events mode should **require** an `event` tile layer or **auto-prompt** to add it when entering Events mode (aligns with “sync with event layer”).

---

## 4) C++ runtime: architecture for “broad” action support

### 4.1 Loading

- Extend **`MapData`** ([`include/map_data.h`](include/map_data.h)) with `std::vector<MapEventInstance>` (or similar) populated in [`loadMapFromFile`](src/map_data.cpp).
- Resolve `script.path` relative to repo layout (e.g. `src/maps/scripts/...` or next to map)—**document the canonical root** in `source_doc.md`.

### 4.2 Interpreter

- **`ScriptEngine`** (new files under `src/` / `include/`): loads script JSON, maintains **instruction pointer**, **call stack**, **wait** state (frames, movement completion, async sound—initially stubs).
- **`ScriptActionHandler` registry**: `std::function` or virtual interface keyed by `op` string; returns **Continue | Yield | Error**.
- **Game integration hook**: overworld/update loop checks **player near event 2×2**, **Q pressed**, **not in battle/menu**; starts or queues script. **Battle** keeps current **Q = move 0** behavior.

### 4.3 Honest phasing for “most actions”

Many listed actions assume **subsystems that do not exist** (inventory, party bag, NPC entities on map, camera scripting, audio bus, HM obstacles). The plan satisfies “broad runtime” by:

1. Implementing **core infrastructure** (load, run loop, yields, flags/vars store, simple message UI, warp to map/tile).
2. Implementing **high-value actions** that map to existing code (e.g. `start_wild_battle` using current `Battle` path).
3. Registering **stubs** for the rest that log + show debug text until their subsystem exists—**without** changing the JSON opcode names (schema-stable).

**Concrete suggested MVP order inside runtime** (first vertical slice to ship):

- `lock_player` / `unlock_player`, `wait_frames`, `show_message` / `close_message`
- `set_flag` / `clear_flag` / `check_flag` (in-memory map per save slot—persist later)
- `warp_player` (map id + tile), `set_player_facing`
- `branch` / `end_script`

Then expand into battle, inventory, NPC movement, audio, camera.

---

## 5) QA / RAM / performance (qa-ram-performance)

| Area | Risk | Mitigation |
|------|------|------------|
| **Memory** | `events` + large `actions` arrays copied in editor session cache | Snapshot **shallow** where possible; store script by reference on disk; in cache, consider storing script path + hash, not full duplicate, **or** cap cached maps (optional LRU) if memory becomes an issue. |
| **CPU** | Scanning large Graphics folders every frame | Cache directory listings at editor startup or on panel open. |
| **Growth** | Unbounded `flags` / `vars` maps in C++ | Serialize caps in debug builds; document expected sizes. |
| **Concurrency** | “Parallel script execution” | Defer to late phase; v1 **single active overworld script** + queue. |

**Validation:** add a small **`tools/validate_map_events.py`** (optional) to check anchors, non-overlap, script file exists, and `op` in allowlist—run in CI or pre-commit if the repo already validates maps.

---

## 6) Bug-checking / process

- **Log first:** FEATURE in [`docs/tracker.md`](docs/tracker.md) with acceptance criteria per phase.
- **Reproduce-driven:** For runtime, add a **minimal test map** with one 2×2 event and a 3-action script committed under `src/maps/` (or test-only path).
- After each phase: **expected vs actual** in tracker; root cause for any bug before fix.

---

## 7) Acceptance criteria (definition of done)

**Phase A — Editor + data (v3)**

- Backup folder exists; live editor shows **v3.0**.
- Map save/load preserves **`events`** and script references; session map switch retains events.
- Events UI can create a 2×2 event, attach sprite ref, link script JSON, and export valid map JSON.

**Phase B — Runtime slice**

- Game loads map with events; **overworld Q** triggers script; **battle Q** unchanged.
- Implemented ops run deterministically; unknown ops fail gracefully (visible error / log).

**Phase C — Expansion**

- Tracker lists opcode implementation status; stubs reduced per milestone until coverage matches project needs.

---

## 8) Open assumptions (document in tracker if accepted)

- Script **syntax** is **JSON op arrays**, not the pseudo-code mini-example (which can be compiled to JSON later if desired).
- **2×2 footprint is fixed** (not configurable per event) unless you later extend schema.
- **Save format** for flags/party/inventory during scripts is **out of scope for first runtime slice** unless you explicitly add a savegame module.

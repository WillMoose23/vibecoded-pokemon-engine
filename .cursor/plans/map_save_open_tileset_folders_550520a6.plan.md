---
name: Map save open tileset folders
overview: Extend the map editor with Save/Save As + id prompts, a dedicated Open map flow, and an editor-only hierarchical tileset folder model in tilesets.json (collapsible list, folder CRUD, colors, reorder) while keeping the flat `tilesets` array for validation and C++.
todos:
  - id: tracker-features
    content: Add FEATURE-MAP-011/012/013 entries to docs/tracker.md
    status: completed
  - id: save-prompt-saveas
    content: Implement save prompt, save_as, overwrite checks, macOS/overlay prompts in map_editor.py + config keys
    status: completed
  - id: open-map
    content: "Implement open_map: macOS file dialog + fallback list overlay; wire key + footer"
    status: completed
  - id: folder-schema-ui
    content: editorTilesetFolders in tilesets.json, validate_maps ignore, virtual rows + folder CRUD + reorder/color in map_editor.py
    status: completed
isProject: false
---

# Map editor: Save As, prompts, Open map, tileset folders

## Prerequisites (workspace rules)

Log **separate** FEATURE entries in [`docs/tracker.md`](docs/tracker.md) before implementation, for example:

- **FEATURE-MAP-011** — Save / Save As + filename (map id) prompts  
- **FEATURE-MAP-012** — Open existing map from disk  
- **FEATURE-MAP-013** — Tileset folders (editor UI + `tilesets.json` metadata)

Reference IDs in code comments where helpful.

---

## 1. Save, first-save prompt, and Save As

**Current behavior:** [`save()`](tools/map_editor.py) writes [`MAPS_DIR / f"{self.map_id}.json"`](tools/map_editor.py) with no dialog; [`saved_once`](tools/map_editor.py) flips true after write.

**Target behavior:**

- **`save()` (regular Save, e.g. `S`):**
  - If the map has **never been successfully saved this session** (`saved_once` is false), **or** you adopt an explicit flag like `needs_id_prompt`, show a **map id / filename prompt** (same UX as below) before writing. Sanitize input to a safe filename stem (alphanumeric + `_-.`, reject empty / duplicates unless user confirms overwrite).
  - If already saved once, write to the current `map_id` path without prompting (current behavior).
- **`save_as()` (new, e.g. shortcut from [`map_editor_config.json`](tools/map_editor_config.json) such as `shift+s` or `save_as` key):**
  - **Always** prompt for a new map id (and optionally display name).
  - On confirm: set `self.map_id` (and `self.map_name` if you prompt for it), write JSON to the new path, call [`refresh_map_file_list`](tools/map_editor.py) and [`write_maps_index`](tools/map_editor.py), set `saved_once = True`, clear undo stacks if you treat this as a new document boundary (recommended: **clear** stacks on Save As to match load/new).

**Prompt implementation:** Reuse existing patterns in this file: **macOS** [`_macos_dialog_text`](tools/map_editor.py) / AppleScript (consistent with import flow), or a **pygame overlay** similar to [`_draw_size_overlay`](tools/map_editor.py) / map id edit mode for cross-platform parity. Pick one approach for **both** first save and Save As so behavior is consistent on each OS.

**Edge cases:**

- Refuse or confirm before **overwriting** an existing `src/maps/<id>.json` that is not the “current” file being edited.
- After Save As, the editor is editing the **new** id; old file on disk is unchanged.

---

## 2. Open an existing map for editing

**Current behavior:** [`[` / `]`](tools/map_editor.py) cycle [`map_files`](tools/map_editor.py) and call [`try_load_map_by_id`](tools/map_editor.py). There is no explicit “Open…” discovery flow.

**Add:**

- **`open_map` action** (new key binding + footer line):  
  - **macOS:** AppleScript `choose file` restricted to `src/maps`, default location that folder, multiple selections false, file types JSON — return POSIX path, derive stem as `map_id`, call `try_load_map_by_id(stem)`.  
  - **Fallback (Linux/Windows):** small **modal list** overlay (scrollable) built from `sorted(MAPS_DIR.glob("*.json"))` excluding `maps_index.json`, click or Enter to load — mirrors the spirit of the C++ map picker without adding Tk.
- On successful open: existing loader already clears undo stacks; ensure **`saved_once = True`** after load (file exists on disk).

---

## 3. Tileset folders in the vertical pane

**Constraint:** [`validate_maps.py`](tools/validate_maps.py) and [`loadTilesetRegistry`](src/map_data.cpp) must keep working with a **flat** `tilesets` array of defs (`id`, `image`, …). **Do not** nest tileset definitions inside folder objects in the validated array.

**Schema (editor metadata in same file):** Add an optional top-level object in [`src/tilesets.json`](src/tilesets.json), e.g. `editorTilesetFolders`, **ignored** by validate_maps and C++:

```json
"editorTilesetFolders": {
  "version": 1,
  "folders": [
    { "id": "uuid-or-slug", "name": "Exteriors", "color": [80, 120, 160], "parentId": null }
  ],
  "order": [
    { "kind": "folder", "id": "..." },
    { "kind": "tileset", "id": "boat" }
  ]
}
```

- **`order`:** defines **vertical order** in the pane and grouping: folder rows and tileset rows interleaved; tilesets listed **only** under their placement in `order` (tilesets not listed fall back to an implicit **“Unfiled”** section at top or bottom — document the choice in UI).
- **Per-tileset folder membership** can be derived from `order` (tileset appears after the folder header that precedes it) **or** via optional `folderId` on entries in `order` — simplest v1: **flat `order` list** where a `folder` row starts a group and following `tileset` rows belong to it until the next `folder` or end.

**[`validate_maps.py`](tools/validate_maps.py):** After loading registry, optionally strip or ignore `editorTilesetFolders` when validating tileset entries; continue validating only the `tilesets` array.

**Editor behavior ([`tools/map_editor.py`](tools/map_editor.py)):**

- On registry load: read `editorTilesetFolders`; build a **virtual row list** (folder headers + tileset rows) for hit-testing, scroll, and draw.
- **Create folder:** e.g. button in tileset column header or key — prompt for name; generate stable `id`; append to `folders` and insert `order` entry.
- **Rename folder:** double-click folder row (parallel to tileset rename) or dedicated mode.
- **Folder color:** picker via prompt (hex or RGB) or small preset palette in overlay; store in `color`.
- **Move folders / reorder:** v1 practical approach — **drag folder row** within the list to new index (update `order`), or **Ctrl/Cmd+Up/Down** when a folder row is focused; **move tileset** between groups by dragging tileset row or “Move to folder…” sub-action.
- **Collapse/expand:** optional `collapsed` set in editor state (session or persisted in JSON) to hide tileset rows under a folder.

**Persistence:** Whenever tilesets.json is written today (import, rename, delete tileset), **merge** and preserve `editorTilesetFolders` unless explicitly corrupted.

**Risk:** Large refactor of [`_tileset_index_at_list_pixel`](tools/map_editor.py), list scroll, and draw loop — plan for incremental milestones: (1) data model + flat rendering with folder headers, (2) create/rename/color, (3) drag reorder.

---

## 4. Files to touch (summary)

| Area | Files |
|------|--------|
| Save / Save As / prompts | [`tools/map_editor.py`](tools/map_editor.py), [`tools/map_editor_config.json`](tools/map_editor_config.json) |
| Open map | [`tools/map_editor.py`](tools/map_editor.py), config keys |
| Tileset folders | [`tools/map_editor.py`](tools/map_editor.py), [`src/tilesets.json`](src/tilesets.json) (data), [`tools/validate_maps.py`](tools/validate_maps.py) (ignore extra key) |
| Process | [`docs/tracker.md`](docs/tracker.md) |

No C++ changes required if `tilesets` array remains the source of truth for the game.

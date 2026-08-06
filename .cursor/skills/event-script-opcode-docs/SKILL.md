---
name: event-script-opcode-docs
description: Use when changing map event script opcodes, C++ script dispatch, event_script_op_meta.json, extract_map_script_ops.py, event_script_ops_generated.py, event_script_schema.py, event_script_opcode_docs.py, map_editor script UI/help, validate_map_events sprite/op rules, or docs/event_script_ops.md — keeps implementation and documentation aligned (FEATURE-MAP-049).
---

# Event script opcode documentation sync

## When this applies

- Any edit to **`src/op.cpp`** opcode dispatch (`mapScriptDispatchOpcode` / `tryDispatchMapViewerOpcodes`) or **`src/map_view.cpp`** `Game::tryMapViewerScriptOpcode_` that adds, removes, or renames a script opcode string.
- Changes to **`tools/event_script_op_meta.json`** (labels, descriptions, `default_args`, `args_help`, `category`, `required_params`, status).
- Changes to **`docs/cursor_helper_scripts/extract_map_script_ops.py`**, **`tools/event_script_ops_generated.py`**, **`tools/event_script_schema.py`**, or **`tools/event_script_opcode_docs.py`**.
- Map editor script modal documentation/help: **`tools/map_editor.py`** (`_event_script_rebuild_doc_lines`, `_help_build_lines` `script_ops`, `HELP_GUIDE_TABS`).
- **`docs/cursor_helper_scripts/validate_map_events.py`** when event JSON rules touch scripts or sprites.
- Human summary **`docs/event_script_ops.md`** or tracker/docs that describe opcodes or editor behavior.

## Steps (ordered checklist)

1. **C++ parity:** Implement or adjust the opcode in `src/op.cpp` (and map viewer behavior in `src/map_view.cpp` when the opcode is map-viewer-specific). Keep `if (op == "name")` strings unique and ordered consistently with existing style.
2. **Meta:** Add or update the matching entry in `tools/event_script_op_meta.json` with `label`, `status`, `description`, `default_args`, `args_help`, `category`, and `required_params` (empty array if all parameters are optional for documentation purposes).
3. **Regenerate:** Run `python3 docs/cursor_helper_scripts/extract_map_script_ops.py` from the repo root. Fix any meta/C++ mismatch errors until exit code **0**.
4. **Python schema:** Reload mentally that `tools/event_script_schema.py` imports generated ops and meta at import time; restart the map editor after regen if it was already running.
5. **Structured docs:** If the documentation **shape** changes (new fields, example format), update **`tools/event_script_opcode_docs.py`** and wire callers in **`tools/map_editor.py`** (doc pane + help tab) as needed.
6. **Human summary:** Update **`docs/event_script_ops.md`** (inventory table and any config/validation sections).
7. **Docs / tracker:** Update **`docs/source_doc.md`** / **`docs/tools_doc.md`** when C++ or tool behavior changes; reference **`FEATURE-MAP-049`** or the active tracker id in substantive edits.
8. **Validation:** If map event JSON shape changes, update **`docs/cursor_helper_scripts/validate_map_events.py`** and run `python3 docs/cursor_helper_scripts/validate_map_events.py`.

## Verification

- `python3 docs/cursor_helper_scripts/extract_map_script_ops.py` exits **0**.
- `python3 docs/cursor_helper_scripts/validate_map_events.py` exits **0** (after sprite/script-related validator edits).
- `make` succeeds when C++ sources changed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -c "import ast; ast.parse(open('tools/map_editor.py').read())"` (or project test command) passes after Python edits.

## Notes

- Opcode **order** in the runtime and editor “source” palette comes from **first occurrence** of `if (op == "...")` in `src/op.cpp` as parsed by the extractor — do not reorder lightly.
- **Single documentation builder:** Prefer extending `tools/event_script_opcode_docs.py` rather than duplicating opcode text in `map_editor.py`.

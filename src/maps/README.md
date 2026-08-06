# Map JSON format (`src/maps`)

Maps are tile grids plus optional **connections** to other map ids (for future overworld).

## Fields

| Field | Meaning |
|-------|---------|
| `version` | Schema version (integer). |
| `id` | Unique map id (matches filename without `.json`). |
| `name` | Display name. |
| `tilesetId` | References `id` in [`../tilesets.json`](../tilesets.json). |
| `width`, `height` | Map size in **tiles**. |
| `tileWidth`, `tileHeight` | Usually match the tileset; can override for editor display math. |
| `layers` | Object of named layers (see below). |
| `connections` | Optional exits: `north`, `south`, `east`, `west`. Each has `mapId` (target map `id` or empty), `entryTileX`, `entryTileY` (where the player lands on the target map). |

### Layer types

- **`tileLayers`** (preferred, schema version ≥ 3): array of **tile stack** entries, **bottom to top** draw order. Each element is `{ "id": "<string>", "cells": [ ... ] }`. `cells` has the same shape as **`groundCells`** below (`height` rows × `width` columns): each cell is `null` or `{ "ts": "<tilesetId>", "t": <int> }` with `t` 1-based in that tileset. Empty cells show the layers below. Layer ids should be unique within the map.
- **`ground`** (legacy): `height` × `width` array of integers. `0` = empty; `1+` = 1-based tile index into the map’s `tilesetId` sheet (left-to-right, top-to-bottom). Loaded as a single tile layer when `tileLayers` is absent.
- **`groundCells`** (legacy): same dimensions as `ground`; each cell is `null` or `{ "ts": "<tilesetId>", "t": <int> }`. If present without `tileLayers`, loaders treat it as **one** layer (id `ground`). The editor saves **`tileLayers`** instead when you save from the current map editor.
- **`walkability`** (optional): `0` = legal to walk, `1` = blocked. Applies to the map as a whole (not per visual layer).
- **`transparent`** (optional): `0` = drawn normally, `1` = treated as transparent in-game (rendering). Global grid, same as walkability.

**C++ rendering:** After loading [`MapData`](../../include/map_data.h), draw each entry in `tileLayers` in order (index `0` = back, last = front). For each `(y, x)`, skip cells with `empty == true` / null. Then apply gameplay overlays (walk/debug) as needed.

Validate with: `python3 docs/cursor_helper_scripts/validate_maps.py`

Edit interactively with: `python3 tools/map_editor.py` (requires Pygame: `python3 -m pip install pygame`). If `pip` is not a command on your system, use `python3 -m pip` instead of `pip`.

**Editor UI:** Run from the **repository root** so paths resolve. The window is **resizable** (minimum about 1020×600). The **footer** uses two short lines for shortcuts plus a separate **status** line: **green** = success (e.g. import), **neutral** = info, **red tint** = error. Enlarge the window if the layout feels cramped.

**Quick-start + keys:** The footer includes a quick-start checklist (`import -> brush -> paint -> collision/transparency -> save`) and a live key legend. If you remap keys in the editor settings, the footer updates to reflect those bindings. Toggle quick-start visibility with `H` by default.

**Import:** Press `O` to choose **one or more** PNG tilesets (⌘-click or shift-click in the macOS file dialog for multiple files). **Tile width and height are inferred** from each image’s pixel size (common grid sizes like 16×16); each file becomes a tileset with an **auto-generated id** from the filename (with `_2`, `_3`, … if the id is already taken). A **successful** import shows as a **green** status line (not an error). The footer may still mention editing [`../tilesets.json`](../tilesets.json) only if you need to fix a wrong guess. Terminal **libpng iCCP** warnings are suppressed while loading; they are unrelated to that message.

**Mixed tilesets on one map:** Paint with one tileset, then switch to another tab and paint — the map stores per-cell `ts` + `t` inside `layers.tileLayers[].cells` (saved as `version` 3). Use **comma** / **period** to change the active tile layer, **Insert** or **L** to add a layer, **End** to remove the current layer (with confirmation). Open **Settings** (the `*` control on the map pane) for **Remove current tile layer…** (same confirmation) and for add/remove of the optional **event** layer. On many Mac keyboards there is no Insert key — use **L** (when not in map-id or connection text modes) or rebind in editor settings (`*`).

**Multi-layer tile stacks:** The editor draws **bottom to top** in array order. Legacy maps with only `ground` or `groundCells` load as a single layer named `ground`.

**Tileset list (middle column):** All imported tilesets are listed in a **scrollable** column (names wrap to two lines; a thin bar shows scroll position). **Click** a row to select; **double-click** to **rename**; **Delete** opens a confirmation (Y/N) and removes the entry from `tilesets.json`, clears map cells using that tileset, and deletes the PNG under `Graphics/Tilesets/` only if no other tileset shares that file. You cannot delete the **last** tileset. Folders are stored in `tilesets.json` under `editorTilesetFolders`; each tileset line in `order` may include optional `in_folder` (folder id) so root tilesets can be interleaved with folder rows while children stay indented when a folder is open. To pull a tileset **out** of a folder to the root list, drag it and **release on a folder row while holding Alt** (Option on macOS); that clears `in_folder` and inserts it before that folder. Dropping without Alt still adds the tileset **into** that folder.

**Palette (left):** The tile **preview** can be taller than the panel — use the **mouse wheel** while the pointer is over the preview to scroll the sheet and reach every tile. **Ctrl**/**Cmd**+wheel zooms the preview; **Shift**+wheel pans horizontally when zoomed.

**Fill (F):** In paint mode, **F** toggles fill (bucket) on the **active** tile layer. A **single click** flood-fills the entire connected same-tile region from that cell. With a **multi-tile brush** (e.g. 2×2), the filled region tiles the brush pattern from the click origin so each cell gets the correct repeating tile. **Dragging** a rectangle runs one flood per cell in the drag, each **clipped to that rectangle**, with tiled brush destinations. A 1×1 brush fills with a single tile as before. One undo (**Z**) reverts the whole fill gesture.

**Note:** Some PNGs print `libpng warning: iCCP: known incorrect sRGB profile` in the terminal; it is harmless. The editor silences it while loading images.

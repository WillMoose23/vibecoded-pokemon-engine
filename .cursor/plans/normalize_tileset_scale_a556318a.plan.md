---
name: Normalize tileset scale
overview: Add a scale-factor prompt to the import flow and a post-import "Rescale tileset" command so any tileset can be nearest-neighbor upscaled to match the Outside_General (Outside_2.png) visual standard of 16x16 pixel tiles.
todos: []
isProject: false
---

# Normalize Tileset Scale on Import

## Problem

All tilesets are registered with 16x16 tile grids, but the **art scale** differs between them. In `Outside_2.png` (the standard), a
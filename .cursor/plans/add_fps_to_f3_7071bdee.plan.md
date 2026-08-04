---
name: add fps to f3
overview: Add a frame counter (FPS) to the existing F3 performance HUD with minimal runtime overhead and full tracker/documentation compliance.
todos: []
isProject: false
---

# Add FPS To F3 HUD

## Goal
Show current FPS in the existing F3 panel (`RAM`, `CPU`) without changing F3/F4 toggle behavior or other UI modes.

## 1) Tracker + Status Flow
- Add a new improvement entry in [`/Users/rheyn/Desktop/project/docs/tracker.md`](/Users/rheyn/Desktop/project/docs/tracker.md) before code edits.
- Use required fields and lifecycle: `OPEN -> IN_PROGRESS -> REVIEW -> DONE`.
- Reference the new issue ID in modified source comments where applicable.

## 2) Add Lightweight FPS Sampling State
- Update [`/Users/rheyn/Desktop/project/include/game.h`](/Users/rheyn/Desktop/project/include/game.h) with small FPS state fields in `Game` (frame count window, last sample time, displayed FPS value).
- Keep it local to `Game` (no need to expand `PerfSampler` unless we decide to centralize perf metrics later).

## 3) Update Main Loop FPS Accumulator
- In [`/Users/rheyn/Desktop/project/src/game.cpp`](/Users/rheyn/Desktop/project/src/game.cpp), update FPS counters once per frame in `Game::run`.
- Use a coarse update window (e.g., ~250 ms) so FPS text changes at a bounded rate and avoids creating a new cached text texture every frame.

## 4) Render FPS In F3 HUD
- Extend `Game::drawPerfHud_` in [`/Users/rheyn/Desktop/project/src/game.cpp`](/Users/rheyn/Desktop/project/src/game.cpp):
  - Add a third line: `FPS: <value>`.
  - Include this line in width calculation and panel height (`totalLines = 3`).
  - Keep existing style/colors/placement consistent with current F3 design.

## 5) Validation
- Build project (`make -j4`) and verify no compile regressions.
- Sanity check runtime:
  - F3 shows RAM/CPU/FPS.
  - F4 still replaces F3 panel.
  - FPS value updates smoothly without obvious flicker.

## 6) Documentation Update
- Update [`/Users/rheyn/Desktop/project/docs/source_doc.md`](/Users/rheyn/Desktop/project/docs/source_doc.md) for changed `Game` HUD behavior and any new FPS helper/state.
- Finalize tracker status to `REVIEW` then `DONE` after validation.

## Implementation Notes
- Keep this behavior-preserving: no gameplay/input changes.
- Bound update frequency to reduce RAM growth pressure from dynamic text caching.
- Prefer minimal edits in `Game` rather than wider refactors.
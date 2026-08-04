---
name: Perf HUD and keybinds
overview: Add a toggleable top-left HUD showing smoothed process CPU % and resident RAM, plus a compact in-game keybind reference. Implement platform-specific RSS sampling (macOS mach, Linux /proc) and wire F3 globally before map UI consumes keys; log FEATURE-GAME-001 in the tracker before coding.
todos:
  - id: tracker-game-001
    content: Add FEATURE-GAME-001 to docs/tracker.md
    status: completed
  - id: perf-stats-module
    content: Add perf_stats.h/.cpp (RSS + CPU EMA, macOS + Linux + fallback)
    status: completed
  - id: game-hud
    content: "game.h/cpp: showPerfHud_, F3 toggle, drawPerfHud_, call before Present"
    status: completed
  - id: title-hint
    content: Append F3 line to displayText_ in Game::run
    status: completed
isProject: false
---

# Toggleable RAM/CPU HUD and keybind list

## Tracker (workspace rule)

Add **FEATURE-GAME-001** to [`docs/tracker.md`](docs/tracker.md): toggleable debug HUD (F3) with process RAM + CPU and keybind cheatsheet; scope `include/game.h`, [`src/game.cpp`](src/game.cpp), new `include/perf_stats.h`, [`src/perf_stats.cpp`](src/perf_stats.cpp). Reference the ID in code comments.

## Toggle and input

- **Toggle key: F3** (`SDLK_F3`) — unused today; document it in the HUD and title help line.
- In `Game::run`, handle **F3 before** the `mapUiMode_ != MapUiMode::None` branch so the overlay works on the title screen, in battle, and in map picker/view ([`src/game.cpp`](src/game.cpp) ~598–604).
- State: `bool showPerfHud_` (private in [`include/game.h`](include/game.h)).

## Metrics (accurate enough, cross-platform)

Add a small module **[`include/perf_stats.h`](include/perf_stats.h)** + **[`src/perf_stats.cpp`](src/perf_stats.cpp)** (picked up automatically by the existing `$(wildcard src/*.cpp)` [Makefile](Makefile)):

| Metric | Approach |
|--------|----------|
| **RAM** | **Current resident** process size: `task_info(TASK_BASIC_INFO)` / `TASK_VM_INFO` on **macOS** (e.g. `resident_size`); on **Linux** read **`VmRSS`** from `/proc/self/status`; fallback: `getrusage` / document as approximate if needed. |
| **CPU %** | Sample **process** user+system CPU time (`getrusage(RUSAGE_SELF, …)` or platform equivalent) and **wall time** (`std::chrono::steady_clock`) between updates. Each frame (or every N ms): `cpuRatio = (cpuSecDelta / wallSecDelta)`; display as **percentage of one core** (`cpuRatio * 100`), clamped for sanity (e.g. 0–1000% if you want to show multi-core usage) — plan default **0–100% display with note** or cap at 100% for a “simple” meter; prefer **allow >100%** so multi-threaded spikes are visible. Apply **EMA smoothing** (e.g. `alpha = 0.15`) to reduce flicker. |

Initialize the first sample without showing wild values (skip or show `—` until the second tick).

## Drawing

- Add `Game::drawPerfHud_()` in [`src/game.cpp`](src/game.cpp) (or split to `game_hud.cpp` only if file grows too large — prefer keeping in `game.cpp` with a short helper).
- Call it **once per frame** immediately **before** [`SDL_RenderPresent`](src/game.cpp) (after `drawDebugDexModal` ~784–787) so it paints on top of title, battle, and map UIs.
- Position: **top-left** at [`kTextMargin`](src/game.cpp) (16,16), same coordinate space as the rest of the UI (logical 1280×720).
- Use existing [`renderText`](src/game.cpp) + `font_`; if the cheatsheet is tall, use `TTF_FontLineSkip` in a small loop. **Dim** color (e.g. gray-green) for readability; optional **dark semi-transparent** background quad behind the block (`SDL_SetRenderDrawBlendMode` + fill rect) so text stays readable on bright battle backgrounds.

**HUD content (when `showPerfHud_`):**

1. Line 1: `RAM: <value> MB` (or MiB — pick one and stay consistent).
2. Line 2: `CPU: <value>%` (with brief interpretation in tracker/docs only if needed).
3. Blank line.
4. **Keybind cheatsheet** (all current bindings from code review):

   - **Global / title:** `1` — Pokédex # debug modal; `2` — quick battle; `3` — map viewer; `F3` — toggle this HUD.
   - **Pokédex modal:** `Enter` — confirm; `Backspace`; `0–9` / keypad; `Esc` — close.
   - **Battle:** `Esc` — return to title; `[` / `]` — cycle battle background; `Q` / `W` / `E` / `R` — moves 1–4.
   - **Map list:** `Up` / `Down`; `Enter`; `Esc` — exit map UI.
   - **Map overworld:** `W` / `A` / `S` / `D` — move; `Esc` — back to list.

Keep wording compact (wrapped lines OK) so it stays a “small” panel.

## Title screen discoverability

Append one short line to `displayText_` in `Game::run` (same block as the existing “Press 1…” text ~577–582), e.g. `F3 — toggle perf / keys`, so users find the HUD without reading source.

## Files to touch

| File | Change |
|------|--------|
| [`docs/tracker.md`](docs/tracker.md) | FEATURE-GAME-001 |
| [`include/game.h`](include/game.h) | `showPerfHud_`, `drawPerfHud_()`, `perfStats_` or sampler member |
| [`src/perf_stats.cpp`](src/perf_stats.cpp) | New: RSS + CPU delta + smooth |
| [`include/perf_stats.h`](include/perf_stats.h) | New: small API (`update`, getters) |
| [`src/game.cpp`](src/game.cpp) | F3 toggle, `drawPerfHud_`, call before present; title text line |

## Testing

- Build with `make`; run from repo root; press **F3** on title, in battle, and in map view; confirm RAM/CPU update and key list matches behavior.
- On non-macOS/non-Linux fallback path (if implemented), verify compile and graceful “N/A” or `getrusage`-only behavior.

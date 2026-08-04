---
name: code-refactoring
description: Guides safe refactoring to remove redundancy, simplify structure, and suggest optimizations while preserving behavior. Use when the user asks to refactor, deduplicate, DRY up code, simplify control flow, remove dead code, or improve structure without changing functionality.
---

# Code refactoring (behavior-preserving)

## Role

Act as a **senior refactoring specialist**: reduce redundancy and structural noise, tighten logic, and flag performance opportunities **without** changing observable behavior unless the user explicitly asks for a behavior change.

## Preconditions

1. **Verify logic before edits** — Understand inputs, outputs, side effects, and invariants. The refactored code must match the original’s **behavior** (return values, errors thrown, I/O, mutation of shared state, ordering where it matters).
2. **Match project style** — Indentation (default 2 spaces if the project does not specify), casing, and operator spacing must follow **existing** project conventions and linters. Do not fight `eslint`, `rustfmt`, `gofmt`, etc.
3. **Scope** — Refactor **application/source** the user owns. **Do not** rewrite or “clean” vendored code, `node_modules`, generated files, or third-party subtrees unless the user explicitly targets them.

## Workflow (mandatory)

Copy this checklist mentally or in the reply:

```text
- [ ] Scan: Read the full function/class/module (or the smallest coherent unit).
- [ ] Identify: List redundancies, dead branches, unused symbols, mergeable conditions, risky spots.
- [ ] Propose: Show the refactored version (or minimal diff-shaped explanation).
- [ ] Explain: Short bullet list of what changed and why behavior is unchanged.
```

If a proposed change **might** alter behavior, **do not apply it**; leave the original logic and say why.

## Principles

### DRY and clarity

- Consolidate **repeated** logic into helpers **only** when extraction does not change evaluation order or side effects in a way that matters.
- Remove **unused** imports, variables, and unreachable code when the toolchain confirms they are unused (or reasoning is airtight).
- Prefer **early returns** to reduce nesting when they **preserve** the same outcomes and side-effect order.

### Structural cleanup (only when safe and style-consistent)

- **Braces on single-arm `if`/`else`:** Omit optional braces **only** where the language and project style allow (many codebases require braces for safety). Never drop braces if it would change which statements belong to the branch.
- Simplify boolean expressions (e.g. `x && x` → `x`) only when types and short-circuit semantics stay equivalent.
- Merge adjacent `if` blocks when the **combined** condition is equivalent and readability does not suffer.
- If one initialization is shared across branches, **hoist** or **extract** only when it clarifies flow and does not change **when** side effects run.

### Optimization suggestions (optional callouts)

When not applying a change directly, **suggest** briefly:

- Early-exit / guard-clause patterns.
- Replacing unnecessary **mutable** accumulators with clearer immutable-style expressions **when** allocation and style allow.
- Nested loops or repeated scans that may be **O(n²)** and could become **O(n)** with a map/set — flag as **hypothesis**, not fact, unless complexity is obvious.

### Renames and APIs

- **Do not** rename functions, methods, classes, variables, or files **unless** the user explicitly requests renames.
- **Do not** change **public** API signatures (exports, HTTP contracts, protobuf fields, etc.) unless asked.

### Comments

- **Keep** comments that document non-obvious intent, invariants, or edge cases.
- **Remove** noise (“fix later”, stale TODOs with no ticket) only when clearly obsolete.
- Add a **short** comment when a structural change is non-obvious and needs a **why** for future readers.

## Safety rules (non-negotiable)

- **No behavior change** from “cleanup” alone — if unsure, skip.
- **No** new **race conditions**, reordered async without analysis, or moved side effects.
- **No** drive-by refactors outside the requested surface unless the user widens scope.
- If the code **cannot** be simplified without changing behavior, **state that explicitly** (see example below).

## Formatting

- Trailing whitespace: remove.
- Spacing around operators: match the file and formatter.
- When project config conflicts with a default (e.g. 4 spaces), **follow the project**.

## Example (no safe simplification)

**Before / after** may differ only in indentation or style. When logic must stay nested:

```typescript
if (user.isOnline) {
  if (user.hasPermission) {
    console.log("Access Granted");
  } else {
    console.log("Access Denied");
  }
} else {
  console.log("User Offline");
}
// If combining conditions would change short-circuit behavior or messaging, leave structure as-is.
```

## Repository logging (when applicable)

If the workspace requires a tracker or log entry before implementation (e.g. per `.cursor/rules/Logging-Rule.mdc`), create or update the appropriate **REFACTOR** (or instructed) record before large or multi-file refactors, not for trivial one-line cleanups unless policy says otherwise.

## Response shape for refactoring tasks

1. **Scan summary** — What unit was considered.
2. **Findings** — Bullets: redundancy, dead code, style issues, performance flags.
3. **Result** — Code or diff-style result.
4. **Change log** — What was optimized and **why behavior is preserved** (or what was left untouched and why).

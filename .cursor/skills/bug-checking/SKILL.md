---
name: bug-checking
description: Enforces reproduce-first debugging, root-cause isolation, minimal fixes, verification, and tracker/docs updates for bugs. Use when fixing bugs, regressions, incorrect behavior, crashes, test failures, or when the user asks for disciplined root-cause analysis before changing code.
---

# Bug checking

## When this applies

Whenever work is **diagnosing or fixing a bug** (including regressions, flaky tests, crashes, or “wrong output”), or the user asks for **evidence-based** debugging. This skill complements general coding rules: it is the strict workflow for **search → fix → prove**.

## Preconditions (mandatory)

- **Log first**: Create or update the matching entry in `/docs/tracker.md` before substantive diagnosis or code changes. Use the **exact required fields** and categories from `.cursor/rules/Logging-Rule.mdc` (for `BUG`, include `STEPS_TO_REPRODUCE`, `EXPECTED_BEHAVIOR`, `ACTUAL_BEHAVIOR`; for `FEATURE`/`IMPROVEMENT`/`REFACTOR`, follow that rule’s shape).
- **Reproduce before fixing**: Run the same steps (or equivalent automated repro) and confirm the failure **consistently** where possible.
- **No guessing**: Prefer logs, traces, tests, and reading execution paths over assumptions. If reproduction is impossible, say so explicitly and list what evidence is missing.

Reference the tracker **`ID`** in commits, PR text, or change notes when the repo expects it.

## Bug search process (strict order)

1. **Reproduce** — Execute the exact steps; confirm the bug is real and repeatable (or document intermittency and triggers).
2. **Define failure** — State expected vs actual in one place (align with the tracker entry).
3. **Isolate scope** — Narrow to the smallest credible surface: file → function → branch → data path.
4. **Trace execution** — Follow control flow and data flow step-by-step until behavior diverges from expectations.
5. **Identify root cause** — Name a **specific** logic flaw, wrong invariant, bad state transition, or incorrect assumption—not a symptom.
6. **Validate cause** — Confirm that this cause **fully** explains observations; if not, return to tracing.

## Fixing rules (strict)

- Change **only** what is required to address the validated root cause.
- Prefer the **smallest** diff that is correct; no drive-by refactors or style-only edits in bugfix commits unless explicitly requested.
- Preserve existing behavior and public contracts unless the user or tracker explicitly requires a behavior change.

## Edge cases

Explicitly consider realistic cases: null/invalid input, boundaries, empty collections, timing/races (if plausible), and inconsistent state after partial failure. The fix should handle them without widening scope unnecessarily.

## Verification (mandatory after a fix)

1. Re-run the **original** reproduction → failure must be gone.
2. Exercise **related** paths → no obvious regressions.
3. Re-check **edge** cases touched by the change.

## Documentation and logging (after fix)

- Set tracker **STATUS** through the lifecycle in `.cursor/rules/Logging-Rule.mdc` (e.g. toward **DONE** when verified).
- In the tracker entry (or linked note), record **root cause** and **fix applied** clearly enough for a future reader.
- If application source changed: update `/docs/source_doc.md` per project documentation rules.
- If tools/scripts/build helpers changed: update `/docs/tools_doc.md` accordingly.

## User-facing summary (strict format)

End the bugfix response (or PR description) with:

```text
ISSUE:
<brief description>

ROOT CAUSE:
<specific reason>

FIX:
<what was changed and why>

VALIDATION:
- Reproduced: yes/no
- Fixed: yes/no
- Regression check: pass/fail
```

## Forbidden

- Guessing fixes or patching symptoms without a validated root cause.
- Fixing without reproduction when reproduction is feasible.
- Large rewrites for small bugs.
- Ignoring edge cases that the change plausibly affects.
- Partial fixes left as “good enough.”
- Silent fixes with **no** tracker record.

## Success criteria

- Root cause is specific and evidence-backed.
- Fix is minimal and correct.
- No new regressions found in verification.
- Tracker and docs updates are complete for the scope of the change.

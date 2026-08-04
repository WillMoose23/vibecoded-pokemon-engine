---
name: planning-rule
description: Defines minimal complete planning and repository-aligned execution (docs, tracker, correctness, security) for Cursor’s planning workflow. Use when the user uses Cursor’s planning tool, Plan mode, asks to plan before implementing, or attaches this skill.
---

# Planning rule

## When this applies

Whenever you use **Cursor’s planning tool** or **Plan mode**, or the user asks for a **plan before implementation**. Treat this skill as the contract for what the plan must contain and how later execution must behave in this repo.

For work that skips a formal plan (tiny fixes), still honor **Project integration** and **Pre-response checklist** below.

## What the plan must include

Plans must be **complete**, **minimal**, and free of unnecessary steps. Each plan should make explicit:

- Goal and acceptance criteria (what “done” means).
- Files or subsystems to touch (best-effort if discovery is still needed).
- Risks, edge cases, and how they will be verified.
- **UI and QA verification** (see below) — not optional for editor/UI work.
- Doc/tracker obligations for this repo (see below).

Do not start implementation until requirements are clear; if unclear, the plan should list questions or assumptions—not silent guesses.

## Clarifying questions (unlimited)

Before or during planning, ask **as many clarifying questions as possible** until requirements are unambiguous. **Never self-limit to two questions** (or any fixed number). There is no cap on how many questions you may ask.

- Use `AskQuestion` when structured multiple-choice answers help; use plain chat when open-ended detail is needed.
- Prefer one focused question at a time when choices are independent; batch related choices in a single `AskQuestion` when that reduces back-and-forth.
- Do not guess on blocking decisions (scope, behavior, UX, data shape, acceptance criteria). Ask until requirements are clear enough to plan and implement.
- After the user answers, ask follow-ups if the answer leaves gaps—repeat until the plan can be complete and minimal without silent assumptions.

If the user explicitly asks to proceed with stated assumptions, document those assumptions in the plan and continue.

## UI and QA verification (required in every plan)

When the work touches UI, modals, overlays, or editor tooling:

- Include a **Verification** subsection with:
  - **Automated** commands (`make`, `unittest`, validators, AST parse for large Python modules, etc.).
  - A **manual UI test matrix**: at least small window (~800×600) and typical size; resize; scroll lists; keyboard focus; confirm panels/popovers/lists are **not clipped** (clamp to parent rects like existing map editor fixes).
- “Done” only after that matrix passes or documented exceptions are accepted by the user.
- For bug fixes, include **regression** checks for related modes (e.g. other modals still receive input correctly).

Pure backend-only plans may omit the UI matrix but must still list automated verification.

## Project integration (non-negotiable)

- Follow `/docs/source_doc.md` and `/docs/tools_doc.md` update rules for any source or tool change.
- Follow bug/feature tracking rules in `/docs/tracker.md`: log before substantive work; reference the tracker `ID` in changes when applicable; keep status accurate.
- Do not contradict existing architecture, conventions, or documented invariants.

## General principles

- Correctness over cleverness; simplest solution that fully meets requirements.
- No overengineering, speculative abstractions, or drive-by refactors outside the request.

## Code quality

- Readable, modular, maintainable; small single-purpose functions; meaningful names; DRY without forced indirection.
- Comments only for non-obvious intent (not syntax narration).

## Correctness and reliability

- Do not invent APIs, symbols, or libraries. If unsure, say so and give a concrete verification step (read header, run build, grep, etc.).
- Handle realistic edge cases; avoid undefined behavior and incomplete paths.
- Deliver complete, runnable code: no TODOs, no partial implementations.

## Performance

- Avoid obvious inefficiencies and wrong data structures; no premature micro-optimization unless justified by requirements or evidence.

## Security

Never introduce hardcoded secrets, unsafe shell composition, or injection-prone patterns. Validate and sanitize external inputs; prefer least privilege.

## Debugging and fixes

1. Find root cause, not symptoms; state it briefly.
2. Apply the smallest precise fix; preserve behavior unless the user asked to change it.
3. Avoid large rewrites unless required.

## Output and communication

- Be direct and concise; skip filler.
- When showing edits, be consistent: either focused diff context or full file—do not mix carelessly.
- Ask clarifying questions whenever requirements are ambiguous; use as many as needed (see **Clarifying questions** above)—do not stop at two or withhold questions to save turns.

## Pre-response checklist

Before sending the final answer:

- [ ] Behavior matches requirements and edge cases.
- [ ] Docs updated per repo rules (`source_doc` / `tools_doc` as applicable).
- [ ] Tracker updated if the work was logged there.
- [ ] UI/QA verification from the plan completed (or explicitly deferred with user approval).
- [ ] No new libraries/patterns/architecture without clear justification and alignment.

If any item fails, fix it before responding.

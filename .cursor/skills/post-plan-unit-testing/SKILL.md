---
name: post-plan-unit-testing
description: Creates comprehensive unit tests for newly implemented plans in C++ and Python codebases using the repository's existing test framework, naming conventions, and mocking approach. Use after implementing features, bug fixes, or refactors when the user asks for unit tests, test coverage, edge cases, negative cases, or test quality improvements in C++ or Python.
---

# Post-Plan Unit Testing

## Instructions

Use this skill after implementation work is complete and the next step is unit testing.

1. Identify the changed public API surface:
   - Public functions, methods, classes, and exported modules.
   - Behaviors that callers rely on (inputs, outputs, side effects, errors).
2. Match the repository's current test stack and style:
   - Python: prefer existing `pytest`/`unittest` style and fixtures.
   - C++: prefer existing `GoogleTest`/`Catch2` style and test fixtures.
   - Follow the test folder layout, file naming, setup/teardown, and assertion style already present.
3. Build a coverage matrix per public behavior:
   - Happy path: valid inputs and expected outcomes.
   - Edge cases: null/none, empty collections, boundary min/max, and default values.
   - Negative cases: invalid input, thrown errors, rejected promises, and validation failures.
4. Isolate tests correctly:
   - Mock or stub external dependencies (database, API, file system, network, clock, process env).
   - Python mocking defaults: `unittest.mock` (`patch`, `MagicMock`, autospec when useful).
   - C++ mocking defaults: `gMock` fakes/mocks for interfaces and external boundaries.
   - Avoid mocking internal helpers unless they cause external side effects.
   - Ensure deterministic tests with no shared mutable global state and no race conditions.
5. Write behavior-driven test names:
   - Use names that state behavior and outcome, for example `calculateTotal_Should_Throw_Error_On_Invalid_Input`.
   - Avoid vague names such as `Test 1`, `works`, or `success case`.
6. Use precise assertions:
   - Python: use `pytest.raises` or `self.assertRaises` for expected errors.
   - C++: use precise assertions such as `EXPECT_EQ`, `ASSERT_THAT`, and exception checks like `EXPECT_THROW`.
   - Assert state changes and observable side effects, not only return values.
7. Keep tests focused and readable:
   - Prefer tests under 20 lines when practical.
   - Split complex scenarios into smaller tests.
   - Keep indentation and formatting consistent with existing tests.

## Constraints

- Do not modify production logic while adding tests.
- Do not test private/internal implementation details unless public API stability depends on them.
- Do not use `try/catch` for expected failures unless the framework requires it; prefer `pytest.raises`, `assertRaises`, or `EXPECT_THROW`.
- Do not skip essential async tests; stabilize them instead.

## Execution Workflow

1. Analyze function signatures and dependencies.
2. List required inputs, outputs, side effects, and error states.
3. Generate tests in the repository's existing structure.
4. Review for clarity, isolation, naming quality, and flake risk.
5. Run the relevant test command and fix failing tests before finishing:
   - Python: `pytest` (or project-specific test runner command).
   - C++: project-standard command (for example `ctest` or direct test binary invocation).

## Output Format

When reporting results, provide:

- Files added or updated.
- Behaviors covered (happy, edge, negative).
- Mocking strategy for each external dependency.
- Test command used and outcome.

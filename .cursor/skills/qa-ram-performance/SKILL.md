---
name: qa-ram-performance
description: Performs deep QA reviews focused on RAM and runtime performance risks in code changes. Use when the user mentions performance, memory, RAM, optimization, profiling, latency, throughput, or resource usage.
---

# QA RAM + Performance Review

## Purpose

Run a deep, balanced QA review that evaluates both memory efficiency and runtime performance, then provide prioritized findings with actionable fixes.

## When to Apply

Apply this skill when the user asks for:
- performance optimization
- RAM or memory optimization
- profiling or bottleneck analysis
- throughput or latency improvements
- resource-usage QA checks

## Review Depth and Priorities

Use deep review depth by default.

Balanced focus means:
1. Evaluate CPU/runtime behavior and memory behavior equally.
2. Prefer high-impact fixes before micro-optimizations.
3. Preserve correctness and readability unless the user requests aggressive optimization.

## Review Workflow

Copy and track this checklist during the review:

```markdown
QA Progress:
- [ ] Scope the changed files and execution paths
- [ ] Identify hot paths and allocation-heavy paths
- [ ] Check algorithmic complexity and data-structure choices
- [ ] Check memory lifetime, retention, and copy behavior
- [ ] Evaluate I/O, blocking, batching, and concurrency effects
- [ ] Propose fixes with expected impact and risk
- [ ] Produce hybrid report (severity findings + checklist summary)
```

### 1) Scope and execution mapping
- Identify code paths affected by the change.
- Mark likely hot paths (loops, request handlers, render/update cycles, repeated jobs).
- Mark likely allocation-heavy paths (string building, object creation, buffering, parsing).

### 2) Runtime performance checks
- Algorithmic complexity regressions (nested loops, repeated scans, N+1 patterns).
- Unnecessary repeated computation (missing caching/memoization where appropriate).
- Inefficient I/O usage (too many small reads/writes, synchronous calls in critical paths).
- Contention risks (coarse locks, serialized work, unnecessary global bottlenecks).
- Overly chatty network/database calls that can be batched.

### 3) RAM and memory checks
- Excess allocations inside tight loops.
- Avoidable copies of large objects/strings/arrays.
- Unbounded in-memory growth (maps, caches, queues, buffers) without limits/eviction.
- Retention leaks (long-lived references, listener/subscription cleanup gaps).
- Large temporary objects where streaming/chunking would be better.

### 4) Safety and edge cases
- Verify optimization suggestions do not change behavior.
- Check degradation under high load and worst-case input size.
- Flag trade-offs clearly (memory vs CPU, latency vs throughput, complexity vs maintainability).

## Output Format (Hybrid)

Provide output with both sections below.

### A) Severity Findings
Use this schema for each finding:

```markdown
- [SEVERITY] <short title>
  - Location: <file/symbol>
  - Risk: <runtime, memory, or both>
  - Why it matters: <impact on latency/throughput/RAM>
  - Recommended change: <specific fix>
  - Expected impact: <qualitative estimate>
  - Confidence: <high|medium|low>
```

Severity scale:
- CRITICAL: likely outage, crash, or severe resource exhaustion
- HIGH: clear production-impacting inefficiency
- MEDIUM: meaningful inefficiency, moderate impact
- LOW: minor or situational improvement

### B) QA Checklist Summary
Return concise pass/fail results:

```markdown
## QA Checklist Summary
- Hot-path complexity: PASS/FAIL - <one line>
- Allocation patterns: PASS/FAIL - <one line>
- Memory growth controls: PASS/FAIL - <one line>
- I/O and batching: PASS/FAIL - <one line>
- Concurrency/contention: PASS/FAIL - <one line>
- Regression risk: PASS/FAIL - <one line>
```

## Review Rules

- Prioritize root causes over symptoms.
- Do not suggest speculative rewrites without evidence.
- Prefer simple, localized fixes first.
- If uncertain, state uncertainty and suggest how to verify (benchmark/profiler/test).
- Include at least one practical validation step for each HIGH or CRITICAL finding.

## Validation Guidance

When proposing fixes, recommend targeted validation:
- microbenchmark for tight-loop or algorithm changes
- memory profiling for retention/allocation claims
- load test for concurrency or I/O pipeline changes
- before/after metrics for latency, throughput, and memory peak

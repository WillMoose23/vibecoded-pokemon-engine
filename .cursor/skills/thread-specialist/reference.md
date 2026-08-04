# Thread Specialist Reference

## Review Checklist

Use this checklist during concurrency/performance reviews:

- [ ] Classify each hot path as CPU-bound, I/O-bound, memory-bound, or mixed.
- [ ] Confirm parallelization target is large enough to amortize overhead.
- [ ] Verify pool reuse (no repeated thread creation in loops).
- [ ] Verify concurrency limits are configurable and bounded.
- [ ] Check lock scope and look for contention hotspots.
- [ ] Check lock ordering consistency across code paths.
- [ ] Check shared-state synchronization (no unsafely mutable shared objects).
- [ ] Check Python CPU-bound paths for GIL-safe approach (`multiprocessing`).
- [ ] Check startup/warm-up does not add latency spikes.
- [ ] Confirm benchmarking/measurement plan exists.

## Recommended Patterns

### Map-Reduce
Use for independent per-item transforms with cheap merge/reduction.

### Pipeline
Use staged processing when work has natural boundaries (parse -> transform -> persist).

### Async I/O Fan-Out
Use bounded concurrency for network/disk calls; include backpressure.

### Data Sharding
Split data into disjoint partitions so workers minimize lock sharing.

## Anti-Patterns

- Spawning one thread/task per item in large loops.
- Global coarse lock around all worker operations.
- Unbounded queue growth without backpressure.
- Mixing blocking calls into async paths without isolation.
- Parallelizing logic with strict ordering but no sequencing mechanism.

## Commenting Guidance

When adding parallel code, include concise comments that explain:
- Why parallelization is beneficial here (not just what the code does)
- Why the chosen concurrency limit is safe
- Which invariants keep shared state thread-safe

## Recommendation Template

```markdown
Workload: [CPU-bound / I/O-bound / mixed]

Current bottleneck:
- [brief evidence]

Proposed structure:
- [pool / pipeline / map-reduce / async]
- [how work is partitioned]

Safety changes:
- [lock ordering / channels / atomics / immutability]

Configuration:
- worker_count: [default formula]
- max_in_flight: [if async I/O]

Expected impact:
- Throughput: [estimate]
- Latency: [estimate, including startup behavior]

Verification:
- [benchmark/scenario 1]
- [race/deadlock checks]
```

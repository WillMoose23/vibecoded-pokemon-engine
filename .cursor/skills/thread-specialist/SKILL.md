---
name: thread-specialist
description: Audits code for concurrency and performance optimization, then proposes safe parallelization and contention reduction strategies with expected latency/throughput impact. Use when users mention parallelism, threading, async, worker pools, contention, deadlocks, race conditions, throughput, latency, CPU-bound, or I/O-bound workloads.
---

# Thread Specialist

## Quick Start

Use this skill to improve throughput and reduce latency without introducing race conditions, deadlocks, or resource exhaustion.

Follow this workflow:
1. Audit synchronous blocks and classify workload type.
2. Design a parallel structure only where it provides measurable benefit.
3. Optimize thread counts, lock scope, and allocation behavior.
4. Verify race/deadlock safety and startup latency impact.
5. Explain expected gains and trade-offs.

## Analysis Rules

- Identify **CPU-bound** work (compute-heavy loops, transforms, math) and consider worker pools, threads, or multiprocessing (Python).
- Identify **I/O-bound** work (network, disk, DB waits) and prefer async/non-blocking patterns.
- Avoid parallelizing trivial operations where thread/task overhead outweighs gains.
- Respect ordering requirements; if strict ordering is required, use thread-safe queues/channels and explicit sequencing.

## Concurrency Design Rules

- Reuse pools; do not create threads/tasks repeatedly inside hot loops.
- Keep pool sizes configurable and hardware-aware:
  - CPU-bound default: `worker_count = cores * 2` (tune by benchmarks)
  - Memory-bound default: `worker_count = cores`
  - I/O-bound default: high concurrency with backpressure/limits
- In Python, account for the GIL; use `multiprocessing` for CPU-bound parallelism.
- Prefer partitioning/sharding data so workers touch disjoint regions.

## Contention and Safety Rules

- Reduce coarse locks to fine-grained locks where safe.
- Consider lock-free/low-contention primitives (atomics/CAS/channels) when appropriate.
- Prefer immutable or copy-on-write data flow to reduce synchronization needs.
- Enforce consistent lock ordering; add timeouts where supported to reduce deadlock risk.
- Ensure shared mutable state has explicit synchronization guarantees.

## Cache and Allocation Rules

- Keep related data close in memory and avoid cross-core cache thrashing.
- Reduce allocations in hot paths to stabilize scheduler behavior and latency.
- Validate that any pool warm-up/startup behavior does not create latency spikes.

## Language-Specific Primitive Mapping

- C++: `std::thread`, thread pools, atomics, lock guards, condition variables.
- JS/TS: `async/await`, Promise concurrency controls, worker threads when needed.
- Java: `Executor`/`ExecutorService`, structured async APIs, concurrent collections.
- Python: `asyncio` for I/O, `multiprocessing` for CPU-bound, thread pools for blocking I/O.

## Output Format

When reporting recommendations, include:
1. Workload classification (CPU-bound, I/O-bound, mixed).
2. Proposed concurrency model (pool, pipeline, map-reduce, async, channels).
3. Contention and synchronization changes.
4. Config knobs (thread/concurrency limits) and safe defaults.
5. Expected impact statement (throughput/latency) and verification checks.

For detailed checklists and templates, see [reference.md](reference.md).

# Performance Deity — CLAUDE.md

Drop this file into your project root. Claude Code reads it automatically at the start of every session.

---

## Global Rules

Apply these rules to every task in this project, regardless of which section below is triggered:

1. Never suggest a code change for performance without benchmarking the existing code first.
2. Every optimization must include a before/after comparison table with real numbers (time, memory, or bytes).
3. Prefer algorithmic improvements over micro-optimizations. Fixing O(n²) to O(n log n) takes priority over any constant-factor trick.
4. If a proposed change does not measurably beat the baseline, discard it and try a different approach. Do not present the failed attempt.
5. Every final report must include a one-paragraph explanation of *why* the change is faster, grounded in CPU architecture, memory layout, or I/O behavior.

---

## When to Apply Each Section

Apply the relevant section based on what the user is asking about.

| Section | Apply when the user is working on... |
|---|---|
| Hot-Path Optimizer | Slow functions, execution time, algorithmic efficiency |
| Leak Hunter | Memory leaks, high RAM usage, OOM errors, GC pauses |
| Race Condition Killer | Threading, async concurrency, race conditions, deadlocks |
| N+1 Slayer | Slow database queries, ORM performance, missing indexes |
| Chaos Engineer | Input hardening, resilience, stress testing, fuzzing |
| Network Squeezer | API payload size, bandwidth, HTTP caching, serialization |
| CI/CD Accelerator | Build times, Docker, Webpack, GitHub Actions pipelines |
| Telemetry | Observability, logging, tracing, production monitoring |
| Frame-Rate Enforcer | UI rendering performance, React re-renders, CSS animations |

---

## Hot-Path Optimizer ⚡

Execute all four phases in order. Do not skip any phase.

### Phase 1 — Establish Baseline
1. Identify the exact code to optimize.
2. Run a micro-benchmark using the included tools:
   - Write a temporary micro-benchmark script in the user's workspace (e.g., `.perf-benchmark.py` or `.perf-benchmark.js`).
   - The script MUST contain a warm-up phase (discard ≥10 iterations).
   - The script MUST run ≥100 iterations and output the Average and P95 execution time.
   - Run the script using the terminal.
   - Delete the temporary script after recording the results.
3. Record P95 and Average. Do not proceed until the benchmark runs without error.
4. Report baseline numbers before writing any new code.

### Phase 2 — Algorithmic Analysis
1. State the current Time Complexity (Big-O) explicitly.
2. State the current Space Complexity and identify the primary allocation sites.
3. Name the bottleneck precisely:
   - "Nested loops causing O(n²) scaling"
   - "Repeated string concatenation causing N heap allocations in a tight loop"
   - "Full table scan caused by missing index on `user_id`"

### Phase 3 — Refactoring
1. Rewrite using a more efficient algorithm or data structure. Apply in order of impact:
   - Replace Array/List lookups with Hash Sets/Dictionaries: O(N) → O(1)
   - Vectorization or batching instead of per-item iteration
   - Caching/memoization of expensive, pure computations
   - Zero-allocation patterns, buffer reuse to reduce GC pressure
   - Bitwise operations where mathematically equivalent
2. Run the benchmark on the new code.
3. If the new code is not measurably faster, discard it, select a different approach, and repeat from step 1 of this phase.

### Phase 4 — Report
Present a Performance Report table:

| Metric | Baseline | Optimized | Δ |
|---|---|---|---|
| Average | Xms | Yms | -Z% |
| P95 | Xms | Yms | -Z% |

Follow with a one-paragraph explanation grounded in CPU/memory theory.

---

## Leak Hunter 🧠

### Phase 1 — Isolation
1. Identify the code suspected of leaking.
2. Write a wrapper that runs it in an infinite loop or for ≥1,000,000 iterations.

### Phase 2 — Instrumentation
Inject memory tracking into the wrapper before running it:
- Node.js: `process.memoryUsage().heapUsed` before and after each iteration.
- Python: `tracemalloc.start()` / `tracemalloc.get_traced_memory()`.
- PowerShell: `[System.GC]::GetTotalMemory($false)`.

If memory continuously grows without recovering after GC, the leak is confirmed. Show the growth in text form:
```
Iteration      0:  10 MB
Iteration 100k:  14 MB
Iteration 500k:  40 MB
```

### Phase 3 — Fix
Identify the uncollected reference:
- Event listeners not removed
- Global arrays or caches growing without a size limit
- Closures retaining large outer-scope objects

Apply the fix:
- `removeEventListener` for detached DOM nodes
- `WeakMap` / `WeakRef` for associating data with objects without preventing GC
- Object pooling to reuse memory instead of allocating new objects per cycle

### Phase 4 — Report
Re-run the instrumented wrapper and present:

| Metric | Before | After |
|---|---|---|
| Memory growth per 10k ops | +50MB | +0MB |
| GC pause frequency | High | Stable |

Explain the root cause and the specific reference that was being retained.

---

## Race Condition Killer 🧵

### Phase 1 — Chaos Script
Write a test that fires ≥1,000 concurrent async requests or threads at the target function simultaneously. The test must assert the final state deterministically (e.g., if a counter is incremented 1,000 times, assert `counter === 1000`).

### Phase 2 — Failure Verification
Run the test. If it passes consistently:
- Increase concurrency to 10,000.
- Add `sleep()` calls mid-execution to force thread context switching.

Prove the function is unsafe before fixing it. Do not add synchronization to code that has not been shown to fail.

### Phase 3 — Synchronization
Implement the minimal synchronization primitive needed (prefer in order):
1. Atomic operations (e.g., `Atomics.add`, `atomic.AddInt64`, `std::atomic`)
2. Mutex / Lock with the smallest possible critical section
3. Semaphore only if mutual exclusion alone is insufficient

Do not hold a lock across any I/O operation.

### Phase 4 — Report
Re-run the test with 10,000 concurrent requests. Report the pass/fail counts. The target is 0 failures.

---

## N+1 Slayer 💾

### Phase 1 — Analysis
1. Take the slow query or ORM code.
2. Generate the equivalent raw SQL.
3. Either instruct the user to run `EXPLAIN QUERY PLAN` (SQLite) or `EXPLAIN ANALYZE` (Postgres/MySQL), or infer missing indexes from the `WHERE`, `JOIN`, and `ORDER BY` clauses directly.

### Phase 2 — N+1 Audit
Check whether queries are issued inside a loop. If yes, rewrite using:
- `IN (...)` batch clause
- SQL `JOIN`
- ORM eager loading: `.include()` (Prisma), `.populate()` (Mongoose), `select_related()` / `prefetch_related()` (Django)

### Phase 3 — Rewrite
1. Provide the optimized SQL or ORM code.
2. Provide the exact `CREATE INDEX` statements required.
3. Explain the disk I/O reduction: Full Table Scan O(N) → Index Lookup O(log N).

---

## Chaos Engineer 💥

### Phase 1 — Fuzzer
Write a script that sends the following inputs to the target function:
- 1GB string payloads
- `null`, `undefined`, `NaN`, `-1`, `Infinity`
- Deeply nested recursive JSON (depth >1,000)
- Malformed Unicode strings (`\uFFFD`, null bytes, RTL override characters)
- Simulated network drops or database timeouts via mocked I/O

### Phase 2 — Attack
Run the fuzzer. For each failure, document:
- The exact input that caused the failure
- The failure mode: unhandled exception, memory exhaustion, infinite loop, or incorrect output without error

### Phase 3 — Hardening
For every documented failure:
1. Add input validation at the function boundary. Reject invalid input immediately with a typed error.
2. Add pagination or streaming for inputs that exceed a byte threshold.
3. Add a circuit breaker or retry-with-exponential-backoff for every network and database dependency.

### Phase 4 — Report
Re-run the full fuzzer. For every input that previously caused a crash, show the new response (a structured error, a safe exit, or a logged degradation event). Zero crashes is the target.

---

## Network Squeezer 🌐

### Phase 1 — Payload Profiling
1. Identify the API endpoint.
2. Measure the raw JSON response size in bytes.
3. Identify nested or repeated structures contributing the most bytes.

### Phase 2 — Compression & Caching
1. Check response headers. Verify `Content-Encoding: gzip` or `Content-Encoding: br` is present. If not, enable it server-side.
2. Add HTTP caching headers:
   - `Cache-Control: max-age=<N>, stale-while-revalidate=<N>`
   - `ETag` for conditional GET support

### Phase 3 — Serialization
If the payload exceeds 1MB:
- Migrate to GraphQL so clients request only the fields they need, or
- Migrate to Protocol Buffers (protobuf) for binary serialization.
- For real-time data, use Server-Sent Events or WebSockets to eliminate repeated full-payload polling.

### Phase 4 — Report

| Metric | Before | After |
|---|---|---|
| Payload size | X KB | Y KB |
| Transfer time (3G sim) | Xms | Yms |
| Cache hit rate | 0% | Z% |

---

## CI/CD Accelerator 🏗️

### Phase 1 — Bottleneck
Analyze whichever config file applies:
- `Dockerfile`
- `webpack.config.js` / `vite.config.ts`
- `.github/workflows/*.yml`

Identify the single step that consumes the most wall-clock time.

### Phase 2 — Fix

**Docker:**
- Reorder layers: least-changing layers first (OS deps, runtime), most-changing last (app code).
- Use multi-stage builds: compile in a full image, copy only the output artifact into a minimal runtime image (e.g., `alpine`).

**Webpack / Vite:**
- Enable code splitting and tree-shaking.
- Enable `TerserPlugin` with `parallel: true`.
- Set `cache: { type: 'filesystem' }` for persistent build caching.

**GitHub Actions:**
- Cache `node_modules` using `actions/cache` keyed on the hash of `package-lock.json`.
- Cache `pip` packages keyed on the hash of `requirements.txt`.
- Add `concurrency:` groups to cancel in-progress runs on force-push.

### Phase 3 — Report
State: "This change will save approximately X minutes per PR run" with explicit reasoning.

---

## Telemetry 👁️

### Phase 1 — Trace Wrap
Wrap the critical-path function in a trace span:
- OpenTelemetry: `tracer.startActiveSpan('operation.name', (span) => { ... span.end(); })`
- Sentry: `const transaction = Sentry.startTransaction({ name: 'operation.name' })`
- Datadog: `tracer.trace('operation.name', () => { ... })`

### Phase 2 — Attribute Injection
Inside the span, attach:
- Execution time (start and stop timer)
- Query tags: `user_id`, `tenant_id`, `endpoint`
- Input and output payload sizes in bytes

### Phase 3 — Alert Rules
Propose an alert rule with all four fields specified:
- Metric name and query
- Threshold value
- Evaluation window
- Severity level

Examples:
- Datadog: `avg(last_5m):avg:trace.operation.duration{env:prod} > 0.200` → P2
- Prometheus: `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 0.2` → warning

---

## Frame-Rate Enforcer 🎨

Target: 60 FPS. Execute all three phases.

### Phase 1 — Render Audit

**React:**
- Find components re-rendering when no props changed → wrap with `React.memo`.
- Find inline function or object literals in JSX props (they create a new reference on every render) → extract with `useCallback` or `useMemo`.
- Find Context providers causing full subtree re-renders → split into separate contexts by update frequency.

**Vanilla JS / Vue:**
- Find DOM reads (`offsetHeight`, `getBoundingClientRect`, `scrollTop`) inside loops. These force synchronous layout. Batch all reads before any writes.

### Phase 2 — GPU Acceleration
Find animations driven by:
- JavaScript timers changing `top`, `left`, or `margin`
- CSS transitions on `width`, `height`, `margin`, or `padding`

Rewrite to use:
- `transform: translate3d(x, y, 0)` — handled by the GPU compositor, triggers zero reflow.
- `opacity` — also compositor-only.
- `will-change: transform` on elements that animate on a known trigger.

### Phase 3 — Virtualization
If a component renders more than 50 list items, replace it with a virtualized list:
- React: `react-window` (`FixedSizeList` / `VariableSizeList`) or `@tanstack/react-virtual`.
- Vanilla / Vue: `IntersectionObserver` to mount items only when they enter the viewport.

Only visible DOM nodes exist in the document. All others are unmounted.

---

## Ephemeral Benchmarking

Do not rely on ad-hoc timing or guessing. Whenever a benchmark is required:
1. Write a temporary script (e.g., `.perf-benchmark.js` or `.perf-benchmark.py`) in the user's workspace.
2. Execute the code with a warm-up phase (discarding at least 10 iterations) to prime caches and JIT.
3. Execute the code for at least 100 iterations.
4. Calculate and output the Average and 95th Percentile (P95) execution times.
5. Run the script, read the output, and then delete the script.

---

## Pre-Commit Gate

```bash
cp hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Blocks commits containing `TODO: optimize`. Resolve and benchmark all optimization TODOs before committing.

---

## Prohibited Patterns

- Do not suggest `Promise.all` as a concurrency fix without first proving a concurrency defect exists.
- Do not add `useMemo` preemptively. Add it only after a render audit shows the component is re-rendering unnecessarily.
- Do not recommend a cache without specifying its invalidation strategy.
- Do not add a database index without verifying the column has sufficient cardinality. A low-cardinality index on a boolean column is slower than a full table scan.
- Do not present an optimization with "this should be faster." Present it with numbers showing it is faster.
- Do not add telemetry instrumentation without attaching at least one concrete alert rule.
- Do not optimize code that has not been profiled. Identify the actual bottleneck before writing any replacement.

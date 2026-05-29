# CONTEXT - resume hint for next session

**Current Task:** Office-hours design session for concurrent Studio runs (v1.3) — running multiple Studio actions at once inside one tab. Design approved, no code yet. Brief + decisions entry written on `dev`.

**Key Decisions:**
- Approach C (phased hybrid): Slice 1 = client run-manager (`Map<runId,RunState>`) + server-side NLM mutex + `queue.json` file lock; Slice 2 = full server JobManager for fire-and-forget queue.
- Concurrency lives inside one tab (sidesteps `TabGuard`); auto-queue contention behaviour. (full entry in memory/decisions.md, 2026-05-29)
- Engine already concurrency-capable (one subprocess per `/ws/studio/run`); the work is frontend run-manager + a mandatory server resource-guard layer.

**Next Steps:**
1. Land `queue.json` file locking standalone first (backlog #1, prerequisite).
2. `/plan-eng-review` on `memory/tasks/briefs/concurrent-studio-runs-design.md` — lock NLM mutex mechanism (Win+WSL), parallel-cap config key, test plan.
3. Build Slice 1; smoke-test the five success criteria in the brief.

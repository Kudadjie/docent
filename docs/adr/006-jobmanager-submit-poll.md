# ADR-006: Background JobManager — submit → poll for long-running actions

**Status:** Active
**Date:** 2026-07-01
**Deciders:** John David K. T. Kudadjie

---

## Context

10 of 11 studio backends run multi-minute pipelines that cannot complete
inside an MCP tool-call timeout — the backend matrix literally documented them
as "✗ (timeout)" over MCP, with users told to fall back to a terminal. The web
UI carried two parallel streaming transports (SSE for in-process runs, a
WebSocket-subprocess path for the live frontend) as a workaround, plus
tuning like oversized h11 event limits. Refreshing the browser lost a run.
The workarounds were accreting faster than the features.

## Decision

A `JobManager` in `core/jobs.py` turns any registered action into a
background job:

- **Thread-per-job, daemonic.** The entire action stack is sync generators;
  threads match the existing fan-out primitive (`studio/fanout.py`) and avoid
  asyncio collisions with FastAPI's event loop. Records left active by a dead
  process are marked `interrupted` on the next startup scan.
- **Admission by `BoundedSemaphore(2)`** — excess submissions queue.
- **Persistence:** one JSON file per job under `~/.docent/data/jobs/`;
  retention = last 50 records.
- **Cooperative cancellation** between ProgressEvents; queued jobs die before
  starting; blocking single-shot actions finish before a cancel lands.
- **Surfaces:** a `jobs` tool (`status` / `result` / `cancel` / `list`) rides
  the tool contract onto CLI, MCP, and the schema-driven web form page;
  `ui_routes/jobs.py` adds REST polling endpoints for the UI.
- **MCP async-by-default:** studio `deep-research`, `lit`, `review`, and
  `to-notebook` with any backend except `free` are submitted as jobs; the MCP
  call returns `{"async": true, "job_id": ...}` with polling instructions.
  This makes every AI backend usable over MCP for the first time.

## Consequences

**Good:**
- The entire backend matrix works over MCP; the "run it in your terminal
  instead" caveat is gone.
- One future UI transport: poll `/api/jobs/{id}` — refresh-safe, no WebSocket
  lifecycle management. The WS-subprocess path stays until the frontend
  switches, then gets deleted.

**Trade-offs:**
- Jobs live inside the serving process — `docent serve` (stdio) dies with its
  client session, killing in-flight jobs (marked `interrupted`). Long runs are
  better hosted by `docent ui`. A detached worker daemon was deliberately NOT
  built (speculative complexity for a single-user tool).
- Blocking actions can't be interrupted mid-flight; cancellation is only as
  granular as the action's progress events.
- No opt-out flag for MCP async in v1 — accepted to keep input schemas
  untouched; revisit if a real need appears.

**Rejected alternatives:**
- **asyncio task queue:** would force `asyncio.run()` bridges through a sync
  generator stack — the same collision the fan-out ADR already rejected.
- **Process pool / detached daemon:** survives server restarts but adds IPC,
  serialization of Context, and lifecycle management — out of proportion for
  a personal tool.
- **Keep streaming transports and raise timeouts:** treats the symptom;
  refresh-loss and dual-transport drift remain.

## Related

- `src/docent/core/jobs.py` — JobManager
- `src/docent/tools/jobs.py` — jobs tool (all surfaces)
- `src/docent/ui_routes/jobs.py` — REST polling endpoints
- `src/docent/mcp_server.py` — `_ASYNC_ACTIONS` routing
- `AGENTS.md` §1 Rule 4 — the agent-facing polling contract
- ARCHITECTURE.md Layer 13 + Studio Backend Matrix

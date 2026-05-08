---
name: Codex review - pre-v1.2.0 blockers and architectural debt
description: Ordered list of issues from the 2026-05-08 Codex review to fix before v1.2.0 and beyond; work on these before new feature work
type: project
---

Fix these in order before any new features or v1.2.0 tag.

## Release blockers (must ship before v1.2.0)

1. **DONE 2026-05-08: Add `/api/tooling` to `ui_server.py`** - the tooling update checker no longer 404s in packaged mode. `src/docent/ui_server.py` now exposes `/api/tooling`, checks global `@companion-ai/feynman` via npm, fetches latest from the npm registry, and has regression coverage in `tests/test_ui_server_tooling.py`.
2. **DONE 2026-05-08: Fix `shell: true` in Next API routes** - all `frontend/src/app/api/**` subprocess calls now use `spawn(..., { shell: false })`. `actions/route.ts` no longer uses `exec` or command strings for reading actions; `tooling/route.ts` uses `npm.cmd` on Windows so npm still works without a shell.
3. **DONE 2026-05-08: Clean `npm run lint`** - frontend lint is now clean. Fixed React compiler lint errors by deferring browser-only initialization out of synchronous effect bodies, removed unused UI state/constants, escaped JSX text, and verified with `npm run lint` plus `npx tsc --noEmit`.
4. **DONE 2026-05-08: Local font fallback** - `frontend/src/app/layout.tsx` no longer imports `next/font/google`. `frontend/src/app/globals.css` now defines `--sans` and `--mono` as system/plain CSS font stacks. Verified with no remaining `next/font` references, `npm run lint`, `npx tsc --noEmit`, and `python scripts/build_ui.py`.
5. **DONE 2026-05-08: Fix stale README/docs flags** - README, `docs/cli.md`, and the UI docs page now use current reading flags (`--category`, `--deadline`, `--key`, `--value`) and no longer mention removed `--course-name`, `--course`, `--date`, `--clear`, or `unpaywall_email` settings. Verified by grep, `npm run lint`, `npx tsc --noEmit`, `python scripts/build_ui.py`, and `uv run pytest --tb=no -q`.

## Medium debt (post-v1.2.0, before v1.3.0)

6. **MCP single-action tools missing** - `mcp_server.py` only iterates `collect_actions(tool_cls)`; single-action plugins never appear. Add the single-action branch (mirrors `cli.py:324`).
7. **`edit --status` bypasses `_set_status`** - `EditInputs.status` accepts any string and writes it directly, skipping the timestamp/lifecycle logic in `_set_status`. Either route through `_set_status` or remove `status` from `edit`. Use `Literal` / enum to prevent invalid values.

## Architectural debt (deliberate backlog)

8. **`docent.core.invoke` module** - CLI, MCP, FastAPI, and Next dev routes all invoke tools differently. A single `invoke(tool, action, inputs, context)` module with adapters for each surface eliminates the drift class of bugs (including the /api/tooling miss above). Biggest leverage move.
9. **Next API routes -> thin dev-only proxies** - FastAPI is the canonical backend (static export has no Next routes; packaged `docent ui` is all FastAPI). The correct architecture: (a) FastAPI implements every endpoint first, (b) Next dev routes forward to `http://127.0.0.1:7432/api/...` with no business logic, (c) post-v1.2.0 decide whether to drop Next routes entirely and just run frontend dev against FastAPI directly. The proxy is a dev adapter, not the backend - FastAPI must have the route first.
10. **Move Rich rendering out of tool result models** - `__rich_console__` inside plugin result models leaks UI concerns. CLI should render shapes explicitly via `to_shapes()`.
11. **File locking on reading queue writes** - atomic temp+rename protects against partial writes but not concurrent read-modify-write races. Add a lock in `ReadingQueueStore`.
12. **Schema-generated docs** - generate README flag tables from registered tool schemas, or add a contract test that docs only reference valid flags.

**Why:** Codex independent review 2026-05-08. These are the findings ranked by release impact. The overarching pattern: four invocation paths (CLI/MCP/FastAPI/Next) diverge silently - any new surface needs `docent.core.invoke` to stay in sync.

**How to apply:** At the start of every session, check whether any of the release blockers (1-5) are still open. Do not tag v1.2.0 until all five are cleared.

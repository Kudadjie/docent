---
name: Docent master todo list
description: Comprehensive ordered todo list across all active tracks; update after each session; read when planning what to work on next
type: project
---

Last updated: 2026-05-11 (Hermes session — Claude Code usage limit)

---

## IMMEDIATE — v1.2.0 blockers

1. ~~**Bug 1: Duplicate tool registration**~~ — FIXED 2026-05-11. Root cause: absolute import `from docent.bundled_plugins.research_to_notebook.oc_client` in `usage()` caused `__init__.py` to execute under a different `sys.modules` key. Fix A: changed to relative `from .oc_client import`. Fix B: registry duplicate check now warns + skips instead of raising.
2. ~~**Bug 2: Replace `duckduckgo_search` with Tavily**~~ — FIXED 2026-05-11. Replaced across `pyproject.toml`, `settings.py`, `search.py`, `__init__.py`, `pipeline.py`. Added Tavily request counter (`tavily_spend.json`). Updated `docs/cli.md` + `README.md`.
3. **Re-run real-life research tests #3–17** after both bugs fixed → tag v1.2.0. (PENDING — needs WSL venv ready + Tavily API key in config)

---

## POST-v1.2.0 — Hardening Sprint (do before Phase 2 UI)

4. **UI server direct invocation** — `ui_server.py` spawns a CLI subprocess per mutation. Causes stale titles (no Mendeley overlay applied), ~100ms spawn overhead, brittle ANSI parsing. Fix: wire `ui_server.py` endpoints to call `invoke_action()` directly (already in `mcp_server.py`).
5. **Reading monolith split** — `bundled_plugins/reading/__init__.py` ~1,215 lines. Split into: `models.py` / `sync.py` / `ordering.py` / `renderers.py` / `tool.py` (~400 lines) / `__init__.py` (re-exports only, ~20 lines).
6. **Research tool DRY-up** — `deep()`, `lit()`, `review()` ~150 lines each with 3–4 real differences. Extract `_run_pipeline()` shared core; each action collapses to ~15 lines. (~400 lines duplication to remove)

---

## POST-v1.2.0 — Medium Codex debt (before v1.3.0)

7. **MCP single-action tools missing** — `mcp_server.py` only iterates `collect_actions()`; single-action plugins never appear. Add the single-action branch (mirrors `cli.py:324`).
8. **`edit --status` bypasses `_set_status`** — `EditInputs.status` writes directly, skipping timestamp/lifecycle logic. Route through `_set_status` or remove `status` from `edit`. Use `Literal`/enum to prevent invalid values.

---

## ARCHITECTURE debt (deliberate backlog)

9. **`docent.core.invoke` module** — CLI, MCP, FastAPI, Next dev routes all invoke tools differently. A single `invoke(tool, action, inputs, context)` with adapters for each surface eliminates the drift class of bugs. Biggest leverage move.
10. **Next API routes → thin dev-only proxies** — FastAPI is the canonical backend. Correct architecture: (a) FastAPI implements every endpoint first, (b) Next dev routes forward to `http://127.0.0.1:7432/api/...` with no business logic. Decide post-v1.2.0 whether to drop Next routes entirely.
11. **Move Rich rendering out of tool result models** — `__rich_console__` inside plugin result models leaks UI concerns. CLI should render shapes explicitly via `to_shapes()`.
12. **File locking on reading queue writes** — atomic temp+rename protects against partial writes but not concurrent read-modify-write races. Add lock in `ReadingQueueStore`.
13. **Schema-generated docs** — generate README flag tables from registered tool schemas, or add a contract test verifying docs only reference valid flags.

---

## Phase 1.5 — Remaining skill ports

14. **`to-notebook` action (Phase D)** — NotebookLM integration: take research output, push sources into a NotebookLM notebook. Completes the "research-to-notebook" name.
15. **`alpha-research` port** — paper search/read via alphaXiv; pairs with reading queue (search → add).
16. **`scholarly-search` port** — Google Scholar wrapper with Semantic Scholar/CrossRef fallback. Cheap once alpha-research lands.
17. **`literature-review` port** — multi-source synthesis consuming alpha + scholarly outputs.
18. **Phase E: remaining Feynman workflows** — `compare`, `draft`, `replicate`, `audit`, `watch` on both backends. Deferred.

---

## Phase 2 — UI

19. **Schema-driven forms** — backend exposes `input_schema` as JSON Schema; React generates forms dynamically. No hard-coded per-tool components.
20. **Live Telemetry pane** — consume `ProgressEvent` stream from generator actions via SSE/WebSocket.
21. **Artifact Viewer** — render Output Shapes as React components (one per shape type).
22. **Omnibox Mode 1** — NL → existing action ("summarize my queue" → `docent reading stats`). Small classifier + `all_tools()` registry.
23. **Omnibox Mode 2** (Phase 2.5) — on-the-fly tool generation + hot-load into registry. Security question to resolve first.

---

## Infrastructure / housekeeping

24. **Pin `actions/setup-node` to SHA** in `publish.yml` — CSO audit flag; still unpinned as of v1.1.1. Must ship before next public release.
25. **`ruff` + `mypy` in CI** — missing from pipeline; flagged in GLM-5.1 review.
26. **`mendeley_mcp_command` config-set** — list-typed setting not yet exposed via `config-set`. Deferred since Step 11.4.
27. **BibTeX export** — needs CrossRef-clean metadata. Deferred since Step 8.
28. **Semantic Scholar orphan identification** — `--identify-orphans` flag on `sync-status`. Deferred since Step 11.1.
29. **`utils/logging.py`** — defer until a step needs logged output.
30. **Eval harness** — trigger: first production LLM call tool that needs golden sets + scoring. Deferred per `harness_principles.md`.

---

## v1.3+ roadmap items

31. **Zotero integration** — `ReferenceManagerClient` protocol, `sync_source` toggle (Mendeley OR Zotero, not both), `pyzotero` vs `zotero-mcp` question open.
32. **Obsidian integration** — `to-vault` output, literature notes on `done`, Dataview-compatible frontmatter, daily notes, Templater.

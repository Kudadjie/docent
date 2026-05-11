---
name: Docent master todo list
description: Comprehensive ordered todo list across all active tracks; update after each session; read when planning what to work on next
type: project
---

Last updated: 2026-05-12 (Hermes session — references-in-markdown + Tavily quota handling)

---

## IMMEDIATE — v1.2.0 release blockers

1. ~~**Bug 1: Duplicate tool registration**~~ — FIXED 2026-05-11
2. ~~**Bug 2: Replace `duckduckgo_search` with Tavily**~~ — FIXED 2026-05-11
3. **Real-life research tests #9–#18 must pass before v1.2.0 tag**
   - Tests #1–#8: PASSED (2026-05-12)
   - Test #9 (lit review): not yet run
   - Test #19 (references section in markdown): not yet run — code is done, needs manual verification
   - Test #18 (Tavily quota exhaustion with invalid key): not yet run — code is done, needs manual verification
   - Tests #10–#17: not yet run (Feynman, budget, MCP, UI — less critical)

---

## DONE this session (2026-05-12)

4. ~~**References section in markdown output**~~ — DONE. `_build_references_section()` added to `__init__.py`; both `deep` and `lit` actions now append a `## References` section with numbered entries (title, URL, source type) to the `.md` output. Sources without URLs are skipped. JSON file kept alongside.
5. ~~**Tavily quota exhaustion — graceful failure**~~ — DONE. `UsageLimitExceededError` caught specifically in `_run_tavily_pipeline` (pipeline.py) with a clear message: "Tavily monthly free tier (1,000 calls) has been exceeded. Wait for next billing cycle, upgrade, or use backend='feynman'." Quota errors skip the manual-pipeline fallback (which would also fail). Other Tavily errors still fall back as before.
6. ~~**Tests #1–#8 real-life verification**~~ — PASSED 2026-05-12

---

## POST-v1.2.0 — Hardening Sprint (do before Phase 2 UI)

7. **UI server direct invocation** — `ui_server.py` spawns a CLI subprocess per mutation. Causes stale titles (no Mendeley overlay applied), ~100ms spawn overhead, brittle ANSI parsing. Fix: wire `ui_server.py` endpoints to call `invoke_action()` directly (already in `mcp_server.py`).
8. **Reading monolith split** — `bundled_plugins/reading/__init__.py` ~1,215 lines. Split into: `models.py` / `sync.py` / `ordering.py` / `renderers.py` / `tool.py` (~400 lines) / `__init__.py` (re-exports only, ~20 lines).
9. **Research tool DRY-up** — `deep()`, `lit()`, `review()` ~150 lines each with 3–4 real differences. Extract `_run_pipeline()` shared core; each action collapses to ~15 lines. (~400 lines duplication to remove)

---

## POST-v1.2.0 — Medium Codex debt (before v1.3.0)

10. **MCP single-action tools missing** — `mcp_server.py` only iterates `collect_actions()`; single-action plugins never appear. Add the single-action branch (mirrors `cli.py:324`).
11. **`edit --status` bypasses `_set_status`** — `EditInputs.status` writes directly, skipping timestamp/lifecycle logic. Route through `_set_status` or remove `status` from `edit`. Use `Literal`/enum to prevent invalid values.

---

## ARCHITECTURE debt (deliberate backlog)

12. **`docent.core.invoke` module** — CLI, MCP, FastAPI, Next dev routes all invoke tools differently. A single `invoke(tool, action, inputs, context)` with adapters for each surface eliminates the drift class of bugs. Biggest leverage move.
13. **Next API routes → thin dev-only proxies** — FastAPI is the canonical backend. Correct architecture: (a) FastAPI implements every endpoint first, (b) Next dev routes forward to `http://127.0.0.1:7432/api/...` with no business logic. Decide post-v1.2.0 whether to drop Next routes entirely.
14. **Move Rich rendering out of tool result models** — `__rich_console__` inside plugin result models leaks UI concerns. CLI should render shapes explicitly via `to_shapes()`.
15. **File locking on reading queue writes** — atomic temp+rename protects against partial writes but not concurrent read-modify-write races. Add lock in `ReadingQueueStore`.
16. **Schema-generated docs** — generate README flag tables from registered tool schemas, or add a contract test verifying docs only reference valid flags.

---

## Phase 1.5 — Remaining skill ports

17. **`to-notebook` action (Phase D)** — NotebookLM integration: take research output, push sources into a NotebookLM notebook. Completes the "research-to-notebook" name.
18. **`alpha-research` port** — paper search/read via alphaXiv; pairs with reading queue (search → add).
19. **`scholarly-search` port** — Google Scholar wrapper with Semantic Scholar/CrossRef fallback. Cheap once alpha-research lands.
20. **`literature-review` port** — multi-source synthesis consuming alpha + scholarly outputs.
21. **Phase E: remaining Feynman workflows** — `compare`, `draft`, `replicate`, `audit`, `watch` on both backends. Deferred.

---

## Phase 2 — UI

22. **Schema-driven forms** — backend exposes `input_schema` as JSON Schema; React generates forms dynamically. No hard-coded per-tool components.
23. **Live Telemetry pane** — consume `ProgressEvent` stream from generator actions via SSE/WebSocket.
24. **Artifact Viewer** — render Output Shapes as React components (one per shape type).
25. **Omnibox Mode 1** — NL → existing action ("summarize my queue" → `docent reading stats`). Small classifier + `all_tools()` registry.
26. **Omnibox Mode 2** (Phase 2.5) — on-the-fly tool generation + hot-load into registry. Security question to resolve first.

---

## Infrastructure / housekeeping

27. **Pin `actions/setup-node` to SHA** in `publish.yml` — CSO audit flag; still unpinned as of v1.1.1. Must ship before next public release.
28. **`ruff` + `mypy` in CI** — missing from pipeline; flagged in GLM-5.1 review.
29. **`mendeley_mcp_command` config-set** — list-typed setting not yet exposed via `config-set`. Deferred since Step 11.4.
30. **BibTeX export** — needs CrossRef-clean metadata. Deferred since Step 8.
31. **Semantic Scholar orphan identification** — `--identify-orphans` flag on `sync-status`. Deferred since Step 11.1.
32. **`utils/logging.py`** — defer until a step needs logged output.
33. **Eval harness** — trigger: first production LLM call tool that needs golden sets + scoring. Deferred per `harness_principles.md`.

---

## v1.3+ roadmap items

34. **Zotero integration** — `ReferenceManagerClient` protocol, `sync_source` toggle (Mendeley OR Zotero, not both), `pyzotero` vs `zotero-mcp` question open.
35. **Obsidian integration** — `to-vault` output, literature notes on `done`, Dataview-compatible frontmatter, daily notes, Templater.
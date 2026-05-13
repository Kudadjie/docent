---
name: Docent master todo list
description: Comprehensive ordered todo list across all active tracks; update after each session; read when planning what to work on next
type: project
---

Last updated: 2026-05-13 (items 13, 14, 16 done — post-v1.2.0 sprint complete)

---

## IMMEDIATE — v1.2.0 release blockers (omnibus: all ship BEFORE tag)

1. ~~**Bug 1: Duplicate tool registration**~~ — FIXED 2026-05-11
2. ~~**Bug 2: Replace `duckduckgo_search` with Tavily**~~ — FIXED 2026-05-11
3. ~~**References section in markdown output**~~ — DONE
4. ~~**Tavily quota exhaustion — graceful failure**~~ — DONE
5. ~~**Duplicate References bug**~~ — FIXED (`_strip_references_section()` + `_append_references()`)
6. ~~**Feynman FileNotFoundError**~~ — FIXED (`FeynmanNotFoundError` + `_find_feynman()`)
7. ~~**Hardening: UI server direct invocation**~~ — DONE 2026-05-13 (ui_server wired to invoke_action(); commit 1dfd8f8)
8. ~~**Hardening: Reading monolith split**~~ — DONE 2026-05-12 (split into models.py + mendeley_sync.py; 1271→618 lines)
9. ~~**Hardening: Research tool DRY-up**~~ — DONE 2026-05-12 (extracted `_run_with_tavily_fallback()`; run_deep/run_lit 55→17 lines)
10. ~~**Medium debt: MCP single-action tools**~~ — DONE 2026-05-12 (`build_mcp_tools()` + `invoke_action()` now handle single-action tools)
11. ~~**Medium debt: `edit --status` bypass**~~ — DONE 2026-05-13 (`_apply_status_transition` helper; timestamps stamped correctly)
12. ~~**`docent doctor`**~~ — DONE 2026-05-13 (10-check table, subprocess-free, 327 tests green)
13. ~~**`docent setup`**~~ — DONE 2026-05-13 (re-runnable guided config wizard)
14. **Real-life tests #10–#19** (can happen in parallel with above; #10 blocked on feynman reinstall + credits)

---

## AFTER v1.2.0

12. ~~**`docent.core.invoke` module**~~ — DONE 2026-05-13. `core/invoke.py`: `make_context()` + `run_action()`; mcp_server delegates to it; ui_server POST /api/config uses it directly.
13. ~~**Next API routes → thin dev-only proxies**~~ — DONE 2026-05-13. Replaced all 6 `route.ts` files with a single `rewrites` rule in `next.config.ts`. `npm run dev` now proxies `/api/*` → `http://127.0.0.1:7432`. Also fixed silent `tags` drop in `ui_server.py` post_action.
14. ~~**Move Rich rendering out of tool result models**~~ — DONE 2026-05-13. Removed 15 `__rich_console__` methods; `_build_callback` in `cli.py` now calls `render_shapes(result.to_shapes(), console)` directly.
15. ~~**File locking on reading queue writes**~~ — DONE 2026-05-13. `ReadingQueueStore.lock()` with filelock, timeout=0 (fail-fast). All 8 mutating actions + mendeley_sync write block wrapped.
16. ~~**Schema-generated docs**~~ — DONE 2026-05-13. `tests/test_doc_flags.py` contract test: all `--flag` mentions in README + docs/cli.md verified against registered tool schemas on every test run.

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
---
name: Docent master todo list
description: Comprehensive ordered todo list across all active tracks; update after each session; read when planning what to work on next
type: project
---

Last updated: 2026-05-13 (CI gap confirmed: tests never run on tag push; #27 already done)

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

## AFTER v1.2.0 — completed hardening sprint

12. ~~**`docent.core.invoke` module**~~ — DONE 2026-05-13.
13. ~~**Next API routes → thin dev-only proxies**~~ — DONE 2026-05-13. Single `rewrites` rule in `next.config.ts`; fixed `tags` drop in `post_action`.
14. ~~**Move Rich rendering out of tool result models**~~ — DONE 2026-05-13. 15 `__rich_console__` methods removed.
15. ~~**File locking on reading queue writes**~~ — DONE 2026-05-13.
16. ~~**Schema-generated docs**~~ — DONE 2026-05-13. `tests/test_doc_flags.py` contract test.

---

## Phase 1.5 — Remaining skill ports

17. ~~**`to-notebook` polish**~~ — DONE 2026-05-14. Fixed `docent research` → `docent studio` in all error messages (3 files); relaxed Feynman-output guard (no sources.json no longer fatal); 19 new NLM helper tests; 369 green.
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

27. ~~**Pin `actions/setup-node` to SHA**~~ — DONE 2026-05-07. All 3 actions SHA-pinned (`checkout`, `setup-uv`, `setup-node`).
28. ~~**CI test + lint gap**~~ — FIXED 2026-05-14. pytest + ruff steps added to publish.yml before uv build; ruff>=0.9 added to dev deps.
29. **`mendeley_mcp_command` config-set** — list-typed setting not yet exposed via `config-set`. Deferred since Step 11.4.
30. **BibTeX export** — needs CrossRef-clean metadata. Deferred since Step 8.
31. **Semantic Scholar orphan identification** — `--identify-orphans` flag on `sync-status`. Deferred since Step 11.1.
32. **`utils/logging.py`** — defer until a step needs logged output.
33. **Eval harness** — trigger: first production LLM call tool that needs golden sets + scoring. Deferred per `harness_principles.md`.
34. **Breaking changes policy** — how to handle breaking changes in external tooling (feynman, MCP servers) and docent itself. Needs a decision before any v2.x work.

---

## v1.3 — Ingestion phase (Vision Phase 1)

> **Prerequisite decision before any work starts:** Mendeley/Zotero coexistence policy. Mendeley is live and battle-tested. Zotero is planned. Researchers are tribal — the answer shapes everything below. Options: (a) coexist as parallel `sync_source` toggle, (b) deprecate Mendeley on a timeline, (c) Zotero is the new default; Mendeley stays for existing users. Decide before coding.

35. **Plugin developer docs** — formal guide for external plugin authors. API is stable; no docs exist. Prerequisite for community-built integrations (Zotero bridge, Overleaf sync, etc.). Short doc covering: `@register_tool`, `@action`, `input_schema`, `to_shapes()`, plugin directory layout, and how to publish.
36. **Zotero SQLite bridge** — monitor `zotero.sqlite` for new entries; auto-insert into reading queue with status "queued". `ReferenceManagerClient` protocol, `pyzotero` vs `zotero-mcp` question open. See `project_zotero_integration.md`. Gate on coexistence decision above.
37. **`docent doctor` auto-install** — extend current doctor (status-only) to offer guided install for missing tools: `feynman`, `mendeley-mcp`, `zotero-mcp`. Not fully automated (user confirms each); just eliminates copy-pasting npm/uvx commands.
38. **ASReview agentic screening** — expose an automated screening pipeline: Docent feeds paper abstracts + inclusion/exclusion criteria to Hermes; Hermes tags relevant/irrelevant autonomously. Targets the systematic review use case. Low priority until Zotero bridge lands (needs bulk ingestion to be useful).

---

## v1.4 — Workspace phase (Vision Phase 3)

39. **Obsidian integration** — `to-vault` output shape, literature notes written on `reading done`, Dataview-compatible frontmatter, daily notes hook, Templater support. See `project_obsidian_integration.md`.
40. **Overleaf / LaTeX Git sync** — when research output or literature review is finalised, push formatted `.tex` to a Git repo linked to an Overleaf project. Config: `overleaf_git_remote`. Keeps local AI engine and cloud compiler in sync.
41. **LaTeX lint guardrail** — pre-export pass checking formatting standards, academic tone, and reference completeness against a target journal template. Paperpal-style; runs locally via Claude.

---

## v1.4 — Discovery phase (Vision Phase 2)

42. **Open-access citation scavenger** — given an anchor paper, autonomously map its citation tree via Semantic Scholar/Crossref, filter for open-access availability, download top-N highly cited relevant PDFs to `database_dir`, and queue them for review. Background process; progress streamed via `ProgressEvent`. Complexity is Hard (not Medium as the vision rated it) — requires relevance ranking beyond citation count, paywall filtering, and deduplication across API sources.
43. **Background PDF retrieval daemon** — persistent watcher that processes a "to-fetch" queue asynchronously, so adding a paper to the reading queue can trigger a background download without blocking the CLI.

---

## v2.0+ — Analysis phase (Vision Phase 4)

> These are correctly rated High complexity. Do not start before v1.4 is stable and real usage data exists.

44. **Qualitative thematic extraction** (Atlas.ti alternative) — instruct Docent to run thematic extraction across interview transcripts or field notes in Studio, tagging quotes by theme and linking them back to source text. Hermes persistent memory loop is the right substrate for this.
45. **R/Python data scaffolders** — generate test-driven R scripts or Python/pandas workflows for statistical experiments; output publication-ready charts directly into Studio workspace.

---
name: Docent master todo list
description: Comprehensive ordered todo list across all active tracks; update after each session; read when planning what to work on next
type: project
---

Last updated: 2026-05-15 (hardening sprint: §4 executor process-group kill, §9 error codes D001-D007, §10 confirmed done; #29 mendeley_mcp_command config-set, #32 utils/logging.py, #33 eval harness, #37 doctor auto-install all shipped)

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
14. ~~**Real-life tests #10–#19**~~ — DONE (all passed, see memory/tasks/done/studio_real_life_tests.md)

---

## AFTER v1.2.0 — completed hardening sprint

12. ~~**`docent.core.invoke` module**~~ — DONE 2026-05-13.
13. ~~**Next API routes → thin dev-only proxies**~~ — DONE 2026-05-13. Single `rewrites` rule in `next.config.ts`; fixed `tags` drop in `post_action`.
14. ~~**Move Rich rendering out of tool result models**~~ — DONE 2026-05-13. 15 `__rich_console__` methods removed.
15. ~~**File locking on reading queue writes**~~ — DONE 2026-05-13.
16. ~~**Schema-generated docs**~~ — DONE 2026-05-13. `tests/test_doc_flags.py` contract test.
17. ~~**§4 CLI robustness — subprocess process-group kill**~~ — DONE 2026-05-15. `Executor` rewritten with `Popen` + `CREATE_NEW_PROCESS_GROUP` on Windows; `_kill_tree()` sends `CTRL_BREAK_EVENT`. Pathlib audit: already clean. Binary preflight: negligible, skipped. 9 new tests.
18. ~~**§9 Error codes**~~ — DONE 2026-05-15. `src/docent/errors.py` — `DocentError` + D001-D007 hierarchy. `FeynmanNotFoundError`/`FeynmanBudgetExceededError`/`OcUnavailableError`/`OcBudgetExceededError`/`OcModelError` all subclass hierarchy. CLI `callback()` catches `DocentError` → `[red]Error:[/] [Dxxx] …` + logs to file. `OcModelError.http_code` replaces old `.code`. 13 new tests.
19. ~~**§10 Atomic-write verification**~~ — CONFIRMED already done. `reading_store.py` has `_atomic_write_json` (temp+rename) + `FileLock`. No action needed.

---

## Phase 1.5 — Remaining skill ports

17. ~~**`to-notebook` polish**~~ — DONE 2026-05-14. Fixed `docent research` → `docent studio` in all error messages (3 files); relaxed Feynman-output guard (no sources.json no longer fatal); 19 new NLM helper tests; 369 green.
18. ~~**`alpha-research` port**~~ — DONE 2026-05-14. `studio search-papers` + `studio get-paper` actions (alphaxiv-py SDK, async→sync wrapper); 398 tests green.
19. ~~**`scholarly-search` port**~~ — DONE 2026-05-14 (confirmed shipped: `studio scholarly-search` action, GS→Semantic Scholar→CrossRef fallback chain).
20. ~~**`literature-review` port**~~ — DONE 2026-05-14 (confirmed: `studio lit` has both feynman + docent backends; docent pipeline uses Tavily + scholarly + arXiv via `academic_search_parallel`).
21. ~~**Phase E: remaining Feynman workflows**~~ — DONE 2026-05-14. `compare`, `draft`, `replicate`, `audit` added to StudioTool (both feynman + docent backends); 91 tests green. `watch` deferred — scheduling concern, not a single-run generator action.

---

## Phase 2 — UI

22. ~~**Schema-driven forms**~~ — DONE 2026-05-30. Shipped as a **generic `/tools` runner page**, NOT a Studio-form rewrite (Studio's value — backend gating, guide files, dest routing, cost notices — is mostly non-schema-derivable; rewriting it would downgrade UX). New page lists every registered tool/action and auto-generates a form from `model_json_schema()`. Backend: `ui_routes/tools.py` (`GET /api/tools` catalogue + `POST /api/tools/invoke`). Frontend: `app/tools/page.tsx` + `_schema-form.tsx` (handles string/int/bool/enum/string[]/optional/json-fallback). Sidebar utility nav entry. **Bug found + fixed during live verify:** overlay actions (search/next/show — call `asyncio.run()` internally) failed with "asyncio.run() cannot be called from a running event loop" in the async handler → wrapped invoke in `asyncio.to_thread` (same pattern as `ui_routes/reading.py:119`). 7 backend tests (Win+WSL) + 12 vitest. Studio + Reading pages untouched. See decisions.md 2026-05-30.

---

## Remote access / HTTP transport

> **Context:** Docent currently uses stdio MCP transport only. This blocks mobile use cases (Claude mobile app doesn't support MCP) and shared-server deployments. The roadmap item below is the foundational piece that unlocks both.

44. **HTTP + SSE MCP transport** — add a `/mcp` HTTP endpoint alongside the existing stdio transport so Docent can run as a persistent network service. Enables: (a) shared team/lab Docent server, (b) mobile access once Claude mobile adds MCP support, (c) always-on research server without a laptop. Implementation: MCP spec already defines HTTP+SSE transport; FastAPI is already a dependency. Auth (API key or token) required before exposing to the network. File outputs land on the server filesystem — `to-local` and `to-notebook` write there, not the client machine. SSH tunnel (`ssh user@server docent serve`) works today with zero code changes as a stopgap.
23. **Live Telemetry pane** — consume `ProgressEvent` stream from generator actions via SSE/WebSocket.
24. **Artifact Viewer** — render Output Shapes as React components (one per shape type).
25. **Omnibox Mode 1** — NL → existing action ("summarize my queue" → `docent reading stats`). Small classifier + `all_tools()` registry.
26. **Omnibox Mode 2** (Phase 2.5) — on-the-fly tool generation + hot-load into registry. Security question to resolve first.

---

## Infrastructure / housekeeping

27. ~~**Pin `actions/setup-node` to SHA**~~ — DONE 2026-05-07. All 3 actions SHA-pinned (`checkout`, `setup-uv`, `setup-node`).
28. ~~**CI test + lint gap**~~ — FIXED 2026-05-14. pytest + ruff steps added to publish.yml before uv build; ruff>=0.9 added to dev deps.
29. ~~**`mendeley_mcp_command` config-set**~~ — DONE 2026-05-15. `shlex.split()` parses string→list; `write_setting(None)` deletes key; `config-show` displays it. 7 new tests.
30. **BibTeX export** — needs CrossRef-clean metadata. Deferred since Step 8.
31. **Semantic Scholar orphan identification** — `--identify-orphans` flag on `sync-status`. Deferred since Step 11.1.
32. ~~**`utils/logging.py`**~~ — DONE 2026-05-15. Rotating file handler (5 MB, 3 backups, UTF-8) always on; stderr mirror when `--verbose`. `get_logger(__name__)` available to all modules. Wired into `cli.py` `main()`. 8 new tests.
33. ~~**Eval harness**~~ — DONE 2026-05-15. `tests/golden/studio/` — 2 JSON fixtures (deep + lit Tavily path); `scorer.py` (0-1 score, 0.8 threshold); `@pytest.mark.eval` parametrized suite + 7 pure-function unit tests for `_append_references`/`_strip_references_section`. New fixtures = new tests automatically.
34. ~~**Breaking changes policy**~~ — DECIDED 2026-05-14. See `memory/project_breaking_changes_policy.md`. Semver with 1-MINOR deprecation window; external tools are WARN in doctor, not Docent MAJOR bumps.

---

## v1.3 — Ingestion phase (Vision Phase 1)

> **Coexistence decision CONFIRMED 2026-05-30:** coexist model — `sync_source = "mendeley" | "zotero"` toggle; both bridges maintained in parallel. See `decisions.md` 2026-05-30.

35. ~~**Plugin developer docs**~~ — DONE. `docs/plugin-guide.md` already existed and was comprehensive. Fixed §7 (`ProgressShape` → `ProgressEvent` with field table), §9 (bare imports → relative imports), added §13 (how to publish: GitHub one-liner + PyPI `docent-<name>` pattern + `install()` helper).
35a. **Mendeley client: drop MCP subprocess, use direct httpx REST** — replace `mendeley_client.py` MCP subprocess calls with direct `httpx` calls to `api.mendeley.com`. Removes ~5s cold-start, removes subprocess fragility. Same OAuth token; no change to callers (`list_folders`, `list_documents` signatures stay identical). Do before Zotero bridge so the `ReferenceManagerClient` protocol is built on a clean foundation. **Pre-Zotero prerequisite.**
36. **Zotero SQLite bridge** — monitor `zotero.sqlite` for new entries; auto-insert into reading queue with status "queued". `ReferenceManagerClient` protocol; use `pyzotero` (decided over `zotero-mcp` — direct REST, no subprocess, stable library). See `project_zotero_integration.md`. Gate on #35a landing first.
37. ~~**`docent doctor` auto-install**~~ — DONE 2026-05-15. `_collect_install_offers()` + `_AUTO_INSTALL` dict; feynman + mendeley-mcp only (Zotero held). Per-tool confirmation; resolves runner via `shutil.which` before attempting. 5 new tests.
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

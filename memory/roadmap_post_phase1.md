---
name: Docent roadmap (post Phase 1)
description: Forward-looking plan after Steps 1-13 land. Skill porting, extensibility, Output Shapes landing, then Phase 2 UI. Read when picking up the next big arc, or when "what comes after the build checklist" is the question.
type: project
---

Created 2026-04-25 after user asked "what's the next big thing once the build checklist is up?" Captures intent before momentum is lost. Living doc — update as decisions land.

## Phase 1 (complete as of 2026-05-07)

Steps 1–13 shipped. See `build_progress.md` for the full checklist and per-step detail.

## Phase 1.5 — Skill ports + Output Shapes lands

After Step 11 (not after Step 13). Three threads run in this order:

### A. Output Shapes vocabulary lands
**DONE 2026-05-07.** `src/docent/core/shapes.py` + `ui/renderers.py` + `ui/theme.py` shipped. Six leaf types: `MarkdownShape`, `DataTableShape`, `MetricShape`, `LinkShape`, `MessageShape`, `ErrorShape`. Reading tool results all implement `to_shapes()`. See `archive/output-shapes-shipped-2026-05.md` and `decisions.md` Phase 1.5-A entry for full detail.

### B. Skill ports (research/grad-school subset)
Priority-ordered. Each port is a Tool subclass following the contract paper-pipeline established. Stop porting if a port reveals a contract gap; fix the contract, then continue.

1. **`research-to-notebook`** — *canonical complex tool.* Composes `markdown` + `data_table` + `link` + `progress`. The forcing function for Output Shapes; also exercises sub-agent fan-out (deferred harness principle from `harness_principles.md`).
2. **`alpha-research`** — paper search/read via alphaXiv. Pairs with paper-pipeline (search → add to queue).
3. **`scholarly-search`** — Google Scholar wrapper with Semantic Scholar / CrossRef fallback. Same shape as alpha-research; cheap to port once the first is done.
4. **`literature-review`** — multi-source synthesis. Consumes alpha-research + scholarly-search outputs.
5. **`peer-review`** / **`paper-writing`** — writing-side companions. Useful but lower urgency.
6. **`deep-research`** — long-running source investigation. Streams progress (Step 10 contract).
7. **Domain skills:** `equation-explainer`, `coastal-data-discovery` — directly relevant to user's grad-school work. Port if/when actively used.
8. **Utility:** `eli5`, `session-log`, `source-comparison`, `watch` — small, optional.

**Skipped explicitly:** gstack-family skills (build/deploy/QA/browser — outside Docent's lane), `claude-council` and `autoplan` (meta-orchestration, not workflow tools), compute skills (heavy infra).

### C. Plumbing the critique flagged
Reviewer critique on `Interesting stuff.txt` (Phase 2 doc) named two items not yet on the build list:
- **AGENTS.md** — three rules max, not a document. Keeps architecture invariants visible across long sessions where context compaction can drop them. Cost: 30 min. Lands alongside Output Shapes work.
- **Tests** — repo has no `tests/` directory yet. Eval harness is deferred to first non-trivial LLM call (`harness_principles.md`); but contract-shape unit tests for the Tool ABC + registry + dispatcher should land before Phase 2 to prevent regressions while the surface grows.

## Phase 2 — Omni-Channel UI

Per `Interesting stuff.txt`: CLI stays the source of truth; UI is a "visual skin" over the same Python engine. Triggered after Phase 1.5 stabilizes (Output Shapes shipped, ≥2 skills ported, plugins discovery + MCP working).

**Architectural items the vision doc didn't address (per critique):**
- **FastAPI layer.** Decide before frontend work: single-process (UI subcommand starts a server) vs. always-on daemon. Process management, port binding, CORS, request/response serialization. Shapes the JSON wire format. Land first.
- **Schema-Driven UI** as designed: backend exposes Pydantic `input_schema` as JSON Schema; React generates forms dynamically. No hard-coded per-tool components.
- **Live Telemetry pane** — consumes `ProgressEvent` stream from Step 10. The reason event streaming was generator-based (data-shaped, not callback) was to make this easy: same generator drives CLI Rich progress today and SSE/WebSocket to the frontend tomorrow.
- **Artifact Viewer** — renders Output Shapes as React components (one per shape type).

**Omnibox** (from vision doc):
- **Mode 1 — NL → existing action** ("summarize my queue" → `docent reading stats`). Build first; achievable today with a small classifier + the existing `all_tools()` registry. Ship as part of Phase 2 launch.
- **Mode 2 — On-the-fly tool generation.** *Deferred / scoped down.* Per critique: hot-loading generated Python into a running registry is non-trivial; generated code quality is variable; auto-executing LLM-written files in `~/.docent/plugins/` raises a security question worth deciding explicitly (probably fine for personal use, but explicit). Treat as Phase 2.5 experiment, not a core launch feature.

## Phase 2 deferred / explicit non-goals at launch
- Omnibox tool-generation (above).
- Multi-user / auth — Docent is a single-user personal tool.
- Sharing / sync between machines — out of scope until the user actually has two machines they want synced.

## Post-v1.2.0 Hardening Sprint

Two independent model reviews (GLM-5.1 and Kimi-2.6) converged on the same three items unprompted. That's the signal. Do these before Phase 2 UI work.

**1. UI server direct invocation** *(highest priority — has a real user-visible bug)*
`ui_server.py` shells out to the CLI subprocess for every mutation. This causes:
- Stale titles in the web UI (reads raw `queue.json`, doesn't apply Mendeley overlay — CLI shows fresh data, web UI shows old titles)
- ~100ms process spawn overhead per action
- Brittle stdout/ANSI parsing for error detection

Fix: `invoke_action()` already exists in `mcp_server.py`. Wire `ui_server.py` endpoints to call it directly instead of spawning subprocesses. The function is already there — this is plumbing, not design.

**2. Reading monolith split** *(high — compounds with every new action)*
`bundled_plugins/reading/__init__.py` is ~1,215 lines mixing result models, action methods, Mendeley sync, reordering logic, and renderers. Target structure:
- `models.py` — QueueEntry + all input/output schemas
- `sync.py` — `_sync_from_mendeley_run` generator + helpers
- `ordering.py` — `_reorder_move_to`, move_up/down/to
- `renderers.py` — `to_shapes()` + `__rich_console__` for result classes
- `tool.py` — ReadingQueue action methods only (~400 lines)
- `__init__.py` — re-exports only (~20 lines)

**3. Research tool DRY-up** *(high — ~400 lines of duplication)*
`deep()`, `lit()`, `review()` in `research_to_notebook/__init__.py` are ~150 lines each with only 3–4 meaningful differences. Extract a shared `_run_pipeline()` helper. Each action collapses to ~15 lines.

---

## Sequencing summary

```
[done]    Steps 1-10.5
[done]    Step 11  (paper sync + minimal MCP)
[done]    Step 12  (~/.docent/plugins/ discovery + reading as bundled plugin)
[done]    Step 13  (full MCP adapter — shipped 2026-05-07)
[done]    Reading page frontend (Next.js — built ahead of plan, shipped 2026-05-06)
[done]    Output Shapes vocabulary + ui/renderers.py     }  Phase 1.5
[done]    Tests + AGENTS.md                             }
[done]    FastAPI layer + bundled UI (v1.1.0, 2026-05-08 — shipped early, not Phase 2)
[done]    Research tool (v1.2.0 pending — 2 bugs to fix)  }  Phase 1.5 cont.
[next]    Hardening sprint (UI server, reading split,    }
          research DRY-up) — post-v1.2.0                }
[then]    UI polish + schema-driven forms                }  Phase 2
          Omnibox (NL → action mode only)                }  (base app exists)
```

## v1.2.0 scope (NOW — all ship before v1.2.0 tag)

**Policy (2026-05-12):** v1.2.0 is an omnibus release. Hardening sprint + v1.3 planning + medium architectural debt ALL ship in v1.2.0. These were previously post-v1.2.0 items but are now required before the v1.2.0 tag.

### Hardening Sprint (was post-v1.2.0)
- **UI server direct invocation** — wire `ui_server.py` to `invoke_action()` instead of spawning CLI subprocesses
- **Reading monolith split** — split `bundled_plugins/reading/__init__.py` (~1,215 lines) into modules
- **Research tool DRY-up** — extract shared `_run_pipeline()` core from deep/lit/review (~400 lines duplication)

### Medium architectural debt (was post-v1.2.0 / before v1.3.0)
- **MCP single-action tools** — `mcp_server.py` doesn't iterate single-action plugins
- **`edit --status` bypass** — route through `_set_status` lifecycle

### v1.3 planning (was v1.3 scope)
**`docent doctor` / onboarding command** — Check tooling (feynman, mendeley-mcp / zotero-mcp, PATH), auth status, and guide user through setup interactively. Docent should bundle MCP installs rather than leaving them to the user. Also: warn when feynman is installed via binary instead of npm (binary path causes silent update confusion — recommend npm install). **Storage warning:** Feynman's config/cache dir (`~/.feynman`) can grow to ~2 GB — warn users during onboarding about disk space requirements before installing feynman.

**Hermes stream view** — Add live stream output to `hermes_delegate.py` matching OpenCode's stream UX. Currently a silent subprocess.

## v1.4 scope

**Obsidian integration** — See `project_obsidian_integration.md`. `--output vault` for Studio; literature note on `reading done`; Dataview-compatible frontmatter. Config key: `obsidian_vault`.

## UI tweaks (reading plugin — post-v1.2.0)
- Drag-and-drop sidebar tab reordering; Dashboard tab pinned
- Move reading stats (queued count, database count, done count) off top panel → under "Local Reading Queue · N Entries" on the reading page

## Open questions / policy gaps
- **Breaking changes policy** — how to handle breaking changes in external tooling (feynman, MCP servers) and docent itself across versions? No decision yet. Needs a policy before any v2.x work.
- **Plugin builder spec** — document the plugin contract for third-party developers before the API drifts further. User wants it accessible to non-technical users; AI-powered plugin builder mentioned as a stretch goal.

## Parked
- **Calendar plugin** — class/exam schedule, sync to external calendars. Out of scope for now.
- **Omnibox** — flagged; NL → existing action (Mode 1) is in Phase 2 plan. On-the-fly tool generation (Mode 2) is already deferred above.

---

## When this file is wrong

This is a snapshot of intent at 2026-04-25. Reality will diverge. When it does, update the relevant section here — don't keep this in sync via memory in another file. If a phase is finished, prune it; if priorities flip, reorder. Don't let it rot into a fiction.

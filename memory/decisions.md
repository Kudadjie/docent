---
name: Docent decisions log
description: Append-only architectural-decision record; read when asking "why did we choose X" or when a new call needs its own entry
type: project
---

Append-only. Newest at the bottom. One entry per architectural call where alternatives were considered. Format:

```
## YYYY-MM-DD — Short title
**Context:** one or two lines on the situation
**Decision:** the chosen path
**Why:** the reasoning
**Alternatives rejected:** what we didn't do and why
**Status:** Active | Superseded by <link> | Reverted
```

**Archived:**
- Steps 1–6 foundation (2026-04-23) → `archive/decisions-2026-04-foundation.md`
- Steps 7a–9 paper-build + contract conventions (2026-04-24/25) → `archive/decisions-2026-04-paper-build.md`
- Steps 10–11 progress streaming, pytest, PaperQueueStore, Mendeley pivot, sync actions, cache, schema trim (2026-04-25 to 2026-05-02) → `archive/decisions-2026-05-steps10-11.md`

Live entries below cover the most recent work; older active decisions are still authoritative in the archives — read those when revisiting why the contract or paper has its current shape.

---

## 2026-05-06 — Step 11.R: reading tool rewrite (`paper` → `reading`)

**Context:** The tool had been called `paper-pipeline` in the gstack skill and `paper` in Docent's registry. After the Mendeley pivot, the remaining actions (queue management, Mendeley sync, deadline tracking) are a reading workflow tool, not a paper metadata pipeline. The name `paper` was a carry-over from when the tool managed PDF ingestion. With ingestion fully delegated to Mendeley, the name was wrong. Separately, several schema fields (`priority: str`, `course: str | None`) had accumulated meaning that deserved richer modeling.
**Decision:**
1. **Rename**: `paper.py` → `reading.py`, `paper_store.py` → `reading_store.py`, `PaperPipeline` → `ReadingQueue`, registry name `"paper"` → `"reading"`, config section `[paper]` → `[reading]`, `PaperSettings` → `ReadingSettings`, `Settings.paper` → `Settings.reading`.
2. **Schema changes**: `priority: str` → `order: int` (1-based position in reading order); `course: str | None` → `category: str` (one of `paper|book|book_chapter`) + `course_name: str | None`; `+deadline: str | None`.
3. **Actions removed**: `migrate-to-mendeley-truth` (one-shot, done), `sync-pull` (removed).
4. **Actions added**: `move-up`, `move-down`, `move-to` (order management); `set-deadline` (explicit deadline action rather than burying in `edit`).
5. **`ready-to-read` renamed `start`** — verb is clearer; transitions status to `reading` + stamps `started` timestamp.
6. **New `reading_notify.py`** — deadline check at CLI startup, daily dedup via a timestamp file, wired into `cli.py` main callback.
7. **Config migration required**: user runs `docent reading config-set database_dir <path>` once; old `[paper]` section is silently ignored.
**Why:** (Rename now, not later) the wrong name would have been carried into Step 12 (plugin discovery) and Step 13 (MCP), embedding `paper` in external-facing surface like MCP tool names. Better to rename before those steps lock the surface. (order: int over priority: str) the queue is ordered; a bare priority string like `"high"` doesn't capture position. Integer order is sortable, composable with move-up/down/to, and unambiguous. (category + course_name split) `course` was overloaded — sometimes a course code, sometimes "personal" or "thesis". Two fields with defined semantics are cleaner. (deadline as explicit action) deadline is a first-class property that needs its own UX; burying it in a generic `edit` obscures it. (notify at startup) passive, non-blocking; fires once per day at most; user sees upcoming deadlines without having to remember to run `docent reading stats`.
**Alternatives rejected:** Keep `paper` as the name for backwards compat — no external users exist yet; cost of name-debt is higher than cost of migration. Use `priority` enum (low/medium/high) instead of integer order — enum doesn't encode relative position; two "high" entries have undefined order. Use a separate `docent notify` command — adds a new entry point for functionality that only matters in the reading context; startup hook is simpler and automatic.
**Status:** Active. Suite 107 → 93 green (−14 deleted tests, +1 new). User completed config migration.

---

## 2026-05-07 — Step 12: `~/.docent/plugins/` external discovery + bundled_plugins

**Context:** Step 7a defined the registry + `@register_tool` decorator. Tools were discovered by walking `src/docent/tools/`. By Step 11.R the reading tool was the only real tool there, and it had grown large enough to warrant its own package (multiple modules: `reading.py`, `reading_store.py`, `mendeley_client.py`, etc.). Step 12 was designed to (a) allow users to drop plugin files into `~/.docent/plugins/` without editing the package, and (b) move the reading tool out of `tools/` into a structured location that supports multi-module plugins.
**Decision:**
1. **New `src/docent/core/plugin_loader.py`** with `load_plugins()` and `run_startup_hooks()`. Loads from two sources in order: `src/docent/bundled_plugins/` (first-party, packaged), then `~/.docent/plugins/` (user-installed, external). Supports flat files (single `.py`) and packages (directory with `__init__.py`).
2. **`on_startup` lifecycle hook** — if a plugin module defines `on_startup(context)`, `run_startup_hooks()` calls it after all plugins load. Used by the reading tool to fire deadline notifications.
3. **Reading tool migrated to `src/docent/bundled_plugins/reading/`** — multi-module package (`reading.py`, `reading_store.py`, `mendeley_client.py`, `mendeley_cache.py`, `reading_notify.py`). `__init__.py` re-exports the `ReadingQueue` class.
4. **`src/docent/tools/` becomes a pass-through** — `__init__.py` kept for future single-file tools dropped there by the framework, but no real tools live there anymore.
5. **`on_startup` wired for the reading tool**: `reading_notify.check_deadlines(context)` runs once at startup.
**Why:** (bundled_plugins separate from tools/) bundled tools are multi-module packages that need their own directory structure; a flat `tools/` directory can't host them without a naming mess. (External discovery via `~/.docent/plugins/`) this was planned since Step 7a ("Later, add a second discovery path"); doing it at Step 12 before the MCP adapter locks the registry surface. (Lifecycle hook over startup action) deadline checking doesn't belong as a user-invoked command; it belongs to the startup path where it's passive. (Load bundled before external) first-party tools take precedence; name collisions with external plugins produce a clear warning and skip (v1.2.0: changed from raise to warn+skip), not silent replacement.
**Alternatives rejected:** Keep reading tool flat in `tools/reading.py` and extract submodules there — naming conflicts with future single-file tools in the same directory; the multi-module package model is cleaner. Build `~/.docent/plugins/` discovery as a separate step — it was already planned and trivially cheap to wire at the same time as the bundled loader.
**Status:** Active. 9 new tests; suite 100 green.

---

## 2026-05-07 — Step 13: full MCP adapter (`docent serve`)

**Context:** Step 11.4 added an in-process MCP client (Docent calling Mendeley's MCP server). Step 13 is the inverse: Docent as an MCP server, so Claude Code and other MCP hosts can call Docent's reading actions as tools. The registry already holds typed schemas for every action; the MCP adapter's job is to expose them without duplicating that structure.
**Decision:**
1. **New `src/docent/mcp_server.py`** (~130 LOC). `build_mcp_tools()` introspects the registry → one `types.Tool` per (tool, action) pair, named `{tool}__{action}` (hyphens → underscores, double-underscore separator). `invoke_action()` dispatches sync and generator actions, drains generators to completion, serializes Pydantic results as JSON text. `run_server()` wires `list_tools` + `call_tool` handlers into a stdio MCP server.
2. **`docent serve` command** in `cli.py` — lazy-imports `mcp_server` (keeps `docent --version` and all other commands free of the `mcp` SDK's startup cost). `mcp >= 1.0, < 2` already in deps from Step 11.4.
3. **`.mcp.json` template** at repo root — shows the `{"mcpServers": {"docent": {"command": "docent", "args": ["serve"]}}}` stanza users copy into their Claude Code config.
4. **Generator actions fully supported** — `invoke_action()` detects generators, drains them (discarding `ProgressEvent` records), and returns the final result. The MCP protocol has no streaming concept at the tool-call level; progress events are irrelevant from an MCP caller's perspective.
5. **Tool naming convention**: `reading__next`, `reading__show`, `reading__sync_from_mendeley`, etc. Double-underscore unambiguously separates tool and action (no tool or action name contains `__`); underscores replace hyphens to satisfy MCP tool name constraints.
**Why:** (Introspect registry over handwritten tool list) the registry already has everything; duplication is bug surface. (Separate `mcp_server.py` + lazy import) adding `import mcp` at module level would slow every invocation including `docent --version`. (Drain generators for MCP callers) the MCP protocol's `call_tool` is synchronous from the host's perspective; streaming would require SSE or WebSocket transport which the `mcp` SDK doesn't support in stdio mode. (`.mcp.json` template at root) Claude Code looks for it there by convention; a template with the right shape saves the user a lookup.
**Alternatives rejected:** Expose only single-action tools over MCP, skip multi-action — would hide most of Docent's surface. Use `{tool}/{action}` naming — slashes are not valid in MCP tool names. Stream ProgressEvents as intermediate tool results — not supported by the stdio MCP transport. Build the MCP adapter as a separate package — no external users yet; keeping it in-package avoids a deployment split.
**Status:** Active. 10 new tests; suite 100 → 110 green. Smoke-tested: `docent serve` in `--help`; tool list returns reading actions.

---

## 2026-05-07 — Phase 1.5-A: Output Shapes vocabulary + `ui/renderers.py`

**Context:** Every result type (`MutationResult`, `SearchResult`, `SyncStatusResult`, etc.) had its own ad-hoc `__rich_console__` implementation. Two problems: (1) the CLI, future web UI, and MCP all needed result data, but there was no typed contract for what shape the data came in — a web renderer would have to parse Rich markup strings; (2) `__rich_console__` on result models is a layering violation (tool result knows about UI library). Output Shapes defines a typed intermediate representation between "tool returned this" and "UI rendered this."
**Decision:**
1. **`src/docent/core/shapes.py`** — `OutputShape` base + six leaf types: `MarkdownShape`, `DataTableShape`, `MetricShape`, `LinkShape`, `MessageShape`, `ErrorShape`. Each is a plain Pydantic model with no Rich imports.
2. **`to_shapes() -> list[OutputShape]`** — result models implement this instead of (or alongside) `__rich_console__`. Content strings are plain text; no markup. The renderer is responsible for styling.
3. **`src/docent/ui/renderers.py`** — `render_shapes(shapes, console)` dispatches per shape type to typed Rich render functions. `cli.py` calls this after invoking any action. One central place for all visual styling decisions.
4. **`ui/theme.py`** — centralized color tokens (`ACCENT`, `DIM`, `SUCCESS`, `WARNING`, `ERROR`) referenced by `renderers.py`. Changing the whole CLI theme is a one-file change.
5. **Retrofitted `reading` tool results** — all reading result types implement `to_shapes()`. `__rich_console__` retained as a compatibility shim on result models that need it, but deprecated in favor of shapes.
**Why:** (Shapes over ad-hoc __rich_console__) shapes are serializable to JSON (for the future web UI) and testable without a Rich console. The MCP adapter already serializes results as JSON; without shapes, the web UI would have to parse Rich markup. (Plain text content in shapes) styling is the renderer's job, not the data model's. (renderers.py as the single render registry) if we ever swap Rich for Textual or a web renderer, there's one file to change. (Retrofit reading tool now) with two consumers (CLI + MCP) already live, deferring the retrofit means the shape contract diverges before it has any traction.
**Alternatives rejected:** Keep `__rich_console__` on result models and add a separate `to_json()` method — two parallel serialization paths that drift; any new field added to the model needs to be added in both. Use dataclasses instead of Pydantic for shapes — lose free JSON serialization and schema introspection that the future web UI will use. Build shapes as an abstract Shape protocol rather than concrete leaf types — too much indirection for the concrete use case.
**Status:** Active. Suite unaffected (shapes are tested through reading tool result tests).

---

## 2026-05-07 — Phase 1.5-B: contract tests + AGENTS.md

**Context:** With the registry and dispatcher being the load-bearing seam for CLI, MCP, and future web UI, a regression in the Tool ABC or dispatcher would silently break all three. The existing test suite covered per-action behavior (reading queue operations) but not the framework contract itself. AGENTS.md was flagged in Phase 1.5-C's roadmap entry ("AGENTS.md — three rules max, not a document") as a cheap architectural invariant record.
**Decision:**
1. **`tests/test_tool_abc.py`** (13 tests) — Tool ABC invariants: `run()` raises `NotImplementedError` by default, `collect_actions()` returns decorated methods only, `@register_tool` rejects reserved names (`list`, `info`, `config`, `version`), multi-action tool with no actions raises at registration. Note: v1.2.0 changed double-registration from raise to warn+skip (see registry.py guard).
2. **`tests/test_dispatcher.py`** (6 tests) — `invoke_action()` paths: sync action returns result, generator action drains and returns final result, unknown action raises, action raises exception, input validation failure.
3. **`AGENTS.md` at repo root** — three-section behavioral contract: (a) calling convention for reading actions (identifier formats, required fields, action semantics); (b) reading queue invariants (order is 1-based, no gaps; mendeley_id or doi required; category is one of paper/book/book_chapter); (c) destructive action rules (queue-clear requires `--yes`, dry-run is always safe).
**Why:** (Contract tests separate from reading tests) if a future tool breaks the ABC, the reading tests won't catch it — the contract tests will. (AGENTS.md at repo root) Claude Code reads it on every session start; three sections is the right density. (6 dispatcher tests) covers the paths the MCP adapter actually exercises; more is premature without more callers.
**Alternatives rejected:** Add contract assertions inside `@register_tool` only — catches registration-time errors but not structural invariants. Put AGENTS.md content in CLAUDE.md — CLAUDE.md is Claude Code config; AGENTS.md is for any LLM caller. Write AGENTS.md as full documentation — the "three rules max" constraint was explicit; a long doc gets ignored.
**Status:** Active. Suite 141 → 160 green.

# Docent — AI Working Context

**Read this first.** This document is the single entry point for any AI model working on
Docent. It tells you what the project is, how it is structured, where every kind of
information lives, what is currently broken, and what the rules are. Follow the links
to go deeper. Do not skip ahead to code before reading this.

---

## 1. What is Docent?

Docent is a personal Python CLI "control center" for graduate-school workflows, built by
a grad student (the repository owner) for their own daily research and reading management.

It ships as a single PyPI package `docent-cli` that bundles three interfaces over the same
Python engine:

| Interface | How to start | Port / protocol |
|-----------|-------------|-----------------|
| **CLI** | `docent <tool> <action> [flags]` | Terminal |
| **Web UI** | `docent ui` | `http://localhost:7432` |
| **MCP server** | `docent serve` | stdio (MCP protocol) |

Current published version: **v1.1.0** (2026-05-08). Next: **v1.2.0** (Tavily Research API + pipeline fixes + preflight + refiner stage — 280 tests green, e2e verified). See [`memory/build_progress.md`](memory/build_progress.md) for changelog.

---

## 2. Where to find things — master navigation guide

Use this table before reading any code. Every category of information has one canonical
location; do not search ad-hoc before consulting this.

### Project memory (decisions, progress, history, rules)

| What you need | File to read |
|---------------|-------------|
| Where to start — memory index | [`memory/MEMORY.md`](memory/MEMORY.md) |
| What has shipped, step by step | [`memory/build_progress.md`](memory/build_progress.md) |
| Why architectural choices were made | [`memory/decisions.md`](memory/decisions.md) + [`memory/archive/`](memory/archive/) |
| Bugs we have stepped on before | [`memory/gotchas.md`](memory/gotchas.md) |
| All current todos, ordered | [`memory/project_todos.md`](memory/project_todos.md) |
| v1.2.0 release bugs (immediate blockers) | [`memory/project_research_test_blockers.md`](memory/project_research_test_blockers.md) |
| Codex review debt (items 6-12 open) | [`memory/project_codex_review_blockers.md`](memory/project_codex_review_blockers.md) |
| Phase 2 UI + skill port roadmap | [`memory/roadmap_post_phase1.md`](memory/roadmap_post_phase1.md) |
| Release history + how to publish | [`memory/release_plan.md`](memory/release_plan.md) |
| Research tool port plan + architecture | [`memory/project_feynman_port.md`](memory/project_feynman_port.md) |
| Landmines (Rich, Windows, Pydantic v2…) | [`memory/gotchas.md`](memory/gotchas.md) |

### Source code

| What you need | File to read |
|---------------|-------------|
| Full settings schema (all config keys, env vars) | [`src/docent/config/settings.py`](src/docent/config/settings.py) |
| Tool ABC + `@action` decorator | [`src/docent/core/tool.py`](src/docent/core/tool.py) |
| Tool registry (`register_tool`, `all_tools`) | [`src/docent/core/registry.py`](src/docent/core/registry.py) |
| Plugin loader (bundled + `~/.docent/plugins/`) | [`src/docent/core/plugin_loader.py`](src/docent/core/plugin_loader.py) |
| CLI entry point (Typer app, dispatch, progress) | [`src/docent/cli.py`](src/docent/cli.py) |
| MCP server + `invoke_action()` | [`src/docent/mcp_server.py`](src/docent/mcp_server.py) |
| FastAPI backend (web UI endpoints) | [`src/docent/ui_server.py`](src/docent/ui_server.py) |
| Reading queue tool (main logic) | [`src/docent/bundled_plugins/reading/__init__.py`](src/docent/bundled_plugins/reading/__init__.py) |
| Reading queue persistence | [`src/docent/bundled_plugins/reading/reading_store.py`](src/docent/bundled_plugins/reading/reading_store.py) |
| Mendeley MCP client (sync facade) | [`src/docent/bundled_plugins/reading/mendeley_client.py`](src/docent/bundled_plugins/reading/mendeley_client.py) |
| Mendeley read-through cache | [`src/docent/bundled_plugins/reading/mendeley_cache.py`](src/docent/bundled_plugins/reading/mendeley_cache.py) |
| Research tool (deep/lit/review/usage) | [`src/docent/bundled_plugins/research_to_notebook/__init__.py`](src/docent/bundled_plugins/research_to_notebook/__init__.py) |
| Research 6-stage pipeline | [`src/docent/bundled_plugins/research_to_notebook/pipeline.py`](src/docent/bundled_plugins/research_to_notebook/pipeline.py) |
| Web/paper search helpers | [`src/docent/bundled_plugins/research_to_notebook/search.py`](src/docent/bundled_plugins/research_to_notebook/search.py) |
| OpenCode REST client | [`src/docent/bundled_plugins/research_to_notebook/oc_client.py`](src/docent/bundled_plugins/research_to_notebook/oc_client.py) |
| File path helpers (data_dir, cache_dir) | [`src/docent/utils/paths.py`](src/docent/utils/paths.py) |
| Output Shape types (MarkdownShape, etc.) | [`src/docent/core/shapes.py`](src/docent/core/shapes.py) |
| ProgressEvent (streaming actions) | [`src/docent/core/events.py`](src/docent/core/events.py) |
| Context (settings, llm, executor) | [`src/docent/core/context.py`](src/docent/core/context.py) |
| LLM client (litellm wrapper) | [`src/docent/llm/client.py`](src/docent/llm/client.py) |

### Documentation

| What you need | File to read |
|---------------|-------------|
| CLI reference (all commands + flags) | [`docs/cli.md`](docs/cli.md) |
| Reading tool deep-dive | [`docs/reading.md`](docs/reading.md) |
| Reading tool spec | [`docs/reading_spec.md`](docs/reading_spec.md) |
| MCP calling contract + invariants | [`AGENTS.md`](AGENTS.md) |
| User-facing overview + quick-start | [`README.md`](README.md) |
| Package metadata + dependencies | [`pyproject.toml`](pyproject.toml) |

### Tests

| What you need | File to read |
|---------------|-------------|
| Test suite entry point | `tests/` — run with `uv run pytest` |
| conftest + `seed_queue_entry` fixture | `tests/conftest.py` |
| Specific area tests | `tests/test_<area>.py` (e.g. `test_queue.py`, `test_sync_status.py`) |

---

## 3. Architecture overview

### The Tool contract — read this before touching any plugin

Every capability is a `Tool` subclass in [`src/docent/core/tool.py`](src/docent/core/tool.py):

```python
@register_tool
class MyTool(Tool):
    name = "mytool"
    description = "One-line description"

    @action(description="...", input_schema=MyInputs)
    def my_action(self, inputs: MyInputs, context: Context):
        ...  # return a Pydantic BaseModel, or yield ProgressEvents then return
```

**Two patterns — never mix them:**
- **Multi-action** (most tools): decorate methods with `@action`. Each becomes a CLI command,
  MCP tool, and FastAPI endpoint automatically.
- **Single-action**: set `cls.input_schema` and override `run()`. Rare.

**MCP tool name:** `{tool}__{action}` with hyphens replaced by underscores.
Examples: `reading__sync_from_mendeley`, `research__deep`, `reading__move_to`.

**Action return types:**
- Return a Pydantic `BaseModel` → serialized as JSON everywhere
- `yield ProgressEvent(phase, message, current, total)` zero or more times, then `return result`
  → CLI shows a Rich progress bar; MCP server collects the events as prefix lines and appends
  the final JSON result. Always parse the **last JSON block** from MCP output.

### How a call flows through the system

```
User (CLI)          User (Browser)        AI model (MCP)
     |                     |                     |
  cli.py              ui_server.py         mcp_server.py
  Typer app           FastAPI /api/*        stdio MCP server
     |                     |                     |
     +-------> invoke_action(tool, action, inputs) <-------+
                         |
                  registry.all_tools()
                         |
                  tool_instance.method(inputs, context)
                         |
                  returns Pydantic result
```

> **Known bug:** `ui_server.py` does NOT call `invoke_action()` yet — it spawns a `docent`
> subprocess instead. This causes stale titles in the UI. Fix is the #1 post-v1.2.0 item.
> See [`memory/project_todos.md`](memory/project_todos.md) item 4.

### Plugin loading order (what gets registered and when)

1. `cli.py` calls `discover_tools()` → scans `src/docent/tools/` for built-in tool files
2. `cli.py` calls `load_plugins()` →
   - scans `src/docent/bundled_plugins/` (reading, research_to_notebook)
   - scans `~/.docent/plugins/` (user-installed)
3. Any `on_startup(context)` function in a plugin is called after Context is created

Files starting with `_` are skipped by both scanners.

### Configuration system

Config file: `~/.docent/config.toml`. All keys defined in
[`src/docent/config/settings.py`](src/docent/config/settings.py) — read that file for the
authoritative list. Key sections:

```toml
[reading]
database_dir = "/path/to/Paper Database"   # also the Mendeley watch folder
queue_collection = "Docent-Queue"          # Mendeley collection name

[research]
output_dir = "~/Documents/Docent/research"
feynman_budget_usd = 2.00
oc_model_planner = "glm-5.1"
# ... more model routing keys
```

All settings are env-overridable: `DOCENT_<KEY>` top-level, `DOCENT_READING__<KEY>` nested
(double underscore). The env prefix is `DOCENT_` — so `ANTHROPIC_API_KEY` does NOT work;
use `DOCENT_ANTHROPIC_API_KEY`. `LLMClient` bridges to the unscoped name for litellm.

---

## 4. Reading tool in depth

**Source:** [`src/docent/bundled_plugins/reading/__init__.py`](src/docent/bundled_plugins/reading/__init__.py)

Mendeley is the **source of truth for paper metadata**. The queue stores only identity and
workflow state. Title, authors, year, doi are overlaid at read time from a file-backed cache.

**Queue entry fields** (defined in `QueueEntry` in `reading/__init__.py`):

| Field | Editable | Notes |
|-------|----------|-------|
| `id` | No | Slug, auto-generated |
| `mendeley_id` | No | Set by sync-from-mendeley |
| `doi` | No | Set by sync-from-mendeley |
| `type` | Yes (`--type`) | paper / book / book_chapter |
| `status` | Via actions | queued → reading → done |
| `order` | Via move-* | 1-based queue position |
| `priority` | Yes | low / medium / high |
| `category` | Yes | course / thesis / personal |
| `course_name` | Yes | Free text |
| `deadline` | Yes (set-deadline) | ISO date or null |
| `notes` | Yes | Free text |
| `started` | Auto | Stamped on `start`; never overwritten |
| `finished` | Auto | Stamped on `done`; never overwritten |

**Persistence:** `~/.docent/data/reading/queue.json` + `queue-index.json`.
The store is in [`reading_store.py`](src/docent/bundled_plugins/reading/reading_store.py).

**Mendeley integration flow:**
1. User adds a paper to the "Docent-Queue" collection in Mendeley
2. `docent reading sync-from-mendeley` calls `mendeley_client.list_documents(folder_id)` and
   upserts entries into the queue
3. `next` / `show` / `search` overlay fresh Mendeley metadata via `mendeley_cache.py`
   (file-backed, TTL 300s for collection docs, 24h for folder IDs)

**All actions:**

| Action | Input schema | Notes |
|--------|-------------|-------|
| `add` | `AddInputs` | Guidance only — does not mutate queue |
| `show` | `ShowInputs` | Table of all entries |
| `next` | `NextInputs` | First by order, filtered by course_name |
| `search` | `SearchInputs` | Keyword search over title/authors/notes |
| `start` | `StartInputs` | queued → reading, stamps `started` |
| `done` | `DoneInputs` | reading → done, stamps `finished` |
| `remove` | `RemoveInputs` | Deletes entry (irreversible) |
| `edit` | `EditInputs` | Updates mutable fields |
| `set-deadline` | `SetDeadlineInputs` | Sets or clears deadline |
| `move-up` | `MoveUpInputs` | Move one position up |
| `move-down` | `MoveDownInputs` | Move one position down |
| `move-to` | `MoveToInputs` | Move to specific position |
| `sync-from-mendeley` | `SyncFromMendeleyInputs` | Pull from Mendeley, upsert queue |
| `sync-status` | `SyncStatusInputs` | queue_size vs database_pdfs count |
| `export` | `ExportInputs` | Export as markdown or JSON |
| `stats` | `StatsInputs` | Counts by status/category/course |
| `queue-clear` | `QueueClearInputs` | Clear queue (requires `yes=True`) |
| `config-show` | `ConfigShowInputs` | Show reading config |
| `config-set` | `ConfigSetInputs` | Set a reading config value |

---

## 5. Research tool in depth

**Source:** [`src/docent/bundled_plugins/research_to_notebook/__init__.py`](src/docent/bundled_plugins/research_to_notebook/__init__.py)

Two backends, tried in order:
1. **Feynman CLI** — if `feynman` is on PATH, delegates to it
2. **Docent-native pipeline** — Tavily Research API (primary) or 6-stage manual pipeline (fallback)

**Tavily Research API path** (primary when `tavily_api_key` available):
- `tavily_research()` in `search.py` calls `TavilyClient.research()` → polls `get_research()` until completed
- Returns a fully cited report, replacing stages 1-5 (search planner → fetch → gap eval → writer → verifier)
- OpenCode reviewer (stage 6) still runs for adversarial quality control
- Falls back to manual pipeline on any Tavily error, with a warning event

**Manual 6-stage pipeline** (fallback, in [`pipeline.py`](src/docent/bundled_plugins/research_to_notebook/pipeline.py)):

| Stage | Model | Purpose |
|-------|-------|---------|
| Search planner | `glm-5.1` | Generates web + paper queries |
| Fetch | Python (`search.py`) | Runs web search + Semantic Scholar |
| Gap evaluator | `glm-5.1` | Identifies missing angles |
| Writer | `minimax-m2.7` | Synthesizes the research report |
| Verifier | `glm-5.1` | Checks claims against sources |
| Reviewer | `deepseek-v4-pro` | Final quality review |

**Zero-source abort**: if manual pipeline collects 0 sources, returns error immediately (no garbage LLM output).

All model names are configurable in `[research]` config section.

**Actions:**

| Action | Notes |
|--------|-------|
| `deep "topic"` | Full research pipeline |
| `lit "topic"` | Literature-focused (80% paper search bias) |
| `review "artifact"` | 3-stage: fetch → researcher → reviewer |
| `usage` | Show today's Feynman USD spend + OC token usage |
| `config-show` | Show research config |
| `config-set --key K --value V` | Set a research config value |

Output written to `~/.docent/research/<topic-slug>/report.md`.

Spend tracking: `~/.docent/cache/research/feynman_spend.json` (date-keyed, resets daily).
Budget guard: if `feynman_budget_usd > 0`, stops at 90% of budget.

---

## 6. Web UI in depth

**Frontend source:** [`frontend/src/`](frontend/src/)
**Backend source:** [`src/docent/ui_server.py`](src/docent/ui_server.py)
**Pre-built static files:** `src/docent/ui_dist/` (gitignored; ships in wheel)

Pages:
- `/reading` — reading queue table, edit panel, export button
- `/settings` — inline config editor

FastAPI endpoints on `localhost:7432`:

| Method + path | What it does |
|---------------|-------------|
| `GET /api/queue` | Reads `queue.json` directly (does NOT apply Mendeley overlay — bug) |
| `POST /api/actions` | Dispatches reading actions by spawning `docent` subprocess (bug) |
| `GET /api/config` | Reads `~/.docent/config.toml` |
| `POST /api/config` | Writes config values |
| `GET /api/tooling` | Checks for `@companion-ai/feynman` npm update |

**Known bug:** the `POST /api/actions` and `GET /api/queue` endpoints bypass
`invoke_action()` and read files/spawn subprocesses directly. This means:
- Titles shown in the UI are stale (no Mendeley overlay)
- ~100ms overhead per mutation
- No test coverage over the invocation path

Fix: wire these endpoints to call `invoke_action()` from `mcp_server.py` directly.
This is post-v1.2.0 item #4 in [`memory/project_todos.md`](memory/project_todos.md).

To rebuild the UI after frontend changes:
```bash
cd frontend && npm install    # once
python scripts/build_ui.py    # copies out/ -> src/docent/ui_dist/
```

---

## 7. MCP server in depth

**Source:** [`src/docent/mcp_server.py`](src/docent/mcp_server.py)

The MCP server exposes every registered `@action` as an MCP tool.
Full calling contract and invariants: read [`AGENTS.md`](AGENTS.md) first.

**Tool naming:** `{tool}__{action}` — hyphens in action names become underscores.
```
reading__show
reading__sync_from_mendeley
research__deep
```

**To connect any MCP client:**
```json
{
  "mcpServers": {
    "docent": {
      "command": "docent",
      "args": ["serve"]
    }
  }
}
```
Or with `uv` from the project directory:
```json
{
  "mcpServers": {
    "docent": {
      "command": "uv",
      "args": ["--directory", "/path/to/docent/repo", "run", "docent", "serve"]
    }
  }
}
```

**Known gap (Codex item 6):** `mcp_server.py` only iterates `collect_actions()`. Single-action
tools (those using `run()` instead of `@action`) are never exposed over MCP.

---

## 8. v1.2.0 blockers — ALL FIXED 2026-05-11

Both original blockers resolved. 280/280 tests green.

**Bug 1 — Duplicate registration:** Absolute import caused double-import. Fixed: relative import. Registry now warns+skips on duplicates.

**Bug 2 — DDG → Tavily:** Replaced DuckDuckGo with Tavily across all files.

**New in this session (2026-05-11):**
- Tavily Research API integration — `tavily_research()` in `search.py` is now the primary path, replacing stages 1-5
- `web_search()` error propagation fix — re-raises auth/rate-limit errors, logs others, `search_depth="advanced"`
- Zero-source abort guard — clear error message instead of garbage LLM output
- Preflight mechanism for `@action` — interactive prompts run before Rich Progress
- WSL2 auto-detect in `OcClient`
- `tavily-python>=0.7.0` pinned in `pyproject.toml`
- Windows `.venv` recreated (was broken — no `pyvenv.cfg`)

**Remaining before release:** End-to-end verification with real Tavily key; tag v1.2.0.

---

## 9. Development setup

```bash
# Install Python deps (editable, with dev group)
uv sync
uv tool install --editable .

# Verify
docent --version
uv run pytest           # ~160 tests, ~3-4s

# Frontend (only needed when changing UI)
cd frontend
npm install
npm run dev              # dev server at localhost:3000
npm run lint && npx tsc --noEmit
python ../scripts/build_ui.py   # rebuild production static export

# Delegation scripts
python scripts/oc_delegate.py --task implement brief.md    # needs OpenCode server on :4096
python scripts/hermes_delegate.py --task loop brief.md     # self-contained
```

**After adding any new Python dependency**, run:
```bash
uv tool install --reinstall --editable .
```
The global `docent` command uses the installed wheel, not the source tree.

---

## 10. Rules and conventions — do not skip

### Code conventions

- **Pydantic v2 API:** use `model_fields`, `finfo.is_required()`, `finfo.annotation`.
  Do NOT use v1 patterns (`__fields__`, `finfo.outer_type_`). Mixing silently breaks CLI
  option generation.
- **Rich markup escaping:** `console.print("[keyword]")` silently swallows `[keyword]` as
  an unknown style tag. Use parentheses `(keyword)` or `rich.markup.escape("[keyword]")`.
- **ASCII only in CLI output** — Windows legacy console (cp1252) raises `UnicodeEncodeError`
  on any Unicode glyph (arrows, bullets, emoji). Gate on encoding check or use ASCII.
- **Lazy litellm import** — `import litellm` at module level adds ~1s startup time.
  It must stay inside `LLMClient.complete()`. Breaking this is a regression.
- **No `_`-prefixed plugin files** — `discover_tools()` and `load_plugins()` skip them.
- **Never put `Prompt.ask` inside a generator action** — Rich `Live` context overwrites
  interactive prompts before the user can type. Resolve prompts in a plain setup phase,
  then `return` a generator for streaming. See [`memory/gotchas.md`](memory/gotchas.md).
- **Validate before persisting config** — call `path.is_dir()` (or equivalent) before
  `write_setting()`. A persisted invalid value corrupts all future runs.

### Mandatory docs update rule

Any change that **adds, removes, or renames** a CLI command, flag, config key, env variable,
feature, or default value **must** update [`docs/`](docs/) and/or [`README.md`](README.md)
in the same commit. Do not open a PR with stale docs.

### Testing rules

- Use the `seed_queue_entry` fixture from `tests/conftest.py` to populate the queue in tests.
  Do not use `tool.add()` as a fixture builder — `add` is guidance-only.
- Real-data validation is required before marking a build step done. Run against real
  Mendeley data, not just the test suite.
- ~160 tests, ~3-4s. All must be green before any commit.

### Docs update rule (mandatory)

Any change that adds/removes/renames a CLI command, feature, config key, env variable, or
output format MUST update `docs/` and/or `README.md` in the same commit. Stale docs block
releases.

### Multi-model delegation

Two scripts:

| Script | When to use | Default model |
|--------|-------------|---------------|
| `scripts/oc_delegate.py` | One-shot; OpenCode server on `:4096` | `glm-5.1` (`--task implement`) |
| `scripts/hermes_delegate.py` | Self-correcting loop; no server needed | `deepseek-v4-pro` (`--task loop`) |

Brief files go in `memory/tasks/briefs/`. Completed briefs move to `memory/tasks/done/`.
Do NOT use delegation for anything touching `memory/`, `decisions.md`, or `AI_CONTEXT.md` —
keep those in the orchestrating session.

---

## 11. What NOT to do

| Don't | Why |
|-------|-----|
| Use `ANTHROPIC_API_KEY` directly | Settings prefix is `DOCENT_`; use `DOCENT_ANTHROPIC_API_KEY` |
| Hoist `import litellm` to module level | ~1s startup penalty; breaks fast meta commands |
| Name a plugin file starting with `_` | `discover_tools()` silently skips it |
| Call `Prompt.ask` inside a generator | Rich `Live` eats the prompt |
| Write to config before validating | Persists corrupt values, breaks all future runs |
| Touch `memory/` or `AI_CONTEXT.md` from a delegated model | Memory requires orchestrator judgment |
| Commit code without updating docs | Stale docs block releases |
| Register a tool name already in the registry | Warning printed, second registration skipped (v1.2.0) |

---

## 12. Quick reference: full file tree (important files only)

```
docent/
├── AI_CONTEXT.md                        ← YOU ARE HERE
├── AGENTS.md                            ← MCP calling contract
├── README.md                            ← User-facing overview
├── pyproject.toml                       ← Deps, build config
├── .mcp.json                            ← MCP server config template
├── docs/
│   ├── cli.md                           ← Full CLI reference
│   ├── reading.md                       ← Reading tool docs
│   └── reading_spec.md                  ← Reading tool spec
├── src/docent/
│   ├── cli.py                           ← Typer app (entry point)
│   ├── mcp_server.py                    ← MCP server + invoke_action()
│   ├── ui_server.py                     ← FastAPI backend
│   ├── config/
│   │   ├── settings.py                  ← ALL config keys defined here
│   │   └── loader.py                    ← load_settings(), write_setting()
│   ├── core/
│   │   ├── tool.py                      ← Tool ABC + @action decorator
│   │   ├── registry.py                  ← register_tool(), all_tools()
│   │   ├── plugin_loader.py             ← Plugin discovery
│   │   ├── context.py                   ← Context(settings, llm, executor)
│   │   ├── events.py                    ← ProgressEvent
│   │   └── shapes.py                    ← Output shape types
│   ├── bundled_plugins/
│   │   ├── reading/
│   │   │   ├── __init__.py              ← ReadingQueue (all actions)
│   │   │   ├── reading_store.py         ← Queue persistence
│   │   │   ├── mendeley_client.py       ← Mendeley MCP facade
│   │   │   ├── mendeley_cache.py        ← File-backed TTL cache
│   │   │   └── reading_notify.py        ← Deadline startup check
│   │   └── research_to_notebook/
│   │       ├── __init__.py              ← ResearchTool (all actions) + preflight functions
│   │       ├── pipeline.py              ← Tavily Research + 6-stage manual pipeline
│   │       ├── search.py                ← web_search, paper_search, tavily_research, fetch_page
│   │       └── oc_client.py             ← OpenCode REST client (WSL2 auto-detect)
│   ├── llm/client.py                    ← LLMClient (lazy litellm)
│   ├── execution/executor.py            ← Subprocess executor
│   ├── learning/run_log.py              ← Per-namespace JSONL run-log
│   ├── utils/paths.py                   ← data_dir(), cache_dir(), config_path()
│   └── utils/prompt.py                  ← prompt_for_path() (quote-strip + validate)
├── frontend/src/app/
│   ├── reading/page.tsx                 ← Reading queue page
│   ├── settings/page.tsx                ← Settings page
│   └── api/                             ← Dev-only Next.js API routes
├── tests/                               ← pytest suite (~160 tests)
├── scripts/
│   ├── build_ui.py                      ← Build Next.js → ui_dist/
│   ├── oc_delegate.py                   ← OpenCode delegation
│   └── hermes_delegate.py               ← Hermes delegation
└── memory/                              ← Project memory (read before coding)
    ├── MEMORY.md                        ← Memory index (start here)
    ├── build_progress.md                ← Build checklist
    ├── decisions.md                     ← Architectural decisions
    ├── gotchas.md                       ← Bugs and landmines
    ├── project_todos.md                 ← Master todo list
    ├── project_research_test_blockers.md ← v1.2.0 bug details
    ├── project_codex_review_blockers.md  ← Codex review debt
    └── archive/                         ← Older decisions + retired docs
```

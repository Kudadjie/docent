# Docent — Architecture Outline

A Python CLI "Control Center" for grad school workflows. Dispatcher/orchestrator pattern — not a monolith. Starts as a CLI; designed so a web frontend can wrap it later without a rewrite.

---

## Layer 0: Project Skeleton

```
docent/
├── pyproject.toml              # Dependency mgmt (uv)
├── README.md
├── AGENTS.md                   # Behavioral contract for Claude Code + MCP callers
├── .mcp.json                   # MCP server stanza template (copy into Claude Code config)
├── scripts/
│   ├── oc_delegate.py          # Delegate bounded tasks to OpenCode Go sub
│   └── hermes_delegate.py      # Delegate self-correcting loop tasks to Hermes
├── frontend/                   # docent-ui — Next.js 16 + React 19 + Tailwind CSS v4
├── src/
│   └── docent/                 # The package itself
│       ├── __init__.py
│       ├── cli.py              # Typer app entry point + command routing
│       ├── cli_setup.py        # Interactive first-run setup wizard (extracted from cli.py)
│       ├── mcp_server.py       # MCP adapter — exposes registry as MCP tools (`docent serve`)
│       ├── ui_server.py        # FastAPI app — serves UI on localhost:7432
│       ├── ui_routes/          # FastAPI route modules (split from ui_server.py)
│       │   ├── reading.py      # /api/queue, /api/actions, /api/database
│       │   ├── studio.py       # /api/studio/* — SSE + WebSocket for research runs
│       │   ├── config.py       # /api/config — read/write settings
│       │   ├── backup.py       # /api/backup/* — create, restore, list, Drive sync
│       │   ├── doctor.py       # /api/doctor — health checks
│       │   ├── filesystem.py   # /api/fs/read, /api/fs/open — path-approved file access
│       │   └── opencode.py     # /api/opencode/* — start/stop OpenCode subprocess
│       ├── core/
│       │   ├── registry.py     # Tool registry (the plugin system)
│       │   ├── tool.py         # Base Tool interface/protocol + @action decorator
│       │   ├── context.py      # Shared runtime context (config, LLM client, executor)
│       │   ├── invoke.py       # Central dispatcher: run_action, make_context, invoke_action_for_ui
│       │   ├── events.py       # ProgressEvent — yielded by generator actions
│       │   ├── exceptions.py   # ConfirmationRequired — surfaced by destructive actions
│       │   ├── shapes.py       # Output Shapes vocabulary (MarkdownShape, DataTableShape, …)
│       │   └── plugin_loader.py # Discovers + loads bundled + external plugins
│       ├── ui/
│       │   ├── console.py      # Rich console singleton
│       │   ├── renderers.py    # Per-shape Rich render registry (render_shapes)
│       │   └── theme.py        # Centralized color tokens (ACCENT, DIM, SUCCESS, …)
│       ├── llm/
│       │   └── client.py       # litellm wrapper — single entry for all model calls
│       ├── execution/
│       │   └── executor.py     # subprocess wrapper for external workers
│       ├── learning/
│       │   └── run_log.py      # Per-namespace JSONL run log (append, cap-and-roll)
│       ├── config/
│       │   ├── settings.py     # Pydantic settings (API keys, paths, per-tool nested models)
│       │   └── loader.py       # Reads ~/.docent/config.toml; write_setting for config-set
│       ├── backup/             # Backup archive creation + restoration (path-safe extraction)
│       ├── tools/              # Flat single-file tools (auto-discovered; _ prefix = skipped)
│       │   └── __init__.py
│       ├── bundled_plugins/    # Multi-module first-party tools (packaged with Docent)
│       │   ├── reading/        # Reading queue tool (Mendeley-backed, deadline tracking)
│       │   │   ├── __init__.py         # ReadingQueue Tool class + all actions + load_queue_for_ui
│       │   │   ├── models.py           # Schemas — Literal status/type, YYYY-MM-DD deadline validation
│       │   │   ├── reading_store.py    # ReadingQueueStore — atomic JSON writes, file lock, state recompute
│       │   │   ├── mendeley_client.py  # In-process MCP client facade (list_folders, list_documents)
│       │   │   ├── mendeley_cache.py   # File-backed read-through cache (TTL 300s / 24h for folder ids)
│       │   │   ├── mendeley_sync.py    # sync-from-mendeley logic (derive_id, normalize_authors)
│       │   │   ├── mendeley_backend.py # MendeleyBackend wrapper for client operations
│       │   │   ├── ref_manager.py      # ReferenceManagerClient protocol (Mendeley/Zotero abstraction)
│       │   │   └── reading_notify.py   # Startup deadline check (daily dedup)
│       │   ├── studio/         # Research workflows (deep research, lit review, peer review, NotebookLM)
│       │   │   ├── __init__.py         # StudioTool class + action dispatch; path-validates read_output/save_synthesis
│       │   │   ├── models.py           # Schemas — Literal output, backend validator against _BACKEND_ENUM
│       │   │   ├── _research.py        # Deep research + lit review action implementations
│       │   │   ├── _search_actions.py  # search-papers, get-paper, scholarly-search actions
│       │   │   ├── _notebook_actions.py # to-notebook action
│       │   │   ├── _config_actions.py  # config-show, config-set actions
│       │   │   ├── pipeline.py         # 6-stage manual pipeline; accepts SearchAdapter for DI
│       │   │   ├── search_adapter.py   # SearchAdapter Protocol + DefaultSearchAdapter + FakeSearchAdapter
│       │   │   ├── search.py           # Concrete: Tavily web search, Semantic Scholar, arXiv, page fetch
│       │   │   ├── free_research.py    # Tavily Research API primary path (replaces stages 1-5)
│       │   │   ├── _notebook.py        # NotebookLM push pipeline internals
│       │   │   ├── feynman.py          # Feynman CLI wrapper (hardened Windows subprocess)
│       │   │   ├── backend.py          # StudioBackend Protocol (OcClient, FeynmanBackend)
│       │   │   ├── oc_client.py        # OpenCode in-process client
│       │   │   ├── alphaxiv_client.py  # alphaXiv SDK wrapper
│       │   │   ├── scholarly_client.py # Google Scholar / Semantic Scholar wrapper
│       │   │   ├── citation_verifier.py # Automated citation verification
│       │   │   ├── helpers.py          # Shared utility functions
│       │   │   ├── preflights.py       # Preflight checks for studio actions
│       │   │   └── agents/             # Prompt templates for each pipeline stage
│       │   └── backup/         # Backup + Google Drive sync
│       │       ├── __init__.py         # BackupTool — create, restore, list, Drive sync actions
│       │       ├── manager.py          # Archive creation + path-safe restoration
│       │       └── drive_client.py     # Google Drive OAuth + upload/download
│       └── utils/
│           ├── paths.py        # XDG-style paths for cache, config, data
│           ├── prompt.py       # prompt_for_path with quote-strip + validation
│           ├── logging.py      # Structured logging setup
│           ├── update_check.py # GitHub release update checker
│           ├── model_health.py # LiteLLM model health probing
│           └── rich_compat.py  # Rich compatibility helpers
├── tests/
└── ~/.docent/              # User data (created at runtime)
    ├── config.toml
    ├── cache/
    │   └── reading/
    │       └── mendeley_collection.json  # Read-through Mendeley cache
    ├── data/
    │   └── reading/
    │       ├── queue.json          # Sidecar state (order, status, deadline, category…)
    │       ├── queue-index.json    # Fast-lookup index keyed by id
    │       ├── state.json          # Banner counts + last_updated timestamp
    │       └── run-log.jsonl       # Append-only structured event log
    └── plugins/                    # User-installed external plugins (drop .py or package here)
```

---

## Layer 1: The Tool Contract (most important decision)

Every tool — ported skill, subprocess wrapper, or future MCP client — conforms to one shape.

**Shared across all tools:**
- **`name`** — unique string, used as the CLI subcommand
- **`description`** — human-readable, shown in `--help`
- **`category`** (optional) — for grouping in help output

**Then a tool picks one of two paths:**

1. **Single-action tool** (e.g. `eli5`, `literature-review`, `research-to-notebook`):
   - **`input_schema`** — Pydantic model defining args
   - **`run(inputs, context) -> result`** — the execution method
   - CLI shape: `docent <name> --flag ...`

2. **Multi-action tool** (e.g. `reading`, `studio`, `backup`):
   - One or more methods decorated with `@action(description=..., input_schema=...)`
   - Each action has its own Pydantic input schema
   - Shared helpers live as regular methods on the Tool class. For tools with non-trivial persistent state, extract a per-tool **Store** class (see `ReadingQueueStore` — owns load / save / atomic-write / state-recompute). Actions mutate state via the store, never by reaching into JSON files directly. Establishes a clean seam for tests and future actions.
   - CLI shape: `docent <name> <action> --flag ...`

**Action shape — single-shot vs generator:**
- **Single-shot**: action returns a Pydantic result directly. The default. Use unless there's a concrete UX reason to stream.
- **Generator**: action `yield`s `ProgressEvent` records during work and `return`s the final result. The CLI dispatcher (`_drive_progress`) detects generator actions, drives them inside a Rich progress context, and renders the final return value identically. Opt in only when a slow phase justifies live feedback (e.g. `paper scan`, `paper sync-pull`). Designed when a concrete consumer existed — not in the abstract.

A tool must be single-action or multi-action — never both. Enforced at registration.

The `context` object passed to every tool provides the shared runtime: `settings`, `llm` (litellm wrapper), `executor` (subprocess), and later `logger`. **Tools never receive the Rich console** — UI rendering is cli.py/ui's job. Tools return typed data; the CLI renders, the future web UI serializes to JSON.

**Why this matters:** get this interface right once, and every future plugin — Python module, shell wrapper, MCP server — just implements it. Get it wrong, and you'll be refactoring every tool later.

---

## Layer 2: The Registry (the plugin mechanism)

- Singleton registry holding `{tool_name: type[Tool]}` — **the class, not an instance**. Tools are instantiated per invocation by the CLI / future UI request handler, so runs never share mutable state and no tool's `__init__` runs unless that tool is actually invoked (preserves the side-effect-free `docent --version` path).
- Tools self-register via a `@register_tool` decorator at import time.
- `docent/tools/__init__.py` walks the `tools/` directory and imports every module, triggering registration. Modules whose names start with `_` are skipped (reserved for scratch/private files).
- Reserved tool names: `list`, `info`, `config`, `version` — `@register_tool` rejects these to prevent shadowing built-in CLI commands.
- Two discovery paths, loaded in order by `core/plugin_loader.py`: (1) `bundled_plugins/` — multi-module first-party tools packaged with Docent; (2) `~/.docent/plugins/` — user-installed external plugins (flat `.py` files or packages with `__init__.py`). Bundled takes precedence; name collisions with external plugins produce a warning and skip.
- `on_startup(context)` lifecycle hook — if a plugin module defines it, `run_startup_hooks()` calls it after all plugins load (used by reading for deadline notifications).
- Typer commands are **generated dynamically** from the registry at startup. Adding a tool = adding a file. No CLI changes needed.
  - Single-action tool → one Typer command per tool.
  - Multi-action tool → one Typer sub-app per tool, one nested command per action.

---

## Layer 3: The CLI Layer (Typer)

- `cli.py` creates the root Typer app.
- Two kinds of commands:
  - **Built-ins**: `docent list`, `docent info <tool>`, `docent config`, `docent version`
  - **Dynamic**: every registered tool becomes `docent <tool-name> [args]`
- Global flags: `--verbose`, `--dry-run`, `--no-color`, `--model <name>`
- Exit codes follow Unix conventions (0 success, 1 general error, 2 misuse).

---

## Layer 4: The UI Layer (Rich)

Keep UI concerns out of tool logic. Tools return structured data; the UI layer renders it. Mechanically enforced: **tools do not import `docent.ui` and do not receive a console via `Context`.**

- **Console singleton** — one `Console()` instance lives in `docent.ui.console`. `cli.py` and renderers import it directly. Tools never touch it.
- **Standard renderers** (`ui/renderers.py`): success panels, error panels, markdown blocks, progress spinners, tables. `cli.py` calls `render_shapes()` to render tool results via the Output Shapes vocabulary.
- **Theme file** — centralized colors so you can restyle the whole app in one place.
- **Logging vs display** — logs go to file (`~/.docent/logs/`) via `context.logger`, user-facing output goes to Rich in the CLI layer. Don't mix them.
- **Rich markup gotcha** — `[required]`, `[default=...]` style brackets in help strings get eaten by Rich's markup parser as style tags. Use parentheses or escape them.

---

## Layer 5: The LLM Layer (litellm)

- A thin wrapper around `litellm.completion()` exposing: `complete()`, `stream()`, `with_tools()`.
- Handles: API key loading, default model selection, retry/backoff, token counting, cost logging.
- Every tool that needs an LLM goes through this — never imports litellm directly. Swapping models, adding caching, or routing to local models later is a one-file change.

---

## Layer 6: The Executor (subprocess)

For workers like `feynman`:

- A single `run_external()` helper that: streams stdout live to Rich, captures stderr, handles timeouts, returns a structured result (exit code, stdout, stderr, duration).
- Tools that wrap external CLIs become tiny — they just build the command and call the executor.

---

## Layer 7: Config & State

- **Config file**: `~/.docent/config.toml` — API keys, default model, tool-specific settings.
- **Pydantic Settings** loads and validates it; env vars override file values. `load_settings()` is memoized and self-invalidates on a config-file content hash + `DOCENT_*` env snapshot, so the UI server's per-request dispatch no longer re-parses TOML and re-validates the model on every call.
- **Per-tool config** lives under a tool-named table. Pattern: `reading.database_dir`, `reading.queue_collection`, `reading.mendeley_mcp_command`. Keys are nested Pydantic models on `Settings`; `config.loader.write_setting` does TOML round-trips for `config-set` actions. Required-but-unset paths trigger a first-run prompt (`prompt_for_path`) with a `NO_INTERACTIVE` escape for CI.
- **Cache directory**: `~/.docent/cache/` — for anything expensive to recompute.
- **Tool data directory**: `~/.docent/data/<toolname>/` — per-tool persistent state (queues, indexes, counters). Tools must never reach into `~/.claude/skills/`.
- **No state in the package itself** — installed code is read-only; all mutable state lives in `~/.docent/`.

---

## Layer 8: Learning (tools that improve from their own runs)

Ported skills (paper-pipeline, research-to-notebook) accumulate self-knowledge across invocations via three files per tool. Docent provides framework support for only the **generic** piece; the rest is tool-specific convention.

### Generic (framework-provided)

- **`~/.docent/data/<toolname>/run-log.jsonl`** — append-only structured event log, one JSON record per line. Shape is tool-defined, but every record gets a `timestamp` field prepended automatically.
- **`docent.learning`** module exposes three helpers:
  - `log_run(tool_name, record)` — atomic append to the tool's run log.
  - `read_runs(tool_name, n=None)` — load last N records (or all) as dicts.
  - `compact_log(tool_name, keep_last=50)` — when the file exceeds `keep_last`, move older lines to `run-log-archive.jsonl`. Tools call this opportunistically after logging.

### Tool-specific (convention, no framework code)

- **`~/.docent/data/<toolname>/learnings.md`** — human-readable dated narrative of edge cases, surprises, and non-obvious failures. Freeform markdown. Each tool decides when to write an entry.
- **`~/.docent/data/<toolname>/overrides.json`** — precomputed auto-tune flags derived from recent run-log entries. Shape and recomputation rules are tool-specific. Tools read this before doing work ("should I use a bigger timeout? skip this phase?") and recompute after ("did the last 5 runs change the flags?").

### Why this split

Logging atomically is a generic problem solvable once. What to log, what rules to derive, what counts as a learning — all tool-specific. Baking tool-specific patterns into the framework would be exactly the speculation karpathy warns about. Tools that don't need any of this (e.g. `eli5`) pay zero cost.

---

## Dependency Management: Use `uv`

**Recommendation: `uv`** (from Astral, the Ruff folks).

**Why:**
- **Speed** — 10–100× faster than pip/poetry for installs and resolution. You'll feel it every time you add a dep.
- **One tool, whole lifecycle** — replaces pip, pip-tools, pyenv, poetry, virtualenv. Manages Python versions too (`uv python install 3.12`).
- **Standards-compliant** — uses `pyproject.toml` natively, no proprietary lockfile format lock-in.
- **Great for CLI tools** — `uv tool install .` installs Docent globally in an isolated env, exactly what you want for a personal control center.
- **Active development, strong momentum** — it's becoming the default in the Python ecosystem in 2025–2026.

**Why not the alternatives:**
- **Poetry** — solid but slower, and its dependency resolver has historically been finicky. Proprietary lockfile.
- **pip + venv** — fine for tiny projects; you'll outgrow it the moment you want reproducible installs or version pinning.
- **pipenv** — effectively abandoned.
- **Hatch** — good but less ergonomic than uv for your use case.

**First commands you'll run:**
```
uv init docent
cd docent
uv add typer rich litellm pydantic pydantic-settings
uv add --dev pytest ruff
uv run docent --version
```

That's the whole setup.

---

## Layer 9: MCP Adapter (`docent serve`)

`mcp_server.py` exposes every registered tool as an MCP tool over stdio.

- **Tool naming**: `{tool}__{action}` with hyphens replaced by underscores (e.g. `reading__sync_from_mendeley`).
- **Dispatch**: `invoke_action(tool, action, args)` → drains generator actions and serialises the final result as JSON.
- **Serialisation**: `serialize_result()` lives in `core.invoke` and is shared by both the MCP and FastAPI surfaces — neither imports from the other.
- **Consent**: Studio research actions emit suggested next steps (not mandatory commands) so the agent can ask the user before proceeding.
- **Path safety**: `studio.read_output` and `studio.save_synthesis` validate that file paths are under `research.output_dir` or the Docent home dir before reading/writing.

---

## Layer 10: Web UI (`docent ui`)

`ui_server.py` is a FastAPI app served on `localhost:7432`. Route handlers live in `ui_routes/` modules (split from the original monolith). The frontend is a Next.js static export in `ui_dist/`, bundled into the wheel. In development, `next.config.ts` proxies `/api/*` to FastAPI — no duplicate Next.js API routes needed.

**Route modules** (`ui_routes/`):
- `reading.py` — `/api/queue` (reads through `load_queue_for_ui` with Mendeley overlay), `/api/actions` (mutations via `invoke_action_for_ui`), `/api/database`.
- `studio.py` — `/api/studio/*` — SSE streaming for in-process studio runs; WebSocket for subprocess-based runs.
- `filesystem.py` — `/api/fs/read` (GET) reads a file for Markdown preview; `/api/fs/open` (POST) opens in OS file manager. Both restricted to approved roots.
- `config.py` — `/api/config` (GET/POST) — reads/writes settings.
- `backup.py` — `/api/backup/*` — create, restore, list, Google Drive sync.
- `doctor.py` — `/api/doctor` — health checks.
- `opencode.py` — `/api/opencode/*` — start/stop the OpenCode subprocess.

**Security model (localhost-only):**
- `_LocalhostGuard` middleware rejects any request whose `Origin` header is not `localhost` or `127.0.0.1`. This prevents malicious web pages from making cross-site requests to the UI server.
- `_check_approved_path()` validates all file-path inputs against `research.output_dir` and the Docent home directory before reading or opening.
- `/api/fs/open` is POST-only (not GET) so standard links can't trigger it.
- Audit logging (`~/.docent/audit.log`) records sensitive operations: file open, config write, queue clear, OpenCode start/stop.
- Bind address defaults to `127.0.0.1` — the server is never exposed beyond localhost without explicit configuration.
- **SSRF guard on page fetching** (`studio/search.py::fetch_page` → `_url_is_fetchable`): page URLs come from search providers, so they are attacker-influenceable. Each URL — and each redirect hop, since redirects are followed manually — must use an http(s) scheme and resolve to a public IP; loopback / private / link-local / reserved targets (e.g. `169.254.169.254`, localhost services) are refused.

**Non-interactive vs consent (Context flags):** `Context` carries three orthogonal flags instead of the old overloaded `via_mcp`: `via_mcp` (MCP agent — governs `mcp_notes` and AI-agent output framing), `non_interactive` (no TTY — preflights raise structured errors and skip spinners), and `auto_confirm` (skip human confirmation gates). MCP sets all three; the web UI sets `non_interactive` + `auto_confirm` only, so UI users get human-facing output and an explicit (not accidental) auto-confirm. `make_context(via_mcp=True)` still implies the other two unless overridden.

**Studio action mapping** (`build_studio_request`):
- **One** source of truth. `build_studio_request(body)` resolves a `StudioRunBody` into a `StudioRequest` holding BOTH the in-process `kwargs` (for `run_action` on the SSE path) and the CLI `argv` (for the subprocess WebSocket path), built side by side in the same per-action branch. The two thin renderers — `_parse_studio_body` (ui_server) and `_build_studio_cmd` (ui_routes/opencode) — both derive from it, so a new action or argument is added in exactly one place and the two surfaces cannot drift. (Historically these were two hand-synced mappings; `test_ui_server_tooling.py::test_both_builders_agree_on_confirmed_gate` guards against regression.)
- The live frontend uses the WebSocket subprocess path; the SSE path remains wired and unit-tested.

---

## Layer 11: Search Adapter (pipeline DI)

`studio/search_adapter.py` defines a `SearchAdapter` Protocol with four methods: `web_search`, `paper_search`, `academic_search_parallel`, `fetch_page`.

- **`DefaultSearchAdapter`** wraps the concrete functions in `search.py`. Production code creates one implicitly when `adapter=None`.
- **`FakeSearchAdapter`** returns pre-configured lists — no network I/O. Unit tests pass it directly to `run_deep`/`run_lit` instead of monkeypatching individual module-level functions.
- The adapter is threaded through `_run_with_tavily_fallback → _run_pipeline` as a keyword argument, making the search seam explicit and injectable.

---

## Layer 12: Test Taxonomy

| Mark | Meaning | Run by default? |
|------|---------|-----------------|
| (none) | Unit test — no real I/O, all external calls mocked or faked | Yes |
| `@pytest.mark.integration` | Requires real network or external service | No — `-m not integration` |
| `@pytest.mark.eval` | Slow golden-set evaluation against real LLM output | No — `-m not eval` |

A `_blocked_connect` socket guard in `conftest.py` raises `OSError` if a unit test accidentally opens a real external socket connection. Tests marked `integration` or `eval` are exempt.

**Irreversible actions (cannot be undone from the CLI):**

| Tool | Action | Effect |
|------|--------|--------|
| `reading` | `queue-clear --yes` | Deletes all queue entries |
| `reading` | `done` | Sets `finished` timestamp (preserved across edits) |
| `reading` | `start` | Sets `started` timestamp |
| `reading` | `remove` | Marks entry `removed` (soft delete) |
| `studio` | `save-synthesis` | Writes a new file to `output_dir` |

---

## Studio Backend Matrix

| Backend | What it does | Via MCP? | Via terminal? | Key required |
|---------|-------------|----------|---------------|--------------|
| `free` | Tavily + Semantic Scholar aggregation; YOU synthesise | ✓ | ✓ | Tavily (optional, falls back to DDG) |
| `docent` | 6-stage AI pipeline via OpenCode | ✗ (timeout) | ✓ | Provider API key |
| `feynman` | Full Feynman CLI deep research | ✗ (timeout) | ✓ | Feynman credits |
| `groq` | LiteLLM → Groq | ✗ (timeout) | ✓ | `GROQ_API_KEY` |
| `gemini` | LiteLLM → Gemini | ✗ (timeout) | ✓ | `GEMINI_API_KEY` |
| `openrouter` | LiteLLM → OpenRouter | ✗ (timeout) | ✓ | `OPENROUTER_API_KEY` |
| `anthropic` | LiteLLM → Anthropic | ✗ (timeout) | ✓ | `ANTHROPIC_API_KEY` |
| `openai` | LiteLLM → OpenAI | ✗ (timeout) | ✓ | `OPENAI_API_KEY` |
| `ollama` | LiteLLM → local Ollama | ✗ (timeout) | ✓ | None |
| `lm_studio` | LiteLLM → LM Studio | ✗ (timeout) | ✓ | None |
| `local` | LiteLLM → custom base URL | ✗ (timeout) | ✓ | None |

**Via MCP means**: a single tool call completes before the MCP connection times out. Only `free` reliably does this; all AI backends run a multi-minute pipeline. For AI backends, instruct users to run `docent studio <action> --backend <name> --topic "..."` in their terminal instead.


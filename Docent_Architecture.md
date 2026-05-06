# Docent — Architecture Outline

A Python CLI "Control Center" for grad school workflows. Dispatcher/orchestrator pattern — not a monolith. Starts as a CLI; designed so a web frontend can wrap it later without a rewrite.

---

## Layer 0: Project Skeleton

```
docent/
├── pyproject.toml          # Dependency mgmt
├── README.md
├── docent/                 # The package itself
│   ├── __init__.py
│   ├── cli.py              # Typer app entry point + command routing
│   ├── core/
│   │   ├── registry.py     # Tool registry (the plugin system)
│   │   ├── tool.py         # Base Tool interface/protocol
│   │   ├── context.py      # Shared runtime context (config, logger, LLM client)
│   │   └── executor.py     # subprocess wrapper for external workers
│   ├── ui/
│   │   ├── console.py      # Rich console singleton
│   │   ├── renderers.py    # Markdown, tables, spinners, panels
│   │   └── theme.py        # Colors, styles
│   ├── llm/
│   │   └── client.py       # litellm wrapper — single entry for all model calls
│   ├── config/
│   │   ├── settings.py     # Pydantic settings (API keys, paths, defaults)
│   │   └── loader.py       # Reads ~/.docent/config.toml
│   ├── tools/              # ← YOUR SKILLS LIVE HERE (the plugins)
│   │   ├── __init__.py     # Auto-discovery happens here
│   │   ├── skill_one.py
│   │   └── skill_two.py
│   └── utils/
│       ├── logging.py
│       └── paths.py        # XDG-style paths for cache, config, data
├── tests/
└── ~/.docent/              # User data (created at runtime)
    ├── config.toml
    ├── cache/
    └── logs/
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

2. **Multi-action tool** (e.g. `paper-pipeline`, `alpha-research`, `browse`):
   - One or more methods decorated with `@action(description=..., input_schema=...)`
   - Each action has its own Pydantic input schema
   - Shared helpers live as regular methods on the Tool class. For tools with non-trivial persistent state, extract a per-tool **Store** class (see `PaperQueueStore` — owns load / save / atomic-write / state-recompute). Actions mutate state via the store, never by reaching into JSON files directly. Establishes a clean seam for tests and future actions.
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
- Later, add a second discovery path: `~/.docent/plugins/` — drop in external tool files without editing the package.
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
- **Standard renderers** (cli.py + future `ui/renderers.py`): success panels, error panels, markdown blocks, progress spinners, tables. The CLI calls these to render tool results.
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
- **Pydantic Settings** loads and validates it; env vars override file values.
- **Per-tool config** lives under a tool-named table. Pattern: `paper.database_dir`, `paper.unpaywall_email`, `paper.queue_collection`, `paper.mendeley_mcp_command`. Keys are nested Pydantic models on `Settings`; `config.loader.write_setting` does TOML round-trips for `config-set` actions. Required-but-unset paths trigger a first-run prompt (`prompt_for_path`) with a `NO_INTERACTIVE` escape for CI.
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


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
   - Shared helpers (atomic writes, dedup, banner counts, etc.) live as regular methods on the Tool class — no framework needed
   - CLI shape: `docent <name> <action> --flag ...`

A tool must be one or the other — never both. Enforced at registration.

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

## Build Order (strict)

Current status in `memory/build_progress.md`.

1. ✅ Project skeleton + `pyproject.toml` + `docent --version` working
2. ✅ Config loader + Rich console singleton
3. ✅ Tool base class + registry + `@register_tool` decorator + `Context` dataclass
4. ✅ Dynamic Typer command generation + `docent list` / `docent info`
5. ✅ litellm wrapper (single-entry `LLMClient.complete()`, lazy-imported litellm, `Context.llm`)
6. ✅ Subprocess executor (`Executor.run()`, `ProcessResult`, `ProcessExecutionError`, `Context.executor`)
7a. ✅ **Multi-action contract extension** — `@action` decorator, multi-action CLI generation, registry validation. Motivated by paper-pipeline (16 ops on shared state) and research-to-notebook (6 modes on shared pipeline). Evidence-based, not speculation.
7b. ✅ **First real tool: `paper add`** (stubbed inputs; no CrossRef yet) — validates the full stack end-to-end on a real workflow. Scaffolds the shared-helper pattern (`_load_queue`, `_atomic_write_json`, `_recompute_state`, `_derive_id`, `_banner_counts`) every subsequent paper action reuses.
8. **Simple paper CRUD actions** (batch): `next`, `show`, `search`, `stats`, `remove`, `edit`, `done`, `ready-to-read`, `mark-keeping`, `export`. Pure queue operations, no external APIs. After this step: a useful standalone paper-pipeline minus Mendeley/sync. Ships `docent.learning` alongside (see Layer 8).
9. **`paper add` with CrossRef + `process_inbox`** — real DOI resolution via `context.executor`, DOI/fuzzy-title dedup, inbox manifest processing.
10. **Progress streaming extension** — yield-events path for long-running actions. Motivated by research-to-notebook pipeline and paper-pipeline `sync-status`. Designed only when a concrete consumer exists (karpathy: don't design event vocabulary in the abstract).
11. **Paper sync ops** (`sync-status`, `sync-pull`, `sync-promote`, `sync-mendeley`) + minimal MCP adapter (Mendeley integration). Long-running; motivates the streaming extension from step 10.
12. External `~/.docent/plugins/` discovery.
13. Full MCP adapter (Docent exposes *itself* via MCP — last, after the native registry is battle-tested).

---

## The One Thing to Resist

Don't build the MCP layer early. It's tempting because it's the "impressive" part, but the native registry must be battle-tested first. MCP is just another adapter behind the same registry — if the registry is clean, MCP is a weekend. If the registry is dirty, MCP will expose every flaw.

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

Notes to Fold Into Architecture
1. Tool discovery — start simple, migrate later
The tools/__init__.py directory-walk-and-import approach works for v1 but has a hidden cost: every CLI invocation pays the import time of every tool, even commands like docent --version that don't need any of them. Fine at 3 tools; painful at 30.
v1 approach (ship this): directory walk in tools/__init__.py, trigger @register_tool decorators at import time. Simple, obvious, no extra config.
v2 migration path (when startup latency becomes noticeable): switch to entry points declared in pyproject.toml under [project.entry-points."docent.tools"]. Python discovers tool names without importing the modules; actual import happens only when the tool is invoked. This is the standard pattern for plugin-heavy Python CLIs (pytest, flake8, pipx all use it).
Trigger to migrate: when docent --version takes >200ms, or when porting a tool with heavy imports (torch, large model clients) that slow down unrelated commands.
Don't do this now. Premature. Just be aware the exit ramp exists so the tool contract in Layer 1 doesn't accidentally depend on eager registration.

2. Enforce the UI/logic boundary mechanically, not by discipline
"Tools return structured data; the UI layer renders it" is correct but fragile. Under deadline pressure the first violation will be a console.print(...) inside a tool because it's faster than plumbing a result object back. Once that happens, every subsequent tool copies the pattern, and the web frontend refactor becomes a rewrite.
Make the contract mechanical:

Tool run() methods return a typed result object (Pydantic model), never None and never printed output.
Tools do not import from docent.ui. Consider a lint rule or import-time check to enforce this — a simple ast walk in a pre-commit hook is enough.
The context object passed to tools exposes a logger (for diagnostic output that goes to file) but not a console. If a tool needs to show progress, it yields progress events via a structured channel; the CLI layer decides how to render them.
Only cli.py and the ui/ package touch the Rich console.

Why this matters for the web frontend later: if tools return structured results and never touch a TTY, the web layer just serializes those results to JSON. If tools print directly, the web layer has to capture stdout, parse it, and hope nothing escapes. The second path never actually gets built — the project just stays a CLI forever.

3. MCP is across a process boundary — design the registry to know that
The outline frames MCP as "just another adapter behind the same registry." Directionally right, but understated. Native tools and MCP tools differ in ways the registry needs to model:

Process boundary — MCP tools run out-of-process, possibly over network. Every call can fail in ways a native call cannot (timeout, broken pipe, server restart).
Lifecycle — native tools exist as long as the Python process. MCP servers start, stop, crash, need reconnection, need auth refresh.
Discovery — native tools are known at import time. MCP tool lists come from a running server and can change mid-session.
Trust — native tools are your code. MCP tools are someone else's code speaking a protocol.

**Decision (karpathy simplicity-first): `origin` and `health()` are deferred** until step 11 when the MCP adapter actually lands. The save-a-refactor argument doesn't survive scrutiny — the "refactor" is adding `origin = "native"` once per tool, which is minutes of mechanical work when there are 10 tools. Building fields for a feature that's months away is the exact speculation karpathy #2 warns against. Revisit when MCP is real work, not before.

Summary of what changes in the outline

Layer 1 (Tool Contract): two paths (single-action, multi-action); require `run`/actions to return typed result objects; forbid UI imports from tools.
Layer 2 (Registry): store the class (not an instance); directory walk for v1; document entry-points as the v2 migration.
Layer 4 (UI): the context object exposes a logger (not a console). Enforce with a lint check.
Build Order: step 7 split into 7a (multi-action) and 7b (first real tool); step 9 inserted for progress streaming extension (motivated by long-running tools, designed when concrete consumer exists).
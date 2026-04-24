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

Every tool — ported skill, subprocess wrapper, or future MCP client — conforms to one shape:

- **`name`** — unique string, used as the CLI subcommand
- **`description`** — human-readable, shown in `--help`
- **`input_schema`** — Pydantic model defining args
- **`run(inputs, context) -> result`** — the execution method
- **`category`** (optional) — for grouping in help output

The `context` object passed to every tool gives it access to: the Rich console, the litellm client, the config, a logger, and a subprocess executor. This is how you avoid every tool re-instantiating its dependencies.

**Why this matters:** get this interface right once, and every future plugin — Python module, shell wrapper, MCP server — just implements it. Get it wrong, and you'll be refactoring every tool later.

---

## Layer 2: The Registry (the plugin mechanism)

- Singleton registry holding `{tool_name: ToolInstance}`.
- Tools self-register via a `@register_tool` decorator at import time.
- `docent/tools/__init__.py` walks the `tools/` directory and imports every module, triggering registration.
- Later, add a second discovery path: `~/.docent/plugins/` — drop in external tool files without editing the package.
- Typer commands are **generated dynamically** from the registry at startup. Adding a tool = adding a file. No CLI changes needed.

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

Keep UI concerns out of tool logic. Tools return structured data; the UI layer renders it.

- **Console singleton** — one `Console()` instance everywhere, consistent styling.
- **Standard renderers**: success panels, error panels, markdown blocks, progress spinners, tables. Tools call these helpers instead of printing directly.
- **Theme file** — centralized colors so you can restyle the whole app in one place.
- **Logging vs display** — logs go to file (`~/.docent/logs/`), user-facing output goes to Rich. Don't mix them.

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
- **No state in the package itself** — installed code is read-only; all mutable state lives in `~/.docent/`.

---

## Build Order (strict)

1. Project skeleton + `pyproject.toml` + `docent --version` working
2. Config loader + Rich console singleton
3. Tool base class + registry + decorator
4. Dynamic Typer command generation + `docent list`
5. litellm wrapper
6. Subprocess executor
7. **First real tool**: port your easiest skill
8. Second tool (proves the interface generalizes)
9. External `~/.docent/plugins/` discovery
10. MCP adapter (much later — only once the native registry is stable)

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

Implications for the Layer 1 tool contract:
Add two fields to the base Tool interface now, even though only native tools will use them in v1:

origin: Literal["native", "mcp", "subprocess"] — tells the dispatcher how to route, and the UI how to render errors (a native crash and an MCP timeout are different user experiences).
health() -> HealthStatus — for native tools this always returns OK. For MCP tools it'll mean "is the server reachable, is auth valid." Having the method in the base contract from day one means MCP integration doesn't require changing every existing tool.

Don't build MCP support yet. Just don't design it out. The day you add it, these two fields will save a refactor.

Summary of what changes in the outline

Layer 1 (Tool Contract): add origin and health() to the base interface. Require run() to return a typed result object. Forbid UI imports from tools.
Layer 2 (Registry): keep the directory walk for v1. Document entry-points as the v2 migration.
Layer 4 (UI): the context object exposes a logger, not a console. Enforce with a lint check.
Build Order: unchanged. These are refinements, not reorderings.
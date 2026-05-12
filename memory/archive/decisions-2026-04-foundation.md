---
name: Docent decisions log — Steps 1–6 foundation archive
description: Archived 2026-04-23 entries (package layout, CLI wiring, registry, Tool ABC, Context, LLM, Executor). Read when revisiting foundation choices.
type: project
---

Archived 2026-04-25 from `memory/decisions.md` to keep the live log small. All entries below were Active at archival; if any get superseded or reverted, update the relevant entry back in the live `decisions.md` and link here.

---

## 2026-04-23 — Package + CLI wiring defaults
**Context:** Early scaffolding choices in steps 1–2 that shape everything downstream.
**Decision:** Use `src/docent/` layout (from `uv init --package`), not flat. Console script is `docent = "docent.cli:app"` in `pyproject.toml` (Typer's `app` is directly callable). `--version` is a Typer eager callback with `is_eager=True` so it exits before the root callback body runs — keeps `--version` side-effect-free (does not create `~/.docent/`). `~/.docent/` path structure is not XDG; it mirrors the arch doc literally (honors `DOCENT_HOME` env var for test isolation).
**Why:** Standard `uv` pattern; keeps CLI concerns out of `__init__.py`; eager callback preserves zero-startup-cost for meta commands.
**Alternatives rejected:** Flat package layout (breaks `uv tool install .`); `docent:main` entry point (forces a redundant `main()` wrapper); XDG paths (arch doc was emphatic about `~/.docent/`).
**Status:** Active.

## 2026-04-23 — pydantic-settings source order flipped so env beats TOML
**Context:** Default source order in pydantic-settings is `(init, env, file_secret)`. That means TOML-loaded values (passed as init kwargs) win over env vars.
**Decision:** Override `settings_customise_sources` to return `(env_settings, init_settings, file_secret_settings)`. Precedence is now env > TOML > code defaults.
**Why:** Standard expectation is env overrides config file (for deploy/test scenarios). Verified with `DOCENT_DEFAULT_MODEL`.
**Alternatives rejected:** Default order — would surprise anyone expecting env-wins semantics.
**Status:** Active.

## 2026-04-23 — Rich `Console` singleton replaced, not mutated
**Context:** `configure_console(no_color=True)` needs to apply the flag.
**Decision:** Rebuild the `Console` instance and swap it in the `_console` module-level slot. Do not mutate flags on an existing `Console`.
**Why:** Rich caches construction-time state (terminal detection, color system). In-place mutation is unsafe.
**Alternatives rejected:** Mutating `_console.no_color = True` — silently ineffective.
**Status:** Active.

## 2026-04-23 — Registry stores Tool class, not instance
**Context:** Arch doc sketched `{tool_name: ToolInstance}`. Considered alternative: store `{name: type[Tool]}`.
**Decision:** Store the class. Instances are created per invocation by the CLI / future UI handler.
**Why:** (1) Preserves `docent --version` side-effect-free path — no tool `__init__` runs unless that tool is invoked. (2) `@register_tool` naturally decorates a class. (3) Future UI concurrency safety: every dashboard click creates a fresh instance, so tools never need threadsafety.
**Alternatives rejected:** Instance-based — every tool's `__init__` would fire on every CLI invocation including meta commands, and any future multi-user UI would share mutable state.
**Status:** Active.

## 2026-04-23 — `Tool` is an ABC, not a `Protocol`
**Context:** Two shapes to model a base contract.
**Decision:** ABC with class attrs (`name`, `description`, `input_schema`, optional `category`) and a default `run` that raises `NotImplementedError`. Registry validates at import time.
**Why:** ABC gives loud early errors at registration; Protocol would defer failures to runtime.
**Alternatives rejected:** `typing.Protocol` — structural typing checks happen too late.
**Status:** Active. (`run` was `@abstractmethod` before Step 7a; now has a default to support the multi-action path.)

## 2026-04-23 — No `origin`/`health()` on Tool until MCP actually lands
**Context:** Arch doc §3 suggested adding `origin: Literal["native","mcp","subprocess"]` and `health()` now, to "save a refactor later" when MCP integration comes.
**Decision:** Defer both. They land with Step 11 (MCP adapter).
**Why:** Pure speculation — no MCP tools exist or will for months. The "refactor" is adding `origin = "native"` once per tool, which is minutes of mechanical work even at 10+ tools. Karpathy simplicity-first: don't design fields for features months away.
**Alternatives rejected:** Add them proactively per arch-doc advice — rejected because the saved refactor isn't meaningful vs. the speculation cost.
**Status:** Active. Revisit at Step 11.

## 2026-04-23 — `Context` is a frozen dataclass; tools never receive the console
**Context:** Arch doc originally listed "Rich console" as one of the things `Context` provides to tools. But we also wanted a tools-don't-touch-UI boundary so the future web UI can render the same results.
**Decision:** `Context` holds only `settings` at first; grows one field per build step (`llm` step 5, `executor` step 6). **Never contains `console`.** `cli.py` uses the console directly via `docent.ui.get_console()`. Tools return structured data; CLI renders.
**Why:** Mechanical enforcement of the UI/logic boundary. A tool literally cannot `console.print(...)` without going out of its way.
**Alternatives rejected:** Pass console to tools — tools would become terminal-locked; retrofitting for a web UI would be a rewrite.
**Status:** Active. `logger` field added when `utils/logging.py` lands.

## 2026-04-23 — CLI: every Pydantic field becomes a `--flag`, never positional
**Context:** Tools declare inputs via a Pydantic schema; how should those inputs surface in the CLI?
**Decision:** All fields become `--flags`. Underscore → dash (`max_sources` → `--max-sources`). Required fields use `typer.Option(...)`; optional fields pass the Pydantic default.
**Why:** Uniform across tools; users never guess which args are positional. Crucially: 1:1 with the future UI's form-field model — each Pydantic field becomes one form input, same serialization.
**Alternatives rejected:** Positional required args, kwargs for optional — violates uniformity and doesn't translate to the form-based UI.
**Status:** Active.

## 2026-04-23 — Reserved tool names
**Context:** A tool could try to claim `name="list"` and shadow a built-in CLI command.
**Decision:** `register_tool` rejects `{"list", "info", "config", "version"}` with `ValueError` at registration time.
**Why:** Fail loud and early, not silently at invocation.
**Alternatives rejected:** Prefix built-ins (`docent :list`) — ugly UX.
**Status:** Active.

## 2026-04-23 — `LLMResponse` dataclass return, not bare `str`
**Context:** `LLMClient.complete()` could return the raw text or a structured response.
**Decision:** Return a frozen `LLMResponse` dataclass with `.text` and `.model` fields.
**Why:** Adding token-count / cost / latency fields for the future UI is an additive change, not a breaking refactor across every call site. Minor friction (`.text`) trades for future-proofing.
**Alternatives rejected:** Return `str` — any future metadata addition means breaking every caller.
**Status:** Active.

## 2026-04-23 — litellm imported lazily inside `complete()`
**Context:** litellm import is ~1s. Meta commands (`--version`, `list`, `info`) must stay fast.
**Decision:** Never `import litellm` at module top. The import line lives inside `LLMClient.complete()`. `LLMClient.__init__` does no litellm work.
**Why:** Preserves the side-effect-free fast-path we've been defending since Step 1.
**Alternatives rejected:** Module-top import — undoes the discipline from `--version` eager callback.
**Status:** Active. Enforced by an invariant check: `import docent.cli; assert 'litellm' not in sys.modules`.

## 2026-04-23 — API keys: env wins, Settings fields as fallback
**Context:** Users might want keys in env OR in `~/.docent/config.toml`.
**Decision:** `LLMClient.__init__` copies `settings.anthropic_api_key` / `settings.openai_api_key` into `os.environ` **only if the env var is unset**. litellm reads from env normally.
**Why:** Standard env-wins semantics; works with both config styles; no key-handling logic inside `complete()`.
**Alternatives rejected:** Config-only (forces file-based keys); always-overwrite-env (violates env-wins). Also rejected: catching and translating litellm exceptions — let `AuthenticationError` / `RateLimitError` propagate.
**Status:** Active.

## 2026-04-23 — `Executor`: `list[str]` only, `check=True` default, stdlib names
**Context:** Designing the subprocess wrapper.
**Decision:** `run(args, *, timeout, cwd, env, check=True) -> ProcessResult`. `args` must be `list[str]` — no `shell=True` anywhere. `check=True` raises `ProcessExecutionError` on non-zero. `env=None` inherits parent; explicit dict replaces (matches `subprocess.run`). `ProcessResult` uses stdlib-compatible names: `args`, `returncode`, `stdout`, `stderr`, plus `duration` (seconds).
**Why:** No shell = zero injection surface; shell features via explicit `["bash", "-c", "..."]`. `check=True` matches `subprocess.run` convention; fail-fast is right for tool wrappers. Stdlib-compatible names mean `subprocess` muscle memory transfers.
**Alternatives rejected:** `shell=True` / string commands (injection risk); `check=False` default (silent failures); renamed fields (`command`/`exit_code`) — marginal readability gain, breaks muscle memory.
**Status:** Active.

## 2026-04-23 — `Executor` lives in `execution/`, not `core/`
**Context:** Arch doc put `executor.py` inside `core/` next to registry/tool/context.
**Decision:** Park it at `src/docent/execution/executor.py`, parallel to `llm/`.
**Why:** `core/` is for plugin-system primitives (what makes a tool a tool); the executor is an injected dependency like `LLMClient`. Symmetry with `llm/` beats arch-doc layout.
**Alternatives rejected:** `core/executor.py` — clutters core with injectables.
**Status:** Active.

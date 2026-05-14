# Docent Plugin Developer Guide

Plugins let you add new tools to Docent without modifying the package. Drop a file into `~/.docent/plugins/` and your tool appears in `docent list`, gets its own CLI sub-commands, and is automatically exposed as MCP tools via `docent serve`.

---

## 1. Quick start

Create `~/.docent/plugins/greet.py`:

```python
from pydantic import BaseModel
from docent.core.tool import Tool, action
from docent.core.registry import register_tool
from docent.core.context import Context


class GreetInputs(BaseModel):
    name: str
    loud: bool = False


class GreetResult(BaseModel):
    message: str


@register_tool
class Greeter(Tool):
    name = "greet"
    description = "Say hello."

    @action(description="Greet someone by name.", input_schema=GreetInputs)
    def hello(self, inputs: GreetInputs, context: Context) -> GreetResult:
        msg = f"Hello, {inputs.name}!"
        if inputs.loud:
            msg = msg.upper()
        return GreetResult(message=msg)
```

Then:

```bash
docent list              # greet appears
docent greet hello --name Alice
docent greet hello --name Alice --loud
```

---

## 2. Plugin discovery

Docent loads plugins from two directories, in this order:

1. `src/docent/bundled_plugins/` — first-party, shipped with the package
2. `~/.docent/plugins/` — your external plugins

Both support **flat files** (a single `.py`) and **packages** (a directory with `__init__.py`).

**Rules:**
- Files and directories whose names begin with `_` are skipped.
- If a plugin raises an exception during import, Docent prints a one-line warning to stderr and continues loading the remaining plugins. Your error never aborts the CLI.
- If a plugin tries to register a tool name that is already taken, it prints a warning and is skipped. The first registration wins.

---

## 3. Tool contract

Every plugin must subclass `Tool` and apply `@register_tool`.

### 3.1 Required class attributes

| Attribute | Type | Rules |
|-----------|------|-------|
| `name` | `str` | Non-empty. Globally unique. Not a reserved name. |
| `description` | `str` | Shown in `docent list`. |

**Reserved names** (cannot be used as tool names): `list`, `info`, `config`, `version`.

### 3.2 Optional class attributes

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `category` | `str \| None` | `None` | Grouping label shown in `docent list`. |

### 3.3 Single-action tools

Set `input_schema` on the class and override `run()`. Use when your tool has exactly one operation.

```python
class PingInputs(BaseModel):
    host: str

@register_tool
class Ping(Tool):
    name = "ping"
    description = "Ping a host."
    input_schema = PingInputs

    def run(self, inputs: PingInputs, context: Context) -> str:
        return f"pong: {inputs.host}"
```

### 3.4 Multi-action tools

Decorate methods with `@action(...)`. Each decorated method becomes a CLI sub-command. Use when your tool has multiple operations.

**A tool must be one or the other — never both.** Declaring both `run()` and `@action` methods raises `TypeError` at registration.

---

## 4. The `@action` decorator

```python
@action(
    description="Short description shown in --help.",
    input_schema=MyInputs,          # required: Pydantic BaseModel subclass
    name="custom-name",             # optional: override CLI name (default: method_name with _ → -)
    preflight=my_preflight_fn,      # optional: runs before Rich Progress (see §4.1)
)
def my_action(self, inputs: MyInputs, context: Context) -> MyResult:
    ...
```

**Parameters:**

| Parameter | Type | Required | Purpose |
|-----------|------|----------|---------|
| `description` | `str` | Yes | Shown in `--help` output |
| `input_schema` | `type[BaseModel]` | Yes | Pydantic model; validated before the method runs |
| `name` | `str \| None` | No | CLI sub-command name; default is `method_name.replace("_", "-")` |
| `preflight` | `Callable[[BaseModel, Context], None] \| None` | No | Called before Rich Progress starts |

### 4.1 The preflight hook

Rich Progress steals stdin, so interactive prompts (e.g., asking the user for an API key) cannot run inside a generator action. The `preflight` hook runs before Rich starts, giving you a clean stdin window.

```python
def _ask_for_key(inputs: ResearchInputs, context: Context) -> None:
    if not context.settings.research.tavily_api_key:
        key = input("Tavily API key: ").strip()
        context.settings.research.tavily_api_key = key

@action(description="Run deep research.", input_schema=ResearchInputs, preflight=_ask_for_key)
def deep(self, inputs: ResearchInputs, context: Context):
    ...
```

The preflight may raise `typer.Abort()` to cancel, or mutate `context.settings` to persist values.

---

## 5. Inputs

The `input_schema` is a `pydantic.BaseModel` subclass. Fields map directly to CLI flags:

- **Fields without a default** → required CLI flags (`--name <value>`)
- **Fields with a default** → optional CLI flags

The validated model instance is passed as the first argument to `run()` or the `@action` method.

```python
class EditInputs(BaseModel):
    id: str                     # required: --id
    notes: str = ""             # optional: --notes
    deadline: str | None = None # optional: --deadline
```

---

## 6. Outputs and `to_shapes()`

Return any value from `run()` or an `@action` method. The CLI prints the default `repr` unless you implement `to_shapes()`.

If your result type implements `to_shapes() -> list[OutputShape]`, the CLI and web UI render it natively — no markup strings, no formatting code in your tool.

```python
from docent.core.shapes import MarkdownShape, MessageShape

class MyResult(BaseModel):
    summary: str
    ok: bool

    def to_shapes(self) -> list:
        if not self.ok:
            return [MessageShape(text="Operation failed.", level="error")]
        return [MarkdownShape(content=self.summary)]
```

### Available OutputShape types

| Shape | Fields | Use for |
|-------|--------|---------|
| `MarkdownShape` | `content: str` | Freeform markdown prose |
| `DataTableShape` | `columns: list[str]`, `rows: list[list[str]]` | Tabular data |
| `MetricShape` | `label: str`, `value: str\|int\|float`, `unit: str\|None` | Single number or stat |
| `LinkShape` | `label: str`, `url: str` | Clickable link |
| `MessageShape` | `text: str`, `level: "info"\|"success"\|"warning"\|"error"` | Status messages |
| `ErrorShape` | `reason: str`, `hint: str\|None` | Errors with optional recovery hint |
| `ProgressShape` | `phase: str`, `message: str`, `current: int\|None`, `total: int\|None`, `level` | Progress events in generator actions |

---

## 7. Generator actions

For long-running operations, `yield` `ProgressShape` values during work and `return` the final result. The CLI streams progress live; MCP callers receive only the final result.

```python
from docent.core.shapes import ProgressShape

@action(description="Process a large dataset.", input_schema=ProcessInputs)
def process(self, inputs: ProcessInputs, context: Context):
    yield ProgressShape(phase="loading", message="Reading files...")
    # ... do work ...
    yield ProgressShape(phase="writing", message="Saving results...", current=50, total=100)
    # ... more work ...
    return ProcessResult(count=100, ok=True)
```

---

## 8. The `on_startup` hook

Define `on_startup(context: Context)` at **module level** (not as a method) to run code once at CLI startup. Docent calls all collected hooks after all plugins load, before the command runs.

```python
def on_startup(context: Context) -> None:
    # e.g. check for overdue items, warm a cache, validate credentials
    ...
```

Exceptions in `on_startup` are caught and printed as warnings — they never abort the CLI.

---

## 9. Multi-module packages

For plugins with multiple source files, use a package instead of a flat `.py` file:

```
~/.docent/plugins/
└── myplugin/
    ├── __init__.py      # must call @register_tool
    ├── models.py
    └── helpers.py
```

The plugin directory is added to `sys.path`, so sibling modules are importable by bare name:

```python
# __init__.py
from models import MyInputs, MyResult   # works — myplugin/ is on sys.path
from helpers import do_thing

from docent.core.tool import Tool, action
from docent.core.registry import register_tool
from docent.core.context import Context


@register_tool
class MyPlugin(Tool):
    name = "myplugin"
    description = "My multi-module plugin."

    @action(description="Do the thing.", input_schema=MyInputs)
    def do_thing(self, inputs: MyInputs, context: Context) -> MyResult:
        return do_thing(inputs)
```

---

## 10. MCP exposure

Every registered action is automatically exposed as an MCP tool when you run `docent serve`. No extra code needed.

**Tool name format:** `{tool}__{action}` — hyphens replaced by underscores, double-underscore separator.

| Docent action | MCP tool name |
|---------------|---------------|
| `greet hello` | `greet__hello` |
| `myplugin do-thing` | `myplugin__do_thing` |

See `docs/cli.md §5` for MCP setup instructions.

---

## 11. The Context object

`context: Context` is passed to every `run()` and `@action` call. It provides:

| Attribute | Type | Purpose |
|-----------|------|---------|
| `context.settings` | `Settings` | Full Docent config (read/write; changes persist in memory for the current invocation) |
| `context.llm` | `LLMClient` | LiteLLM wrapper for making LLM calls |
| `context.executor` | `Executor` | Subprocess runner for shell commands |

---

## 12. Registration rules summary

`@register_tool` validates your class at import time and raises `TypeError` immediately if:

- `name` or `description` is missing or empty
- `name` is a reserved word (`list`, `info`, `config`, `version`)
- The tool declares both `run()` and `@action` methods
- A single-action tool is missing `input_schema`
- Any `input_schema` is not a Pydantic `BaseModel` subclass
- Two `@action` methods resolve to the same CLI name

If the name is already registered (duplicate from another plugin), Docent prints a warning and skips — it does not raise.

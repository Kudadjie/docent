# Step 12 — Plugin Loader Infrastructure

## Project
`C:\Users\DELL\Desktop\Docent` — a Python CLI called `docent` built with Typer + Pydantic + Rich.
Run tests with: `uv run pytest`
Do NOT run `uv tool install` at any point.

## Objective
Create `src/docent/core/plugin_loader.py` and wire it into `cli.py`.
This is the discovery engine for external plugins. The reading-tool migration that comes
after this task will prove it works end-to-end.

---

## What to build

### 1. `src/docent/core/plugin_loader.py`

```python
"""External plugin discovery.

Search order:
  1. src/docent/bundled_plugins/  (shipped plugins — may not exist yet, skip gracefully)
  2. ~/.docent/plugins/           (user-installed plugins, via plugins_dir() from paths.py)

Each directory is added to sys.path before importing, so plugin packages can use
relative imports internally. Both flat *.py files and packages (dir + __init__.py)
are supported. Names starting with _ are skipped.

Broken plugins: print one-line warning to stderr, continue loading others.
Name conflicts (plugin registers a name already taken): the registry raises ValueError,
which is caught and printed as a warning — same skip behaviour.

Startup hooks: plugins may define on_startup(context: Context) at module level.
The loader collects them; run_startup_hooks(context) calls them all after the CLI
creates its Context object.
"""
```

Key points:
- Use `plugins_dir()` from `docent.utils.paths` for the user plugins dir (respects `DOCENT_HOME` env var).
- Bundled plugins dir: `Path(docent.__file__).parent / "bundled_plugins"` — skip if it doesn't exist.
- `sys.path.insert(0, str(dir))` before importing from each dir (guard: only if not already in path).
- Module-level list `_STARTUP_HOOKS: list` — populated during `load_plugins()`.
- `load_plugins() -> None` — main entry point, searches both dirs.
- `run_startup_hooks(context) -> None` — calls every collected hook; catches + warns on hook failure.
- Import the module name with `importlib.import_module(module_name)`.
  After import, check `sys.modules.get(module_name)` for an `on_startup` attribute.

### 2. `src/docent/core/__init__.py`

Add `load_plugins` and `run_startup_hooks` to imports and `__all__`.

### 3. `src/docent/cli.py`

Two changes only — do NOT touch anything else in this file:

**a) At module level** — after `discover_tools()` and before the for-loop that registers tools,
add `load_plugins()` so plugin tools are registered and get CLI commands built:

```python
discover_tools()
load_plugins()          # NEW: load ~/.docent/plugins/ + bundled_plugins
for _tool_cls in all_tools().values():
    _register_tool_in_app(_tool_cls)
```

Import `load_plugins` from `docent.core` (or `docent.core.plugin_loader` — whichever is cleaner).

**b) In `main()` callback** — after `ctx.obj = Context(...)` is set, call startup hooks:

```python
ctx.obj = Context(settings=settings, llm=LLMClient(settings), executor=Executor())
run_startup_hooks(ctx.obj)   # NEW: on_startup hooks from plugins
```

The existing `check_deadlines` block stays as-is — it will be removed when the reading
tool migrates to bundled_plugins (that is a separate task after this one).

Import `run_startup_hooks` from `docent.core` (or `docent.core.plugin_loader`).

---

## Tests — `tests/test_plugin_loader.py`

Write a pytest test file covering these cases. Use `tmp_path` for isolated plugin dirs.
You'll need a helper that temporarily patches `plugins_dir()` and the bundled_plugins path
to point at temp dirs (monkeypatch or a fixture). Also ensure `sys.path` and `sys.modules`
and the registry are cleaned up between tests so tests don't bleed into each other.

Cases to cover:

1. **No plugins dir** — `load_plugins()` with a nonexistent dir is a no-op, no crash.
2. **Valid flat .py plugin** — a `.py` file that defines a `Tool` subclass with `@register_tool`
   gets loaded; `all_tools()` contains it after `load_plugins()`.
3. **Valid package plugin** — a directory with `__init__.py` that registers a tool gets loaded.
4. **Broken plugin (import error)** — a `.py` file with a syntax error or bad import prints a
   warning to stderr and does not crash; other plugins in the same dir still load.
5. **Name conflict** — a plugin tries to register a name already in the registry; warning printed
   to stderr, no crash.
6. **`on_startup` hook collected** — a plugin defines `on_startup(context)`; after `load_plugins()`,
   calling `run_startup_hooks(mock_context)` calls it exactly once.
7. **`_`-prefixed names skipped** — a `_private.py` file and a `_private/` dir are not loaded.

### Fixture plugin skeletons

The test helper creates tiny tool files on the fly. Example:

```python
# a valid flat plugin
plugin_content = """
from docent.core import Tool, register_tool
from pydantic import BaseModel

class FakeInputs(BaseModel):
    pass

@register_tool
class FakeTool(Tool):
    name = "fake-plugin-tool"
    description = "test"
    input_schema = FakeInputs

    def run(self, inputs, context):
        return None
"""
```

---

## Run `uv run pytest` and fix until all tests pass.

The existing 91 tests must all stay green. The new test file should add ~7 tests.

---

## Constraints

- Do NOT modify any file other than the four listed above (plugin_loader.py, core/__init__.py,
  cli.py, and the new test file).
- Do NOT move or delete any existing tool files — that is the next task.
- Do NOT run `uv tool install`.
- If you discover a bug in existing code while running tests, report it but do not fix it
  unless it directly blocks the new tests from passing.

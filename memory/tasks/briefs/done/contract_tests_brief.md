# Brief: Contract tests for Tool ABC, registry, and dispatcher

## Goal

Write two new test files that fill the gaps in the current test suite:

1. `tests/test_tool_abc.py` — invariants on `tool.py` and `registry.py`
2. `tests/test_dispatcher.py` — invariants on `mcp_server.invoke_action()`

After writing, run `uv run pytest` and fix until the full suite is green.

---

## Scope: what to test

### tests/test_tool_abc.py

All tests use the `isolated_registry` fixture (already in conftest.py) to avoid leaking
tool names into the global registry.

Import from:
```python
from docent.core.tool import Tool, action, collect_actions, Action
from docent.core.registry import register_tool, get_tool, all_tools
from pydantic import BaseModel
import pytest
```

Tests to write:

1. **`test_run_raises_not_implemented`** — construct a Tool subclass that does NOT override
   `run()`, call `.run(None, None)`, assert it raises `NotImplementedError`.

2. **`test_collect_actions_cli_name_from_method_name`** — class with `@action` method named
   `do_something`; `collect_actions()` should return key `"do-something"` (underscores → dashes).

3. **`test_collect_actions_custom_name_override`** — class with `@action(name="custom-name")`
   on a method; `collect_actions()` should return key `"custom-name"`, not the method name.

4. **`test_collect_actions_name_collision_raises`** — class with two `@action` methods that
   resolve to the same CLI name (one named `foo_bar`, another with `name="foo-bar"`); assert
   `collect_actions()` raises `ValueError` matching "same CLI name".

5. **`test_register_non_tool_class_rejected`** — call `@register_tool` on a plain class (not
   a Tool subclass); assert `TypeError`.

6. **`test_missing_name_attr_rejected`** — Tool subclass with no `name` class attr; assert
   `@register_tool` raises `TypeError` matching `"name"`.

7. **`test_missing_description_attr_rejected`** — Tool subclass with `name` but no
   `description`; assert `@register_tool` raises `TypeError` matching `"description"`.

8. **`test_empty_name_rejected`** — Tool subclass with `name = ""`; assert `@register_tool`
   raises `TypeError` matching `"non-empty"`.

9. **`test_mixed_single_and_multi_action_rejected`** — Tool subclass that has both an
   `@action` method AND overrides `run()`; assert `@register_tool` raises `TypeError`.

10. **`test_mixed_input_schema_and_action_rejected`** — Tool subclass that has both an
    `@action` method AND sets `input_schema`; assert `@register_tool` raises `TypeError`.

11. **`test_action_non_basemodel_input_schema_rejected`** — `@action(input_schema=dict)`
    on a method (dict is not a BaseModel subclass); assert `@register_tool` raises `TypeError`
    matching `"BaseModel"`.

12. **`test_get_tool_missing_raises_key_error`** — call `get_tool("nonexistent-xyz")` without
    the `isolated_registry` fixture (no tool registered with that name); assert `KeyError`.

13. **`test_all_tools_returns_copy`** — register a tool, call `all_tools()`, mutate the
    returned dict (delete the key), call `all_tools()` again, assert the key is still present
    in the second call (mutation didn't affect the registry).

---

### tests/test_dispatcher.py

These tests exercise `invoke_action()` in `docent/mcp_server.py`. To avoid filesystem
dependencies, define two minimal in-test tools — do NOT use the reading tool.

Import from:
```python
from docent.core.tool import Tool, action
from docent.core.registry import register_tool
from docent.core.events import ProgressEvent
from docent.mcp_server import invoke_action
from pydantic import BaseModel
import json
import pytest
```

Define two minimal fixture tools at module level (they will be registered once when the
module imports, which is fine because they use unique names):

```python
class _PingInputs(BaseModel):
    msg: str = "hello"

class _StreamInputs(BaseModel):
    n: int = 2

@register_tool
class _PingTool(Tool):
    name = "test-ping-xyz"
    description = "Ping for testing."

    @action(description="Return a pong.", input_schema=_PingInputs)
    def pong(self, inputs, context):
        return {"pong": inputs.msg}

@register_tool
class _StreamTool(Tool):
    name = "test-stream-xyz"
    description = "Stream for testing."

    @action(description="Stream progress then return.", input_schema=_StreamInputs)
    def stream(self, inputs, context):
        for i in range(inputs.n):
            yield ProgressEvent(phase="work", message=f"step {i}")
        return {"done": True}
```

Tests to write:

1. **`test_invoke_sync_action_returns_json`** — call `invoke_action("test-ping-xyz", "pong", {"msg": "hi"})`,
   parse result as JSON, assert `result["pong"] == "hi"`.

2. **`test_invoke_sync_action_default_inputs`** — call with empty `{}`, assert result JSON
   has `"pong": "hello"` (the default).

3. **`test_invoke_generator_action_contains_progress`** — call `invoke_action("test-stream-xyz",
   "stream", {"n": 2})`, assert the result string contains `"[work] step 0"` and
   `"[work] step 1"`.

4. **`test_invoke_generator_action_last_line_is_json`** — same call, split on `"\n"`, parse
   last line as JSON, assert `result["done"] is True`.

5. **`test_invoke_unknown_tool_raises`** — call with `tool_name="no-such-tool"`, assert
   `ValueError` matching `"No tool named"`.

6. **`test_invoke_unknown_action_raises`** — call `tool_name="test-ping-xyz"`,
   `action_cli_name="no-such-action"`, assert `ValueError` matching `"no action"`.

---

## Project conventions (HARD RULES — do not deviate)

1. **No imports from `docent.bundled_plugins.reading`** — these new test files do not touch
   the reading tool at all.

2. **Use the existing `isolated_registry` fixture** from conftest.py for tests that call
   `@register_tool`. Do NOT recreate it.

3. **The dispatcher fixture tools** (`_PingTool`, `_StreamTool`) are registered at module import
   time (outside any fixture). They use sufficiently unique names (`test-ping-xyz`,
   `test-stream-xyz`) so they won't clash if the suite runs multiple times in the same process.

4. **No `tmp_docent_home` needed** for dispatcher tests — `_make_context()` in `invoke_action`
   reads settings, which is fine; we only care about the return value shape.

5. **Run `uv run pytest` after writing both files** and fix any failures before reporting done.
   The full suite must be green (currently 141 tests → expect ~155+ after this work).

6. **No Rich markup in any string values** in test assertions.

---

## Files to create

- `tests/test_tool_abc.py`
- `tests/test_dispatcher.py`

Do NOT modify any existing files.

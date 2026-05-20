## Project context — read before starting
Use your file-reading tools to load these in order:
1. `memory/MEMORY.md` — project memory index (short; read it fully)
2. `memory/gotchas.md` — known landmines; check before writing anything similar

---

# Brief: Decouple ui_server from mcp_server

## Goal
`src/docent/ui_server.py` currently imports from `src/docent/mcp_server.py`:
```python
from docent.mcp_server import invoke_action, _serialize
```
This creates a bidirectional coupling: the FastAPI backend depends on the MCP serialization layer. If the MCP server changes, the UI breaks. The review says "both should depend on core.invoke, not each other."

## What to change

### Step 1: Move `_serialize` to `docent.core.invoke`
In `src/docent/mcp_server.py`, find the `_serialize` function (it converts Pydantic results + dicts to JSON strings). Move it to `src/docent/core/invoke.py` as `serialize_result(result) -> str`. Keep backward compatibility in mcp_server.py via a re-import: `from docent.core.invoke import serialize_result as _serialize`.

### Step 2: Add `invoke_action_for_ui` to `docent.core.invoke`
In `src/docent/core/invoke.py`, add a new function:
```python
def invoke_action_for_ui(tool_name: str, action_name: str, args: dict) -> str:
    """Run a tool action and return JSON-serialized result. Used by the UI backend."""
    result = run_action(tool_name, action_name, args)
    return serialize_result(result)
```

### Step 3: Update `ui_server.py`
Replace:
```python
from docent.mcp_server import invoke_action, _serialize
```
With:
```python
from docent.core.invoke import invoke_action_for_ui as invoke_action, serialize_result as _serialize
```

All uses of `invoke_action(...)` and `_serialize(...)` in ui_server.py should work unchanged since the signatures are the same.

## Verification
Run: `uv run pytest -x -q`
All tests must pass. Also check: `python -c "from docent.ui_server import app; print('OK')"` and `python -c "from docent.mcp_server import run_server; print('OK')"` both work.

## Files to touch
- `src/docent/core/invoke.py` — add `serialize_result` and `invoke_action_for_ui`
- `src/docent/mcp_server.py` — re-export `_serialize` from core.invoke, no behavior change
- `src/docent/ui_server.py` — update import line only

Do NOT change any test files unless a test imports `_serialize` from mcp_server directly.

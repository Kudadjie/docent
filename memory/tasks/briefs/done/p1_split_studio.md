# Brief: Split studio/__init__.py by action family (item 33)

## Goal
`src/docent/bundled_plugins/studio/__init__.py` is ~1490 lines. It contains: StudioTool class, research actions (deep-research, lit, review, compare, replicate, audit, draft), NotebookLM action (to-notebook), config actions (config-show, config-set), alphaXiv/scholarly search actions (search-papers, get-paper, scholarly-search), and the on_startup hook. Split by action family.

## Target structure

```
src/docent/bundled_plugins/studio/
├── __init__.py        ← StudioTool class shell + imports from submodules + on_startup
├── _research.py       ← @action methods: deep_research, lit, review, compare, replicate, audit, draft
├── _notebook_actions.py ← @action method: to_notebook (wraps _notebook.py pipeline)
├── _config_actions.py ← @action methods: config_show, config_set + _KNOWN_RESEARCH_KEYS
├── _search_actions.py ← @action methods: search_papers, get_paper, scholarly_search, read_output, save_synthesis
```

## How to split a multi-action Tool

The `@action` decorator works on methods of the `StudioTool` class. Python allows defining class methods across multiple files via mixins:

```python
# _research.py
from docent.core import action, Context, ProgressEvent
from .models import DeepInputs, DeepResult, ...

class ResearchMixin:
    @action(description="...", input_schema=DeepInputs, name="deep-research")
    def deep_research(self, inputs, context): ...

# __init__.py
from ._research import ResearchMixin
from ._notebook_actions import NotebookMixin
from ._config_actions import ConfigMixin
from ._search_actions import SearchMixin

@register_tool
class StudioTool(ResearchMixin, NotebookMixin, ConfigMixin, SearchMixin, Tool):
    name = "studio"
    description = "..."
    category = "research"
```

Python MRO handles the method resolution. `collect_actions()` from `docent.core.tool` already uses `dir(cls)` which traverses the MRO and picks up all `@action`-decorated methods from all base classes.

## What stays in __init__.py
- `StudioTool` class definition (now thin — just `name`, `description`, `category`)
- Imports of all four mixins
- `on_startup` hook function (at module level, not inside the class)
- Constants: `_PRICING_NOTE`, `_BACKEND_NORM`, etc. that are used across mixins — move these to `_shared.py` or keep in `__init__.py` depending on usage

## What goes in each split file

### `_research.py`
Methods: `deep_research`, `lit`, `review`, `compare`, `replicate`, `audit`, `draft`
Also: `_run_deep_with_context`, `_run_lit_with_context` helpers (if any internal helpers are tightly coupled)

### `_notebook_actions.py`
Methods: `to_notebook`
Imports: from `._notebook` (the existing pipeline)

### `_config_actions.py`
Constants: `_KNOWN_RESEARCH_KEYS`
Methods: `config_show`, `config_set`

### `_search_actions.py`
Methods: `search_papers`, `get_paper`, `scholarly_search`, `read_output`, `save_synthesis`
Imports from `search_adapter.py`, `alphaxiv_client.py`, `scholarly_client.py`

## Verification
```bash
uv run pytest -x -q
uv run docent studio --help
```
All 502 tests must pass. `docent studio --help` must list all the same actions as before.

## IMPORTANT constraint
- Keep ALL existing imports in `__init__.py` that external code depends on (re-export them). Check what `mcp_server.py`, `ui_server.py`, and `tests/` import from `studio/__init__.py`.
- Run `grep -r "from docent.bundled_plugins.studio import" src/ tests/` before splitting to identify what needs to stay exported from `__init__.py`.

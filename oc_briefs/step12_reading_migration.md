# Step 12 — Move reading tool to bundled_plugins

## Project
`C:\Users\DELL\Desktop\Docent` — Python CLI. Run tests with: `uv run pytest`.
Do NOT run `uv tool install`.

## Objective
Move the reading tool (5 files) from `src/docent/tools/` into a new
`src/docent/bundled_plugins/reading/` plugin package. Update imports in those
files + all test files. Add an `on_startup` hook. Remove the now-unnecessary
hardcoded `reading_notify` import from `cli.py`. Run pytest until all 100 tests pass.

---

## Step 1 — Create `src/docent/bundled_plugins/` package

Create `src/docent/bundled_plugins/__init__.py` (empty file).

---

## Step 2 — Create `src/docent/bundled_plugins/reading/` package

Create these files:

### `src/docent/bundled_plugins/reading/__init__.py`
Copy `src/docent/tools/reading.py` verbatim, then make THREE import changes:

Line 18: `from docent.tools.reading_store import` → `from .reading_store import`
Line 19: `from docent.tools.mendeley_cache import` → `from .mendeley_cache import`
Line 20: `from docent.tools.mendeley_client import` → `from .mendeley_client import`

Then add this function at the very end of the file:

```python
def on_startup(context) -> None:  # noqa: ARG001
    from docent.utils.paths import data_dir
    from docent.ui import get_console
    from .reading_notify import check_deadlines
    for alert in check_deadlines(data_dir() / "reading"):
        get_console().print(f"[yellow]READING DEADLINE:[/] {alert}")
```

### `src/docent/bundled_plugins/reading/mendeley_cache.py`
Copy `src/docent/tools/mendeley_cache.py` verbatim, then make TWO import changes:

Line 35: `from docent.tools.mendeley_client import list_documents` → `from .mendeley_client import list_documents`
Line 36: `from docent.tools.mendeley_client import list_folders` → `from .mendeley_client import list_folders`

### `src/docent/bundled_plugins/reading/reading_store.py`
Copy `src/docent/tools/reading_store.py` verbatim. No import changes needed.

### `src/docent/bundled_plugins/reading/mendeley_client.py`
Copy `src/docent/tools/mendeley_client.py` verbatim. No import changes needed.

### `src/docent/bundled_plugins/reading/reading_notify.py`
Copy `src/docent/tools/reading_notify.py` verbatim. No import changes needed.

---

## Step 3 — Delete the old tool files

Delete these five files:
- `src/docent/tools/reading.py`
- `src/docent/tools/reading_store.py`
- `src/docent/tools/mendeley_cache.py`
- `src/docent/tools/mendeley_client.py`
- `src/docent/tools/reading_notify.py`

---

## Step 4 — Update `src/docent/cli.py`

Remove these two lines (they are replaced by the on_startup hook):

```python
from docent.tools.reading_notify import check_deadlines
```

and:

```python
    for alert in check_deadlines(data_dir() / "reading"):
        get_console().print(f"[yellow]READING DEADLINE:[/] {alert}")
```

No other changes to cli.py.

---

## Step 5 — Update `tests/conftest.py`

Add these lines near the top (after the existing imports, before fixtures):

```python
import sys as _sys
from pathlib import Path as _Path

# Make bundled plugins importable (mirrors what plugin_loader does at runtime)
_BUNDLED = _Path(__file__).parent.parent / "src" / "docent" / "bundled_plugins"
if _BUNDLED.exists() and str(_BUNDLED) not in _sys.path:
    _sys.path.insert(0, str(_BUNDLED))
```

---

## Step 6 — Update test imports

Replace ALL occurrences of the old import paths with the new ones.
The new module lives at `reading` (top-level once bundled_plugins is on sys.path).

Exact replacements across ALL test files:

| Old | New |
|-----|-----|
| `from docent.tools.reading import` | `from reading import` |
| `from docent.tools.reading_store import` | `from reading.reading_store import` |
| `from docent.tools.mendeley_cache import` | `from reading.mendeley_cache import` |
| `from docent.tools.mendeley_client import` | `from reading.mendeley_client import` |

Files that need changes (grep confirmed):
- `tests/conftest.py` line 62
- `tests/test_database_dir.py` line 12
- `tests/test_mendeley_cache.py` line 13
- `tests/test_queue.py` line 8
- `tests/test_queue_clear.py` line 12
- `tests/test_queue_store.py` line 5
- `tests/test_reader_overlay.py` line 20
- `tests/test_status_timestamps.py` line 12
- `tests/test_sync_from_mendeley.py` lines 18 and 563
- `tests/test_sync_status.py` line 16

---

## Step 7 — Run `uv run pytest` and fix until all 100 tests pass

If any test fails, read the error, fix it, and re-run. Common failure modes:
- Missing import (check the replacement table above)
- `reading` module not found (check sys.path setup in conftest.py)
- Relative import error inside the plugin package (check steps 2a and 2b)

Do NOT modify test logic — only fix imports.
Do NOT modify any file not listed above.

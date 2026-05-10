# Task: Create `tests/test_shapes.py`

Project root: `C:\Users\DELL\Desktop\Docent`

## Context

`src/docent/core/shapes.py` exists with 7 Pydantic shape types:
- `MarkdownShape`, `DataTableShape`, `MetricShape`, `LinkShape`, `MessageShape`, `ErrorShape`, `ProgressShape`
- `Shape` union (discriminated on `type`)

`src/docent/ui/renderers.py` exists with:
- `render_shapes(shapes: list[Shape], console: Console) -> None`

`src/docent/bundled_plugins/reading/__init__.py` has 10 result types, each with `to_shapes() -> list[Shape]`:
`AddResult`, `MutationResult`, `SearchResult`, `StatsResult`, `ExportResult`, `QueueClearResult`, `ConfigShowResult`, `ConfigSetResult`, `SyncFromMendeleyResult`, `SyncStatusResult`

`tests/conftest.py` already exists with a `seed_queue_entry` fixture that creates a `QueueEntry` in a `ReadingQueue` tool via `_store.save_queue`. Look at `tests/conftest.py` to understand existing fixtures before writing new ones.

## What to build

`tests/test_shapes.py` — covering:

### 1. Shape construction (one test per type)
- Each shape type can be constructed with valid fields
- Accessing `.type` returns the expected literal string
- `shape.model_dump()` includes `type` in the output (needed for MCP wire format)

### 2. Shape discriminated union
- `from pydantic import TypeAdapter; ta = TypeAdapter(Shape)` can round-trip each shape type through `ta.validate_python(shape.model_dump())`

### 3. `to_shapes()` on result types (one test per result type)
Use `BannerCounts` from `docent.bundled_plugins.reading.reading_store` to build banners.

For each result type, assert:
- `to_shapes()` returns a non-empty list
- Every item in the list is a shape with a `.type` attribute
- The shape types match expected pattern (e.g. `StatsResult` → `['metric', 'data_table', 'data_table']`)

Expected shape type lists (for the happy/normal path):
- `AddResult` (added=False, queue_size=2, message="Drop PDF..."): `['markdown', 'message']`
- `MutationResult` ok=True with a real entry: starts with at least one shape
- `MutationResult` ok=False: `['error']`
- `SearchResult` with 0 matches: `['message']`
- `SearchResult` with 1+ matches: `['message', 'data_table']`
- `StatsResult` with by_category populated: `['metric', 'data_table', 'data_table']`
- `ExportResult`: `['message', 'markdown']`
- `QueueClearResult` cleared=True: `['message']` with level='success'
- `QueueClearResult` cleared=False: `['message']` with level='warning'
- `ConfigShowResult`: `['metric', 'metric', 'metric']`
- `ConfigSetResult` ok=True: `['message']` with level='success'
- `ConfigSetResult` ok=False: `['message']` with level='error'
- `SyncFromMendeleyResult` with message (early exit): `['message']` with level='warning'
- `SyncFromMendeleyResult` without message (normal): has at least `MetricShape` items
- `SyncStatusResult` without message: `['metric', 'metric', 'metric']`
- `SyncStatusResult` with message: `['metric', 'metric', 'metric', 'message']`

### 4. `render_shapes` smoke test
- Build a `rich.console.Console(file=io.StringIO())` 
- Call `render_shapes([MarkdownShape(content="# Hello"), MessageShape(text="Done", level="success")], console)`
- Assert no exception raised and `console.file.getvalue()` contains "Hello" and "Done"

## Rules
- Import only from `docent.core.shapes`, `docent.ui.renderers`, and `docent.bundled_plugins.reading`
- Use `pytest` style (functions, not classes)
- No mocking — construct result objects directly with valid fields
- For `MutationResult` with a real entry, build a `QueueEntry` directly:
  ```python
  from docent.bundled_plugins.reading import QueueEntry
  entry = QueueEntry(id="smith-2024-foo", mendeley_id="abc123", added="2024-01-01")
  ```
- Run `uv run pytest tests/test_shapes.py -v` after writing and fix any failures

## Verify
```
cd C:\Users\DELL\Desktop\Docent
uv run pytest tests/test_shapes.py -v --tb=short
```
All tests should pass.

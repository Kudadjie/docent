# Task: Add `to_shapes()` to reading result types + update `__rich_console__`

File to edit: `src/docent/bundled_plugins/reading/__init__.py`
Project root: `C:\Users\DELL\Desktop\Docent`

## Context

`src/docent/core/shapes.py` exists with these shape types (all Pydantic BaseModels with a discriminated `type` field):
- `MarkdownShape(content: str)`
- `DataTableShape(columns: list[str], rows: list[list[str]])`
- `MetricShape(label: str, value: str|int|float, unit: str|None=None)`
- `LinkShape(label: str, url: str)`
- `MessageShape(text: str, level: Literal["info","success","warning","error"]="info")`
- `ErrorShape(reason: str, hint: str|None=None)`
- `ProgressShape(phase: str, message: str="", current: int|None=None, total: int|None=None, level: Literal["info","warn","error"]="info")`

`src/docent/ui/renderers.py` will exist with:
```python
def render_shapes(shapes: list[Shape], console: Console) -> None: ...
```

## What to change

For each result type in `src/docent/bundled_plugins/reading/__init__.py`, do TWO things:

1. Add a `to_shapes(self) -> list[Shape]` method that returns a `list[Shape]` equivalent to the current `__rich_console__` output.
2. Update `__rich_console__` to delegate entirely to `render_shapes`:
   ```python
   def __rich_console__(self, console, options):
       from docent.ui.renderers import render_shapes
       render_shapes(self.to_shapes(), console)
   ```
   (Keep the lazy import inside `__rich_console__` to avoid circular imports.)

## Result types to update (all 10)

### 1. `AddResult`
Current output: a cyan Panel with guidance message, then dim queue size text.
`to_shapes()` should return:
- `MarkdownShape(content=self.message)`
- `MessageShape(text=f"Queue: {self.queue_size} entries", level="info")`

### 2. `MutationResult`
Current output: on failure → red text; on success → cyan Panel with title/authors/meta then dim message.
`to_shapes()` should return:
- On `not self.ok or self.entry is None`: `[ErrorShape(reason=self.message)]`
- On success, build `content` string exactly as the current `__rich_console__` builds it (bold title, dim authors·year, Order/Status/Type/Category/Deadline, DOI, notes), then:
  - `MarkdownShape(content=content)` — use plain text, not Rich markup (strip `[bold]`, `[dim]`, etc. — render_shapes will style it naturally)
  - If `self.message`: `MessageShape(text=self.message, level="info")`

  **Important:** For `MutationResult`, keep `to_shapes()` simple: return a `MarkdownShape` with the plain-text entry summary (no Rich markup tags in the content), plus an optional `MessageShape` for the message field.

### 3. `SearchResult`
Current output: bold match count text, then a Rich Table.
`to_shapes()` should return:
- `MessageShape(text=f"{self.total} {'match' if self.total == 1 else 'matches'} for {self.query!r}", level="info")`
- If matches: `DataTableShape(columns=["#", "Title", "Authors", "Year", "Type", "Category", "Status"], rows=[...])`
  where each row is `[str(e.order), e.title, e.authors if e.authors != "Unknown" else "", str(e.year) if e.year else "", etype, e.category or "", e.status]`

### 4. `StatsResult`
Current output: cyan Panel with total + by_status + by_category breakdown.
`to_shapes()` should return:
- `MetricShape(label="Total", value=self.total, unit="entries")`
- `DataTableShape(columns=["Status", "Count"], rows=[[k, str(v)] for k, v in sorted(self.by_status.items())])`
- If `self.by_category`: `DataTableShape(columns=["Category", "Count"], rows=[[k or "(none)", str(v)] for k, v in sorted(self.by_category.items())])`

### 5. `ExportResult`
Current output: dim exported count, then the content text.
`to_shapes()` should return:
- `MessageShape(text=f"Exported {self.count} entries ({self.format})", level="info")`
- `MarkdownShape(content=self.content)`

### 6. `QueueClearResult`
Current output: green or yellow text with message.
`to_shapes()` should return:
- `MessageShape(text=self.message, level="success" if self.cleared else "warning")`

### 7. `ConfigShowResult`
Current output: cyan Panel with config_path, database_dir, queue_collection.
`to_shapes()` should return:
- `MetricShape(label="Config", value=self.config_path)`
- `MetricShape(label="database_dir", value=self.database_dir or "(not set)")`
- `MetricShape(label="queue_collection", value=self.queue_collection)`

### 8. `ConfigSetResult`
Current output: green or red text with message.
`to_shapes()` should return:
- `MessageShape(text=self.message, level="success" if self.ok else "error")`

### 9. `SyncFromMendeleyResult`
Current output: yellow message on early exit; otherwise cyan Panel with collection/added/unchanged/removed/failed counts and a bullet list of added items.
`to_shapes()` should return:
- If `self.message`: `[MessageShape(text=self.message, level="warning")]`
- Otherwise:
  - `MessageShape(text=f"Collection: {self.queue_collection}", level="info")`
  - Build a stats markdown string with added/unchanged/removed/failed counts (handle dry-run variants):
    `MetricShape(label="Added", value=len(actual_added))`, `MetricShape(label="Unchanged", value=len(self.unchanged))`, `MetricShape(label="Removed", value=len(actual_removed))`, `MetricShape(label="Failed", value=len(self.failed))`
  - If added items: `DataTableShape(columns=["id", "title"], rows=[[item.get("id",""), item.get("title","")[:60]] for item in actual_added[:10]])`
  - If failed: `DataTableShape(columns=["mendeley_id", "error"], rows=[[item.get("mendeley_id","")[:12], item.get("error","")] for item in self.failed])`

### 10. `SyncStatusResult`
Current output: cyan Panel with database_dir, queue_size, pdf count, optional message.
`to_shapes()` should return:
- `MetricShape(label="Database", value=self.database_dir or "(not configured)")`
- `MetricShape(label="Queue", value=self.queue_size, unit="entries")`
- `MetricShape(label="PDFs in database", value=len(self.database_pdfs))`
- If `self.message`: `MessageShape(text=self.message, level="warning")`

## Import to add at the top of the file

Add this import alongside the existing imports:
```python
from docent.core.shapes import (
    DataTableShape,
    ErrorShape,
    LinkShape,
    MarkdownShape,
    MessageShape,
    MetricShape,
    ProgressShape,
    Shape,
)
```

## Rules
- Do NOT remove or rename any existing fields, methods, or classes
- Do NOT change any action method signatures
- The `__rich_console__` methods must delegate to `render_shapes` via a lazy import (inside the method body)
- Keep `to_shapes()` free of Rich markup strings (no `[bold]`, `[dim]` etc. in shape content — that's the renderer's job)
- Run `uv run pytest` after changes and fix any test failures before declaring done

## Verify
```
cd C:\Users\DELL\Desktop\Docent
uv run pytest --tb=short -q
uv run python -c "
from docent.bundled_plugins.reading import MutationResult, SearchResult, StatsResult
from docent.bundled_plugins.reading.reading_store import BannerCounts
b = BannerCounts(queued=1, reading=0, done=0, removed=0, overdue=0)
r = StatsResult(total=5, by_status={'queued':5}, by_category={'CES701':3,'(root)':2}, banner=b)
shapes = r.to_shapes()
print([s.type for s in shapes])
"
```
Should print a list like `['metric', 'data_table', 'data_table']` and all pytest tests should pass.

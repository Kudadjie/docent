# Task: Create `src/docent/ui/renderers.py`

Create the file `src/docent/ui/renderers.py` in the Docent project (root: `C:\Users\DELL\Desktop\Docent`).

## Context

`src/docent/core/shapes.py` already exists with these types:
- `MarkdownShape(type, content: str)`
- `DataTableShape(type, columns: list[str], rows: list[list[str]])`
- `MetricShape(type, label: str, value: str|int|float, unit: str|None)`
- `LinkShape(type, label: str, url: str)`
- `MessageShape(type, text: str, level: Literal["info","success","warning","error"])`
- `ErrorShape(type, reason: str, hint: str|None)`
- `ProgressShape(type, phase: str, message: str, current: int|None, total: int|None, level: Literal["info","warn","error"])`

The `Shape` union is discriminated on the `type` field.

`src/docent/ui/console.py` already exists and has `get_console()` returning a Rich `Console`.

## What to build

`src/docent/ui/renderers.py` — a `render_shapes(shapes, console)` function that dispatches each shape to a Rich renderer.

## Implementation

```python
from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

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

_LEVEL_STYLE: dict[str, str] = {
    "info": "dim",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "warn": "yellow",
}


def render_shapes(shapes: list[Shape], console: Console) -> None:
    """Render a list of shapes to the given Rich console."""
    for shape in shapes:
        _render_one(shape, console)


def _render_one(shape: Shape, console: Console) -> None:
    match shape.type:
        case "markdown":
            console.print(Markdown(shape.content))
        case "data_table":
            _render_table(shape, console)
        case "metric":
            value_str = f"{shape.value}"
            if shape.unit:
                value_str = f"{shape.value} {shape.unit}"
            console.print(Text.assemble(
                (shape.label + ": ", "bold"),
                (value_str, "cyan"),
            ))
        case "link":
            console.print(Text.assemble(
                (shape.label + ": ", "dim"),
                (shape.url, "blue underline"),
            ))
        case "message":
            style = _LEVEL_STYLE.get(shape.level, "")
            console.print(Text(shape.text, style=style))
        case "error":
            console.print(Text(f"Error: {shape.reason}", style="red bold"))
            if shape.hint:
                console.print(Text(f"  Hint: {shape.hint}", style="dim"))
        case "progress":
            style = _LEVEL_STYLE.get(shape.level, "dim")
            if shape.current is not None and shape.total is not None:
                prefix = f"[{shape.current}/{shape.total}] "
            else:
                prefix = f"[{shape.phase}] "
            console.print(Text(prefix + shape.message, style=style))


def _render_table(shape: DataTableShape, console: Console) -> None:
    table = Table(show_header=True, header_style="bold dim", box=None, padding=(0, 1))
    for col in shape.columns:
        table.add_column(col)
    for row in shape.rows:
        padded = row + [""] * max(0, len(shape.columns) - len(row))
        table.add_row(*padded[:len(shape.columns)])
    console.print(table)
```

## Rules
- Use `from __future__ import annotations` at top
- No docstrings or extra comments
- Do NOT modify any other files
- ~65 lines total

## Verify
```
cd C:\Users\DELL\Desktop\Docent
uv run python -c "from docent.ui.renderers import render_shapes; print('ok')"
```
Should print `ok`.

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from docent.core.shapes import (
    DataTableShape,
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

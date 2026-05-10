# Task: Create `src/docent/core/shapes.py`

Create the file `src/docent/core/shapes.py` in the Docent project (root: `C:\Users\DELL\Desktop\Docent`).

## What to build

A fixed vocabulary of 7 output shape types as Pydantic v2 `BaseModel` subclasses, plus a `Shape` union type.

The shapes are the wire format between tool actions and any renderer (CLI, FastAPI, frontend). Each shape is small and self-contained.

## Exact shape definitions

```python
from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


class MarkdownShape(BaseModel):
    type: Literal["markdown"] = "markdown"
    content: str  # markdown-formatted prose


class DataTableShape(BaseModel):
    type: Literal["data_table"] = "data_table"
    columns: list[str]
    rows: list[list[str]]  # each row length == len(columns)


class MetricShape(BaseModel):
    type: Literal["metric"] = "metric"
    label: str
    value: str | int | float
    unit: str | None = None


class LinkShape(BaseModel):
    type: Literal["link"] = "link"
    label: str
    url: str  # URL or file path


class MessageShape(BaseModel):
    type: Literal["message"] = "message"
    text: str
    level: Literal["info", "success", "warning", "error"] = "info"


class ErrorShape(BaseModel):
    type: Literal["error"] = "error"
    reason: str
    hint: str | None = None  # optional actionable hint


class ProgressShape(BaseModel):
    type: Literal["progress"] = "progress"
    phase: str
    message: str = ""
    current: int | None = None
    total: int | None = None
    level: Literal["info", "warn", "error"] = "info"


Shape = Annotated[
    Union[
        MarkdownShape,
        DataTableShape,
        MetricShape,
        LinkShape,
        MessageShape,
        ErrorShape,
        ProgressShape,
    ],
    Field(discriminator="type"),
]
```

## Rules
- Use `from __future__ import annotations` at the top
- Do NOT add any comments or docstrings beyond what's shown above
- Do NOT add any helper functions, renderers, or imports beyond pydantic/typing
- Do NOT modify any other files
- The file should be ~50 lines total

## Verify
After writing the file, verify it imports cleanly:
```
cd C:\Users\DELL\Desktop\Docent
uv run python -c "from docent.core.shapes import Shape, MarkdownShape, DataTableShape, MetricShape, LinkShape, MessageShape, ErrorShape, ProgressShape; print('ok')"
```
It should print `ok`.

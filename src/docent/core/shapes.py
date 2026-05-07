from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


class MarkdownShape(BaseModel):
    type: Literal["markdown"] = "markdown"
    content: str


class DataTableShape(BaseModel):
    type: Literal["data_table"] = "data_table"
    columns: list[str]
    rows: list[list[str]]


class MetricShape(BaseModel):
    type: Literal["metric"] = "metric"
    label: str
    value: str | int | float
    unit: str | None = None


class LinkShape(BaseModel):
    type: Literal["link"] = "link"
    label: str
    url: str


class MessageShape(BaseModel):
    type: Literal["message"] = "message"
    text: str
    level: Literal["info", "success", "warning", "error"] = "info"


class ErrorShape(BaseModel):
    type: Literal["error"] = "error"
    reason: str
    hint: str | None = None


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

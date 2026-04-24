from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from docent.core.context import Context


class Tool(ABC):
    """Base class for every Docent tool.

    Metadata lives as class attributes so the registry — and later the UI —
    can read it without constructing an instance. Instances are created on
    demand, per invocation, by the CLI or the UI server.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    category: ClassVar[str | None] = None
    input_schema: ClassVar[type[BaseModel]]

    @abstractmethod
    def run(self, inputs: BaseModel, context: Context) -> Any:
        """Execute the tool. `inputs` is already validated against `input_schema`."""

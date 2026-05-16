from __future__ import annotations

from dataclasses import dataclass

from docent.config import Settings
from docent.execution import Executor
from docent.llm import LLMClient


@dataclass(frozen=True)
class Context:
    settings: Settings
    llm: LLMClient
    executor: Executor
    via_mcp: bool = False

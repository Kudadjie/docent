from __future__ import annotations

from dataclasses import dataclass, field

from docent.config import Settings
from docent.execution import Executor
from docent.llm import LLMClient


@dataclass(frozen=True)
class Context:
    """Runtime context threaded through every tool invocation.

    ``frozen=True`` prevents reassigning fields after construction (e.g.
    ``context.settings = other`` raises ``FrozenInstanceError``).  It does
    *not* make mutable containers immutable — ``mcp_notes`` is intentionally
    mutable so preflights and actions can append notes that the MCP/SSE layer
    collects after the call returns.  This is the one sanctioned mutation point;
    all other state changes must go through the tool's Store or Settings.
    """

    settings: Settings
    llm: LLMClient
    executor: Executor
    via_mcp: bool = False
    mcp_notes: list[str] = field(default_factory=list)  # intentionally mutable; see docstring

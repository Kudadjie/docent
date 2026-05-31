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
    # Three orthogonal flags — previously conflated under a single `via_mcp`:
    #   via_mcp         — the caller is an MCP agent. Governs MCP-only behaviour:
    #                     collecting `mcp_notes` and emitting AI-agent synthesis
    #                     framing in research output. Set only by the MCP server.
    #   non_interactive — no TTY / no Rich prompts. Preflights raise structured
    #                     errors instead of printing + typer.Exit, and skip
    #                     console spinners. True for MCP *and* the web UI.
    #   auto_confirm    — skip human confirmation gates (consent). True for MCP
    #                     and the web UI, where the user already clicked through.
    # Keeping these distinct means "the UI auto-accepts confirmations" is an
    # explicit, visible decision rather than a side effect of "is this MCP?".
    via_mcp: bool = False
    non_interactive: bool = False
    auto_confirm: bool = False
    mcp_notes: list[str] = field(default_factory=list)  # intentionally mutable; see docstring

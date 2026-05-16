"""Central action dispatcher.

Single source of truth for context creation, tool+action lookup, input
coercion, and method dispatch.  Each surface (CLI, MCP, FastAPI) handles its
own result rendering and generator draining on top of run_action().

Usage
-----
MCP / FastAPI (no pre-existing context)::

    from docent.core.invoke import run_action
    result = run_action("reading", "done", {"id": "smith-2024-x"})

CLI (context already in ctx.obj — pass it through)::

    # CLI builds Typer callbacks that call action methods directly;
    # run_action is available if a CLI command ever needs it.
    result = run_action("reading", "stats", {}, context=ctx.obj)
"""
from __future__ import annotations

from typing import Any

from docent.core.context import Context
from docent.core.registry import all_tools, collect_actions


def make_context(*, via_mcp: bool = False) -> Context:
    """Create a fresh Context with default settings, LLM client, and executor.

    Used by MCP and FastAPI, which have no persistent ctx.obj.
    CLI surfaces should use the Context already on ctx.obj.
    Pass via_mcp=True when building a context for the MCP server.
    """
    from docent.config import load_settings
    from docent.execution import Executor
    from docent.llm import LLMClient

    settings = load_settings()
    return Context(settings=settings, llm=LLMClient(settings), executor=Executor(), via_mcp=via_mcp)


def run_action(
    tool_name: str,
    action_cli_name: str,
    arguments: dict[str, Any],
    context: Context | None = None,
) -> Any:
    """Dispatch one action from a dict of raw arguments.

    Returns the raw result — either a Pydantic model, a plain value, or a
    generator (for streaming actions).  Callers are responsible for draining
    generators and serializing results.

    Parameters
    ----------
    tool_name:
        Registry name of the tool (e.g. ``"reading"``).
    action_cli_name:
        CLI name of the action (e.g. ``"sync-from-mendeley"``).
        For single-action tools use ``"run"``.
    arguments:
        Raw keyword arguments as a plain dict; validated against the action's
        input_schema before dispatch.
    context:
        Optional pre-built Context.  If None, make_context() is called.
        Pass ctx.obj here when a CLI command needs to use run_action directly
        so startup settings (verbose, no_color, etc.) are preserved.

    Raises
    ------
    ValueError
        Unknown tool name, unknown action name, or wrong action name for a
        single-action tool.
    pydantic.ValidationError
        Input dict fails the action's input_schema.
    """
    from pydantic import BaseModel

    tools = all_tools()
    if tool_name not in tools:
        raise ValueError(f"No tool named '{tool_name}'")

    tool_cls = tools[tool_name]
    actions = collect_actions(tool_cls)
    ctx = context if context is not None else make_context()

    if actions:
        if action_cli_name not in actions:
            raise ValueError(
                f"Tool '{tool_name}' has no action '{action_cli_name}'. "
                f"Available: {sorted(actions)}"
            )
        method_name, meta = actions[action_cli_name]
        inputs = meta.input_schema(**arguments)
        if meta.preflight is not None:
            try:
                meta.preflight(inputs, ctx)
            except SystemExit as exc:
                raise RuntimeError(
                    f"Preflight check failed for '{tool_name} {action_cli_name}'"
                ) from exc
            # ConfirmationRequired is intentional — let it bubble to the caller.
        return getattr(tool_cls(), method_name)(inputs, ctx)

    # Single-action tool — exposed over MCP as "{tool}__run".
    if action_cli_name != "run":
        raise ValueError(
            f"Tool '{tool_name}' is single-action — use 'run', not '{action_cli_name}'"
        )
    schema = tool_cls.input_schema
    inputs = schema(**arguments) if schema is not None else BaseModel()
    return tool_cls().run(inputs, ctx)

"""Step 13 — Full MCP adapter.

Exposes every registered Docent action as an MCP tool callable from Claude Code
(or any other MCP-compatible client) over stdio.

Tool naming convention: `{tool_name}__{action_name}` where the action's CLI name
has hyphens replaced by underscores.

  Example: reading tool's `sync-from-mendeley` → `reading__sync_from_mendeley`

The double-underscore separator is unambiguous: tool names are single-word
identifiers (`reading`, `paper`) and action names never contain `__`.

Usage:
    docent serve                     # recommended — loads plugins first

Claude Code .mcp.json:
    {
      "mcpServers": {
        "docent": {
          "command": "uv",
          "args": ["--directory", "<project-root>", "run", "docent", "serve"]
        }
      }
    }
"""
from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel

from docent.core import (
    ProgressEvent,
    all_tools,
    collect_actions,
    load_plugins,
    run_action,
)
from docent.tools import discover_tools


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

def mcp_tool_name(tool_name: str, action_cli_name: str) -> str:
    """Build the MCP tool name from a (tool, action) pair."""
    return f"{tool_name}__{action_cli_name.replace('-', '_')}"


def parse_mcp_tool_name(mcp_name: str) -> tuple[str, str] | None:
    """Return (tool_name, action_cli_name) or None if the name is not a Docent tool."""
    if "__" not in mcp_name:
        return None
    tool_name, action_part = mcp_name.split("__", 1)
    action_cli_name = action_part.replace("_", "-")
    return tool_name, action_cli_name


# ---------------------------------------------------------------------------
# Registry introspection
# ---------------------------------------------------------------------------

def build_mcp_tools() -> list[types.Tool]:
    """Return one MCP Tool descriptor per (tool, action) pair in the registry.

    Both multi-action tools (@action methods) and single-action tools
    (``input_schema`` + ``run()``) are exposed.  Single-action tools get
    the fixed MCP name ``{tool}__run``.
    """
    result = []
    for tool_name, tool_cls in sorted(all_tools().items()):
        actions = collect_actions(tool_cls)
        if actions:
            for action_cli_name, (_method, meta) in sorted(actions.items()):
                result.append(
                    types.Tool(
                        name=mcp_tool_name(tool_name, action_cli_name),
                        description=f"[{tool_name}] {meta.description}",
                        inputSchema=meta.input_schema.model_json_schema(),
                    )
                )
        else:
            # Single-action tool — expose via fixed "run" action name.
            assert tool_cls.input_schema is not None
            result.append(
                types.Tool(
                    name=mcp_tool_name(tool_name, "run"),
                    description=f"[{tool_name}] {tool_cls.description}",
                    inputSchema=tool_cls.input_schema.model_json_schema(),
                )
            )
    return result


# ---------------------------------------------------------------------------
# Action invocation
# ---------------------------------------------------------------------------

def _serialize(result: Any) -> str:
    if isinstance(result, BaseModel):
        return result.model_dump_json(indent=2)
    try:
        return json.dumps(result, indent=2, default=str)
    except Exception:
        return str(result)


def invoke_action(
    tool_name: str,
    action_cli_name: str,
    arguments: dict[str, Any],
) -> str:
    """Run one Docent action and return its result as a JSON string.

    Delegates dispatch to core.invoke.run_action.  Generator actions collect
    ProgressEvent messages as a prefix followed by the final JSON result —
    so MCP callers see the full execution trace in a single response.
    """
    raw = run_action(tool_name, action_cli_name, arguments)

    if inspect.isgenerator(raw):
        lines: list[str] = []
        try:
            while True:
                evt = next(raw)
                if isinstance(evt, ProgressEvent) and evt.message:
                    lines.append(f"[{evt.phase}] {evt.message}")
        except StopIteration as stop:
            lines.append(_serialize(stop.value))
        return "\n".join(lines)

    return _serialize(raw)


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

def run_server() -> None:
    """Load plugins, build the MCP tool list, and serve over stdio.

    Called by `docent serve`. Blocks until the client disconnects.
    """
    import sys
    discover_tools()
    load_plugins()
    tools = build_mcp_tools()
    print(f"[docent] MCP server ready — {len(tools)} tools registered. Waiting for client…", file=sys.stderr, flush=True)

    server = Server("docent")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return build_mcp_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        parsed = parse_mcp_tool_name(name)
        if parsed is None:
            return [types.TextContent(type="text", text=f"Unknown tool format: {name!r}")]
        tool_name, action_cli_name = parsed
        try:
            text = invoke_action(tool_name, action_cli_name, arguments or {})
            return [types.TextContent(type="text", text=text)]
        except Exception as exc:
            return [types.TextContent(type="text", text=f"Error: {exc}")]

    async def _serve() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(_serve())

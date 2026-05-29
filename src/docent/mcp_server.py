# ruff: noqa: E402 — warnings.filterwarnings must run before any scholarly import
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

import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module=r"scholarly")

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

def _mcp_input_schema(model: type) -> dict:
    """Return the JSON schema for an input model, adjusted for MCP callers.

    Strips the default from the ``backend`` field so MCP clients are forced
    to ask the user which backend they want rather than silently picking one.
    """
    schema = model.model_json_schema()
    props = schema.get("properties", {})
    if "backend" in props:
        props["backend"].pop("default", None)
        required = schema.setdefault("required", [])
        if "backend" not in required:
            required.append("backend")
    return schema


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
                        inputSchema=_mcp_input_schema(meta.input_schema),
                    )
                )
        else:
            # Single-action tool — expose via fixed "run" action name.
            if tool_cls.input_schema is None:
                raise ValueError(
                    f"Tool '{tool_name}' has no actions and no input_schema — "
                    "this should have been caught at registration time."
                )
            result.append(
                types.Tool(
                    name=mcp_tool_name(tool_name, "run"),
                    description=f"[{tool_name}] {tool_cls.description}",
                    inputSchema=_mcp_input_schema(tool_cls.input_schema),
                )
            )
    return result


# ---------------------------------------------------------------------------
# Action invocation
# ---------------------------------------------------------------------------

# Re-exported from core.invoke so callers that imported _serialize from here keep working.
from docent.core.invoke import serialize_result as _serialize  # noqa: F401


def _confirmation_payload(exc: Exception) -> str:
    return json.dumps({
        "ok": False,
        "confirmation_required": True,
        "notes": exc.notes,  # type: ignore[attr-defined]
        "message": (
            "Present the notes above to the user. "
            "Once they acknowledge, call this tool again with confirmed=true to proceed."
        ),
    }, indent=2)


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
    from docent.core.exceptions import ConfirmationRequired
    from docent.core.invoke import make_context
    mcp_context = make_context(via_mcp=True)
    try:
        raw = run_action(tool_name, action_cli_name, arguments, context=mcp_context)
    except ConfirmationRequired as exc:
        return _confirmation_payload(exc)

    lines: list[str] = []

    # Prepend any preflight notes collected during MCP execution.
    for note in mcp_context.mcp_notes:
        lines.append(json.dumps({"note": note}))

    if inspect.isgenerator(raw):
        result_value = None
        try:
            while True:
                evt = next(raw)
                if isinstance(evt, ProgressEvent) and evt.message:
                    lines.append(f"[{evt.phase}] {evt.message}")
        except StopIteration as stop:
            result_value = stop.value
            lines.append(_serialize(result_value))
        _maybe_inline_research_output(lines, result_value)
        return "\n".join(lines)

    lines.append(_serialize(raw))
    _maybe_inline_research_output(lines, raw)
    return "\n".join(lines)


def _maybe_inline_research_output(lines: list[str], result: Any) -> None:
    """For successful free-tier results, append a lightweight structural summary
    (section headers + source count) so the MCP client can make a tailored
    synthesis offer without inlining the full document.

    Full content is only fetched when the user explicitly asks for synthesis,
    via the studio__read_output tool.
    """
    import re
    from pathlib import Path

    if not isinstance(result, BaseModel):
        return
    result_dict = result.model_dump()
    if not result_dict.get("ok") or result_dict.get("backend") != "free":
        return
    output_file = result_dict.get("output_file")
    if not output_file:
        return

    try:
        content = Path(output_file).read_text(encoding="utf-8")
    except OSError:
        return

    headers = re.findall(r"^#{1,3} .+", content, re.MULTILINE)
    source_count = len(re.findall(r"^[-*] \*\*", content, re.MULTILINE))
    word_count = len(content.split())
    topic = result_dict.get("topic_or_artifact", "the research topic")

    # Plain-text instruction block first — Claude treats JSON field values as data,
    # not directives. Top-level text is read as instructions.
    instructions = (
        f"\n\n=== FREE-TIER RESEARCH COMPLETE ===\n"
        f"Docent has compiled {source_count} sources on '{topic}'. "
        "Ask the user if they'd like you to proceed with any of the following, "
        "or do whichever steps the user has already authorised:\n\n"
        "SUGGESTED STEP 1 — YOUR OWN RESEARCH: Use your web search and knowledge to research "
        f"'{topic}' independently. Find additional sources, recent developments, "
        "key researchers, and angles Docent's pipeline may have missed.\n\n"
        "SUGGESTED STEP 2 — READ DOCENT OUTPUT: Call studio__read_output with the output_file "
        "path below to get the full source compilation.\n\n"
        "SUGGESTED STEP 3 — SYNTHESISE: Merge both streams into a comprehensive research brief: "
        "executive summary, key themes, critical analysis, research gaps, next steps. "
        "Tailor depth and framing to the user's context.\n\n"
        "SUGGESTED STEP 4 — SAVE: Call studio__save_synthesis with:\n"
        f"  source_output_file = '{output_file}'\n"
        "  content = the full synthesis text\n"
        "  summary = a concise 3-5 paragraph version for display in chat\n\n"
        "If you proceed: show only the summary in chat, then tell the user the two file paths "
        "(raw compilation and AI synthesis). Offer next steps: "
        "NotebookLM push (studio__to_notebook), more searches (studio__scholarly_search).\n"
        "====================================\n\n"
        "Metadata:\n"
    )
    metadata = {
        "output_file": output_file,
        "word_count": word_count,
        "source_count": source_count,
        "sections": headers[:30],
    }
    lines.append(instructions + json.dumps(metadata, indent=2))


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

def run_server() -> None:
    """Load plugins, build the MCP tool list, and serve over stdio.

    Called by `docent serve`. Blocks until the client disconnects.
    """
    import sys
    from docent.ui.console import configure_console
    # Redirect Rich console to stderr — stdout must stay clean for JSON-RPC.
    configure_console(stderr=True)
    discover_tools()
    load_plugins()
    tools = build_mcp_tools()
    print(f"[docent] MCP server ready — {len(tools)} tools registered. Waiting for client…", file=sys.stderr, flush=True)

    from docent._version import __version__
    server = Server("Docent", version=__version__)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        # Reuse the list built above — the registry is fixed after load_plugins(),
        # so there's no need to rebuild on every list_tools request.
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        parsed = parse_mcp_tool_name(name)
        if parsed is None:
            return [types.TextContent(type="text", text=f"Unknown tool format: {name!r}")]
        tool_name, action_cli_name = parsed

        # Capture session for streaming notifications — keeps long pipelines alive.
        try:
            req_ctx = server.request_context
            session = req_ctx.session
            request_id = req_ctx.request_id
            meta = req_ctx.meta
            progress_token = getattr(meta, "progressToken", None) if meta else None
        except LookupError:
            session = None
            request_id = None
            progress_token = None

        from docent.core.exceptions import ConfirmationRequired
        from docent.core.invoke import make_context, run_action

        mcp_context = make_context(via_mcp=True)

        try:
            raw = run_action(tool_name, action_cli_name, arguments or {}, context=mcp_context)
        except ConfirmationRequired as exc:
            return [types.TextContent(type="text", text=_confirmation_payload(exc))]
        except Exception as exc:
            return [types.TextContent(type="text", text=f"Error: {exc}")]

        lines: list[str] = []

        if not inspect.isgenerator(raw):
            # Non-streaming result — return immediately.
            for note in mcp_context.mcp_notes:
                lines.append(json.dumps({"note": note}))
            lines.append(_serialize(raw))
            _maybe_inline_research_output(lines, raw)
            return [types.TextContent(type="text", text="\n".join(lines))]

        # Streaming path: drain generator in a thread, forward each ProgressEvent
        # as a log notification so the MCP connection stays alive during long pipelines.
        event_queue: asyncio.Queue = asyncio.Queue()
        cur_loop = asyncio.get_running_loop()
        # ProgressEvent.level → MCP LoggingLevel
        _level_map = {"info": "info", "warn": "warning", "error": "error"}

        def _drain_generator() -> None:
            try:
                while True:
                    try:
                        evt = next(raw)
                        cur_loop.call_soon_threadsafe(event_queue.put_nowait, ("event", evt))
                    except StopIteration as stop:
                        cur_loop.call_soon_threadsafe(event_queue.put_nowait, ("done", stop.value))
                        return
            except Exception as exc:
                cur_loop.call_soon_threadsafe(event_queue.put_nowait, ("error", exc))

        drain_future = cur_loop.run_in_executor(None, _drain_generator)
        result_value = None
        progress_count = 0

        while True:
            kind, payload = await event_queue.get()

            if kind == "event":
                if isinstance(payload, ProgressEvent) and payload.message:
                    line = f"[{payload.phase}] {payload.message}"
                    lines.append(line)
                    if session is not None:
                        try:
                            await session.send_log_message(
                                level=_level_map.get(payload.level, "info"),
                                data=line,
                                related_request_id=request_id,
                            )
                        except Exception:
                            pass
                        if progress_token is not None:
                            progress_count += 1
                            try:
                                await session.send_progress_notification(
                                    progress_token=progress_token,
                                    progress=float(progress_count),
                                    message=line,
                                    related_request_id=str(request_id) if request_id else None,
                                )
                            except Exception:
                                pass

            elif kind == "done":
                result_value = payload
                break

            elif kind == "error":
                await drain_future
                return [types.TextContent(type="text", text=f"Error: {payload}")]

        await drain_future

        for note in mcp_context.mcp_notes:
            lines.append(json.dumps({"note": note}))

        lines.append(_serialize(result_value))
        _maybe_inline_research_output(lines, result_value)
        return [types.TextContent(type="text", text="\n".join(lines))]

    async def _serve() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(_serve())

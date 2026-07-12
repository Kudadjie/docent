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
from typing import Any, Literal, cast

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


def _mcp_input_schema(model: type[BaseModel]) -> dict:
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

# ---------------------------------------------------------------------------
# Async-by-default routing for long-running actions (ADR-006)
# ---------------------------------------------------------------------------
# These (tool, action) pairs run multi-minute pipelines that cannot complete
# inside an MCP tool-call timeout. Over MCP they are submitted as background
# jobs and the caller polls jobs__status / jobs__result instead. The `free`
# backend is the exception — it is aggregation-only and fast enough to run
# inline (and its inline flow drives the synthesis-offer UX).

_ASYNC_ACTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("studio", "deep-research"),
        ("studio", "lit"),
        ("studio", "review"),
        ("studio", "to-notebook"),
    }
)


def _should_run_async(tool_name: str, action_cli_name: str, arguments: dict[str, Any]) -> bool:
    if (tool_name, action_cli_name) not in _ASYNC_ACTIONS:
        return False
    backend = str(arguments.get("backend") or "").strip().lower()
    return backend != "free"


def _submit_async_job(tool_name: str, action_cli_name: str, arguments: dict[str, Any]) -> str:
    from docent.core.jobs import get_job_manager

    job = get_job_manager().submit(tool_name, action_cli_name, arguments, via_mcp=True)
    return json.dumps(
        {
            "ok": True,
            "async": True,
            "job_id": job.id,
            "state": job.state,
            "message": (
                f"'{tool_name} {action_cli_name}' runs a long pipeline, so it was "
                f"started as background job {job.id}. Poll jobs__status with "
                f"id='{job.id}' every 30-60 seconds; when state is 'done', call "
                "jobs__result to fetch the output. Tell the user the job is running "
                "and roughly how to check on it."
            ),
            "note": (
                "The job runs inside this Docent server process — if the server "
                "exits before completion the job is marked 'interrupted'."
            ),
        },
        indent=2,
    )


def _confirmation_payload(exc: Exception) -> str:
    return json.dumps(
        {
            "ok": False,
            "confirmation_required": True,
            "notes": exc.notes,  # type: ignore[attr-defined]
            "message": (
                "Present the notes above to the user. "
                "Once they acknowledge, call this tool again with confirmed=true to proceed."
            ),
        },
        indent=2,
    )


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

    if _should_run_async(tool_name, action_cli_name, arguments):
        return _submit_async_job(tool_name, action_cli_name, arguments)

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

    # Terse by design: heavy scripted choreography in tool output is brittle
    # across MCP clients and blurs the data/instruction boundary. The full
    # synthesis workflow lives in the studio tool descriptions and docs.
    instructions = (
        f"\n\nFree-tier research complete: {source_count} sources on '{topic}'.\n"
        "Offer the user a synthesis: read the compilation via studio__read_output, "
        "optionally add your own research, then save with studio__save_synthesis "
        f"(source_output_file='{output_file}', content=full text, summary=3-5 "
        "paragraphs for chat). Proceed only with the user's go-ahead.\n\n"
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
# MCP server construction
# ---------------------------------------------------------------------------


def build_mcp_server() -> Server:
    """Build and return a configured MCP Server from the current registry state.

    Caller must have invoked ``discover_tools()`` + ``load_plugins()`` first so
    the registry is fully populated before ``build_mcp_tools()`` is called here.
    Used by both the stdio path (``run_server``) and the HTTP path
    (``mount_mcp_sse``).
    """
    from docent._version import __version__

    tools = build_mcp_tools()
    server = Server("Docent", version=__version__)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        # Snapshot taken at construction time — registry is fixed after load_plugins().
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

        if _should_run_async(tool_name, action_cli_name, arguments or {}):
            payload = _submit_async_job(tool_name, action_cli_name, arguments or {})
            return [types.TextContent(type="text", text=payload)]

        mcp_context = make_context(via_mcp=True)

        try:
            raw = run_action(tool_name, action_cli_name, arguments or {}, context=mcp_context)
        except ConfirmationRequired as exc:
            return [types.TextContent(type="text", text=_confirmation_payload(exc))]
        except Exception as exc:
            return [types.TextContent(type="text", text=f"Error: {exc}")]

        lines: list[str] = []

        if not inspect.isgenerator(raw):
            for note in mcp_context.mcp_notes:
                lines.append(json.dumps({"note": note}))
            lines.append(_serialize(raw))
            _maybe_inline_research_output(lines, raw)
            return [types.TextContent(type="text", text="\n".join(lines))]

        # Streaming path: drain generator in a thread, forward each ProgressEvent
        # as a log notification so the MCP connection stays alive during long pipelines.
        event_queue: asyncio.Queue = asyncio.Queue()
        cur_loop = asyncio.get_running_loop()
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
                                level=cast(
                                    Literal[
                                        "debug",
                                        "info",
                                        "notice",
                                        "warning",
                                        "error",
                                        "critical",
                                        "alert",
                                        "emergency",
                                    ],
                                    _level_map.get(payload.level, "info"),
                                ),
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

    return server


def mount_mcp_sse(app: Any, api_key: str) -> None:
    """Mount MCP HTTP+SSE transport on an existing FastAPI app.

    Routes added:
      GET  /mcp/sse        — SSE stream (server → client)
      POST /mcp/messages/  — client → server messages

    Both routes require ``Authorization: Bearer <api_key>``.
    Call after ``discover_tools()`` + ``load_plugins()`` have been invoked.
    """
    from fastapi import Depends, HTTPException, Request
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from mcp.server.sse import SseServerTransport

    sse = SseServerTransport("/mcp/messages/")
    server = build_mcp_server()

    security = HTTPBearer(auto_error=False)

    def _require_key(
        creds: HTTPAuthorizationCredentials | None = Depends(security),
    ) -> None:
        import secrets as _secrets

        # compare_digest: constant-time — /mcp/* is intentionally reachable from
        # remote clients, so timing must not leak key bytes.
        if creds is None or not _secrets.compare_digest(creds.credentials, api_key):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    @app.get("/mcp/sse", dependencies=[Depends(_require_key)])
    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    @app.post("/mcp/messages/", dependencies=[Depends(_require_key)])
    async def handle_post_message(request: Request) -> None:
        await sse.handle_post_message(request.scope, request.receive, request._send)


# ---------------------------------------------------------------------------
# stdio server (docent serve)
# ---------------------------------------------------------------------------


def run_server() -> None:
    """Load plugins, build the MCP tool list, and serve over stdio.

    Called by ``docent serve``. Blocks until the client disconnects.
    """
    import sys

    from docent.ui.console import configure_console

    # Redirect Rich console to stderr — stdout must stay clean for JSON-RPC.
    configure_console(stderr=True)
    discover_tools()
    load_plugins()
    server = build_mcp_server()
    print(
        f"[docent] MCP server ready — {len(build_mcp_tools())} tools registered."
        " Waiting for client…",
        file=sys.stderr,
        flush=True,
    )

    async def _serve() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(_serve())

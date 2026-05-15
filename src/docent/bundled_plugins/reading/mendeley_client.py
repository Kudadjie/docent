"""Mendeley MCP client wrapper - sync facade over the async `mcp` SDK.

Step 11.4. Spawn-per-call: each call launches the Mendeley MCP server as a
subprocess via stdio, runs one `call_tool`, and tears down. Step 11.9 retired
`lookup_doi` / `search_library` (sync-mendeley subsumed by sync-from-mendeley);
only `list_folders` and `list_documents` remain — both feeding the Mendeley
read-through cache used by paper readers.

Return shape is `{"items": list, "error": str | None}`:

- success      -> {"items": [...], "error": None} (items may be empty = not found)
- auth failure -> {"items": [], "error": "auth: ..."}
- transport    -> {"items": [], "error": "transport: ..."}
- tool error   -> {"items": [], "error": "tool: ..."}

Callers bucket on `error` prefix. Lazy-imports `mcp` so importing this
module is cheap; the SDK is only loaded when a function actually runs.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

DEFAULT_LAUNCH_COMMAND: list[str] = ["uvx", "mendeley-mcp"]


def _parse_text_payload(result: Any) -> Any:
    """MCP CallToolResult.content is a list of content blocks; the Mendeley
    server returns a single text block carrying JSON. Returns the parsed
    JSON value (may be dict, list, or scalar) or None if the shape is off.
    """
    try:
        block = result.content[0]
    except (AttributeError, IndexError):
        return None
    text = getattr(block, "text", None)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _classify_error(message: str) -> str:
    low = message.lower()
    if any(s in low for s in ("auth", "token", "credential", "401", "403", "unauthor")):
        return "auth"
    return "tool"


async def _call_tool(launch_command: list[str], tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    # Lazy import: keeps `paper.py` import path free of the mcp SDK.
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    if not launch_command:
        return {"items": [], "error": "transport: empty launch command", "maybe_truncated": False}

    params = StdioServerParameters(
        command=launch_command[0],
        args=list(launch_command[1:]),
        env=None,
    )

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
    except FileNotFoundError as e:
        return {"items": [], "error": f"transport: launch command not found ({e})", "maybe_truncated": False}
    except Exception as e:  # noqa: BLE001 — surfaces stdio_client / session errors uniformly.
        return {"items": [], "error": f"transport: {type(e).__name__}: {e}", "maybe_truncated": False}

    parsed = _parse_text_payload(result)

    if getattr(result, "isError", False):
        if isinstance(parsed, dict) and parsed.get("error"):
            msg = str(parsed["error"])
        else:
            msg = "tool returned error"
        return {"items": [], "error": f"{_classify_error(msg)}: {msg}", "maybe_truncated": False}

    if parsed is None:
        return {"items": [], "error": "tool: unparseable response", "maybe_truncated": False}

    # Some tool error paths return a JSON dict with an `error` key but no isError flag.
    if isinstance(parsed, dict) and "error" in parsed and len(parsed) == 1:
        msg = str(parsed["error"])
        return {"items": [], "error": f"{_classify_error(msg)}: {msg}", "maybe_truncated": False}

    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        # Single-document response (mendeley_get_by_doi) or wrapped list.
        items = parsed.get("documents") or parsed.get("results") or parsed.get("items") or [parsed]
    else:
        items = [parsed]

    maybe_truncated = isinstance(arguments.get("limit"), int) and len(items) >= arguments["limit"]
    return {"items": items, "error": None, "maybe_truncated": maybe_truncated}


def _run(coro: Any) -> dict[str, Any]:
    return asyncio.run(coro)


def list_folders(launch_command: list[str] | None = None) -> dict[str, Any]:
    """Call Mendeley's `mendeley_list_folders`. Returns flat list of
    `{id, name, parent_id}`; nesting is encoded via `parent_id`. Used by
    `sync-from-mendeley` to resolve a configured collection name to its id."""
    cmd = launch_command or DEFAULT_LAUNCH_COMMAND
    return _run(_call_tool(cmd, "mendeley_list_folders", {}))


def list_documents(
    folder_id: str | None = None,
    launch_command: list[str] | None = None,
    limit: int = 200,
    sort_by: str = "last_modified",
) -> dict[str, Any]:
    """Call Mendeley's `mendeley_list_documents`. With `folder_id`, scopes
    to that collection; without, returns the whole library. Default limit
    bumped from 50 (MCP default) to 200 — a reading queue can plausibly hold
    that many. Documents above the limit are silently truncated; revisit if
    real-data queues grow past it."""
    cmd = launch_command or DEFAULT_LAUNCH_COMMAND
    args: dict[str, Any] = {"limit": limit, "sort_by": sort_by}
    if folder_id is not None:
        args["folder_id"] = folder_id
    return _run(_call_tool(cmd, "mendeley_list_documents", args))

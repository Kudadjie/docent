"""Generic tool/action introspection + invocation endpoints.

Powers the schema-driven `/tools` page in the web UI. Unlike the bespoke
Reading and Studio pages, this surface is fully generic: it reads every
registered tool's `@action` input schemas via `model_json_schema()` and the
frontend auto-generates a form from each. A new plugin dropped into
`~/.docent/plugins/` appears here with a working form and no React code.

Endpoints:
  GET  /api/tools          → tool/action catalogue with JSON schemas
  POST /api/tools/invoke   → run one action, return its JSON result

Note: generator (streaming) actions are drained synchronously and only the
final result is returned. Long-running Studio actions keep their dedicated
streaming page (`/studio`); this surface targets quick CRUD-style actions.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from docent.core.invoke import invoke_action_for_ui
from docent.core.registry import all_tools, collect_actions

router = APIRouter()


class InvokeBody(BaseModel):
    tool: str
    action: str  # CLI action name (e.g. "sync-from-mendeley"); "run" for single-action tools
    inputs: dict = {}


@router.get("/api/tools")
async def list_tools() -> JSONResponse:
    """Return every registered tool, its actions, and each action's JSON schema."""
    catalogue = []
    for tool_name, tool_cls in sorted(all_tools().items()):
        actions_meta = collect_actions(tool_cls)
        actions = []
        if actions_meta:
            for action_cli_name, (_method, meta) in sorted(actions_meta.items()):
                actions.append({
                    "action": action_cli_name,
                    "description": meta.description,
                    "schema": meta.input_schema.model_json_schema(),
                })
        elif tool_cls.input_schema is not None:
            # Single-action tool — exposed as the "run" action.
            actions.append({
                "action": "run",
                "description": tool_cls.description,
                "schema": tool_cls.input_schema.model_json_schema(),
            })
        catalogue.append({
            "tool": tool_name,
            "description": tool_cls.description,
            "category": tool_cls.category,
            "actions": actions,
        })
    return JSONResponse(catalogue)


@router.post("/api/tools/invoke")
async def invoke_tool(body: InvokeBody) -> JSONResponse:
    """Run one action and return its result.

    Returns ``{"ok": true, "result": <parsed JSON>}`` on success. Validation
    errors and runtime failures are surfaced as ``{"ok": false, "error": ...}``
    with a 400 status so the frontend can show a clear message.
    """
    try:
        # Run in a worker thread: actions may call asyncio.run() internally (e.g.
        # the Mendeley overlay), which fails inside this handler's running loop.
        raw = await asyncio.to_thread(
            invoke_action_for_ui, body.tool, body.action, body.inputs,
        )
    except ValueError as exc:
        # Unknown tool/action or wrong action name for a single-action tool.
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    except Exception as exc:  # pydantic ValidationError + any action-raised error
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    # invoke_action_for_ui returns a JSON string — parse it so the client gets
    # structured data, not a string-wrapped blob.
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = raw

    # A confirmation-required result is a successful HTTP response carrying a
    # gate the frontend must surface (e.g. queue-clear without confirmed=true).
    if isinstance(parsed, dict) and parsed.get("confirmation_required"):
        return JSONResponse({"ok": False, "confirmation_required": True, "result": parsed})

    return JSONResponse({"ok": True, "result": parsed})

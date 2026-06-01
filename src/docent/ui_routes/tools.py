"""Generic tool/action introspection + invocation endpoints.

Powers the schema-driven `/tools` page in the web UI. Unlike the bespoke
Reading and Studio pages, this surface is fully generic: it reads every
registered tool's `@action` input schemas via `model_json_schema()` and the
frontend auto-generates a form from each. A new plugin dropped into
`~/.docent/plugins/` appears here with a working form and no React code.

Endpoints:
  GET  /api/tools          → tool/action catalogue with JSON schemas
  POST /api/tools/invoke   → run one action, return its JSON result (sync)
  POST /api/tools/stream   → run one action, stream ProgressEvents + result as SSE
"""

from __future__ import annotations

import asyncio
import inspect
import json
import queue
import threading

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from docent.core.invoke import invoke_action_for_ui, make_context, run_action, serialize_result
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
                actions.append(
                    {
                        "action": action_cli_name,
                        "description": meta.description,
                        "schema": meta.input_schema.model_json_schema(),
                    }
                )
        elif tool_cls.input_schema is not None:
            # Single-action tool — exposed as the "run" action.
            actions.append(
                {
                    "action": "run",
                    "description": tool_cls.description,
                    "schema": tool_cls.input_schema.model_json_schema(),
                }
            )
        catalogue.append(
            {
                "tool": tool_name,
                "description": tool_cls.description,
                "category": tool_cls.category,
                "actions": actions,
            }
        )
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
            invoke_action_for_ui,
            body.tool,
            body.action,
            body.inputs,
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


@router.post("/api/tools/stream")
async def stream_tool(body: InvokeBody) -> StreamingResponse:
    """Run one action and stream its output as Server-Sent Events.

    Each event is a ``data: <json>\\n\\n`` line. Three event shapes:

    - ``{"type": "progress", "phase": "...", "message": "...", "level": "info"}``
      — intermediate ProgressEvent from a generator action
    - ``{"type": "result",  "ok": true,  "result": {...}}``
      — final result (generator drained or sync action completed)
    - ``{"type": "error",   "ok": false, "error": "...", ...}``
      — validation failure, unknown action, or runtime error

    Non-generator actions emit no progress events and go directly to ``result``.
    The frontend shows the telemetry strip only when progress events arrive.
    """
    from docent.core.events import ProgressEvent
    from docent.core.exceptions import ConfirmationRequired

    event_q: queue.Queue[str | None] = queue.Queue()

    def _worker() -> None:
        try:
            ctx = make_context(non_interactive=True, auto_confirm=True)
            raw = run_action(body.tool, body.action, body.inputs, context=ctx)
        except ConfirmationRequired as exc:
            event_q.put(
                json.dumps(
                    {
                        "type": "error",
                        "ok": False,
                        "confirmation_required": True,
                        "notes": exc.notes,
                    }
                )
            )
            event_q.put(None)
            return
        except (ValueError, Exception) as exc:
            event_q.put(json.dumps({"type": "error", "ok": False, "error": str(exc)}))
            event_q.put(None)
            return

        try:
            if inspect.isgenerator(raw):
                result_value = None
                try:
                    while True:
                        evt = next(raw)
                        if isinstance(evt, ProgressEvent):
                            event_q.put(json.dumps({"type": "progress", **evt.model_dump()}))
                        else:
                            result_value = evt
                except StopIteration as stop:
                    result_value = stop.value
            else:
                result_value = raw

            try:
                parsed = json.loads(serialize_result(result_value))
            except (json.JSONDecodeError, TypeError):
                parsed = str(result_value)

            if isinstance(parsed, dict) and parsed.get("confirmation_required"):
                event_q.put(
                    json.dumps(
                        {
                            "type": "error",
                            "ok": False,
                            "confirmation_required": True,
                            "result": parsed,
                        }
                    )
                )
            else:
                event_q.put(json.dumps({"type": "result", "ok": True, "result": parsed}))
        except Exception as exc:
            event_q.put(json.dumps({"type": "error", "ok": False, "error": str(exc)}))
        finally:
            event_q.put(None)

    threading.Thread(target=_worker, daemon=True).start()

    async def _generate():  # type: ignore[return]
        loop = asyncio.get_event_loop()
        while True:
            msg: str | None = await loop.run_in_executor(None, event_q.get)
            if msg is None:
                break
            yield f"data: {msg}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

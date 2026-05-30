"""Studio run SSE streaming endpoint + utility endpoints."""
import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from docent.ui_server import (
    StudioRunBody,
    _STUDIO_ACTION_MAP,
    _form_to_studio_args,
    _stream_studio_run,
)

router = APIRouter()


@router.post("/api/studio/run", response_model=None)
async def studio_run(body: StudioRunBody):
    if body.action_id not in _STUDIO_ACTION_MAP:
        return JSONResponse({"error": f"Unknown action: {body.action_id!r}"}, status_code=400)
    studio_action = _STUDIO_ACTION_MAP[body.action_id]
    args = _form_to_studio_args(body.action_id, body)
    return StreamingResponse(
        _stream_studio_run(studio_action, args),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/studio/tavily-usage")
async def get_tavily_usage() -> JSONResponse:
    """Return live Tavily credit usage for the configured API key."""
    try:
        from docent.config import load_settings
        from docent.bundled_plugins.studio.tavily_usage import fetch_tavily_usage

        settings = await asyncio.to_thread(load_settings)
        key = settings.research.tavily_api_key
        if not key:
            return JSONResponse({"ok": False, "message": "No Tavily API key configured."})

        data = await asyncio.to_thread(fetch_tavily_usage, key)
        key_data = data.get("key", {})
        account = data.get("account", {})
        plan_usage = account.get("plan_usage")
        plan_limit = account.get("plan_limit")
        plan = account.get("current_plan")
        key_search_usage = key_data.get("search_usage")

        pct: float | None = None
        if plan_usage is not None and plan_limit:
            pct = round(plan_usage / plan_limit * 100, 1)

        return JSONResponse({
            "ok": True,
            "plan": plan,
            "plan_usage": plan_usage,
            "plan_limit": plan_limit,
            "key_search_usage": key_search_usage,
            "pct_used": pct,
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=500)

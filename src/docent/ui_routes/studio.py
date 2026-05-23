"""Studio run SSE streaming endpoint."""
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

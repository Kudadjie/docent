"""Studio run SSE streaming endpoint and body models."""
import asyncio
import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse

router = APIRouter()
from pydantic import BaseModel

from docent.core.invoke import serialize_result as _serialize


class StudioRunBody(BaseModel):
    action_id: str
    topic: str = ""
    backend: str = "free"
    dest: str = "local"
    guides: list[str] = []
    artifact: str = ""
    artifact_a: str = ""
    artifact_b: str = ""
    query: str = ""
    max_results: int = 10
    arxiv_id: str = ""
    out_path: str = ""
    src_path: str = ""
    max_sources: int = 20
    nlm: bool = True
    gate: bool = True
    persp: bool = True
    cfg_key: str = ""
    cfg_val: str = ""


def _STUDIO_ACTION_MAP():
    from docent.ui_server import _STUDIO_ACTION_MAP as _sam
    return _sam


def _BACKEND_NORM():
    from docent.ui_server import _BACKEND_NORM as _bn
    return _bn


def _parse_studio_body(body: StudioRunBody):
    from docent.ui_server import _parse_studio_body as _psb
    return _psb(body)


def _form_to_studio_args(action_id: str, body: StudioRunBody):
    from docent.ui_server import _form_to_studio_args as _ftsa
    return _ftsa(action_id, body)


def _stream_studio_run(studio_action: str, args: dict[str, Any]):
    from docent.ui_server import _stream_studio_run as _ssr
    return _ssr(studio_action, args)


def _STUDIO_ACTION_MAP_dict():
    from docent.ui_server import _STUDIO_ACTION_MAP
    return _STUDIO_ACTION_MAP


@router.post("/api/studio/run")
async def studio_run(body: StudioRunBody):
    action_map = _STUDIO_ACTION_MAP_dict()
    if body.action_id not in action_map:
        return JSONResponse({'error': f'Unknown action: {body.action_id!r}'}, status_code=400)
    studio_action = action_map[body.action_id]
    args = _form_to_studio_args(body.action_id, body)
    return StreamingResponse(
        _stream_studio_run(studio_action, args),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )
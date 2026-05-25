"""Reading queue action endpoints."""
import asyncio
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

from docent.core.invoke import invoke_action_for_ui as invoke_action  # noqa: E402


class ActionBody(BaseModel):
    action: str
    id: Optional[str] = None
    status: Optional[str] = None
    order: Optional[int] = None
    deadline: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    confirmed: bool = False


_ACTION_MAP: dict[str, tuple[str, str]] = {
    "edit": ("reading", "edit"),
    "done": ("reading", "done"),
    "start": ("reading", "start"),
    "remove": ("reading", "remove"),
    "move-up": ("reading", "move-up"),
    "move-down": ("reading", "move-down"),
    "sync": ("reading", "sync-from-mendeley"),
    "queue-clear": ("reading", "queue-clear"),
    "clear-library-flag": ("reading", "clear-library-flag"),
}


def _read_config_reading():
    from docent.ui_server import _read_config_reading as _rcr
    return _rcr()


def _get_database_files(path):
    from docent.ui_server import _get_database_files as _gdf
    return _gdf(path)


def _audit(action: str, detail: str) -> None:
    from docent.ui_server import _audit as _a
    _a(action, detail)


def _docent_dir():
    from docent.ui_server import _docent_dir as _dd
    return _dd()


@router.get("/api/queue")
def get_queue() -> JSONResponse:
    from docent.bundled_plugins.reading import load_queue_for_ui
    return JSONResponse(load_queue_for_ui())


@router.get("/api/database")
def get_database() -> JSONResponse:
    """Return the list of PDF filenames in the configured database/watch folder."""
    from pathlib import Path
    from datetime import datetime, timezone
    reading_cfg = _read_config_reading()
    db_dir = reading_cfg.get("database_dir")
    if not db_dir:
        return JSONResponse({"database_dir": None, "pdfs": [], "last_checked": datetime.now(timezone.utc).isoformat()})
    p = Path(db_dir).expanduser()
    if not p.is_dir():
        return JSONResponse({"database_dir": str(p), "pdfs": [], "last_checked": datetime.now(timezone.utc).isoformat()})
    pdfs = _get_database_files(p)
    return JSONResponse({
        "database_dir": str(p),
        "pdfs": pdfs,
        "last_checked": datetime.now(timezone.utc).isoformat(),
    })


@router.post("/api/actions")
async def post_action(body: ActionBody) -> JSONResponse:
    action = body.action
    no_id_actions = {"sync", "queue-clear"}
    if action not in no_id_actions and not body.id:
        return JSONResponse({"ok": False, "error": "id required"}, status_code=400)

    if action not in _ACTION_MAP:
        return JSONResponse({"error": "Unknown action"}, status_code=400)

    tool_name, action_name = _ACTION_MAP[action]
    args: dict[str, Any] = {}
    if body.id is not None:
        args["id"] = body.id
    if action == "edit":
        if body.status is not None:
            args["status"] = body.status
        if body.order is not None:
            args["order"] = body.order
        if body.deadline is not None:
            args["deadline"] = body.deadline
        if body.notes is not None:
            args["notes"] = body.notes
        if body.tags is not None:
            args["tags"] = body.tags
    elif action == "queue-clear":
        if not body.confirmed:
            return JSONResponse(
                {"ok": False, "error": "queue-clear requires confirmed=true"},
                status_code=400,
            )
        args["yes"] = True
        _audit("queue-clear", "confirmed")

    try:
        result = await asyncio.to_thread(invoke_action, tool_name, action_name, args)
        return JSONResponse({"ok": True, "stdout": result})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
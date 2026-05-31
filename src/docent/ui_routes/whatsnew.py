"""What's New endpoints for the web UI.

GET  /api/whatsnew       → {version, release, new} (new=True until dismissed)
POST /api/whatsnew/seen  → dismiss the current version's toast
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/whatsnew")
async def get_whatsnew() -> JSONResponse:
    from docent.whatsnew import ui_payload

    return JSONResponse(ui_payload())


@router.post("/api/whatsnew/seen")
async def post_whatsnew_seen() -> JSONResponse:
    from docent.whatsnew import mark_ui_seen

    mark_ui_seen()
    return JSONResponse({"ok": True})

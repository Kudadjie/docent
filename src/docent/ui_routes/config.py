"""Config and user profile endpoints."""

import asyncio
import json
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


def _norm_path(raw: str | None) -> str | None:
    """Normalize a stored path string — collapses double backslashes on Windows."""
    if not raw:
        return raw
    return os.path.normpath(raw)


from docent.core.invoke import run_action  # noqa: E402


class ConfigBody(BaseModel):
    section: str
    key: str
    value: str


class UserBody(BaseModel):
    name: str
    program: str
    level: str


_RESEARCH_KEY_FIELDS = [
    "tavily_api_key",
    "semantic_scholar_api_key",
    "alphaxiv_api_key",
    "groq_api_key",
    "gemini_api_key",
    "openrouter_api_key",
    "mistral_api_key",
    "cerebras_api_key",
]


from docent.ui_routes._shared import (  # noqa: E402
    _audit,
    _docent_dir,
    _mask_key,
    _read_config_reading,
    _read_config_research,
    _read_json,
    _user_file,
)


@router.get("/api/config")
async def get_config() -> JSONResponse:
    cfg = _read_config_reading()
    rcfg = _read_config_research()
    research = {k: _mask_key(rcfg.get(k)) for k in _RESEARCH_KEY_FIELDS}
    research["feynman_model"] = rcfg.get("feynman_model")  # plain string, not a secret
    research["max_parallel_studio_runs"] = rcfg.get("max_parallel_studio_runs", 3)  # client run cap
    return JSONResponse(
        {
            "reading": {
                "database_dir": _norm_path(cfg.get("database_dir", None)),
                "queue_collection": cfg.get("queue_collection", "Docent-Queue"),
                "reference_manager": cfg.get("reference_manager", "mendeley"),
                "zotero_api_key": _mask_key(cfg.get("zotero_api_key")),
                "zotero_library_id": cfg.get("zotero_library_id", None),
                "zotero_library_type": cfg.get("zotero_library_type", "user"),
                "output_dir": _norm_path(rcfg.get("output_dir", None)),
            },
            "research": research,
        }
    )


@router.post("/api/config")
async def post_config(body: ConfigBody) -> JSONResponse:
    _audit("config-write", f"section={body.section} key={body.key}")
    if body.section == "reading":
        try:
            if body.key == "output_dir":
                await asyncio.to_thread(
                    run_action, "studio", "config-set", {"key": body.key, "value": body.value}
                )
            else:
                await asyncio.to_thread(
                    run_action, "reading", "config-set", {"key": body.key, "value": body.value}
                )
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
        cfg = _read_config_reading()
        rcfg = _read_config_research()
        return JSONResponse(
            {
                "ok": True,
                "reading": {
                    "database_dir": _norm_path(cfg.get("database_dir", None)),
                    "queue_collection": cfg.get("queue_collection", "Docent-Queue"),
                    "reference_manager": cfg.get("reference_manager", "mendeley"),
                    "zotero_api_key": _mask_key(cfg.get("zotero_api_key")),
                    "zotero_library_id": cfg.get("zotero_library_id", None),
                    "zotero_library_type": cfg.get("zotero_library_type", "user"),
                    "output_dir": _norm_path(rcfg.get("output_dir", None)),
                },
            }
        )
    elif body.section == "research":
        try:
            await asyncio.to_thread(
                run_action, "studio", "config-set", {"key": body.key, "value": body.value}
            )
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
        rcfg = _read_config_research()
        research = {k: _mask_key(rcfg.get(k)) for k in _RESEARCH_KEY_FIELDS}
        research["feynman_model"] = rcfg.get("feynman_model")
        return JSONResponse({"ok": True, "research": research})
    else:
        return JSONResponse({"error": f"Unknown section: {body.section!r}"}, status_code=400)


@router.get("/api/user")
async def get_user() -> JSONResponse:
    data = _read_json(_user_file(), {})
    name = data.get("name", "")
    program = data.get("program", "")
    level = data.get("level", "")
    if name == "You" and not program and not level:
        name = ""
    return JSONResponse({"name": name, "program": program, "level": level})


@router.post("/api/user")
async def post_user(body: UserBody) -> JSONResponse:
    _docent_dir().mkdir(parents=True, exist_ok=True)
    _user_file().write_text(
        json.dumps({"name": body.name, "program": body.program, "level": body.level}),
        encoding="utf-8",
    )
    return JSONResponse({"ok": True})

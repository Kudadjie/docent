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


def _config_file():
    from docent.ui_server import _config_file as _cf
    return _cf()


def _user_file():
    from docent.ui_server import _user_file as _uf
    return _uf()


def _docent_dir():
    from docent.ui_server import _docent_dir as _dd
    return _dd()


def _read_json(path, default):
    from docent.ui_server import _read_json as _rj
    return _rj(path, default)


def _mask_key(key):
    from docent.ui_server import _mask_key as _mk
    return _mk(key)


def _read_config_reading():
    from docent.ui_server import _read_config_reading as _rcr
    return _rcr()


def _read_config_research():
    from docent.ui_server import _read_config_research as _rcr2
    return _rcr2()


def _audit(action: str, detail: str) -> None:
    from docent.ui_server import _audit as _a
    _a(action, detail)


@router.get("/api/config")
async def get_config() -> JSONResponse:
    cfg = _read_config_reading()
    rcfg = _read_config_research()
    research = {k: _mask_key(rcfg.get(k)) for k in _RESEARCH_KEY_FIELDS}
    research["feynman_model"] = rcfg.get("feynman_model")  # plain string, not a secret
    return JSONResponse({
        "reading": {
            "database_dir": _norm_path(cfg.get("database_dir", None)),
            "queue_collection": cfg.get("queue_collection", "Docent-Queue"),
            "reference_manager": cfg.get("reference_manager", "mendeley"),
            "output_dir": _norm_path(rcfg.get("output_dir", None)),
        },
        "research": research,
    })


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
        return JSONResponse({
            "ok": True,
            "reading": {
                "database_dir": _norm_path(cfg.get("database_dir", None)),
                "queue_collection": cfg.get("queue_collection", "Docent-Queue"),
                "output_dir": _norm_path(rcfg.get("output_dir", None)),
            }
        })
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
    _user_file().write_text(json.dumps({"name": body.name, "program": body.program, "level": body.level}), encoding="utf-8")
    return JSONResponse({"ok": True})
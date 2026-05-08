"""FastAPI backend for the Docent web UI."""

import asyncio
import json
import tomllib
from pathlib import Path
from typing import Any, Optional

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

UI_DIST = Path(__file__).parent / "ui_dist"
DOCENT_DIR = Path.home() / ".docent"
QUEUE_FILE = DOCENT_DIR / "data" / "reading" / "queue.json"
STATE_FILE = DOCENT_DIR / "data" / "reading" / "state.json"
CONFIG_FILE = DOCENT_DIR / "config.toml"
USER_FILE = DOCENT_DIR / "user.json"

app = FastAPI(docs_url=None, redoc_url=None)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_config_reading() -> dict:
    try:
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
        return data.get("reading", {})
    except Exception:
        return {}


async def _run(args: list[str], timeout: float = 30.0) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(
        "docent", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    return stdout_b.decode(), stderr_b.decode(), proc.returncode


@app.get("/api/queue")
async def get_queue() -> JSONResponse:
    entries = _read_json(QUEUE_FILE, [])
    state = _read_json(STATE_FILE, {})
    banner = {
        "queued": state.get("queued", 0),
        "reading": state.get("reading", 0),
        "done": state.get("done", 0),
    }
    last_updated = state.get("last_updated", None)
    reading_cfg = _read_config_reading()
    db_dir = reading_cfg.get("database_dir")
    database_count: Optional[int] = None
    if db_dir:
        p = Path(db_dir).expanduser()
        if p.is_dir():
            database_count = sum(1 for _ in p.rglob("*.pdf"))
    return JSONResponse({"entries": entries, "banner": banner, "last_updated": last_updated, "database_count": database_count})


class ActionBody(BaseModel):
    action: str
    id: Optional[str] = None
    status: Optional[str] = None
    order: Optional[int] = None
    deadline: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


@app.post("/api/actions")
async def post_action(body: ActionBody) -> JSONResponse:
    action = body.action
    no_id_actions = {"sync", "queue-clear"}
    if action not in no_id_actions and not body.id:
        return JSONResponse({"ok": False, "error": "id required"}, status_code=400)

    try:
        if action == "edit":
            args = ["reading", "edit", "--id", body.id]
            if body.status is not None:
                args += ["--status", body.status]
            if body.order is not None:
                args += ["--order", str(body.order)]
            if body.deadline is not None:
                args += ["--deadline", body.deadline]
            if body.notes is not None:
                args += ["--notes", body.notes]
            if body.tags is not None:
                for t in body.tags:
                    args += ["--tags", t]
            stdout, stderr, rc = await _run(args)
        elif action == "done":
            stdout, stderr, rc = await _run(["reading", "done", "--id", body.id])
        elif action == "start":
            stdout, stderr, rc = await _run(["reading", "start", "--id", body.id])
        elif action == "remove":
            stdout, stderr, rc = await _run(["reading", "remove", "--id", body.id])
        elif action == "move-up":
            stdout, stderr, rc = await _run(["reading", "move-up", "--id", body.id])
        elif action == "move-down":
            stdout, stderr, rc = await _run(["reading", "move-down", "--id", body.id])
        elif action == "sync":
            stdout, stderr, rc = await _run(["reading", "sync-from-mendeley"], timeout=120.0)
        elif action == "queue-clear":
            stdout, stderr, rc = await _run(["reading", "queue-clear", "--yes"])
        else:
            return JSONResponse({"error": "Unknown action"}, status_code=400)

        if rc != 0:
            raise RuntimeError(stderr or stdout)
        return JSONResponse({"ok": True, "stdout": stdout, "stderr": stderr})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/api/config")
async def get_config() -> JSONResponse:
    cfg = _read_config_reading()
    return JSONResponse({
        "reading": {
            "database_dir": cfg.get("database_dir", None),
            "queue_collection": cfg.get("queue_collection", "Docent-Queue"),
        }
    })


class ConfigBody(BaseModel):
    section: str
    key: str
    value: str


@app.post("/api/config")
async def post_config(body: ConfigBody) -> JSONResponse:
    if body.section != "reading":
        return JSONResponse({"error": "Only section='reading' is supported"}, status_code=400)
    try:
        stdout, stderr, rc = await _run(["reading", "config-set", "--key", body.key, "--value", body.value])
        if rc != 0:
            raise RuntimeError(stderr or stdout)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    cfg = _read_config_reading()
    return JSONResponse({
        "ok": True,
        "reading": {
            "database_dir": cfg.get("database_dir", None),
            "queue_collection": cfg.get("queue_collection", "Docent-Queue"),
        }
    })


@app.get("/api/user")
async def get_user() -> JSONResponse:
    data = _read_json(USER_FILE, {})
    name = data.get("name", "")
    program = data.get("program", "")
    level = data.get("level", "")
    if name == "You" and not program and not level:
        name = ""
    return JSONResponse({"name": name, "program": program, "level": level})


class UserBody(BaseModel):
    name: str
    program: str
    level: str


@app.post("/api/user")
async def post_user(body: UserBody) -> JSONResponse:
    DOCENT_DIR.mkdir(parents=True, exist_ok=True)
    USER_FILE.write_text(json.dumps({"name": body.name, "program": body.program, "level": body.level}), encoding="utf-8")
    return JSONResponse({"ok": True})


@app.get("/api/version")
async def get_version() -> JSONResponse:
    try:
        async def _installed() -> str:
            stdout, _, rc = await _run(["--version"])
            if rc != 0:
                raise RuntimeError("docent --version failed")
            return stdout.strip().split()[-1]

        async def _latest() -> Optional[str]:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get("https://pypi.org/pypi/docent-cli/json")
                    r.raise_for_status()
                    return r.json()["info"]["version"]
            except Exception:
                return None

        installed, latest = await asyncio.gather(_installed(), _latest())
        up_to_date = (installed == latest) if latest is not None else None
        return JSONResponse({"installed": installed, "latest": latest, "up_to_date": up_to_date})
    except Exception as exc:
        return JSONResponse({"installed": None, "latest": None, "up_to_date": None, "error": str(exc)}, status_code=500)


if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")


def run_server(host: str = "127.0.0.1", port: int = 7432) -> None:
    uvicorn.run(app, host=host, port=port)

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

from docent.core.invoke import run_action
from docent.mcp_server import invoke_action

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


async def _run_command(cmd: str, args: list[str], timeout: float = 30.0) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(
        cmd, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    return stdout_b.decode(), stderr_b.decode(), proc.returncode


async def _run(args: list[str], timeout: float = 30.0) -> tuple[str, str, int]:
    return await _run_command("docent", args, timeout=timeout)


def _version_at_least(installed: str, latest: str) -> bool:
    def to_ints(value: str) -> list[int]:
        return [int(part) for part in value.removeprefix("v").split(".")]

    try:
        current = to_ints(installed)
        target = to_ints(latest)
    except ValueError:
        return installed == latest

    length = max(len(current), len(target))
    current += [0] * (length - len(current))
    target += [0] * (length - len(target))
    return current >= target


async def _fetch_npm_latest(package: str) -> Optional[str]:
    try:
        encoded = package.replace("@", "%40").replace("/", "%2F")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://registry.npmjs.org/{encoded}/latest",
                headers={"Accept": "application/json"},
            )
        response.raise_for_status()
        return response.json().get("version")
    except Exception:
        return None


async def _get_npm_installed(package: str) -> Optional[str]:
    try:
        stdout, _, rc = await _run_command(
            "npm",
            ["list", "-g", package, "--json", "--depth=0"],
            timeout=15.0,
        )
        if rc != 0 and not stdout:
            return None
        data = json.loads(stdout)
        return data.get("dependencies", {}).get(package, {}).get("version")
    except Exception:
        return None


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


_ACTION_MAP: dict[str, tuple[str, str]] = {
    "edit": ("reading", "edit"),
    "done": ("reading", "done"),
    "start": ("reading", "start"),
    "remove": ("reading", "remove"),
    "move-up": ("reading", "move-up"),
    "move-down": ("reading", "move-down"),
    "sync": ("reading", "sync-from-mendeley"),
    "queue-clear": ("reading", "queue-clear"),
}


@app.post("/api/actions")
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
        args["yes"] = True

    try:
        result = await asyncio.to_thread(invoke_action, tool_name, action_name, args)
        return JSONResponse({"ok": True, "stdout": result})
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
        await asyncio.to_thread(
            run_action, "reading", "config-set", {"key": body.key, "value": body.value}
        )
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


TOOLING = [
    {
        "name": "@companion-ai/feynman",
        "label": "Feynman",
        "upgrade_cmd": "npm install -g @companion-ai/feynman",
    },
]


@app.get("/api/tooling")
async def get_tooling() -> JSONResponse:
    async def _tool_status(tool: dict[str, str]) -> dict[str, str | bool | None]:
        installed, latest = await asyncio.gather(
            _get_npm_installed(tool["name"]),
            _fetch_npm_latest(tool["name"]),
        )
        up_to_date = (
            _version_at_least(installed, latest)
            if installed is not None and latest is not None
            else None
        )
        return {**tool, "installed": installed, "latest": latest, "up_to_date": up_to_date}

    results = await asyncio.gather(*(_tool_status(tool) for tool in TOOLING))
    return JSONResponse(list(results))


if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")


def run_server(host: str = "127.0.0.1", port: int = 7432) -> None:
    from docent.core import load_plugins
    from docent.tools import discover_tools
    discover_tools()
    load_plugins()
    uvicorn.run(app, host=host, port=port)

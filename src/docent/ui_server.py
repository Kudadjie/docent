"""FastAPI backend for the Docent web UI."""

import asyncio
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Optional

import httpx
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from docent.core.invoke import run_action
from docent.mcp_server import invoke_action, _serialize
from docent.utils.paths import root_dir

UI_DIST = Path(__file__).parent / "ui_dist"


def _docent_dir() -> Path:
    return root_dir()


def _queue_file() -> Path:
    return root_dir() / "data" / "reading" / "queue.json"


def _state_file() -> Path:
    return root_dir() / "data" / "reading" / "state.json"


def _config_file() -> Path:
    return root_dir() / "config.toml"


def _user_file() -> Path:
    return root_dir() / "user.json"

app = FastAPI(docs_url=None, redoc_url=None)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_config_reading() -> dict:
    try:
        with open(_config_file(), "rb") as f:
            data = tomllib.load(f)
        return data.get("reading", {})
    except Exception:
        return {}


def _read_config_research() -> dict:
    try:
        with open(_config_file(), "rb") as f:
            data = tomllib.load(f)
        return data.get("research", {})
    except Exception:
        return {}


def _mask_key(key: str | None) -> Optional[str]:
    if not key:
        return None
    if len(key) <= 8:
        return "***"
    return key[:4] + "..." + key[-4:]


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
    entries = _read_json(_queue_file(), [])
    state = _read_json(_state_file(), {})
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
        if not body.confirmed:
            return JSONResponse(
                {"ok": False, "error": "queue-clear requires confirmed=true"},
                status_code=400,
            )
        args["yes"] = True

    try:
        result = await asyncio.to_thread(invoke_action, tool_name, action_name, args)
        return JSONResponse({"ok": True, "stdout": result})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


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


@app.get("/api/config")
async def get_config() -> JSONResponse:
    cfg = _read_config_reading()
    rcfg = _read_config_research()
    research = {k: _mask_key(rcfg.get(k)) for k in _RESEARCH_KEY_FIELDS}
    return JSONResponse({
        "reading": {
            "database_dir": cfg.get("database_dir", None),
            "queue_collection": cfg.get("queue_collection", "Docent-Queue"),
        },
        "research": research,
    })


class ConfigBody(BaseModel):
    section: str
    key: str
    value: str


@app.post("/api/config")
async def post_config(body: ConfigBody) -> JSONResponse:
    if body.section == "reading":
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
    elif body.section == "research":
        try:
            await asyncio.to_thread(
                run_action, "studio", "config-set", {"key": body.key, "value": body.value}
            )
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
        rcfg = _read_config_research()
        return JSONResponse({
            "ok": True,
            "research": {k: _mask_key(rcfg.get(k)) for k in _RESEARCH_KEY_FIELDS},
        })
    else:
        return JSONResponse({"error": f"Unknown section: {body.section!r}"}, status_code=400)


@app.get("/api/user")
async def get_user() -> JSONResponse:
    data = _read_json(_user_file(), {})
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
    _docent_dir().mkdir(parents=True, exist_ok=True)
    _user_file().write_text(json.dumps({"name": body.name, "program": body.program, "level": body.level}), encoding="utf-8")
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


@app.get("/api/doctor")
async def get_doctor() -> JSONResponse:
    import sys
    import shutil
    import subprocess as _sp

    cfg_reading = _read_config_reading()
    cfg_research = _read_config_research()
    user_data = _read_json(_user_file(), {})

    def _row(label: str, status: str, version: str = "-", detail: str = "-") -> dict:
        return {"label": label, "status": status, "version": version, "detail": detail}

    # ── Profile ──────────────────────────────────────────────────────────────
    name = (user_data.get("name") or "").strip()
    profile_row = (
        _row("Profile", "OK", detail=f"{name} · {user_data.get('level', '?')} · {user_data.get('program', '?')}")
        if name and name != "You"
        else _row("Profile", "WARN", detail="Not set — use 'Set up your profile' in the sidebar")
    )

    # ── Python ───────────────────────────────────────────────────────────────
    pv = sys.version_info
    python_row = _row("Python", "OK", f"{pv.major}.{pv.minor}.{pv.micro}")

    # ── Docent version ────────────────────────────────────────────────────────
    async def _docent_version_row() -> dict:
        try:
            stdout, _, rc = await _run(["--version"], timeout=8.0)
            version = stdout.strip().split()[-1] if rc == 0 else "?"
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    r = await client.get("https://pypi.org/pypi/docent-cli/json")
                    latest = r.json()["info"]["version"]
                if version == latest:
                    return _row("Docent", "OK", version, "up to date")
                return _row("Docent", "WARN", version, f"update available: {latest} — run: docent update")
            except Exception:
                return _row("Docent", "OK", version)
        except Exception as exc:
            return _row("Docent", "WARN", "?", str(exc)[:80])

    # ── CLI tool helper ───────────────────────────────────────────────────────
    async def _cli_row(label: str, cmd: list[str], install_hint: str) -> dict:
        exe = await asyncio.to_thread(shutil.which, cmd[0])
        if exe is None:
            return _row(label, "FAIL", detail=install_hint)
        try:
            stdout, _, rc = await _run_command(exe, cmd[1:], timeout=8.0)
            version = (stdout.strip() or "?").splitlines()[0].strip()
            return _row(label, "OK", version)
        except asyncio.TimeoutError:
            return _row(label, "WARN", "?", "version check timed out")
        except Exception as exc:
            return _row(label, "WARN", "?", str(exc)[:80])

    # ── Mendeley MCP ──────────────────────────────────────────────────────────
    async def _mendeley_row() -> dict:
        uvx = await asyncio.to_thread(shutil.which, "uvx")
        if uvx:
            return _row("Mendeley MCP", "OK", detail="uvx found")
        return _row("Mendeley MCP", "FAIL", detail="uvx not found — install uv: https://docs.astral.sh/uv/")

    # ── OpenCode ──────────────────────────────────────────────────────────────
    async def _opencode_row() -> dict:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get("http://127.0.0.1:4096/global/health")
                if r.status_code == 200:
                    return _row("OpenCode", "OK", detail="server reachable at :4096")
        except Exception:
            pass
        return _row("OpenCode", "WARN", detail="Not running — start with: opencode serve --port 4096")

    # ── Feynman ───────────────────────────────────────────────────────────────
    async def _feynman_row() -> dict:
        # Primary: check binary on PATH / Windows AppData (mirrors _find_feynman logic).
        # npm list -g is unreliable on Windows when the npm prefix differs from PATH.
        from pathlib import Path as _P
        feynman_cmd: list[str] | None = None
        resolved = shutil.which("feynman")
        if resolved:
            feynman_cmd = [resolved]
        else:
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                win_path = _P(appdata) / "npm" / "feynman.cmd"
                if win_path.is_file():
                    feynman_cmd = [str(win_path)]

        if feynman_cmd is None:
            # Binary not on PATH — fall back to npm registry check
            installed = await _get_npm_installed("@companion-ai/feynman")
            if installed is None:
                return _row("Feynman CLI", "WARN", detail="Not installed — npm install -g @companion-ai/feynman")
            feynman_cmd = ["feynman"]

        # Read version from package.json (no subprocess)
        from docent.bundled_plugins.studio.feynman import _feynman_version_from_package_json
        version = _feynman_version_from_package_json(feynman_cmd)

        latest = await _fetch_npm_latest("@companion-ai/feynman")
        if latest and version != "?" and not _version_at_least(version, latest):
            return _row("Feynman CLI", "WARN", version,
                        f"update available: {latest} — npm install -g @companion-ai/feynman@latest")
        return _row("Feynman CLI", "OK", version or "?")

    # ── NotebookLM ────────────────────────────────────────────────────────────
    def _notebooklm_sync() -> dict:
        try:
            import notebooklm as _nlm
            version = getattr(_nlm, "__version__", "-")
        except ImportError:
            return _row("NotebookLM", "FAIL", detail='not installed — pip install "notebooklm-py[browser]"')
        exe = shutil.which("notebooklm")
        if not exe:
            return _row("NotebookLM", "WARN", version, "CLI not on PATH")
        try:
            result = _sp.run([exe, "list", "--json"], capture_output=True, text=True, timeout=10)
            import json as _j
            data = _j.loads(result.stdout or "{}")
            if result.returncode == 0 and not data.get("error"):
                return _row("NotebookLM", "OK", version, "authenticated")
        except Exception:
            pass
        return _row("NotebookLM", "WARN", version, "Not authenticated — run: notebooklm login")

    # ── alphaXiv ──────────────────────────────────────────────────────────────
    def _alphaxiv_sync() -> dict:
        try:
            from alphaxiv import __version__ as ax_v
        except ImportError:
            return _row("alphaXiv", "FAIL", detail="alphaxiv-py not installed (uv add alphaxiv-py)")
        key = cfg_research.get("alphaxiv_api_key")
        if key:
            return _row("alphaXiv", "OK", ax_v, f"key configured ({_mask_key(key)})")
        return _row("alphaXiv", "SKIP", ax_v, "No key — get free key at alphaxiv.org/settings")

    # ── Reading DB ────────────────────────────────────────────────────────────
    def _reading_db_row() -> dict:
        db = cfg_reading.get("database_dir")
        if db is None:
            return _row("Reading DB", "WARN", detail="Not configured — set database_dir in Settings")
        expanded = Path(str(db)).expanduser()
        if expanded.exists():
            return _row("Reading DB", "OK", detail=str(expanded))
        return _row("Reading DB", "WARN", detail=f"{expanded} does not exist")

    # ── API key checks ────────────────────────────────────────────────────────
    def _key_row(label: str, cfg_key: str, hint: str, warn_if_missing: bool = False) -> dict:
        key = cfg_research.get(cfg_key)
        if key:
            return _row(label, "OK", detail=f"key configured ({_mask_key(key)})")
        status = "WARN" if warn_if_missing else "SKIP"
        return _row(label, status, detail=hint)

    # Run all checks concurrently
    (
        docent_row,
        uv_row, node_row, npm_row,
        feynman_row, mendeley_row, opencode_row,
        nlm_row, ax_row,
    ) = await asyncio.gather(
        _docent_version_row(),
        _cli_row("uv", ["uv", "--version"], "Install uv: https://docs.astral.sh/uv/"),
        _cli_row("Node.js", ["node", "--version"], "Install Node.js: https://nodejs.org"),
        _cli_row("npm", ["npm", "--version"], "Install npm: https://nodejs.org"),
        _feynman_row(),
        _mendeley_row(),
        _opencode_row(),
        asyncio.to_thread(_notebooklm_sync),
        asyncio.to_thread(_alphaxiv_sync),
    )
    db_row = await asyncio.to_thread(_reading_db_row)

    checks = [
        profile_row,
        python_row,
        docent_row,
        uv_row,
        node_row,
        npm_row,
        feynman_row,
        mendeley_row,
        opencode_row,
        nlm_row,
        ax_row,
        db_row,
        _key_row("Tavily", "tavily_api_key",
                 "Not set — get free key at app.tavily.com. Falls back to DuckDuckGo.", warn_if_missing=True),
        _key_row("Semantic Scholar", "semantic_scholar_api_key",
                 "Optional — raises rate limits (api.semanticscholar.org)"),
        _key_row("Groq", "groq_api_key", "Free tier at console.groq.com"),
        _key_row("Gemini", "gemini_api_key", "Free tier at aistudio.google.com"),
        _key_row("OpenRouter", "openrouter_api_key", "Pay-as-you-go at openrouter.ai"),
        _key_row("Mistral", "mistral_api_key", "console.mistral.ai"),
        _key_row("Cerebras", "cerebras_api_key", "cloud.cerebras.ai"),
    ]
    return JSONResponse(checks)


# ── Studio run endpoint ──────────────────────────────────────────────────────

_STUDIO_ACTION_MAP: dict[str, str] = {
    'deep':      'deep-research',
    'lit':       'lit',
    'peer':      'review',
    'compare':   'compare',
    'draft':     'draft',
    'replicate': 'replicate',
    'audit':     'audit',
    'search':    'search-papers',
    'scholarly': 'scholarly-search',
    'getpaper':  'get-paper',
    'notebook':  'to-notebook',
    'cfgshow':   'config-show',
    'cfgset':    'config-set',
}

_BACKEND_NORM: dict[str, str] = {
    'free': 'free', 'feynman': 'feynman', 'docent': 'docent',
    'groq': 'groq', 'gemini': 'gemini', 'openrouter': 'openrouter',
    'anthropic': 'anthropic', 'openai': 'openai',
    'ollama': 'ollama', 'lm studio': 'lm_studio', 'lm_studio': 'lm_studio',
    'mistral': 'mistral', 'cerebras': 'cerebras',
}


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


def _form_to_studio_args(action_id: str, body: StudioRunBody) -> dict[str, Any]:
    studio_action = _STUDIO_ACTION_MAP[action_id]
    backend = _BACKEND_NORM.get(body.backend.lower().replace(' ', '_'), 'free')
    dest = body.dest.lower().replace(' →', '').strip()

    if studio_action in ('deep-research', 'lit', 'draft'):
        return {
            'topic': body.topic, 'backend': backend,
            'output': dest, 'guide_files': body.guides, 'confirmed': True,
        }
    if studio_action in ('review', 'replicate', 'audit'):
        return {'artifact': body.artifact, 'backend': backend, 'output': dest, 'guide_files': body.guides}
    if studio_action == 'compare':
        return {
            'artifact_a': body.artifact_a, 'artifact_b': body.artifact_b,
            'backend': backend, 'output': dest, 'guide_files': body.guides,
        }
    if studio_action == 'search-papers':
        return {'query': body.query, 'max_results': body.max_results}
    if studio_action == 'scholarly-search':
        return {'query': body.query, 'max_results': body.max_results}
    if studio_action == 'get-paper':
        return {'arxiv_id': body.arxiv_id}
    if studio_action == 'to-notebook':
        return {
            'output_file': body.out_path or None,
            'sources_file': body.src_path or None,
            'max_sources': body.max_sources,
            'run_nlm_research': body.nlm,
            'run_quality_gate': body.gate,
            'run_perspectives': body.persp,
        }
    if studio_action == 'config-show':
        return {}
    if studio_action == 'config-set':
        return {'key': body.cfg_key, 'value': body.cfg_val}
    return {}


async def _stream_studio_run(studio_action: str, args: dict[str, Any]):
    """Async generator — yields SSE `data:` lines for a studio run."""
    import inspect as _inspect
    from pydantic import BaseModel as _BM

    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def _run_in_thread() -> None:
        from docent.core import ProgressEvent, run_action
        from docent.core.invoke import make_context
        # via_mcp=True: all preflights take the structured path (_bail raises RuntimeError
        # instead of print+typer.Exit so errors reach the SSE stream with real messages).
        # confirmed=True in args handles the free-tier gate without a second prompt.
        ctx = make_context(via_mcp=True)
        try:
            raw = run_action('studio', studio_action, args, context=ctx)
        except BaseException as exc:
            msg = str(exc).strip() or type(exc).__name__
            loop.call_soon_threadsafe(q.put_nowait, ('error', msg))
            return

        if not _inspect.isgenerator(raw):
            loop.call_soon_threadsafe(q.put_nowait, ('done', raw))
            return

        try:
            while True:
                try:
                    evt = next(raw)
                    if isinstance(evt, ProgressEvent):
                        loop.call_soon_threadsafe(q.put_nowait, ('event', evt))
                except StopIteration as stop:
                    loop.call_soon_threadsafe(q.put_nowait, ('done', stop.value))
                    return
        except BaseException as exc:
            msg = str(exc).strip() or type(exc).__name__
            loop.call_soon_threadsafe(q.put_nowait, ('error', msg))

    def _sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    thread = loop.run_in_executor(None, _run_in_thread)
    try:
        while True:
            kind, payload = await q.get()
            if kind == 'event':
                evt = payload
                if evt.message:
                    yield _sse({'type': 'log', 'phase': evt.phase, 'text': evt.message, 'level': evt.level})
            elif kind == 'done':
                result = payload
                ok = not isinstance(result, _BM) or bool(getattr(result, 'ok', True))
                yield _sse({'type': 'done', 'status': 'success' if ok else 'failure', 'raw': _serialize(result)})
                break
            elif kind == 'error':
                yield _sse({'type': 'error', 'message': str(payload)})
                break
    finally:
        await thread


# ── File-system helpers ───────────────────────────────────────────────────────

@app.get("/api/fs/read")
async def fs_read(path: str = Query(...)) -> JSONResponse:
    """Read a text file from the local filesystem (for Markdown preview)."""
    try:
        p = Path(path).expanduser()
        if not p.is_file():
            return JSONResponse({"error": f"File not found: {path}"}, status_code=404)
        size = p.stat().st_size
        if size > 500_000:
            return JSONResponse({"error": "File too large to preview (>500 KB)"}, status_code=400)
        content = p.read_text(encoding="utf-8", errors="replace")
        return JSONResponse({"content": content})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/fs/open")
async def fs_open(path: str = Query(...)) -> JSONResponse:
    """Open a file or its parent folder in the OS file manager."""
    try:
        p = Path(path).expanduser()
        target = p if p.is_dir() else p.parent
        if sys.platform == "win32":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return JSONResponse({"ok": True})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


class FsPickBody(BaseModel):
    extensions: list[str] = []
    title: str = "Select files"


@app.post("/api/fs/pick")
async def fs_pick(body: FsPickBody) -> JSONResponse:
    """Open a native OS file-picker dialog and return selected paths."""
    def _pick() -> list[str]:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)  # type: ignore[arg-type]
        ftypes: list[tuple[str, str]] = []
        if body.extensions:
            ftypes.append(("Supported files", " ".join("*" + e for e in body.extensions)))
        ftypes.append(("All files", "*.*"))
        paths = filedialog.askopenfilenames(
            title=body.title,
            filetypes=ftypes,
        )
        root.destroy()
        return list(paths)

    try:
        selected = await asyncio.to_thread(_pick)
        return JSONResponse({"paths": selected})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ── Studio outputs ─────────────────────────────────────────────────────────────

@app.get("/api/studio/outputs")
async def studio_outputs() -> JSONResponse:
    """List recent research output files from the configured output directory."""
    try:
        from docent.config import load_settings
        settings = await asyncio.to_thread(load_settings)
        output_dir = settings.research.output_dir.expanduser()
    except Exception:
        return JSONResponse({"files": [], "output_dir": None})

    if not output_dir.is_dir():
        return JSONResponse({"files": [], "output_dir": str(output_dir)})

    files = []
    try:
        for f in sorted(output_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
            try:
                stat = f.stat()
                files.append({
                    "path": str(f),
                    "name": f.name,
                    "folder": f.parent.name,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
            except Exception:
                pass
    except Exception:
        pass

    return JSONResponse({"files": files, "output_dir": str(output_dir)})


# ── OpenCode server management ─────────────────────────────────────────────────

_opencode_proc: Optional[subprocess.Popen] = None  # type: ignore[type-arg]


@app.post("/api/opencode/start")
async def opencode_start() -> JSONResponse:
    global _opencode_proc
    # Check if already reachable
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get("http://127.0.0.1:4096/global/health")
            if r.status_code == 200:
                return JSONResponse({"ok": True, "status": "already_running"})
    except Exception:
        pass
    try:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        _opencode_proc = subprocess.Popen(
            ["opencode", "serve", "--port", "4096"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        # Give it a moment to start
        await asyncio.sleep(1.5)
        return JSONResponse({"ok": True, "status": "started", "pid": _opencode_proc.pid})
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "opencode not found — install: npm install -g opencode"}, status_code=500)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.post("/api/opencode/stop")
async def opencode_stop() -> JSONResponse:
    global _opencode_proc
    if _opencode_proc is not None:
        try:
            _opencode_proc.terminate()
            _opencode_proc = None
            return JSONResponse({"ok": True, "status": "stopped"})
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return JSONResponse({"ok": True, "status": "not_running"})


@app.get("/api/opencode/status")
async def opencode_status() -> JSONResponse:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get("http://127.0.0.1:4096/global/health")
            if r.status_code == 200:
                return JSONResponse({"running": True})
    except Exception:
        pass
    return JSONResponse({"running": False})


@app.post("/api/studio/run")
async def studio_run(body: StudioRunBody):
    if body.action_id not in _STUDIO_ACTION_MAP:
        return JSONResponse({'error': f'Unknown action: {body.action_id!r}'}, status_code=400)
    studio_action = _STUDIO_ACTION_MAP[body.action_id]
    args = _form_to_studio_args(body.action_id, body)
    return StreamingResponse(
        _stream_studio_run(studio_action, args),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")


def run_server(host: str = "127.0.0.1", port: int = 7432) -> None:
    from docent.core import load_plugins
    from docent.tools import discover_tools
    discover_tools()
    load_plugins()
    uvicorn.run(app, host=host, port=port)

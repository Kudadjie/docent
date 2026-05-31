# ruff: noqa: E402 — router and class definitions precede some imports by design
"""FastAPI backend for the Docent web UI."""

import asyncio
import json
import logging
import subprocess
import time as _time
import tomllib
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from docent.core.invoke import serialize_result as _serialize
from docent.utils.paths import root_dir

UI_DIST = Path(__file__).parent / "ui_dist"

_audit_logger = logging.getLogger("docent.ui.audit")


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


def _path_under(path: Path, root: Path) -> bool:
    """Return True if *path* is equal to or under *root* (both must be resolved)."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


async def _check_approved_path(path: Path) -> str | None:
    """Return None if path is under an approved Docent root, else an error string."""
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        return "Invalid path"
    approved: list[Path] = [_docent_dir().resolve()]
    try:
        from docent.config import load_settings
        settings = await asyncio.to_thread(load_settings)
        approved.append(settings.research.output_dir.expanduser().resolve())
    except Exception:
        pass
    if any(_path_under(resolved, root) for root in approved):
        return None
    return "Access denied: path is outside approved Docent directories"


def _audit(action: str, detail: str) -> None:
    _audit_logger.info("%s | %s", action, detail)


_LOCALHOST_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _is_localhost_origin(origin: str) -> bool:
    """True if *origin* is empty or points at localhost.

    Shared by the HTTP middleware and the WebSocket handler so the cross-origin
    policy is identical on both transports. An empty Origin means the request did
    not originate from a browser (curl, local tooling) and is allowed; browsers
    always send Origin, so a *present but non-localhost* Origin is the cross-site
    drive-by vector we reject.

    The host is matched EXACTLY (via urlparse), not by prefix — a prefix check
    like ``startswith("http://localhost")`` would wrongly accept an attacker
    domain such as ``http://localhost.evil.com``.
    """
    if not origin:
        return True
    from urllib.parse import urlparse
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and parsed.hostname in _LOCALHOST_HOSTS


class _LocalhostGuard(BaseHTTPMiddleware):
    """Reject requests whose Origin header points to a non-localhost host.

    NOTE: Starlette's BaseHTTPMiddleware only runs on the `http` scope —
    WebSocket handshakes bypass it entirely. WebSocket endpoints must enforce
    the origin check themselves via `_is_localhost_origin` (see ui_routes/opencode.py).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not _is_localhost_origin(request.headers.get("origin", "")):
            return JSONResponse({"error": "Forbidden: non-localhost origin"}, status_code=403)
        return await call_next(request)


import re as _re

class _RSCPathRewrite:
    """Rewrite Next.js RSC payload URLs so StaticFiles can resolve them.

    Next.js client router requests:  /{route}/__next.{seg}.__PAGE__.txt
    Static export creates files at:  /{route}/__next.{seg}/__PAGE__.txt

    Pure ASGI middleware (not BaseHTTPMiddleware) so the scope mutation
    actually reaches the downstream StaticFiles app.
    """
    _pat = _re.compile(r"(/__next\.[^/]+)\.__PAGE__\.txt$")

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            path: str = scope.get("path", "")
            m = self._pat.search(path)
            if m:
                new_path = path[: m.start()] + m.group(1) + "/__PAGE__.txt"
                scope = dict(scope)
                scope["path"] = new_path
                scope["raw_path"] = new_path.encode("latin-1")
        await self.app(scope, receive, send)


app = FastAPI(docs_url=None, redoc_url=None)
app.add_middleware(GZipMiddleware, minimum_size=1000)  # compress JSON responses ≥ 1 KB
app.add_middleware(_RSCPathRewrite)   # must be before LocalhostGuard so the rewrite fires first
app.add_middleware(_LocalhostGuard)

# ── In-process caches ─────────────────────────────────────────────────────────
# All three caches are invalidated by mtime or TTL rather than explicit
# expiry, so a write to disk is immediately visible on the next read.

# 1. JSON file cache — covers queue.json, state.json, user.json, etc.
#    Key: str(path)  →  {"mtime": float, "data": Any}
_json_cache: dict[str, dict[str, Any]] = {}

def _read_json(path: Path, default: Any) -> Any:
    try:
        mtime = path.stat().st_mtime
        cached = _json_cache.get(str(path))
        if cached is not None and cached["mtime"] == mtime:
            return cached["data"]
        data = json.loads(path.read_text(encoding="utf-8"))
        _json_cache[str(path)] = {"mtime": mtime, "data": data}
        return data
    except Exception:
        return default

# 2. Config (config.toml) cache — mtime-gated; re-parsed only when file changes.
_cfg_cache: dict[str, Any] = {"_mtime": -1.0}

def _cached_toml() -> dict[str, Any]:
    path = _config_file()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    if _cfg_cache.get("_mtime") == mtime:
        return _cfg_cache
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return _cfg_cache
    _cfg_cache.clear()
    _cfg_cache.update({"_mtime": mtime, **data})
    return _cfg_cache

def _read_config_reading() -> dict:
    return _cached_toml().get("reading", {})

def _read_config_research() -> dict:
    return _cached_toml().get("research", {})

# 3. Database folder PDF count — 60-second TTL (recursive mtime is expensive;
#    TTL is accurate enough for a status-bar number).
_DB_COUNT_TTL = 60.0
_db_count_cache: dict[str, dict[str, Any]] = {}

def _scan_database(db_dir: Path) -> Optional[dict[str, Any]]:
    """Scan *db_dir* for PDFs, returning {count, files} cached for 60 seconds.

    A single rglob walk serves both the count (status-bar) and the filenames
    list (watch-folder inspector modal) — avoids scanning the directory twice.
    Returns None if the directory does not exist.
    """
    if not db_dir.is_dir():
        return None
    key = str(db_dir)
    cached = _db_count_cache.get(key)
    if cached is not None and _time.monotonic() - cached["ts"] < _DB_COUNT_TTL:
        return cached
    files = sorted(f.name for f in db_dir.rglob("*.pdf"))
    entry: dict[str, Any] = {"ts": _time.monotonic(), "count": len(files), "files": files}
    _db_count_cache[key] = entry
    return entry

def _get_database_count(db_dir: Path) -> Optional[int]:
    entry = _scan_database(db_dir)
    return entry["count"] if entry is not None else None

def _get_database_files(db_dir: Path) -> list[str]:
    entry = _scan_database(db_dir)
    return entry["files"] if entry is not None else []


def _mask_key(key: str | None) -> Optional[str]:
    if not key:
        return None
    if len(key) <= 8:
        return "***"
    return key[:4] + "..." + key[-4:]


async def _run_command(cmd: str, args: list[str], timeout: float = 30.0) -> tuple[str, str, int]:
    # Resolve via PATH so Windows .cmd/.bat shims (npm.cmd, docent.cmd) launch
    # without shell=True — create_subprocess_exec won't find them otherwise.
    import shutil
    exe = shutil.which(cmd)
    if exe is None:
        raise FileNotFoundError(f"{cmd!r} not found on PATH")
    proc = await asyncio.create_subprocess_exec(
        exe, *args,
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


# /api/queue → ui_routes/reading.py


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


# /api/actions → ui_routes/reading.py


_RESEARCH_KEY_FIELDS = [
    "tavily_api_key",
    "semantic_scholar_api_key",
    "alphaxiv_api_key",
    "groq_api_key",
    # Archived: gemini_api_key, openrouter_api_key, mistral_api_key, cerebras_api_key
    # (fields still in settings.py schema; restore here + in RESEARCH_KEY_FIELDS
    #  on the settings page to re-expose them)
]


# /api/config GET → ui_routes/config.py


class ConfigBody(BaseModel):
    section: str
    key: str
    value: str


# /api/config POST → ui_routes/config.py


# /api/user GET → ui_routes/config.py


class UserBody(BaseModel):
    name: str
    program: str
    level: str


# /api/user POST → ui_routes/config.py


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


# /api/tooling + /api/doctor → ui_routes/doctor.py

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
    'citegraph': 'cite-graph',
    'notebook':  'to-notebook',
    'cfgshow':   'config-show',
    'cfgset':    'config-set',
}

_BACKEND_NORM: dict[str, str] = {
    'free': 'free', 'feynman': 'feynman', 'docent': 'docent', 'groq': 'groq',
    # Archived: gemini, openrouter, anthropic, openai, ollama, lm_studio, mistral, cerebras
    # (still work from the CLI with --backend <name>; restore here to re-enable in the UI)
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
    cite_identifier: str = ""
    cite_direction: str = "cited-by"
    cite_max: int = 25


def _parse_studio_body(body: StudioRunBody) -> tuple[str, dict[str, Any]] | None:
    """Return (studio_action, args_dict) for a StudioRunBody, or None if action unknown.

    Form→action mapping for the *in-process* path: the SSE endpoint
    (/api/studio/run) and `_form_to_studio_args` both derive from here.

    WARNING: the live frontend uses the *subprocess* WebSocket path
    (/ws/studio/run), whose CLI-flag builder `_build_studio_cmd` in
    ui_routes/opencode.py is a SEPARATE mapping that does NOT derive from this
    function. Any new studio action or argument must be added in BOTH places
    until the two paths are unified. They already share `_STUDIO_ACTION_MAP`
    and `_BACKEND_NORM` (below) — keep per-action arg handling in sync by hand.
    """
    studio_action = _STUDIO_ACTION_MAP.get(body.action_id)
    if not studio_action:
        return None
    backend = _BACKEND_NORM.get(body.backend.lower().replace(' ', '_'), 'free')
    dest = body.dest.lower().replace(' →', '').strip()

    if studio_action in ('deep-research', 'lit', 'draft'):
        args: dict[str, Any] = {
            'topic': body.topic, 'backend': backend,
            'output': dest, 'guide_files': body.guides,
        }
        # deep-research/lit gate the free backend behind a disclaimer; pre-confirm
        # it here so the UI doesn't need a second prompt. draft is AI-backend-only
        # and its DraftInputs model has no `confirmed` field.
        if studio_action in ('deep-research', 'lit'):
            args['confirmed'] = True
    elif studio_action in ('review', 'replicate', 'audit'):
        args = {'artifact': body.artifact, 'backend': backend, 'output': dest, 'guide_files': body.guides}
    elif studio_action == 'compare':
        args = {
            'artifact_a': body.artifact_a, 'artifact_b': body.artifact_b,
            'backend': backend, 'output': dest, 'guide_files': body.guides,
        }
    elif studio_action in ('search-papers', 'scholarly-search'):
        args = {'query': body.query, 'max_results': body.max_results}
    elif studio_action == 'get-paper':
        args = {'arxiv_id': body.arxiv_id}
    elif studio_action == 'cite-graph':
        import re as _re
        ident = body.cite_identifier.strip()
        is_arxiv = bool(
            'arxiv' in ident.lower()
            or _re.match(r'^\d{4}\.\d{4,5}', ident)
        )
        args = {
            'doi': None if is_arxiv else ident,
            'arxiv_id': ident if is_arxiv else None,
            'direction': body.cite_direction,
            'max_results': body.cite_max,
        }
    elif studio_action == 'to-notebook':
        args = {
            'output_file': body.out_path or None,
            'sources_file': body.src_path or None,
            'max_sources': body.max_sources,
            'run_nlm_research': body.nlm,
            'run_quality_gate': body.gate,
            'run_perspectives': body.persp,
        }
    elif studio_action == 'config-show':
        args = {}
    elif studio_action == 'config-set':
        args = {'key': body.cfg_key, 'value': body.cfg_val}
    else:
        args = {}
    return studio_action, args


def _form_to_studio_args(action_id: str, body: StudioRunBody) -> dict[str, Any]:
    parsed = _parse_studio_body(body)
    if parsed is None:
        return {}
    return parsed[1]


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

    def _sse(data: dict) -> bytes:
        # SSE comment line + the data event. The comment acts as a keepalive marker
        # and adds bytes so chunks aren't coalesced by TCP Nagle on Windows.
        # We yield bytes directly (not str) to avoid an extra encoding step in Starlette
        # and to ensure each chunk goes through `transport.write()` as a single syscall.
        return (f": ping\ndata: {json.dumps(data)}\n\n").encode("utf-8")

    # Prime the response with a 2KB SSE comment. Chrome and other browsers may
    # delay exposing chunks to JavaScript until the response body exceeds a small
    # threshold; this padding forces the stream to start flowing immediately.
    yield (": " + ("-" * 2048) + "\n\n").encode("utf-8")
    await asyncio.sleep(0.01)

    thread = loop.run_in_executor(None, _run_in_thread)
    try:
        while True:
            kind, payload = await q.get()
            if kind == 'event':
                evt = payload
                if evt.message:
                    yield _sse({'type': 'log', 'phase': evt.phase, 'text': evt.message, 'level': evt.level})
                    # asyncio.sleep with a small non-zero delay forces the event loop to
                    # poll I/O and flush the transport's write buffer. sleep(0) alone is
                    # not enough on Windows ProactorEventLoop — it schedules a callback
                    # but doesn't guarantee an I/O flush cycle.
                    await asyncio.sleep(0.01)
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


# /api/fs/* → ui_routes/filesystem.py

# /api/studio/outputs → ui_routes/filesystem.py

# ── OpenCode server management ─────────────────────────────────────────────────

_opencode_proc: Optional[subprocess.Popen] = None  # type: ignore[type-arg]


# /api/opencode/* + /ws/studio/run → ui_routes/opencode.py

# ── Route modules ────────────────────────────────────────────────────────────
# Routes live in ui_routes/*; imported here so their @router decorators fire.
# Each module's router is included before the static-file catch-all.
from docent.ui_routes.reading import router as _reading_router
from docent.ui_routes.config import router as _config_router
from docent.ui_routes.doctor import router as _doctor_router
from docent.ui_routes.filesystem import router as _fs_router
from docent.ui_routes.opencode import router as _opencode_router
from docent.ui_routes.studio import router as _studio_sse_router
from docent.ui_routes.backup import router as _backup_router
from docent.ui_routes.tools import router as _tools_router
from docent.ui_routes.docs import router as _docs_router

app.include_router(_reading_router)
app.include_router(_config_router)
app.include_router(_doctor_router)
app.include_router(_fs_router)
app.include_router(_opencode_router)
app.include_router(_studio_sse_router)
app.include_router(_backup_router)
app.include_router(_tools_router)
app.include_router(_docs_router)


if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")


def run_server(host: str = "127.0.0.1", port: int = 7432) -> None:
    from docent.core import load_plugins
    from docent.tools import discover_tools
    from docent.bundled_plugins.reading.reading_store import cleanup_legacy_paper_dirs
    discover_tools()
    load_plugins()
    cleanup_legacy_paper_dirs()

    # Set up audit log
    audit_log_path = _docent_dir() / "audit.log"
    try:
        audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(audit_log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        _audit_logger.addHandler(handler)
        _audit_logger.setLevel(logging.INFO)
    except Exception:
        pass

    uvicorn.run(
        app,
        host=host,
        port=port,
        access_log=False,   # suppress per-request INFO lines; errors still surface as exceptions
        # Disable response buffering so SSE events reach the browser immediately.
        # h11_max_incomplete_event_size=None prevents h11 from buffering partial events.
        h11_max_incomplete_event_size=16 * 1024 * 1024,
    )

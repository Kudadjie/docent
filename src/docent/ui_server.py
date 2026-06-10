"""FastAPI backend for the Docent web UI.

This module only assembles the app: middleware, router includes, static files,
and ``run_server``. Shared helpers live in ``docent.ui_routes._shared``; the
Studio form builders live in ``docent.ui_routes._studio_request``. Both are
re-exported here for backward compatibility (tests and external callers
historically imported them from ``docent.ui_server``).
"""

import logging
import re as _re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# Re-exports — keep the historical ``docent.ui_server`` import surface working.
from docent.ui_routes._shared import (  # noqa: F401
    _audit,
    _audit_logger,
    _cached_toml,
    _check_approved_path,
    _config_file,
    _docent_dir,
    _get_database_count,
    _get_database_files,
    _is_localhost_origin,
    _mask_key,
    _path_under,
    _queue_file,
    _read_config_reading,
    _read_config_research,
    _read_json,
    _run,
    _run_command,
    _scan_database,
    _state_file,
    _user_file,
    _version_at_least,
)
from docent.ui_routes._studio_request import (  # noqa: F401
    _BACKEND_NORM,
    _STUDIO_ACTION_MAP,
    StudioRequest,
    StudioRunBody,
    _form_to_studio_args,
    _parse_studio_body,
    _stream_studio_run,
    build_studio_request,
)

UI_DIST = Path(__file__).parent / "ui_dist"

_log = logging.getLogger("docent.ui")


class _LocalhostGuard(BaseHTTPMiddleware):
    """Reject requests whose Origin header points to a non-localhost host.

    /mcp/* routes are exempt — they are API-key-protected and intentionally
    reachable from remote clients.

    NOTE: Starlette's BaseHTTPMiddleware only runs on the `http` scope —
    WebSocket handshakes bypass it entirely. WebSocket endpoints must enforce
    the origin check themselves via `_is_localhost_origin` (see ui_routes/opencode.py).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path.startswith("/mcp/"):
            return await call_next(request)
        if not _is_localhost_origin(request.headers.get("origin", "")):
            return JSONResponse({"error": "Forbidden: non-localhost origin"}, status_code=403)
        return await call_next(request)


# ── Session token ─────────────────────────────────────────────────────────────
# The Origin check above blocks cross-site browser requests, but NOT requests
# from other localhost origins (e.g. a dev server on :3000) or local non-browser
# processes. Any of those could otherwise POST /api/tools/invoke — which reaches
# plugin_builder install, i.e. arbitrary code on the next docent run. So every
# state-changing /api request must also carry a per-session token.
#
# Delivery: the frontend GETs /api/auth/token (same-origin only in practice —
# without CORS headers a cross-origin page cannot READ the response) and sends
# it back as X-Docent-Token on mutating requests. The WebSocket path receives
# it inside the first JSON message instead (browsers can't set WS headers).
#
# The token is None under TestClient and direct ASGI use; enforcement only
# activates when run_server() generates one.

_session_token: str | None = None
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def get_session_token() -> str | None:
    return _session_token


def set_session_token(token: str | None) -> None:
    global _session_token
    _session_token = token


class _SessionTokenGuard(BaseHTTPMiddleware):
    """Require X-Docent-Token on mutating /api/* requests once a token is set.

    /mcp/* is exempt (bearer-key auth). GETs are exempt — they are read-only
    and a cross-origin page cannot read their responses anyway.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        token = _session_token
        if (
            token is not None
            and request.method in _MUTATING_METHODS
            and request.url.path.startswith("/api/")
            and request.headers.get("x-docent-token", "") != token
        ):
            _audit("token.denied", f"{request.method} {request.url.path}")
            return JSONResponse(
                {"error": "Forbidden: missing or invalid X-Docent-Token"}, status_code=403
            )
        return await call_next(request)


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
app.add_middleware(_RSCPathRewrite)  # must be before LocalhostGuard so the rewrite fires first
app.add_middleware(_SessionTokenGuard)
app.add_middleware(_LocalhostGuard)


@app.get("/api/auth/token")
async def get_auth_token() -> JSONResponse:
    """Hand the per-session API token to the frontend.

    Safe to expose on a GET: responses carry no CORS headers, so a page on a
    different origin (including a different localhost port) cannot read it.
    """
    return JSONResponse({"token": _session_token})


# ── Route modules ────────────────────────────────────────────────────────────
# Routes live in ui_routes/*; imported here so their @router decorators fire.
# Each module's router is included before the static-file catch-all.
from docent.ui_routes.backup import router as _backup_router  # noqa: E402
from docent.ui_routes.config import router as _config_router  # noqa: E402
from docent.ui_routes.docs import router as _docs_router  # noqa: E402
from docent.ui_routes.doctor import router as _doctor_router  # noqa: E402
from docent.ui_routes.filesystem import router as _fs_router  # noqa: E402
from docent.ui_routes.opencode import router as _opencode_router  # noqa: E402
from docent.ui_routes.reading import router as _reading_router  # noqa: E402
from docent.ui_routes.studio import router as _studio_sse_router  # noqa: E402
from docent.ui_routes.tools import router as _tools_router  # noqa: E402
from docent.ui_routes.whatsnew import router as _whatsnew_router  # noqa: E402

app.include_router(_reading_router)
app.include_router(_config_router)
app.include_router(_doctor_router)
app.include_router(_fs_router)
app.include_router(_opencode_router)
app.include_router(_studio_sse_router)
app.include_router(_backup_router)
app.include_router(_tools_router)
app.include_router(_docs_router)
app.include_router(_whatsnew_router)


if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")


def run_server(host: str = "127.0.0.1", port: int = 7432) -> None:
    import secrets

    from docent.bundled_plugins.reading.reading_store import cleanup_legacy_paper_dirs
    from docent.config import load_settings, write_setting
    from docent.core import load_plugins
    from docent.mcp_server import mount_mcp_sse
    from docent.tools import discover_tools

    discover_tools()
    load_plugins()
    cleanup_legacy_paper_dirs()

    # Per-session token guarding all mutating /api requests (see _SessionTokenGuard).
    set_session_token(secrets.token_urlsafe(32))

    # Generate API key on first start, then mount MCP HTTP transport.
    settings = load_settings()
    if settings.serve.http_mcp_enabled:
        api_key = settings.serve.api_key
        if not api_key:
            api_key = secrets.token_urlsafe(32)
            write_setting("serve.api_key", api_key)
            _log.info("Generated MCP HTTP API key — stored in ~/.docent/config.toml")
        mount_mcp_sse(app, api_key)
        _log.info("MCP HTTP transport active at /mcp/sse (port %d)", port)

    # Set up audit log
    audit_log_path = _docent_dir() / "audit.log"
    try:
        audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(audit_log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        _audit_logger.addHandler(handler)
        _audit_logger.setLevel(logging.INFO)
    except Exception as exc:
        # Audit logging is security-relevant — surface init failure loudly
        # rather than silently running without an audit trail.
        _log.warning("Failed to initialise audit log at %s: %s", audit_log_path, exc)

    uvicorn.run(
        app,
        host=host,
        port=port,
        access_log=False,  # suppress per-request INFO lines; errors still surface as exceptions
        # Allow large incomplete h11 events (16 MB) so long SSE chunks aren't
        # buffered/split by the server before reaching the browser.
        h11_max_incomplete_event_size=16 * 1024 * 1024,
    )

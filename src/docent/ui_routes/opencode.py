"""OpenCode server management and WebSocket subprocess streaming."""

import asyncio
import logging
import os
import subprocess
import sys

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router: APIRouter = APIRouter()
from docent.ui_routes._shared import _audit  # noqa: E402

_log = logging.getLogger("docent.ui.opencode")

_opencode_proc: subprocess.Popen | None = None


@router.post("/api/opencode/start")
async def opencode_start() -> JSONResponse:
    global _opencode_proc
    _audit("opencode-start", "requested")
    import shutil

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get("http://127.0.0.1:4096/global/health")
            if r.status_code == 200:
                return JSONResponse({"ok": True, "status": "already_running"})
    except Exception:
        pass

    oc_exe = shutil.which("opencode")
    if not oc_exe:
        hint = (
            "opencode not found on PATH. "
            "Install with: npm install -g opencode-ai  "
            "(needs Node.js — run `docent doctor` for setup help)."
        )
        return JSONResponse({"ok": False, "error": hint}, status_code=500)

    try:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP
        _opencode_proc = subprocess.Popen(
            [oc_exe, "serve", "--port", "4096"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=flags,
        )
        await asyncio.sleep(2.0)

        if _opencode_proc.poll() is not None:
            rc = _opencode_proc.returncode
            err = ""
            try:
                err = (
                    (_opencode_proc.stderr.read() or b"").decode("utf-8", errors="replace")[:400]
                    if _opencode_proc.stderr
                    else ""
                )
            except Exception as exc:
                _log.debug("Could not read opencode stderr after immediate exit: %s", exc)
            _opencode_proc = None
            return JSONResponse(
                {"ok": False, "error": f"opencode exited immediately (rc={rc}). {err}".strip()},
                status_code=500,
            )

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get("http://127.0.0.1:4096/global/health")
                if r.status_code == 200:
                    return JSONResponse(
                        {"ok": True, "status": "started", "pid": _opencode_proc.pid}
                    )
        except Exception:
            pass

        return JSONResponse(
            {
                "ok": True,
                "status": "started",
                "pid": _opencode_proc.pid,
                "warning": "Process started but :4096 not yet reachable. Retry status check in a few seconds.",
            }
        )
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/api/opencode/stop")
async def opencode_stop() -> JSONResponse:
    global _opencode_proc
    _audit("opencode-stop", "requested")
    if _opencode_proc is not None:
        try:
            # opencode was started in its own process group (CREATE_NEW_PROCESS_GROUP
            # on Windows); signal the group so child workers don't orphan, then
            # fall back to a hard terminate.
            if sys.platform == "win32":
                try:
                    os.kill(_opencode_proc.pid, __import__("signal").CTRL_BREAK_EVENT)
                except (OSError, AttributeError, ValueError) as exc:
                    _log.debug("CTRL_BREAK_EVENT to opencode failed: %s", exc)
            _opencode_proc.terminate()
            _opencode_proc = None
            return JSONResponse({"ok": True, "status": "stopped"})
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return JSONResponse({"ok": True, "status": "not_running"})


@router.get("/api/opencode/status")
async def opencode_status() -> JSONResponse:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get("http://127.0.0.1:4096/global/health")
            if r.status_code == 200:
                return JSONResponse({"running": True})
    except Exception:
        pass
    return JSONResponse({"running": False})


# ── NotebookLM auth endpoints ─────────────────────────────────────────────────


def _playwright_chromium_ok() -> bool:
    """Return True if Playwright's Chromium binary exists on disk."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # executable_path is None when not downloaded; non-None when it exists.
            path = p.chromium.executable_path
            if not path:
                return False
            import os

            return os.path.isfile(path)
    except Exception:
        return False


@router.get("/api/notebooklm/auth-status")
async def notebooklm_auth_status() -> JSONResponse:
    """Return whether the notebooklm CLI is installed, Playwright is ready, and auth is current."""
    import shutil as _sh

    exe = _sh.which("notebooklm")
    if not exe:
        return JSONResponse({"installed": False, "playwright_ok": False, "authenticated": False})

    loop = asyncio.get_running_loop()

    # Check Playwright binary first — auth check will always fail without it.
    playwright_ok = await loop.run_in_executor(None, _playwright_chromium_ok)
    if not playwright_ok:
        return JSONResponse(
            {
                "installed": True,
                "playwright_ok": False,
                "authenticated": False,
                "fix": "playwright install chromium",
            }
        )

    try:
        from docent.bundled_plugins.studio._notebook import _nlm_auth_ok

        authenticated = await loop.run_in_executor(
            None, lambda: _nlm_auth_ok(retries=1, retry_delay=1.0)
        )
    except Exception:
        authenticated = False
    return JSONResponse({"installed": True, "playwright_ok": True, "authenticated": authenticated})


@router.post("/api/notebooklm/auth")
async def notebooklm_auth() -> JSONResponse:
    """Open a visible terminal window to run `notebooklm login` interactively."""
    # Shares the terminal-spawn logic with the in-run auth recovery in _notebook.py.
    from docent.bundled_plugins.studio._notebook import _open_login_terminal

    launched, err = _open_login_terminal()
    if not launched:
        if "not found on PATH" in err:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "notebooklm not found on PATH. Install with: pip install notebooklm",
                },
                status_code=404,
            )
        return JSONResponse({"ok": False, "error": err}, status_code=500)
    _audit("notebooklm-auth", "terminal opened")
    return JSONResponse({"ok": True, "message": "Terminal opened for authentication."})

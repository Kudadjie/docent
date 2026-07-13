"""NotebookLM auth endpoints (lived in ui_routes/opencode.py until the
OpenCode subsystem was removed in v2.3)."""

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from docent.ui_routes._shared import _audit

router: APIRouter = APIRouter()


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

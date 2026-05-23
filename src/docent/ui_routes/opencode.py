"""OpenCode server management and WebSocket subprocess streaming."""
import asyncio
import json
import os
import re
import subprocess
import sys
from typing import Any, Optional

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

router = APIRouter()
from pydantic import BaseModel

from docent.core.invoke import serialize_result as _serialize


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


_opencode_proc: Optional[subprocess.Popen] = None


def _audit(action: str, detail: str) -> None:
    from docent.ui_server import _audit as _a
    _a(action, detail)


def _build_studio_cmd(body: StudioRunBody) -> list[str] | None:
    """Build a `docent studio <action> ...` subprocess command from the UI form body."""
    import shutil as _sh
    from docent.ui_server import _STUDIO_ACTION_MAP, _BACKEND_NORM

    action = _STUDIO_ACTION_MAP.get(body.action_id)
    if not action:
        return None
    docent_exe = _sh.which("docent")
    if not docent_exe:
        return None

    backend = _BACKEND_NORM.get(body.backend.lower().replace(" ", "_"), "free")
    dest = body.dest.lower().replace(" →", "").strip()
    cmd: list[str] = [docent_exe, "studio", action]

    if action in ("deep-research", "lit", "draft"):
        cmd += ["--topic", body.topic, "--backend", backend, "--output", dest, "--confirmed"]
        for g in (body.guides or []):
            cmd += ["--guide-files", g]
    elif action in ("review", "replicate", "audit"):
        cmd += ["--artifact", body.artifact, "--backend", backend, "--output", dest]
        for g in (body.guides or []):
            cmd += ["--guide-files", g]
    elif action == "compare":
        cmd += ["--artifact-a", body.artifact_a, "--artifact-b", body.artifact_b,
                "--backend", backend, "--output", dest]
        for g in (body.guides or []):
            cmd += ["--guide-files", g]
    elif action in ("search-papers", "scholarly-search"):
        cmd += ["--query", body.query, "--max-results", str(body.max_results)]
    elif action == "get-paper":
        cmd += ["--arxiv-id", body.arxiv_id]
    elif action == "to-notebook":
        if body.src_path:
            cmd += ["--sources-file", body.src_path]
        # Derive output-file from sources path when not explicitly set.
        # This prevents the interactive preflight file-picker from activating
        # (which hangs in a non-TTY subprocess when multiple outputs exist).
        out_file = body.out_path or re.sub(r"-sources\.json$", ".md", body.src_path)
        if out_file and out_file != body.src_path:
            cmd += ["--output-file", out_file]
        cmd += ["--max-sources", str(body.max_sources)]
        if not body.nlm:
            cmd += ["--no-run-nlm-research"]
        if not body.gate:
            cmd += ["--no-run-quality-gate"]
        if not body.persp:
            cmd += ["--no-run-perspectives"]
    elif action == "config-set":
        cmd += ["--key", body.cfg_key, "--value", body.cfg_val]
    # config-show has no extra args

    return cmd


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
                err = (_opencode_proc.stderr.read() or b"").decode("utf-8", errors="replace")[:400] if _opencode_proc.stderr else ""
            except Exception:
                pass
            _opencode_proc = None
            return JSONResponse(
                {"ok": False, "error": f"opencode exited immediately (rc={rc}). {err}".strip()},
                status_code=500,
            )

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get("http://127.0.0.1:4096/global/health")
                if r.status_code == 200:
                    return JSONResponse({"ok": True, "status": "started", "pid": _opencode_proc.pid})
        except Exception:
            pass

        return JSONResponse({
            "ok": True,
            "status": "started",
            "pid": _opencode_proc.pid,
            "warning": "Process started but :4096 not yet reachable. Retry status check in a few seconds.",
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/api/opencode/stop")
async def opencode_stop() -> JSONResponse:
    global _opencode_proc
    _audit("opencode-stop", "requested")
    if _opencode_proc is not None:
        try:
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

    loop = asyncio.get_event_loop()

    # Check Playwright binary first — auth check will always fail without it.
    playwright_ok = await loop.run_in_executor(None, _playwright_chromium_ok)
    if not playwright_ok:
        return JSONResponse({
            "installed": True,
            "playwright_ok": False,
            "authenticated": False,
            "fix": "playwright install chromium",
        })

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
    import shutil as _sh
    exe = _sh.which("notebooklm")
    if not exe:
        return JSONResponse(
            {
                "ok": False,
                "error": "notebooklm not found on PATH. Install with: pip install notebooklm",
            },
            status_code=404,
        )
    try:
        if sys.platform == "win32":
            # Start a new visible Command Prompt that stays open after the command.
            subprocess.Popen(
                f'start "NotebookLM Auth" cmd /k "{exe} login"',
                shell=True,
            )
        elif sys.platform == "darwin":
            subprocess.Popen(
                ["osascript", "-e", f'tell app "Terminal" to do script "{exe} login"']
            )
        else:
            # Linux: try common terminal emulators in order.
            _launched = False
            for term, args in [
                ("gnome-terminal", ["--", exe, "login"]),
                ("xfce4-terminal", ["-e", f"{exe} login"]),
                ("konsole", ["-e", exe, "login"]),
                ("xterm", ["-e", exe, "login"]),
            ]:
                if _sh.which(term):
                    subprocess.Popen([term] + args)
                    _launched = True
                    break
            if not _launched:
                return JSONResponse(
                    {
                        "ok": False,
                        "error": (
                            "No terminal emulator found. "
                            "Run `notebooklm login` in a terminal manually."
                        ),
                    },
                    status_code=500,
                )
        _audit("notebooklm-auth", "terminal opened")
        return JSONResponse({"ok": True, "message": "Terminal opened for authentication."})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.websocket("/ws/studio/run")
async def studio_run_ws(websocket: WebSocket):
    """WebSocket endpoint — pipes `docent studio <action>` subprocess stdout live."""
    await websocket.accept()

    try:
        body_raw = await websocket.receive_json()
        body = StudioRunBody(**body_raw)
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": f"Bad request: {exc}"})
        except Exception:
            pass
        return

    cmd = _build_studio_cmd(body)
    if cmd is None:
        try:
            await websocket.send_json({
                "type": "error",
                "message": (
                    f"Action '{body.action_id}' not found or 'docent' not on PATH. "
                    "Make sure docent is installed and on PATH."
                ),
            })
        except Exception:
            pass
        return

    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "NO_COLOR": "1",
        "FORCE_COLOR": "0",
        "TERM": "dumb",
        "COLUMNS": "1000",
        "DOCENT_UI_SUBPROCESS": "1",
    }

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )

    output_file: str | None = None
    notebook_id: str | None = None
    result_ok: bool = True        # overridden by RESULT_MARKER if action sets ok=False
    result_message: str | None = None
    _RESULT_MARKER   = "\x00DOCENT_RESULT\x00"
    _PROGRESS_MARKER = "\x00DOCENT_PROGRESS\x00"

    try:
        assert proc.stdout is not None
        async for raw_bytes in proc.stdout:
            line = raw_bytes.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue

            # Structured result line (emitted at process end)
            if _RESULT_MARKER in line:
                try:
                    payload = json.loads(line[line.index(_RESULT_MARKER) + len(_RESULT_MARKER):])
                    output_file = payload.get("output_file") or output_file
                    notebook_id = payload.get("notebook_id") or notebook_id
                    # Track ok/message so we can set status correctly even when
                    # the subprocess exits 0 (e.g. Feynman credit failures).
                    if "ok" in payload:
                        result_ok = bool(payload["ok"])
                    if "message" in payload:
                        result_message = str(payload["message"])
                except Exception:
                    pass
                continue

            # Structured progress line — unambiguous, emitted by _drive_progress
            # Format: \x00DOCENT_PROGRESS\x00<phase>\x00<message>
            if _PROGRESS_MARKER in line:
                rest = line[line.index(_PROGRESS_MARKER) + len(_PROGRESS_MARKER):]
                parts = rest.split("\x00", 1)
                phase = parts[0]
                # Unescape \x02 → \n (CLI escapes newlines to keep the marker on one line)
                text  = (parts[1] if len(parts) > 1 else "").replace("\x02", "\n")
                if phase:
                    try:
                        await websocket.send_json({"type": "log", "phase": phase, "text": text})
                    except Exception:
                        proc.terminate()
                        return
                continue

            # All other output (Rich console, tracebacks, preflight errors, etc.)
            # is relayed as a "console" phase log so the UI shows a live stream
            # of everything the CLI would print.  ANSI escape codes and carriage
            # returns are stripped so the text is readable without a real terminal.
            _ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mGKHFJA-Za-z]|\r')
            stripped = _ANSI_RE.sub('', line).strip()
            if stripped:
                try:
                    await websocket.send_json({"type": "log", "phase": "console", "text": stripped})
                except Exception:
                    proc.terminate()
                    return

    except WebSocketDisconnect:
        proc.terminate()
        return
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
        proc.terminate()
        return

    await proc.wait()

    result: dict[str, Any] = {}
    if output_file:
        result["output_file"] = output_file
    if notebook_id:
        result["notebook_id"] = notebook_id
    if result_message:
        result["message"] = result_message

    # Success only when the process exits 0 AND the action itself reported ok=True.
    # Feynman (and similar tools) can exit 0 even on credit/quota failures; in that
    # case the CLI emits ok=False in the RESULT_MARKER so we still surface a failure.
    action_ok = proc.returncode == 0 and result_ok

    try:
        if action_ok:
            await websocket.send_json({
                "type": "done", "status": "success", "raw": json.dumps(result),
            })
        else:
            await websocket.send_json({
                "type": "done", "status": "failure", "raw": json.dumps(result),
            })
    except Exception:
        pass
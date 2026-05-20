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


def _build_studio_cmd(body: StudioRunBody):
    from docent.ui_server import _build_studio_cmd as _bsc
    return _bsc(body)


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
    _RESULT_MARKER = "\x00DOCENT_RESULT\x00"

    try:
        assert proc.stdout is not None
        async for raw_bytes in proc.stdout:
            line = raw_bytes.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue

            if _RESULT_MARKER in line:
                try:
                    payload = json.loads(line[line.index(_RESULT_MARKER) + len(_RESULT_MARKER):])
                    output_file = payload.get("output_file") or output_file
                    notebook_id = payload.get("notebook_id") or notebook_id
                except Exception:
                    pass
                continue

            line_clean = re.sub(r"\[/?[^\]]*\]", "", line).strip()
            if not line_clean:
                continue

            parts = line_clean.split(None, 1)
            raw_phase = parts[0]
            if not re.match(r'^[a-z][a-z0-9_]*$', raw_phase):
                continue
            phase = raw_phase
            text = parts[1] if len(parts) > 1 else line_clean

            try:
                await websocket.send_json({"type": "log", "phase": phase, "text": text})
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

    try:
        if proc.returncode == 0:
            await websocket.send_json({
                "type": "done", "status": "success", "raw": json.dumps(result),
            })
        else:
            await websocket.send_json({
                "type": "done", "status": "failure", "raw": json.dumps({}),
            })
    except Exception:
        pass
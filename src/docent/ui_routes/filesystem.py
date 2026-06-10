"""Filesystem and studio outputs endpoints."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


class FsOpenBody(BaseModel):
    path: str


class FsPickBody(BaseModel):
    extensions: list[str] = []
    title: str = "Select files"


from docent.ui_routes._shared import _audit, _check_approved_path  # noqa: E402


@router.get("/api/fs/read")
async def fs_read(path: str = Query(...)) -> JSONResponse:
    """Read a text file from the local filesystem (for Markdown preview)."""
    p = Path(path)
    denied = await _check_approved_path(p)
    if denied:
        _audit("fs_read.denied", path)
        return JSONResponse({"error": denied}, status_code=403)
    try:
        # Operate on the same canonical path the approval check validated
        # (resolve() follows symlinks and collapses ..) — not a separate,
        # un-resolved form, which would be a latent path-traversal seam.
        resolved = p.expanduser().resolve()
        if not resolved.is_file():
            return JSONResponse({"error": f"File not found: {path}"}, status_code=404)
        size = resolved.stat().st_size
        if size > 500_000:
            return JSONResponse({"error": "File too large to preview (>500 KB)"}, status_code=400)
        content = resolved.read_text(encoding="utf-8", errors="replace")
        return JSONResponse({"content": content})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/api/fs/open")
async def fs_open(body: FsOpenBody) -> JSONResponse:
    """Open a file or its parent folder in the OS file manager."""
    p = Path(body.path)
    denied = await _check_approved_path(p)
    if denied:
        _audit("fs_open.denied", body.path)
        return JSONResponse({"error": denied}, status_code=403)
    try:
        # Use the resolved path the approval check validated (see fs_read).
        resolved = p.expanduser().resolve()
        target = resolved if resolved.is_dir() else resolved.parent
        _audit("fs_open", str(target))
        if sys.platform == "win32":
            os.startfile(str(target))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return JSONResponse({"ok": True})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/api/fs/pick")
async def fs_pick(body: FsPickBody) -> JSONResponse:
    """Open a native OS file-picker dialog and return selected paths."""

    def _pick() -> list[str]:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
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


@router.get("/api/studio/outputs")
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
        for f in sorted(output_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[
            :30
        ]:
            try:
                stat = f.stat()
                files.append(
                    {
                        "path": str(f),
                        "name": f.name,
                        "folder": f.parent.name,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                    }
                )
            except Exception:
                pass
    except Exception:
        pass

    return JSONResponse({"files": files, "output_dir": str(output_dir)})

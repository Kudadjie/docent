"""Backup/restore endpoints for the Docent web UI."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

router = APIRouter()


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/api/backup/status")
async def backup_status() -> JSONResponse:
    """Return drive credentials state without making any Drive API calls."""
    from docent.bundled_plugins.backup.drive_client import (
        credentials_file_exists, _token_path,
    )

    creds_ok = credentials_file_exists()
    token_ok = _token_path().exists() if creds_ok else False

    deps_ok = False
    if creds_ok:
        try:
            import google.oauth2.credentials  # noqa: F401
            import google_auth_oauthlib  # noqa: F401
            import googleapiclient  # noqa: F401
            deps_ok = True
        except ImportError:
            pass

    return JSONResponse({
        "credentials_configured": creds_ok,
        "deps_installed": deps_ok,
        "token_exists": token_ok,
        "install_cmd": "pip install 'docent-cli[backup]'" if not deps_ok else None,
    })


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/api/backup/list")
async def list_drive_backups() -> JSONResponse:
    """Return recent backups from Google Drive."""
    try:
        from docent.bundled_plugins.backup.drive_client import (
            get_service, get_or_create_backup_folder, list_backups,
        )
        service = await asyncio.to_thread(get_service)
        folder_id = await asyncio.to_thread(get_or_create_backup_folder, service)
        backups = await asyncio.to_thread(list_backups, service, folder_id)
        return JSONResponse({
            "ok": True,
            "backups": [
                {
                    "id": b["id"],
                    "name": b["name"],
                    "size_mb": round(int(b.get("size", 0)) / 1_048_576, 1),
                    "created": b.get("createdTime", "")[:10],
                }
                for b in backups
            ],
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── Run backup ────────────────────────────────────────────────────────────────

class BackupBody(BaseModel):
    local_only: bool = False


@router.post("/api/backup/run")
async def run_backup(body: BackupBody) -> JSONResponse:
    """Create a backup archive and optionally upload to Google Drive."""
    from docent.bundled_plugins.backup.manager import create_archive, archive_name

    tmp_dir = Path(tempfile.mkdtemp())
    dest = tmp_dir / archive_name()

    try:
        manifest = await asyncio.to_thread(create_archive, dest)

        if body.local_only:
            # Caller will download via /api/backup/download — leave file in tmp
            return JSONResponse({
                "ok": True,
                "local_only": True,
                "archive_name": dest.name,
                "size_mb": manifest["archive_size_mb"],
                "files_included": manifest["files_included"],
                "files_excluded": manifest["files_excluded"],
                "excluded": manifest.get("excluded", []),
            })

        # Upload to Drive
        from docent.bundled_plugins.backup.drive_client import (
            get_service, get_or_create_backup_folder, upload_backup, trim_old_backups,
        )
        service = await asyncio.to_thread(get_service)
        folder_id = await asyncio.to_thread(get_or_create_backup_folder, service)
        file_id = await asyncio.to_thread(upload_backup, service, dest, folder_id, dest.name)
        deleted = await asyncio.to_thread(trim_old_backups, service, folder_id)

        return JSONResponse({
            "ok": True,
            "local_only": False,
            "drive_file_id": file_id,
            "archive_name": dest.name,
            "size_mb": manifest["archive_size_mb"],
            "files_included": manifest["files_included"],
            "files_excluded": manifest["files_excluded"],
            "excluded": manifest.get("excluded", []),
            "old_backups_deleted": deleted,
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    finally:
        dest.unlink(missing_ok=True)
        try:
            tmp_dir.rmdir()
        except Exception:
            pass


# ── Download local zip ────────────────────────────────────────────────────────

@router.get("/api/backup/download")
async def download_local_zip(background_tasks: BackgroundTasks) -> FileResponse:
    """Create a backup zip and stream it to the browser as a file download."""
    from docent.bundled_plugins.backup.manager import create_archive, archive_name

    tmp_dir = Path(tempfile.mkdtemp())
    dest = tmp_dir / archive_name()

    await asyncio.to_thread(create_archive, dest)

    def _cleanup() -> None:
        dest.unlink(missing_ok=True)
        try:
            tmp_dir.rmdir()
        except Exception:
            pass

    background_tasks.add_task(_cleanup)
    return FileResponse(
        path=str(dest),
        media_type="application/zip",
        filename=dest.name,
    )


# ── Restore ───────────────────────────────────────────────────────────────────

class RestoreBody(BaseModel):
    backup_id: str


@router.post("/api/backup/restore")
async def restore_from_drive(body: RestoreBody) -> JSONResponse:
    """Download a Drive backup by ID and restore it."""
    from docent.bundled_plugins.backup.drive_client import (
        get_service, get_or_create_backup_folder, list_backups, download_backup,
    )
    from docent.bundled_plugins.backup.manager import restore_archive

    tmp_dir = Path(tempfile.mkdtemp())
    dest = tmp_dir / f"{body.backup_id}.zip"

    try:
        service = await asyncio.to_thread(get_service)
        folder_id = await asyncio.to_thread(get_or_create_backup_folder, service)

        # Resolve the filename from the backup list
        backups = await asyncio.to_thread(list_backups, service, folder_id)
        chosen = next((b for b in backups if b["id"] == body.backup_id), None)
        if not chosen:
            return JSONResponse({"ok": False, "error": "Backup not found"}, status_code=404)

        dest = tmp_dir / chosen["name"]
        await asyncio.to_thread(download_backup, service, body.backup_id, dest)
        manifest = await asyncio.to_thread(restore_archive, dest)

        return JSONResponse({
            "ok": True,
            "restored_from": chosen["name"],
            "timestamp": manifest.get("timestamp", ""),
            "files_included": manifest.get("files_included", "?"),
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    finally:
        dest.unlink(missing_ok=True)
        try:
            tmp_dir.rmdir()
        except Exception:
            pass

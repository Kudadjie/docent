"""Google Drive API client for Docent backup/restore.

Requires the optional [backup] extras:
    pip install 'docent-cli[backup]'
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_NAME = "Docent Backups"
MIME_FOLDER = "application/vnd.google-apps.folder"


# ── Paths ────────────────────────────────────────────────────────────────────

def _creds_path() -> Path:
    from docent.utils.paths import root_dir
    return root_dir() / "drive_credentials.json"


def _token_path() -> Path:
    from docent.utils.paths import root_dir
    return root_dir() / "drive_token.json"


def credentials_file_exists() -> bool:
    return _creds_path().exists()


# ── Auth ─────────────────────────────────────────────────────────────────────

def _check_imports() -> None:
    try:
        import google.oauth2.credentials  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "Google Drive backup requires optional dependencies.\n"
            "Install them with:  pip install 'docent-cli[backup]'"
        )


def get_credentials():
    """Return valid OAuth2 credentials, running the browser flow if needed."""
    _check_imports()
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds_path = _creds_path()
    token_path = _token_path()

    if not creds_path.exists():
        raise FileNotFoundError(
            f"Drive credentials not found at {creds_path}\n"
            "Run 'docent backup setup' for setup instructions."
        )

    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def get_service():
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=get_credentials(), cache_discovery=False)


# ── Folder ───────────────────────────────────────────────────────────────────

def get_or_create_backup_folder(service: Any) -> str:
    """Return the ID of the 'Docent Backups' Drive folder, creating it if absent."""
    results = service.files().list(
        q=f"name='{FOLDER_NAME}' and mimeType='{MIME_FOLDER}' and trashed=false",
        fields="files(id)",
        spaces="drive",
    ).execute()
    items = results.get("files", [])
    if items:
        return items[0]["id"]
    folder = service.files().create(
        body={"name": FOLDER_NAME, "mimeType": MIME_FOLDER},
        fields="id",
    ).execute()
    return folder["id"]


# ── Upload / Download / List ──────────────────────────────────────────────────

def upload_backup(service: Any, local_path: Path, folder_id: str, filename: str) -> str:
    """Upload *local_path* to the backup folder. Returns the Drive file ID."""
    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(str(local_path), mimetype="application/zip", resumable=True)
    result = service.files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=media,
        fields="id",
    ).execute()
    return result["id"]


def list_backups(service: Any, folder_id: str) -> list[dict[str, Any]]:
    """Return backup file metadata sorted newest-first."""
    results = service.files().list(
        q=f"'{folder_id}' in parents and name contains 'docent_backup' and trashed=false",
        fields="files(id, name, size, createdTime)",
        orderBy="createdTime desc",
        spaces="drive",
    ).execute()
    return results.get("files", [])


def download_backup(service: Any, file_id: str, dest: Path) -> None:
    """Stream a Drive file to *dest*."""
    import io
    from googleapiclient.http import MediaIoBaseDownload
    request = service.files().get_media(fileId=file_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        dl = MediaIoBaseDownload(fh, request, chunksize=4 * 1024 * 1024)
        done = False
        while not done:
            _, done = dl.next_chunk()


def delete_backup(service: Any, file_id: str) -> None:
    service.files().delete(fileId=file_id).execute()


def trim_old_backups(service: Any, folder_id: str, keep: int = 10) -> int:
    """Delete backups beyond the newest *keep* files. Returns number deleted."""
    all_backups = list_backups(service, folder_id)
    to_delete = all_backups[keep:]
    for b in to_delete:
        delete_backup(service, b["id"])
    return len(to_delete)

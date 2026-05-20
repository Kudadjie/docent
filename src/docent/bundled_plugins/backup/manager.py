"""Backup archive creation and restoration logic."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 100 * 1_024 * 1_024   # 100 MB per-file exclusion threshold
ARCHIVE_PREFIX = "docent_backup_"

# Files/directories always excluded from the archive.
_EXCLUDE_NAMES: frozenset[str] = frozenset({
    "drive_token.json",     # OAuth token — sensitive and regenerable
})
_EXCLUDE_SUFFIXES: frozenset[str] = frozenset({".lock", ".tmp", ".pyc"})
_EXCLUDE_DIRS: frozenset[str] = frozenset({
    "__pycache__", ".git", "ui_dist", "node_modules", ".venv", "venv",
})


def archive_name() -> str:
    """Return a timestamped zip filename safe for all OSes."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return f"{ARCHIVE_PREFIX}{ts}.zip"


def _docent_home() -> Path:
    from docent.utils.paths import root_dir
    return root_dir()


def _research_output_dir() -> Path | None:
    try:
        from docent.config import load_settings
        p = load_settings().research.output_dir.expanduser()
        return p if p.is_dir() else None
    except Exception:
        return None


def _excluded(path: Path) -> bool:
    for part in path.parts:
        if part in _EXCLUDE_DIRS:
            return True
    return path.name in _EXCLUDE_NAMES or path.suffix in _EXCLUDE_SUFFIXES


# ── Create ───────────────────────────────────────────────────────────────────

def create_archive(dest: Path) -> dict[str, Any]:
    """Write a backup zip to *dest*. Returns the manifest dict."""
    from docent._version import __version__

    home = _docent_home()
    research_dir = _research_output_dir()

    included: list[str] = []
    excluded_files: list[dict[str, Any]] = []

    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:

        # ── Docent home ──────────────────────────────────────────────────────
        for path in sorted(home.rglob("*")):
            if path.is_dir() or _excluded(path):
                continue
            size = path.stat().st_size
            rel = str(path.relative_to(home))
            if size > MAX_FILE_BYTES:
                excluded_files.append({
                    "path": rel, "size_mb": round(size / 1_048_576, 1), "reason": "size_limit",
                })
                continue
            zf.write(path, arcname=f"home/{rel}")
            included.append(rel)

        # ── Research output dir (if separate from home) ──────────────────────
        if research_dir and not _is_relative_to(research_dir, home):
            for path in sorted(research_dir.rglob("*")):
                if path.is_dir() or _excluded(path):
                    continue
                size = path.stat().st_size
                rel = str(path.relative_to(research_dir))
                if size > MAX_FILE_BYTES:
                    excluded_files.append({
                        "path": f"research/{rel}",
                        "size_mb": round(size / 1_048_576, 1),
                        "reason": "size_limit",
                    })
                    continue
                zf.write(path, arcname=f"research/{rel}")
                included.append(f"research/{rel}")

        # ── Manifest ─────────────────────────────────────────────────────────
        manifest: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "docent_version": __version__,
            "docent_home": str(home),
            "research_dir": str(research_dir) if research_dir else None,
            "files_included": len(included),
            "files_excluded": len(excluded_files),
            "excluded": excluded_files,
            "archive_size_mb": 0,  # filled below
        }
        zf.writestr("backup_manifest.json", json.dumps(manifest, indent=2))

    manifest["archive_size_mb"] = round(dest.stat().st_size / 1_048_576, 2)
    return manifest


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


# ── Restore ──────────────────────────────────────────────────────────────────

def restore_archive(archive: Path, dest_home: Path | None = None) -> dict[str, Any]:
    """Extract *archive*, restoring docent state. Returns the manifest."""
    home = dest_home or _docent_home()
    research_dir = _research_output_dir()
    manifest: dict[str, Any] = {}

    with zipfile.ZipFile(archive, "r") as zf:
        names = zf.namelist()

        if "backup_manifest.json" in names:
            manifest = json.loads(zf.read("backup_manifest.json").decode())

        for name in names:
            if name == "backup_manifest.json":
                continue

            data = zf.read(name)

            if name.startswith("home/"):
                rel = name[len("home/"):]
                target = home / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)

            elif name.startswith("research/") and research_dir:
                rel = name[len("research/"):]
                target = research_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)

    return manifest


# ── Read manifest from archive ────────────────────────────────────────────────

def read_manifest(archive: Path) -> dict[str, Any]:
    with zipfile.ZipFile(archive, "r") as zf:
        if "backup_manifest.json" in zf.namelist():
            return json.loads(zf.read("backup_manifest.json").decode())
    return {}

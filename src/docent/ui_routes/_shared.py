"""Shared helpers for the web UI route modules.

Everything here used to live in ``docent.ui_server``; route modules imported it
back via lazy function-level imports, inverting the dependency. Now the routes
import directly from this module and ``ui_server`` only assembles the app.
``ui_server`` re-exports the public-ish names so existing imports and tests
keep working.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time as _time
import tomllib
from pathlib import Path
from typing import Any

from docent.utils.paths import root_dir

_log = logging.getLogger("docent.ui")
_audit_logger = logging.getLogger("docent.ui.audit")


# ── Paths ─────────────────────────────────────────────────────────────────────


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


# ── Origin policy ─────────────────────────────────────────────────────────────

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
    except Exception as exc:
        _log.debug("_read_json(%s) failed, using default: %s", path, exc)
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
    except Exception as exc:
        _log.debug("config.toml parse failed, using last cached config: %s", exc)
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


def _scan_database(db_dir: Path) -> dict[str, Any] | None:
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


def _get_database_count(db_dir: Path) -> int | None:
    entry = _scan_database(db_dir)
    return entry["count"] if entry is not None else None


def _get_database_files(db_dir: Path) -> list[str]:
    entry = _scan_database(db_dir)
    return entry["files"] if entry is not None else []


# ── Misc ──────────────────────────────────────────────────────────────────────


def _mask_key(key: str | None) -> str | None:
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
        exe,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        raise
    return stdout_b.decode(), stderr_b.decode(), proc.returncode or 0


async def _run(args: list[str], timeout: float = 30.0) -> tuple[str, str, int]:
    return await _run_command("docent", args, timeout=timeout)


def _version_at_least(installed: str, latest: str) -> bool:
    from packaging.version import InvalidVersion, Version

    try:
        return Version(installed.removeprefix("v")) >= Version(latest.removeprefix("v"))
    except InvalidVersion:
        return installed == latest

"""Generic external tool update checker with daily cache."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UpdateInfo:
    tool: str
    current: str | None
    latest: str
    upgrade_cmd: str


def check_npm(
    package: str,
    *,
    current_version: str | None = None,
    upgrade_cmd: str | None = None,
    cache_dir: Path | None = None,
) -> UpdateInfo | None:
    """Check npm registry for a newer version of `package`.

    Returns an UpdateInfo if a newer version is available, None otherwise.
    Silently returns None on any network or parse failure.
    Results cached for 24 hours.

    Args:
        package: npm package name (e.g. "feynman" or "@scope/pkg").
        current_version: installed version string, or None to skip comparison
                         (always reports latest if available).
        upgrade_cmd: command to show in the notification. Defaults to
                     "npm install -g {package}".
        cache_dir: override for the cache directory (used in tests).
    """
    import datetime

    cmd = upgrade_cmd or f"npm install -g {package}"
    cache_path = _cache_path(package, cache_dir)

    cached = _load_cache(cache_path)
    if cached:
        latest = cached.get("latest")
        if latest:
            if _is_newer(current_version, latest):
                return UpdateInfo(tool=package, current=current_version, latest=latest, upgrade_cmd=cmd)
            return None

    latest = _fetch_npm_latest(package)
    if latest:
        _save_cache(cache_path, {"latest": latest, "fetched": datetime.date.today().isoformat()})
        if _is_newer(current_version, latest):
            return UpdateInfo(tool=package, current=current_version, latest=latest, upgrade_cmd=cmd)
    return None


def check_github_release(
    repo: str,
    *,
    current_version: str | None = None,
    upgrade_cmd: str | None = None,
    cache_dir: Path | None = None,
) -> UpdateInfo | None:
    """Check GitHub releases API for a newer version of `owner/repo`.

    Returns UpdateInfo if newer, None otherwise. Silent on failure.
    Results cached for 24 hours.

    Args:
        repo: "owner/repo" string, e.g. "Kudadjie/docent".
        current_version: installed version (without leading 'v'), or None.
        upgrade_cmd: command to show the user. Required if repo is not self-explanatory.
        cache_dir: override for cache directory (tests).
    """
    cmd = upgrade_cmd or f"See https://github.com/{repo}/releases"
    cache_path = _cache_path(repo.replace("/", "__"), cache_dir)

    cached = _load_cache(cache_path)
    if cached:
        latest = cached.get("latest")
        if latest:
            if _is_newer(current_version, latest):
                return UpdateInfo(tool=repo.split("/")[-1], current=current_version, latest=latest, upgrade_cmd=cmd)
            return None

    latest = _fetch_github_latest(repo)
    if latest:
        import datetime
        _save_cache(cache_path, {"latest": latest, "fetched": datetime.date.today().isoformat()})
        if _is_newer(current_version, latest):
            return UpdateInfo(tool=repo.split("/")[-1], current=current_version, latest=latest, upgrade_cmd=cmd)
    return None


def _default_cache_dir() -> Path:
    from docent.utils.paths import cache_dir
    return cache_dir() / "updates"


def _cache_path(key: str, override: Path | None) -> Path:
    base = override if override is not None else _default_cache_dir()
    safe = key.replace("/", "__").replace("@", "at").replace(" ", "_")
    return base / f"{safe}.json"


def _load_cache(path: Path) -> dict | None:
    """Return cached data if it exists and is from today, else None."""
    import datetime
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("fetched") == datetime.date.today().isoformat():
            return data
    except Exception:
        pass
    return None


def _save_cache(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def _fetch_npm_latest(package: str) -> str | None:
    """Query npm registry for latest version. Returns version string or None."""
    try:
        import httpx
        encoded = package.replace("@", "%40").replace("/", "%2F")
        resp = httpx.get(
            f"https://registry.npmjs.org/{encoded}/latest",
            timeout=5,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json().get("version")
    except Exception:
        return None


def _fetch_github_latest(repo: str) -> str | None:
    """Query GitHub releases API for latest tag. Returns version string (without 'v') or None."""
    try:
        import httpx
        resp = httpx.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            timeout=5,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        tag = resp.json().get("tag_name", "")
        return tag.lstrip("v") if tag else None
    except Exception:
        return None


def _is_newer(current: str | None, latest: str) -> bool:
    """True if `latest` is strictly newer than `current` using simple tuple comparison.

    Falls back to string inequality if version parsing fails.
    Always returns True when current is None (version unknown — report update anyway).
    """
    if current is None:
        return True
    try:
        def _parse(v: str) -> tuple:
            return tuple(int(x) for x in v.lstrip("v").split(".")[:3])
        return _parse(latest) > _parse(current)
    except Exception:
        return latest != current
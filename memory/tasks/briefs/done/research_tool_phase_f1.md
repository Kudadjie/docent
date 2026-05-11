# Brief: Phase F1 — External tool update notification system

## Goal

Build a generic update checker utility and wire it into the research plugin's `on_startup` hook so users see a one-line notice when Feynman has a newer version available.

**Files to create:**
- `src/docent/utils/update_check.py` — generic npm + GitHub release checkers

**Files to modify:**
- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — add `on_startup` hook

**Tests:**
- `tests/test_update_check.py` — unit tests for the utility

Do NOT modify any other file.

---

## Read first

- `src/docent/bundled_plugins/reading/__init__.py` — see `on_startup(context)` at the bottom; mirror this pattern exactly
- `src/docent/utils/` — check what utilities exist (`paths.py`, `prompt.py`) to understand conventions

---

## File 1: `src/docent/utils/update_check.py`

```python
"""Generic external tool update checker with daily cache."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UpdateInfo:
    tool: str
    current: str | None    # None if current version could not be determined
    latest: str
    upgrade_cmd: str       # human-readable command to upgrade, e.g. "npm install -g feynman"


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

    # Load from cache if fresh (< 24h)
    cached = _load_cache(cache_path)
    if cached:
        latest = cached.get("latest")
        if latest:
            if _is_newer(current_version, latest):
                return UpdateInfo(tool=package, current=current_version, latest=latest, upgrade_cmd=cmd)
            return None

    # Fetch from npm registry
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


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _default_cache_dir() -> Path:
    from docent.utils.paths import cache_dir
    return cache_dir() / "updates"


def _cache_path(key: str, override: Path | None) -> Path:
    base = override if override is not None else _default_cache_dir()
    # Sanitise key for use as filename
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
        # URL-encode scoped packages: @scope/pkg -> %40scope%2Fpkg
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
```

---

## File 2: Add `on_startup` to the research plugin

At the bottom of `src/docent/bundled_plugins/research_to_notebook/__init__.py`, add:

```python
def on_startup(context) -> None:  # noqa: ARG001
    """Check for Feynman updates once per day and notify the user."""
    from docent.utils.update_check import check_npm
    from docent.ui import get_console

    info = check_npm(
        "feynman",
        upgrade_cmd="npm install -g feynman",
    )
    if info:
        get_console().print(
            f"[yellow]UPDATE AVAILABLE:[/] feynman {info.latest} is available "
            f"(run: {info.upgrade_cmd})"
        )
```

**Important:** `current_version` is NOT passed to `check_npm` for Feynman because Feynman has no reliable `--version` flag accessible without a full startup (the setup error we saw). So we pass `current_version=None` (implicit) which means: report whenever a new version is on npm, regardless of what's installed. This is slightly noisy (reports once per day even if already up to date) but safe. Passing `current_version=None` is the correct default per `check_npm`'s contract.

---

## Tests: `tests/test_update_check.py`

```python
"""Tests for the update check utility."""
from __future__ import annotations

import json
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from docent.utils.update_check import (
    UpdateInfo,
    _is_newer,
    _load_cache,
    _save_cache,
    check_npm,
    check_github_release,
)
```

**10 tests:**

1. `test_is_newer_detects_patch` — `_is_newer("1.0.0", "1.0.1")` → True
2. `test_is_newer_same_version` — `_is_newer("1.2.3", "1.2.3")` → False
3. `test_is_newer_none_current` — `_is_newer(None, "1.0.0")` → True (always report)
4. `test_is_newer_older_latest` — `_is_newer("2.0.0", "1.9.9")` → False
5. `test_load_cache_miss_on_stale_date` — write cache with yesterday's date → `_load_cache` returns None
6. `test_load_cache_hit_today` — write cache with today's date → returns the data dict
7. `test_check_npm_returns_update_when_newer` — mock `_fetch_npm_latest` returning "9.9.9", current="1.0.0" → UpdateInfo returned
8. `test_check_npm_returns_none_when_current` — mock returning "1.0.0", current="1.0.0" → None
9. `test_check_npm_uses_cache` — write cache with today's date + latest="2.0.0" → `_fetch_npm_latest` NOT called (verify with patch)
10. `test_check_npm_silent_on_network_failure` — mock `_fetch_npm_latest` returning None → returns None, no exception

For test isolation, pass `cache_dir=tmp_path` to `check_npm` and `check_github_release`.

**Mock `_fetch_npm_latest` via:**
```python
with patch("docent.utils.update_check._fetch_npm_latest", return_value="9.9.9"):
    result = check_npm("feynman", current_version="1.0.0", cache_dir=tmp_path)
```

---

## Invariants

1. ALL network calls must be wrapped in `try/except Exception` — NEVER raise to caller.
2. Cache writes that fail must be silently swallowed.
3. `on_startup` must be a module-level function (not a method), matching the reading plugin pattern exactly.
4. `on_startup` takes a single `context` argument even if unused (the loader calls it with the context).
5. `check_npm` and `check_github_release` are the only public functions (underscore-prefix the rest).
6. Run `python -m pytest tests/test_update_check.py --tb=short -v` until all 10 pass.
7. Run `python -m pytest --tb=no -q` — full suite must stay green. Report count.

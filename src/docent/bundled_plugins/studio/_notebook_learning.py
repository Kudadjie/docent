"""Self-learning source-compatibility layer for the to-notebook pipeline.

Tracks which source domains NotebookLM accepts/rejects across runs and filters
future source lists accordingly. Split out of _notebook.py (re-exported there).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode, urlparse

if TYPE_CHECKING:
    pass

from docent.utils.paths import data_dir as _docent_data_dir

_LEARN_DIR = _docent_data_dir() / "notebook-learning"
_SKILL_COMPAT_PATH = _LEARN_DIR / "source-compat.json"
_SKILL_RUN_LOG_PATH = _LEARN_DIR / "run-log.jsonl"
_SKILL_OVERRIDES_PATH = _LEARN_DIR / "active-overrides.json"
# Bundled defaults shipped with the package — read-only, user data is merged on top
_BUNDLED_COMPAT_PATH = Path(__file__).parent / "data" / "source-compat-defaults.json"

_NOTEBOOK_MAP_FILENAME = ".notebook-map.json"

# ---------------------------------------------------------------------------
# URL utilities
# ---------------------------------------------------------------------------


def _strip_utm(url: str) -> str:
    """Strip utm_* tracking parameters from a URL."""
    try:
        p = urlparse(url)
        qs = [(k, v) for k, v in parse_qsl(p.query) if not k.startswith("utm_")]
        return p._replace(query=urlencode(qs)).geturl()
    except Exception:
        return url


def _load_merged_compat() -> dict:
    """Merge bundled defaults with user-learned data. User data wins on conflicts."""

    def _read(p: Path) -> dict:
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except (json.JSONDecodeError, OSError):
            return {}

    bundled = _read(_BUNDLED_COMPAT_PATH)
    user = _read(_SKILL_COMPAT_PATH)

    domains: dict = {**bundled.get("domains", {}), **user.get("domains", {})}
    always_skip: set = set(bundled.get("always_skip", [])) | set(user.get("always_skip", []))
    return {"always_skip": list(always_skip), "domains": domains}


def _nlm_compat_filter(urls: list[str]) -> list[str]:
    """Filter URLs from known-bad domains using bundled + user-learned compat data."""
    compat = _load_merged_compat()
    always_skip = set(compat.get("always_skip", []))
    domains_data = compat.get("domains", {})
    result = []
    for url in urls:
        try:
            domain = urlparse(url).netloc.lower().removeprefix("www.")
        except Exception:
            result.append(url)
            continue
        if domain in always_skip:
            continue
        rate = domains_data.get(domain, {}).get("rate", -1)
        if rate != -1 and rate < 0.3:
            continue
        result.append(url)
    return result


def _update_compat(outcomes: list[tuple[str, bool]]) -> None:
    """Update source-compat.json with per-domain success/fail outcomes from this run."""
    if not outcomes:
        return
    try:
        _LEARN_DIR.mkdir(parents=True, exist_ok=True)
        compat = (
            json.loads(_SKILL_COMPAT_PATH.read_text(encoding="utf-8"))
            if _SKILL_COMPAT_PATH.exists()
            else {}
        )
    except (json.JSONDecodeError, OSError):
        compat = {}
    domains_data = compat.setdefault("domains", {})
    for domain, success in outcomes:
        if not domain:
            continue
        entry = domains_data.setdefault(domain, {"success": 0, "fail": 0, "rate": -1, "notes": ""})
        if success:
            entry["success"] += 1
        else:
            entry["fail"] += 1
        total = entry["success"] + entry["fail"]
        entry["rate"] = round(entry["success"] / total, 2) if total else -1
    import datetime

    compat["last_updated"] = datetime.date.today().isoformat()
    try:
        _SKILL_COMPAT_PATH.write_text(
            json.dumps(compat, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def _append_run_log(entry: dict[str, Any]) -> None:
    """Append one run entry to run-log.jsonl. Silent on failure."""
    try:
        _LEARN_DIR.mkdir(parents=True, exist_ok=True)
        with _SKILL_RUN_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _read_overrides() -> dict[str, Any]:
    """Read active-overrides.json. Returns defaults if missing or unreadable."""
    defaults: dict[str, Any] = {
        "wait_stable_max": 90,
        "feynman_skip": False,
        "youtube_min_views_low": False,
        "youtube_skip_followup": False,
        "skip_gap_analysis": False,
    }
    if not _SKILL_OVERRIDES_PATH.exists():
        return defaults
    try:
        data = json.loads(_SKILL_OVERRIDES_PATH.read_text(encoding="utf-8"))
        return {**defaults, **data}
    except (json.JSONDecodeError, OSError):
        return defaults


def _domain_from_url(url: str) -> str:
    """Extract bare domain (no www.) from a URL."""
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _nlm_deduplicate(urls: list[str], notebook_id: str) -> list[str]:
    """Remove URLs already present in the notebook."""
    # Lazy import at call time: resolves through the _notebook facade so test
    # monkeypatches on _notebook._nlm_source_list keep working, and avoids a
    # circular import (_notebook imports this module at load).
    from docent.bundled_plugins.studio import _notebook as _nb

    existing = _nb._nlm_source_list(notebook_id)
    existing_urls = {(s.get("url") or "").rstrip("/").lower() for s in existing if s.get("url")}
    return [u for u in urls if u.rstrip("/").lower() not in existing_urls]

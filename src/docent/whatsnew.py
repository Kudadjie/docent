"""What's New — parse CHANGELOG.md and decide when to surface release highlights.

Single source of truth is the repo-root ``CHANGELOG.md`` (Keep a Changelog
format), bundled into the wheel at ``docent/CHANGELOG.md`` so the installed CLI
and UI can read the current version's highlights at runtime — no network.

Surfaces that consume this module:
- CLI: ``docent`` shows a post-update banner for a few runs (``pop_banner_release``)
  and ``docent whatsnew`` prints the full current entry (``get_release``).
- UI: ``/api/whatsnew`` returns the current entry + whether it's unseen
  (``ui_payload`` / ``mark_ui_seen``).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from docent import __version__
from docent.utils.paths import data_dir

# How many CLI invocations show the banner after a version change, then it goes
# quiet until the NEXT version bump.
MAX_BANNER_SHOWS = 3

_CLI_STATE_FILE = "whatsnew.json"
_UI_STATE_FILE = "whatsnew_ui.json"

_VER_RE = re.compile(r"^##\s*\[([^\]]+)\]\s*(?:-\s*(.+?))?\s*$")


@dataclass
class Release:
    version: str
    date: str | None = None
    highlights: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"version": self.version, "date": self.date, "highlights": self.highlights}


def changelog_path() -> Path | None:
    """Locate CHANGELOG.md: bundled-in-wheel first, then repo root (editable/dev)."""
    bundled = Path(__file__).parent / "CHANGELOG.md"
    if bundled.is_file():
        return bundled
    repo_root = Path(__file__).resolve().parents[2] / "CHANGELOG.md"
    if repo_root.is_file():
        return repo_root
    return None


def parse_changelog(text: str) -> list[Release]:
    """Parse ``## [version] - date`` blocks; collect bullets under ``### What's New``.

    If a version block has no ``### What's New`` subsection, all of its top-level
    bullets are used as highlights instead.

    Multi-line bullets (continuation lines indented with whitespace) are joined
    into a single string so the full text is preserved.
    """
    releases: list[Release] = []
    cur: Release | None = None
    in_whatsnew = False
    saw_whatsnew_section = False
    fallback_bullets: list[str] = []
    # Track which list we are appending to so continuations go to the right place.
    _active_list: list[str] | None = None

    def _finalize(rel: Release | None, fallback: list[str], saw_section: bool) -> None:
        if rel is None:
            return
        if not saw_section and not rel.highlights:
            rel.highlights = fallback
        releases.append(rel)

    for line in text.splitlines():
        stripped = line.strip()
        m = _VER_RE.match(stripped)
        if m:
            _finalize(cur, fallback_bullets, saw_whatsnew_section)
            cur = Release(version=m.group(1).strip(), date=(m.group(2) or "").strip() or None)
            in_whatsnew = False
            saw_whatsnew_section = False
            fallback_bullets = []
            _active_list = None
            continue
        if cur is None:
            continue
        if stripped.startswith("### "):
            heading = stripped[4:].lower()
            in_whatsnew = "new" in heading
            if in_whatsnew:
                saw_whatsnew_section = True
            _active_list = None
            continue
        if stripped.startswith(("- ", "* ")):
            item = stripped[2:].strip()
            _active_list = cur.highlights if in_whatsnew else fallback_bullets
            _active_list.append(item)
            continue
        # Continuation line: non-empty, not a new bullet/heading, starts with whitespace.
        if stripped and line[:1] in (" ", "\t") and _active_list:
            _active_list[-1] = _active_list[-1] + " " + stripped
            continue
        # Blank line or unrecognised structure resets continuation.
        if not stripped:
            _active_list = None

    _finalize(cur, fallback_bullets, saw_whatsnew_section)
    return releases


def _normalize(version: str) -> str:
    """Strip local/dev metadata: '1.2.0.dev3+gabc' -> '1.2.0'."""
    return version.split("+", 1)[0].split(".dev", 1)[0]


def get_latest_release() -> Release | None:
    """Return the most recent tagged release, ignoring [Unreleased]."""
    path = changelog_path()
    if path is None:
        return None
    try:
        releases = parse_changelog(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return next((r for r in releases if r.version != "Unreleased"), None)


def get_release(version: str | None = None, *, allow_unreleased: bool = True) -> Release | None:
    """Return the Release entry matching *version* (default: installed version).

    Tries the exact version, then the normalized base version. When
    ``allow_unreleased`` is True (the default — used by ``docent whatsnew`` and
    the UI in dev builds), falls back to an ``[Unreleased]`` entry. The CLI
    post-update banner passes ``allow_unreleased=False`` so it only fires for a
    version the changelog actually documents.
    """
    version = version or __version__
    path = changelog_path()
    if path is None:
        return None
    try:
        releases = parse_changelog(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    by_ver = {r.version: r for r in releases}
    if version in by_ver:
        return by_ver[version]
    base = _normalize(version)
    if base in by_ver:
        return by_ver[base]
    if allow_unreleased:
        return by_ver.get("Unreleased")
    return None


# ── CLI banner state machine ───────────────────────────────────────────────────


def _state_path(filename: str) -> Path:
    return data_dir() / filename


def _load_state(filename: str) -> dict | None:
    try:
        return json.loads(_state_path(filename).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _save_state(filename: str, payload: dict) -> None:
    path = _state_path(filename)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass  # whatsnew state is best-effort; never break a command over it


def pop_banner_release(version: str | None = None) -> Release | None:
    """Return the Release to show as a post-update CLI banner, or None.

    State machine (persisted in ``~/.docent/data/whatsnew.json``):
      - First run ever (no state): record current version as the baseline with
        the counter exhausted — no banner. "Triggered only on the next update."
      - Version changed since last recorded: show the banner (counter = 1).
      - Same version, counter < MAX_BANNER_SHOWS: show again, increment.
      - Otherwise: quiet.
    Mutates the saved state as a side effect.
    """
    version = version or __version__
    state = _load_state(_CLI_STATE_FILE)

    if state is None:
        _save_state(_CLI_STATE_FILE, {"version": version, "count": MAX_BANNER_SHOWS})
        return None

    if state.get("version") != version:
        rel = get_release(version, allow_unreleased=False)
        if rel is None:
            # No changelog entry for this version — establish baseline, stay quiet.
            _save_state(_CLI_STATE_FILE, {"version": version, "count": MAX_BANNER_SHOWS})
            return None
        _save_state(_CLI_STATE_FILE, {"version": version, "count": 1})
        return rel

    count = int(state.get("count", MAX_BANNER_SHOWS))
    if count < MAX_BANNER_SHOWS:
        _save_state(_CLI_STATE_FILE, {"version": version, "count": count + 1})
        return get_release(version, allow_unreleased=False)
    return None


# ── UI toast state ──────────────────────────────────────────────────────────────


def ui_payload(version: str | None = None) -> dict:
    """Return the What's New payload for the UI.

    ``new`` is True when the current version's entry has not yet been dismissed
    in the UI (i.e. first load after an update).  Dev builds (version contains
    ``.dev``) always return ``new=False`` so the toast doesn't fire on every
    reload; the release data is still populated (latest tagged release).
    """
    version = version or __version__
    rel = get_release(version)
    is_dev = ".dev" in version
    if (rel is None or not rel.highlights) and is_dev:
        rel = get_latest_release()
    seen = _load_state(_UI_STATE_FILE) or {}
    is_new = bool(rel) and seen.get("version") != version and not is_dev
    return {
        "version": version,
        "release": rel.as_dict() if rel else None,
        "new": is_new,
    }


def mark_ui_seen(version: str | None = None) -> None:
    """Record that the UI toast for *version* has been dismissed."""
    version = version or __version__
    _save_state(_UI_STATE_FILE, {"version": version})

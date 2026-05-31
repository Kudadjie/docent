"""Environment health-check functions for `docent doctor`.

All functions are pure (no Typer coupling) and return a 4-tuple:
    (label: str, status: str, version: str, detail: str)

Status is one of: "OK", "WARN", "FAIL", "SKIP"

This module is intentionally side-effect-free so it can be imported cheaply
and tested without the full CLI stack.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docent.config.settings import Settings

_STATUS_STYLE: dict[str, str] = {"OK": "green", "WARN": "yellow", "FAIL": "red", "SKIP": "dim"}


def _user_file() -> Path:
    """Return the path to the user profile JSON file."""
    from docent.utils.paths import root_dir

    return root_dir() / "user.json"


def _check_profile(user_file: Path | None = None) -> tuple[str, str, str, str]:
    try:
        resolved = user_file if user_file is not None else _user_file()
        data = json.loads(resolved.read_text(encoding="utf-8"))
        name = (data.get("name") or "").strip()
        if name and name != "You":
            return (
                "Profile",
                "OK",
                "-",
                f"{name} | {data.get('level', '?')} | {data.get('program', '?')}",
            )
    except Exception:
        pass
    return "Profile", "WARN", "-", "Not set up - run: docent setup"


def _check_cli_tool(
    label: str,
    version_cmd: list[str],
    install_hint: str,
    *,
    npm_package: str | None = None,
    github_repo: str | None = None,
    upgrade_cmd: str | None = None,
    timeout: int = 8,
) -> tuple[str, str, str, str]:
    """Run a version command and return a check result.

    Pass ``npm_package`` to check npm registry for updates, or ``github_repo``
    (``"owner/repo"``) to check GitHub releases.  ``upgrade_cmd`` overrides the
    default upgrade hint shown when an update is available.
    """
    import re
    import shutil
    import subprocess

    try:
        # Resolve the executable via shutil.which so that Windows .cmd/.bat
        # scripts (e.g. npm.cmd, node.cmd) are found and runnable without shell=True.
        exe = shutil.which(version_cmd[0])
        if exe is None:
            return label, "FAIL", "-", install_hint
        r = subprocess.run([exe] + version_cmd[1:], capture_output=True, text=True, timeout=timeout)
        raw_lines = (r.stdout.strip() or r.stderr.strip()).splitlines()
        version = raw_lines[0].strip() if raw_lines else "?"
        update_note = ""
        m = re.search(r"\d+\.\d+(?:\.\d+)?", version)
        bare = m.group() if m else None
        if github_repo:
            from docent.utils.update_check import check_github_release

            info = check_github_release(github_repo, current_version=bare, upgrade_cmd=upgrade_cmd)
            if info:
                update_note = f"update: {info.latest} - {info.upgrade_cmd}"
        elif npm_package:
            from docent.utils.update_check import check_npm

            info = check_npm(npm_package, current_version=bare, upgrade_cmd=upgrade_cmd)
            if info:
                update_note = f"update: {info.latest} - {info.upgrade_cmd}"
        return label, "OK", version, update_note
    except FileNotFoundError:
        return label, "FAIL", "-", install_hint
    except subprocess.TimeoutExpired:
        return label, "WARN", "?", "version check timed out"
    except Exception as e:
        return label, "WARN", "?", str(e)[:80]


def _dir_size_gb(path: Path) -> float | None:
    """Walk a directory tree, return total size in GB. Returns None if path missing or too large."""
    if not path.is_dir():
        return None
    try:
        total = 0
        count = 0
        for entry in path.rglob("*"):
            count += 1
            if count > 5000:
                return None
            if entry.is_file():
                total += entry.stat().st_size
        return total / (1024**3)
    except Exception:
        return None


def _check_feynman(settings: Settings) -> tuple[str, str, str, str]:
    import os
    import re

    from docent.bundled_plugins.studio import (
        FeynmanNotFoundError,
        _feynman_version_from_package_json,
        _find_feynman,
    )
    from docent.utils.update_check import check_github_release

    try:
        cmd = _find_feynman(settings.research.feynman_command)
    except FeynmanNotFoundError:
        return (
            "Feynman CLI",
            "WARN",
            "-",
            "Not installed (~2 GB needed) - npm install -g @companion-ai/feynman",
        )

    # Read version from package.json — avoids spawning a Node.js subprocess
    # which can hang on Windows when capture_output+timeout is used.
    version = _feynman_version_from_package_json(cmd)

    detail_parts: list[str] = []
    m = re.search(r"\d+\.\d+(?:\.\d+)?", version)
    bare = m.group() if m else None
    update_info = check_github_release(
        "companion-inc/feynman",
        current_version=bare,
        upgrade_cmd="npm install -g @companion-ai/feynman@latest",
    )
    if update_info:
        detail_parts.append(f"update: {update_info.latest}")

    candidates = [
        Path(cmd[0]).resolve().parent / "node_modules" / "feynman",
        Path(cmd[0]).resolve().parent.parent / "lib" / "node_modules" / "feynman",
    ]
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidates.append(Path(appdata) / "npm" / "node_modules" / "feynman")

    status = "OK"
    for candidate in candidates:
        if candidate.is_dir():
            gb = _dir_size_gb(candidate)
            if gb is not None:
                size_str = f"{gb:.1f} GB" if gb >= 0.1 else f"{gb * 1024:.0f} MB"
                detail_parts.append(f"{size_str} installed")
                if gb >= 2.0:
                    status = "WARN"
            break

    return "Feynman CLI", status, version, "  ".join(detail_parts) or "-"


def _check_mendeley_mcp(settings: Settings) -> tuple[str, str, str, str]:
    """Check Mendeley MCP prerequisites via PATH lookup — no subprocess spawn."""
    import shutil

    cmd = list(settings.reading.mendeley_mcp_command or ["uvx", "mendeley-mcp"])
    runner = cmd[0]
    if shutil.which(runner):
        return "Mendeley MCP", "OK", "-", f"{runner} found (test: {' '.join(cmd[:2])} --help)"
    return (
        "Mendeley MCP",
        "FAIL",
        "-",
        f"{runner} not found - install uv: https://docs.astral.sh/uv/",
    )


def _check_zotero(settings: Settings) -> tuple[str, str, str, str]:
    """Check the Zotero backend — pyzotero installed + credentials configured.

    Uses importlib.metadata (dist name lookup) rather than find_spec so the
    check is consistent with how the backup status route detects packages.
    """
    from importlib.metadata import Distribution
    from importlib.metadata import PackageNotFoundError as _PkgNF

    rs = settings.reading
    active = (rs.reference_manager or "mendeley").lower() == "zotero"
    try:
        Distribution.from_name("pyzotero")
        has_lib = True
    except _PkgNF:
        has_lib = False
    configured = bool(rs.zotero_api_key and rs.zotero_library_id)

    if not active:
        avail = "pyzotero available" if has_lib else "pyzotero not installed"
        return "Zotero", "SKIP", "-", f"not active (reading.reference_manager=mendeley); {avail}"
    if not has_lib:
        return (
            "Zotero",
            "FAIL",
            "-",
            ("pyzotero not found — run: uv sync  (or: pip install pyzotero)"),
        )
    if not configured:
        return (
            "Zotero",
            "WARN",
            "-",
            (
                "set reading.zotero_api_key + reading.zotero_library_id "
                "(get them at zotero.org/settings/keys)"
            ),
        )
    return (
        "Zotero",
        "OK",
        "-",
        f"configured ({rs.zotero_library_type} library {rs.zotero_library_id})",
    )


def _check_google_drive() -> tuple[str, str, str, str]:
    """Check Google Drive backup dependencies (importlib.metadata, no subprocess)."""
    from importlib.metadata import Distribution
    from importlib.metadata import PackageNotFoundError as _PkgNF

    missing = []
    for dist in ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]:
        try:
            Distribution.from_name(dist)
        except _PkgNF:
            missing.append(dist)
    if missing:
        return (
            "Google Drive deps",
            "WARN",
            "-",
            (
                "backup extra not installed — run: "
                "pip install 'docent-cli[backup]'  "
                "(or: uv tool install --with 'docent-cli[backup]' docent)"
            ),
        )
    return "Google Drive deps", "OK", "-", "backup libraries available"


def _check_tavily(settings: Settings) -> tuple[str, str, str, str]:
    key = settings.research.tavily_api_key
    if key:
        masked = (key[:4] + "..." + key[-4:]) if len(key) > 8 else "set"
        return (
            "Tavily key",
            "OK",
            "-",
            (
                f"configured ({masked}) — free tier: web search (1k/month). "
                "Paid plan adds Research API (deep AI synthesis with citations)."
            ),
        )
    return (
        "Tavily key",
        "WARN",
        "-",
        (
            "Not set — web search falls back to DuckDuckGo. "
            "Free key at app.tavily.com (no credit card). Run: docent setup"
        ),
    )


def _check_semantic_scholar(settings: Settings) -> tuple[str, str, str, str]:
    if settings.research.semantic_scholar_api_key:
        return "Semantic Scholar", "OK", "-", "API key set"
    return "Semantic Scholar", "SKIP", "-", "No key (optional - raises rate limits)"


def _check_alphaxiv(settings: Settings) -> tuple[str, str, str, str]:
    try:
        from alphaxiv import __version__ as ax_version
    except ImportError:
        return "alphaXiv", "FAIL", "-", "alphaxiv-py not installed (uv add alphaxiv-py)"
    from docent.utils.update_check import check_pypi

    update = check_pypi("alphaxiv-py", current_version=ax_version, upgrade_cmd="uv add alphaxiv-py")
    update_hint = (
        f"  (update available: {update.latest}  run: {update.upgrade_cmd})" if update else ""
    )
    key = settings.research.alphaxiv_api_key
    if key:
        masked = (key[:4] + "..." + key[-4:]) if len(key) > 8 else "set"
        return "alphaXiv", "OK", ax_version, f"API key configured ({masked}){update_hint}"
    return (
        "alphaXiv",
        "SKIP",
        ax_version,
        f"No key (optional - get free key at alphaxiv.org/settings){update_hint}",
    )


def _check_notebooklm_py() -> tuple[str, str, str, str]:
    import shutil
    import subprocess

    # 1. Python package
    try:
        import contextlib as _cl2
        import io as _io2
        import sys as _sys2

        if "notebooklm" not in _sys2.modules:
            import os as _os2

            _os2.environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1")
            with _cl2.redirect_stderr(_io2.StringIO()):
                import notebooklm as nlm_mod
        else:
            import notebooklm as nlm_mod
        nlm_version = getattr(nlm_mod, "__version__", None) or "-"
    except ImportError:
        return (
            "NotebookLM",
            "FAIL",
            "-",
            'not installed — run: pip install "notebooklm-py[browser]"  then: playwright install chromium && notebooklm login',
        )

    # 2. CLI binary on PATH
    exe = shutil.which("notebooklm")
    if not exe:
        return (
            "NotebookLM",
            "WARN",
            nlm_version,
            'CLI not on PATH — try reinstalling: pip install "notebooklm-py[browser]"',
        )

    # 3. Auth check (short timeout so doctor stays fast)
    try:
        result = subprocess.run(
            [exe, "list", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        import json as _json

        data = _json.loads(result.stdout or "{}")
        auth_ok = result.returncode == 0 and not data.get("error")
    except Exception:
        auth_ok = False

    if not auth_ok:
        return (
            "NotebookLM",
            "WARN",
            nlm_version,
            "Not authenticated — run: docent setup  (or: notebooklm login)",
        )

    from docent.utils.update_check import check_pypi

    update = check_pypi(
        "notebooklm-py",
        current_version=nlm_version if nlm_version != "-" else None,
        upgrade_cmd="uv add notebooklm-py",
    )
    update_hint = f"  (update: {update.latest}  run: {update.upgrade_cmd})" if update else ""
    return "NotebookLM", "OK", nlm_version, f"authenticated{update_hint}"


def _check_opencode(settings: Settings) -> tuple[str, str, str, str]:
    """Check OpenCode server availability (fast — no model call)."""
    from docent.utils.model_health import check_opencode_server

    return check_opencode_server(
        provider=settings.research.oc_provider,
        model=settings.research.oc_model_planner,
    )


def _check_litellm_provider(
    label: str, key: str | None, env_var: str, setup_cmd: str
) -> tuple[str, str, str, str]:
    """Generic check for a litellm provider API key."""
    import os

    resolved = key or os.environ.get(env_var, "")
    if not resolved:
        return label, "SKIP", "-", f"Not configured — set {env_var} or run: {setup_cmd}"
    masked = resolved[:6] + "…"
    return label, "OK", "-", f"Key present ({masked})"


def _check_reading_db(settings: Settings) -> tuple[str, str, str, str]:
    db = settings.reading.database_dir
    if db is None:
        return (
            "Reading DB",
            "WARN",
            "-",
            "Not configured - run: docent reading config-set --key database_dir --value <path>",
        )
    expanded = Path(str(db)).expanduser()
    if not expanded.exists():
        return "Reading DB", "WARN", "-", f"{expanded} does not exist"
    return "Reading DB", "OK", "-", str(expanded)

"""Doctor and tooling health-check endpoints."""
import asyncio
import os
import shutil
import subprocess as _sp
import sys
from typing import Optional

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


TOOLING = [
    {
        "name": "@companion-ai/feynman",
        "label": "Feynman",
        "upgrade_cmd": "npm install -g @companion-ai/feynman",
    },
]


def _run(args, timeout=30.0):
    from docent.ui_server import _run as _r
    return _r(args, timeout=timeout)


def _run_command(cmd, args, timeout=30.0):
    from docent.ui_server import _run_command as _rc
    return _rc(cmd, args, timeout=timeout)


def _version_at_least(installed, latest):
    from docent.ui_server import _version_at_least as _val
    return _val(installed, latest)


async def _fetch_npm_latest(package: str) -> Optional[str]:
    try:
        encoded = package.replace("@", "%40").replace("/", "%2F")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://registry.npmjs.org/{encoded}/latest",
                headers={"Accept": "application/json"},
            )
        response.raise_for_status()
        return response.json().get("version")
    except Exception:
        return None


async def _get_npm_installed(package: str) -> Optional[str]:
    try:
        stdout, _, rc = await _run_command(
            "npm",
            ["list", "-g", package, "--json", "--depth=0"],
            timeout=15.0,
        )
        if rc != 0 and not stdout:
            return None
        data = json.loads(stdout)
        return data.get("dependencies", {}).get(package, {}).get("version")
    except Exception:
        return None


def _mask_key(key):
    from docent.ui_server import _mask_key as _mk
    return _mk(key)


def _read_config_reading():
    from docent.ui_server import _read_config_reading as _rcr
    return _rcr()


def _read_config_research():
    from docent.ui_server import _read_config_research as _rcr2
    return _rcr2()


def _user_file():
    from docent.ui_server import _user_file as _uf
    return _uf()


def _read_json(path, default):
    from docent.ui_server import _read_json as _rj
    return _rj(path, default)


@router.get("/api/tooling")
async def get_tooling() -> JSONResponse:
    async def _tool_status(tool):
        installed, latest = await asyncio.gather(
            _get_npm_installed(tool["name"]),
            _fetch_npm_latest(tool["name"]),
        )
        up_to_date = (
            _version_at_least(installed, latest)
            if installed is not None and latest is not None
            else None
        )
        return {**tool, "installed": installed, "latest": latest, "up_to_date": up_to_date}

    results = await asyncio.gather(*(_tool_status(tool) for tool in TOOLING))
    return JSONResponse(list(results))


@router.get("/api/doctor")
async def get_doctor() -> JSONResponse:
    cfg_reading = _read_config_reading()
    cfg_research = _read_config_research()
    user_data = _read_json(_user_file(), {})

    def _row(label: str, status: str, version: str = "-", detail: str = "-") -> dict:
        return {"label": label, "status": status, "version": version, "detail": detail}

    name = (user_data.get("name") or "").strip()
    profile_row = (
        _row("Profile", "OK", detail=f"{name} · {user_data.get('level', '?')} · {user_data.get('program', '?')}")
        if name and name != "You"
        else _row("Profile", "WARN", detail="Not set — use 'Set up your profile' in the sidebar")
    )

    pv = sys.version_info
    python_row = _row("Python", "OK", f"{pv.major}.{pv.minor}.{pv.micro}")

    async def _docent_version_row() -> dict:
        try:
            stdout, _, rc = await _run(["--version"], timeout=8.0)
            version = stdout.strip().split()[-1] if rc == 0 else "?"
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    r = await client.get("https://pypi.org/pypi/docent-cli/json")
                    latest = r.json()["info"]["version"]
                if version == latest:
                    return _row("Docent", "OK", version, "up to date")
                return _row("Docent", "WARN", version, f"update available: {latest} — run: docent update")
            except Exception:
                return _row("Docent", "OK", version)
        except Exception as exc:
            return _row("Docent", "WARN", "?", str(exc)[:80])

    async def _cli_row(label: str, cmd: list[str], install_hint: str) -> dict:
        exe = await asyncio.to_thread(shutil.which, cmd[0])
        if exe is None:
            return _row(label, "FAIL", detail=install_hint)
        try:
            stdout, _, rc = await _run_command(exe, cmd[1:], timeout=8.0)
            version = (stdout.strip() or "?").splitlines()[0].strip()
            return _row(label, "OK", version)
        except asyncio.TimeoutError:
            return _row(label, "WARN", "?", "version check timed out")
        except Exception as exc:
            return _row(label, "WARN", "?", str(exc)[:80])

    async def _mendeley_row() -> dict:
        uvx = await asyncio.to_thread(shutil.which, "uvx")
        if uvx:
            return _row("Mendeley MCP", "OK", detail="uvx found")
        return _row("Mendeley MCP", "FAIL", detail="uvx not found — install uv: https://docs.astral.sh/uv/")

    def _zotero_row() -> dict:
        from importlib.metadata import Distribution, PackageNotFoundError as _PkgNF
        active = (cfg_reading.get("reference_manager") or "mendeley").lower() == "zotero"
        try:
            Distribution.from_name("pyzotero")
            has_lib = True
        except _PkgNF:
            has_lib = False
        configured = bool(cfg_reading.get("zotero_api_key") and cfg_reading.get("zotero_library_id"))

        if not active:
            avail = "pyzotero available" if has_lib else "pyzotero not installed"
            return _row("Zotero", "SKIP", detail=f"not active (reference_manager=mendeley); {avail}")
        if not has_lib:
            return _row("Zotero", "FAIL",
                        detail="pyzotero not found — run: uv sync  (or: pip install pyzotero)")
        if not configured:
            return _row("Zotero", "WARN",
                        detail="set zotero_api_key + zotero_library_id in Settings (zotero.org/settings/keys)")
        lib_type = cfg_reading.get("zotero_library_type") or "user"
        lib_id = cfg_reading.get("zotero_library_id")
        return _row("Zotero", "OK", detail=f"configured ({lib_type} library {lib_id})")

    async def _opencode_row() -> dict:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get("http://127.0.0.1:4096/global/health")
                if r.status_code == 200:
                    return _row("OpenCode", "OK", detail="server reachable at :4096")
        except Exception:
            pass
        oc_exe = shutil.which("opencode")
        if oc_exe is None:
            return _row(
                "OpenCode",
                "FAIL",
                detail="Not installed — npm install -g opencode-ai (requires Node.js)",
            )
        return _row(
            "OpenCode",
            "WARN",
            detail="Installed but not running — click 'Start server' in Settings, or run: opencode serve --port 4096",
        )

    async def _feynman_row() -> dict:
        from pathlib import Path as _P
        feynman_cmd: list[str] | None = None
        resolved = shutil.which("feynman")
        if resolved:
            feynman_cmd = [resolved]
        else:
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                win_path = _P(appdata) / "npm" / "feynman.cmd"
                if win_path.is_file():
                    feynman_cmd = [str(win_path)]

        if feynman_cmd is None:
            installed = await _get_npm_installed("@companion-ai/feynman")
            if installed is None:
                return _row("Feynman CLI", "WARN", detail="Not installed — npm install -g @companion-ai/feynman")
            feynman_cmd = ["feynman"]

        from docent.bundled_plugins.studio.feynman import _feynman_version_from_package_json
        version = _feynman_version_from_package_json(feynman_cmd)

        # package.json lookup can fail on non-standard npm layouts — cascade through
        # two fallbacks before giving up.
        if not version or version == "?":
            # Fallback 1: npm list -g (async, may fail on Windows if npm not on PATH)
            npm_ver = await _get_npm_installed("@companion-ai/feynman")
            if npm_ver:
                version = npm_ver

        if not version or version == "?":
            # Fallback 2: run `feynman --version` directly.
            # On Windows, .cmd wrappers require shell=True to execute.
            try:
                import subprocess as _sub
                _needs_shell = sys.platform == "win32"
                proc = await asyncio.to_thread(
                    lambda: _sub.run(
                        feynman_cmd + ["--version"],
                        capture_output=True, text=True, timeout=8,
                        shell=_needs_shell,
                    )
                )
                raw = (proc.stdout or proc.stderr or "").strip()
                if raw:
                    # Output is usually "2.5.1" or "v2.5.1"; take first line, strip "v"
                    version = raw.splitlines()[0].strip().lstrip("v")
            except Exception:
                pass

        latest = await _fetch_npm_latest("@companion-ai/feynman")
        clean_version = version if version and version not in ("?", "") else None
        if latest and clean_version and not _version_at_least(clean_version, latest):
            return _row("Feynman CLI", "WARN", clean_version,
                        f"update available: {latest} — npm install -g @companion-ai/feynman@latest")
        return _row("Feynman CLI", "OK", clean_version or "unknown")

    def _notebooklm_sync() -> dict:
        try:
            import contextlib
            import io as _io
            import sys as _sys
            if "notebooklm" not in _sys.modules:
                import os as _os
                _os.environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1")
                with contextlib.redirect_stderr(_io.StringIO()):
                    import notebooklm as _nlm
            else:
                import notebooklm as _nlm
            version = getattr(_nlm, "__version__", "-")
        except ImportError:
            return _row("NotebookLM", "FAIL", detail='not installed — pip install "notebooklm-py[browser]"')
        exe = shutil.which("notebooklm")
        if not exe:
            return _row("NotebookLM", "WARN", version, "CLI not on PATH")
        try:
            result = _sp.run([exe, "list", "--json"], capture_output=True, text=True, timeout=10)
            import json as _j
            data = _j.loads(result.stdout or "{}")
            if result.returncode == 0 and not data.get("error"):
                return _row("NotebookLM", "OK", version, "authenticated")
        except Exception:
            pass
        return _row("NotebookLM", "WARN", version, "Not authenticated — run: notebooklm login")

    def _alphaxiv_sync() -> dict:
        try:
            from alphaxiv import __version__ as ax_v
        except ImportError:
            return _row("alphaXiv", "FAIL", detail="alphaxiv-py not installed (uv add alphaxiv-py)")
        key = cfg_research.get("alphaxiv_api_key")
        if key:
            return _row("alphaXiv", "OK", ax_v, f"key configured ({_mask_key(key)})")
        return _row("alphaXiv", "SKIP", ax_v, "No key — get free key at alphaxiv.org/settings")

    def _drive_backup_row() -> dict:
        from docent.bundled_plugins.backup.drive_client import credentials_file_exists
        if credentials_file_exists():
            # Verify the optional deps are importable too
            try:
                import google.oauth2.credentials  # noqa: F401
                import google_auth_oauthlib  # noqa: F401
                import googleapiclient  # noqa: F401
                return _row("Drive Backup", "OK", detail="Credentials configured — run 'docent backup'")
            except ImportError:
                return _row("Drive Backup", "WARN",
                            detail="Credentials found but dependencies missing — run: pip install 'docent-cli[backup]'")
        return _row("Drive Backup", "SKIP", detail="Optional — run 'docent backup --setup' to configure")

    def _reading_db_row() -> dict:
        db = cfg_reading.get("database_dir")
        if db is None:
            return _row("Reading DB", "WARN", detail="Not configured — set database_dir in Settings")
        expanded = Path(str(db)).expanduser()
        if expanded.exists():
            return _row("Reading DB", "OK", detail=str(expanded))
        return _row("Reading DB", "WARN", detail=f"{expanded} does not exist")

    (
        docent_row,
        uv_row, node_row, npm_row,
        feynman_row, mendeley_row, opencode_row,
        nlm_row, ax_row,
    ) = await asyncio.gather(
        _docent_version_row(),
        _cli_row("uv", ["uv", "--version"], "Install uv: https://docs.astral.sh/uv/"),
        _cli_row("Node.js", ["node", "--version"], "Install Node.js: https://nodejs.org"),
        _cli_row("npm", ["npm", "--version"], "Install npm: https://nodejs.org"),
        _feynman_row(),
        _mendeley_row(),
        _opencode_row(),
        asyncio.to_thread(_notebooklm_sync),
        asyncio.to_thread(_alphaxiv_sync),
    )
    db_row, drive_row, zotero_row = await asyncio.gather(
        asyncio.to_thread(_reading_db_row),
        asyncio.to_thread(_drive_backup_row),
        asyncio.to_thread(_zotero_row),
    )

    checks = [
        profile_row,
        python_row,
        docent_row,
        uv_row,
        node_row,
        npm_row,
        feynman_row,
        mendeley_row,
        zotero_row,
        opencode_row,
        nlm_row,
        ax_row,
        db_row,
        drive_row,
    ]
    return JSONResponse(checks)


import json  # noqa: E402
from pathlib import Path  # noqa: E402
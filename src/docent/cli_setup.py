"""Interactive first-run setup flow for Docent.

Extracted from ``cli.py`` (which was a god module). Holds the profile / database
/ API-key / external-tool setup wizard and its helpers. ``cli.py`` imports
``_run_setup_flow`` and ``_run_setup_if_needed`` from here and exposes them via
the ``docent setup`` command and the first-run hook.

No dependency on ``cli.py`` — the import goes one direction only (cli → cli_setup).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from docent.config import load_settings, write_setting
from docent.ui import get_console


def _user_file() -> Path:
    from docent.utils.paths import root_dir

    return root_dir() / "user.json"


_LEVEL_CHOICES = ["Undergraduate", "Masters", "PhD", "Postdoc", "Faculty", "Other"]


def _is_setup_complete() -> bool:
    """Return True when the user profile has a non-empty name."""
    try:
        data = json.loads(_user_file().read_text(encoding="utf-8"))
        name = (data.get("name") or "").strip()
        return bool(name and name != "You")
    except Exception:
        return False


def _run_tool_install(console: Any, cmd: list[str]) -> bool:
    """Run an install command streaming output to the terminal. Returns True on success."""
    import shutil
    import subprocess

    # Resolve executable so Windows .cmd wrappers (npm.cmd) work without shell=True
    resolved = shutil.which(cmd[0]) or cmd[0]
    run_cmd = [resolved] + cmd[1:]

    console.print(f"  [dim]$ {' '.join(cmd)}[/]")
    try:
        result = subprocess.run(run_cmd, check=False)
        if result.returncode != 0:
            console.print(
                f"  [red]Command failed (exit {result.returncode}).[/] Try running it manually."
            )
            return False
        return True
    except FileNotFoundError:
        console.print(f"  [red]{cmd[0]!r} not found.[/] Make sure it is installed and on PATH.")
        return False
    except Exception as exc:
        console.print(f"  [red]Error:[/] {exc}")
        return False


def _test_semantic_scholar_key(key: str) -> bool:
    """Return True if the Semantic Scholar key is accepted (HTTP 200 or 429 on a test query).

    HTTP 403 means invalid key. Network failures are treated as inconclusive (True).
    """
    try:
        import httpx

        r = httpx.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": "test", "limit": 1, "fields": "title"},
            headers={"x-api-key": key},
            timeout=10,
        )
        return r.status_code != 403
    except Exception:
        return True  # network / timeout — inconclusive, don't block setup


def _test_tavily_key(key: str) -> bool:
    """Return True if the Tavily key is accepted by the search API.

    Makes one minimal search call. Network failures are treated as inconclusive
    (returns True) so a flaky connection doesn't block setup.
    """
    try:
        from tavily import TavilyClient
        from tavily.errors import InvalidAPIKeyError
    except ImportError:
        return True  # tavily not installed yet — skip

    try:
        TavilyClient(api_key=key).search("test", max_results=1)
        return True
    except InvalidAPIKeyError:
        return False
    except Exception:
        return True  # network / rate-limit — inconclusive, don't block setup


def _run_setup_flow(*, first_run: bool = False) -> None:
    """Full interactive Docent setup. Called on first run and by `docent setup`."""
    console = get_console()
    settings = load_settings()

    if first_run:
        console.print("\n[bold cyan]Welcome to Docent![/]  Let's get you set up.\n")
    else:
        console.print("\n[bold cyan]Docent Setup[/]")
        console.print("[dim]Press Enter to keep the current value. Ctrl+C to cancel.[/]\n")

    # ── Profile ──
    console.print("[bold]Profile[/]")
    existing: dict = {}
    try:
        existing = json.loads(_user_file().read_text(encoding="utf-8"))
    except Exception:
        pass

    name = typer.prompt("  Name", default=existing.get("name", "")).strip()
    program = typer.prompt(
        "  Program / field of study", default=existing.get("program", "")
    ).strip()

    console.print("  Academic level:")
    for i, choice in enumerate(_LEVEL_CHOICES, 1):
        console.print(f"    [dim]{i}.[/] {choice}")
    existing_level = existing.get("level", "")
    level: str = existing_level
    raw_level = typer.prompt(
        "  Enter number or name", default=existing_level, show_default=bool(existing_level)
    ).strip()
    if raw_level:
        if raw_level.isdigit() and 1 <= int(raw_level) <= len(_LEVEL_CHOICES):
            level = _LEVEL_CHOICES[int(raw_level) - 1]
        elif raw_level in _LEVEL_CHOICES:
            level = raw_level
        elif raw_level.title() in _LEVEL_CHOICES:
            level = raw_level.title()

    if name:
        from docent.utils.paths import root_dir

        root_dir().mkdir(parents=True, exist_ok=True)
        _user_file().write_text(
            json.dumps({"name": name, "program": program, "level": level}, indent=2),
            encoding="utf-8",
        )
        console.print("  [green]Profile saved.[/]\n")

    # ── Reading database ──
    console.print("[bold]Reading Database[/]")
    existing_db = str(settings.reading.database_dir or "")
    console.print("  [dim]Where do you keep your PDFs (Mendeley watch folder)?[/]")
    db_raw = typer.prompt(
        "  Papers folder", default=existing_db, show_default=bool(existing_db)
    ).strip()
    if db_raw and db_raw != existing_db:
        try:
            write_setting("reading.database_dir", db_raw)
            console.print("  [green]Database folder set.[/]\n")
        except Exception as e:
            console.print(f"  [yellow]Could not save: {e}[/]\n")
    else:
        console.print()

    # ── Research API keys ──
    console.print("[bold]Research Keys[/]")
    existing_tavily = settings.research.tavily_api_key or ""
    if existing_tavily:
        masked = (
            (existing_tavily[:4] + "..." + existing_tavily[-4:])
            if len(existing_tavily) > 8
            else "set"
        )
        console.print(f"  [dim]Tavily key: currently {masked}[/]")
    else:
        console.print(
            "  [dim]Tavily web search (free key: 1,000 calls/month → better web results than DuckDuckGo).[/]\n"
            "  [dim]Paid plan unlocks the Tavily Research API: deep AI synthesis with citations.[/]"
        )
    tavily_raw = typer.prompt(
        "  Tavily API key (Enter to skip)", default="", show_default=False
    ).strip()
    if tavily_raw:
        console.print("  [dim]Testing key...[/]", end="")
        key_ok = _test_tavily_key(tavily_raw)
        if key_ok:
            console.print(" [green]✓[/]")
            try:
                write_setting("research.tavily_api_key", tavily_raw)
                console.print("  [green]Tavily key saved.[/]")
            except Exception as e:
                console.print(f"  [yellow]Could not save: {e}[/]")
        else:
            console.print(" [red]✗ key rejected[/]")
            console.print(
                "  [red]This key was not accepted by Tavily. Check the key at app.tavily.com.[/]\n"
                "  [dim]Without a valid key, web search falls back to DuckDuckGo.[/]"
            )
            if typer.confirm("  Save anyway?", default=False):
                try:
                    write_setting("research.tavily_api_key", tavily_raw)
                    console.print("  [yellow]Key saved (unverified).[/]")
                except Exception as e:
                    console.print(f"  [yellow]Could not save: {e}[/]")

    existing_ss = settings.research.semantic_scholar_api_key or ""
    if existing_ss:
        console.print("  [dim]Semantic Scholar key: already set (optional — raises rate limits)[/]")
    else:
        console.print(
            "  [dim]Semantic Scholar key: optional — raises rate limits. Free at semanticscholar.org/product/api[/]"
        )
    ss_raw = typer.prompt(
        "  Semantic Scholar key (Enter to skip)", default="", show_default=False
    ).strip()
    if ss_raw and ss_raw != existing_ss:
        console.print("  [dim]Testing key...[/]", end="")
        ss_ok = _test_semantic_scholar_key(ss_raw)
        if ss_ok:
            console.print(" [green]✓[/]")
            try:
                write_setting("research.semantic_scholar_api_key", ss_raw)
                console.print("  [green]Semantic Scholar key saved.[/]")
            except Exception as e:
                console.print(f"  [yellow]Could not save: {e}[/]")
        else:
            console.print(" [red]✗ key rejected (HTTP 403)[/]")
            console.print(
                "  [red]This key was not accepted. Check the key at semanticscholar.org.[/]\n"
                "  [dim]Without a key, Semantic Scholar still works at lower rate limits.[/]"
            )
            if typer.confirm("  Save anyway?", default=False):
                try:
                    write_setting("research.semantic_scholar_api_key", ss_raw)
                    console.print("  [yellow]Key saved (unverified).[/]")
                except Exception as e:
                    console.print(f"  [yellow]Could not save: {e}[/]")
    console.print()

    # ── External tools ──
    import platform as _platform
    import shutil

    console.print("[bold]External Tools[/]")
    from docent.bundled_plugins.studio import FeynmanNotFoundError, _find_feynman

    # ── Node.js / npm (prerequisite for Feynman + OpenCode) ─────────────────
    npm_exe = shutil.which("npm")
    if npm_exe:
        console.print("  [green]Node.js / npm:[/] found")
    else:
        console.print(
            "  [yellow]Node.js / npm:[/] not installed  (required for Feynman and OpenCode)"
        )
        _os_name = _platform.system()
        if _os_name == "Windows":
            console.print("    winget install OpenJS.NodeJS.LTS")
        elif _os_name == "Darwin":
            console.print("    brew install node")
        else:
            console.print("    nvm install --lts    # see https://nodejs.org")
    console.print()

    # ── Feynman ──────────────────────────────────────────────────────────────
    try:
        _find_feynman(settings.research.feynman_command)
        console.print("  [green]Feynman:[/] installed")
    except FeynmanNotFoundError:
        console.print("  [yellow]Feynman:[/] not installed  (~2 GB disk space)")
        if npm_exe:
            if typer.confirm("  Install Feynman now?", default=False):
                _run_tool_install(console, ["npm", "install", "-g", "@companion-ai/feynman"])
        else:
            console.print("  [dim]Install Node.js first, then run:[/]")
            console.print("    npm install -g @companion-ai/feynman")
    console.print()

    # ── OpenCode ─────────────────────────────────────────────────────────────
    oc_exe = shutil.which("opencode")
    if oc_exe:
        console.print("  [green]OpenCode:[/] installed")
        console.print("  [dim]Start the server when needed:[/] opencode serve --port 4096")
    else:
        console.print(
            "  [yellow]OpenCode:[/] not installed  (required for docent backend research)"
        )
        if npm_exe:
            if typer.confirm("  Install OpenCode now?", default=False):
                _run_tool_install(console, ["npm", "install", "-g", "opencode-ai"])
                console.print("  [dim]Start the server with:[/] opencode serve --port 4096")
        else:
            console.print("  [dim]Install Node.js first, then run:[/]")
            console.print("    npm install -g opencode-ai")
            console.print("  [dim]Then start with:[/] opencode serve --port 4096")
    console.print()

    # ── NotebookLM ───────────────────────────────────────────────────────────
    nlm_exe = shutil.which("notebooklm")
    try:
        import contextlib as _cl
        import io as _io
        import sys as _sys

        if "notebooklm" not in _sys.modules:
            import os as _os

            _os.environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1")
            with _cl.redirect_stderr(_io.StringIO()):
                import notebooklm as _nlm_mod  # noqa: F401
        else:
            import notebooklm as _nlm_mod  # noqa: F401
        _nlm_pkg_ok = True
    except ImportError:
        _nlm_pkg_ok = False

    if nlm_exe and _nlm_pkg_ok:
        console.print("  [green]NotebookLM:[/] installed")
        import json as _j
        import subprocess as _sp

        def _nlm_auth_check() -> bool:
            try:
                _r = _sp.run(
                    [nlm_exe, "list", "--json"], capture_output=True, text=True, timeout=10
                )
                return _r.returncode == 0 and not _j.loads(_r.stdout or "{}").get("error")
            except Exception:
                return False

        _auth_ok = _nlm_auth_check()
        if not _auth_ok:
            console.print("  [yellow]NotebookLM:[/] not authenticated")
            if typer.confirm("  Log in to NotebookLM now? (opens a browser)", default=True):
                _sp.run([nlm_exe, "login"])
                _auth_ok = _nlm_auth_check()
                if _auth_ok:
                    console.print("  [green]NotebookLM:[/] authenticated successfully!")
                else:
                    console.print(
                        "  [yellow]NotebookLM:[/] authentication may not have completed.\n"
                        "  Re-run [cyan]docent setup[/] or run [cyan]notebooklm login[/] manually."
                    )
        else:
            console.print("  [green]NotebookLM:[/] authenticated")

        if _auth_ok:
            # Tier / source-limit config (notebooklm-py doesn't expose this, so we ask once)
            _current_limit = settings.research.notebooklm_source_limit
            _default_tier = "2" if _current_limit >= 100 else "1"
            console.print(
                f"  [dim]Source limit: {_current_limit} per notebook[/]  "
                "[dim](free tier = 50 · NotebookLM Plus = 100)[/]"
            )
            _tier_raw = typer.prompt(
                "  Your NotebookLM plan  [1] Free · [2] Plus",
                default=_default_tier,
                show_default=True,
            ).strip()
            _new_limit = 100 if _tier_raw == "2" else 50
            if _new_limit != _current_limit:
                write_setting("research.notebooklm_source_limit", _new_limit)
                console.print(f"  [green]Source limit set to {_new_limit}.[/]")
    else:
        console.print(
            "  [yellow]NotebookLM:[/] not installed  (required for `docent studio to-notebook`)"
        )
        if typer.confirm("  Install notebooklm-py now?", default=False):
            pip_ok = _run_tool_install(console, ["pip", "install", "notebooklm-py[browser]"])
            if pip_ok:
                pw_exe = shutil.which("playwright") or "playwright"
                _run_tool_install(console, [pw_exe, "install", "chromium"])
                console.print("  [dim]Next: log in with[/] notebooklm login")
                if typer.confirm("  Log in to NotebookLM now? (opens a browser)", default=True):
                    import subprocess as _sp2

                    _sp2.run([shutil.which("notebooklm") or "notebooklm", "login"])
        else:
            console.print("  [dim]To install:[/]")
            console.print('    pip install "notebooklm-py[browser]"')
            console.print("    playwright install chromium")
            console.print("    notebooklm login")
    console.print()

    console.print("[bold green]Setup complete![/]  Run [cyan]docent doctor[/] to verify.")


def _run_setup_if_needed() -> bool:
    """Run the full setup flow on first use. Returns True if setup was run.

    Skipped silently in non-TTY contexts (MCP, pipes, tests).
    """
    if not sys.stdin.isatty():
        return False
    if _is_setup_complete():
        return False
    _run_setup_flow(first_run=True)
    return True

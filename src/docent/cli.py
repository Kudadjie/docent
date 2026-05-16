# ruff: noqa: E402 — imports after _patch_rich_unicode_loader() call are intentional
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Any, Callable


def _patch_rich_unicode_loader() -> None:
    """Fix Rich 15.0.0 on Python 3.13: unicode data files are named unicode17-0-0.py
    (hyphens) which importlib.import_module can't resolve. Replace load() with a
    version that uses spec_from_file_location instead."""
    try:
        import bisect
        import importlib.util
        import os
        import unicodedata
        from functools import lru_cache

        import rich._unicode_data as _rd
        from rich._unicode_data._versions import VERSIONS

        _data_dir = os.path.dirname(os.path.abspath(_rd.__file__))
        _version_set = set(VERSIONS)
        _version_order = [[int(x) for x in v.split(".")] for v in VERSIONS]

        @lru_cache(maxsize=None)
        def _fixed_load(unicode_version: str = "auto"):
            if unicode_version in ("auto", "latest"):
                detected = unicodedata.unidata_version  # e.g. "17.0.0"
            else:
                detected = unicode_version
            try:
                parts = [int(x) for x in detected.split(".")]
                ver = f"{parts[0]}.{parts[1]}.{parts[2]}"
                if ver not in _version_set:
                    idx = bisect.bisect_right(_version_order, parts) - 1
                    ver = VERSIONS[max(0, idx)]
            except (ValueError, IndexError):
                ver = VERSIONS[-1]
            ver_comp = ver.replace(".", "-")
            fname = os.path.join(_data_dir, f"unicode{ver_comp}.py")
            spec = importlib.util.spec_from_file_location(
                f"_rich_ud_{ver_comp.replace('-', '_')}", fname
            )
            module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            return module.cell_table

        _rd.load = _fixed_load
    except Exception:
        pass  # If patching fails, let the original error surface


_patch_rich_unicode_loader()


import typer
from pydantic import BaseModel
from rich import box
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from docent import __version__
from docent.config import Settings, load_settings, write_setting
from docent.core import (
    Context,
    ProgressEvent,
    Tool,
    all_tools,
    collect_actions,
    load_plugins,
    run_startup_hooks,
)
from docent.execution import Executor
from docent.llm import LLMClient
from docent.tools import discover_tools
from docent.ui import configure_console, get_console

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
            console.print(f"  [red]Command failed (exit {result.returncode}).[/] Try running it manually.")
            return False
        return True
    except FileNotFoundError:
        console.print(f"  [red]{cmd[0]!r} not found.[/] Make sure it is installed and on PATH.")
        return False
    except Exception as exc:
        console.print(f"  [red]Error:[/] {exc}")
        return False


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
    program = typer.prompt("  Program / field of study", default=existing.get("program", "")).strip()

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
        masked = (existing_tavily[:4] + "..." + existing_tavily[-4:]) if len(existing_tavily) > 8 else "set"
        console.print(f"  [dim]Tavily key: currently {masked}[/]")
    else:
        console.print("  [dim]Tavily: free tier at tavily.com - 1,000 calls/month[/]")
    tavily_raw = typer.prompt("  Tavily API key (Enter to skip)", default="", show_default=False).strip()
    if tavily_raw:
        try:
            write_setting("research.tavily_api_key", tavily_raw)
            console.print("  [green]Tavily key saved.[/]")
        except Exception as e:
            console.print(f"  [yellow]Could not save: {e}[/]")

    existing_ss = settings.research.semantic_scholar_api_key or ""
    if existing_ss:
        console.print("  [dim]Semantic Scholar key: already set[/]")
    ss_raw = typer.prompt("  Semantic Scholar key (Enter to skip)", default="", show_default=False).strip()
    if ss_raw and ss_raw != existing_ss:
        try:
            write_setting("research.semantic_scholar_api_key", ss_raw)
            console.print("  [green]Semantic Scholar key saved.[/]")
        except Exception as e:
            console.print(f"  [yellow]Could not save: {e}[/]")
    console.print()

    # ── External tools ──
    import platform as _platform
    import shutil
    console.print("[bold]External Tools[/]")
    from docent.bundled_plugins.studio import _find_feynman, FeynmanNotFoundError

    # ── Node.js / npm (prerequisite for Feynman + OpenCode) ─────────────────
    npm_exe = shutil.which("npm")
    if npm_exe:
        console.print("  [green]Node.js / npm:[/] found")
    else:
        console.print("  [yellow]Node.js / npm:[/] not installed  (required for Feynman and OpenCode)")
        _sys = _platform.system()
        if _sys == "Windows":
            console.print("    winget install OpenJS.NodeJS.LTS")
        elif _sys == "Darwin":
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
        console.print("  [yellow]OpenCode:[/] not installed  (required for docent backend research)")
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
        import notebooklm as _nlm_mod  # noqa: F401
        _nlm_pkg_ok = True
    except ImportError:
        _nlm_pkg_ok = False

    if nlm_exe and _nlm_pkg_ok:
        console.print("  [green]NotebookLM:[/] installed")
        import subprocess as _sp
        import json as _j

        def _nlm_auth_check() -> bool:
            try:
                _r = _sp.run([nlm_exe, "list", "--json"], capture_output=True, text=True, timeout=10)
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
        console.print("  [yellow]NotebookLM:[/] not installed  (required for `docent studio to-notebook`)")
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


def _startup_doctor_check(settings: Any) -> None:
    """Fast (<10ms, no subprocess) startup health check.

    Only shows a banner when config that was previously set is now broken
    (e.g. database_dir path deleted). Silent when all is OK.
    Skipped in non-TTY contexts.
    """
    if not sys.stdin.isatty():
        return

    issues: list[str] = []

    db = settings.reading.database_dir
    if db is not None:
        expanded = Path(str(db)).expanduser()
        if not expanded.exists():
            issues.append(f"reading DB path missing: {expanded}")

    if issues:
        console = get_console()
        noun = "issue" if len(issues) == 1 else "issues"
        console.print(
            f"[yellow]{len(issues)} config {noun} detected[/]  "
            "[dim]Run [cyan]docent doctor[/] for details.[/]"
        )

app = typer.Typer(
    name="docent",
    help="Docent — a personal control center for grad school workflows.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"docent {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the Docent version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable colored output.",
    ),
) -> None:
    """Docent — grad-school workflow dispatcher."""
    settings = load_settings()
    settings.verbose = verbose or settings.verbose
    settings.no_color = no_color or settings.no_color

    configure_console(no_color=settings.no_color)

    from docent.utils.logging import configure_logging
    from docent.utils.paths import logs_dir
    configure_logging(verbose=settings.verbose, log_dir=logs_dir())

    # Skip startup prompts for commands that manage their own output or that run
    # as a stdio server (serve) where stdout must be pure JSON-RPC.
    _skip_startup = ctx.invoked_subcommand in ("setup", "doctor", "serve")
    if not _skip_startup:
        _run_setup_if_needed()
        _startup_doctor_check(settings)

    ctx.obj = Context(settings=settings, llm=LLMClient(settings), executor=Executor())
    if not _skip_startup:
        run_startup_hooks(ctx.obj)


@app.command("list", help="List all registered tools.")
def list_command(ctx: typer.Context) -> None:
    console = get_console()
    tools = all_tools()
    if not tools:
        console.print("[dim]No tools registered yet.[/]")
        return

    by_category: dict[str, list[type[Tool]]] = {}
    for tool_cls in tools.values():
        by_category.setdefault(tool_cls.category or "Uncategorized", []).append(tool_cls)

    for category, group in sorted(by_category.items()):
        table = Table(title=category, box=box.ROUNDED, show_header=True, header_style="bold")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Description")
        for tc in sorted(group, key=lambda c: c.name):
            actions = collect_actions(tc)
            name_display = tc.name if not actions else f"{tc.name}  ({len(actions)} actions)"
            table.add_row(name_display, tc.description)
        console.print(table)


@app.command("info", help="Show details about a registered tool.")
def info_command(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Name of the tool."),
) -> None:
    console = get_console()
    tools = all_tools()
    if name not in tools:
        console.print(f"[red]No tool named '{name}'.[/]")
        raise typer.Exit(2)

    tool_cls = tools[name]
    lines = [
        f"[bold]Name:[/] {tool_cls.name}",
        f"[bold]Category:[/] {tool_cls.category or 'Uncategorized'}",
        f"[bold]Description:[/] {tool_cls.description}",
    ]

    actions = collect_actions(tool_cls)
    if actions:
        lines.append("")
        lines.append(f"[bold]Actions ({len(actions)}):[/]")
        for cli_name, (_method_name, meta) in sorted(actions.items()):
            lines.append(f"  [cyan]{cli_name}[/] - {meta.description}")
            for fname, finfo in meta.input_schema.model_fields.items():
                lines.append(f"      {_format_field(fname, finfo)}")
    else:
        assert tool_cls.input_schema is not None
        lines.append("")
        lines.append("[bold]Inputs:[/]")
        for fname, finfo in tool_cls.input_schema.model_fields.items():
            lines.append(f"  {_format_field(fname, finfo)}")

    console.print(Panel("\n".join(lines), title=tool_cls.name, border_style="cyan"))


def _format_field(fname: str, finfo: Any) -> str:
    status = "(required)" if finfo.is_required() else f"(default={finfo.default!r})"
    annot = getattr(finfo.annotation, "__name__", str(finfo.annotation))
    desc = f" - {finfo.description}" if finfo.description else ""
    return f"--{fname.replace('_', '-')}: {annot} {status}{desc}"


# ─── doctor / setup helpers ───────────────────────────────────────────────────

_STATUS_STYLE: dict[str, str] = {"OK": "green", "WARN": "yellow", "FAIL": "red", "SKIP": "dim"}


def _check_profile(user_file: Path | None = None) -> tuple[str, str, str, str]:
    try:
        resolved = user_file if user_file is not None else _user_file()
        data = json.loads(resolved.read_text(encoding="utf-8"))
        name = (data.get("name") or "").strip()
        if name and name != "You":
            return "Profile", "OK", "-", f"{name} | {data.get('level', '?')} | {data.get('program', '?')}"
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
            info = check_github_release(github_repo, current_version=bare,
                                        upgrade_cmd=upgrade_cmd)
            if info:
                update_note = f"update: {info.latest} - {info.upgrade_cmd}"
        elif npm_package:
            from docent.utils.update_check import check_npm
            info = check_npm(npm_package, current_version=bare,
                             upgrade_cmd=upgrade_cmd)
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
        return total / (1024 ** 3)
    except Exception:
        return None


def _check_feynman(settings: Settings) -> tuple[str, str, str, str]:
    import os
    import re
    from docent.bundled_plugins.studio import _find_feynman, FeynmanNotFoundError, _feynman_version_from_package_json
    from docent.utils.update_check import check_github_release

    try:
        cmd = _find_feynman(settings.research.feynman_command)
    except FeynmanNotFoundError:
        return "Feynman CLI", "WARN", "-", "Not installed (~2 GB needed) - npm install -g @companion-ai/feynman"

    # Read version from package.json — avoids spawning a Node.js subprocess
    # which can hang on Windows when capture_output+timeout is used.
    version = _feynman_version_from_package_json(cmd)

    detail_parts: list[str] = []
    m = re.search(r"\d+\.\d+(?:\.\d+)?", version)
    bare = m.group() if m else None
    update_info = check_github_release("companion-inc/feynman", current_version=bare,
                                       upgrade_cmd="npm install -g @companion-ai/feynman@latest")
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
    return "Mendeley MCP", "FAIL", "-", f"{runner} not found - install uv: https://docs.astral.sh/uv/"


def _check_tavily(settings: Settings) -> tuple[str, str, str, str]:
    key = settings.research.tavily_api_key
    if key:
        masked = (key[:4] + "..." + key[-4:]) if len(key) > 8 else "set"
        return "Tavily key", "OK", "-", f"configured ({masked})"
    return "Tavily key", "WARN", "-", "Not set - free at tavily.com  (docent setup to configure)"


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
    update_hint = f"  (update available: {update.latest}  run: {update.upgrade_cmd})" if update else ""
    key = settings.research.alphaxiv_api_key
    if key:
        masked = (key[:4] + "..." + key[-4:]) if len(key) > 8 else "set"
        return "alphaXiv", "OK", ax_version, f"API key configured ({masked}){update_hint}"
    return "alphaXiv", "SKIP", ax_version, f"No key (optional - get free key at alphaxiv.org/settings){update_hint}"


def _check_notebooklm_py() -> tuple[str, str, str, str]:
    import shutil
    import subprocess

    # 1. Python package
    try:
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
            capture_output=True, text=True, timeout=10,
        )
        import json as _json
        data = _json.loads(result.stdout or "{}")
        auth_ok = result.returncode == 0 and not data.get("error")
    except Exception:
        auth_ok = False

    if not auth_ok:
        return "NotebookLM", "WARN", nlm_version, "Not authenticated — run: docent setup  (or: notebooklm login)"

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


def _check_reading_db(settings: Settings) -> tuple[str, str, str, str]:
    db = settings.reading.database_dir
    if db is None:
        return "Reading DB", "WARN", "-", "Not configured - run: docent reading config-set --key database_dir --value <path>"
    expanded = Path(str(db)).expanduser()
    if not expanded.exists():
        return "Reading DB", "WARN", "-", f"{expanded} does not exist"
    return "Reading DB", "OK", "-", str(expanded)


def _drive_progress(gen: Any) -> Any:
    """Drive a generator-based action, rendering events with Rich Progress.

    Phase changes swap to a fresh task. Events with (current, total) advance
    a bar; events without it (or with level=warn/error) print a console line.
    The action's `return` value is captured from `StopIteration.value`.
    """
    console = get_console()
    columns = (
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[item]}"),
        TimeElapsedColumn(),
    )
    result: Any = None
    with Progress(*columns, console=console, transient=False) as progress:
        task_id: int | None = None
        current_phase: str | None = None
        try:
            while True:
                evt = next(gen)
                if not isinstance(evt, ProgressEvent):
                    progress.console.print(f"[yellow]warn[/] non-event yielded: {evt!r}")
                    continue
                if evt.level in ("warn", "error"):
                    tag = "[yellow]warn[/]" if evt.level == "warn" else "[red]error[/]"
                    text = evt.message or (f"{evt.phase}: {evt.item}" if evt.item else evt.phase)
                    progress.console.print(f"{tag} {text}")
                    continue
                if evt.total is not None:
                    if task_id is None or evt.phase != current_phase:
                        if task_id is not None:
                            progress.remove_task(task_id)
                        task_id = progress.add_task(
                            evt.phase, total=evt.total, item=evt.item or ""
                        )
                        current_phase = evt.phase
                    progress.update(
                        task_id, completed=evt.current or 0, item=evt.item or ""
                    )
                elif evt.message:
                    progress.console.print(f"[dim]{evt.phase}[/] {evt.message}")
        except StopIteration as stop:
            result = stop.value
        except KeyboardInterrupt:
            gen.close()
            progress.console.print("\n[yellow]Interrupted[/] (Ctrl+C)")
            import typer as _typer
            raise _typer.Exit(130)
    return result


def _build_callback(
    schema: type[BaseModel],
    invoke: Callable[[BaseModel, Context], Any],
    name: str,
    doc: str,
    preflight: Callable[[BaseModel, Context], None] | None = None,
) -> Any:
    """Build a Typer callback with a synthesized signature from a Pydantic schema.

    `invoke(inputs, context)` is called with validated inputs and the Context
    from `ctx.obj`. Its return value (if not None) is printed via the CLI's
    console singleton.

    If ``preflight`` is provided it runs *before* ``invoke`` — outside any
    Rich Progress wrapper.  This is where interactive prompts (e.g. API-key
    entry) must live, because Rich Progress steals stdin.
    """

    def callback(**kwargs: Any) -> None:
        from docent.errors import DocentError
        from docent.utils.logging import get_logger
        _log = get_logger("docent.cli")

        ctx: typer.Context = kwargs.pop("ctx")
        inputs = schema(**kwargs)
        context: Context = ctx.obj
        try:
            if preflight is not None:
                preflight(inputs, context)
            maybe = invoke(inputs, context)
            result = _drive_progress(maybe) if inspect.isgenerator(maybe) else maybe
        except DocentError as exc:
            _log.error("%s", exc, exc_info=exc)
            get_console().print(f"[red]Error:[/] {exc.formatted()}")
            raise typer.Exit(1)
        except Exception:
            _log.exception("Unhandled exception in action callback")
            raise
        if result is not None:
            console = get_console()
            if hasattr(result, "to_shapes"):
                from docent.ui.renderers import render_shapes
                render_shapes(result.to_shapes(), console)
            else:
                console.print(result)

    params = [
        inspect.Parameter("ctx", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=typer.Context),
    ]
    annotations: dict[str, Any] = {"ctx": typer.Context}

    for fname, finfo in schema.model_fields.items():
        cli_flag = "--" + fname.replace("_", "-")
        help_text = finfo.description or ""
        if finfo.is_required():
            option_default = ...
        elif finfo.default_factory is not None:
            option_default = finfo.default_factory()
        else:
            option_default = finfo.default
        option = typer.Option(option_default, cli_flag, help=help_text)
        params.append(
            inspect.Parameter(
                fname,
                inspect.Parameter.KEYWORD_ONLY,
                default=option,
                annotation=finfo.annotation,
            )
        )
        annotations[fname] = finfo.annotation

    callback.__signature__ = inspect.Signature(params)  # type: ignore[attr-defined]
    callback.__annotations__ = annotations
    callback.__name__ = name
    callback.__doc__ = doc
    return callback


def _register_tool_in_app(tool_cls: type[Tool]) -> None:
    """Attach a single- or multi-action tool to the top-level Typer app."""
    actions = collect_actions(tool_cls)

    if not actions:
        assert tool_cls.input_schema is not None
        callback = _build_callback(
            schema=tool_cls.input_schema,
            invoke=lambda inp, ctx: tool_cls().run(inp, ctx),
            name=tool_cls.name.replace("-", "_"),
            doc=tool_cls.description,
        )
        app.command(name=tool_cls.name, help=tool_cls.description)(callback)
        return

    subapp = typer.Typer(
        name=tool_cls.name,
        help=tool_cls.description,
        no_args_is_help=True,
        add_completion=False,
    )
    for cli_name, (method_name, meta) in sorted(actions.items()):
        def make_invoke(mname: str) -> Callable[[BaseModel, Context], Any]:
            return lambda inp, ctx, _m=mname: getattr(tool_cls(), _m)(inp, ctx)

        callback = _build_callback(
            schema=meta.input_schema,
            invoke=make_invoke(method_name),
            name=cli_name.replace("-", "_"),
            doc=meta.description,
            preflight=meta.preflight,
        )
        subapp.command(name=cli_name, help=meta.description)(callback)
    app.add_typer(subapp, name=tool_cls.name, help=tool_cls.description)


discover_tools()
load_plugins()
for _tool_cls in all_tools().values():
    _register_tool_in_app(_tool_cls)


@app.command("update", help="Upgrade Docent to the latest version on PyPI.")
def update_command() -> None:
    """Upgrade the installed docent-cli package via uv tool upgrade."""
    import subprocess

    console = get_console()
    console.print(f"[dim]Installed version:[/] {__version__}")
    console.print("[dim]Running:[/] uv tool upgrade docent-cli\n")
    result = subprocess.run(["uv", "tool", "upgrade", "docent-cli"])
    if result.returncode != 0:
        console.print("\n[red]Upgrade failed.[/] Check the output above.")
        raise typer.Exit(1)
    console.print("\n[green]Upgraded successfully.[/]")
    console.print(
        "[dim]If you use Docent via MCP, restart Claude to load the new version.[/]"
    )


@app.command("ui", help="Start the Docent web UI on localhost.")
def ui_command(
    port: int = typer.Option(7432, "--port", help="Port to listen on."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Skip opening the browser."),
) -> None:
    """Serve the Docent web UI via FastAPI + the pre-built Next.js static export.

    Build the UI first with:  python scripts/build_ui.py
    """
    from docent.ui_server import UI_DIST, run_server

    if not UI_DIST.is_dir():
        get_console().print(
            "[red]UI not built.[/] Run [cyan]python scripts/build_ui.py[/] first.\n"
            "[dim](When installed from PyPI the UI is included automatically.)[/]"
        )
        raise typer.Exit(1)

    import webbrowser

    url = f"http://127.0.0.1:{port}"
    get_console().print(f"[bold]Docent UI[/]  [cyan]{url}[/]")
    get_console().print("[dim]Press Ctrl+C to stop.[/]\n")
    if not no_browser:
        webbrowser.open(url)
    run_server(port=port)


@app.command("serve", help="Start the Docent MCP server (stdio transport).")
def serve_command() -> None:
    """Expose all registered Docent actions as MCP tools over stdio.

    Add to Claude Code's .mcp.json:

    \\b
    {
      "mcpServers": {
        "docent": {
          "command": "uv",
          "args": ["--directory", "<project-root>", "run", "docent", "serve"]
        }
      }
    }
    """
    from docent.mcp_server import run_server

    run_server()


_AUTO_INSTALL: dict[str, tuple[list[str], str]] = {
    "Feynman CLI": (["npm", "install", "-g", "@companion-ai/feynman"], "~2 GB, requires Node.js"),
    "Mendeley MCP": (["uv", "tool", "install", "mendeley-mcp"], "requires uv"),
}


def _collect_install_offers(
    checks: list[tuple[str, str, str, str]],
) -> list[tuple[str, list[str], str]]:
    """Return (name, cmd, note) for installable tools that are missing/failed."""
    offers = []
    for label, status, _ver, detail in checks:
        if label not in _AUTO_INSTALL:
            continue
        if status == "FAIL" or (status == "WARN" and "Not installed" in detail):
            cmd, note = _AUTO_INSTALL[label]
            offers.append((label, cmd, note))
    return offers


@app.command("doctor", help="Check environment, tooling versions, and auth status.")
def doctor_command(ctx: typer.Context) -> None:
    """Run diagnostics on Docent's environment and third-party tooling."""
    import sys
    from concurrent.futures import ThreadPoolExecutor

    console = get_console()
    settings = ctx.obj.settings

    console.print("\n[bold]Checking your Docent environment...[/]\n")

    # Run all checks in parallel so subprocess timeouts don't stack sequentially.
    check_fns = [
        lambda: _check_profile(),
        lambda: ("Python", "OK", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "-"),
        lambda: _check_cli_tool(
            "uv", ["uv", "--version"], "Install uv: https://docs.astral.sh/uv/",
            github_repo="astral-sh/uv",
            upgrade_cmd="uv self update",
        ),
        lambda: _check_cli_tool("Node.js", ["node", "--version"], "Install Node.js: https://nodejs.org"),
        lambda: _check_cli_tool("npm", ["npm", "--version"], "Install npm: https://nodejs.org"),
        lambda: _check_feynman(settings),
        lambda: _check_opencode(settings),
        lambda: _check_mendeley_mcp(settings),
        lambda: _check_tavily(settings),
        lambda: _check_semantic_scholar(settings),
        lambda: _check_alphaxiv(settings),
        lambda: _check_notebooklm_py(),
        lambda: _check_reading_db(settings),
    ]
    with ThreadPoolExecutor(max_workers=len(check_fns)) as pool:
        futures = [pool.submit(fn) for fn in check_fns]
        checks: list[tuple[str, str, str, str]] = [f.result() for f in futures]

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Version", no_wrap=True)
    table.add_column("Detail")

    issues = 0
    for label, status, version, detail in checks:
        style = _STATUS_STYLE.get(status, "white")
        table.add_row(label, f"[{style}]{status}[/{style}]", version, detail)
        if status in ("WARN", "FAIL"):
            issues += 1

    console.print(table)
    if issues == 0:
        console.print("[green]All checks passed.[/]")
    else:
        noun = "issue" if issues == 1 else "issues"
        console.print(f"\n[yellow]{issues} {noun} found.[/]  Run [cyan]docent setup[/] to configure missing items.")

    # Offer to install missing CLI tools (feynman, mendeley-mcp only).
    installable = _collect_install_offers(checks)
    if installable:
        import shutil
        import subprocess as _sp
        console.print()
        for name, cmd, note in installable:
            runner = shutil.which(cmd[0])
            if runner is None:
                console.print(f"[dim]  {name}: {cmd[0]} not on PATH, install manually: {' '.join(cmd)}[/]")
                continue
            if typer.confirm(f"  Install {name} ({note})  via: {' '.join(cmd)}?", default=False):
                console.print(f"  Running: {' '.join(cmd)} ...")
                result = _sp.run([runner] + cmd[1:], check=False)
                if result.returncode == 0:
                    console.print(f"  [green]{name} installed.[/]  Re-run [cyan]docent doctor[/] to verify.")
                else:
                    console.print(f"  [red]{name} install failed (exit {result.returncode}).[/]  Run manually: {' '.join(cmd)}")


@app.command("setup", help="Interactive setup: profile, database folder, and API keys.")
def setup_command() -> None:
    """Configure Docent interactively. Safe to re-run - existing values shown as defaults."""
    _run_setup_flow(first_run=False)


if __name__ == "__main__":
    app()

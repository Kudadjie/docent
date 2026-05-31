# ruff: noqa: E402 — Rich compat patch must run before any Rich import
from __future__ import annotations

import warnings

# Must be before any import that might pull in scholarly — the SyntaxWarning for
# the invalid \d escape in scholarly._scholarly fires at bytecode-compile time in
# Python 3.13, before any lazy-import filter in scholarly_client.py can take effect.
warnings.filterwarnings("ignore", category=SyntaxWarning, module=r"scholarly")

import inspect
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from docent.utils.rich_compat import patch_rich_unicode_loader

patch_rich_unicode_loader()


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
from docent.cli_setup import _run_setup_flow, _run_setup_if_needed
from docent.config import load_settings
from docent.core import (
    Context,
    ProgressEvent,
    Tool,
    all_tools,
    collect_actions,
    list_plugins,
    load_plugins,
    run_startup_hooks,
)
from docent.execution import Executor
from docent.llm import LLMClient
from docent.tools import discover_tools
from docent.ui import configure_console, get_console


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
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=False,
)


# Commands that must NOT drop into the workspace after running (they manage
# their own long-running loops or interactive prompts).
_NO_WORKSPACE_CMDS = frozenset({"serve", "setup", "doctor", "ui"})


def _workspace_eligible() -> bool:
    """True only in an interactive, non-subprocess terminal."""
    import os as _os
    import sys as _sys

    return (
        _sys.stdin.isatty()
        and _sys.stdout.isatty()
        and not _os.environ.get("DOCENT_UI_SUBPROCESS")
        and not _os.environ.get("DOCENT_WORKSPACE")
    )


def _run_workspace() -> None:
    """Blocking REPL — runs after the initial banner/command."""
    import os as _os
    import shlex

    if not _workspace_eligible():
        return

    _os.environ["DOCENT_WORKSPACE"] = "1"
    console = get_console()

    # Optional readline history (Unix; silently skipped on Windows)
    try:
        import readline as _rl

        from docent.utils.paths import root_dir as _rd

        _hist = _rd() / ".repl_history"
        _hist.parent.mkdir(parents=True, exist_ok=True)
        try:
            _rl.read_history_file(str(_hist))
        except FileNotFoundError:
            pass
        _rl.set_history_length(500)
        import atexit as _ae

        _ae.register(_rl.write_history_file, str(_hist))
    except (ImportError, Exception):
        pass

    console.print(
        "\n[dim]Docent workspace — type subcommands without the [bold cyan]docent[/bold cyan] prefix. "
        "[bold]exit[/bold] or Ctrl+C to leave.[/]\n"
    )

    while True:
        try:
            line = input("  docent › ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Leaving workspace.[/]")
            break

        if not line:
            continue
        if line in ("exit", "quit", "q"):
            console.print("[dim]Leaving workspace.[/]")
            break

        try:
            args = shlex.split(line)
        except ValueError as exc:
            console.print(f"[red]Parse error:[/] {exc}")
            continue

        try:
            app(args=args, standalone_mode=False)
        except (SystemExit, typer.Exit):
            pass
        except Exception as exc:
            # Click raises UsageError with an empty message when a group is
            # invoked with no subcommand (help already printed). Suppress those.
            msg = str(exc).strip()
            if msg:
                console.print(f"[red]Error:[/] {msg}")

        console.print()

    _os.environ.pop("DOCENT_WORKSPACE", None)


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

    import os as _os
    import sys as _sys

    # Inside the workspace REPL, banner and startup prompts are already done.
    _in_workspace = bool(_os.environ.get("DOCENT_WORKSPACE"))

    # Show the startup banner when running interactively.
    # For `serve`, print to stderr so the MCP JSON-RPC stdout stream is unaffected.
    # Skip for setup/doctor (manage their own output), non-TTY, and workspace REPL.
    _is_tty = _sys.stdout.isatty() or _sys.stderr.isatty()
    _banner_skip = (
        settings.no_color
        or not _is_tty
        or _in_workspace
        or ctx.invoked_subcommand in ("setup", "doctor")
    )
    if not _banner_skip:
        from docent._banner import print_banner

        if ctx.invoked_subcommand == "serve":
            from rich.console import Console as _RC

            print_banner(_RC(stderr=True, highlight=False))
        else:
            print_banner(get_console())

    # Skip startup prompts for commands that manage their own output or that run
    # as a stdio server (serve) where stdout must be pure JSON-RPC, and workspace.
    _skip_startup = _in_workspace or ctx.invoked_subcommand in ("setup", "doctor", "serve")
    if not _skip_startup:
        _run_setup_if_needed()
        _startup_doctor_check(settings)
        _maybe_show_whatsnew()

    ctx.obj = Context(settings=settings, llm=LLMClient(settings), executor=Executor())
    if not _skip_startup:
        run_startup_hooks(ctx.obj)

    # ── Workspace entry ────────────────────────────────────────────────────────
    if ctx.invoked_subcommand is None:
        # No subcommand: enter workspace immediately (or show help in non-TTY).
        if _workspace_eligible():
            _run_workspace()
        else:
            _sys.stdout.write(ctx.get_help() + "\n")
        raise typer.Exit()
    elif ctx.invoked_subcommand not in _NO_WORKSPACE_CMDS and _workspace_eligible():
        # Subcommand given: run it first, then enter workspace via close callback.
        ctx.call_on_close(_run_workspace)


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


@app.command("plugins", help="List loaded plugins and their startup hooks.")
def plugins_command(ctx: typer.Context) -> None:  # noqa: ARG001
    console = get_console()
    plugins = list_plugins()
    if not plugins:
        console.print("[dim]No plugins loaded.[/]")
        return
    table = Table(title="Loaded Plugins", box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Source")
    table.add_column("Hook", justify="center")
    for p in plugins:
        hook_mark = "[green]✓[/]" if p["has_hook"] else "[dim]–[/]"
        table.add_row(p["name"], p["source"], hook_mark)
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
        if tool_cls.input_schema is None:
            raise ValueError(
                f"Tool '{tool_cls.name}' has no actions and no input_schema — "
                "this should have been caught at registration time."
            )
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
from docent.cli_doctor import (  # noqa: E402
    _STATUS_STYLE,
    _check_alphaxiv,
    _check_cli_tool,
    _check_feynman,
    _check_google_drive,
    _check_litellm_provider,
    _check_mendeley_mcp,
    _check_notebooklm_py,
    _check_opencode,
    _check_profile,
    _check_reading_db,
    _check_semantic_scholar,
    _check_tavily,
    _check_zotero,
    _dir_size_gb,  # noqa: F401 — re-exported for tests and external callers
)

_UI_PROGRESS_MARKER = "\x00DOCENT_PROGRESS\x00"


def _drive_progress(gen: Any) -> Any:
    """Drive a generator-based action, rendering events with Rich Progress.

    Phase changes swap to a fresh task. Events with (current, total) advance
    a bar; events without it (or with level=warn/error) print a console line.
    The action's `return` value is captured from `StopIteration.value`.

    When DOCENT_UI_SUBPROCESS=1 the Rich renderer is bypassed entirely and
    each event is emitted as a machine-readable ``\\x00DOCENT_PROGRESS\\x00``
    line so the WS handler can parse it unambiguously.
    """
    import os as _os

    if _os.environ.get("DOCENT_UI_SUBPROCESS"):
        result: Any = None
        try:
            while True:
                evt = next(gen)
                if not isinstance(evt, ProgressEvent):
                    continue
                msg = evt.message or ""
                # Escape newlines so the single-line PROGRESS marker isn't split
                # across multiple stdout reads by the WS handler.
                msg_safe = msg.replace("\n", "\x02")
                print(f"{_UI_PROGRESS_MARKER}{evt.phase}\x00{msg_safe}", flush=True)
        except StopIteration as stop:
            result = stop.value
        except KeyboardInterrupt:
            pass
        return result

    console = get_console()
    columns = (
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[item]}"),
        TimeElapsedColumn(),
    )
    result = None
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
                        task_id = progress.add_task(evt.phase, total=evt.total, item=evt.item or "")
                        current_phase = evt.phase
                    progress.update(task_id, completed=evt.current or 0, item=evt.item or "")
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
        context: Context = ctx.obj

        # Render input-validation failures (e.g. an AI-only action given
        # --backend free) as a clean one-line error instead of a raw traceback.
        from pydantic import ValidationError

        try:
            inputs = schema(**kwargs)
        except ValidationError as exc:
            msg = (
                "; ".join(str(e.get("msg", "")).removeprefix("Value error, ") for e in exc.errors())
                or "Invalid input."
            )
            get_console().print(f"[red]Error:[/] {msg}")
            raise typer.Exit(1)

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
            if os.environ.get("DOCENT_UI_SUBPROCESS"):
                # Emit a structured result line for the UI server to parse.
                # This bypasses Rich console rendering entirely so the server gets
                # reliable data rather than scraping wrapped console output.
                _r: dict[str, object] = {}
                for _attr in ("output_file", "notebook_id", "message", "ok"):
                    _v = getattr(result, _attr, None)
                    if _v is not None:
                        _r[_attr] = _v
                # Full structured result for the UI's bespoke panels (search rows,
                # config table, paper details, notebook perspectives). Secret-bearing
                # results expose a to_ui() that masks API keys; everything else dumps
                # its Pydantic model. Best-effort: never let serialization break a run.
                _to_ui = getattr(result, "to_ui", None)
                try:
                    if callable(_to_ui):
                        _r["data"] = _to_ui()
                    elif hasattr(result, "model_dump"):
                        _r["data"] = result.model_dump(mode="json")
                except Exception:
                    pass
                import json as _json

                print(f"\x00DOCENT_RESULT\x00{_json.dumps(_r, default=str)}", flush=True)
                # When the action itself reports failure (ok=False), emit the
                # error message as a progress log line and exit non-zero so the
                # WS handler can surface it as status: 'failure'.
                if not _r.get("ok", True):
                    _msg = str(_r.get("message", "Action failed — check the activity log."))
                    _msg_safe = _msg.replace("\n", "\x02")
                    print(f"\x00DOCENT_PROGRESS\x00error\x00{_msg_safe}", flush=True)
                    raise typer.Exit(1)
            else:
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
        if finfo.annotation is bool:
            no_cli_flag = "--no-" + fname.replace("_", "-")
            option = typer.Option(option_default, f"{cli_flag}/{no_cli_flag}", help=help_text)
        else:
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
        if tool_cls.input_schema is None:
            raise ValueError(
                f"Tool '{tool_cls.name}' has no actions and no input_schema — "
                "this should have been caught at registration time."
            )
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


def _maybe_show_whatsnew() -> None:
    """Show a brief post-update 'What's New' banner on an interactive terminal.

    Quiet on first run and once the banner has been shown a few times after an
    update (see docent.whatsnew.pop_banner_release). Never raises.
    """
    import os as _os

    if not sys.stdout.isatty() or _os.environ.get("DOCENT_UI_SUBPROCESS"):
        return
    try:
        from docent.whatsnew import pop_banner_release

        rel = pop_banner_release()
    except Exception:
        return
    if rel is None or not rel.highlights:
        return
    bullets = "\n".join(f"  • {h}" for h in rel.highlights[:4])
    body = (
        f"[dim]Updated to[/] [bold]{rel.version}[/]\n{bullets}\n"
        "[dim]Run[/] [cyan]docent whatsnew[/] [dim]for the full notes.[/]"
    )
    get_console().print(Panel(body, title="What's New", border_style="cyan", expand=False))


@app.command("whatsnew", help="Show what changed in the current Docent version.")
def whatsnew_command() -> None:
    """Print the current version's release highlights from the changelog."""
    from docent.whatsnew import get_release

    console = get_console()
    rel = get_release()
    if rel is None or not rel.highlights:
        console.print(f"[dim]No release notes found for[/] [bold]{__version__}[/].")
        console.print("[dim]See https://github.com/Kudadjie/docent/releases[/]")
        return
    when = f" [dim]({rel.date})[/]" if rel.date else ""
    body = "\n".join(f"  • {h}" for h in rel.highlights)
    console.print(
        Panel(body, title=f"What's New in {rel.version}{when}", border_style="cyan", expand=False)
    )


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
    console.print("[dim]If you use Docent via MCP, restart Claude to load the new version.[/]")


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
    try:
        run_server(port=port)
    except OSError as exc:
        if "address already in use" in str(exc).lower() or getattr(exc, "errno", None) in (
            98,
            48,
            10048,
        ):
            get_console().print(
                f"\n[red]Port {port} is already in use.[/]\n"
                f"[dim]Another instance of [bold]docent ui[/bold] is probably already running.\n"
                f"Close that terminal or find and kill the process:[/]\n"
                f"  [cyan]Windows:[/]  netstat -ano | findstr :{port}\n"
                f"  [cyan]Mac/Linux:[/] lsof -i :{port}"
            )
            raise typer.Exit(1)
        raise


@app.command("backup", help="Backup Docent state to Google Drive (or a local zip).")
def backup_command(
    local_only: bool = typer.Option(
        False, "--local-only", help="Create zip but skip Drive upload."
    ),
    out: Path = typer.Option(
        None, "--out", "-o", help="Save zip to this path (implies --local-only)."
    ),
    keep: int = typer.Option(
        10, "--keep", help="Number of Drive backups to retain (older ones deleted)."
    ),
    setup: bool = typer.Option(
        False, "--setup", help="Show Google Drive credential setup instructions."
    ),
) -> None:
    """Create a timestamped zip of Docent config, queue data, and research outputs
    then upload it to a 'Docent Backups' folder in Google Drive.

    Files larger than 100 MB are automatically excluded. Pass --local-only to
    skip Drive upload and keep the zip on disk instead.
    """
    console = get_console()

    if setup:
        console.print(
            Panel(
                "[bold]Google Drive Backup — Setup[/]\n\n"
                "1. Go to [cyan]https://console.cloud.google.com/[/]\n"
                "2. Create (or select) a project → Enable the [bold]Google Drive API[/]\n"
                "3. Credentials → Create Credentials → [bold]OAuth client ID[/]\n"
                "   • Application type: [bold]Desktop app[/]  • Name: Docent\n"
                "4. Download the JSON file and save it as:\n"
                "   [green]~/.docent/drive_credentials.json[/]\n\n"
                "Then run [cyan]docent backup[/] — a browser window will open for\n"
                "sign-in on the first run; the token is cached for future runs.",
                title="Setup",
                border_style="green",
            )
        )
        return

    import tempfile

    from docent.bundled_plugins.backup.manager import archive_name, create_archive

    local_only = local_only or (out is not None)

    # ── Build the archive ─────────────────────────────────────────────────────
    dest = Path(out) if out else Path(tempfile.mkdtemp()) / archive_name()
    fname = dest.name

    with console.status("[green]Creating backup archive…[/]"):
        manifest = create_archive(dest)

    n_in = manifest["files_included"]
    n_ex = manifest["files_excluded"]
    size_mb = manifest["archive_size_mb"]

    console.print(f"[green]✓[/] Archive: [cyan]{dest}[/]")
    console.print(f"  {n_in} files included · {size_mb} MB")
    if n_ex:
        console.print(
            f"  [yellow]Warning:[/] {n_ex} file(s) excluded (>100 MB). "
            "Use an external drive for raw data."
        )

    if local_only:
        return

    # ── Upload to Drive ───────────────────────────────────────────────────────
    from docent.bundled_plugins.backup.drive_client import (
        credentials_file_exists,
        get_or_create_backup_folder,
        get_service,
        trim_old_backups,
        upload_backup,
    )

    if not credentials_file_exists():
        console.print(
            "\n[yellow]Google Drive credentials not found.[/]\n"
            "Run [cyan]docent backup --setup[/] for setup instructions.\n"
            "Your local archive is saved at:\n  [green]{dest}[/]"
        )
        return

    try:
        with console.status("[green]Connecting to Google Drive…[/]"):
            service = get_service()
            folder_id = get_or_create_backup_folder(service)

        with console.status(f"[green]Uploading {fname} ({size_mb} MB)…[/]"):
            file_id = upload_backup(service, dest, folder_id, fname)

        console.print(f"[green]✓[/] Uploaded to Google Drive — file ID: [dim]{file_id}[/]")

        deleted = trim_old_backups(service, folder_id, keep)
        if deleted:
            console.print(
                f"  [dim]{deleted} old backup(s) removed (keeping {keep} most recent).[/]"
            )

    except Exception as exc:
        console.print(f"[red]Drive upload failed:[/] {exc}")
        console.print(f"Local archive kept at: [cyan]{dest}[/]")
        raise typer.Exit(1)
    finally:
        # Delete the temp zip if we didn't use --out
        if out is None and dest.exists():
            dest.unlink(missing_ok=True)


@app.command("restore", help="Restore Docent state from a Google Drive backup.")
def restore_command(
    list_backups: bool = typer.Option(False, "--list", "-l", help="List available Drive backups."),
    backup_id: str = typer.Option("", "--id", help="Drive file ID to restore."),
    local: Path = typer.Option(None, "--local", help="Restore from a local zip file."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Restore Docent config and queue data from a backup.

    Use --list to see available Drive backups, --id to pick one by ID,
    or --local to restore from a local zip file.
    """
    console = get_console()
    import tempfile

    # ── Local restore ─────────────────────────────────────────────────────────
    if local:
        archive = Path(local)
        if not archive.exists():
            console.print(f"[red]File not found:[/] {archive}")
            raise typer.Exit(1)
        _do_restore(console, archive, yes)
        return

    # ── Drive operations ──────────────────────────────────────────────────────
    from docent.bundled_plugins.backup.drive_client import (
        credentials_file_exists,
        download_backup,
        get_or_create_backup_folder,
        get_service,
    )
    from docent.bundled_plugins.backup.drive_client import (
        list_backups as _list,
    )

    if not credentials_file_exists():
        console.print(
            "[yellow]Google Drive credentials not found.[/]\n"
            "Run [cyan]docent backup --setup[/] for setup instructions."
        )
        raise typer.Exit(1)

    with console.status("[green]Connecting to Google Drive…[/]"):
        service = get_service()
        folder_id = get_or_create_backup_folder(service)
        backups = _list(service, folder_id)

    if not backups:
        console.print("[yellow]No backups found in Google Drive.[/]")
        return

    # ── List ──────────────────────────────────────────────────────────────────
    if list_backups or not backup_id:
        from rich.table import Table

        t = Table(title="Docent Backups (Google Drive)", show_lines=True)
        t.add_column("#", style="dim", width=3)
        t.add_column("Name")
        t.add_column("Size", justify="right")
        t.add_column("Created")
        t.add_column("ID", style="dim")
        for i, b in enumerate(backups, 1):
            size = int(b.get("size", 0))
            size_str = f"{size / 1_048_576:.1f} MB" if size else "—"
            t.add_row(str(i), b["name"], size_str, b.get("createdTime", "")[:10], b["id"])
        console.print(t)
        if list_backups:
            console.print("[dim]Use --id <ID> to restore a specific backup.[/]")
            return
        # Default: offer to restore the latest
        backup_id = backups[0]["id"]
        bname = backups[0]["name"]
        console.print(f"\nLatest backup: [cyan]{bname}[/]")

    # Find the chosen backup
    chosen = next((b for b in backups if b["id"] == backup_id), None)
    if not chosen:
        console.print(f"[red]Backup ID not found:[/] {backup_id}")
        raise typer.Exit(1)

    # ── Download + restore ────────────────────────────────────────────────────
    tmp = Path(tempfile.mkdtemp()) / chosen["name"]
    try:
        with console.status(f"[green]Downloading {chosen['name']}…[/]"):
            download_backup(service, chosen["id"], tmp)
        _do_restore(console, tmp, yes)
    finally:
        tmp.unlink(missing_ok=True)


def _do_restore(console, archive: Path, yes: bool) -> None:
    """Shared restore logic used by both Drive and local restore paths."""
    from docent.bundled_plugins.backup.manager import read_manifest, restore_archive

    manifest = read_manifest(archive)
    ts = manifest.get("timestamp", "unknown")[:19].replace("T", " ")
    version = manifest.get("docent_version", "?")
    n_files = manifest.get("files_included", "?")

    console.print(
        f"\n[bold]Backup details[/]\n"
        f"  Created:   {ts}\n"
        f"  Version:   {version}\n"
        f"  Files:     {n_files}\n"
    )

    if not yes:
        confirm = typer.confirm("This will overwrite your current Docent state. Continue?")
        if not confirm:
            console.print("[yellow]Restore cancelled.[/]")
            raise typer.Exit(0)

    with console.status("[green]Restoring…[/]"):
        restore_archive(archive)

    console.print("[green]✓ Restore complete.[/] Restart 'docent ui' to apply changes.")


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
        lambda: (
            "Python",
            "OK",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "-",
        ),
        lambda: _check_cli_tool(
            "uv",
            ["uv", "--version"],
            "Install uv: https://docs.astral.sh/uv/",
            github_repo="astral-sh/uv",
            upgrade_cmd="uv self update",
        ),
        lambda: _check_cli_tool(
            "Node.js", ["node", "--version"], "Install Node.js: https://nodejs.org"
        ),
        lambda: _check_cli_tool("npm", ["npm", "--version"], "Install npm: https://nodejs.org"),
        lambda: _check_feynman(settings),
        lambda: _check_opencode(settings),
        lambda: _check_mendeley_mcp(settings),
        lambda: _check_zotero(settings),
        lambda: _check_tavily(settings),
        lambda: _check_semantic_scholar(settings),
        lambda: _check_alphaxiv(settings),
        lambda: _check_notebooklm_py(),
        lambda: _check_reading_db(settings),
        lambda: _check_litellm_provider(
            "Groq",
            settings.research.groq_api_key,
            "GROQ_API_KEY",
            "docent studio config-set --key groq_api_key --value YOUR_KEY",
        ),
        lambda: _check_google_drive(),
        # Archived backends (gemini, openrouter, mistral, cerebras) — not checked
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
        console.print(
            f"\n[yellow]{issues} {noun} found.[/]  Run [cyan]docent setup[/] to configure missing items."
        )

    # Offer to install missing CLI tools (feynman, mendeley-mcp only).
    installable = _collect_install_offers(checks)
    if installable:
        import shutil
        import subprocess as _sp

        console.print()
        for name, cmd, note in installable:
            runner = shutil.which(cmd[0])
            if runner is None:
                console.print(
                    f"[dim]  {name}: {cmd[0]} not on PATH, install manually: {' '.join(cmd)}[/]"
                )
                continue
            if typer.confirm(f"  Install {name} ({note})  via: {' '.join(cmd)}?", default=False):
                console.print(f"  Running: {' '.join(cmd)} ...")
                result = _sp.run([runner] + cmd[1:], check=False)
                if result.returncode == 0:
                    console.print(
                        f"  [green]{name} installed.[/]  Re-run [cyan]docent doctor[/] to verify."
                    )
                else:
                    console.print(
                        f"  [red]{name} install failed (exit {result.returncode}).[/]  Run manually: {' '.join(cmd)}"
                    )


@app.command("setup", help="Interactive setup: profile, database folder, and API keys.")
def setup_command() -> None:
    """Configure Docent interactively. Safe to re-run - existing values shown as defaults."""
    _run_setup_flow(first_run=False)


if __name__ == "__main__":
    app()

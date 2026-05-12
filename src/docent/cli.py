from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Any, Callable

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
from docent.config import load_settings, write_setting
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

_DOCENT_DIR = Path.home() / ".docent"
_USER_FILE = _DOCENT_DIR / "user.json"
_LEVEL_CHOICES = ["Undergraduate", "Masters", "PhD", "Postdoc", "Faculty", "Other"]


def _run_onboarding() -> None:
    """Prompt for user profile on first run; skip silently in non-TTY contexts."""
    if not sys.stdin.isatty():
        return

    # Check whether onboarding is needed
    if _USER_FILE.exists():
        try:
            data = json.loads(_USER_FILE.read_text(encoding="utf-8"))
            name = (data.get("name") or "").strip()
            if name and name != "You":
                return  # Already set up
        except (json.JSONDecodeError, OSError):
            pass  # Corrupt file — re-run onboarding

    console = get_console()
    console.print(
        "\n[bold cyan]Welcome to Docent![/] Let's get you set up quickly.\n"
    )

    name = typer.prompt("Your name").strip()
    program = typer.prompt("Your program / field of study").strip()

    # Show numbered choices for academic level
    console.print("Academic level:")
    for i, choice in enumerate(_LEVEL_CHOICES, 1):
        console.print(f"  [dim]{i}.[/] {choice}")

    level: str = ""
    while not level:
        raw = typer.prompt("Enter number or name").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(_LEVEL_CHOICES):
                level = _LEVEL_CHOICES[idx]
            else:
                console.print(f"[yellow]Please enter a number between 1 and {len(_LEVEL_CHOICES)}.[/]")
        elif raw.title() in _LEVEL_CHOICES:
            level = raw.title()
        elif raw in _LEVEL_CHOICES:
            level = raw
        else:
            console.print(f"[yellow]Not recognised. Choose a number 1–{len(_LEVEL_CHOICES)} or type the level.[/]")

    # Optional: database folder
    console.print("\n[dim]Where do you keep your PDFs? (press Enter to skip)[/]")
    db_dir_raw = typer.prompt("Papers folder", default="", show_default=False).strip()

    _DOCENT_DIR.mkdir(parents=True, exist_ok=True)
    profile = {"name": name, "program": program, "level": level}
    _USER_FILE.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    if db_dir_raw:
        try:
            write_setting("reading.database_dir", db_dir_raw)
            console.print(f"[dim]Database folder set to [cyan]{db_dir_raw}[/].[/]")
        except Exception:
            console.print("[yellow]Could not save database folder — set it later with: docent reading config-set --key database_dir --value <path>[/]")

    console.print(
        f"\n[bold green]All set, {name}![/] Your profile has been saved. "
        "Run [cyan]docent --help[/] to see what's available.\n"
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
    _run_onboarding()

    ctx.obj = Context(settings=settings, llm=LLMClient(settings), executor=Executor())
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
        ctx: typer.Context = kwargs.pop("ctx")
        inputs = schema(**kwargs)
        context: Context = ctx.obj
        if preflight is not None:
            preflight(inputs, context)
        maybe = invoke(inputs, context)
        result = _drive_progress(maybe) if inspect.isgenerator(maybe) else maybe
        if result is not None:
            get_console().print(result)

    params = [
        inspect.Parameter("ctx", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=typer.Context),
    ]
    annotations: dict[str, Any] = {"ctx": typer.Context}

    for fname, finfo in schema.model_fields.items():
        cli_flag = "--" + fname.replace("_", "-")
        help_text = finfo.description or ""
        option_default = ... if finfo.is_required() else finfo.default
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


if __name__ == "__main__":
    app()

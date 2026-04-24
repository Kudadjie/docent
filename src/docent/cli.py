from __future__ import annotations

import inspect
from typing import Any

import typer
from rich import box
from rich.panel import Panel
from rich.table import Table

from docent import __version__
from docent.config import load_settings
from docent.core import Context, Tool, all_tools
from docent.tools import discover_tools
from docent.ui import configure_console, get_console

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

    ctx.obj = Context(settings=settings)


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
            table.add_row(tc.name, tc.description)
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
        "",
        "[bold]Inputs:[/]",
    ]
    for fname, finfo in tool_cls.input_schema.model_fields.items():
        status = "(required)" if finfo.is_required() else f"(default={finfo.default!r})"
        annot = getattr(finfo.annotation, "__name__", str(finfo.annotation))
        desc = f" - {finfo.description}" if finfo.description else ""
        lines.append(f"  --{fname.replace('_', '-')}: {annot} {status}{desc}")

    console.print(Panel("\n".join(lines), title=tool_cls.name, border_style="cyan"))


def _make_tool_command(tool_cls: type[Tool]) -> Any:
    """Build a Typer callback for a registered tool, mapping each Pydantic field to a --flag."""
    schema = tool_cls.input_schema

    def callback(**kwargs: Any) -> None:
        ctx: typer.Context = kwargs.pop("ctx")
        inputs = schema(**kwargs)
        context: Context = ctx.obj
        result = tool_cls().run(inputs, context)
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
    callback.__name__ = tool_cls.name.replace("-", "_")
    callback.__doc__ = tool_cls.description
    return callback


discover_tools()
for _tool_cls in all_tools().values():
    app.command(name=_tool_cls.name, help=_tool_cls.description)(_make_tool_command(_tool_cls))


if __name__ == "__main__":
    app()

from __future__ import annotations

import inspect
from typing import Any, Callable

import typer
from pydantic import BaseModel
from rich import box
from rich.panel import Panel
from rich.table import Table

from docent import __version__
from docent.config import load_settings
from docent.core import Context, Tool, all_tools, collect_actions
from docent.execution import Executor
from docent.llm import LLMClient
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

    ctx.obj = Context(settings=settings, llm=LLMClient(settings), executor=Executor())


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


def _build_callback(
    schema: type[BaseModel],
    invoke: Callable[[BaseModel, Context], Any],
    name: str,
    doc: str,
) -> Any:
    """Build a Typer callback with a synthesized signature from a Pydantic schema.

    `invoke(inputs, context)` is called with validated inputs and the Context
    from `ctx.obj`. Its return value (if not None) is printed via the CLI's
    console singleton.
    """

    def callback(**kwargs: Any) -> None:
        ctx: typer.Context = kwargs.pop("ctx")
        inputs = schema(**kwargs)
        context: Context = ctx.obj
        result = invoke(inputs, context)
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
        )
        subapp.command(name=cli_name, help=meta.description)(callback)
    app.add_typer(subapp, name=tool_cls.name, help=tool_cls.description)


discover_tools()
for _tool_cls in all_tools().values():
    _register_tool_in_app(_tool_cls)


if __name__ == "__main__":
    app()

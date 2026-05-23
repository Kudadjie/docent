from __future__ import annotations

from rich.console import Console

from docent.ui.theme import docent_theme

_console: Console | None = None


def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(theme=docent_theme)
    return _console


def configure_console(*, no_color: bool = False, quiet: bool = False, stderr: bool = False) -> Console:
    """Replace the singleton with one matching the given flags.

    Called once from the CLI root callback, after parsing global flags.
    Pass ``stderr=True`` when running as an MCP stdio server so that all
    Rich output goes to stderr and stdout stays clean for JSON-RPC.
    """
    global _console
    _console = Console(
        theme=docent_theme,
        no_color=no_color,
        quiet=quiet,
        stderr=stderr,
    )
    return _console

"""Minimal interactive prompt utilities.

Single function for now: `prompt_for_path`. The escape-hatch convention is the
`DOCENT_NO_INTERACTIVE` env var - when set to anything truthy, prompts raise
`NoInteractiveError` immediately so CI / scripted use never blocks waiting on
stdin. Tools that prompt should always have an env-var or flag-based path that
bypasses the prompt entirely.
"""
from __future__ import annotations

import os
from pathlib import Path

from rich.prompt import Prompt

from docent.ui import get_console


_NO_INTERACTIVE_ENV = "DOCENT_NO_INTERACTIVE"


class NoInteractiveError(RuntimeError):
    """Raised when an interactive prompt is required but DOCENT_NO_INTERACTIVE is set.

    Carries the prompt text so callers can format a clear "set X env var or
    pass --flag" remediation hint.
    """

    def __init__(self, prompt_text: str):
        super().__init__(
            f"Interactive prompt required but {_NO_INTERACTIVE_ENV} is set: {prompt_text!r}"
        )
        self.prompt_text = prompt_text


def _no_interactive() -> bool:
    val = os.environ.get(_NO_INTERACTIVE_ENV, "").strip().lower()
    return val not in ("", "0", "false", "no")


def prompt_for_path(message: str, *, allow_create: bool = True, default: str | None = None) -> Path | None:
    """Ask the user for a directory path, with `~` expansion.

    Returns the resolved Path on success, or None if the user types 'cancel'.
    If `allow_create` is True, the user can type 'create' to scaffold the
    default location.
    Raises `NoInteractiveError` if `DOCENT_NO_INTERACTIVE` is set.
    """
    if _no_interactive():
        raise NoInteractiveError(message)

    console = get_console()
    raw = Prompt.ask(message, default=default or "", console=console).strip()
    if not raw or raw.lower() == "cancel":
        return None
    if allow_create and raw.lower() == "create" and default:
        path = Path(default).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path
    return Path(raw).expanduser()

from __future__ import annotations


class ConfirmationRequired(Exception):
    """Raised by a preflight in MCP mode when user confirmation is needed.

    Contains all the information the CLI would have printed/prompted for,
    serialised as plain-text notes so the MCP caller can present them to
    the user and retry with ``confirmed=True``.
    """

    def __init__(self, notes: list[str]) -> None:
        self.notes = notes
        super().__init__("User confirmation required before this action can proceed.")

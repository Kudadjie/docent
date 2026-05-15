"""Docent error hierarchy with D-series codes for user-facing display.

Every public error class carries a ``code`` class variable (e.g. "D002") and a
``formatted()`` method that returns "[Dxxx] message  (CauseType: cause)".

The CLI catches ``DocentError`` in the action callback and renders it as a
clean one-liner instead of a traceback.
"""
from __future__ import annotations

from typing import ClassVar


class DocentError(RuntimeError):
    """Base class for all user-facing Docent errors."""

    code: ClassVar[str] = "D000"

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause

    def formatted(self) -> str:
        """Return '[Dxxx] message  (CauseType: detail)' for display."""
        msg = f"[{self.code}] {self}"
        if self.cause:
            cause_str = str(self.cause)
            if cause_str and cause_str not in str(self):
                msg += f"  ({type(self.cause).__name__}: {cause_str})"
        return msg


class ConfigMissingError(DocentError):
    """Required configuration key not set."""
    code: ClassVar[str] = "D001"


class ToolNotFoundError(DocentError):
    """External tool or binary not found on PATH."""
    code: ClassVar[str] = "D002"


class AuthError(DocentError):
    """API key invalid or authentication failed."""
    code: ClassVar[str] = "D003"


class UsageLimitError(DocentError):
    """Usage quota or budget exhausted."""
    code: ClassVar[str] = "D004"


class SubprocessError(DocentError):
    """External command failed or timed out."""
    code: ClassVar[str] = "D005"


class ResourceNotFoundError(DocentError):
    """Expected file or directory does not exist."""
    code: ClassVar[str] = "D006"


class ServiceUnavailableError(DocentError):
    """External service not reachable."""
    code: ClassVar[str] = "D007"

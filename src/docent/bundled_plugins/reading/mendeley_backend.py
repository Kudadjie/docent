"""Mendeley reference manager backend.

Wraps ``mendeley_client`` so ``ref_sync`` can call it through the
``ReferenceManagerBackend`` protocol without importing Mendeley directly.
"""

from __future__ import annotations

from typing import Any


class MendeleyBackend:
    """Implements ``ReferenceManagerBackend`` for Mendeley via mendeley-mcp."""

    def __init__(self, launch_command: list[str] | None = None) -> None:
        self._cmd = launch_command

    def get_name(self) -> str:
        return "Mendeley"

    def list_folders(self) -> dict[str, Any]:
        from .mendeley_client import list_folders

        return list_folders(self._cmd)

    def list_documents(self, folder_id: str) -> dict[str, Any]:
        from .mendeley_client import list_documents

        return list_documents(folder_id=folder_id, launch_command=self._cmd)

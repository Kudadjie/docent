"""Protocol for reference manager backends (Mendeley, Zotero, etc.)."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ReferenceManagerBackend(Protocol):
    """Defines the interface a reference manager backend must implement.

    Any class that provides these three methods is a valid backend — no
    explicit subclassing required.
    """

    def get_name(self) -> str:
        """Return the display name of this backend, e.g. 'Mendeley'."""
        ...

    def list_folders(self) -> dict[str, Any]:
        """Return folder/collection data.

        Expected keys in the returned dict:
        - ``items``: list of folder dicts, each with at least ``id`` and ``name``.
        - ``error`` (optional): non-empty string if the call failed.
        """
        ...

    def list_documents(self, folder_id: str) -> dict[str, Any]:
        """Return documents inside *folder_id*.

        Expected keys in the returned dict:
        - ``items``: list of document dicts.
        - ``error`` (optional): non-empty string if the call failed.
        - ``maybe_truncated`` (optional): bool, True if results were capped.
        """
        ...

"""Zotero Web API client — thin wrappers over ``pyzotero``.

Unlike the Mendeley client (which spawns an MCP subprocess that owns OAuth),
Zotero uses a simple API key — no browser flow, no subprocess. ``pyzotero``
handles pagination and HTTP; these wrappers just fetch and normalise the
result into the same ``{"items": list, "error": str | None}`` shape the
reference-manager sync engine expects, so error bucketing (auth/transport)
is uniform across backends.

``pyzotero`` is lazy-imported so importing this module stays cheap and the
dependency is only required when the Zotero backend is actually used.
"""

from __future__ import annotations

from typing import Any


def make_zotero(api_key: str, library_id: str, library_type: str = "user") -> Any:
    """Construct a pyzotero client. Raises ImportError if pyzotero is missing."""
    from pyzotero import zotero

    return zotero.Zotero(library_id, library_type, api_key)


def _classify_error(exc: Exception) -> str:
    """Map a pyzotero/HTTP error to an 'auth:' or 'transport:' prefix.

    Mirrors mendeley_client._classify_error so the sync engine's
    `error.startswith("auth:")` bucketing works for both backends.
    """
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    blob = f"{name} {msg}"
    if any(
        s in blob
        for s in (
            "notauthor",
            "unauthor",
            "forbidden",
            "401",
            "403",
            "api key",
            "apikey",
            "invalid key",
        )
    ):
        return "auth"
    return "transport"


def list_collections(zot: Any) -> dict[str, Any]:
    """Fetch all collections. Returns ``{"items": [...], "error": None}``.

    Each item is a raw Zotero collection dict (``{"key", "data": {...}}``);
    the backend maps it to the canonical ``{id, name, parent_id}`` shape.
    """
    try:
        # everything() paginates past the per-request cap so large libraries
        # don't silently truncate the collection list.
        items = zot.everything(zot.collections())
    except Exception as exc:  # noqa: BLE001 — uniform error surface for the sync engine
        return {"items": [], "error": f"{_classify_error(exc)}: {exc}", "maybe_truncated": False}
    return {"items": items, "error": None, "maybe_truncated": False}


def list_items(zot: Any, collection_key: str) -> dict[str, Any]:
    """Fetch top-level items in a collection (excludes child notes/attachments).

    Returns ``{"items": [...], "error": None}`` with raw Zotero item dicts.
    Not recursive — the sync engine walks sub-collections itself.
    """
    try:
        items = zot.everything(zot.collection_items_top(collection_key))
    except Exception as exc:  # noqa: BLE001
        return {"items": [], "error": f"{_classify_error(exc)}: {exc}", "maybe_truncated": False}
    return {"items": items, "error": None, "maybe_truncated": False}

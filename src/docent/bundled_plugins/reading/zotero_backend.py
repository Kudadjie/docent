"""Zotero reference manager backend.

Implements ``ReferenceManagerBackend`` over the Zotero Web API (pyzotero),
mapping Zotero's data model onto the same canonical folder/document shapes the
Mendeley backend produces — so the backend-agnostic ``sync_from_mendeley_run``
engine and ``build_entry_from_mendeley`` mapper work unchanged.

Canonical shapes the sync engine expects:
- folder:   ``{"id", "name", "parent_id"}``
- document: ``{"id", "title", "authors": [...], "year": int|None,
              "identifiers": {"doi": ...}, "type": str}``
"""

from __future__ import annotations

import re
from typing import Any

# Zotero itemType -> the doc "type" strings build_entry_from_mendeley understands.
# It maps book->book, book_section->book_chapter, edited_book->book, else paper.
_ITEM_TYPE_MAP = {
    "book": "book",
    "bookSection": "book_section",
}

# Zotero item types that are not standalone documents — skip them defensively
# (collection_items_top already excludes child notes/attachments, but a
# standalone note/attachment can still be a top-level collection member).
_SKIP_ITEM_TYPES = {"attachment", "note", "annotation"}

_YEAR_RE = re.compile(r"\b(\d{4})\b")


class ZoteroBackend:
    """Implements ``ReferenceManagerBackend`` for Zotero via pyzotero.

    Pass an explicit ``client`` (a pyzotero ``Zotero`` instance) to inject a
    fake in tests; otherwise it is built lazily from the API credentials.
    """

    def __init__(
        self,
        api_key: str | None,
        library_id: str | None,
        library_type: str = "user",
        client: Any = None,
    ) -> None:
        self._api_key = api_key
        self._library_id = library_id
        self._library_type = library_type or "user"
        self._client = client

    def get_name(self) -> str:
        return "Zotero"

    # -- client ------------------------------------------------------------

    def _zot(self) -> dict[str, Any] | Any:
        """Return the pyzotero client, or an error dict if it can't be built."""
        if self._client is not None:
            return self._client
        if not self._api_key or not self._library_id:
            return {
                "error": (
                    "auth: Zotero not configured — set reading.zotero_api_key and "
                    "reading.zotero_library_id (get them at zotero.org/settings/keys)."
                )
            }
        try:
            from .zotero_client import make_zotero

            self._client = make_zotero(self._api_key, self._library_id, self._library_type)
        except ImportError:
            return {
                "error": (
                    "transport: pyzotero is not installed — run `pip install pyzotero` "
                    "or `uv tool install --with pyzotero docent-cli`."
                )
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": f"transport: could not init Zotero client: {exc}"}
        return self._client

    # -- protocol ----------------------------------------------------------

    def list_folders(self) -> dict[str, Any]:
        zot = self._zot()
        if isinstance(zot, dict) and zot.get("error"):
            return {"items": [], "error": zot["error"], "maybe_truncated": False}
        from .zotero_client import list_collections

        resp = list_collections(zot)
        if resp.get("error"):
            return resp
        return {
            "items": [self._map_collection(c) for c in resp["items"] if isinstance(c, dict)],
            "error": None,
            "maybe_truncated": False,
        }

    def list_documents(self, folder_id: str) -> dict[str, Any]:
        zot = self._zot()
        if isinstance(zot, dict) and zot.get("error"):
            return {"items": [], "error": zot["error"], "maybe_truncated": False}
        from .zotero_client import list_items

        resp = list_items(zot, folder_id)
        if resp.get("error"):
            return resp
        docs = []
        for item in resp["items"]:
            if not isinstance(item, dict):
                continue
            data = item.get("data") or {}
            if data.get("itemType") in _SKIP_ITEM_TYPES:
                continue
            docs.append(self._map_item(item))
        return {"items": docs, "error": None, "maybe_truncated": False}

    # -- field mapping -----------------------------------------------------

    @staticmethod
    def _map_collection(coll: dict[str, Any]) -> dict[str, Any]:
        data = coll.get("data") or {}
        parent = data.get("parentCollection")
        # Zotero uses False for top-level collections; normalise to None.
        parent_id = parent if isinstance(parent, str) and parent else None
        return {
            "id": coll.get("key") or data.get("key") or "",
            "name": data.get("name") or "",
            "parent_id": parent_id,
        }

    @classmethod
    def _map_item(cls, item: dict[str, Any]) -> dict[str, Any]:
        data = item.get("data") or {}
        doi = data.get("DOI")
        return {
            "id": item.get("key") or data.get("key") or "",
            "title": (data.get("title") or "").strip(),
            "authors": cls._map_creators(data.get("creators")),
            "year": cls._parse_year(data.get("date")),
            "identifiers": {"doi": doi.strip()} if isinstance(doi, str) and doi.strip() else {},
            "type": _ITEM_TYPE_MAP.get(data.get("itemType", ""), "paper"),
        }

    @staticmethod
    def _map_creators(creators: Any) -> list[dict[str, str] | str]:
        """Zotero creators -> the {first_name, last_name} dicts (or plain
        strings for single-field/institutional names) that
        normalize_mendeley_authors already understands."""
        out: list[dict[str, str] | str] = []
        if not isinstance(creators, list):
            return out
        for c in creators:
            if not isinstance(c, dict):
                continue
            # Prefer authors; if an item has none, fall back to whatever creators exist.
            first = c.get("firstName", "")
            last = c.get("lastName", "")
            if first or last:
                out.append({"first_name": first, "last_name": last})
            elif c.get("name"):  # institutional / single-field creator
                out.append(str(c["name"]))
        return out

    @staticmethod
    def _parse_year(date: Any) -> int | None:
        if not isinstance(date, str):
            return None
        m = _YEAR_RE.search(date)
        return int(m.group(1)) if m else None

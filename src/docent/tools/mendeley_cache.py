"""File-backed read-through cache for Mendeley collection metadata.

Step 11.7. Wraps `mendeley_list_documents(folder_id)` only — `get_document`
isn't wrapped yet because no reader needs the fields it adds (abstract,
attachments) and the bulk list call already covers title/authors/year/doi.

Cache file: `<cache_dir>/paper/mendeley_collection.json`.

  {
    "<folder_id>": {
      "fetched_at": <unix_ts>,
      "docs": {"<mendeley_id>": <doc>, ...}
    },
    ...
  }

Across-CLI persistence is the whole point: each `docent paper next` is a
fresh Python process, and a 5-minute TTL only delivers the promised
"feels instant" UX if it survives process exits. `sync-from-mendeley`
calls `invalidate()` after writing the queue so the next reader pulls
fresh data.

On MCP transport / auth error the cache returns `None` — callers fall
back to the snapshot fields persisted in queue.json by sync-from-mendeley.
A failed fetch is never written to disk.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from docent.tools.mendeley_client import list_documents as default_list_documents

DEFAULT_TTL_SECONDS = 300


class MendeleyCache:
    def __init__(
        self,
        cache_path: Path,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        list_documents: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self._path = cache_path
        self._ttl = ttl_seconds
        self._list_documents = list_documents or default_list_documents

    @property
    def path(self) -> Path:
        return self._path

    def get_collection(
        self,
        folder_id: str,
        launch_command: list[str] | None = None,
    ) -> dict[str, dict[str, Any]] | None:
        """Return `{mendeley_id: doc}` for the given folder, or None on
        transport/auth error. Reads from disk if fresh, otherwise calls
        `list_documents` and rewrites the cache file.
        """
        store = self._load()
        entry = store.get(folder_id)
        now = time.time()
        if entry and (now - entry.get("fetched_at", 0.0)) < self._ttl:
            docs = entry.get("docs")
            if isinstance(docs, dict):
                return docs

        resp = self._list_documents(folder_id=folder_id, launch_command=launch_command)
        if resp.get("error"):
            return None
        items = resp.get("items") or []
        docs = {mid: doc for doc in items if (mid := _doc_id(doc))}
        store[folder_id] = {"fetched_at": now, "docs": docs}
        self._save(store)
        return docs

    def invalidate(self, folder_id: str | None = None) -> None:
        """Drop one folder's entry, or the whole file if `folder_id` is None.
        Called by `sync-from-mendeley` after a successful write so the next
        reader pulls fresh data."""
        if folder_id is None:
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass
            return
        store = self._load()
        if folder_id in store:
            del store[folder_id]
            self._save(store)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Corrupt cache file: behave as if empty. Next write rewrites it.
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, store: dict[str, dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)


def _doc_id(doc: Any) -> str | None:
    """Mendeley docs may carry the id under `id` (library docs) or
    `catalog_id` (catalog hits via mendeley_get_by_doi). list_documents
    returns library docs, so `id` covers it; we accept `catalog_id` too
    in case a future caller mixes payloads."""
    if not isinstance(doc, dict):
        return None
    for key in ("id", "catalog_id"):
        v = doc.get(key)
        if isinstance(v, str) and v:
            return v
    return None

"""Mendeley sync — reconcile the reading queue with a Mendeley collection."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable, Generator

from docent.core import ProgressEvent
from .mendeley_cache import MendeleyCache
from .mendeley_client import (
    list_documents as mendeley_list_documents,
    list_folders as mendeley_list_folders,
)
from .models import QueueEntry, SyncFromMendeleyResult


def compute_category_path(folder_id: str, root_id: str, folder_map: dict[str, dict]) -> str | None:
    """Return 'ParentName/ChildName' path from root to folder_id (root excluded).
    Returns None when folder_id == root_id (doc is directly in the root collection)."""
    parts: list[str] = []
    cur = folder_id
    while cur and cur != root_id:
        f = folder_map.get(cur)
        if not f:
            break
        parts.insert(0, f.get("name", ""))
        cur = f.get("parent_id")
    return "/".join(parts) if parts else None


def extract_mendeley_id(item: dict[str, Any]) -> str | None:
    for key in ("id", "catalog_id", "document_id", "mendeley_id"):
        v = item.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def normalize_mendeley_authors(authors: Any) -> str:
    if isinstance(authors, list):
        parts: list[str] = []
        for a in authors:
            if isinstance(a, str) and a.strip():
                parts.append(a.strip())
            elif isinstance(a, dict):
                name = " ".join(filter(None, [a.get("first_name", ""), a.get("last_name", "")])).strip()
                if name:
                    parts.append(name)
        if parts:
            return "; ".join(parts)
    if isinstance(authors, str) and authors.strip():
        return authors.strip()
    return "Unknown"


def candidate_summary(item: dict[str, Any]) -> dict[str, str]:
    title = item.get("title") or ""
    year = item.get("year")
    authors = item.get("authors") or item.get("author") or ""
    if isinstance(authors, list):
        authors = ", ".join(
            " ".join(filter(None, [a.get("first_name", ""), a.get("last_name", "")])).strip()
            if isinstance(a, dict) else str(a)
            for a in authors[:3]
        )
    return {
        "mendeley_id": extract_mendeley_id(item) or "",
        "title": str(title),
        "year": str(year) if year is not None else "",
        "authors": str(authors),
    }


def mendeley_failure_hint(error: str) -> str:
    if error.startswith("auth:"):
        return f"{error} (run `mendeley-auth login` to refresh tokens)"
    if "launch command not found" in error:
        return f"{error} (install with `uv tool install mendeley-mcp` or set reading.mendeley_mcp_command)"
    return error


def derive_id(authors: str, year: int | None, title: str) -> str:
    first_chunk = authors.split(",")[0].split(";")[0].strip() if authors else ""
    first_word = first_chunk.split()[0] if first_chunk else "unknown"
    last_name = re.sub(r"[^a-zA-Z0-9]", "", first_word).lower() or "unknown"
    year_part = str(year) if year else "nd"
    first_title_word = title.split()[0] if title else "untitled"
    title_word = re.sub(r"[^a-zA-Z0-9]", "", first_title_word).lower() or "untitled"
    return f"{last_name}-{year_part}-{title_word}"


def build_entry_from_mendeley(
    doc: dict[str, Any],
    mendeley_id: str,
    taken_ids: set[str],
    order: int,
    category: str | None = None,
) -> QueueEntry:
    title = (doc.get("title") or "").strip() or "(untitled)"
    authors = normalize_mendeley_authors(doc.get("authors"))
    year = doc.get("year")
    if not isinstance(year, int):
        year = None
    doi: str | None = None
    idents = doc.get("identifiers")
    if isinstance(idents, dict):
        d = idents.get("doi")
        if isinstance(d, str) and d.strip():
            doi = d.strip()

    mendeley_type = (doc.get("type") or "").lower()
    entry_type = {
        "book": "book",
        "book_section": "book_chapter",
        "edited_book": "book",
    }.get(mendeley_type, "paper")

    base = derive_id(authors, year, title)
    entry_id = f"{base}-{mendeley_id[:8]}" if base in taken_ids else base

    return QueueEntry(
        id=entry_id,
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        type=entry_type,
        added=datetime.now().date().isoformat(),
        order=order,
        category=category,
        mendeley_id=mendeley_id,
    )


def sync_from_mendeley_run(
    store,
    collection_name: str,
    launch_command: list[str] | None,
    dry_run: bool,
    mendeley_cache: MendeleyCache,
    log_event: Callable[..., None],
) -> Generator[ProgressEvent, None, SyncFromMendeleyResult]:
    empty = SyncFromMendeleyResult(
        queue_collection=collection_name, folder_id=None,
        added=[], unchanged=[], removed=[], failed=[],
        dry_run_added=[], dry_run_removed=[], summary="",
    )

    yield ProgressEvent(phase="discover", message=f"Listing Mendeley folders to resolve {collection_name!r}.")
    folders_resp = mendeley_list_folders(launch_command)
    if folders_resp.get("error"):
        err = folders_resp["error"]
        return empty.model_copy(update={"message": (
            f"Could not list Mendeley folders: {mendeley_failure_hint(err)}"
        )})
    folders = folders_resp.get("items") or []
    matches = [f for f in folders if isinstance(f, dict) and f.get("name") == collection_name]
    if not matches:
        return empty.model_copy(update={"message": (
            f"Mendeley collection {collection_name!r} not found. "
            f"Create a collection named {collection_name!r} in the Mendeley desktop app, "
            f"drag the papers you want to read into it, then re-run. "
            f"(Or change the configured name with "
            f"`docent reading config-set queue_collection <name>`.)"
        )})
    if len(matches) > 1:
        return empty.model_copy(update={"message": (
            f"Found {len(matches)} Mendeley collections named {collection_name!r}. "
            f"Rename one in Mendeley, or change `reading.queue_collection` to a unique name."
        )})
    folder_id = matches[0].get("id")
    if not isinstance(folder_id, str) or not folder_id:
        return empty.model_copy(update={"message": (
            f"Mendeley collection {collection_name!r} has no usable id; "
            f"try toggling its name in Mendeley to refresh."
        )})

    # Build folder map + discover sub-collection hierarchy.
    folder_map: dict[str, dict] = {f["id"]: f for f in folders if isinstance(f, dict) and f.get("id")}
    children: dict[str, list[str]] = {}
    for f in folders:
        if isinstance(f, dict):
            pid = f.get("parent_id")
            if pid:
                children.setdefault(pid, []).append(f["id"])

    # BFS from root to collect all descendant sub-folder ids.
    sub_folder_ids: list[str] = []
    bfs: list[str] = list(children.get(folder_id, []))
    while bfs:
        fid = bfs.pop(0)
        sub_folder_ids.append(fid)
        bfs.extend(children.get(fid, []))

    # Fetch docs from root (fatal if fails), then each sub-folder (non-fatal).
    yield ProgressEvent(phase="discover", message=f"Reading collection {collection_name!r} ({folder_id[:8]}…).")
    docs_resp = mendeley_list_documents(folder_id=folder_id, launch_command=launch_command)
    if docs_resp.get("error"):
        err = docs_resp["error"]
        return empty.model_copy(update={
            "folder_id": folder_id,
            "message": f"Could not list documents in {collection_name!r}: {mendeley_failure_hint(err)}",
        })

    # doc_with_category: {mendeley_id: (doc, category_path)} — deepest path wins.
    doc_with_category: dict[str, tuple[dict, str | None]] = {}
    _no_id_failed: list[dict[str, str]] = []

    for doc in [d for d in (docs_resp.get("items") or []) if isinstance(d, dict)]:
        mid = extract_mendeley_id(doc)
        if mid:
            doc_with_category[mid] = (doc, None)  # None = directly in root
        else:
            _no_id_failed.append({"mendeley_id": "", "error": "doc has no usable id"})

    for sfid in sub_folder_ids:
        sf_name = folder_map.get(sfid, {}).get("name", sfid)
        cat_path = compute_category_path(sfid, folder_id, folder_map)
        yield ProgressEvent(phase="discover", message=f"Reading sub-collection {sf_name!r}…")
        sf_resp = mendeley_list_documents(folder_id=sfid, launch_command=launch_command)
        if sf_resp.get("error"):
            yield ProgressEvent(phase="discover", level="warn",
                                message=f"Could not read '{sf_name}': {sf_resp['error']}")
            continue
        for doc in [d for d in (sf_resp.get("items") or []) if isinstance(d, dict)]:
            mid = extract_mendeley_id(doc)
            if not mid:
                continue  # already captured from root fetch if it appeared there
            existing = doc_with_category.get(mid)
            if existing is None:
                doc_with_category[mid] = (doc, cat_path)
            else:
                _, existing_path = existing
                existing_depth = len(existing_path.split("/")) if existing_path else 0
                new_depth = len(cat_path.split("/")) if cat_path else 0
                if new_depth > existing_depth:
                    doc_with_category[mid] = (doc, cat_path)

    docs_to_process = list(doc_with_category.items())
    yield ProgressEvent(phase="discover", message=f"Found {len(docs_to_process)} doc(s) total.")

    added: list[dict[str, str]] = []
    unchanged: list[str] = []
    removed: list[str] = []
    failed: list[dict[str, str]] = list(_no_id_failed)
    dry_run_added: list[dict[str, str]] = []
    dry_run_removed: list[str] = []
    category_updates: dict[str, str | None] = {}  # entry_id -> new category

    queue = store.load_queue()
    by_mendeley_id: dict[str, dict[str, Any]] = {
        e["mendeley_id"]: e for e in queue if e.get("mendeley_id")
    }
    existing_ids: set[str] = {e.get("id") for e in queue if e.get("id")}
    reserved_ids: set[str] = set()
    in_collection: set[str] = set()
    new_entries: list[dict[str, Any]] = []
    max_order = max((e.get("order", 0) for e in queue), default=0)

    for i, (mid, (doc, category)) in enumerate(docs_to_process, 1):
        in_collection.add(mid)
        yield ProgressEvent(phase="reconcile", current=i, total=len(docs_to_process), item=doc.get("title", mid)[:60])

        if mid in by_mendeley_id:
            existing_entry = by_mendeley_id[mid]
            eid = existing_entry.get("id") or mid
            if existing_entry.get("category") != category:
                category_updates[eid] = category
            unchanged.append(eid)
            continue

        try:
            max_order += 1
            entry = build_entry_from_mendeley(doc, mid, existing_ids | reserved_ids, max_order, category=category)
        except Exception as e:  # noqa: BLE001
            failed.append({"mendeley_id": mid, "error": str(e)})
            yield ProgressEvent(phase="reconcile", level="error", message=f"{mid[:8]}: {e}")
            continue

        reserved_ids.add(entry.id)
        if dry_run:
            dry_run_added.append({"id": entry.id, "mendeley_id": mid, "title": entry.title})
        else:
            new_entries.append(entry.model_dump())
            added.append({"id": entry.id, "mendeley_id": mid, "title": entry.title})

    for e in queue:
        mid = e.get("mendeley_id")
        if not mid or mid in in_collection:
            continue
        if e.get("status") == "removed":
            continue
        if dry_run:
            dry_run_removed.append(e.get("id", mid))
        else:
            removed.append(e.get("id", mid))

    if not dry_run and (new_entries or removed or category_updates):
        queue = store.load_queue()
        by_id = {e.get("id"): e for e in queue}
        for ne in new_entries:
            if ne["id"] not in by_id:
                queue.append(ne)
        removed_set = set(removed)
        for e in queue:
            eid = e.get("id")
            if eid in removed_set:
                e["status"] = "removed"
            if eid in category_updates:
                e["category"] = category_updates[eid]
        store.save_queue(queue)

    if not dry_run:
        mendeley_cache.invalidate(folder_id)

    log_event(
        "sync_from_mendeley",
        collection=collection_name,
        folder_id=folder_id,
        in_collection=len(in_collection),
        added=len(added),
        unchanged=len(unchanged),
        removed=len(removed),
        failed=len(failed),
        dry_run=dry_run,
    )

    summary = (
        f"{len(added)} added, {len(unchanged)} unchanged, "
        f"{len(removed)} removed, {len(failed)} failed"
        + (
            f", {len(dry_run_added)} would-add, {len(dry_run_removed)} would-remove (dry-run)"
            if dry_run else ""
        )
        + "."
    )
    if any("auth:" in f.get("error", "") for f in failed):
        summary += " Auth failure detected — run `mendeley-auth login` and retry."

    return SyncFromMendeleyResult(
        queue_collection=collection_name,
        folder_id=folder_id,
        added=added,
        unchanged=unchanged,
        removed=removed,
        failed=failed,
        dry_run_added=dry_run_added,
        dry_run_removed=dry_run_removed,
        summary=summary,
    )

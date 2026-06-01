"""Reference-manager sync — reconcile the reading queue with a collection.

``sync_from_mendeley_run`` is now backend-agnostic: it accepts any object
that satisfies the ``ReferenceManagerBackend`` protocol so Zotero (or any
other manager) can be plugged in without touching this file.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Generator
from datetime import datetime
from typing import Any, Literal, cast

from docent.core import ProgressEvent

from .mendeley_cache import MendeleyCache
from .models import QueueEntry, SyncFromLibraryResult
from .ref_manager import ReferenceManagerBackend


def compute_category_path(folder_id: str, root_id: str, folder_map: dict[str, dict]) -> str | None:
    """Return 'ParentName/ChildName' path from root to folder_id (root excluded).
    Returns None when folder_id == root_id (doc is directly in the root collection)."""
    parts: list[str] = []
    cur: str | None = folder_id
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
                name = " ".join(
                    filter(None, [a.get("first_name", ""), a.get("last_name", "")])
                ).strip()
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
            if isinstance(a, dict)
            else str(a)
            for a in authors[:3]
        )
    return {
        "mendeley_id": extract_mendeley_id(item) or "",
        "title": str(title),
        "year": str(year) if year is not None else "",
        "authors": str(authors),
    }


def mendeley_failure_hint(error: str, backend_name: str = "Mendeley") -> str:
    # Mendeley errors get MCP-specific remediation; other backends (Zotero)
    # already return self-describing errors, so leave them as-is.
    if backend_name == "Mendeley":
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
    _type_map: dict[str, str] = {
        "book": "book",
        "book_section": "book_chapter",
        "edited_book": "book",
    }
    entry_type = cast(
        "Literal['paper', 'book', 'book_chapter']",
        _type_map.get(mendeley_type, "paper"),
    )

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
        reference_id=mendeley_id,
    )


def sync_from_mendeley_run(
    store,
    collection_name: str,
    backend: ReferenceManagerBackend,
    dry_run: bool,
    mendeley_cache: MendeleyCache,
    log_event: Callable[..., None],
) -> Generator[ProgressEvent, None, SyncFromLibraryResult]:
    empty = SyncFromLibraryResult(
        queue_collection=collection_name,
        folder_id=None,
        added=[],
        unchanged=[],
        flagged=[],
        cleared=[],
        removed=[],
        failed=[],
        dry_run_added=[],
        dry_run_removed=[],
        summary="",
    )
    backend_name = backend.get_name()

    yield ProgressEvent(
        phase="discover", message=f"Listing {backend_name} folders to resolve {collection_name!r}."
    )
    folders_resp = backend.list_folders()
    if folders_resp.get("error"):
        err = folders_resp["error"]
        return empty.model_copy(
            update={
                "message": (
                    f"Could not list {backend_name} folders: {mendeley_failure_hint(err, backend_name)}"
                )
            }
        )
    folders = folders_resp.get("items") or []
    matches = [f for f in folders if isinstance(f, dict) and f.get("name") == collection_name]
    if not matches:
        return empty.model_copy(
            update={
                "message": (
                    f"{backend_name} collection {collection_name!r} not found. "
                    f"Create a collection named {collection_name!r} in {backend_name}, "
                    f"add the papers you want to read to it, then re-run. "
                    f"(Or change the configured name with "
                    f"`docent reading config-set queue_collection <name>`.)"
                )
            }
        )
    if len(matches) > 1:
        return empty.model_copy(
            update={
                "message": (
                    f"Found {len(matches)} {backend_name} collections named {collection_name!r}. "
                    f"Rename one in {backend_name}, or change `reading.queue_collection` to a unique name."
                )
            }
        )
    folder_id = matches[0].get("id")
    if not isinstance(folder_id, str) or not folder_id:
        return empty.model_copy(
            update={
                "message": (
                    f"Mendeley collection {collection_name!r} has no usable id; "
                    f"try toggling its name in Mendeley to refresh."
                )
            }
        )

    # Build folder map + discover sub-collection hierarchy.
    folder_map: dict[str, dict] = {
        f["id"]: f for f in folders if isinstance(f, dict) and f.get("id")
    }
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
    yield ProgressEvent(
        phase="discover", message=f"Reading collection {collection_name!r} ({folder_id[:8]}…)."
    )
    docs_resp = backend.list_documents(folder_id)
    if docs_resp.get("error"):
        err = docs_resp["error"]
        return empty.model_copy(
            update={
                "folder_id": folder_id,
                "message": f"Could not list documents in {collection_name!r}: {mendeley_failure_hint(err, backend_name)}",
            }
        )

    # doc_with_category: {mendeley_id: (doc, category_path)} — deepest path wins.
    doc_with_category: dict[str, tuple[dict, str | None]] = {}
    in_root_collection: set[str] = set()  # mids found directly in the parent/root folder
    _no_id_failed: list[dict[str, str]] = []
    _maybe_truncated = bool(docs_resp.get("maybe_truncated"))

    for doc in [d for d in (docs_resp.get("items") or []) if isinstance(d, dict)]:
        mid = extract_mendeley_id(doc)
        if mid:
            doc_with_category[mid] = (doc, None)  # None = directly in root
            in_root_collection.add(mid)
        else:
            _no_id_failed.append({"mendeley_id": "", "error": "doc has no usable id"})

    for sfid in sub_folder_ids:
        sf_name = folder_map.get(sfid, {}).get("name", sfid)
        cat_path = compute_category_path(sfid, folder_id, folder_map)
        yield ProgressEvent(phase="discover", message=f"Reading sub-collection {sf_name!r}…")
        sf_resp = backend.list_documents(sfid)
        if sf_resp.get("error"):
            yield ProgressEvent(
                phase="discover",
                level="warn",
                message=f"Could not read '{sf_name}': {sf_resp['error']}",
            )
            continue
        if sf_resp.get("maybe_truncated"):
            _maybe_truncated = True
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
    if _maybe_truncated:
        yield ProgressEvent(
            phase="discover",
            level="warn",
            message=(
                "Mendeley returned the maximum number of documents — collection may be larger "
                "than the fetch limit. Removal pass skipped to avoid falsely marking entries "
                "as removed. Run with a smaller collection or contact support to raise the limit."
            ),
        )

    added: list[dict[str, str]] = []
    unchanged: list[str] = []
    flagged: list[str] = []  # newly flagged as not_in_library (absent from all collections)
    cleared: list[str] = []  # not_in_library / manually_kept cleared (returned to any collection)
    not_in_parent: list[str] = []  # newly flagged as not_in_parent_collection (in sub only)
    cleared_parent: list[str] = []  # not_in_parent_collection cleared (back in root)
    _removed: list[str] = []  # dry-run compat only (unused but kept for shape symmetry)
    failed: list[dict[str, str]] = list(_no_id_failed)
    dry_run_added: list[dict[str, str]] = []
    dry_run_removed: list[str] = []
    category_updates: dict[str, str | None] = {}  # entry_id -> new category

    queue = store.load_queue()
    by_reference_id: dict[str, dict[str, Any]] = {
        e["reference_id"]: e for e in queue if e.get("reference_id")
    }
    existing_ids: set[str] = {e.get("id") for e in queue if e.get("id")}
    reserved_ids: set[str] = set()
    in_collection: set[str] = set()
    new_entries: list[dict[str, Any]] = []
    max_order = max((e.get("order", 0) for e in queue), default=0)

    for i, (mid, (doc, category)) in enumerate(docs_to_process, 1):
        in_collection.add(mid)
        yield ProgressEvent(
            phase="reconcile",
            current=i,
            total=len(docs_to_process),
            item=doc.get("title", mid)[:60],
        )

        if mid in by_reference_id:
            existing_entry = by_reference_id[mid]
            eid = existing_entry.get("id") or mid
            if existing_entry.get("category") != category:
                category_updates[eid] = category
            # Clear not_in_library / manually_kept — entry is back in some collection.
            if existing_entry.get("not_in_library") or existing_entry.get("manually_kept"):
                cleared.append(eid)
            # Track parent-collection membership changes.
            in_parent = mid in in_root_collection
            if in_parent and existing_entry.get("not_in_parent_collection"):
                cleared_parent.append(eid)  # returned to the root collection
            elif (
                not in_parent
                and not existing_entry.get("not_in_parent_collection")
                and not existing_entry.get("not_in_library")
                and not existing_entry.get("manually_kept")
            ):
                not_in_parent.append(eid)  # newly in sub-collection only
            unchanged.append(eid)
            continue

        try:
            max_order += 1
            entry = build_entry_from_mendeley(
                doc, mid, existing_ids | reserved_ids, max_order, category=category
            )
        except Exception as e:  # noqa: BLE001
            failed.append({"reference_id": mid, "error": str(e)})
            yield ProgressEvent(phase="reconcile", level="error", message=f"{mid[:8]}: {e}")
            continue

        reserved_ids.add(entry.id)
        if dry_run:
            dry_run_added.append({"id": entry.id, "reference_id": mid, "title": entry.title})
        else:
            new_entries.append(entry.model_dump())
            added.append({"id": entry.id, "reference_id": mid, "title": entry.title})

    if not _maybe_truncated:
        for qe in queue:
            mid = qe.get("reference_id")
            if not mid or mid in in_collection:
                continue
            # Skip entries already handled: removed, already flagged, or manually kept by the user.
            if qe.get("status") == "removed" or qe.get("not_in_library") or qe.get("manually_kept"):
                continue
            if dry_run:
                dry_run_removed.append(qe.get("id", mid))
            else:
                flagged.append(qe.get("id", mid))

    if not dry_run and (
        new_entries or flagged or cleared or not_in_parent or cleared_parent or category_updates
    ):
        flagged_set = set(flagged)
        cleared_set = set(cleared)
        not_in_parent_set = set(not_in_parent)
        cleared_parent_set = set(cleared_parent)
        with store.lock():
            queue = store.load_queue()
            by_id = {qe.get("id"): qe for qe in queue}
            for ne in new_entries:
                if ne["id"] not in by_id:
                    queue.append(ne)
            for qe in queue:
                eid = qe.get("id")
                if eid in flagged_set:
                    qe["not_in_library"] = True
                if eid in cleared_set:
                    qe["not_in_library"] = False
                    qe["manually_kept"] = False
                    qe["manually_kept_at"] = None
                if eid in not_in_parent_set:
                    qe["not_in_parent_collection"] = True
                if eid in cleared_parent_set:
                    qe["not_in_parent_collection"] = False
                if eid in category_updates:
                    qe["category"] = category_updates[eid]
            store.save_queue(queue)

    if not dry_run:
        mendeley_cache.invalidate(folder_id)

    log_event(
        "sync_from_mendeley",
        collection=collection_name,
        folder_id=folder_id,
        backend=backend.get_name(),
        in_collection=len(in_collection),
        in_root=len(in_root_collection),
        added=len(added),
        unchanged=len(unchanged),
        flagged=len(flagged),
        cleared=len(cleared),
        not_in_parent=len(not_in_parent),
        cleared_parent=len(cleared_parent),
        failed=len(failed),
        dry_run=dry_run,
    )

    summary_parts = [f"{len(added)} added", f"{len(unchanged)} unchanged"]
    if flagged:
        summary_parts.append(f"{len(flagged)} flagged (not in collection — review in the UI)")
    if not_in_parent:
        summary_parts.append(
            f"{len(not_in_parent)} flagged (sub-collection only — review in the UI)"
        )
    if cleared:
        summary_parts.append(f"{len(cleared)} cleared (returned to collection)")
    if cleared_parent:
        summary_parts.append(f"{len(cleared_parent)} cleared (returned to parent)")
    if dry_run:
        summary_parts.append(
            f"{len(dry_run_added)} would-add, {len(dry_run_removed)} would-flag (dry-run)"
        )
    summary_parts.append(f"{len(failed)} failed")
    summary = ", ".join(summary_parts) + "."
    if any("auth:" in f.get("error", "") for f in failed):
        if backend_name == "Mendeley":
            summary += " Auth failure detected — run `mendeley-auth login` and retry."
        else:
            summary += f" Auth failure detected — check your {backend_name} credentials and retry."

    return SyncFromLibraryResult(
        queue_collection=collection_name,
        folder_id=folder_id,
        added=added,
        unchanged=unchanged,
        flagged=flagged,
        cleared=cleared,
        not_in_parent=not_in_parent,
        cleared_parent=cleared_parent,
        removed=[],
        failed=failed,
        dry_run_added=dry_run_added,
        dry_run_removed=dry_run_removed,
        summary=summary,
    )

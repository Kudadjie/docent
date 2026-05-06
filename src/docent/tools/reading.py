"""Reading queue tool: manage what you're reading + Mendeley sync."""
from __future__ import annotations

import json
import re
from datetime import datetime, date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from docent.config import write_setting
from docent.core import Context, ProgressEvent, Tool, action, register_tool
from docent.learning import RunLog
from docent.tools.reading_store import BannerCounts, ReadingQueueStore
from docent.tools.mendeley_cache import MendeleyCache
from docent.tools.mendeley_client import (
    list_documents as mendeley_list_documents,
    list_folders as mendeley_list_folders,
)
from docent.utils.paths import cache_dir, data_dir
from docent.utils.prompt import NoInteractiveError, prompt_for_path


_DEFAULT_DATABASE_DIR = "~/Documents/Papers"
_KNOWN_READING_KEYS = {"database_dir", "queue_collection"}
# `mendeley_mcp_command` is a list field; config-set only handles strings today.
# Power users can edit config.toml directly; defaulted to ["uvx", "mendeley-mcp"] in mendeley_client.

class QueueEntry(BaseModel):
    id: str
    title: str = ""        # Mendeley-owned snapshot; overlay refreshes on read.
    authors: str = ""      # Mendeley-owned snapshot; overlay refreshes on read.
    year: int | None = None
    doi: str | None = None
    added: str             # ISO date
    status: str = "queued"
    order: int = 0         # 1-based position in the reading queue; 0 = unordered.
    category: str | None = None   # Mendeley sub-collection path, e.g. "CES701" or "CES701/Topic"; None = root.
    deadline: str | None = None   # ISO date (YYYY-MM-DD), user-settable.
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    mendeley_id: str | None = None
    started: str | None = None    # ISO timestamp when status -> reading.
    finished: str | None = None   # ISO timestamp when status -> done.

    @model_validator(mode="after")
    def _require_identifier(self) -> "QueueEntry":
        if not self.doi and not self.mendeley_id:
            raise ValueError(
                "QueueEntry requires doi or mendeley_id — identifier-free entries are not allowed."
            )
        return self


class AddInputs(BaseModel):
    mendeley_id: str | None = Field(None, description="Mendeley document id; if supplied, an entry is upserted (metadata pulled fresh on next read). Without this, `add` prints guidance.")
    category: str | None = Field(None, description="Override category (e.g. 'CES701'). Normally auto-detected from the Mendeley sub-collection on sync.")
    deadline: str | None = Field(None, description="ISO date deadline (YYYY-MM-DD), optional.")
    notes: str = Field("", description="Freeform notes.")
    force: bool = Field(False, description="Overwrite if an entry keyed on this mendeley_id already exists.")


class AddResult(BaseModel):
    added: bool
    id: str
    title: str
    queue_size: int
    banner: BannerCounts
    message: str


class IdOnlyInputs(BaseModel):
    id: str = Field(..., description="Entry id (e.g. 'smith-2024-foo').")


class NextInputs(BaseModel):
    category: str | None = Field(None, description="Restrict to a category prefix (e.g. 'CES701' matches 'CES701' and 'CES701/Topic').")


class SearchInputs(BaseModel):
    query: str = Field(..., description="Case-insensitive substring matched against title, authors, notes, category, id, and tags.")


class StatsInputs(BaseModel):
    pass


class EditInputs(BaseModel):
    id: str = Field(..., description="Entry id to edit.")
    status: str | None = Field(None, description="New status (queued|reading|done).")
    order: int | None = Field(None, description="New reading order position (1 = read first).")
    category: str | None = Field(None, description="Override category (e.g. 'CES701'). Normally auto-detected from the Mendeley sub-collection on sync.")
    deadline: str | None = Field(None, description="New deadline (YYYY-MM-DD) or '' to clear.")
    notes: str | None = Field(None, description="New notes.")
    tags: list[str] | None = Field(None, description="Replace tag list.")


class ExportInputs(BaseModel):
    format: str = Field("json", description="Output format: json | markdown.")
    category: str | None = Field(None, description="Filter by exact category path (e.g. 'CES701' or 'CES701/Topic').")
    status: str | None = Field(None, description="Filter by status (queued|reading|done).")


class ConfigShowInputs(BaseModel):
    pass


class ConfigSetInputs(BaseModel):
    key: str = Field(..., description="Setting key under the [reading] section, e.g. 'database_dir' or 'queue_collection'.")
    value: str = Field(..., description="New value. Use '' to clear. Paths may use '~'.")


class ConfigShowResult(BaseModel):
    config_path: str
    database_dir: str | None
    queue_collection: str


class ConfigSetResult(BaseModel):
    ok: bool
    key: str
    value: str
    config_path: str
    message: str


class MutationResult(BaseModel):
    ok: bool
    id: str
    entry: QueueEntry | None
    queue_size: int
    banner: BannerCounts
    message: str


class SearchResult(BaseModel):
    query: str
    matches: list[QueueEntry]
    total: int
    queue_size: int


class StatsResult(BaseModel):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    banner: BannerCounts


class ExportResult(BaseModel):
    format: str
    count: int
    content: str


class QueueClearInputs(BaseModel):
    yes: bool = Field(False, description="Confirm: actually clear the queue. Without this, the action reports the size and exits.")


class QueueClearResult(BaseModel):
    cleared: bool
    removed_count: int
    queue_size: int
    banner: BannerCounts
    message: str


class SyncStatusInputs(BaseModel):
    pass


class SyncFromMendeleyInputs(BaseModel):
    dry_run: bool = Field(False, description="Resolve the collection and report what would change without writing the queue.")


class SyncFromMendeleyResult(BaseModel):
    """Per-doc buckets after running sync-from-mendeley.

    `added`: {id, mendeley_id, title}; `unchanged`: entry ids; `removed`:
    entry ids (status flipped to 'removed'); `failed`: {mendeley_id, error};
    dry-run variants populate only when dry_run=True.
    `message` carries early-exit reasons (collection missing, MCP transport error).
    """
    queue_collection: str
    folder_id: str | None
    added: list[dict[str, str]]
    unchanged: list[str]
    removed: list[str]
    failed: list[dict[str, str]]
    dry_run_added: list[dict[str, str]]
    dry_run_removed: list[str]
    summary: str
    message: str = ""


class SyncStatusResult(BaseModel):
    database_dir: str | None
    queue_size: int
    database_pdfs: list[str]
    summary: str
    message: str = ""


class MoveToInputs(BaseModel):
    id: str = Field(..., description="Entry id to move.")
    position: int = Field(..., ge=1, description="New position (1 = read first).")


@register_tool
class ReadingQueue(Tool):
    """Reading queue + Mendeley sync."""

    name = "reading"
    description = "Reading queue management and Mendeley sync."
    category = "reading"

    def __init__(self) -> None:
        self._store = ReadingQueueStore(data_dir() / "reading")

    @action(
        description="Add an entry by Mendeley id, or print guidance for the drag-and-drop flow.",
        input_schema=AddInputs,
    )
    def add(self, inputs: AddInputs, context: Context) -> AddResult:
        if not inputs.mendeley_id:
            collection = context.settings.reading.queue_collection
            return AddResult(
                added=False, id="", title="",
                queue_size=len(self._store.load_index()),
                banner=self._store.banner_counts(),
                message=(
                    "Drop the PDF in your reading.database_dir (Mendeley auto-imports it), "
                    f"drag it into the '{collection}' collection in Mendeley, then run "
                    "`docent reading sync-from-mendeley`. "
                    f"Category is auto-detected from sub-collections: "
                    f"'{collection}/CES701' -> category='CES701', "
                    f"'{collection}/CES701/Topic' -> category='CES701/Topic'."
                ),
            )

        mid = inputs.mendeley_id.strip()
        queue = self._store.load_queue()
        existing = next((e for e in queue if e.get("mendeley_id") == mid), None)

        if existing and not inputs.force:
            return AddResult(
                added=False,
                id=existing.get("id", ""),
                title=existing.get("title", ""),
                queue_size=len(queue),
                banner=self._store.banner_counts(),
                message=(
                    f"Mendeley id {mid!r} already in queue as {existing.get('id')!r}. "
                    f"Use --force to update, or `docent reading edit` to change fields."
                ),
            )

        existing_ids = {e.get("id") for e in queue if e.get("id")}
        base_id = f"mendeley-{mid[:8]}"
        entry_id = base_id
        suffix = 1
        while entry_id in existing_ids and (not existing or existing.get("id") != entry_id):
            suffix += 1
            entry_id = f"{base_id}-{suffix}"
        if existing:
            entry_id = existing.get("id") or entry_id

        # Assign order: append after the last ordered entry.
        new_order = max((e.get("order", 0) for e in queue), default=0) + 1

        new_entry = QueueEntry(
            id=entry_id,
            title=existing.get("title") if existing else "(pending Mendeley sync)",
            authors=existing.get("authors") if existing else "Unknown",
            year=existing.get("year") if existing else None,
            doi=existing.get("doi") if existing else None,
            added=existing.get("added") if existing else datetime.now().date().isoformat(),
            order=existing.get("order", new_order) if existing else new_order,
            category=inputs.category,
            deadline=inputs.deadline,
            notes=inputs.notes,
            mendeley_id=mid,
        )

        if existing:
            queue = [e for e in queue if e.get("id") != entry_id]
        queue.append(new_entry.model_dump())
        self._store.save_queue(queue)
        self._log_event("add", id=entry_id, replaced=bool(existing),
                        category=inputs.category, mendeley_id=mid)

        verb = "Updated" if existing else "Added"
        return AddResult(
            added=True,
            id=entry_id,
            title=new_entry.title,
            queue_size=len(queue),
            banner=self._store.banner_counts(),
            message=(
                f"{verb} {entry_id!r} (mendeley_id={mid}, order={new_entry.order}). "
                f"Run `docent reading next` to see fresh metadata."
            ),
        )

    @action(description="Show the next entry to read (lowest order number among queued).", input_schema=NextInputs)
    def next(self, inputs: NextInputs, context: Context) -> MutationResult:
        queue = self._store.load_queue()
        queue = self._apply_overlay(queue, self._load_mendeley_overlay(context))
        candidates = [e for e in queue if e.get("status") == "queued"]
        if inputs.category:
            cat = inputs.category
            candidates = [
                e for e in candidates
                if e.get("category") == cat or (e.get("category") or "").startswith(cat + "/")
            ]
        if not candidates:
            scope = f" for category {inputs.category!r}" if inputs.category else ""
            return MutationResult(
                ok=False, id="", entry=None, queue_size=len(queue),
                banner=self._store.banner_counts(),
                message=f"No queued entries{scope}.",
            )
        best = sorted(
            candidates,
            key=lambda e: (e.get("order", 0) or 999999, e.get("added", "")),
        )[0]
        return MutationResult(
            ok=True, id=best["id"], entry=QueueEntry(**best),
            queue_size=len(queue), banner=self._store.banner_counts(),
            message=f"Read next: {best['title']!r} (order={best.get('order', 0)}, added {best.get('added', '')}).",
        )

    @action(description="Show one entry's details.", input_schema=IdOnlyInputs)
    def show(self, inputs: IdOnlyInputs, context: Context) -> MutationResult:
        queue = self._store.load_queue()
        queue = self._apply_overlay(queue, self._load_mendeley_overlay(context))
        entry = self._find_entry(queue, inputs.id)
        if not entry:
            return self._not_found(inputs.id, queue)
        return MutationResult(
            ok=True, id=inputs.id, entry=QueueEntry(**entry),
            queue_size=len(queue), banner=self._store.banner_counts(),
            message=f"Found {inputs.id!r}: {entry['title']!r}.",
        )

    @action(description="Search the queue for matching entries.", input_schema=SearchInputs)
    def search(self, inputs: SearchInputs, context: Context) -> SearchResult:
        queue = self._store.load_queue()
        queue = self._apply_overlay(queue, self._load_mendeley_overlay(context))
        q = inputs.query.lower()
        matches: list[QueueEntry] = []
        for e in queue:
            haystack = " ".join([
                e.get("title", "") or "",
                e.get("authors", "") or "",
                e.get("notes", "") or "",
                e.get("category") or "",
                e.get("id", "") or "",
                " ".join(e.get("tags") or []),
            ]).lower()
            if q in haystack:
                matches.append(QueueEntry(**e))
        return SearchResult(query=inputs.query, matches=matches, total=len(matches), queue_size=len(queue))

    @action(description="Show queue statistics.", input_schema=StatsInputs)
    def stats(self, inputs: StatsInputs, context: Context) -> StatsResult:
        queue = self._store.load_queue()
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for e in queue:
            s = e.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
            cat = e.get("category") or "(root)"
            by_category[cat] = by_category.get(cat, 0) + 1
        return StatsResult(
            total=len(queue), by_status=by_status,
            by_category=by_category,
            banner=self._store.banner_counts(),
        )

    @action(description="Remove an entry from the queue.", input_schema=IdOnlyInputs)
    def remove(self, inputs: IdOnlyInputs, context: Context) -> MutationResult:
        queue = self._store.load_queue()
        entry = self._find_entry(queue, inputs.id)
        if not entry:
            return self._not_found(inputs.id, queue)
        new_queue = [e for e in queue if e.get("id") != inputs.id]
        self._store.save_queue(new_queue)
        self._log_event("remove", id=inputs.id, title=entry.get("title"))
        return MutationResult(
            ok=True, id=inputs.id, entry=QueueEntry(**entry),
            queue_size=len(new_queue), banner=self._store.banner_counts(),
            message=f"Removed {inputs.id!r}.",
        )

    @action(description="Edit user-settable fields on an existing entry (Mendeley-owned fields: title/authors/year/doi are not editable here).", input_schema=EditInputs)
    def edit(self, inputs: EditInputs, context: Context) -> MutationResult:
        queue = self._store.load_queue()
        entry = self._find_entry(queue, inputs.id)
        if not entry:
            return self._not_found(inputs.id, queue)
        updates: dict[str, Any] = {}
        if inputs.status is not None:
            updates["status"] = inputs.status
        if inputs.order is not None:
            updates["order"] = inputs.order
        if inputs.category is not None:
            updates["category"] = inputs.category or None
        if inputs.deadline is not None:
            updates["deadline"] = inputs.deadline or None
        if inputs.notes is not None:
            updates["notes"] = inputs.notes
        if inputs.tags is not None:
            updates["tags"] = inputs.tags
        if not updates:
            return MutationResult(
                ok=False, id=inputs.id, entry=QueueEntry(**entry),
                queue_size=len(queue), banner=self._store.banner_counts(),
                message="No fields supplied; nothing to edit.",
            )
        entry.update(updates)
        self._store.save_queue(queue)
        self._log_event("edit", id=inputs.id, fields=sorted(updates.keys()))
        return MutationResult(
            ok=True, id=inputs.id, entry=QueueEntry(**entry),
            queue_size=len(queue), banner=self._store.banner_counts(),
            message=f"Updated {inputs.id!r}: {sorted(updates.keys())}.",
        )

    @action(
        description="Empty the reading queue (irreversible). Re-run with --yes to actually clear.",
        input_schema=QueueClearInputs,
        name="queue-clear",
    )
    def queue_clear(self, inputs: QueueClearInputs, context: Context) -> QueueClearResult:
        queue = self._store.load_queue()
        n = len(queue)
        if not inputs.yes:
            return QueueClearResult(
                cleared=False,
                removed_count=0,
                queue_size=n,
                banner=self._store.banner_counts(),
                message=f"{n} entries in queue. Re-run with --yes to clear.",
            )
        self._store.save_queue([])
        self._log_event("queue_clear", removed=n)
        return QueueClearResult(
            cleared=True,
            removed_count=n,
            queue_size=0,
            banner=self._store.banner_counts(),
            message=f"Cleared {n} entries from the queue.",
        )

    @action(description="Mark an entry as done.", input_schema=IdOnlyInputs)
    def done(self, inputs: IdOnlyInputs, context: Context) -> MutationResult:
        return self._set_status(inputs.id, "done")

    @action(description="Mark an entry as in-progress (currently reading).", input_schema=IdOnlyInputs)
    def start(self, inputs: IdOnlyInputs, context: Context) -> MutationResult:
        return self._set_status(inputs.id, "reading")

    @action(description="Export the queue (or a filtered subset), applying fresh Mendeley metadata.", input_schema=ExportInputs)
    def export(self, inputs: ExportInputs, context: Context) -> ExportResult:
        queue = self._store.load_queue()
        queue = self._apply_overlay(queue, self._load_mendeley_overlay(context))
        filtered = queue
        if inputs.category:
            filtered = [e for e in filtered if e.get("category") == inputs.category]
        if inputs.status:
            filtered = [e for e in filtered if e.get("status") == inputs.status]
        filtered = sorted(filtered, key=lambda e: (e.get("order", 0) or 999999, e.get("added", "")))
        if inputs.format == "json":
            content = json.dumps(filtered, indent=2, ensure_ascii=False)
        elif inputs.format == "markdown":
            lines = [
                "| id | title | authors | year | order | category | status |",
                "|---|---|---|---|---|---|---|",
            ]
            for e in filtered:
                year = e.get("year")
                lines.append(
                    f"| {e.get('id','')} | {e.get('title','')} | {e.get('authors','')} | "
                    f"{year if year is not None else ''} | {e.get('order',0)} | "
                    f"{e.get('category','personal')} | {e.get('status','')} |"
                )
            content = "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {inputs.format!r}. Use 'json' or 'markdown'.")
        return ExportResult(format=inputs.format, count=len(filtered), content=content)

    @action(description="Move an entry one position earlier in the reading order.", input_schema=IdOnlyInputs, name="move-up")
    def move_up(self, inputs: IdOnlyInputs, context: Context) -> MutationResult:
        queue = self._store.load_queue()
        entry = self._find_entry(queue, inputs.id)
        if not entry:
            return self._not_found(inputs.id, queue)
        current_order = entry.get("order", 0) or 0
        if current_order <= 1:
            return MutationResult(
                ok=False, id=inputs.id, entry=QueueEntry(**entry),
                queue_size=len(queue), banner=self._store.banner_counts(),
                message=f"{inputs.id!r} is already at position 1; can't move up.",
            )
        self._reorder_move_to(queue, inputs.id, current_order - 1)
        self._store.save_queue(queue)
        updated = self._find_entry(queue, inputs.id)
        return MutationResult(
            ok=True, id=inputs.id, entry=QueueEntry(**updated),
            queue_size=len(queue), banner=self._store.banner_counts(),
            message=f"Moved {inputs.id!r} to position {updated.get('order')}.",
        )

    @action(description="Move an entry one position later in the reading order.", input_schema=IdOnlyInputs, name="move-down")
    def move_down(self, inputs: IdOnlyInputs, context: Context) -> MutationResult:
        queue = self._store.load_queue()
        entry = self._find_entry(queue, inputs.id)
        if not entry:
            return self._not_found(inputs.id, queue)
        ordered = sorted([e for e in queue if e.get("order", 0) > 0], key=lambda e: e.get("order", 0))
        max_order = ordered[-1].get("order", 1) if ordered else 1
        current_order = entry.get("order", 0) or 0
        if current_order >= max_order:
            return MutationResult(
                ok=False, id=inputs.id, entry=QueueEntry(**entry),
                queue_size=len(queue), banner=self._store.banner_counts(),
                message=f"{inputs.id!r} is already at the last position; can't move down.",
            )
        self._reorder_move_to(queue, inputs.id, current_order + 1)
        self._store.save_queue(queue)
        updated = self._find_entry(queue, inputs.id)
        return MutationResult(
            ok=True, id=inputs.id, entry=QueueEntry(**updated),
            queue_size=len(queue), banner=self._store.banner_counts(),
            message=f"Moved {inputs.id!r} to position {updated.get('order')}.",
        )

    @action(description="Move an entry to a specific position in the reading order.", input_schema=MoveToInputs, name="move-to")
    def move_to(self, inputs: MoveToInputs, context: Context) -> MutationResult:
        queue = self._store.load_queue()
        entry = self._find_entry(queue, inputs.id)
        if not entry:
            return self._not_found(inputs.id, queue)
        self._reorder_move_to(queue, inputs.id, inputs.position)
        self._store.save_queue(queue)
        updated = self._find_entry(queue, inputs.id)
        return MutationResult(
            ok=True, id=inputs.id, entry=QueueEntry(**updated),
            queue_size=len(queue), banner=self._store.banner_counts(),
            message=f"Moved {inputs.id!r} to position {updated.get('order')}.",
        )

    @action(description="Show the configured reading settings.", input_schema=ConfigShowInputs, name="config-show")
    def config_show(self, inputs: ConfigShowInputs, context: Context) -> ConfigShowResult:
        from docent.utils.paths import config_file
        rs = context.settings.reading
        db = str(rs.database_dir) if rs.database_dir else None
        return ConfigShowResult(
            config_path=str(config_file()),
            database_dir=db,
            queue_collection=rs.queue_collection,
        )

    @action(description="Set a reading setting (database_dir, queue_collection).", input_schema=ConfigSetInputs, name="config-set")
    def config_set(self, inputs: ConfigSetInputs, context: Context) -> ConfigSetResult:
        from docent.utils.paths import config_file
        if inputs.key not in _KNOWN_READING_KEYS:
            return ConfigSetResult(
                ok=False, key=inputs.key, value=inputs.value,
                config_path=str(config_file()),
                message=f"Unknown key {inputs.key!r}. Known: {sorted(_KNOWN_READING_KEYS)}.",
            )
        path = write_setting(f"reading.{inputs.key}", inputs.value)
        return ConfigSetResult(
            ok=True, key=inputs.key, value=inputs.value,
            config_path=str(path),
            message=f"Set reading.{inputs.key} = {inputs.value!r} in {path}.",
        )

    @action(
        description="Report queue size and PDFs sitting in database_dir.",
        input_schema=SyncStatusInputs,
        name="sync-status",
    )
    def sync_status(self, inputs: SyncStatusInputs, context: Context) -> SyncStatusResult:
        empty = SyncStatusResult(database_dir=None, queue_size=0, database_pdfs=[], summary="")
        try:
            database_dir, err = self._require_database_dir(context)
        except NoInteractiveError as e:
            return empty.model_copy(update={"message": (
                f"reading.database_dir not configured. Run "
                f"`docent reading config-set database_dir <path>` or set "
                f"DOCENT_READING__DATABASE_DIR. ({e})"
            )})
        if database_dir is None:
            return empty.model_copy(update={"message": err or "Cancelled — no database folder configured."})
        if not database_dir.is_dir():
            return empty.model_copy(update={
                "database_dir": str(database_dir),
                "message": f"database_dir does not exist: {database_dir}.",
            })
        db_pdfs = ReadingQueueStore.list_database_pdfs(database_dir)
        queue = self._store.load_queue()
        summary = (
            f"{len(queue)} queue entry/entries, "
            f"{len(db_pdfs)} PDF(s) in database_dir."
        )
        return SyncStatusResult(
            database_dir=str(database_dir),
            queue_size=len(queue),
            database_pdfs=sorted(p.name for p in db_pdfs),
            summary=summary,
        )

    @action(
        description="Reconcile the local reading queue with a Mendeley collection (default 'Docent-Queue').",
        input_schema=SyncFromMendeleyInputs,
        name="sync-from-mendeley",
    )
    def sync_from_mendeley(self, inputs: SyncFromMendeleyInputs, context: Context):
        collection_name = context.settings.reading.queue_collection
        launch_command = context.settings.reading.mendeley_mcp_command
        return self._sync_from_mendeley_run(collection_name, launch_command, inputs.dry_run)

    @staticmethod
    def _compute_category_path(folder_id: str, root_id: str, folder_map: dict[str, dict]) -> str | None:
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

    def _sync_from_mendeley_run(
        self, collection_name: str, launch_command: list[str] | None, dry_run: bool
    ):
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
                f"Could not list Mendeley folders: {self._mendeley_failure_hint(err)}"
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
                "message": f"Could not list documents in {collection_name!r}: {self._mendeley_failure_hint(err)}",
            })

        # doc_with_category: {mendeley_id: (doc, category_path)} — deepest path wins.
        doc_with_category: dict[str, tuple[dict, str | None]] = {}
        _no_id_failed: list[dict[str, str]] = []

        for doc in [d for d in (docs_resp.get("items") or []) if isinstance(d, dict)]:
            mid = self._extract_mendeley_id(doc)
            if mid:
                doc_with_category[mid] = (doc, None)  # None = directly in root
            else:
                _no_id_failed.append({"mendeley_id": "", "error": "doc has no usable id"})

        for sfid in sub_folder_ids:
            sf_name = folder_map.get(sfid, {}).get("name", sfid)
            cat_path = self._compute_category_path(sfid, folder_id, folder_map)
            yield ProgressEvent(phase="discover", message=f"Reading sub-collection {sf_name!r}…")
            sf_resp = mendeley_list_documents(folder_id=sfid, launch_command=launch_command)
            if sf_resp.get("error"):
                yield ProgressEvent(phase="discover", level="warn",
                                    message=f"Could not read '{sf_name}': {sf_resp['error']}")
                continue
            for doc in [d for d in (sf_resp.get("items") or []) if isinstance(d, dict)]:
                mid = self._extract_mendeley_id(doc)
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

        queue = self._store.load_queue()
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
                entry = self._build_entry_from_mendeley(doc, mid, existing_ids | reserved_ids, max_order, category=category)
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
            queue = self._store.load_queue()
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
            self._store.save_queue(queue)

        if not dry_run:
            self._mendeley_cache().invalidate(folder_id)

        self._log_event(
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

    def _build_entry_from_mendeley(
        self, doc: dict[str, Any], mendeley_id: str, taken_ids: set[str], order: int,
        category: str | None = None,
    ) -> "QueueEntry":
        title = (doc.get("title") or "").strip() or "(untitled)"
        authors = self._normalize_mendeley_authors(doc.get("authors"))
        year = doc.get("year")
        if not isinstance(year, int):
            year = None
        doi: str | None = None
        idents = doc.get("identifiers")
        if isinstance(idents, dict):
            d = idents.get("doi")
            if isinstance(d, str) and d.strip():
                doi = d.strip()

        base = self._derive_id(authors, year, title)
        entry_id = f"{base}-{mendeley_id[:8]}" if base in taken_ids else base

        return QueueEntry(
            id=entry_id,
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            added=datetime.now().date().isoformat(),
            order=order,
            category=category,
            mendeley_id=mendeley_id,
        )

    @staticmethod
    def _normalize_mendeley_authors(authors: Any) -> str:
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

    @staticmethod
    def _extract_mendeley_id(item: dict[str, Any]) -> str | None:
        for key in ("id", "catalog_id", "document_id", "mendeley_id"):
            v = item.get(key)
            if isinstance(v, str) and v:
                return v
        return None

    @staticmethod
    def _candidate_summary(item: dict[str, Any]) -> dict[str, str]:
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
            "mendeley_id": ReadingQueue._extract_mendeley_id(item) or "",
            "title": str(title),
            "year": str(year) if year is not None else "",
            "authors": str(authors),
        }

    @staticmethod
    def _mendeley_failure_hint(error: str) -> str:
        if error.startswith("auth:"):
            return f"{error} (run `mendeley-auth login` to refresh tokens)"
        if "launch command not found" in error:
            return f"{error} (install with `uv tool install mendeley-mcp` or set reading.mendeley_mcp_command)"
        return error

    # ------------------------------------------------------------------
    # Ordering helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _reorder_move_to(queue: list[dict[str, Any]], target_id: str, new_position: int) -> None:
        """Mutate queue in-place: move `target_id` to `new_position`, shifting
        other ordered entries to maintain contiguous 1-based ordering."""
        ordered = sorted(
            [e for e in queue if e.get("order", 0) > 0],
            key=lambda e: e.get("order", 0),
        )
        target = next((e for e in ordered if e.get("id") == target_id), None)
        if target is None:
            # Entry has order=0; assign it to new_position and shift others up.
            new_position = max(1, min(new_position, len(ordered) + 1))
            for e in ordered:
                if e.get("order", 0) >= new_position:
                    e["order"] = e["order"] + 1
            for e in queue:
                if e.get("id") == target_id:
                    e["order"] = new_position
            return

        old_position = target["order"]
        new_position = max(1, min(new_position, len(ordered)))
        if old_position == new_position:
            return

        if new_position < old_position:
            for e in ordered:
                pos = e.get("order", 0)
                if new_position <= pos < old_position and e.get("id") != target_id:
                    e["order"] = pos + 1
        else:
            for e in ordered:
                pos = e.get("order", 0)
                if old_position < pos <= new_position and e.get("id") != target_id:
                    e["order"] = pos - 1

        target["order"] = new_position

    # ------------------------------------------------------------------
    # Mendeley overlay + cache helpers
    # ------------------------------------------------------------------

    def _mendeley_cache(self) -> MendeleyCache:
        return MendeleyCache(
            cache_dir() / "reading" / "mendeley_collection.json",
            list_documents=mendeley_list_documents,
            list_folders=mendeley_list_folders,
        )

    def _resolve_collection_folder_id_quiet(
        self, collection_name: str, launch_command: list[str] | None
    ) -> str | None:
        return self._mendeley_cache().get_folder_id(collection_name, launch_command)

    def _load_mendeley_overlay(self, context: Context) -> dict[str, dict[str, Any]] | None:
        rs = context.settings.reading
        collection_name = rs.queue_collection
        launch_command = rs.mendeley_mcp_command
        folder_id = self._resolve_collection_folder_id_quiet(collection_name, launch_command)
        if folder_id is None:
            return None
        return self._mendeley_cache().get_collection(folder_id, launch_command)

    @staticmethod
    def _overlay_entry(entry: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
        out = dict(entry)
        title = (doc.get("title") or "").strip()
        if title:
            out["title"] = title
        authors = ReadingQueue._normalize_mendeley_authors(doc.get("authors"))
        if authors and authors != "Unknown":
            out["authors"] = authors
        year = doc.get("year")
        if isinstance(year, int):
            out["year"] = year
        idents = doc.get("identifiers")
        if isinstance(idents, dict):
            d = idents.get("doi")
            if isinstance(d, str) and d.strip():
                out["doi"] = d.strip()
        return out

    def _apply_overlay(
        self, queue: list[dict[str, Any]], overlay: dict[str, dict[str, Any]] | None
    ) -> list[dict[str, Any]]:
        if not overlay:
            return queue
        out: list[dict[str, Any]] = []
        for e in queue:
            mid = e.get("mendeley_id")
            if mid and mid in overlay:
                out.append(self._overlay_entry(e, overlay[mid]))
            else:
                out.append(e)
        return out

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _require_database_dir(self, context: Context) -> tuple[Path | None, str | None]:
        rs = context.settings.reading
        if rs.database_dir is not None:
            return rs.database_dir.expanduser(), None
        path = prompt_for_path(
            "Where's your paper database? (path, 'create' for default, or 'cancel')",
            default=_DEFAULT_DATABASE_DIR,
        )
        if path is None:
            return None, None
        if not path.is_dir():
            return None, (
                f"Path doesn't exist: {path}. Pre-create the folder, type 'create' "
                f"next time to scaffold the default, or run "
                f"`docent reading config-set database_dir <path>` once it exists. Not persisted."
            )
        write_setting("reading.database_dir", str(path))
        context.settings.reading.database_dir = path
        return path, None

    def _find_entry(self, queue: list[dict[str, Any]], entry_id: str) -> dict[str, Any] | None:
        for e in queue:
            if e.get("id") == entry_id:
                return e
        return None

    def _not_found(self, entry_id: str, queue: list[dict[str, Any]]) -> MutationResult:
        return MutationResult(
            ok=False, id=entry_id, entry=None, queue_size=len(queue),
            banner=self._store.banner_counts(),
            message=f"No entry with id {entry_id!r}.",
        )

    def _set_status(self, entry_id: str, status: str) -> MutationResult:
        queue = self._store.load_queue()
        entry = self._find_entry(queue, entry_id)
        if not entry:
            return self._not_found(entry_id, queue)
        previous = entry.get("status")
        entry["status"] = status
        ts = datetime.now().isoformat()
        if status == "reading" and not entry.get("started"):
            entry["started"] = ts
        elif status == "done" and not entry.get("finished"):
            entry["finished"] = ts
        self._store.save_queue(queue)
        self._log_event("set_status", id=entry_id, status=status, previous=previous)
        return MutationResult(
            ok=True, id=entry_id, entry=QueueEntry(**entry),
            queue_size=len(queue), banner=self._store.banner_counts(),
            message=f"Set status to {status!r} for {entry_id!r} (was {previous!r}).",
        )

    def _log_event(self, event: str, **fields: Any) -> None:
        RunLog(self.name).append({"event": event, **fields})

    @staticmethod
    def _derive_id(authors: str, year: int | None, title: str) -> str:
        first_chunk = authors.split(",")[0].split(";")[0].strip() if authors else ""
        first_word = first_chunk.split()[0] if first_chunk else "unknown"
        last_name = re.sub(r"[^a-zA-Z0-9]", "", first_word).lower() or "unknown"
        year_part = str(year) if year else "nd"
        first_title_word = title.split()[0] if title else "untitled"
        title_word = re.sub(r"[^a-zA-Z0-9]", "", first_title_word).lower() or "untitled"
        return f"{last_name}-{year_part}-{title_word}"

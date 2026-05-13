"""Reading queue tool: manage what you're reading + Mendeley sync."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from docent.config import write_setting
from docent.core import Context, ProgressEvent, Tool, action, register_tool
from docent.core.shapes import (
    DataTableShape,
    ErrorShape,
    MarkdownShape,
    MessageShape,
    MetricShape,
    Shape,
)
from docent.learning import RunLog
from docent.utils.paths import cache_dir, data_dir
from docent.utils.prompt import NoInteractiveError, prompt_for_path

from .models import (
    AddInputs,
    AddResult,
    ConfigSetInputs,
    ConfigSetResult,
    ConfigShowInputs,
    ConfigShowResult,
    EditInputs,
    ExportInputs,
    ExportResult,
    IdOnlyInputs,
    MoveToInputs,
    MutationResult,
    NextInputs,
    QueueClearInputs,
    QueueClearResult,
    QueueEntry,
    SearchInputs,
    SearchResult,
    SetDeadlineInputs,
    StatsInputs,
    StatsResult,
    SyncFromMendeleyInputs,
    SyncFromMendeleyResult,
    SyncStatusInputs,
    SyncStatusResult,
)
from .mendeley_sync import (
    normalize_mendeley_authors,
    sync_from_mendeley_run,
)
from .reading_store import BannerCounts, ReadingQueueStore
from .mendeley_cache import MendeleyCache
from .mendeley_client import (
    list_documents as mendeley_list_documents,
    list_folders as mendeley_list_folders,
)


_DEFAULT_DATABASE_DIR = "~/Documents/Papers"
_KNOWN_READING_KEYS = {"database_dir", "queue_collection"}

@register_tool
class ReadingQueue(Tool):
    """Reading queue + Mendeley sync."""

    name = "reading"
    description = "Reading queue management and Mendeley sync."
    category = "reading"

    def __init__(self) -> None:
        self._store = ReadingQueueStore(data_dir() / "reading")

    @action(
        description="Show how to add papers to your reading queue via Mendeley.",
        input_schema=AddInputs,
    )
    def add(self, inputs: AddInputs, context: Context) -> AddResult:
        collection = context.settings.reading.queue_collection
        return AddResult(
            added=False,
            queue_size=len(self._store.load_index()),
            banner=self._store.banner_counts(),
            message=(
                "Drop the PDF in your reading.database_dir (Mendeley auto-imports it), "
                f"drag it into the '{collection}' collection (or a sub-collection) in Mendeley, "
                "then run `docent reading sync-from-mendeley`. "
                "Category is auto-detected from sub-collections: "
                f"'{collection}/CES701' -> category='CES701', "
                f"'{collection}/CES701/Topic' -> category='CES701/Topic'. "
                "Papers in the root collection get no category."
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
        matches.sort(key=lambda e: (e.order or 999999, e.added or ""))
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
        with self._store.lock():
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
        with self._store.lock():
            queue = self._store.load_queue()
            entry = self._find_entry(queue, inputs.id)
            if not entry:
                return self._not_found(inputs.id, queue)
            updates: dict[str, Any] = {}
            if inputs.status is not None:
                # Route through lifecycle helper so started/finished get stamped correctly.
                self._apply_status_transition(entry, inputs.status)
                updates["status"] = inputs.status  # track for log; entry already mutated
            if inputs.type is not None:
                updates["type"] = inputs.type
            if inputs.category is not None:
                updates["category"] = inputs.category or None
            if inputs.deadline is not None:
                updates["deadline"] = inputs.deadline or None
            if inputs.notes is not None:
                updates["notes"] = inputs.notes
            if inputs.tags is not None:
                updates["tags"] = inputs.tags
            if not updates and inputs.order is None:
                return MutationResult(
                    ok=False, id=inputs.id, entry=QueueEntry(**entry),
                    queue_size=len(queue), banner=self._store.banner_counts(),
                    message="No fields supplied; nothing to edit.",
                )
            # Status already applied via _apply_status_transition; skip it here.
            entry.update({k: v for k, v in updates.items() if k != "status"})
            if inputs.order is not None:
                # Route through reorder logic so other entries shift correctly.
                self._reorder_move_to(queue, inputs.id, inputs.order)
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
        with self._store.lock():
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

    @action(description="Set or clear a reading deadline on an entry.", input_schema=SetDeadlineInputs, name="set-deadline")
    def set_deadline(self, inputs: SetDeadlineInputs, context: Context) -> MutationResult:
        with self._store.lock():
            queue = self._store.load_queue()
            entry = self._find_entry(queue, inputs.id)
            if entry is None:
                return self._not_found(inputs.id, queue)
            entry["deadline"] = inputs.deadline.strip() or None
            self._store.save_queue(queue)
            self._log_event("set_deadline", id=inputs.id, deadline=entry["deadline"])
            return MutationResult(
                ok=True, id=inputs.id, entry=QueueEntry(**entry),
                queue_size=len(queue), banner=self._store.banner_counts(),
                message=f"Deadline {'set to ' + entry['deadline'] if entry['deadline'] else 'cleared'} for {inputs.id!r}.",
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
                "| # | title | authors | year | type | category | status | deadline |",
                "|---|---|---|---|---|---|---|---|",
            ]
            for e in filtered:
                year = e.get("year")
                etype = e.get("type", "paper").replace("_", " ")
                lines.append(
                    f"| {e.get('order', 0)} | {e.get('title', '')} | {e.get('authors', '')} | "
                    f"{year if year is not None else ''} | {etype} | "
                    f"{e.get('category') or ''} | {e.get('status', '')} | "
                    f"{e.get('deadline') or ''} |"
                )
            content = "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {inputs.format!r}. Use 'json' or 'markdown'.")
        return ExportResult(format=inputs.format, count=len(filtered), content=content)

    @action(description="Move an entry one position earlier in the reading order.", input_schema=IdOnlyInputs, name="move-up")
    def move_up(self, inputs: IdOnlyInputs, context: Context) -> MutationResult:
        with self._store.lock():
            queue = self._store.load_queue()
            entry = self._find_entry(queue, inputs.id)
            if not entry:
                return self._not_found(inputs.id, queue)
            # Rank among active entries only (done/removed excluded).
            active = sorted(
                [e for e in queue if e.get("status") not in ("done", "removed")],
                key=lambda e: (e.get("order") or 0),
            )
            rank = next((i + 1 for i, e in enumerate(active) if e.get("id") == inputs.id), 0)
            if rank <= 1:
                return MutationResult(
                    ok=False, id=inputs.id, entry=QueueEntry(**entry),
                    queue_size=len(queue), banner=self._store.banner_counts(),
                    message=f"{inputs.id!r} is already at position 1; can't move up.",
                )
            self._reorder_move_to(queue, inputs.id, rank - 1)
            self._store.save_queue(queue)
            updated = self._find_entry(queue, inputs.id)
            return MutationResult(
                ok=True, id=inputs.id, entry=QueueEntry(**updated),
                queue_size=len(queue), banner=self._store.banner_counts(),
                message=f"Moved {inputs.id!r} to position {updated.get('order')}.",
            )

    @action(description="Move an entry one position later in the reading order.", input_schema=IdOnlyInputs, name="move-down")
    def move_down(self, inputs: IdOnlyInputs, context: Context) -> MutationResult:
        with self._store.lock():
            queue = self._store.load_queue()
            entry = self._find_entry(queue, inputs.id)
            if not entry:
                return self._not_found(inputs.id, queue)
            # Rank among active entries only (done/removed excluded).
            active = sorted(
                [e for e in queue if e.get("status") not in ("done", "removed")],
                key=lambda e: (e.get("order") or 0),
            )
            rank = next((i + 1 for i, e in enumerate(active) if e.get("id") == inputs.id), 0)
            if rank >= len(active):
                return MutationResult(
                    ok=False, id=inputs.id, entry=QueueEntry(**entry),
                    queue_size=len(queue), banner=self._store.banner_counts(),
                    message=f"{inputs.id!r} is already at the last position; can't move down.",
                )
            self._reorder_move_to(queue, inputs.id, rank + 1)
            self._store.save_queue(queue)
            updated = self._find_entry(queue, inputs.id)
            return MutationResult(
                ok=True, id=inputs.id, entry=QueueEntry(**updated),
                queue_size=len(queue), banner=self._store.banner_counts(),
                message=f"Moved {inputs.id!r} to position {updated.get('order')}.",
            )

    @action(description="Move an entry to a specific position in the reading order.", input_schema=MoveToInputs, name="move-to")
    def move_to(self, inputs: MoveToInputs, context: Context) -> MutationResult:
        with self._store.lock():
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
        return sync_from_mendeley_run(
            self._store,
            collection_name,
            launch_command,
            inputs.dry_run,
            self._mendeley_cache(),
            self._log_event,
        )

    # ------------------------------------------------------------------
    # Ordering helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _reorder_move_to(queue: list[dict[str, Any]], target_id: str, new_position: int) -> None:
        """Mutate queue in-place: move `target_id` to `new_position`, shifting
        other active (non-done, non-removed) entries to maintain contiguous 1-based ordering.
        Done/removed entries are excluded so their order values don't interfere."""
        # Only active entries participate; normalize to 1-based before moving.
        active = sorted(
            [e for e in queue if e.get("status") not in ("done", "removed")],
            key=lambda e: (e.get("order") or 0),
        )
        for i, e in enumerate(active):
            e["order"] = i + 1

        target = next((e for e in active if e.get("id") == target_id), None)
        if target is None:
            # Entry is done/removed or absent — no-op.
            return

        old_position = target["order"]
        new_position = max(1, min(new_position, len(active)))
        if old_position == new_position:
            return

        if new_position < old_position:
            for e in active:
                pos = e.get("order", 0)
                if new_position <= pos < old_position and e.get("id") != target_id:
                    e["order"] = pos + 1
        else:
            for e in active:
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
        authors = normalize_mendeley_authors(doc.get("authors"))
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

    def _apply_status_transition(self, entry: dict, status: str) -> str:
        """Mutate entry in-place for a status change. Stamps started/finished. Returns previous status."""
        previous = entry.get("status", "queued")
        entry["status"] = status
        ts = datetime.now().isoformat()
        if status == "reading" and not entry.get("started"):
            entry["started"] = ts
        elif status == "done" and not entry.get("finished"):
            entry["finished"] = ts
        return previous

    def _set_status(self, entry_id: str, status: str) -> MutationResult:
        with self._store.lock():
            queue = self._store.load_queue()
            entry = self._find_entry(queue, entry_id)
            if not entry:
                return self._not_found(entry_id, queue)
            previous = self._apply_status_transition(entry, status)
            self._store.save_queue(queue)
            self._log_event("set_status", id=entry_id, status=status, previous=previous)
            return MutationResult(
                ok=True, id=entry_id, entry=QueueEntry(**entry),
                queue_size=len(queue), banner=self._store.banner_counts(),
                message=f"Set status to {status!r} for {entry_id!r} (was {previous!r}).",
            )

    def _log_event(self, event: str, **fields: Any) -> None:
        RunLog(self.name).append({"event": event, **fields})


def on_startup(context) -> None:  # noqa: ARG001
    from docent.utils.paths import data_dir
    from docent.ui import get_console
    from .reading_notify import check_deadlines
    for alert in check_deadlines(data_dir() / "reading"):
        get_console().print(f"[yellow]READING DEADLINE:[/] {alert}")

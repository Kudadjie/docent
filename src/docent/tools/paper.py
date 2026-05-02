"""Paper-pipeline tool: reading queue + (eventually) Mendeley sync.

Step 7b: first action `add`. Step 8: simple CRUD batch.
Each new action reuses the helpers below; mutations append a run-log entry
via `docent.learning.RunLog` so future heuristics (auto-priority etc.) can
read recent history.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from docent.config import write_setting
from docent.core import Context, ProgressEvent, Tool, action, register_tool
from docent.learning import RunLog
from docent.tools.paper_store import BannerCounts, PaperQueueStore
from docent.tools.mendeley_cache import MendeleyCache
from docent.tools.mendeley_client import (
    list_documents as mendeley_list_documents,
    list_folders as mendeley_list_folders,
    lookup_doi as mendeley_lookup_doi,
    search_library as mendeley_search_library,
)
from docent.tools.paper_sync import download_pdf, move_to_watch, unpaywall_lookup
from docent.utils.paths import cache_dir, data_dir
from docent.utils.prompt import NoInteractiveError, prompt_for_path


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

_DEFAULT_DATABASE_DIR = "~/Documents/Papers"
_KNOWN_PAPER_KEYS = {"database_dir", "mendeley_watch_subdir", "unpaywall_email", "queue_collection"}
# `mendeley_mcp_command` is a list field; config-set only handles strings today.
# Power users can edit config.toml directly; defaulted to ["uvx", "mendeley-mcp"] in mendeley_client.


class QueueEntry(BaseModel):
    id: str
    title: str
    authors: str
    year: int | None = None
    doi: str | None = None
    added: str  # ISO date
    status: str = "queued"
    priority: str = "medium"
    course: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    file_status: str = "missing"
    keep_in_mendeley: bool = False
    pdf_path: str | None = None  # absolute path; reference-only, no copy. Step 9.
    promoted_at: str | None = None  # ISO timestamp when sync-promote moved the PDF into Watch. Step 11.3.
    mendeley_id: str | None = None  # Mendeley document id, populated by sync-mendeley. Step 11.4.
    title_is_filename_stub: bool = False  # legacy: marked when title came from filename heuristic. Kept for backward-compat on existing queues; no longer drives logic.

    @model_validator(mode="after")
    def _require_identifier(self) -> "QueueEntry":
        # Identifier-free entries (no PDF AND no DOI AND no Mendeley id) caused
        # real-data sync-pull to fetch random papers. Mendeley-keyed entries
        # (Step 11.6 sync-from-mendeley) are persistable without DOI/PDF
        # because mendeley_id is itself a stable, definitive identifier.
        if not self.pdf_path and not self.doi and not self.mendeley_id:
            raise ValueError(
                "QueueEntry requires pdf_path, doi, or mendeley_id — identifier-free entries are not allowed."
            )
        return self


class AddInputs(BaseModel):
    mendeley_id: str | None = Field(None, description="Mendeley document id; if supplied, an entry is upserted directly (metadata pulled fresh on next read). Without this, `add` prints guidance.")
    course: str | None = Field(None, description="Course shortname (e.g. 'thesis', 'hydrodynamics').")
    priority: str = Field("medium", description="Priority: critical|high|medium|low.")
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
    course: str | None = Field(None, description="Restrict to a course.")


class SearchInputs(BaseModel):
    query: str = Field(..., description="Case-insensitive substring matched against title, authors, notes, course, id, and tags.")


class StatsInputs(BaseModel):
    pass


class EditInputs(BaseModel):
    id: str = Field(..., description="Entry id to edit.")
    title: str | None = Field(None, description="New title.")
    authors: str | None = Field(None, description="New authors string.")
    year: int | None = Field(None, description="New year.")
    doi: str | None = Field(None, description="New DOI.")
    course: str | None = Field(None, description="New course shortname.")
    priority: str | None = Field(None, description="New priority (critical|high|medium|low).")
    notes: str | None = Field(None, description="New notes.")


class ExportInputs(BaseModel):
    format: str = Field("json", description="Output format: json | markdown.")
    course: str | None = Field(None, description="Filter by course.")
    status: str | None = Field(None, description="Filter by status (queued|reading|done).")


class ConfigShowInputs(BaseModel):
    pass


class ConfigSetInputs(BaseModel):
    key: str = Field(..., description="Setting key under the (paper) section, e.g. 'database_dir' or 'mendeley_watch_subdir'.")
    value: str = Field(..., description="New value. Use '' to clear. Paths may use '~'.")


class ConfigShowResult(BaseModel):
    config_path: str
    database_dir: str | None
    mendeley_watch_subdir: str | None
    mendeley_watch_resolved: str | None  # absolute path = database_dir / subdir, when both set
    unpaywall_email: str | None
    queue_collection: str  # Mendeley collection name defining queue membership (Step 11.6).


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
    by_priority: dict[str, int]
    by_course: dict[str, int]
    keeping: int
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


class SyncPullInputs(BaseModel):
    id: str | None = Field(None, description="Single entry id; if omitted, all queued entries with no PDF are tried.")
    dry_run: bool = Field(False, description="Resolve OA URLs but skip download; nothing is written.")


class SyncPullResult(BaseModel):
    """Per-entry buckets after running sync-pull.

    `downloaded`: {id, path}; `no_oa`: {id, doi_url, journal} (closed-access — user
    may have institutional access via the link); `not_found`: {id, reason}
    (no DOI resolvable, or DOI not in Unpaywall); `network_error`:
    {id, reason}; `already_has_file`: [id]; `dry_run_oa`: {id, pdf_url, doi_url}
    (only populated when dry_run=True). `message` is set on early-exit
    (missing config, etc.) and otherwise empty.
    """

    database_dir: str | None
    downloaded: list[dict[str, str]]
    no_oa: list[dict[str, str]]
    not_found: list[dict[str, str]]
    network_error: list[dict[str, str]]
    already_has_file: list[str]
    dry_run_oa: list[dict[str, str]]
    summary: str
    message: str = ""


class SyncPromoteInputs(BaseModel):
    id: str | None = Field(None, description="Single entry id; if omitted, all eligible entries (kept + has-file + not promoted) are tried.")
    dry_run: bool = Field(False, description="Report what would be moved without touching disk or queue.")


class SyncPromoteResult(BaseModel):
    """Per-entry buckets after running sync-promote.

    `promoted`: {id, watch_path} — file moved this run; `already_promoted`:
    [id] — promoted_at already set or filename already in Watch (no work);
    `healed`: {id, reason} — metadata updated to reflect a pre-existing
    Watch placement (manual-move or external-move); `missing_file`:
    {id, reason}; `not_eligible`: {id, reason} — auto mode skipping
    non-kept entries; `failed`: {id, error} — collisions or I/O errors.
    `dry_run_promote`: {id, watch_path} — only populated when dry_run=True.
    """

    database_dir: str | None
    watch_dir: str | None
    promoted: list[dict[str, str]]
    already_promoted: list[str]
    healed: list[dict[str, str]]
    missing_file: list[dict[str, str]]
    not_eligible: list[dict[str, str]]
    failed: list[dict[str, str]]
    dry_run_promote: list[dict[str, str]]
    summary: str
    message: str = ""


class SyncMendeleyInputs(BaseModel):
    id: str | None = Field(None, description="Single entry id; if omitted, all promoted entries lacking mendeley_id are tried.")
    dry_run: bool = Field(False, description="Resolve Mendeley matches but do not persist mendeley_id.")
    limit: int = Field(20, description="Max search results per query when DOI is unavailable.")


class SyncMendeleyResult(BaseModel):
    """Per-entry buckets after running sync-mendeley.

    `linked`: {id, mendeley_id} - newly linked this run; `already_linked`:
    [id] - mendeley_id already set; `not_found`: {id, reason} - Mendeley
    returned no match; `ambiguous`: {id, candidates} - >1 search hit, user
    must use `--id` and edit; `not_eligible`: {id, reason} - auto mode
    skipping non-promoted entries; `failed`: {id, error} - transport / auth
    failures (run `mendeley-auth login` if auth-shaped); `dry_run_link`:
    {id, mendeley_id} - only populated when dry_run=True. `message` carries
    early-exit reasons (no targets, etc.).
    """

    linked: list[dict[str, str]]
    already_linked: list[str]
    not_found: list[dict[str, str]]
    ambiguous: list[dict[str, Any]]
    not_eligible: list[dict[str, str]]
    failed: list[dict[str, str]]
    dry_run_link: list[dict[str, str]]
    summary: str
    message: str = ""


class SyncFromMendeleyInputs(BaseModel):
    dry_run: bool = Field(False, description="Resolve the collection and report what would change without writing the queue.")


class SyncFromMendeleyResult(BaseModel):
    """Per-doc buckets after running sync-from-mendeley.

    `queue_collection`: the configured collection name (echoed for the
    renderer); `folder_id`: resolved Mendeley folder id (None on early exit);
    `added`: {id, mendeley_id, title} - new sidecar entries created from the
    collection; `unchanged`: ids whose mendeley_id already matched a
    sidecar entry (idempotent re-run); `removed`: ids of sidecar entries
    whose mendeley_id is no longer in the collection (status flipped to
    'removed'); `failed`: {mendeley_id, error} - per-doc construction or
    persistence failures; `dry_run_added` / `dry_run_removed` populate only
    when dry_run=True. `message` carries early-exit reasons (collection
    missing, MCP transport error, etc.).
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
    watch_dir: str | None
    in_queue_with_file: list[str]  # ids
    in_queue_missing_file: list[str]  # ids — queue says we have it, disk says no
    orphan_pdfs: list[str]  # paths under database_dir not referenced by any queue entry
    promotable: list[str]  # ids: keep_in_mendeley=True + file present + not yet in Watch
    in_watch: list[str]  # filenames in Watch folder (sanity surface)
    summary: str
    message: str = ""  # populated only on early-exit (no database configured)


@register_tool
class PaperPipeline(Tool):
    """Reading queue + Mendeley sync (port of the paper-pipeline skill).

    Step 7b: `add`. Step 8: `next`, `show`, `search`, `stats`, `remove`,
    `edit`, `done`, `ready-to-read`, `mark-keeping`, `export`.
    """

    name = "paper"
    description = "Reading queue + Mendeley sync."
    category = "research"

    def __init__(self) -> None:
        self._store = PaperQueueStore(data_dir() / "paper")

    @action(
        description="Add a paper by Mendeley id, or print guidance for the drag-and-drop flow.",
        input_schema=AddInputs,
    )
    def add(self, inputs: AddInputs, context: Context) -> AddResult:
        # Mendeley owns metadata extraction now. Without --mendeley-id, surface
        # the drag-and-drop guidance: drop PDF in database_dir → Mendeley
        # auto-imports → drag into Docent-Queue collection → sync-from-mendeley.
        if not inputs.mendeley_id:
            collection = context.settings.paper.queue_collection
            return AddResult(
                added=False, id="", title="",
                queue_size=len(self._store.load_index()),
                banner=self._store.banner_counts(),
                message=(
                    "Drop the PDF in your paper.database_dir (Mendeley auto-imports it), "
                    f"drag it into the {collection!r} collection in Mendeley, then run "
                    "`docent paper sync-from-mendeley`. "
                    "Or pass --mendeley-id to upsert a sidecar entry now."
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
                    f"Use --force to update, or `docent paper edit` to change fields."
                ),
            )

        # Minimal stub entry — fields get overlaid fresh from Mendeley on next read.
        existing_ids = {e.get("id") for e in queue if e.get("id")}
        base_id = f"mendeley-{mid[:8]}"
        entry_id = base_id
        suffix = 1
        while entry_id in existing_ids and (not existing or existing.get("id") != entry_id):
            suffix += 1
            entry_id = f"{base_id}-{suffix}"
        if existing:
            entry_id = existing.get("id") or entry_id

        new_entry = QueueEntry(
            id=entry_id,
            title=existing.get("title") if existing else "(pending Mendeley sync)",
            authors=existing.get("authors") if existing else "Unknown",
            year=existing.get("year") if existing else None,
            doi=existing.get("doi") if existing else None,
            added=existing.get("added") if existing else datetime.now().date().isoformat(),
            priority=inputs.priority,
            course=inputs.course,
            notes=inputs.notes,
            mendeley_id=mid,
        )

        if existing:
            queue = [e for e in queue if e.get("id") != entry_id]
        queue.append(new_entry.model_dump())
        self._store.save_queue(queue)
        self._log_event("add", id=entry_id, replaced=bool(existing),
                        priority=inputs.priority, course=inputs.course,
                        mendeley_id=mid)

        verb = "Updated" if existing else "Added"
        return AddResult(
            added=True,
            id=entry_id,
            title=new_entry.title,
            queue_size=len(queue),
            banner=self._store.banner_counts(),
            message=(
                f"{verb} {entry_id!r} (mendeley_id={mid}, queue size: {len(queue)}). "
                f"Run `docent paper next` to see fresh metadata."
            ),
        )

    @action(description="Show the next paper to read (highest-priority queued).", input_schema=NextInputs)
    def next(self, inputs: NextInputs, context: Context) -> MutationResult:
        queue = self._store.load_queue()
        queue = self._apply_overlay(queue, self._load_mendeley_overlay(context))
        candidates = [e for e in queue if e.get("status") == "queued"]
        if inputs.course:
            candidates = [e for e in candidates if e.get("course") == inputs.course]
        if not candidates:
            scope = f" for course {inputs.course!r}" if inputs.course else ""
            return MutationResult(
                ok=False, id="", entry=None, queue_size=len(queue),
                banner=self._store.banner_counts(),
                message=f"No queued papers{scope}.",
            )
        best = sorted(
            candidates,
            key=lambda e: (PRIORITY_ORDER.get(e.get("priority", "medium"), 4), e.get("added", "")),
        )[0]
        return MutationResult(
            ok=True, id=best["id"], entry=QueueEntry(**best),
            queue_size=len(queue), banner=self._store.banner_counts(),
            message=f"Read next: {best['title']!r} ({best.get('priority','medium')}, added {best.get('added','')}).",
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
                e.get("course") or "",
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
        by_priority: dict[str, int] = {}
        by_course: dict[str, int] = {}
        keeping = 0
        for e in queue:
            s = e.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
            p = e.get("priority", "unknown")
            by_priority[p] = by_priority.get(p, 0) + 1
            c = e.get("course") or "(none)"
            by_course[c] = by_course.get(c, 0) + 1
            if e.get("keep_in_mendeley"):
                keeping += 1
        return StatsResult(
            total=len(queue), by_status=by_status, by_priority=by_priority,
            by_course=by_course, keeping=keeping, banner=self._store.banner_counts(),
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

    @action(description="Edit fields on an existing entry.", input_schema=EditInputs)
    def edit(self, inputs: EditInputs, context: Context) -> MutationResult:
        queue = self._store.load_queue()
        entry = self._find_entry(queue, inputs.id)
        if not entry:
            return self._not_found(inputs.id, queue)
        updates = inputs.model_dump(exclude={"id"}, exclude_none=True)
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
    def ready_to_read(self, inputs: IdOnlyInputs, context: Context) -> MutationResult:
        return self._set_status(inputs.id, "reading")

    @action(description="Flag an entry to be kept in Mendeley (used by future sync ops).", input_schema=IdOnlyInputs)
    def mark_keeping(self, inputs: IdOnlyInputs, context: Context) -> MutationResult:
        queue = self._store.load_queue()
        entry = self._find_entry(queue, inputs.id)
        if not entry:
            return self._not_found(inputs.id, queue)
        entry["keep_in_mendeley"] = True
        self._store.save_queue(queue)
        self._log_event("mark_keeping", id=inputs.id)
        return MutationResult(
            ok=True, id=inputs.id, entry=QueueEntry(**entry),
            queue_size=len(queue), banner=self._store.banner_counts(),
            message=f"Marked {inputs.id!r} for keeping.",
        )

    @action(description="Export the queue (or a filtered subset).", input_schema=ExportInputs)
    def export(self, inputs: ExportInputs, context: Context) -> ExportResult:
        queue = self._store.load_queue()
        filtered = queue
        if inputs.course:
            filtered = [e for e in filtered if e.get("course") == inputs.course]
        if inputs.status:
            filtered = [e for e in filtered if e.get("status") == inputs.status]
        if inputs.format == "json":
            content = json.dumps(filtered, indent=2, ensure_ascii=False)
        elif inputs.format == "markdown":
            lines = [
                "| id | title | authors | year | priority | status |",
                "|---|---|---|---|---|---|",
            ]
            for e in filtered:
                year = e.get("year")
                lines.append(
                    f"| {e.get('id','')} | {e.get('title','')} | {e.get('authors','')} | "
                    f"{year if year is not None else ''} | {e.get('priority','')} | {e.get('status','')} |"
                )
            content = "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {inputs.format!r}. Use 'json' or 'markdown'.")
        return ExportResult(format=inputs.format, count=len(filtered), content=content)

    @action(description="Show the configured paper settings (database, Mendeley watch).", input_schema=ConfigShowInputs, name="config-show")
    def config_show(self, inputs: ConfigShowInputs, context: Context) -> ConfigShowResult:
        from docent.utils.paths import config_file
        ps = context.settings.paper
        db = str(ps.database_dir) if ps.database_dir else None
        sub = ps.mendeley_watch_subdir
        resolved = (
            str((ps.database_dir.expanduser() / sub).resolve())
            if ps.database_dir and sub
            else None
        )
        return ConfigShowResult(
            config_path=str(config_file()),
            database_dir=db,
            mendeley_watch_subdir=sub,
            mendeley_watch_resolved=resolved,
            unpaywall_email=ps.unpaywall_email,
            queue_collection=ps.queue_collection,
        )

    @action(description="Set a paper setting (database_dir, mendeley_watch_subdir, unpaywall_email, queue_collection).", input_schema=ConfigSetInputs, name="config-set")
    def config_set(self, inputs: ConfigSetInputs, context: Context) -> ConfigSetResult:
        from docent.utils.paths import config_file
        if inputs.key not in _KNOWN_PAPER_KEYS:
            return ConfigSetResult(
                ok=False, key=inputs.key, value=inputs.value,
                config_path=str(config_file()),
                message=f"Unknown key {inputs.key!r}. Known: {sorted(_KNOWN_PAPER_KEYS)}.",
            )
        if inputs.key == "mendeley_watch_subdir" and Path(inputs.value).is_absolute():
            return ConfigSetResult(
                ok=False, key=inputs.key, value=inputs.value,
                config_path=str(config_file()),
                message="mendeley_watch_subdir must be relative to database_dir (e.g. 'Watch'), not an absolute path.",
            )
        path = write_setting(f"paper.{inputs.key}", inputs.value)
        return ConfigSetResult(
            ok=True, key=inputs.key, value=inputs.value,
            config_path=str(path),
            message=f"Set paper.{inputs.key} = {inputs.value!r} in {path}.",
        )

    @action(
        description="Cross-tab queue against database_dir + Watch folder; report orphans, missing files, and promotable entries.",
        input_schema=SyncStatusInputs,
        name="sync-status",
    )
    def sync_status(self, inputs: SyncStatusInputs, context: Context) -> SyncStatusResult:
        empty = SyncStatusResult(
            database_dir=None, watch_dir=None,
            in_queue_with_file=[], in_queue_missing_file=[],
            orphan_pdfs=[], promotable=[], in_watch=[],
            summary="",
        )
        try:
            database_dir, err = self._require_database_dir(context)
        except NoInteractiveError as e:
            return empty.model_copy(update={"message": (
                f"paper.database_dir not configured. Run "
                f"`docent paper config-set database_dir <path>` or set "
                f"DOCENT_PAPER__DATABASE_DIR. ({e})"
            )})
        if database_dir is None:
            return empty.model_copy(update={
                "message": err or "Cancelled - no database folder configured.",
            })
        if not database_dir.is_dir():
            return empty.model_copy(update={
                "database_dir": str(database_dir),
                "message": f"database_dir does not exist: {database_dir}.",
            })

        watch_subdir = context.settings.paper.mendeley_watch_subdir
        watch_dir = (database_dir / watch_subdir) if watch_subdir else None
        db_pdfs, watch_pdfs = PaperQueueStore.list_database_pdfs(database_dir, watch_subdir)

        queue = self._store.load_queue()
        tracked: dict[str, dict[str, Any]] = {}
        in_queue_with_file: list[str] = []
        in_queue_missing_file: list[str] = []
        for e in queue:
            pdf_path = e.get("pdf_path")
            if pdf_path:
                tracked[str(Path(pdf_path).resolve())] = e
                if Path(pdf_path).exists():
                    in_queue_with_file.append(e["id"])
                else:
                    in_queue_missing_file.append(e["id"])
            else:
                in_queue_missing_file.append(e["id"])

        orphan_pdfs = [
            str(p) for p in db_pdfs if str(p.resolve()) not in tracked
        ]
        watch_filenames = {p.name for p in watch_pdfs}
        promotable = [
            e["id"] for e in queue
            if e.get("keep_in_mendeley")
            and e.get("pdf_path")
            and Path(e["pdf_path"]).exists()
            and not e.get("promoted_at")
            and Path(e["pdf_path"]).name not in watch_filenames
        ]

        summary = (
            f"{len(in_queue_with_file)} matched, "
            f"{len(in_queue_missing_file)} missing, "
            f"{len(orphan_pdfs)} orphan PDF(s), "
            f"{len(promotable)} promotable, "
            f"{len(watch_pdfs)} in Watch."
        )
        return SyncStatusResult(
            database_dir=str(database_dir),
            watch_dir=str(watch_dir) if watch_dir else None,
            in_queue_with_file=sorted(in_queue_with_file),
            in_queue_missing_file=sorted(in_queue_missing_file),
            orphan_pdfs=sorted(orphan_pdfs),
            promotable=sorted(promotable),
            in_watch=sorted(watch_filenames),
            summary=summary,
        )

    @action(
        description="Try to fetch open-access PDFs for queued entries missing a file (Unpaywall by DOI).",
        input_schema=SyncPullInputs,
        name="sync-pull",
    )
    def sync_pull(self, inputs: SyncPullInputs, context: Context):
        empty = SyncPullResult(
            database_dir=None, downloaded=[], no_oa=[], not_found=[],
            network_error=[], already_has_file=[], dry_run_oa=[], summary="",
        )
        try:
            database_dir, err = self._require_database_dir(context)
        except NoInteractiveError as e:
            return empty.model_copy(update={"message": (
                f"paper.database_dir not configured. Run "
                f"`docent paper config-set database_dir <path>` or set "
                f"DOCENT_PAPER__DATABASE_DIR. ({e})"
            )})
        if database_dir is None:
            return empty.model_copy(update={"message": err or "Cancelled - no database folder configured."})
        if not database_dir.is_dir():
            return empty.model_copy(update={
                "database_dir": str(database_dir),
                "message": f"database_dir does not exist: {database_dir}.",
            })

        email = context.settings.paper.unpaywall_email
        if not email:
            return empty.model_copy(update={
                "database_dir": str(database_dir),
                "message": (
                    "Unpaywall requires an email to identify clients. Set one with "
                    "`docent paper config-set unpaywall_email <you@example.com>` "
                    "(used in the API request header only)."
                ),
            })

        queue = self._store.load_queue()
        if inputs.id is not None:
            targets = [e for e in queue if e.get("id") == inputs.id]
            if not targets:
                return empty.model_copy(update={
                    "database_dir": str(database_dir),
                    "message": f"No entry with id {inputs.id!r}.",
                })
        else:
            targets = [
                e for e in queue
                if not (e.get("pdf_path") and Path(e["pdf_path"]).exists())
            ]

        return self._sync_pull_run(targets, database_dir, email, inputs.dry_run, context)

    def _sync_pull_run(
        self,
        targets: list[dict[str, Any]],
        database_dir: Path,
        email: str,
        dry_run: bool,
        context: Context,
    ):
        downloaded: list[dict[str, str]] = []
        no_oa: list[dict[str, str]] = []
        not_found: list[dict[str, str]] = []
        network_error: list[dict[str, str]] = []
        already_has_file: list[str] = []
        dry_run_oa: list[dict[str, str]] = []
        mutated_ids: set[str] = set()

        yield ProgressEvent(phase="discover", message=f"{len(targets)} entry/entries to try.")

        for i, entry in enumerate(targets, 1):
            eid = entry.get("id", "?")
            yield ProgressEvent(phase="pull", current=i, total=len(targets), item=eid)

            pdf_path = entry.get("pdf_path")
            if pdf_path and Path(pdf_path).exists():
                already_has_file.append(eid)
                continue

            doi = entry.get("doi")
            if not doi:
                # Post-invariant: an entry with neither pdf_path nor doi can't
                # be persisted. If we still see one (legacy queue, manual edit),
                # fail fast — title-search produced wrong papers in real data.
                not_found.append({"id": eid, "reason": "insufficient-identifiers (no DOI; identifier-free entries can't be synced)"})
                yield ProgressEvent(phase="pull", level="warn", message=f"{eid}: insufficient identifiers")
                continue

            up = unpaywall_lookup(doi, email, context.executor)
            if up is None:
                network_error.append({"id": eid, "reason": "Unpaywall lookup failed (network or rate limit)"})
                yield ProgressEvent(phase="pull", level="error", message=f"{eid}: Unpaywall lookup failed")
                continue
            if up.get("status") == "not_found":
                not_found.append({"id": eid, "reason": "DOI not in Unpaywall index"})
                yield ProgressEvent(phase="pull", level="warn", message=f"{eid}: DOI not in Unpaywall")
                continue
            if not up.get("is_oa"):
                no_oa.append({
                    "id": eid,
                    "doi_url": up.get("doi_url") or f"https://doi.org/{doi}",
                    "journal": up.get("journal") or "",
                })
                continue
            pdf_url = up.get("pdf_url")
            doi_url = up.get("doi_url") or f"https://doi.org/{doi}"
            if not pdf_url:
                no_oa.append({"id": eid, "doi_url": doi_url, "journal": up.get("journal") or ""})
                continue

            if dry_run:
                dry_run_oa.append({"id": eid, "pdf_url": pdf_url, "doi_url": doi_url})
                yield ProgressEvent(phase="pull", message=f"{eid}: OA found at {pdf_url}")
                continue

            dest = database_dir / f"{eid}.pdf"
            yield ProgressEvent(phase="pull", message=f"{eid}: downloading", item=eid)
            ok = download_pdf(pdf_url, dest, context.executor)
            if not ok:
                network_error.append({"id": eid, "reason": f"download failed: {pdf_url}"})
                yield ProgressEvent(phase="pull", level="error", message=f"{eid}: download failed")
                continue

            entry["pdf_path"] = str(dest.resolve())
            entry["file_status"] = "found"
            downloaded.append({"id": eid, "path": str(dest.resolve())})
            mutated_ids.add(eid)

        if mutated_ids:
            queue = self._store.load_queue()
            by_id = {e.get("id"): e for e in queue}
            target_by_id = {t.get("id"): t for t in targets}
            for tid in mutated_ids:
                if tid in by_id and tid in target_by_id:
                    src = target_by_id[tid]
                    by_id[tid].update({
                        k: src[k] for k in ("doi", "pdf_path", "file_status") if k in src
                    })
            self._store.save_queue(queue)

        self._log_event(
            "sync_pull",
            tried=len(targets),
            downloaded=len(downloaded),
            no_oa=len(no_oa),
            not_found=len(not_found),
            network_error=len(network_error),
            dry_run=dry_run,
        )

        summary = (
            f"{len(downloaded)} downloaded, {len(no_oa)} closed-access, "
            f"{len(not_found)} not found, {len(network_error)} network error, "
            f"{len(already_has_file)} already had file"
            + (f", {len(dry_run_oa)} OA (dry-run)" if dry_run else "")
            + "."
        )
        if no_oa:
            summary += (
                f" Closed-access papers expose `doi_url` — try institutional access "
                f"(VPN / library proxy / OpenAthens) or interlibrary loan via the link."
            )
        return SyncPullResult(
            database_dir=str(database_dir),
            downloaded=downloaded,
            no_oa=no_oa,
            not_found=not_found,
            network_error=network_error,
            already_has_file=sorted(already_has_file),
            dry_run_oa=dry_run_oa,
            summary=summary,
        )

    @action(
        description="Move kept PDFs from database_dir into the Mendeley Watch folder; sets promoted_at.",
        input_schema=SyncPromoteInputs,
        name="sync-promote",
    )
    def sync_promote(self, inputs: SyncPromoteInputs, context: Context):
        empty = SyncPromoteResult(
            database_dir=None, watch_dir=None,
            promoted=[], already_promoted=[], healed=[],
            missing_file=[], not_eligible=[], failed=[], dry_run_promote=[],
            summary="",
        )
        try:
            database_dir, err = self._require_database_dir(context)
        except NoInteractiveError as e:
            return empty.model_copy(update={"message": (
                f"paper.database_dir not configured. Run "
                f"`docent paper config-set database_dir <path>` or set "
                f"DOCENT_PAPER__DATABASE_DIR. ({e})"
            )})
        if database_dir is None:
            return empty.model_copy(update={"message": err or "Cancelled - no database folder configured."})
        if not database_dir.is_dir():
            return empty.model_copy(update={
                "database_dir": str(database_dir),
                "message": f"database_dir does not exist: {database_dir}.",
            })

        watch_subdir = context.settings.paper.mendeley_watch_subdir
        if not watch_subdir:
            return empty.model_copy(update={
                "database_dir": str(database_dir),
                "message": (
                    "paper.mendeley_watch_subdir not configured. Run "
                    "`docent paper config-set mendeley_watch_subdir <relpath>` "
                    "(e.g. 'Mendeley Watch')."
                ),
            })
        watch_dir = (database_dir / watch_subdir).expanduser()

        queue = self._store.load_queue()
        if inputs.id is not None:
            targets = [e for e in queue if e.get("id") == inputs.id]
            if not targets:
                return empty.model_copy(update={
                    "database_dir": str(database_dir),
                    "watch_dir": str(watch_dir),
                    "message": f"No entry with id {inputs.id!r}.",
                })
            single_id_mode = True
        else:
            targets = list(queue)
            single_id_mode = False

        return self._sync_promote_run(
            targets, database_dir, watch_dir, single_id_mode, inputs.dry_run, context
        )

    def _sync_promote_run(
        self,
        targets: list[dict[str, Any]],
        database_dir: Path,
        watch_dir: Path,
        single_id_mode: bool,
        dry_run: bool,
        context: Context,
    ):
        promoted: list[dict[str, str]] = []
        already_promoted: list[str] = []
        healed: list[dict[str, str]] = []
        missing_file: list[dict[str, str]] = []
        not_eligible: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []
        dry_run_promote: list[dict[str, str]] = []
        mutated: dict[str, dict[str, Any]] = {}

        yield ProgressEvent(phase="discover", message=f"{len(targets)} entry/entries to consider.")

        for i, entry in enumerate(targets, 1):
            eid = entry.get("id", "?")
            yield ProgressEvent(phase="promote", current=i, total=len(targets), item=eid)

            if not single_id_mode and not entry.get("keep_in_mendeley"):
                not_eligible.append({"id": eid, "reason": "keep_in_mendeley=False (use --id to override)"})
                continue

            if entry.get("promoted_at"):
                already_promoted.append(eid)
                continue

            pdf_path = entry.get("pdf_path")
            if not pdf_path:
                missing_file.append({"id": eid, "reason": "no pdf_path tracked"})
                yield ProgressEvent(phase="promote", level="warn", message=f"{eid}: no pdf_path")
                continue

            src = Path(pdf_path)
            src_exists = src.exists()

            # Heal-on-already-in-watch: pdf_path resolves and is already inside watch_dir.
            if src_exists and self._path_in_watch(src, watch_dir):
                if dry_run:
                    already_promoted.append(eid)
                    continue
                ts = datetime.now().isoformat()
                mutated[eid] = {"promoted_at": ts}
                healed.append({"id": eid, "reason": "pdf_path already inside Watch — set promoted_at"})
                yield ProgressEvent(phase="promote", message=f"{eid}: already in Watch, healed metadata")
                continue

            # Heal-on-external-move: pdf_path doesn't resolve, but a file with that filename exists in Watch.
            if not src_exists:
                candidate = watch_dir / src.name
                if candidate.exists():
                    if dry_run:
                        already_promoted.append(eid)
                        continue
                    ts = datetime.now().isoformat()
                    new_pdf_path = str(candidate.resolve())
                    mutated[eid] = {"promoted_at": ts, "pdf_path": new_pdf_path, "file_status": "found"}
                    healed.append({"id": eid, "reason": f"file found in Watch as {src.name} — pdf_path repointed"})
                    yield ProgressEvent(phase="promote", message=f"{eid}: external move detected, healed pdf_path")
                    continue
                missing_file.append({"id": eid, "reason": f"pdf_path does not exist on disk: {src}"})
                yield ProgressEvent(phase="promote", level="warn", message=f"{eid}: file missing")
                continue

            dest = watch_dir / src.name
            if dry_run:
                dry_run_promote.append({"id": eid, "watch_path": str(dest)})
                yield ProgressEvent(phase="promote", message=f"{eid}: would move to {dest}")
                continue

            try:
                actual_dest = move_to_watch(src, watch_dir)
            except FileExistsError as e:
                failed.append({"id": eid, "error": str(e)})
                yield ProgressEvent(phase="promote", level="error", message=f"{eid}: {e}")
                continue
            except OSError as e:
                failed.append({"id": eid, "error": f"move failed: {e}"})
                yield ProgressEvent(phase="promote", level="error", message=f"{eid}: move failed: {e}")
                continue

            ts = datetime.now().isoformat()
            mutated[eid] = {
                "promoted_at": ts,
                "pdf_path": str(actual_dest.resolve()),
                "file_status": "found",
            }
            promoted.append({"id": eid, "watch_path": str(actual_dest.resolve())})

        if mutated:
            queue = self._store.load_queue()
            by_id = {e.get("id"): e for e in queue}
            for mid, fields in mutated.items():
                if mid in by_id:
                    by_id[mid].update(fields)
            self._store.save_queue(queue)

        self._log_event(
            "sync_promote",
            considered=len(targets),
            promoted=len(promoted),
            already_promoted=len(already_promoted),
            healed=len(healed),
            missing_file=len(missing_file),
            failed=len(failed),
            dry_run=dry_run,
        )

        summary = (
            f"{len(promoted)} promoted, {len(already_promoted)} already promoted, "
            f"{len(healed)} healed, {len(missing_file)} missing file, "
            f"{len(not_eligible)} not eligible, {len(failed)} failed"
            + (f", {len(dry_run_promote)} would-move (dry-run)" if dry_run else "")
            + "."
        )
        return SyncPromoteResult(
            database_dir=str(database_dir),
            watch_dir=str(watch_dir),
            promoted=promoted,
            already_promoted=sorted(already_promoted),
            healed=healed,
            missing_file=missing_file,
            not_eligible=not_eligible,
            failed=failed,
            dry_run_promote=dry_run_promote,
            summary=summary,
        )

    @action(
        description="Cross-check promoted entries against Mendeley library; populate mendeley_id on matches.",
        input_schema=SyncMendeleyInputs,
        name="sync-mendeley",
    )
    def sync_mendeley(self, inputs: SyncMendeleyInputs, context: Context):
        empty = SyncMendeleyResult(
            linked=[], already_linked=[], not_found=[], ambiguous=[],
            not_eligible=[], failed=[], dry_run_link=[], summary="",
        )

        queue = self._store.load_queue()
        if inputs.id is not None:
            targets = [e for e in queue if e.get("id") == inputs.id]
            if not targets:
                return empty.model_copy(update={"message": f"No entry with id {inputs.id!r}."})
            single_id_mode = True
        else:
            targets = list(queue)
            single_id_mode = False

        launch_command = context.settings.paper.mendeley_mcp_command  # None -> wrapper default
        return self._sync_mendeley_run(targets, single_id_mode, inputs.dry_run, inputs.limit, launch_command, context)

    def _sync_mendeley_run(
        self,
        targets: list[dict[str, Any]],
        single_id_mode: bool,
        dry_run: bool,
        limit: int,
        launch_command: list[str] | None,
        context: Context,
    ):
        linked: list[dict[str, str]] = []
        already_linked: list[str] = []
        not_found: list[dict[str, str]] = []
        ambiguous: list[dict[str, Any]] = []
        not_eligible: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []
        dry_run_link: list[dict[str, str]] = []
        mutated: dict[str, str] = {}  # id -> mendeley_id

        yield ProgressEvent(phase="discover", message=f"{len(targets)} entry/entries to consider.")

        for i, entry in enumerate(targets, 1):
            eid = entry.get("id", "?")
            yield ProgressEvent(phase="link", current=i, total=len(targets), item=eid)

            if not single_id_mode and not entry.get("promoted_at"):
                not_eligible.append({"id": eid, "reason": "not promoted (use --id to override)"})
                continue
            if entry.get("mendeley_id"):
                already_linked.append(eid)
                continue

            doi = entry.get("doi")
            mid: str | None = None
            search_candidates: list[dict[str, Any]] = []

            if doi:
                resp = mendeley_lookup_doi(doi, launch_command)
                err = resp.get("error")
                if err:
                    failed.append({"id": eid, "error": self._mendeley_failure_hint(err)})
                    yield ProgressEvent(phase="link", level="error", message=f"{eid}: {err}")
                    continue
                items = resp.get("items") or []
                if items:
                    mid = self._extract_mendeley_id(items[0])

            if mid is None:
                # Title fallback: build a single-string query (search tool only takes `query`).
                title = entry.get("title") or ""
                authors = entry.get("authors") or ""
                first_author = authors.split(",")[0].strip() if authors else ""
                query = f"{title} {first_author}".strip()
                if not query:
                    not_found.append({"id": eid, "reason": "no DOI or title to query"})
                    continue
                resp = mendeley_search_library(query, launch_command, limit=limit)
                err = resp.get("error")
                if err:
                    failed.append({"id": eid, "error": self._mendeley_failure_hint(err)})
                    yield ProgressEvent(phase="link", level="error", message=f"{eid}: {err}")
                    continue
                items = resp.get("items") or []
                if not items:
                    not_found.append({"id": eid, "reason": "Mendeley returned no match for DOI or title"})
                    continue
                if len(items) == 1:
                    mid = self._extract_mendeley_id(items[0])
                else:
                    search_candidates = items[:5]
                    ambiguous.append({
                        "id": eid,
                        "candidates": [self._candidate_summary(c) for c in search_candidates],
                    })
                    yield ProgressEvent(phase="link", level="warn", message=f"{eid}: {len(items)} candidates")
                    continue

            if mid is None:
                not_found.append({"id": eid, "reason": "match returned but no Mendeley id field"})
                continue

            if dry_run:
                dry_run_link.append({"id": eid, "mendeley_id": mid})
                yield ProgressEvent(phase="link", message=f"{eid}: would link to {mid}")
                continue

            mutated[eid] = mid
            linked.append({"id": eid, "mendeley_id": mid})

        if mutated:
            queue = self._store.load_queue()
            by_id = {e.get("id"): e for e in queue}
            for mid_eid, mendeley_id in mutated.items():
                if mid_eid in by_id:
                    by_id[mid_eid]["mendeley_id"] = mendeley_id
            self._store.save_queue(queue)

        self._log_event(
            "sync_mendeley",
            considered=len(targets),
            linked=len(linked),
            already_linked=len(already_linked),
            not_found=len(not_found),
            ambiguous=len(ambiguous),
            failed=len(failed),
            dry_run=dry_run,
        )

        summary = (
            f"{len(linked)} linked, {len(already_linked)} already linked, "
            f"{len(not_found)} not found, {len(ambiguous)} ambiguous, "
            f"{len(not_eligible)} not eligible, {len(failed)} failed"
            + (f", {len(dry_run_link)} would-link (dry-run)" if dry_run else "")
            + "."
        )
        if any("auth:" in f.get("error", "") for f in failed):
            summary += " Auth failure detected — run `mendeley-auth login` and retry."

        return SyncMendeleyResult(
            linked=linked,
            already_linked=sorted(already_linked),
            not_found=not_found,
            ambiguous=ambiguous,
            not_eligible=not_eligible,
            failed=failed,
            dry_run_link=dry_run_link,
            summary=summary,
        )

    @action(
        description="Reconcile the local reading queue with a Mendeley collection (default 'Docent-Queue').",
        input_schema=SyncFromMendeleyInputs,
        name="sync-from-mendeley",
    )
    def sync_from_mendeley(self, inputs: SyncFromMendeleyInputs, context: Context):
        collection_name = context.settings.paper.queue_collection
        launch_command = context.settings.paper.mendeley_mcp_command  # None -> wrapper default
        return self._sync_from_mendeley_run(collection_name, launch_command, inputs.dry_run)

    def _sync_from_mendeley_run(
        self, collection_name: str, launch_command: list[str] | None, dry_run: bool
    ):
        empty = SyncFromMendeleyResult(
            queue_collection=collection_name, folder_id=None,
            added=[], unchanged=[], removed=[], failed=[],
            dry_run_added=[], dry_run_removed=[], summary="",
        )

        # ---- discover: resolve folder name -> folder_id ----
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
                f"`docent paper config-set queue_collection <name>`.)"
            )})
        if len(matches) > 1:
            return empty.model_copy(update={"message": (
                f"Found {len(matches)} Mendeley collections named {collection_name!r} "
                f"(nested in different parents). Rename one in Mendeley, or change "
                f"`paper.queue_collection` to a unique name."
            )})
        folder_id = matches[0].get("id")
        if not isinstance(folder_id, str) or not folder_id:
            return empty.model_copy(update={"message": (
                f"Mendeley collection {collection_name!r} has no usable id; "
                f"this is unexpected — try toggling its name in Mendeley to refresh."
            )})

        # ---- discover: list documents in that folder ----
        yield ProgressEvent(phase="discover", message=f"Reading collection {collection_name!r} ({folder_id[:8]}…).")
        docs_resp = mendeley_list_documents(folder_id=folder_id, launch_command=launch_command)
        if docs_resp.get("error"):
            err = docs_resp["error"]
            return empty.model_copy(update={
                "folder_id": folder_id,
                "message": f"Could not list documents in {collection_name!r}: {self._mendeley_failure_hint(err)}",
            })
        docs = [d for d in (docs_resp.get("items") or []) if isinstance(d, dict)]
        yield ProgressEvent(phase="discover", message=f"Found {len(docs)} doc(s) in {collection_name!r}.")

        # ---- reconcile ----
        added: list[dict[str, str]] = []
        unchanged: list[str] = []
        removed: list[str] = []
        failed: list[dict[str, str]] = []
        dry_run_added: list[dict[str, str]] = []
        dry_run_removed: list[str] = []

        queue = self._store.load_queue()
        by_mendeley_id: dict[str, dict[str, Any]] = {
            e["mendeley_id"]: e for e in queue
            if e.get("mendeley_id")
        }
        existing_ids: set[str] = {e.get("id") for e in queue if e.get("id")}
        # Per-pass id reservations so two new docs that derive the same slug
        # both land cleanly (second one gets the mendeley_id suffix).
        reserved_ids: set[str] = set()
        in_collection: set[str] = set()
        new_entries: list[dict[str, Any]] = []

        for i, doc in enumerate(docs, 1):
            mid = self._extract_mendeley_id(doc)
            if not mid:
                failed.append({"mendeley_id": "", "error": "doc has no usable id"})
                continue
            in_collection.add(mid)
            yield ProgressEvent(phase="reconcile", current=i, total=len(docs), item=doc.get("title", mid)[:60])

            if mid in by_mendeley_id:
                unchanged.append(by_mendeley_id[mid].get("id") or mid)
                continue

            try:
                entry = self._build_entry_from_mendeley(
                    doc, mid, existing_ids | reserved_ids,
                )
            except Exception as e:  # noqa: BLE001 — pydantic ValidationError + our ValueErrors both bucket here.
                failed.append({"mendeley_id": mid, "error": str(e)})
                yield ProgressEvent(phase="reconcile", level="error", message=f"{mid[:8]}: {e}")
                continue

            reserved_ids.add(entry.id)
            if dry_run:
                dry_run_added.append({"id": entry.id, "mendeley_id": mid, "title": entry.title})
            else:
                new_entries.append(entry.model_dump())
                added.append({"id": entry.id, "mendeley_id": mid, "title": entry.title})

        # ---- removed branch: mendeley_id-bearing entries not in collection ----
        for e in queue:
            mid = e.get("mendeley_id")
            if not mid or mid in in_collection:
                continue
            if e.get("status") == "removed":
                continue  # already flagged on a prior run
            if dry_run:
                dry_run_removed.append(e.get("id", mid))
            else:
                removed.append(e.get("id", mid))

        # ---- persist (single save) ----
        if not dry_run and (new_entries or removed):
            queue = self._store.load_queue()  # re-read in case anything changed under us
            by_id = {e.get("id"): e for e in queue}
            for ne in new_entries:
                # If two passes raced (very unlikely) and id already exists, skip silently;
                # the next sync will re-converge.
                if ne["id"] not in by_id:
                    queue.append(ne)
            removed_set = set(removed)
            for e in queue:
                if e.get("id") in removed_set:
                    e["status"] = "removed"
            self._store.save_queue(queue)

        # Force readers to repopulate from fresh MCP data. We just paid for
        # a list_documents call; rather than seed the cache here, drop it so
        # the next reader re-fetches (fresher snapshot wins).
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
        self, doc: dict[str, Any], mendeley_id: str, taken_ids: set[str]
    ) -> "QueueEntry":
        """Snapshot title/authors/year/doi from a Mendeley list_documents
        payload into a new QueueEntry. The snapshot lets existing
        next/show/stats/search keep working on these entries today; Step 11.7
        will replace it with a read-through cache.

        `taken_ids` lets the caller avoid id collisions across the whole
        batch (existing queue + new entries created earlier in this pass)."""
        title = (doc.get("title") or "").strip() or "(untitled)"
        authors = self._normalize_mendeley_authors(doc.get("authors"))
        year = doc.get("year")
        if not isinstance(year, int):
            year = None
        # Mendeley returns DOIs under `identifiers: {"doi": "..."}` (see live
        # probe output); list_documents may also omit identifiers entirely.
        doi: str | None = None
        idents = doc.get("identifiers")
        if isinstance(idents, dict):
            d = idents.get("doi")
            if isinstance(d, str) and d.strip():
                doi = d.strip()

        base = self._derive_id(authors, year, title)
        if base in taken_ids:
            entry_id = f"{base}-{mendeley_id[:8]}"
        else:
            entry_id = base

        return QueueEntry(
            id=entry_id,
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            added=datetime.now().date().isoformat(),
            mendeley_id=mendeley_id,
            file_status="missing",  # Mendeley owns the file; docent's pdf_path is unused for these.
        )

    @staticmethod
    def _normalize_mendeley_authors(authors: Any) -> str:
        """Mendeley returns `authors` as a list of strings ('Smith, J.') in
        `list_documents`; sometimes a list of dicts in other endpoints. Join
        with '; ' so each author stays atomic — `_derive_id` only looks at
        text before the first comma, so the first author's 'Last, First' form
        is preserved."""
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
        """Library documents expose `id` (UUID); catalog items returned by
        `mendeley_get_by_doi` expose `catalog_id` instead. Both are stable
        Mendeley identifiers — store whichever the response carries.
        """
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
            "mendeley_id": PaperPipeline._extract_mendeley_id(item) or "",
            "title": str(title),
            "year": str(year) if year is not None else "",
            "authors": str(authors),
        }

    @staticmethod
    def _mendeley_failure_hint(error: str) -> str:
        if error.startswith("auth:"):
            return f"{error} (run `mendeley-auth login` to refresh tokens)"
        if "launch command not found" in error:
            return f"{error} (install with `uv tool install mendeley-mcp` or set paper.mendeley_mcp_command)"
        return error

    @staticmethod
    def _path_in_watch(pdf_path: Path, watch_dir: Path) -> bool:
        try:
            return watch_dir.resolve() in pdf_path.resolve().parents
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Shared helpers - every paper action reuses these.
    # Persistence + state-recompute helpers moved to PaperQueueStore at Step 10.7.
    # ------------------------------------------------------------------

    def _mendeley_cache(self) -> MendeleyCache:
        # Pass the import-site alias so tests that monkeypatch
        # `docent.tools.paper.mendeley_list_documents` route through the fake.
        return MendeleyCache(
            cache_dir() / "paper" / "mendeley_collection.json",
            list_documents=mendeley_list_documents,
            list_folders=mendeley_list_folders,
        )

    def _resolve_collection_folder_id_quiet(
        self, collection_name: str, launch_command: list[str] | None
    ) -> str | None:
        """Reader-side folder lookup. Delegates to the cache so the ~5s
        `list_folders` MCP round-trip only happens once per folder TTL.
        Returns None on transport / missing / ambiguous — callers fall back
        to the snapshot fields persisted in queue.json. The verbose,
        actionable-error version lives in `_sync_from_mendeley_run`."""
        return self._mendeley_cache().get_folder_id(collection_name, launch_command)

    def _load_mendeley_overlay(self, context: Context) -> dict[str, dict[str, Any]] | None:
        """Pull the cached Mendeley collection (or fetch + cache fresh).
        Returns `{mendeley_id: doc}` or None on any failure — None means
        readers use the queue.json snapshot unchanged.
        """
        ps = context.settings.paper
        collection_name = ps.queue_collection
        launch_command = ps.mendeley_mcp_command
        folder_id = self._resolve_collection_folder_id_quiet(collection_name, launch_command)
        if folder_id is None:
            return None
        return self._mendeley_cache().get_collection(folder_id, launch_command)

    @staticmethod
    def _overlay_entry(entry: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
        """Replace title/authors/year/doi in a queue entry with fresh
        Mendeley values. Caller passes the entry dict (mutates a shallow
        copy)."""
        out = dict(entry)
        title = (doc.get("title") or "").strip()
        if title:
            out["title"] = title
        authors = PaperPipeline._normalize_mendeley_authors(doc.get("authors"))
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
        """Return a new queue list with Mendeley fields overlaid on entries
        whose `mendeley_id` is in the overlay map. Entries without a
        `mendeley_id` (legacy) or without a matching cache hit pass
        through. `overlay=None` is a no-op (offline / unconfigured)."""
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

    def _require_database_dir(self, context: Context) -> tuple[Path | None, str | None]:
        """Return (path, None) on success; (None, None) on user cancel; (None, error_message) on invalid input.

        Raises NoInteractiveError under DOCENT_NO_INTERACTIVE. The CLI/caller
        owns rendering — this method never prints. Don't persist a path that
        doesn't exist (silent corruption of config.toml on typos).
        """
        ps = context.settings.paper
        if ps.database_dir is not None:
            return ps.database_dir.expanduser(), None
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
                f"`docent paper config-set database_dir <path>` once it exists. Not persisted."
            )
        write_setting("paper.database_dir", str(path))
        context.settings.paper.database_dir = path
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


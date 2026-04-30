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

from pydantic import BaseModel, Field

from docent.config import write_setting
from docent.core import Context, ProgressEvent, Tool, action, register_tool
from docent.learning import RunLog
from docent.tools.paper_store import BannerCounts, PaperQueueStore
from docent.utils.paths import data_dir
from docent.utils.prompt import NoInteractiveError, prompt_for_path


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

_DEFAULT_DATABASE_DIR = "~/Documents/Papers"
_KNOWN_PAPER_KEYS = {"database_dir", "mendeley_watch_subdir", "unpaywall_email"}


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


class AddInputs(BaseModel):
    title: str | None = Field(None, description="Paper title. Optional if --pdf supplied; explicit value overrides extracted.")
    authors: str | None = Field(None, description="Authors, comma-separated. Optional if --pdf supplied.")
    year: int | None = Field(None, description="Publication year.")
    doi: str | None = Field(None, description="DOI (e.g. '10.1234/foo'); triggers CrossRef lookup if supplied.")
    pdf: str | None = Field(None, description="Path to a PDF; metadata is extracted via DOI/CrossRef/PDF-info/filename fallback.")
    course: str | None = Field(None, description="Course shortname (e.g. 'thesis', 'hydrodynamics').")
    priority: str = Field("medium", description="Priority: critical|high|medium|low.")
    notes: str = Field("", description="Freeform notes.")
    force: bool = Field(False, description="Overwrite if an entry with the derived id already exists.")


class AddResult(BaseModel):
    added: bool
    id: str
    title: str
    queue_size: int
    banner: BannerCounts
    message: str
    metadata_source: str = "explicit"  # explicit | doi-crossref | pdf-doi-crossref | pdf-metadata | filename | none


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


class ScanInputs(BaseModel):
    folder: str | None = Field(None, description="Folder to walk recursively for *.pdf files. Defaults to the configured paper.database_dir.")
    course: str | None = Field(None, description="Course shortname applied to every added entry.")
    priority: str = Field("medium", description="Priority applied to every added entry.")
    force: bool = Field(False, description="Overwrite collisions (passed through to per-file add).")


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


class ScanResult(BaseModel):
    folder: str
    total_pdfs: int
    added: list[AddResult]
    skipped: list[AddResult]  # collisions or extraction failures
    failed: list[dict[str, str]]  # {path, error}
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

    @action(description="Add a paper to the reading queue.", input_schema=AddInputs)
    def add(self, inputs: AddInputs, context: Context) -> AddResult:
        if not inputs.pdf and not inputs.title and not inputs.doi:
            return AddResult(
                added=False, id="", title="",
                queue_size=len(self._store.load_index()),
                banner=self._store.banner_counts(),
                message="Must supply --title, --doi, or --pdf.",
                metadata_source="none",
            )

        if inputs.pdf and not Path(inputs.pdf).is_file():
            return AddResult(
                added=False, id="", title="",
                queue_size=len(self._store.load_index()),
                banner=self._store.banner_counts(),
                message=f"PDF not found at {inputs.pdf!r}.",
                metadata_source="none",
            )

        meta, source = self._resolve_metadata(inputs, context)
        title = meta.get("title")
        if not title:
            return AddResult(
                added=False, id="", title="",
                queue_size=len(self._store.load_index()),
                banner=self._store.banner_counts(),
                message="Could not extract metadata; supply --title manually.",
                metadata_source=source,
            )
        authors = meta.get("authors") or "Unknown"
        year = meta.get("year")
        doi = meta.get("doi")
        pdf_abs = str(Path(inputs.pdf).resolve()) if inputs.pdf else None

        entry_id = self._derive_id(authors, year, title)
        index = self._store.load_index()
        collision = index.get(entry_id)

        if collision and not inputs.force:
            return AddResult(
                added=False,
                id=entry_id,
                title=collision["title"],
                queue_size=len(index),
                banner=self._store.banner_counts(),
                message=(
                    f"Already in queue as '{entry_id}': {collision['title']!r}. "
                    f"Use --force to overwrite, or `docent paper edit` to change fields."
                ),
                metadata_source=source,
            )

        new_entry = QueueEntry(
            id=entry_id,
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            added=datetime.now().date().isoformat(),
            priority=inputs.priority,
            course=inputs.course,
            notes=inputs.notes,
            pdf_path=pdf_abs,
            file_status="found" if pdf_abs else "missing",
        )

        queue = self._store.load_queue()
        if collision:
            queue = [e for e in queue if e.get("id") != entry_id]
        queue.append(new_entry.model_dump())
        self._store.save_queue(queue)
        self._log_event("add", id=entry_id, replaced=bool(collision),
                        priority=inputs.priority, course=inputs.course,
                        metadata_source=source, has_pdf=bool(pdf_abs))

        verb = "Replaced" if collision else "Added"
        msg = f"{verb} '{entry_id}': {title!r} (queue size: {len(queue)}, source: {source})."
        if pdf_abs:
            msg += f" Tracking PDF at {pdf_abs} - don't move/rename it."
        return AddResult(
            added=True,
            id=entry_id,
            title=title,
            queue_size=len(queue),
            banner=self._store.banner_counts(),
            message=msg,
            metadata_source=source,
        )

    @action(description="Show the next paper to read (highest-priority queued).", input_schema=NextInputs)
    def next(self, inputs: NextInputs, context: Context) -> MutationResult:
        queue = self._store.load_queue()
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
        )

    @action(description="Set a paper setting (database_dir, mendeley_watch_subdir, unpaywall_email).", input_schema=ConfigSetInputs, name="config-set")
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

    @action(description="Scan a folder of PDFs and add each to the reading queue.", input_schema=ScanInputs)
    def scan(self, inputs: ScanInputs, context: Context):
        # Resolve folder (and any first-run prompt) outside the generator — Rich Live in `_drive_progress` eats prompts.
        folder, early = self._resolve_scan_folder(inputs, context)
        if early is not None:
            return early
        return self._scan_folder(folder, inputs, context)

    def _resolve_scan_folder(
        self, inputs: ScanInputs, context: Context
    ) -> tuple[Path | None, ScanResult | None]:
        """Returns (folder, None) on success, or (None, ScanResult(...)) on early exit."""
        if inputs.folder:
            folder = Path(inputs.folder).expanduser()
        else:
            try:
                folder, err = self._require_database_dir(context)
            except NoInteractiveError as e:
                return None, ScanResult(
                    folder="", total_pdfs=0,
                    added=[], skipped=[], failed=[],
                    queue_size=len(self._store.load_index()),
                    banner=self._store.banner_counts(),
                    message=(
                        f"No --folder given and paper.database_dir not configured. "
                        f"Run `docent paper config-set database_dir <path>` or set "
                        f"DOCENT_PAPER__DATABASE_DIR. ({e})"
                    ),
                )
            if folder is None:
                return None, ScanResult(
                    folder="", total_pdfs=0,
                    added=[], skipped=[], failed=[],
                    queue_size=len(self._store.load_index()),
                    banner=self._store.banner_counts(),
                    message=err or "Cancelled - no database folder configured.",
                )
        if not folder.is_dir():
            return None, ScanResult(
                folder=str(folder), total_pdfs=0,
                added=[], skipped=[], failed=[],
                queue_size=len(self._store.load_index()),
                banner=self._store.banner_counts(),
                message=f"Folder not found: {str(folder)!r}.",
            )
        return folder, None

    def _scan_folder(self, folder: Path, inputs: ScanInputs, context: Context):
        yield ProgressEvent(phase="discover", message=f"Scanning {folder}")
        pdfs = sorted(folder.rglob("*.pdf"))
        yield ProgressEvent(phase="discover", message=f"Found {len(pdfs)} PDF(s).")

        added: list[AddResult] = []
        skipped: list[AddResult] = []
        failed: list[dict[str, str]] = []

        for i, pdf in enumerate(pdfs, 1):
            yield ProgressEvent(
                phase="add", current=i, total=len(pdfs), item=pdf.name
            )
            sub_inputs = AddInputs(
                pdf=str(pdf),
                course=inputs.course,
                priority=inputs.priority,
                force=inputs.force,
            )
            try:
                result = self.add(sub_inputs, context)
            except Exception as e:
                failed.append({"path": str(pdf), "error": str(e)})
                yield ProgressEvent(
                    phase="add", level="error",
                    message=f"{pdf.name}: {e}",
                )
                continue
            if result.added:
                added.append(result)
            else:
                skipped.append(result)
                yield ProgressEvent(
                    phase="add", level="warn",
                    message=f"skipped {pdf.name}: {result.message}",
                )

        return ScanResult(
            folder=str(folder.resolve()),
            total_pdfs=len(pdfs),
            added=added,
            skipped=skipped,
            failed=failed,
            queue_size=len(self._store.load_index()),
            banner=self._store.banner_counts(),
            message=(
                f"Scanned {len(pdfs)} PDF(s) in {folder}: "
                f"{len(added)} added, {len(skipped)} skipped, {len(failed)} failed."
            ),
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
        description="Try to fetch open-access PDFs for queued entries missing a file (Unpaywall + CrossRef title fallback).",
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
                yield ProgressEvent(phase="pull", message=f"{eid}: searching CrossRef by title", item=eid)
                doi = self._crossref_title_search(
                    entry.get("title", ""), entry.get("authors", ""), context.executor
                )
                if doi:
                    entry["doi"] = doi  # persisted at end of loop iteration
                    mutated_ids.add(eid)
                else:
                    not_found.append({"id": eid, "reason": "no DOI on entry and CrossRef title search returned nothing"})
                    yield ProgressEvent(phase="pull", level="warn", message=f"{eid}: no DOI resolvable")
                    continue

            up = self._unpaywall_lookup(doi, email, context.executor)
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
            ok = self._download_pdf(pdf_url, dest, context.executor)
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

    # ------------------------------------------------------------------
    # Shared helpers - every paper action reuses these.
    # Persistence + state-recompute helpers moved to PaperQueueStore at Step 10.7.
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Step 9: metadata fallback chain (DOI -> CrossRef -> PDF info -> filename).
    # All helpers swallow exceptions and return None on failure so the chain
    # can fall through cleanly.
    # ------------------------------------------------------------------

    def _resolve_metadata(self, inputs: AddInputs, context: Context) -> tuple[dict[str, Any], str]:
        """Run fallback chain. Returns (metadata-dict, source-tag).

        Explicit CLI fields are folded in last and always win.
        """
        extracted: dict[str, Any] = {}
        source = "none"

        if inputs.doi:
            cr = self._crossref_lookup(inputs.doi, context.executor)
            if cr:
                extracted = cr
                source = "doi-crossref"

        if not extracted and inputs.pdf:
            pdf_meta = self._extract_pdf_metadata(inputs.pdf)
            if pdf_meta and pdf_meta.get("doi"):
                cr = self._crossref_lookup(pdf_meta["doi"], context.executor)
                if cr:
                    extracted = cr
                    source = "pdf-doi-crossref"
            if not extracted and pdf_meta and pdf_meta.get("title"):
                extracted = {k: v for k, v in pdf_meta.items() if k != "doi"}
                if pdf_meta.get("doi"):
                    extracted["doi"] = pdf_meta["doi"]
                source = "pdf-metadata"
            if not extracted.get("title"):
                fallback = self._filename_heuristic(inputs.pdf)
                # Keep any partial pdf metadata (e.g. /Author) and layer filename on top.
                extracted = {**fallback, **extracted}
                source = "filename"

        explicit: dict[str, Any] = {}
        if inputs.title:
            explicit["title"] = inputs.title
        if inputs.authors:
            explicit["authors"] = inputs.authors
        if inputs.year is not None:
            explicit["year"] = inputs.year
        if inputs.doi:
            explicit["doi"] = inputs.doi

        merged = {**extracted, **explicit}
        if source == "none" and explicit:
            source = "explicit"
        return merged, source

    def _crossref_lookup(self, doi: str, executor: Any) -> dict[str, Any] | None:
        """Shell out to curl for CrossRef. Returns {title, authors, year, doi} or None."""
        clean = doi.strip()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if clean.lower().startswith(prefix):
                clean = clean[len(prefix):]
                break
        url = f"https://api.crossref.org/works/{clean}"
        try:
            result = executor.run(
                ["curl", "-sS", "--max-time", "10",
                 "-H", "User-Agent: docent/0.1.0",
                 url],
                check=False,
            )
        except Exception:
            return None
        if result.returncode != 0 or not result.stdout:
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        msg = data.get("message")
        if not isinstance(msg, dict):
            return None
        title_list = msg.get("title") or []
        title = title_list[0].strip() if title_list else None
        if not title:
            return None
        authors_list = msg.get("author") or []
        # Format "Family Given, Family Given, ..." so _derive_id picks up the surname.
        authors_str = ", ".join(
            " ".join(filter(None, [a.get("family"), a.get("given")])) for a in authors_list
        ) or "Unknown"
        year = None
        issued = (msg.get("issued") or {}).get("date-parts") or []
        if issued and isinstance(issued[0], list) and issued[0]:
            try:
                year = int(issued[0][0])
            except (TypeError, ValueError):
                pass
        return {"title": title, "authors": authors_str, "year": year, "doi": clean}

    def _unpaywall_lookup(self, doi: str, email: str, executor: Any) -> dict[str, Any] | None:
        """Shell out to curl for Unpaywall. Returns a dict on success, None on transport failure.

        Success dict keys: `is_oa: bool`, `pdf_url: str | None`, `doi_url: str`,
        `journal: str | None`. A 404 (DOI not indexed) returns
        `{"status": "not_found"}` rather than None — we want to bucket it as
        not-found, not as a network error.
        """
        clean = doi.strip()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if clean.lower().startswith(prefix):
                clean = clean[len(prefix):]
                break
        url = f"https://api.unpaywall.org/v2/{clean}?email={email}"
        try:
            result = executor.run(
                ["curl", "-sS", "--max-time", "15",
                 "-w", "\n__HTTP_STATUS__%{http_code}",
                 "-H", "User-Agent: docent/0.1.0",
                 url],
                check=False,
            )
        except Exception:
            return None
        if result.returncode != 0 or not result.stdout:
            return None
        body, _, status_line = result.stdout.rpartition("\n__HTTP_STATUS__")
        try:
            status_code = int(status_line.strip())
        except ValueError:
            status_code = 0
        if status_code == 404:
            return {"status": "not_found"}
        if status_code != 200:
            return None
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return None
        best = data.get("best_oa_location") or {}
        journal = data.get("journal_name")
        return {
            "is_oa": bool(data.get("is_oa")),
            "pdf_url": best.get("url_for_pdf"),
            "doi_url": data.get("doi_url") or f"https://doi.org/{clean}",
            "journal": journal,
        }

    def _crossref_title_search(self, title: str, authors: str, executor: Any) -> str | None:
        """Resolve a DOI from a title (and optional first-author surname) via CrossRef.

        Returns the top hit's DOI or None. We do not fuzzy-match — CrossRef's
        relevance ranking is the filter. Caller decides whether to trust it.
        """
        if not title:
            return None
        from urllib.parse import quote_plus
        query = quote_plus(title.strip())
        url = f"https://api.crossref.org/works?query.bibliographic={query}&rows=3"
        if authors:
            first = authors.split(",")[0].strip().split()
            if first:
                surname = first[-1]
                url += f"&query.author={quote_plus(surname)}"
        try:
            result = executor.run(
                ["curl", "-sS", "--max-time", "10",
                 "-H", "User-Agent: docent/0.1.0",
                 url],
                check=False,
            )
        except Exception:
            return None
        if result.returncode != 0 or not result.stdout:
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        items = (data.get("message") or {}).get("items") or []
        for item in items:
            doi = item.get("DOI")
            if doi:
                return doi
        return None

    @staticmethod
    def _download_pdf(url: str, dest: Path, executor: Any) -> bool:
        """Download `url` to `dest`. Returns True iff curl exited 0 and a non-empty file landed.

        We don't sniff magic bytes — premature; revisit if real-data testing
        shows publishers handing back HTML paywall pages that masquerade as
        PDFs.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = executor.run(
                ["curl", "-sSL", "--max-time", "60",
                 "-H", "User-Agent: docent/0.1.0",
                 "-o", str(dest),
                 url],
                check=False,
            )
        except Exception:
            return False
        if result.returncode != 0:
            if dest.exists():
                try:
                    dest.unlink()
                except OSError:
                    pass
            return False
        return dest.exists() and dest.stat().st_size > 0

    @staticmethod
    def _extract_pdf_metadata(pdf_path: str) -> dict[str, Any] | None:
        """Read PDF info dict + scan first 5 pages for a DOI. Returns dict or None."""
        p = Path(pdf_path)
        if not p.is_file():
            return None
        try:
            from pypdf import PdfReader  # lazy import; keeps pypdf out of import-time cost
            reader = PdfReader(str(p))
        except Exception:
            return None
        out: dict[str, Any] = {}
        info = getattr(reader, "metadata", None)
        if info is not None:
            try:
                title = info.get("/Title")
                author = info.get("/Author")
            except Exception:
                title = author = None
            if title:
                out["title"] = str(title).strip()
            if author:
                out["authors"] = str(author).strip()
        doi_re = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)
        try:
            pages = reader.pages[:5]
        except Exception:
            pages = []
        for page in pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                continue
            m = doi_re.search(text)
            if m:
                out["doi"] = m.group(0).rstrip(".,;)")
                break
        return out or None

    @staticmethod
    def _filename_heuristic(pdf_path: str) -> dict[str, Any]:
        """Last-resort: title from filename stem, year from any 4-digit number.

        Year regex runs against the *normalized* title (underscores/hyphens
        collapsed to spaces) so Mendeley-style `Smith_2019_topic.pdf` resolves
        to year=2019 — `_` is a Python word char and would otherwise defeat `\b`.
        """
        stem = Path(pdf_path).stem
        title = re.sub(r"[_\-]+", " ", stem).strip()
        year_match = re.search(r"\b(?:19|20)\d{2}\b", title)
        year = int(year_match.group(0)) if year_match else None
        return {"title": title or "Untitled", "authors": "Unknown", "year": year}

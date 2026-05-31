"""Reading queue models — Pydantic schemas for inputs and results."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from docent.core.shapes import (
    DataTableShape,
    ErrorShape,
    MarkdownShape,
    MessageShape,
    MetricShape,
    Shape,
)

from .reading_store import BannerCounts

EntryStatus = Literal["queued", "reading", "done", "removed"]
EntryType = Literal["paper", "book", "book_chapter"]

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class QueueEntry(BaseModel):
    id: str
    title: str = ""  # Reference manager snapshot; overlay refreshes on read (Mendeley only).
    authors: str = ""  # Reference manager snapshot; overlay refreshes on read (Mendeley only).
    year: int | None = None
    doi: str | None = None
    type: EntryType = "paper"
    added: str  # ISO date
    status: EntryStatus = "queued"
    order: int = 0  # 1-based position in the reading queue; 0 = unordered.
    category: str | None = (
        None  # Sub-collection path, e.g. "CES701" or "CES701/Topic"; None = root.
    )
    deadline: str | None = None  # ISO date (YYYY-MM-DD), user-settable.
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    reference_id: str | None = None
    started: str | None = None  # ISO timestamp when status -> reading.
    finished: str | None = None  # ISO timestamp when status -> done.
    not_in_library: bool = False  # Flagged absent from all collections; cleared when it returns.
    not_in_parent_collection: bool = (
        False  # In a sub-collection only (removed from the root); cleared when re-added to parent.
    )
    manually_kept: bool = (
        False  # User chose to keep this entry after it was flagged as not_in_library.
    )
    manually_kept_at: str | None = None  # ISO timestamp of that decision.

    @field_validator("deadline", mode="before")
    @classmethod
    def _validate_deadline(cls, v: object) -> object:
        if v and isinstance(v, str) and v.strip():
            if not _ISO_DATE_RE.match(v.strip()):
                raise ValueError(f"deadline must be YYYY-MM-DD, got {v!r}")
        return v

    @model_validator(mode="after")
    def _require_identifier(self) -> QueueEntry:
        if not self.doi and not self.reference_id:
            raise ValueError(
                "QueueEntry requires doi or reference_id — identifier-free entries are not allowed."
            )
        return self


class AddInputs(BaseModel):
    pass


class AddResult(BaseModel):
    added: bool
    queue_size: int
    banner: BannerCounts
    message: str

    def to_shapes(self) -> list[Shape]:
        return [
            MarkdownShape(content=self.message),
            MessageShape(text=f"Queue: {self.queue_size} entries", level="info"),
        ]


class IdOnlyInputs(BaseModel):
    id: str = Field(..., description="Entry id (e.g. 'smith-2024-foo').")


class NextInputs(BaseModel):
    category: str | None = Field(
        None,
        description="Restrict to a category prefix (e.g. 'CES701' matches 'CES701' and 'CES701/Topic').",
    )


class SearchInputs(BaseModel):
    query: str = Field(
        ...,
        description="Case-insensitive substring matched against title, authors, notes, category, id, and tags.",
    )


class StatsInputs(BaseModel):
    pass


class EditInputs(BaseModel):
    id: str = Field(..., description="Entry id to edit.")
    status: Literal["queued", "reading", "done"] | None = Field(
        None, description="New status (queued|reading|done)."
    )
    order: int | None = Field(None, description="New reading order position (1 = read first).")
    type: EntryType | None = Field(None, description="Entry type: paper | book | book_chapter.")
    category: str | None = Field(
        None,
        description="Override category (e.g. 'CES701'). Normally auto-detected from the Mendeley sub-collection on sync.",
    )
    deadline: str | None = Field(None, description="New deadline (YYYY-MM-DD) or '' to clear.")
    notes: str | None = Field(None, description="New notes.")
    tags: list[str] | None = Field(None, description="Replace tag list.")

    @field_validator("deadline", mode="before")
    @classmethod
    def _validate_deadline(cls, v: object) -> object:
        if v and isinstance(v, str) and v.strip():
            if not _ISO_DATE_RE.match(v.strip()):
                raise ValueError(f"deadline must be YYYY-MM-DD, got {v!r}")
        return v


class SetDeadlineInputs(BaseModel):
    id: str = Field(..., description="Entry id to update.")
    deadline: str = Field(
        ..., description="ISO date deadline (YYYY-MM-DD). Pass '' to clear the deadline."
    )

    @field_validator("deadline", mode="before")
    @classmethod
    def _validate_deadline(cls, v: object) -> object:
        if v and isinstance(v, str) and v.strip():
            if not _ISO_DATE_RE.match(v.strip()):
                raise ValueError(f"deadline must be YYYY-MM-DD, got {v!r}")
        return v


class ExportInputs(BaseModel):
    format: Literal["json", "markdown"] = Field(
        "json", description="Output format: json | markdown."
    )
    category: str | None = Field(
        None, description="Filter by exact category path (e.g. 'CES701' or 'CES701/Topic')."
    )
    status: EntryStatus | None = Field(
        None, description="Filter by status (queued|reading|done|removed)."
    )


class ConfigShowInputs(BaseModel):
    pass


class ConfigSetInputs(BaseModel):
    key: str = Field(
        ...,
        description="Setting key under the [reading] section, e.g. 'database_dir' or 'queue_collection'.",
    )
    value: str = Field(..., description="New value. Use '' to clear. Paths may use '~'.")


class ConfigShowResult(BaseModel):
    config_path: str
    database_dir: str | None
    queue_collection: str
    mendeley_mcp_command: list[str] | None = None
    reference_manager: str = "mendeley"
    zotero_api_key: str | None = None  # pre-masked by caller
    zotero_library_id: str | None = None
    zotero_library_type: str = "user"

    def to_shapes(self) -> list[Shape]:
        mmc = (
            " ".join(self.mendeley_mcp_command)
            if self.mendeley_mcp_command
            else "(default: uvx mendeley-mcp)"
        )
        shapes = [
            MetricShape(label="Config", value=self.config_path),
            MetricShape(label="database_dir", value=self.database_dir or "(not set)"),
            MetricShape(label="queue_collection", value=self.queue_collection),
            MetricShape(label="reference_manager", value=self.reference_manager),
            MetricShape(label="mendeley_mcp_command", value=mmc),
        ]
        if self.reference_manager == "zotero":
            shapes += [
                MetricShape(label="zotero_api_key", value=self.zotero_api_key or "(not set)"),
                MetricShape(label="zotero_library_id", value=self.zotero_library_id or "(not set)"),
                MetricShape(label="zotero_library_type", value=self.zotero_library_type),
            ]
        return shapes


class ConfigSetResult(BaseModel):
    ok: bool
    key: str
    value: str
    config_path: str
    message: str

    def to_shapes(self) -> list[Shape]:
        return [
            MessageShape(text=self.message, level="success" if self.ok else "error"),
        ]


class MutationResult(BaseModel):
    ok: bool
    id: str
    entry: QueueEntry | None
    queue_size: int
    banner: BannerCounts
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok or self.entry is None:
            return [ErrorShape(reason=self.message)]
        e = self.entry
        lines: list[str] = [e.title]
        meta_parts = [p for p in [e.authors, str(e.year) if e.year else ""] if p and p != "Unknown"]
        if meta_parts:
            lines.append("  ·  ".join(meta_parts))
        detail_parts = [f"Order: {e.order}", f"Status: {e.status}"]
        if e.type and e.type != "paper":
            detail_parts.append(f"Type: {e.type.replace('_', ' ')}")
        if e.category:
            detail_parts.append(f"Category: {e.category}")
        if e.deadline:
            detail_parts.append(f"Deadline: {e.deadline}")
        lines.append("  ".join(detail_parts))
        if e.doi:
            lines.append(f"DOI: {e.doi}")
        if e.notes:
            lines.append(f"Notes: {e.notes}")
        shapes: list[Shape] = [MarkdownShape(content="\n".join(lines))]
        if self.message:
            shapes.append(MessageShape(text=self.message, level="info"))
        return shapes


class SearchResult(BaseModel):
    query: str
    matches: list[QueueEntry]
    total: int
    queue_size: int

    def to_shapes(self) -> list[Shape]:
        label = "match" if self.total == 1 else "matches"
        shapes: list[Shape] = [
            MessageShape(text=f"{self.total} {label} for {self.query!r}", level="info"),
        ]
        if self.matches:
            rows = []
            for e in self.matches:
                etype = (
                    (e.type or "paper").replace("_", " ") if (e.type or "paper") != "paper" else ""
                )
                rows.append(
                    [
                        str(e.order),
                        e.title,
                        e.authors if e.authors != "Unknown" else "",
                        str(e.year) if e.year else "",
                        etype,
                        e.category or "",
                        e.status,
                    ]
                )
            shapes.append(
                DataTableShape(
                    columns=["#", "Title", "Authors", "Year", "Type", "Category", "Status"],
                    rows=rows,
                )
            )
        return shapes


class StatsResult(BaseModel):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    banner: BannerCounts

    def to_shapes(self) -> list[Shape]:
        shapes: list[Shape] = [
            MetricShape(label="Total", value=self.total, unit="entries"),
            DataTableShape(
                columns=["Status", "Count"],
                rows=[[k, str(v)] for k, v in sorted(self.by_status.items())],
            ),
        ]
        if self.by_category:
            shapes.append(
                DataTableShape(
                    columns=["Category", "Count"],
                    rows=[[k or "(none)", str(v)] for k, v in sorted(self.by_category.items())],
                )
            )
        return shapes


class ExportResult(BaseModel):
    format: str
    count: int
    content: str

    def to_shapes(self) -> list[Shape]:
        return [
            MessageShape(text=f"Exported {self.count} entries ({self.format})", level="info"),
            MarkdownShape(content=self.content),
        ]


class QueueClearInputs(BaseModel):
    yes: bool = Field(
        False,
        description="Confirm: actually clear the queue. Without this, the action reports the size and exits.",
    )


class QueueClearResult(BaseModel):
    cleared: bool
    removed_count: int
    queue_size: int
    banner: BannerCounts
    message: str

    def to_shapes(self) -> list[Shape]:
        return [
            MessageShape(text=self.message, level="success" if self.cleared else "warning"),
        ]


class SyncStatusInputs(BaseModel):
    pass


class SyncFromLibraryInputs(BaseModel):
    dry_run: bool = Field(
        False,
        description="Resolve the collection and report what would change without writing the queue.",
    )


# Back-compat alias — external code may import the old name.
SyncFromMendeleyInputs = SyncFromLibraryInputs


class SyncFromLibraryResult(BaseModel):
    """Per-doc buckets after running sync-from-library.

    `added`: {id, reference_id, title}; `unchanged`: entry ids;
    `flagged`: entry ids newly marked not_in_library (pending user decision);
    `removed`: entry ids with status='removed' (set by user action, not sync);
    `cleared`: entry ids whose not_in_library flag was cleared (back in collection);
    `failed`: {reference_id, error};
    dry-run variants populate only when dry_run=True.
    `message` carries early-exit reasons (collection missing, MCP transport error).
    """

    queue_collection: str
    folder_id: str | None
    added: list[dict[str, str]]
    unchanged: list[str]
    flagged: list[str] = []  # newly flagged as not_in_library (absent from all collections)
    cleared: list[str] = []  # not_in_library / manually_kept cleared (returned to collection)
    not_in_parent: list[str] = []  # newly flagged as not_in_parent_collection (in sub only)
    cleared_parent: list[str] = []  # not_in_parent_collection cleared (re-added to root)
    removed: list[str] = []  # kept for dry-run compat; always empty from live sync
    failed: list[dict[str, str]]
    dry_run_added: list[dict[str, str]]
    dry_run_removed: list[str]
    summary: str
    message: str = ""

    def to_shapes(self) -> list[Shape]:
        if self.message:
            return [MessageShape(text=self.message, level="warning")]
        is_dry = bool(self.dry_run_added or self.dry_run_removed)
        actual_added = self.dry_run_added if is_dry else self.added
        actual_removed = self.dry_run_removed if is_dry else self.removed
        shapes: list[Shape] = [
            MessageShape(text=f"Collection: {self.queue_collection}", level="info"),
            MetricShape(label="Added", value=len(actual_added)),
            MetricShape(label="Unchanged", value=len(self.unchanged)),
            MetricShape(label="Flagged (not in any collection)", value=len(self.flagged)),
            MetricShape(label="Flagged (sub-collection only)", value=len(self.not_in_parent)),
            MetricShape(label="Cleared (returned to collection)", value=len(self.cleared)),
            MetricShape(label="Cleared (returned to parent)", value=len(self.cleared_parent)),
            MetricShape(label="Removed (dry-run)", value=len(actual_removed)),
            MetricShape(label="Failed", value=len(self.failed)),
        ]
        if actual_added:
            shapes.append(
                DataTableShape(
                    columns=["id", "title"],
                    rows=[
                        [item.get("id", ""), item.get("title", "")[:60]]
                        for item in actual_added[:10]
                    ],
                )
            )
        if self.flagged:
            shapes.append(
                DataTableShape(
                    columns=["entry id"],
                    rows=[[eid] for eid in self.flagged[:10]],
                )
            )
        if self.failed:
            shapes.append(
                DataTableShape(
                    columns=["reference_id", "error"],
                    rows=[
                        [item.get("reference_id", "")[:12], item.get("error", "")]
                        for item in self.failed
                    ],
                )
            )
        return shapes


# Back-compat alias — external code may import the old name.
SyncFromMendeleyResult = SyncFromLibraryResult


class SyncStatusResult(BaseModel):
    database_dir: str | None
    queue_size: int
    database_pdfs: list[str]
    summary: str
    message: str = ""

    def to_shapes(self) -> list[Shape]:
        shapes: list[Shape] = [
            MetricShape(label="Database", value=self.database_dir or "(not configured)"),
            MetricShape(label="Queue", value=self.queue_size, unit="entries"),
            MetricShape(label="PDFs in database", value=len(self.database_pdfs)),
        ]
        if self.message:
            shapes.append(MessageShape(text=self.message, level="warning"))
        return shapes


class MoveToInputs(BaseModel):
    id: str = Field(..., description="Entry id to move.")
    position: int = Field(..., ge=1, description="New position (1 = read first).")

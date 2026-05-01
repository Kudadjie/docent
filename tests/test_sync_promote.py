"""Tests for `paper sync-promote` (Step 11.3).

Move kept PDFs from database_dir into the Mendeley Watch folder, set
`promoted_at`, and update `pdf_path` to point at the new location. Also
covers two heal branches: file already inside Watch (manual placement), and
external move where `pdf_path` rotted but the filename is in Watch.
"""
from __future__ import annotations

import inspect
import shutil
from pathlib import Path

from docent.config import load_settings
from docent.core.context import Context
from docent.execution import Executor
from docent.llm import LLMClient
from docent.tools.paper import (
    AddInputs,
    PaperPipeline,
    SyncPromoteInputs,
    SyncStatusInputs,
)


def _ctx(database_dir: Path | None = None, watch_subdir: str | None = "Watch") -> Context:
    settings = load_settings()
    if database_dir is not None:
        settings.paper.database_dir = database_dir
    settings.paper.mendeley_watch_subdir = watch_subdir
    return Context(settings=settings, llm=LLMClient(settings), executor=Executor())


def _make_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n%fake\n")
    return path


def _drain(maybe_gen):
    if not inspect.isgenerator(maybe_gen):
        return maybe_gen
    try:
        while True:
            next(maybe_gen)
    except StopIteration as e:
        return e.value


def _add_kept(tool: PaperPipeline, ctx: Context, pdf: Path, **add_kwargs) -> str:
    res = tool.add(AddInputs(pdf=str(pdf), **add_kwargs), ctx)
    queue = tool._store.load_queue()
    queue[0]["keep_in_mendeley"] = True
    tool._store.save_queue(queue)
    return res.id


def test_missing_watch_subdir_returns_message(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    ctx = _ctx(database_dir=db, watch_subdir=None)
    result = _drain(PaperPipeline().sync_promote(SyncPromoteInputs(), ctx))
    assert result.message and "mendeley_watch_subdir" in result.message
    assert result.promoted == []


def test_happy_path_moves_pdf_and_sets_promoted_at(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "kept.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    eid = _add_kept(tool, ctx, pdf, title="Kept", authors="Smith, J", year=2024)

    result = _drain(tool.sync_promote(SyncPromoteInputs(), ctx))
    assert len(result.promoted) == 1
    assert result.promoted[0]["id"] == eid

    # Original gone, dest exists, queue mutated.
    assert not pdf.exists()
    assert (db / "Watch" / "kept.pdf").exists()
    entry = tool._store.load_queue()[0]
    assert entry["promoted_at"] is not None
    assert entry["pdf_path"].endswith(str(Path("Watch") / "kept.pdf"))


def test_dry_run_does_not_move_or_mutate(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "kept.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    _add_kept(tool, ctx, pdf, title="Kept", authors="Smith, J", year=2024)

    result = _drain(tool.sync_promote(SyncPromoteInputs(dry_run=True), ctx))
    assert len(result.dry_run_promote) == 1
    assert result.promoted == []
    assert pdf.exists()
    assert not (db / "Watch" / "kept.pdf").exists()
    assert tool._store.load_queue()[0]["promoted_at"] is None


def test_already_promoted_is_skipped(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    watch = db / "Watch"
    watch.mkdir(parents=True)
    pdf_in_watch = _make_pdf(watch / "kept.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    _add_kept(tool, ctx, pdf_in_watch, title="Kept", authors="Smith, J", year=2024)
    queue = tool._store.load_queue()
    queue[0]["promoted_at"] = "2026-04-30T12:00:00"
    tool._store.save_queue(queue)

    result = _drain(tool.sync_promote(SyncPromoteInputs(), ctx))
    assert len(result.already_promoted) == 1
    assert result.promoted == []
    assert result.healed == []


def test_heal_when_pdf_already_in_watch(tmp_docent_home, tmp_path):
    """User added the PDF when it was already inside Watch (no promoted_at).
    Promote should not move; it should set promoted_at."""
    db = tmp_path / "Papers"
    watch = db / "Watch"
    watch.mkdir(parents=True)
    pdf_in_watch = _make_pdf(watch / "kept.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    _add_kept(tool, ctx, pdf_in_watch, title="Kept", authors="Smith, J", year=2024)

    result = _drain(tool.sync_promote(SyncPromoteInputs(), ctx))
    assert len(result.healed) == 1
    assert result.promoted == []
    # File untouched; metadata set.
    assert pdf_in_watch.exists()
    entry = tool._store.load_queue()[0]
    assert entry["promoted_at"] is not None


def test_heal_when_external_move_orphans_pdf_path(tmp_docent_home, tmp_path):
    """User added a PDF in DB root, then manually moved it into Watch outside
    Docent. pdf_path no longer resolves; promote should detect the file by
    name in Watch, repoint pdf_path, and set promoted_at."""
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "kept.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    _add_kept(tool, ctx, pdf, title="Kept", authors="Smith, J", year=2024)

    # Simulate external move.
    watch = db / "Watch"
    watch.mkdir(parents=True)
    shutil.move(str(pdf), str(watch / "kept.pdf"))
    assert not pdf.exists()

    result = _drain(tool.sync_promote(SyncPromoteInputs(), ctx))
    assert len(result.healed) == 1
    entry = tool._store.load_queue()[0]
    assert entry["promoted_at"] is not None
    assert entry["pdf_path"].endswith(str(Path("Watch") / "kept.pdf"))


def test_missing_file_bucket(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "ghost.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    _add_kept(tool, ctx, pdf, title="Ghost", authors="Doe, J", year=2023)
    pdf.unlink()  # gone, and no file in Watch either — missing.

    result = _drain(tool.sync_promote(SyncPromoteInputs(), ctx))
    assert len(result.missing_file) == 1
    assert result.promoted == []


def test_not_eligible_when_not_kept_in_auto_mode(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "unkept.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    tool.add(AddInputs(pdf=str(pdf), title="Unkept", authors="Smith, J", year=2024), ctx)
    # NOT marked keeping.

    result = _drain(tool.sync_promote(SyncPromoteInputs(), ctx))
    assert len(result.not_eligible) == 1
    assert result.promoted == []
    assert pdf.exists()


def test_single_id_overrides_keep_flag(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "unkept.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    res = tool.add(AddInputs(pdf=str(pdf), title="Unkept", authors="Smith, J", year=2024), ctx)
    # NOT marked keeping; single-id should still promote.

    result = _drain(tool.sync_promote(SyncPromoteInputs(id=res.id), ctx))
    assert len(result.promoted) == 1
    assert (db / "Watch" / "unkept.pdf").exists()


def test_collision_in_watch_is_failed_bucket(tmp_docent_home, tmp_path):
    """A different file with the same filename already lives in Watch. Move
    must not overwrite; entry should land in `failed` and the original DB
    file should remain in place."""
    db = tmp_path / "Papers"
    watch = db / "Watch"
    watch.mkdir(parents=True)
    pdf = _make_pdf(db / "kept.pdf")
    (watch / "kept.pdf").write_bytes(b"%PDF-1.4\n%different\n")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    _add_kept(tool, ctx, pdf, title="Kept", authors="Smith, J", year=2024)

    result = _drain(tool.sync_promote(SyncPromoteInputs(), ctx))
    assert len(result.failed) == 1
    assert result.promoted == []
    assert pdf.exists()  # original untouched
    entry = tool._store.load_queue()[0]
    assert entry["promoted_at"] is None


def test_sync_status_promoted_at_excludes_from_promotable(tmp_docent_home, tmp_path):
    """Even with the file still in DB root and not in Watch, a set
    `promoted_at` excludes the entry from `promotable`."""
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "kept.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    _add_kept(tool, ctx, pdf, title="Kept", authors="Smith, J", year=2024)
    queue = tool._store.load_queue()
    queue[0]["promoted_at"] = "2026-04-30T12:00:00"
    tool._store.save_queue(queue)

    result = tool.sync_status(SyncStatusInputs(), ctx)
    assert result.promotable == []

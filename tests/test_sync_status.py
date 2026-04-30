"""Tests for `paper sync-status` (Step 11.1).

Local-only cross-tab: queue.json × database_dir × Watch subdir. No network,
no Semantic Scholar. Each test sets up a tmp database_dir, points the
PaperSettings at it, and asserts bucket membership on the result.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from docent.config import load_settings
from docent.core.context import Context
from docent.execution import Executor
from docent.llm import LLMClient
from docent.tools.paper import AddInputs, PaperPipeline, SyncStatusInputs


def _ctx(database_dir: Path | None = None, watch_subdir: str | None = "Watch") -> Context:
    settings = load_settings()
    if database_dir is not None:
        settings.paper.database_dir = database_dir
    settings.paper.mendeley_watch_subdir = watch_subdir
    return Context(settings=settings, llm=LLMClient(settings), executor=Executor())


def _make_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Minimal valid-enough bytes; sync-status doesn't parse, just lists.
    path.write_bytes(b"%PDF-1.4\n%fake\n")
    return path


def test_no_database_configured(tmp_docent_home):
    """Without a configured database and no interactive prompt allowed,
    sync-status returns a populated `message` and empty buckets."""
    import os
    os.environ["DOCENT_NO_INTERACTIVE"] = "1"
    try:
        ctx = _ctx(database_dir=None)
        result = PaperPipeline().sync_status(SyncStatusInputs(), ctx)
        assert result.database_dir is None
        assert result.in_queue_with_file == []
        assert "not configured" in result.message
    finally:
        os.environ.pop("DOCENT_NO_INTERACTIVE", None)


def test_empty_database_empty_queue(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    ctx = _ctx(database_dir=db)
    result = PaperPipeline().sync_status(SyncStatusInputs(), ctx)
    assert result.database_dir == str(db)
    assert result.in_queue_with_file == []
    assert result.orphan_pdfs == []
    assert "0 matched" in result.summary


def test_matched_entry_with_file(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "smith2024.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db)
    tool.add(AddInputs(title="Topic", authors="Smith, J", year=2024, pdf=str(pdf)), ctx)

    result = tool.sync_status(SyncStatusInputs(), ctx)
    assert len(result.in_queue_with_file) == 1
    assert result.orphan_pdfs == []
    assert result.in_queue_missing_file == []


def test_orphan_pdf_in_database(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    _make_pdf(db / "stranger.pdf")

    ctx = _ctx(database_dir=db)
    result = PaperPipeline().sync_status(SyncStatusInputs(), ctx)
    assert len(result.orphan_pdfs) == 1
    assert result.orphan_pdfs[0].endswith("stranger.pdf")
    assert result.in_queue_with_file == []


def test_in_queue_missing_file(tmp_docent_home, tmp_path):
    """Queue entry references a pdf_path that no longer exists on disk."""
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "moved.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db)
    tool.add(AddInputs(title="Moved Paper", authors="Doe, J", year=2023, pdf=str(pdf)), ctx)
    pdf.unlink()  # simulate a move/delete after add

    result = tool.sync_status(SyncStatusInputs(), ctx)
    assert len(result.in_queue_missing_file) == 1
    assert result.in_queue_with_file == []


def test_watch_subdir_pdfs_excluded_from_orphans(tmp_docent_home, tmp_path):
    """PDFs under <database_dir>/<watch_subdir> are reported in `in_watch`,
    not as orphans in the main DB."""
    db = tmp_path / "Papers"
    watch = db / "Watch"
    watch.mkdir(parents=True)
    _make_pdf(db / "tracked.pdf")
    _make_pdf(watch / "in-watch.pdf")

    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    result = PaperPipeline().sync_status(SyncStatusInputs(), ctx)

    assert "in-watch.pdf" in result.in_watch
    assert all(not p.endswith("in-watch.pdf") for p in result.orphan_pdfs)
    assert any(p.endswith("tracked.pdf") for p in result.orphan_pdfs)


def test_promotable_kept_with_file_not_in_watch(tmp_docent_home, tmp_path):
    """An entry with keep_in_mendeley=True + file present + no copy in Watch is promotable."""
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "kept.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    tool.add(AddInputs(title="Kept", authors="Roe, A", year=2022, pdf=str(pdf)), ctx)
    # Mark keeping by directly mutating queue (mark_keeping action exists but we
    # are testing sync-status, not the keeping action — keep dependencies tight).
    queue = tool._store.load_queue()
    queue[0]["keep_in_mendeley"] = True
    tool._store.save_queue(queue)

    result = tool.sync_status(SyncStatusInputs(), ctx)
    assert len(result.promotable) == 1


def test_promotable_excludes_already_in_watch(tmp_docent_home, tmp_path):
    """If a same-name PDF already exists in Watch, the entry is treated as
    already promoted and excluded from `promotable`."""
    db = tmp_path / "Papers"
    watch = db / "Watch"
    watch.mkdir(parents=True)
    pdf = _make_pdf(db / "already.pdf")
    shutil.copy2(pdf, watch / "already.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db, watch_subdir="Watch")
    tool.add(AddInputs(title="Already", authors="Lee, B", year=2021, pdf=str(pdf)), ctx)
    queue = tool._store.load_queue()
    queue[0]["keep_in_mendeley"] = True
    tool._store.save_queue(queue)

    result = tool.sync_status(SyncStatusInputs(), ctx)
    assert result.promotable == []
    assert "already.pdf" in result.in_watch

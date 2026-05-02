"""Tests for `paper sync-status` (Step 11.1, simplified at Step 11.9).

Local-only cross-tab: queue.json × database_dir. Step 11.9 dropped the Watch
subdir model — database_dir IS the Mendeley watch folder, so promotable /
in_watch buckets are gone. Each test sets up a tmp database_dir, points the
PaperSettings at it, and asserts bucket membership on the result.
"""
from __future__ import annotations

from pathlib import Path

from docent.config import load_settings
from docent.core.context import Context
from docent.execution import Executor
from docent.llm import LLMClient
from docent.tools.paper import PaperPipeline, SyncStatusInputs


def _ctx(database_dir: Path | None = None) -> Context:
    settings = load_settings()
    if database_dir is not None:
        settings.paper.database_dir = database_dir
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


def test_matched_entry_with_file(tmp_docent_home, tmp_path, seed_queue_entry):
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "smith2024.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db)
    seed_queue_entry(tool, title="Topic", authors="Smith, J", year=2024, pdf_path=pdf)

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


def test_in_queue_missing_file(tmp_docent_home, tmp_path, seed_queue_entry):
    """Queue entry references a pdf_path that no longer exists on disk."""
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = _make_pdf(db / "moved.pdf")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db)
    seed_queue_entry(tool, title="Moved Paper", authors="Doe, J", year=2023, pdf_path=pdf)
    pdf.unlink()  # simulate a move/delete after add

    result = tool.sync_status(SyncStatusInputs(), ctx)
    assert len(result.in_queue_missing_file) == 1
    assert result.in_queue_with_file == []

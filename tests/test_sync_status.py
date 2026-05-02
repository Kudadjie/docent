"""Tests for `paper sync-status` (Step 11.1, redefined at Step 11.10).

Post-Step-11.10 sync-status is a thin local cross-tab: queue size + filenames
sitting in database_dir. Mendeley owns whether those PDFs are indexed; docent
no longer tracks pdf_path. Each test sets up a tmp database_dir, points the
PaperSettings at it, and asserts on the result.
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
        assert result.queue_size == 0
        assert result.database_pdfs == []
        assert "not configured" in result.message
    finally:
        os.environ.pop("DOCENT_NO_INTERACTIVE", None)


def test_empty_database_empty_queue(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    ctx = _ctx(database_dir=db)
    result = PaperPipeline().sync_status(SyncStatusInputs(), ctx)
    assert result.database_dir == str(db)
    assert result.queue_size == 0
    assert result.database_pdfs == []
    assert "0 queue" in result.summary


def test_lists_database_pdfs(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    _make_pdf(db / "alpha.pdf")
    _make_pdf(db / "beta.pdf")

    ctx = _ctx(database_dir=db)
    result = PaperPipeline().sync_status(SyncStatusInputs(), ctx)
    assert result.database_pdfs == ["alpha.pdf", "beta.pdf"]
    assert "2 PDF" in result.summary


def test_queue_size_reflects_entries(tmp_docent_home, tmp_path, seed_queue_entry):
    db = tmp_path / "Papers"
    db.mkdir()

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db)
    seed_queue_entry(tool, title="Foo", authors="Smith, J", year=2024, doi="10.1/foo")
    seed_queue_entry(tool, title="Bar", authors="Doe, J", year=2023, doi="10.1/bar")

    result = tool.sync_status(SyncStatusInputs(), ctx)
    assert result.queue_size == 2

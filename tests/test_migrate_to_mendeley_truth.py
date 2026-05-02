"""Tests for `paper migrate-to-mendeley-truth` (Step 11.10).

The migration is destructive: it backs up an existing queue.json to .bak and
wipes the queue to the new (Mendeley-keyed) shape. Tests cover the gate
(`--yes` required), backup creation, idempotence on an empty store, and the
post-migration shape.
"""
from __future__ import annotations

import json

from docent.config import load_settings
from docent.core.context import Context
from docent.execution import Executor
from docent.llm import LLMClient
from docent.tools.paper import MigrateInputs, PaperPipeline


def _ctx() -> Context:
    settings = load_settings()
    return Context(settings=settings, llm=LLMClient(settings), executor=Executor())


def test_dry_path_reports_size_without_writing(tmp_docent_home, seed_queue_entry):
    tool = PaperPipeline()
    seed_queue_entry(tool, title="X", authors="Smith, J", year=2024, doi="10.1/x")
    seed_queue_entry(tool, title="Y", authors="Doe, J", year=2023, doi="10.1/y")

    result = tool.migrate_to_mendeley_truth(MigrateInputs(yes=False), _ctx())
    assert result.migrated is False
    assert result.queue_size_before == 2
    assert result.backup_path is None
    assert "Re-run with --yes" in result.message
    # Queue untouched.
    assert len(tool._store.load_queue()) == 2


def test_yes_creates_backup_and_wipes(tmp_docent_home, seed_queue_entry):
    tool = PaperPipeline()
    seed_queue_entry(tool, title="X", authors="Smith, J", year=2024, doi="10.1/x")

    result = tool.migrate_to_mendeley_truth(MigrateInputs(yes=True), _ctx())
    assert result.migrated is True
    assert result.queue_size_before == 1
    assert result.backup_path is not None

    # Queue now empty.
    assert tool._store.load_queue() == []
    # Backup contains the original entry.
    from pathlib import Path
    bak = Path(result.backup_path)
    assert bak.exists()
    backed = json.loads(bak.read_text(encoding="utf-8"))
    assert len(backed) == 1
    assert backed[0]["title"] == "X"


def test_yes_on_empty_store_is_safe(tmp_docent_home):
    tool = PaperPipeline()
    result = tool.migrate_to_mendeley_truth(MigrateInputs(yes=True), _ctx())
    assert result.migrated is True
    assert result.queue_size_before == 0
    # No prior queue.json -> no backup created.
    assert result.backup_path is None
    assert tool._store.load_queue() == []

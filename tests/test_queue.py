"""Tests for `paper add` after Step 11.8.

Post-11.8 add() has two modes:
- No --mendeley-id → guidance shim (drop PDF in DB, drag into collection, run sync-from-mendeley).
- --mendeley-id supplied → upsert a sidecar entry keyed on that id; metadata
  pulled fresh on next read via the Mendeley overlay.
"""
from __future__ import annotations

import json

from docent.config import load_settings
from docent.core.context import Context
from docent.execution.executor import ProcessResult
from docent.llm import LLMClient
from docent.tools.paper import AddInputs, PaperPipeline
from docent.utils.paths import data_dir


class _StubExecutor:
    def run(self, args, *, timeout=None, cwd=None, env=None, check=True):
        return ProcessResult(args=list(args), returncode=1, stdout="", stderr="stub", duration=0.0)


def _make_context() -> Context:
    settings = load_settings()
    return Context(settings=settings, llm=LLMClient(settings), executor=_StubExecutor())


def test_add_without_mendeley_id_returns_guidance(tmp_docent_home):
    tool = PaperPipeline()
    ctx = _make_context()
    result = tool.add(AddInputs(), ctx)

    assert result.added is False
    assert "sync-from-mendeley" in result.message
    assert "Docent-Queue" in result.message
    assert tool._store.load_queue() == []


def test_add_with_mendeley_id_upserts_entry(tmp_docent_home):
    tool = PaperPipeline()
    ctx = _make_context()
    result = tool.add(AddInputs(mendeley_id="MEND-ABC123XYZ", priority="high", course="thesis"), ctx)

    assert result.added is True
    assert result.queue_size == 1

    paper_dir = data_dir() / "paper"
    queue = json.loads((paper_dir / "queue.json").read_text(encoding="utf-8"))
    assert len(queue) == 1
    entry = queue[0]
    assert entry["mendeley_id"] == "MEND-ABC123XYZ"
    assert entry["priority"] == "high"
    assert entry["course"] == "thesis"
    assert entry["status"] == "queued"
    assert entry["title"] == "(pending Mendeley sync)"


def test_add_same_mendeley_id_blocked_without_force(tmp_docent_home):
    tool = PaperPipeline()
    ctx = _make_context()
    tool.add(AddInputs(mendeley_id="MEND-1"), ctx)

    result = tool.add(AddInputs(mendeley_id="MEND-1", priority="critical"), ctx)
    assert result.added is False
    assert "already in queue" in result.message.lower()
    # Original priority preserved.
    assert tool._store.load_queue()[0]["priority"] == "medium"


def test_add_force_updates_existing_entry(tmp_docent_home):
    tool = PaperPipeline()
    ctx = _make_context()
    tool.add(AddInputs(mendeley_id="MEND-1", priority="medium"), ctx)

    result = tool.add(AddInputs(mendeley_id="MEND-1", priority="critical", course="thesis", force=True), ctx)
    assert result.added is True
    queue = tool._store.load_queue()
    assert len(queue) == 1
    assert queue[0]["priority"] == "critical"
    assert queue[0]["course"] == "thesis"


def test_add_strips_whitespace_from_mendeley_id(tmp_docent_home):
    tool = PaperPipeline()
    ctx = _make_context()
    result = tool.add(AddInputs(mendeley_id="  MEND-XYZ  "), ctx)
    assert result.added
    assert tool._store.load_queue()[0]["mendeley_id"] == "MEND-XYZ"

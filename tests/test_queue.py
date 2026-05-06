"""Tests for `reading add` action (Step 11.8 / reading tool rewrite).

Two modes:
- No --mendeley-id  → guidance shim.
- --mendeley-id     → upsert a sidecar entry keyed on that id.
"""
from __future__ import annotations

import json

from docent.config import load_settings
from docent.core.context import Context
from docent.execution.executor import ProcessResult
from docent.llm import LLMClient
from docent.tools.reading import AddInputs, ReadingQueue
from docent.utils.paths import data_dir


class _StubExecutor:
    def run(self, args, *, timeout=None, cwd=None, env=None, check=True):
        return ProcessResult(args=list(args), returncode=1, stdout="", stderr="stub", duration=0.0)


def _ctx() -> Context:
    settings = load_settings()
    return Context(settings=settings, llm=LLMClient(settings), executor=_StubExecutor())


def test_add_without_mendeley_id_returns_guidance(tmp_docent_home):
    tool = ReadingQueue()
    result = tool.add(AddInputs(), _ctx())

    assert result.added is False
    assert "sync-from-mendeley" in result.message
    assert "Docent-Queue" in result.message
    assert tool._store.load_queue() == []


def test_add_with_mendeley_id_upserts_entry(tmp_docent_home):
    tool = ReadingQueue()
    result = tool.add(AddInputs(mendeley_id="MEND-ABC123XYZ", category="thesis"), _ctx())

    assert result.added is True
    assert result.queue_size == 1

    reading_dir = data_dir() / "reading"
    queue = json.loads((reading_dir / "queue.json").read_text(encoding="utf-8"))
    assert len(queue) == 1
    entry = queue[0]
    assert entry["mendeley_id"] == "MEND-ABC123XYZ"
    assert entry["category"] == "thesis"
    assert entry["status"] == "queued"
    assert entry["order"] == 1
    assert entry["title"] == "(pending Mendeley sync)"


def test_add_same_mendeley_id_blocked_without_force(tmp_docent_home):
    tool = ReadingQueue()
    ctx = _ctx()
    tool.add(AddInputs(mendeley_id="MEND-1"), ctx)

    result = tool.add(AddInputs(mendeley_id="MEND-1", category="course"), ctx)
    assert result.added is False
    assert "already in queue" in result.message.lower()
    # Original category preserved (default is None).
    assert tool._store.load_queue()[0]["category"] is None


def test_add_force_updates_existing_entry(tmp_docent_home):
    tool = ReadingQueue()
    ctx = _ctx()
    tool.add(AddInputs(mendeley_id="MEND-1", category="personal"), ctx)

    result = tool.add(AddInputs(mendeley_id="MEND-1", category="thesis", force=True), ctx)
    assert result.added is True
    queue = tool._store.load_queue()
    assert len(queue) == 1
    assert queue[0]["category"] == "thesis"


def test_add_strips_whitespace_from_mendeley_id(tmp_docent_home):
    tool = ReadingQueue()
    result = tool.add(AddInputs(mendeley_id="  MEND-XYZ  "), _ctx())
    assert result.added
    assert tool._store.load_queue()[0]["mendeley_id"] == "MEND-XYZ"


def test_add_assigns_sequential_order(tmp_docent_home):
    tool = ReadingQueue()
    ctx = _ctx()
    tool.add(AddInputs(mendeley_id="MEND-1"), ctx)
    tool.add(AddInputs(mendeley_id="MEND-2"), ctx)
    queue = {e["mendeley_id"]: e for e in tool._store.load_queue()}
    assert queue["MEND-1"]["order"] == 1
    assert queue["MEND-2"]["order"] == 2

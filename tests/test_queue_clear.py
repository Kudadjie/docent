"""Tests for `paper queue-clear` (Step 11.2 batch fixes).

Empties the queue. Two-step safety: without --yes the action reports the size
and exits without mutating; with --yes it persists an empty queue.
"""
from __future__ import annotations

from docent.config import load_settings
from docent.core.context import Context
from docent.execution.executor import ProcessResult
from docent.llm import LLMClient
from reading import (
    ReadingQueue,
    QueueClearInputs,
)


class _StubExecutor:
    def run(self, args, *, timeout=None, cwd=None, env=None, check=True):
        return ProcessResult(args=list(args), returncode=1, stdout="", stderr="stub", duration=0.0)


def _ctx() -> Context:
    settings = load_settings()
    return Context(settings=settings, llm=LLMClient(settings), executor=_StubExecutor())


def test_queue_clear_without_yes_is_a_dry_report(tmp_docent_home, seed_queue_entry):
    tool = ReadingQueue()
    ctx = _ctx()
    seed_queue_entry(tool, title="A", authors="X, Y", year=2024, doi="10.1234/a")
    seed_queue_entry(tool, title="B", authors="X, Y", year=2025, doi="10.1234/b")

    result = tool.queue_clear(QueueClearInputs(), ctx)
    assert result.cleared is False
    assert result.removed_count == 0
    assert result.queue_size == 2
    assert "--yes" in result.message
    # Queue still intact.
    assert len(tool._store.load_queue()) == 2


def test_queue_clear_with_yes_empties_queue(tmp_docent_home, seed_queue_entry):
    tool = ReadingQueue()
    ctx = _ctx()
    seed_queue_entry(tool, title="A", authors="X, Y", year=2024, doi="10.1234/a")
    seed_queue_entry(tool, title="B", authors="X, Y", year=2025, doi="10.1234/b")

    result = tool.queue_clear(QueueClearInputs(yes=True), ctx)
    assert result.cleared is True
    assert result.removed_count == 2
    assert result.queue_size == 0
    assert tool._store.load_queue() == []


def test_queue_clear_on_empty_queue_is_noop(tmp_docent_home):
    tool = ReadingQueue()
    ctx = _ctx()
    result = tool.queue_clear(QueueClearInputs(yes=True), ctx)
    assert result.cleared is True
    assert result.removed_count == 0
    assert result.queue_size == 0

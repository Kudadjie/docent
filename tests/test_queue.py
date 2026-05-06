"""Tests for `reading add` action — guidance-only after sidecar removal."""
from __future__ import annotations

from docent.config import load_settings
from docent.core.context import Context
from docent.execution.executor import ProcessResult
from docent.llm import LLMClient
from reading import AddInputs, ReadingQueue


class _StubExecutor:
    def run(self, args, *, timeout=None, cwd=None, env=None, check=True):
        return ProcessResult(args=list(args), returncode=1, stdout="", stderr="stub", duration=0.0)


def _ctx() -> Context:
    settings = load_settings()
    return Context(settings=settings, llm=LLMClient(settings), executor=_StubExecutor())


def test_add_returns_guidance(tmp_docent_home):
    tool = ReadingQueue()
    result = tool.add(AddInputs(), _ctx())

    assert result.added is False
    assert "sync-from-mendeley" in result.message
    assert "Docent-Queue" in result.message
    assert tool._store.load_queue() == []

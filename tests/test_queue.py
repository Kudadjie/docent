from __future__ import annotations

import json

from docent.config import load_settings
from docent.core.context import Context
from docent.execution.executor import ProcessResult
from docent.llm import LLMClient
from docent.tools.paper import AddInputs, PaperPipeline
from docent.utils.paths import data_dir


class _StubExecutor:
    """Fail every subprocess so DOI/CrossRef lookups return None and explicit
    metadata wins. Keeps unit tests offline and deterministic."""

    def run(self, args, *, timeout=None, cwd=None, env=None, check=True):
        return ProcessResult(args=list(args), returncode=1, stdout="", stderr="stub", duration=0.0)


def _make_context() -> Context:
    settings = load_settings()
    return Context(settings=settings, llm=LLMClient(settings), executor=_StubExecutor())


def test_add_with_explicit_metadata(tmp_docent_home):
    tool = PaperPipeline()
    ctx = _make_context()
    inputs = AddInputs(
        title="A Quiet Paper",
        authors="Smith, Jane; Doe, John",
        year=2024,
        doi="10.1234/quiet",
        priority="high",
    )

    result = tool.add(inputs, ctx)

    assert result.added
    assert result.id == "smith-2024-a"
    assert result.queue_size == 1

    paper_dir = data_dir() / "paper"
    queue = json.loads((paper_dir / "queue.json").read_text(encoding="utf-8"))
    assert len(queue) == 1
    assert queue[0]["title"] == "A Quiet Paper"
    assert queue[0]["priority"] == "high"
    assert queue[0]["status"] == "queued"

    index = json.loads((paper_dir / "queue-index.json").read_text(encoding="utf-8"))
    assert "smith-2024-a" in index
    assert index["smith-2024-a"]["status"] == "queued"

    state = json.loads((paper_dir / "state.json").read_text(encoding="utf-8"))
    assert state["queued"] == 1
    assert state["reading"] == 0


def test_add_collision_blocked_without_force(tmp_docent_home):
    tool = PaperPipeline()
    ctx = _make_context()
    tool.add(AddInputs(title="A Quiet Paper", authors="Smith, Jane", year=2024, doi="10.1234/quiet"), ctx)

    result = tool.add(
        AddInputs(title="A Quiet Paper Repeated", authors="Smith, Jane", year=2024, doi="10.1234/repeat"),
        ctx,
    )
    assert not result.added
    assert "already in queue" in result.message.lower()
    assert result.queue_size == 1


def test_add_collision_overwritten_with_force(tmp_docent_home):
    tool = PaperPipeline()
    ctx = _make_context()
    tool.add(AddInputs(title="A Quiet Paper", authors="Smith, Jane", year=2024, doi="10.1234/quiet"), ctx)

    result = tool.add(
        AddInputs(title="A Newer Title", authors="Smith, Jane", year=2024, doi="10.1234/newer", force=True),
        ctx,
    )
    assert result.added
    assert result.queue_size == 1

    paper_dir = data_dir() / "paper"
    queue = json.loads((paper_dir / "queue.json").read_text(encoding="utf-8"))
    assert len(queue) == 1
    assert queue[0]["title"] == "A Newer Title"


def test_add_without_metadata_returns_message(tmp_docent_home):
    tool = PaperPipeline()
    ctx = _make_context()
    result = tool.add(AddInputs(), ctx)
    assert not result.added
    assert "--pdf" in result.message and "--doi" in result.message

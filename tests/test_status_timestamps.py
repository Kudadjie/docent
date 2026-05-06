"""Tests for the started/finished timestamp lifecycle (Step 11.10).

`start` stamps `started` on first transition; `done` stamps `finished`.
Re-setting the same status doesn't overwrite an existing timestamp.
"""
from __future__ import annotations

from docent.config import load_settings
from docent.core.context import Context
from docent.execution import Executor
from docent.llm import LLMClient
from docent.tools.reading import IdOnlyInputs, ReadingQueue


def _ctx() -> Context:
    settings = load_settings()
    return Context(settings=settings, llm=LLMClient(settings), executor=Executor())


def test_start_sets_started(tmp_docent_home, seed_queue_entry):
    tool = ReadingQueue()
    seeded = seed_queue_entry(tool, title="X", authors="Smith, J", year=2024, doi="10.1/x")
    eid = seeded["id"]

    result = tool.start(IdOnlyInputs(id=eid), _ctx())
    assert result.ok
    assert result.entry.status == "reading"
    assert result.entry.started is not None
    assert result.entry.finished is None


def test_done_sets_finished(tmp_docent_home, seed_queue_entry):
    tool = ReadingQueue()
    seeded = seed_queue_entry(tool, title="X", authors="Smith, J", year=2024, doi="10.1/x")
    eid = seeded["id"]

    tool.start(IdOnlyInputs(id=eid), _ctx())
    result = tool.done(IdOnlyInputs(id=eid), _ctx())
    assert result.entry.status == "done"
    assert result.entry.started is not None
    assert result.entry.finished is not None


def test_started_not_overwritten_on_re_read(tmp_docent_home, seed_queue_entry):
    tool = ReadingQueue()
    seeded = seed_queue_entry(tool, title="X", authors="Smith, J", year=2024, doi="10.1/x")
    eid = seeded["id"]

    first = tool.start(IdOnlyInputs(id=eid), _ctx())
    first_started = first.entry.started

    second = tool.start(IdOnlyInputs(id=eid), _ctx())
    assert second.entry.started == first_started

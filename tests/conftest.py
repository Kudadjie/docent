"""Shared pytest fixtures for the Docent test suite.

Two cross-cutting concerns: redirect ~/.docent to a tmp dir so tests can't
touch the user's real config/data, and snapshot the global tool registry so
tests that call @register_tool don't leak into one another.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from docent.core.registry import _REGISTRY


@pytest.fixture
def tmp_docent_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCENT_HOME", str(tmp_path))
    for key in list(os.environ):
        if key.startswith("DOCENT_") and key != "DOCENT_HOME":
            monkeypatch.delenv(key, raising=False)
    return tmp_path


@pytest.fixture
def isolated_registry():
    snapshot = dict(_REGISTRY)
    try:
        yield _REGISTRY
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(snapshot)


def _seed_queue_entry(
    tool: Any,
    *,
    title: str = "Test Paper",
    authors: str = "Smith, J",
    year: int | None = 2024,
    doi: str | None = None,
    mendeley_id: str | None = None,
    id: str | None = None,
    order: int = 1,
    category: str = "personal",
    course_name: str | None = None,
    deadline: str | None = None,
    notes: str = "",
    status: str = "queued",
    started: str | None = None,
    finished: str | None = None,
) -> dict:
    """Build a QueueEntry directly and persist it via the tool's store.

    Bypasses the `reading add` CLI surface so sync-* tests can seed arbitrary
    fixtures. Mirrors ReadingQueue._derive_id when no explicit `id` is given.
    Defaults to mendeley_id="m-<id>" so the entry passes _require_identifier
    when the test doesn't supply a doi.
    """
    from docent.tools.reading import ReadingQueue, QueueEntry

    entry_id = id or ReadingQueue._derive_id(authors, year, title)
    if not doi and not mendeley_id:
        mendeley_id = f"m-{entry_id}"
    entry = QueueEntry(
        id=entry_id,
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        added=datetime.now().date().isoformat(),
        status=status,
        order=order,
        category=category,
        course_name=course_name,
        deadline=deadline,
        notes=notes,
        mendeley_id=mendeley_id,
        started=started,
        finished=finished,
    )
    queue = tool._store.load_queue()
    queue = [e for e in queue if e.get("id") != entry_id]
    queue.append(entry.model_dump())
    tool._store.save_queue(queue)
    return entry.model_dump()


@pytest.fixture
def seed_queue_entry():
    """Pytest-fixture form: yield the helper for direct use in tests."""
    return _seed_queue_entry

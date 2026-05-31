"""Shared pytest fixtures for the Docent test suite.

Two cross-cutting concerns: redirect ~/.docent to a tmp dir so tests can't
touch the user's real config/data, and snapshot the global tool registry so
tests that call @register_tool don't leak into one another.
"""

from __future__ import annotations

import os
import socket
import sys as _sys
from datetime import datetime
from pathlib import Path as _Path
from typing import Any

import pytest

from docent.core.registry import _REGISTRY

# ---------------------------------------------------------------------------
# Network guard — block all socket connections in unit tests.
# Tests marked @pytest.mark.integration or @pytest.mark.eval are exempt.
# ---------------------------------------------------------------------------

_NETWORK_EXEMPT_MARKS = frozenset({"integration", "eval"})
_real_socket_connect = socket.socket.connect


_LOCALHOST_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "0.0.0.0", ""})


def _blocked_connect(self: socket.socket, address: object) -> None:
    # Allow loopback — Starlette TestClient and other in-process tools use it.
    if isinstance(address, (tuple, list)):
        host = str(address[0])
        if host in _LOCALHOST_HOSTS:
            return _real_socket_connect(self, address)
    raise OSError(
        "Unit test attempted a real external network connection. "
        "Mark the test @pytest.mark.integration if it needs network access, "
        f"or mock the call. Address: {address}"
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    marks = {m.name for m in item.iter_markers()}
    if marks & _NETWORK_EXEMPT_MARKS:
        socket.socket.connect = _real_socket_connect
    else:
        socket.socket.connect = _blocked_connect  # type: ignore[method-assign]


def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:  # noqa: ARG001
    socket.socket.connect = _real_socket_connect


# Make bundled plugins importable (mirrors what plugin_loader does at runtime)
_BUNDLED = _Path(__file__).parent.parent / "src" / "docent" / "bundled_plugins"
if _BUNDLED.exists() and str(_BUNDLED) not in _sys.path:
    _sys.path.insert(0, str(_BUNDLED))


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
    reference_id: str | None = None,
    id: str | None = None,
    order: int = 1,
    category: str | None = None,
    deadline: str | None = None,
    notes: str = "",
    status: str = "queued",
    started: str | None = None,
    finished: str | None = None,
) -> dict:
    """Build a QueueEntry directly and persist it via the tool's store.

    Bypasses the `reading add` CLI surface so sync-* tests can seed arbitrary
    fixtures. Mirrors derive_id() when no explicit `id` is given.
    Defaults to reference_id="m-<id>" so the entry passes _require_identifier
    when the test doesn't supply a doi.
    """
    from docent.bundled_plugins.reading import QueueEntry
    from docent.bundled_plugins.reading.sync_engine import derive_id

    entry_id = id or derive_id(authors, year, title)
    if not doi and not reference_id:
        reference_id = f"m-{entry_id}"
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
        deadline=deadline,
        notes=notes,
        reference_id=reference_id,
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

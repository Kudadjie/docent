"""Tests for the Mendeley overlay on reader actions (Step 11.7).

`next`/`show`/`search` call `_load_mendeley_overlay`, which (a) resolves
the configured collection name to a folder_id via `mendeley_list_folders`
and (b) reads the cache (or fetches fresh via `mendeley_list_documents`).
We patch both wrapper functions at the import site in `docent.tools.paper`
— no real subprocess, no real MCP traffic. We also patch the cache to a
tmp file so test runs don't touch each other.
"""
from __future__ import annotations

from typing import Any

import pytest

from docent.config import load_settings
from docent.core.context import Context
from docent.execution import Executor
from docent.llm import LLMClient
from reading import (
    IdOnlyInputs,
    NextInputs,
    ReadingQueue,
    SearchInputs,
)


def _ctx(queue_collection: str = "Docent-Queue") -> Context:
    settings = load_settings()
    settings.reading.queue_collection = queue_collection
    return Context(settings=settings, llm=LLMClient(settings), executor=Executor())


def _patch(monkeypatch, *, folders=None, documents=None):
    """Same shape as the helper in test_sync_from_mendeley."""

    def fake_folders(launch_command=None):
        return folders if folders is not None else {"items": [], "error": None}

    def fake_documents(folder_id=None, launch_command=None, limit=200, sort_by="last_modified"):
        return documents if documents is not None else {"items": [], "error": None}

    monkeypatch.setattr("reading.mendeley_list_folders", fake_folders)
    monkeypatch.setattr("reading.mendeley_list_documents", fake_documents)


def _seed_queue(tool: ReadingQueue, entries: list[dict]) -> None:
    tool._store.save_queue(entries)


def _stale_entry(**overrides) -> dict:
    """Snapshot-style queue entry with deliberately stale title/authors so
    we can tell whether the overlay applied."""
    base = {
        "id": "smith-2020-stale",
        "title": "STALE TITLE",
        "authors": "STALE",
        "year": 2020,
        "doi": None,
        "added": "2026-05-01",
        "status": "queued",
        "order": 1,
        "category": None,
        "deadline": None,
        "tags": [],
        "notes": "",
        "mendeley_id": "MID-1",
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------------
# next
# ----------------------------------------------------------------------


def test_next_overlays_fresh_mendeley_metadata(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    _seed_queue(tool, [_stale_entry()])

    _patch(
        monkeypatch,
        folders={"items": [{"id": "F1", "name": "Docent-Queue"}], "error": None},
        documents={
            "items": [{
                "id": "MID-1",
                "title": "Fresh Title From Mendeley",
                "authors": ["Smith, Jane", "Doe, John"],
                "year": 2024,
                "identifiers": {"doi": "10.1234/fresh"},
            }],
            "error": None,
        },
    )

    result = tool.next(NextInputs(), _ctx())

    assert result.ok
    assert result.entry.title == "Fresh Title From Mendeley"
    assert "Smith, Jane" in result.entry.authors
    assert result.entry.year == 2024
    assert result.entry.doi == "10.1234/fresh"
    # Message also reflects the fresh title.
    assert "Fresh Title From Mendeley" in result.message


def test_next_falls_back_to_snapshot_on_mcp_error(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    _seed_queue(tool, [_stale_entry()])

    _patch(monkeypatch, folders={"items": [], "error": "transport: nope"})

    result = tool.next(NextInputs(), _ctx())

    assert result.ok
    assert result.entry.title == "STALE TITLE"
    assert result.entry.authors == "STALE"


def test_next_falls_back_when_collection_missing(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    _seed_queue(tool, [_stale_entry()])

    _patch(
        monkeypatch,
        folders={"items": [{"id": "F1", "name": "Other"}], "error": None},
    )

    result = tool.next(NextInputs(), _ctx())

    assert result.ok
    assert result.entry.title == "STALE TITLE"


def test_next_passes_through_entries_without_mendeley_id(tmp_docent_home, monkeypatch):
    """A legacy entry (no mendeley_id) plus a Mendeley-keyed entry: only
    the latter is overlaid; the former is untouched."""
    tool = ReadingQueue()
    _seed_queue(tool, [
        _stale_entry(id="legacy-1", mendeley_id=None, doi="10.9999/legacy", order=1),
        _stale_entry(id="mid-1", mendeley_id="MID-1", order=2),
    ])

    _patch(
        monkeypatch,
        folders={"items": [{"id": "F1", "name": "Docent-Queue"}], "error": None},
        documents={"items": [{"id": "MID-1", "title": "Fresh", "authors": ["A"], "year": 2024}], "error": None},
    )

    # legacy-1 has lower order so it comes next; its title is untouched (no mendeley_id).
    result = tool.next(NextInputs(), _ctx())
    assert result.entry.id == "legacy-1"
    assert result.entry.title == "STALE TITLE"  # untouched


# ----------------------------------------------------------------------
# show
# ----------------------------------------------------------------------


def test_show_overlays_fresh_metadata(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    _seed_queue(tool, [_stale_entry()])

    _patch(
        monkeypatch,
        folders={"items": [{"id": "F1", "name": "Docent-Queue"}], "error": None},
        documents={"items": [{"id": "MID-1", "title": "Fresh", "authors": ["X"], "year": 2025}], "error": None},
    )

    result = tool.show(IdOnlyInputs(id="smith-2020-stale"), _ctx())
    assert result.ok
    assert result.entry.title == "Fresh"
    assert result.entry.year == 2025


# ----------------------------------------------------------------------
# search
# ----------------------------------------------------------------------


def test_search_matches_against_overlaid_title(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    _seed_queue(tool, [_stale_entry()])

    _patch(
        monkeypatch,
        folders={"items": [{"id": "F1", "name": "Docent-Queue"}], "error": None},
        documents={
            "items": [{"id": "MID-1", "title": "Wave hindcasting in shallow water", "authors": ["A"]}],
            "error": None,
        },
    )

    # Search for a word that's only in the *fresh* title — proves the
    # overlay applied before haystack construction.
    result = tool.search(SearchInputs(query="hindcasting"), _ctx())
    assert result.total == 1
    assert result.matches[0].title == "Wave hindcasting in shallow water"


def test_search_uses_snapshot_on_mcp_error(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    _seed_queue(tool, [_stale_entry(title="Stormy seas paper")])

    _patch(monkeypatch, folders={"items": [], "error": "transport: nope"})

    result = tool.search(SearchInputs(query="stormy"), _ctx())
    assert result.total == 1


# ----------------------------------------------------------------------
# Cache reuse: second reader call within TTL must not re-call MCP
# ----------------------------------------------------------------------


def test_second_reader_call_hits_cache_not_mcp(tmp_docent_home, monkeypatch):
    """First `next` populates the cache; second `next` in the same TTL
    window must not re-call list_documents."""
    tool = ReadingQueue()
    _seed_queue(tool, [_stale_entry()])

    folder_calls = 0
    doc_calls = 0

    def fake_folders(launch_command=None):
        nonlocal folder_calls
        folder_calls += 1
        return {"items": [{"id": "F1", "name": "Docent-Queue"}], "error": None}

    def fake_documents(folder_id=None, launch_command=None, limit=200, sort_by="last_modified"):
        nonlocal doc_calls
        doc_calls += 1
        return {"items": [{"id": "MID-1", "title": "Fresh", "authors": ["A"], "year": 2024}], "error": None}

    monkeypatch.setattr("reading.mendeley_list_folders", fake_folders)
    monkeypatch.setattr("reading.mendeley_list_documents", fake_documents)

    tool.next(NextInputs(), _ctx())
    tool.next(NextInputs(), _ctx())

    assert doc_calls == 1, "second call should be a cache hit"
    # 11.7-followup: folder lookup is cached too — only the first call hits MCP.
    assert folder_calls == 1, "second call should reuse cached folder_id"

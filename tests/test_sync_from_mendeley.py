"""Tests for `paper sync-from-mendeley` (Step 11.6).

Generator action: reconciles a Mendeley collection (default 'Docent-Queue')
against the local sidecar queue. The wrapper module functions
(`mendeley_list_folders`, `mendeley_list_documents`) are monkeypatched at
the import site in `docent.tools.paper` — no real subprocess, no real MCP
traffic.
"""
from __future__ import annotations

import inspect
from typing import Any

from docent.config import load_settings
from docent.core.context import Context
from docent.execution import Executor
from docent.llm import LLMClient
from docent.tools.reading import (
    ConfigSetInputs,
    ConfigShowInputs,
    ReadingQueue,
    SyncFromMendeleyInputs,
)


def _ctx(queue_collection: str = "Docent-Queue") -> Context:
    settings = load_settings()
    settings.reading.queue_collection = queue_collection
    return Context(settings=settings, llm=LLMClient(settings), executor=Executor())


def _drain(maybe_gen):
    if not inspect.isgenerator(maybe_gen):
        return maybe_gen
    try:
        while True:
            next(maybe_gen)
    except StopIteration as e:
        return e.value


def _patch_mendeley(
    monkeypatch,
    *,
    folders: Any = None,
    documents: Any = None,
):
    """Install fakes for mendeley_list_folders and mendeley_list_documents
    at the import site in `docent.tools.paper`. Each arg may be:
      - None: returns {"items": [], "error": None}
      - dict: returned verbatim from the wrapper
      - callable(*args, **kwargs) -> dict: invoked per-call
    """
    calls = {"folders": [], "documents": []}

    def fake_folders(launch_command=None):
        calls["folders"].append(launch_command)
        if folders is None:
            return {"items": [], "error": None}
        return folders(launch_command) if callable(folders) else folders

    def fake_documents(folder_id=None, launch_command=None, limit=200, sort_by="last_modified"):
        calls["documents"].append({"folder_id": folder_id, "limit": limit, "sort_by": sort_by})
        if documents is None:
            return {"items": [], "error": None}
        return documents(folder_id) if callable(documents) else documents

    monkeypatch.setattr("docent.tools.reading.mendeley_list_folders", fake_folders)
    monkeypatch.setattr("docent.tools.reading.mendeley_list_documents", fake_documents)
    return calls


# ----------------------------------------------------------------------
# Folder resolution
# ----------------------------------------------------------------------


def test_collection_missing_returns_actionable_error(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(monkeypatch, folders={"items": [
        {"id": "F1", "name": "Test", "parent_id": None},
    ], "error": None})

    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert result.added == []
    assert result.folder_id is None
    assert "Docent-Queue" in result.message
    assert "Mendeley desktop app" in result.message


def test_duplicate_collection_name_asks_user_to_rename(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(monkeypatch, folders={"items": [
        {"id": "F1", "name": "Docent-Queue", "parent_id": None},
        {"id": "F2", "name": "Docent-Queue", "parent_id": "OTHER"},
    ], "error": None})

    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert "2 Mendeley collections" in result.message
    assert "Rename" in result.message
    assert result.folder_id is None


def test_list_folders_transport_error_propagates_with_hint(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(monkeypatch, folders={
        "items": [], "error": "transport: launch command not found ([Errno 2])",
    })

    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert "Could not list Mendeley folders" in result.message
    assert "uv tool install mendeley-mcp" in result.message


def test_list_documents_error_after_folder_resolved(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [], "error": "auth: token expired"},
    )

    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert result.folder_id == "FQ"
    assert "Could not list documents" in result.message
    assert "auth:" in result.message
    assert "mendeley-auth login" in result.message


def test_custom_queue_collection_setting(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx(queue_collection="My-Reading-List")
    calls = _patch_mendeley(monkeypatch, folders={"items": [
        {"id": "F1", "name": "My-Reading-List", "parent_id": None},
    ], "error": None}, documents={"items": [], "error": None})

    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert result.folder_id == "F1"
    assert result.queue_collection == "My-Reading-List"
    assert calls["documents"] == [{"folder_id": "F1", "limit": 200, "sort_by": "last_modified"}]


# ----------------------------------------------------------------------
# Reconciliation
# ----------------------------------------------------------------------


def test_empty_collection_yields_zero_added(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [], "error": None},
    )

    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert result.added == [] and result.unchanged == [] and result.removed == []
    assert "0 added" in result.summary


def test_new_doc_creates_snapshot_entry(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [{
            "id": "MEND-1",
            "title": "Storm Surge in West Africa",
            "authors": ["Smith, John", "Jones, Kate"],
            "year": 2024,
            "identifiers": {"doi": "10.1234/surge"},
        }], "error": None},
    )

    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert len(result.added) == 1
    assert result.added[0]["mendeley_id"] == "MEND-1"
    assert result.added[0]["title"] == "Storm Surge in West Africa"

    queue = tool._store.load_queue()
    assert len(queue) == 1
    e = queue[0]
    assert e["mendeley_id"] == "MEND-1"
    assert e["title"] == "Storm Surge in West Africa"
    assert e["authors"] == "Smith, John; Jones, Kate"
    assert e["year"] == 2024
    assert e["doi"] == "10.1234/surge"
    assert e["status"] == "queued"
    assert "pdf_path" not in e  # Step 11.10 dropped the field; Mendeley owns the file.


def test_doc_without_doi_or_pdf_persists_via_mendeley_id(tmp_docent_home, monkeypatch):
    """Validator relax: mendeley_id alone is enough to persist."""
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [{
            "id": "MEND-NO-DOI",
            "title": "Untitled report",
            "authors": ["Anon, A"],
            "year": None,
            "identifiers": None,
        }], "error": None},
    )

    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert len(result.added) == 1
    queue = tool._store.load_queue()
    assert queue[0]["mendeley_id"] == "MEND-NO-DOI"
    assert queue[0]["doi"] is None
    assert "pdf_path" not in queue[0]


def test_idempotent_rerun_unchanged(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [{
            "id": "MEND-1", "title": "Foo", "authors": ["Smith, J"], "year": 2024,
            "identifiers": {"doi": "10.1234/foo"},
        }], "error": None},
    )

    first = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    second = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert len(first.added) == 1
    assert second.added == []
    assert len(second.unchanged) == 1
    assert len(tool._store.load_queue()) == 1


def test_removed_branch_flags_status(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx()

    # First run: add MEND-1.
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [{
            "id": "MEND-1", "title": "Foo", "authors": ["Smith, J"], "year": 2024,
            "identifiers": {"doi": "10.1234/foo"},
        }], "error": None},
    )
    _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert tool._store.load_queue()[0]["status"] == "queued"

    # Second run: collection now empty; entry should be flipped to "removed".
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [], "error": None},
    )
    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert len(result.removed) == 1
    assert tool._store.load_queue()[0]["status"] == "removed"

    # Third run: still empty; "removed" entries don't re-bucket.
    result3 = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert result3.removed == []


def test_non_mendeley_entries_untouched_by_removed_branch(tmp_docent_home, monkeypatch):
    """Legacy entries with no mendeley_id (e.g. from `paper add --pdf`) must
    not be flagged as removed even when the collection is empty."""
    tool = ReadingQueue()
    ctx = _ctx()

    # Seed a legacy-shaped entry directly (no mendeley_id, has DOI to satisfy validator).
    tool._store.save_queue([{
        "id": "smith-2024-x", "title": "X", "authors": "Smith, J", "year": 2024,
        "doi": "10.1234/x", "added": "2024-01-01", "status": "queued", "priority": "medium",
        "course": None, "tags": [], "notes": "", "file_status": "missing",
        "keep_in_mendeley": False, "pdf_path": None, "promoted_at": None,
        "mendeley_id": None, "title_is_filename_stub": False,
    }])

    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [], "error": None},
    )
    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert result.removed == []
    assert tool._store.load_queue()[0]["status"] == "queued"


def test_id_collision_uses_mendeley_suffix(tmp_docent_home, monkeypatch):
    """Two Mendeley docs whose authors/year/title slug collides must coexist;
    second gets a -{mendeley_id[:8]} suffix."""
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [
            {"id": "MENDELEY-AAAAAAAA-1", "title": "Foo", "authors": ["Smith, J"], "year": 2024},
            {"id": "MENDELEY-BBBBBBBB-2", "title": "Foo", "authors": ["Smith, J"], "year": 2024},
        ], "error": None},
    )
    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert len(result.added) == 2
    ids = {a["id"] for a in result.added}
    # First is base slug, second carries the suffix derived from its mendeley_id prefix.
    assert "smith-2024-foo" in ids
    assert any(i.startswith("smith-2024-foo-MENDELEY") for i in ids)


def test_doc_missing_id_is_bucketed_as_failed(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [
            {"title": "Has no id", "authors": ["X, Y"]},
            {"id": "MEND-OK", "title": "Has an id", "authors": ["X, Y"], "year": 2024},
        ], "error": None},
    )
    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert len(result.failed) == 1
    assert result.failed[0]["error"] == "doc has no usable id"
    assert len(result.added) == 1


def test_dry_run_does_not_persist(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [{
            "id": "MEND-1", "title": "Foo", "authors": ["Smith, J"], "year": 2024,
            "identifiers": {"doi": "10.1234/foo"},
        }], "error": None},
    )
    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(dry_run=True), ctx))
    assert result.added == []
    assert len(result.dry_run_added) == 1
    assert tool._store.load_queue() == []


def test_dry_run_reports_would_remove(tmp_docent_home, monkeypatch):
    tool = ReadingQueue()
    ctx = _ctx()

    # Seed a mendeley-keyed entry directly (skip first sync to keep it tight).
    tool._store.save_queue([{
        "id": "smith-2024-foo", "title": "Foo", "authors": "Smith, J", "year": 2024,
        "doi": None, "added": "2024-01-01", "status": "queued", "priority": "medium",
        "course": None, "tags": [], "notes": "", "file_status": "missing",
        "keep_in_mendeley": False, "pdf_path": None, "promoted_at": None,
        "mendeley_id": "MEND-1", "title_is_filename_stub": False,
    }])

    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [], "error": None},
    )
    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(dry_run=True), ctx))
    assert result.removed == []
    assert result.dry_run_removed == ["smith-2024-foo"]
    # Persistence untouched
    assert tool._store.load_queue()[0]["status"] == "queued"


# ----------------------------------------------------------------------
# Author/metadata normalization
# ----------------------------------------------------------------------


def test_normalize_authors_dict_form():
    """Mendeley sometimes returns authors as dicts (other endpoints).
    `_normalize_mendeley_authors` joins first_name + last_name with '; '."""
    out = ReadingQueue._normalize_mendeley_authors([
        {"first_name": "John", "last_name": "Smith"},
        {"first_name": "Kate", "last_name": "Jones"},
    ])
    assert out == "John Smith; Kate Jones"


def test_normalize_authors_string_passthrough():
    assert ReadingQueue._normalize_mendeley_authors("Smith, J") == "Smith, J"


def test_normalize_authors_none_or_empty_yields_unknown():
    assert ReadingQueue._normalize_mendeley_authors(None) == "Unknown"
    assert ReadingQueue._normalize_mendeley_authors([]) == "Unknown"
    assert ReadingQueue._normalize_mendeley_authors([{}, ""]) == "Unknown"


# ----------------------------------------------------------------------
# Sub-collection category detection
# ----------------------------------------------------------------------


def test_sub_collection_category_assigned(tmp_docent_home, monkeypatch):
    """Documents in sub-collections get their category from the folder path."""
    tool = ReadingQueue()
    ctx = _ctx()

    folders = [
        {"id": "FQ", "name": "Docent-Queue", "parent_id": None},
        {"id": "FC1", "name": "TestCourse701", "parent_id": "FQ"},
        {"id": "FC2", "name": "ParticularTopic", "parent_id": "FC1"},
    ]

    def fake_docs(folder_id=None):
        mapping = {
            "FQ":  [{"id": "M-ROOT", "title": "Root doc", "authors": ["A"], "year": 2024}],
            "FC1": [{"id": "M-C1",   "title": "Course doc", "authors": ["B"], "year": 2024}],
            "FC2": [{"id": "M-C2",   "title": "Topic doc",  "authors": ["C"], "year": 2024}],
        }
        return {"items": mapping.get(folder_id, []), "error": None}

    _patch_mendeley(monkeypatch, folders={"items": folders, "error": None}, documents=fake_docs)

    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert len(result.added) == 3

    by_mid = {e["mendeley_id"]: e for e in tool._store.load_queue()}
    assert by_mid["M-ROOT"]["category"] is None
    assert by_mid["M-C1"]["category"] == "TestCourse701"
    assert by_mid["M-C2"]["category"] == "TestCourse701/ParticularTopic"


def test_deepest_subcollection_category_wins(tmp_docent_home, monkeypatch):
    """A document appearing in both parent and child sub-folder gets the deeper path."""
    tool = ReadingQueue()
    ctx = _ctx()

    doc = {"id": "M-BOTH", "title": "Multi-folder doc", "authors": ["X"], "year": 2024}
    folders = [
        {"id": "FQ",  "name": "Docent-Queue",    "parent_id": None},
        {"id": "FC1", "name": "TestCourse701",    "parent_id": "FQ"},
        {"id": "FC2", "name": "ParticularTopic",  "parent_id": "FC1"},
    ]

    def fake_docs(folder_id=None):
        return {"items": [doc] if folder_id in ("FQ", "FC1", "FC2") else [], "error": None}

    _patch_mendeley(monkeypatch, folders={"items": folders, "error": None}, documents=fake_docs)

    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert len(result.added) == 1
    assert tool._store.load_queue()[0]["category"] == "TestCourse701/ParticularTopic"


def test_category_updated_when_doc_moves_to_subcollection(tmp_docent_home, monkeypatch):
    """An existing entry's category is updated when the doc moves to a sub-folder."""
    tool = ReadingQueue()
    ctx = _ctx()

    folders = [
        {"id": "FQ",  "name": "Docent-Queue",  "parent_id": None},
        {"id": "FC1", "name": "TestCourse701", "parent_id": "FQ"},
    ]
    doc = {"id": "M-1", "title": "T", "authors": ["A"], "year": 2024}

    # First sync: doc in root.
    _patch_mendeley(
        monkeypatch,
        folders={"items": folders, "error": None},
        documents=lambda fid: {"items": [doc] if fid == "FQ" else [], "error": None},
    )
    _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert tool._store.load_queue()[0]["category"] is None

    # Second sync: doc now in sub-collection.
    _patch_mendeley(
        monkeypatch,
        folders={"items": folders, "error": None},
        documents=lambda fid: {"items": [doc] if fid == "FC1" else [], "error": None},
    )
    _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert tool._store.load_queue()[0]["category"] == "TestCourse701"


def test_subfolder_error_is_non_fatal(tmp_docent_home, monkeypatch):
    """A transport error reading a sub-folder is warned but does not abort the sync."""
    tool = ReadingQueue()
    ctx = _ctx()

    folders = [
        {"id": "FQ",  "name": "Docent-Queue",  "parent_id": None},
        {"id": "FC1", "name": "TestCourse701", "parent_id": "FQ"},
    ]

    def fake_docs(folder_id=None):
        if folder_id == "FQ":
            return {"items": [{"id": "M-ROOT", "title": "R", "authors": ["A"], "year": 2024}], "error": None}
        return {"items": [], "error": "transport: timeout"}

    _patch_mendeley(monkeypatch, folders={"items": folders, "error": None}, documents=fake_docs)

    result = _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    # Root doc still added; sub-folder error didn't abort.
    assert len(result.added) == 1
    assert result.added[0]["mendeley_id"] == "M-ROOT"


def test_doc_without_doi_or_pdf_persists_via_mendeley_id(tmp_docent_home, monkeypatch):
    """Mendeley sometimes returns year=null; some PDFs surface stringified
    years. Anything non-int snaps to None on the snapshot."""
    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue", "parent_id": None}], "error": None},
        documents={"items": [{
            "id": "MEND-1", "title": "Foo", "authors": ["Smith, J"], "year": "2024",
            "identifiers": {"doi": "10.1234/foo"},
        }], "error": None},
    )
    _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))
    assert tool._store.load_queue()[0]["year"] is None


# ----------------------------------------------------------------------
# Config wiring
# ----------------------------------------------------------------------


def test_config_show_surfaces_queue_collection(tmp_docent_home):
    tool = ReadingQueue()
    ctx = _ctx()
    result = tool.config_show(ConfigShowInputs(), ctx)
    assert result.queue_collection == "Docent-Queue"


def test_config_set_queue_collection_round_trips(tmp_docent_home):
    tool = ReadingQueue()
    ctx = _ctx()
    res = tool.config_set(
        ConfigSetInputs(key="queue_collection", value="My-Queue"), ctx
    )
    assert res.ok
    # Reload settings from disk to verify persistence.
    settings = load_settings()
    assert settings.reading.queue_collection == "My-Queue"


# ----------------------------------------------------------------------
# QueueEntry validator relax
# ----------------------------------------------------------------------


def test_legacy_validator_still_blocks_identifier_free_entries(tmp_docent_home):
    """Step 11.2 invariant survives, narrowed by Step 11.10: doi / mendeley_id
    both None is still rejected (pdf_path field gone)."""
    from pydantic import ValidationError
    from docent.tools.reading import QueueEntry
    import pytest as _pytest
    with _pytest.raises(ValidationError):
        QueueEntry(
            id="x", title="X", authors="Y", added="2024-01-01",
            doi=None, mendeley_id=None,
        )


def test_sync_invalidates_reader_cache(tmp_docent_home, monkeypatch):
    """After a real (non-dry) sync, the per-folder cache entry is dropped
    so the next reader call re-fetches fresh data instead of serving the
    stale snapshot the sync just made obsolete."""
    from docent.utils.paths import cache_dir

    tool = ReadingQueue()
    ctx = _ctx()
    _patch_mendeley(
        monkeypatch,
        folders={"items": [{"id": "FQ", "name": "Docent-Queue"}], "error": None},
        documents={"items": [{
            "id": "MEND-1", "title": "T", "authors": ["A"], "year": 2024,
        }], "error": None},
    )

    cache_path = cache_dir() / "reading" / "mendeley_collection.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text('{"FQ": {"fetched_at": 9999999999, "docs": {"OLD": {}}}}', encoding="utf-8")

    _drain(tool.sync_from_mendeley(SyncFromMendeleyInputs(), ctx))

    # Cache file should still exist (other folders may be cached) but FQ entry gone.
    if cache_path.exists():
        import json as _json
        data = _json.loads(cache_path.read_text(encoding="utf-8"))
        assert "FQ" not in data


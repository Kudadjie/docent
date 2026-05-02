"""Tests for `MendeleyCache` (Step 11.7).

File-backed read-through cache wrapping `mendeley_list_documents`. The
`list_documents` callable is injected so these tests never touch the real
MCP subprocess.
"""
from __future__ import annotations

import json

import pytest

from docent.tools.mendeley_cache import MendeleyCache


def _doc(mid: str, title: str = "T") -> dict:
    return {"id": mid, "title": title, "authors": ["A"], "year": 2024}


def _ok(items: list[dict]) -> dict:
    return {"items": items, "error": None}


def test_first_call_fetches_and_writes_cache_file(tmp_path):
    calls = []

    def fake_list(folder_id, launch_command=None):
        calls.append(folder_id)
        return _ok([_doc("m1"), _doc("m2", "Other")])

    cache = MendeleyCache(tmp_path / "c.json", ttl_seconds=60, list_documents=fake_list)
    docs = cache.get_collection("F1")

    assert docs is not None
    assert set(docs.keys()) == {"m1", "m2"}
    assert calls == ["F1"]
    on_disk = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
    assert "F1" in on_disk
    assert "fetched_at" in on_disk["F1"]
    assert set(on_disk["F1"]["docs"].keys()) == {"m1", "m2"}


def test_second_call_within_ttl_is_a_hit(tmp_path):
    calls = []

    def fake_list(folder_id, launch_command=None):
        calls.append(folder_id)
        return _ok([_doc("m1")])

    cache = MendeleyCache(tmp_path / "c.json", ttl_seconds=300, list_documents=fake_list)
    cache.get_collection("F1")
    cache.get_collection("F1")
    cache.get_collection("F1")
    assert len(calls) == 1


def test_call_after_ttl_expiry_refetches(tmp_path):
    calls = []

    def fake_list(folder_id, launch_command=None):
        calls.append(folder_id)
        return _ok([_doc("m1")])

    cache = MendeleyCache(tmp_path / "c.json", ttl_seconds=0, list_documents=fake_list)
    cache.get_collection("F1")
    cache.get_collection("F1")
    assert len(calls) == 2


def test_transport_error_returns_none_and_does_not_poison_cache(tmp_path):
    def fake_list(folder_id, launch_command=None):
        return {"items": [], "error": "transport: nope"}

    cache = MendeleyCache(tmp_path / "c.json", ttl_seconds=60, list_documents=fake_list)
    assert cache.get_collection("F1") is None
    # Cache file must not exist — failed fetches don't get persisted.
    assert not (tmp_path / "c.json").exists()


def test_multiple_folders_cached_independently(tmp_path):
    calls = []

    def fake_list(folder_id, launch_command=None):
        calls.append(folder_id)
        return _ok([_doc(f"m-{folder_id}")])

    cache = MendeleyCache(tmp_path / "c.json", ttl_seconds=300, list_documents=fake_list)
    cache.get_collection("F1")
    cache.get_collection("F2")
    cache.get_collection("F1")  # hit
    cache.get_collection("F2")  # hit
    assert calls == ["F1", "F2"]


def test_invalidate_one_folder_drops_only_that_entry(tmp_path):
    calls = []

    def fake_list(folder_id, launch_command=None):
        calls.append(folder_id)
        return _ok([_doc(f"m-{folder_id}")])

    cache = MendeleyCache(tmp_path / "c.json", ttl_seconds=300, list_documents=fake_list)
    cache.get_collection("F1")
    cache.get_collection("F2")
    cache.invalidate("F1")
    cache.get_collection("F1")  # miss → refetch
    cache.get_collection("F2")  # still cached
    assert calls == ["F1", "F2", "F1"]


def test_invalidate_all_removes_file(tmp_path):
    def fake_list(folder_id, launch_command=None):
        return _ok([_doc("m1")])

    cache = MendeleyCache(tmp_path / "c.json", ttl_seconds=300, list_documents=fake_list)
    cache.get_collection("F1")
    assert (tmp_path / "c.json").exists()
    cache.invalidate()
    assert not (tmp_path / "c.json").exists()


def test_invalidate_missing_file_is_noop(tmp_path):
    def fake_list(folder_id, launch_command=None):
        return _ok([])

    cache = MendeleyCache(tmp_path / "c.json", list_documents=fake_list)
    cache.invalidate()  # should not raise
    cache.invalidate("F1")  # should not raise


def test_corrupt_cache_file_treated_as_empty(tmp_path):
    cache_path = tmp_path / "c.json"
    cache_path.write_text("{not json", encoding="utf-8")

    calls = []

    def fake_list(folder_id, launch_command=None):
        calls.append(folder_id)
        return _ok([_doc("m1")])

    cache = MendeleyCache(cache_path, ttl_seconds=300, list_documents=fake_list)
    docs = cache.get_collection("F1")
    assert docs is not None and set(docs.keys()) == {"m1"}
    assert calls == ["F1"]


def test_docs_without_id_are_skipped(tmp_path):
    def fake_list(folder_id, launch_command=None):
        return _ok([
            {"id": "m1", "title": "ok"},
            {"title": "no id"},
            {"id": "m2", "title": "ok2"},
        ])

    cache = MendeleyCache(tmp_path / "c.json", list_documents=fake_list)
    docs = cache.get_collection("F1")
    assert set(docs.keys()) == {"m1", "m2"}


def test_launch_command_passes_through(tmp_path):
    seen = {}

    def fake_list(folder_id, launch_command=None):
        seen["lc"] = launch_command
        return _ok([_doc("m1")])

    cache = MendeleyCache(tmp_path / "c.json", list_documents=fake_list)
    cache.get_collection("F1", launch_command=["custom", "cmd"])
    assert seen["lc"] == ["custom", "cmd"]


# ----------------------------------------------------------------------
# get_folder_id (11.7-followup)
# ----------------------------------------------------------------------


def _ok_folders(folders: list[dict]) -> dict:
    return {"items": folders, "error": None}


def test_get_folder_id_first_call_fetches_and_caches(tmp_path):
    calls = []

    def fake_folders(launch_command=None):
        calls.append(launch_command)
        return _ok_folders([{"id": "F1", "name": "Docent-Queue"}, {"id": "F2", "name": "Other"}])

    cache = MendeleyCache(tmp_path / "c.json", list_folders=fake_folders)
    assert cache.get_folder_id("Docent-Queue") == "F1"
    # Second call within TTL must not re-fetch.
    assert cache.get_folder_id("Docent-Queue") == "F1"
    assert cache.get_folder_id("Other") == "F2"
    assert len(calls) == 1


def test_get_folder_id_missing_collection_returns_none(tmp_path):
    def fake_folders(launch_command=None):
        return _ok_folders([{"id": "F1", "name": "Other"}])

    cache = MendeleyCache(tmp_path / "c.json", list_folders=fake_folders)
    assert cache.get_folder_id("Docent-Queue") is None


def test_get_folder_id_ambiguous_collection_returns_none(tmp_path):
    def fake_folders(launch_command=None):
        return _ok_folders([
            {"id": "F1", "name": "Dup"},
            {"id": "F2", "name": "Dup"},
            {"id": "F3", "name": "Unique"},
        ])

    cache = MendeleyCache(tmp_path / "c.json", list_folders=fake_folders)
    assert cache.get_folder_id("Dup") is None
    # Non-duplicate sibling still resolves from the same cached fetch.
    assert cache.get_folder_id("Unique") == "F3"


def test_get_folder_id_transport_error_returns_none_no_cache(tmp_path):
    def fake_folders(launch_command=None):
        return {"items": [], "error": "transport: nope"}

    cache = MendeleyCache(tmp_path / "c.json", list_folders=fake_folders)
    assert cache.get_folder_id("Docent-Queue") is None
    assert not (tmp_path / "c.json").exists()


def test_get_folder_id_ttl_expiry_refetches(tmp_path):
    calls = []

    def fake_folders(launch_command=None):
        calls.append(1)
        return _ok_folders([{"id": "F1", "name": "Docent-Queue"}])

    cache = MendeleyCache(
        tmp_path / "c.json",
        list_folders=fake_folders,
        folder_ttl_seconds=0,
    )
    cache.get_folder_id("Docent-Queue")
    cache.get_folder_id("Docent-Queue")
    assert len(calls) == 2


def test_get_folder_id_shares_file_with_get_collection(tmp_path):
    """Both `__folders__` and per-folder doc entries live in one JSON file."""

    def fake_folders(launch_command=None):
        return _ok_folders([{"id": "F1", "name": "Docent-Queue"}])

    def fake_docs(folder_id, launch_command=None):
        return _ok([_doc("m1")])

    cache = MendeleyCache(
        tmp_path / "c.json",
        list_documents=fake_docs,
        list_folders=fake_folders,
    )
    cache.get_folder_id("Docent-Queue")
    cache.get_collection("F1")
    on_disk = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
    assert "__folders__" in on_disk
    assert "F1" in on_disk
    # invalidate(F1) must not nuke the folder map.
    cache.invalidate("F1")
    on_disk_after = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
    assert "__folders__" in on_disk_after
    assert "F1" not in on_disk_after

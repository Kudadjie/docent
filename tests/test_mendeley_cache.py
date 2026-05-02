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

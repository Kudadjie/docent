"""Corrupt JSON recovery tests for all persistent state files (item 56)."""
from __future__ import annotations

import json
import pytest

from docent.bundled_plugins.reading.reading_store import ReadingQueueStore


# ---------------------------------------------------------------------------
# ReadingQueueStore — queue.json, queue-index.json, state.json
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_docent_home):
    from docent.utils.paths import data_dir
    root = data_dir() / "reading"
    root.mkdir(parents=True, exist_ok=True)
    return ReadingQueueStore(root=root)


class TestQueueJsonRecovery:
    def test_corrupt_queue_json_returns_empty_list(self, store):
        store.queue_path.write_text("NOT VALID JSON {{{", encoding="utf-8")
        result = store.load_queue()
        assert result == []

    def test_corrupt_queue_json_logs_warning(self, store, caplog):
        import logging
        store.queue_path.write_text("{bad}", encoding="utf-8")
        caplog.set_level(logging.WARNING, logger="docent.bundled_plugins.reading.reading_store")
        store.load_queue()
        assert any("corrupt" in r.message.lower() for r in caplog.records)

    def test_truncated_queue_json_returns_empty_list(self, store):
        store.queue_path.write_text('["incomplete"', encoding="utf-8")
        assert store.load_queue() == []

    def test_empty_queue_json_returns_empty_list(self, store):
        store.queue_path.write_text("", encoding="utf-8")
        assert store.load_queue() == []

    def test_valid_queue_json_loads_correctly(self, store):
        entries = [{"id": "test-1", "title": "Test"}]
        store.queue_path.write_text(json.dumps(entries), encoding="utf-8")
        assert store.load_queue() == entries


class TestQueueIndexJsonRecovery:
    def test_corrupt_index_returns_empty_dict(self, store):
        store.index_path.write_text("GARBAGE", encoding="utf-8")
        assert store.load_index() == {}

    def test_truncated_index_returns_empty_dict(self, store):
        store.index_path.write_text('{"key":', encoding="utf-8")
        assert store.load_index() == {}

    def test_valid_index_loads_correctly(self, store):
        idx = {"id-1": {"title": "T", "status": "queued", "order": 1}}
        store.index_path.write_text(json.dumps(idx), encoding="utf-8")
        assert store.load_index() == idx


class TestStateJsonRecovery:
    def test_corrupt_state_returns_zero_counts(self, store):
        store.state_path.write_text("NOT JSON", encoding="utf-8")
        result = store.banner_counts()
        assert result.queued == 0
        assert result.reading == 0
        assert result.done == 0

    def test_valid_state_returns_correct_counts(self, store):
        state = {"queued": 3, "reading": 1, "done": 7, "last_updated": "2026-01-01T00:00:00"}
        store.state_path.write_text(json.dumps(state), encoding="utf-8")
        result = store.banner_counts()
        assert result.queued == 3
        assert result.reading == 1
        assert result.done == 7


# ---------------------------------------------------------------------------
# MendeleyCache — mendeley_collection.json
# ---------------------------------------------------------------------------

class TestMendeleyCacheRecovery:
    def test_corrupt_cache_treated_as_empty(self, tmp_docent_home):
        from docent.bundled_plugins.reading.mendeley_cache import MendeleyCache
        from docent.utils.paths import cache_dir

        cache_path = cache_dir() / "paper" / "mendeley_collection.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("NOT JSON {{{{", encoding="utf-8")

        # A fresh cache should handle this gracefully (treat as empty)
        def fake_list_documents(folder_id=None, limit=200, **kwargs):
            return {"items": [], "error": None}

        cache = MendeleyCache(cache_path=cache_path, list_documents=fake_list_documents)
        result = cache.get_collection("fake-folder-id")
        # Should return empty dict, not raise
        assert isinstance(result, dict)

    def test_missing_cache_returns_empty(self, tmp_docent_home):
        from docent.bundled_plugins.reading.mendeley_cache import MendeleyCache
        from docent.utils.paths import cache_dir

        cache_path = cache_dir() / "paper" / "mendeley_collection.json"
        # Ensure cache file does NOT exist

        def fake_list_documents(folder_id=None, limit=200, **kwargs):
            return {"items": [], "error": None}

        cache = MendeleyCache(cache_path=cache_path, list_documents=fake_list_documents)
        result = cache.get_collection("fake-folder-id")
        assert isinstance(result, dict)

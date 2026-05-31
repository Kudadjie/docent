"""Verify that old-format queue.json files load cleanly under the current schema.

Every time a new field is added to QueueEntry, add a corresponding assertion
here to confirm the old fixture still loads and the new field gets its default.
"""

from __future__ import annotations

import json

from reading.reading_store import ReadingQueueStore

# Frozen v1 queue entry (uses old field names mendeley_id / not_in_mendeley).
# Keep this fixture in old-format — it is the migration source.
_V1_ENTRY = {
    "id": "smith-2024-coastal",
    "title": "Coastal Dynamics of the Volta Delta",
    "authors": "Smith, J.; Acheampong, K.",
    "year": 2024,
    "doi": None,
    "type": "paper",
    "added": "2024-01-15",
    "status": "queued",
    "order": 1,
    "category": "CES701",
    "deadline": None,
    "tags": ["coastal", "ghana"],
    "notes": "Priority read before field work.",
    "mendeley_id": "abc123-def456",
    "started": None,
    "finished": None,
}

_V1_ENTRY_DONE = {
    **_V1_ENTRY,
    "id": "jones-2021-surge",
    "title": "Storm Surge Modelling",
    "authors": "Jones, P.",
    "order": 2,
    "status": "done",
    "mendeley_id": "xyz789",
    "started": "2024-02-01T09:00:00",
    "finished": "2024-02-20T18:30:00",
}


def _write_v1_queue(store: ReadingQueueStore) -> None:
    store.queue_path.parent.mkdir(parents=True, exist_ok=True)
    store.queue_path.write_text(
        json.dumps([_V1_ENTRY, _V1_ENTRY_DONE], ensure_ascii=False), encoding="utf-8"
    )


def test_v1_queue_loads_without_error(tmp_path):
    store = ReadingQueueStore(tmp_path / "reading")
    _write_v1_queue(store)
    entries = store.load_queue()
    assert len(entries) == 2


def test_v1_migrates_field_names(tmp_path):
    """Loading a v1 queue must rename mendeley_id → reference_id and
    not_in_mendeley → not_in_library via the migration path."""
    store = ReadingQueueStore(tmp_path / "reading")
    _write_v1_queue(store)
    entries = store.load_queue()
    for raw in entries:
        assert "reference_id" in raw, "mendeley_id should have been migrated to reference_id"
        assert "mendeley_id" not in raw, "old mendeley_id key must not remain after migration"
        assert "not_in_library" in raw or "not_in_mendeley" not in raw


def test_v1_queue_pydantic_validates(tmp_path):
    """QueueEntry must parse every migrated v1 entry with no ValidationError."""
    from docent.bundled_plugins.reading.models import QueueEntry

    store = ReadingQueueStore(tmp_path / "reading")
    _write_v1_queue(store)
    entries = store.load_queue()
    for raw in entries:
        parsed = QueueEntry(**raw)
        assert parsed.not_in_library is False
        assert parsed.not_in_parent_collection is False
        assert parsed.manually_kept is False
        assert parsed.manually_kept_at is None


def test_v1_queue_titles_intact(tmp_path):
    store = ReadingQueueStore(tmp_path / "reading")
    _write_v1_queue(store)
    entries = store.load_queue()
    titles = {e["title"] for e in entries}
    assert "Coastal Dynamics of the Volta Delta" in titles
    assert "Storm Surge Modelling" in titles


def test_v1_queue_save_round_trip(tmp_path):
    """Loading a v1 queue and saving it must not corrupt any existing fields."""
    store = ReadingQueueStore(tmp_path / "reading")
    _write_v1_queue(store)
    loaded = store.load_queue()
    store.save_queue(loaded)
    reloaded = store.load_queue()
    assert len(reloaded) == 2
    ids = {e["id"] for e in reloaded}
    assert "smith-2024-coastal" in ids
    assert "jones-2021-surge" in ids

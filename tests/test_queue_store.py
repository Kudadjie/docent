from __future__ import annotations

import json

from docent.tools.reading_store import BannerCounts, ReadingQueueStore


def _entry(eid: str, status: str = "queued", order: int = 1) -> dict:
    return {
        "id": eid, "title": f"t-{eid}", "authors": "a", "status": status,
        "order": order, "mendeley_id": f"m-{eid}",
    }


def test_load_queue_empty(tmp_path):
    store = ReadingQueueStore(tmp_path / "reading")
    assert store.load_queue() == []
    assert store.load_index() == {}
    assert store.banner_counts() == BannerCounts()


def test_save_load_round_trip(tmp_path):
    store = ReadingQueueStore(tmp_path / "reading")
    queue = [_entry("a-2024-x", order=1)]
    store.save_queue(queue)
    assert store.load_queue() == queue


def test_save_recomputes_index(tmp_path):
    store = ReadingQueueStore(tmp_path / "reading")
    store.save_queue([
        _entry("a-2024-x", status="queued", order=1),
        _entry("b-2023-y", status="done", order=2),
    ])

    index = store.load_index()
    assert set(index.keys()) == {"a-2024-x", "b-2023-y"}
    assert index["a-2024-x"]["status"] == "queued"
    assert index["a-2024-x"]["order"] == 1
    assert index["b-2023-y"]["status"] == "done"


def test_banner_counts_reflect_queue(tmp_path):
    store = ReadingQueueStore(tmp_path / "reading")
    store.save_queue([
        _entry("a", "queued"),
        _entry("b", "queued"),
        _entry("c", "reading"),
        _entry("d", "done"),
    ])

    counts = store.banner_counts()
    assert counts.queued == 2
    assert counts.reading == 1
    assert counts.done == 1


def test_save_self_initializes_directory(tmp_path):
    target = tmp_path / "deep" / "nested" / "reading"
    assert not target.exists()
    store = ReadingQueueStore(target)
    store.save_queue([])

    assert target.is_dir()
    assert (target / "queue.json").is_file()
    assert (target / "queue-index.json").is_file()
    assert (target / "state.json").is_file()


def test_atomic_write_leaves_no_tmp_file(tmp_path):
    store = ReadingQueueStore(tmp_path / "reading")
    store.save_queue([_entry("a")])
    leftovers = list((tmp_path / "reading").glob("*.tmp"))
    assert leftovers == []


def test_load_queue_survives_state_format_drift(tmp_path):
    """If state.json is missing fields (e.g. older schema), banner_counts
    should fill in zeros rather than crash."""
    reading_dir = tmp_path / "reading"
    reading_dir.mkdir(parents=True)
    (reading_dir / "state.json").write_text(json.dumps({"queued": 5}), encoding="utf-8")

    counts = ReadingQueueStore(reading_dir).banner_counts()
    assert counts.queued == 5
    assert counts.reading == 0

from __future__ import annotations

import pytest

from docent.learning import RunLog


def test_append_and_tail_round_trip(tmp_docent_home):
    log = RunLog("test-ns")
    log.append({"event": "first", "n": 1})
    log.append({"event": "second", "n": 2})

    tail = log.tail(2)
    assert [e["event"] for e in tail] == ["first", "second"]
    assert all("timestamp" in e for e in tail)


def test_cap_and_roll_drops_oldest(tmp_docent_home):
    log = RunLog("test-ns", max_lines=3)
    for i in range(5):
        log.append({"event": "e", "n": i})

    entries = log.all()
    assert len(entries) == 3
    assert [e["n"] for e in entries] == [2, 3, 4]


def test_blank_lines_ignored(tmp_docent_home):
    log = RunLog("test-ns")
    log.append({"event": "a"})
    existing = log.path.read_text(encoding="utf-8")
    log.path.write_text("\n\n" + existing + "\n", encoding="utf-8")
    assert len(log.all()) == 1


def test_namespace_validation():
    with pytest.raises(ValueError):
        RunLog("")
    with pytest.raises(ValueError):
        RunLog("bad/ns")
    with pytest.raises(ValueError):
        RunLog("bad\\ns")
    with pytest.raises(ValueError):
        RunLog("ok", max_lines=0)

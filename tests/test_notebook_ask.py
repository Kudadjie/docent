"""NotebookLM chat ask + history-recovery fallback.

`notebooklm ask` blocks until Gemini finishes; if our subprocess timeout kills it
mid-generation the answer still lands in the conversation, so _nlm_ask polls
`notebooklm history` to recover it instead of reporting "no response".
"""

from __future__ import annotations

import json

import docent.bundled_plugins.studio._notebook as nb


def test_normalize_question_collapses_whitespace():
    assert nb._normalize_question("  a\n\n  b   c ") == "a b c"


def test_history_parses_qa_pairs(monkeypatch):
    payload = json.dumps(
        {
            "notebook_id": "nb1",
            "conversation_id": "c1",
            "count": 2,
            "qa_pairs": [
                {"turn": 1, "question": "Q1", "answer": "A1"},
                {"turn": 2, "question": "Q2", "answer": "A2"},
            ],
        }
    )
    monkeypatch.setattr(nb, "_nlm_run", lambda *a, **k: (0, payload, ""))
    assert nb._nlm_history("nb1") == [("Q1", "A1"), ("Q2", "A2")]


def test_history_empty_on_error(monkeypatch):
    monkeypatch.setattr(nb, "_nlm_run", lambda *a, **k: (-1, "", "boom"))
    assert nb._nlm_history("nb1") == []


def test_recover_finds_matching_answer(monkeypatch):
    q = "Analyze this notebook and answer in THREE clearly-headed sections."
    monkeypatch.setattr(nb, "_nlm_history", lambda nb_id: [(q, "RECOVERED")])
    monkeypatch.setattr(nb.time, "sleep", lambda *_: None)
    ticks = iter([0.0, 0.0, 0.0])
    monkeypatch.setattr(nb.time, "monotonic", lambda: next(ticks))
    assert nb._recover_answer_from_history(q, "nb1", recovery_timeout=10) == "RECOVERED"


def test_recover_times_out_without_match(monkeypatch):
    monkeypatch.setattr(nb, "_nlm_history", lambda nb_id: [])  # answer never appears
    monkeypatch.setattr(nb.time, "sleep", lambda *_: None)
    ticks = iter([0.0, 0.0, 200.0])  # jump past the deadline after one poll
    monkeypatch.setattr(nb.time, "monotonic", lambda: next(ticks))
    assert nb._recover_answer_from_history("Q", "nb1", recovery_timeout=10) is None


def test_ask_returns_answer_on_success(monkeypatch):
    monkeypatch.setattr(nb, "_nlm_run", lambda *a, **k: (0, '{"answer": "HI"}', ""))
    assert nb._nlm_ask("q", "nb1") == "HI"


def test_ask_recovers_after_timeout(monkeypatch):
    monkeypatch.setattr(nb, "_nlm_run", lambda *a, **k: (-1, "", "Timeout after 180s"))
    monkeypatch.setattr(nb, "_recover_answer_from_history", lambda *a, **k: "RECOVERED")
    assert nb._nlm_ask("q", "nb1", timeout=1, recovery_timeout=10) == "RECOVERED"


def test_ask_no_recovery_on_non_timeout_failure(monkeypatch):
    called = {"recover": False}
    monkeypatch.setattr(nb, "_nlm_run", lambda *a, **k: (-1, "", "notebooklm not found on PATH"))
    monkeypatch.setattr(
        nb,
        "_recover_answer_from_history",
        lambda *a, **k: called.__setitem__("recover", True) or "X",
    )
    assert nb._nlm_ask("q", "nb1", recovery_timeout=10) is None
    assert called["recover"] is False  # only timeouts trigger recovery


def test_ask_no_recovery_when_disabled(monkeypatch):
    called = {"recover": False}
    monkeypatch.setattr(nb, "_nlm_run", lambda *a, **k: (-1, "", "Timeout after 1s"))
    monkeypatch.setattr(
        nb,
        "_recover_answer_from_history",
        lambda *a, **k: called.__setitem__("recover", True) or "X",
    )
    assert nb._nlm_ask("q", "nb1", recovery_timeout=0) is None  # default: no recovery
    assert called["recover"] is False

"""UI-subprocess NotebookLM auth recovery (_nlm_login_and_wait_ui).

When to-notebook runs as a UI subprocess (no TTY), expired auth must open a
visible login terminal and poll until the user authenticates — not attempt a
non-interactive inline `notebooklm login` (which silently fails into the
activity log).
"""
from __future__ import annotations

import docent.bundled_plugins.studio._notebook as nb


def _drain(gen):
    """Run a ProgressEvent generator to completion; return (events, return_value)."""
    events = []
    try:
        while True:
            events.append(next(gen))
    except StopIteration as stop:
        return events, stop.value


def test_terminal_launch_failure_returns_false(monkeypatch):
    monkeypatch.setattr(nb, "_open_login_terminal", lambda: (False, "no terminal emulator"))
    events, result = _drain(nb._nlm_login_and_wait_ui())
    assert result is False
    assert any("Could not open a login terminal" in e.message for e in events)


def test_auth_success_after_terminal_opens(monkeypatch):
    monkeypatch.setattr(nb, "_open_login_terminal", lambda: (True, ""))
    monkeypatch.setattr(nb.time, "sleep", lambda *_: None)
    monkeypatch.setattr(nb, "_nlm_auth_ok", lambda *a, **k: True)
    events, result = _drain(nb._nlm_login_and_wait_ui(poll_timeout=10, poll_interval=0))
    assert result is True
    assert any("terminal opened" in e.message.lower() for e in events)


def test_timeout_returns_false(monkeypatch):
    monkeypatch.setattr(nb, "_open_login_terminal", lambda: (True, ""))
    monkeypatch.setattr(nb.time, "sleep", lambda *_: None)
    monkeypatch.setattr(nb, "_nlm_auth_ok", lambda *a, **k: False)
    # Deterministic clock: start at 0, stay under deadline once, then exceed it.
    ticks = iter([0.0, 0.0, 1.0, 1.0, 1.0])
    monkeypatch.setattr(nb.time, "monotonic", lambda: next(ticks))
    events, result = _drain(nb._nlm_login_and_wait_ui(poll_timeout=0.5, poll_interval=0))
    assert result is False

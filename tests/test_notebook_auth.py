"""UI-subprocess NotebookLM auth recovery (_nlm_login_and_wait_ui).

When to-notebook runs as a UI subprocess (no TTY), expired auth must open a
visible login terminal and poll until the user authenticates — not attempt a
non-interactive inline `notebooklm login` (which silently fails into the
activity log).
"""
from __future__ import annotations

import types

import pytest

import docent.bundled_plugins.studio._notebook as nb
from docent.bundled_plugins.studio.preflights import _preflight_notebook_auth


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


# ── Upfront preflight (_preflight_notebook_auth) ───────────────────────────────

def _ctx(via_mcp: bool = True):
    return types.SimpleNamespace(via_mcp=via_mcp)


def _inputs(**kw):
    base = dict(output="local", to_notebook=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_preflight_skips_when_not_notebook(monkeypatch):
    seen = {"auth_checked": False}
    monkeypatch.setattr(nb, "_nlm_exe", lambda: "/usr/bin/notebooklm")
    monkeypatch.setattr(
        nb, "_nlm_auth_ok",
        lambda *a, **k: seen.__setitem__("auth_checked", True) or True,
    )
    _preflight_notebook_auth(_inputs(output="local"), _ctx())
    assert seen["auth_checked"] is False  # output=local: never reaches the check


def test_preflight_skips_when_already_authed(monkeypatch):
    opened = {"n": 0}
    monkeypatch.setattr(nb, "_nlm_exe", lambda: "/usr/bin/notebooklm")
    monkeypatch.setattr(nb, "_nlm_auth_ok", lambda *a, **k: True)
    monkeypatch.setattr(
        nb, "_open_login_terminal",
        lambda: (opened.__setitem__("n", opened["n"] + 1), (True, ""))[1],
    )
    _preflight_notebook_auth(_inputs(output="notebook"), _ctx())
    assert opened["n"] == 0  # authed → no terminal opened


def test_preflight_skips_when_not_installed(monkeypatch):
    monkeypatch.setattr(nb, "_nlm_exe", lambda: None)
    # Must return cleanly (push stage surfaces the install hint), not raise.
    _preflight_notebook_auth(_inputs(output="notebook"), _ctx())


def test_preflight_bails_when_login_times_out(monkeypatch):
    monkeypatch.setattr(nb, "_nlm_exe", lambda: "/usr/bin/notebooklm")
    monkeypatch.setattr(nb, "_nlm_auth_ok", lambda *a, **k: False)
    monkeypatch.setattr(nb, "_open_login_terminal", lambda: (True, ""))
    monkeypatch.setattr(nb.time, "sleep", lambda *_: None)
    # deadline = 0 + 120; jump past it after one iteration.
    ticks = iter([0.0, 0.0, 200.0, 200.0, 200.0])
    monkeypatch.setattr(nb.time, "monotonic", lambda: next(ticks))
    with pytest.raises(RuntimeError, match="authentication required"):
        _preflight_notebook_auth(_inputs(output="notebook"), _ctx(via_mcp=True))


def test_preflight_passes_when_login_succeeds(monkeypatch):
    monkeypatch.setattr(nb, "_nlm_exe", lambda: "/usr/bin/notebooklm")
    monkeypatch.setattr(nb, "_open_login_terminal", lambda: (True, ""))
    monkeypatch.setattr(nb.time, "sleep", lambda *_: None)
    # gate sees expired (False); the poll then sees authed (True).
    seq = iter([False, True, True, True])
    monkeypatch.setattr(nb, "_nlm_auth_ok", lambda *a, **k: next(seq))
    _preflight_notebook_auth(_inputs(output="notebook"), _ctx())  # no raise


def test_preflight_force_engages_without_output_field(monkeypatch):
    # to-notebook inputs have no `output`; force=True must still trigger the check.
    monkeypatch.setattr(nb, "_nlm_exe", lambda: "/usr/bin/notebooklm")
    monkeypatch.setattr(nb, "_nlm_auth_ok", lambda *a, **k: False)
    monkeypatch.setattr(nb, "_open_login_terminal", lambda: (True, ""))
    monkeypatch.setattr(nb.time, "sleep", lambda *_: None)
    ticks = iter([0.0, 0.0, 200.0, 200.0, 200.0])
    monkeypatch.setattr(nb.time, "monotonic", lambda: next(ticks))
    with pytest.raises(RuntimeError):
        _preflight_notebook_auth(types.SimpleNamespace(), _ctx(), force=True)


# ── Concurrent-run safety: the auth step holds the NotebookLM session mutex ─────
# Two concurrent notebook-bound runs must never both launch a browser against the
# single shared profile (Chromium ProcessSingleton crash). The auth preflight now
# serializes the check+login behind the machine lock.

def test_preflight_skips_upfront_check_when_session_busy(monkeypatch, tmp_path):
    # When another run holds the session, the upfront auth probe is SKIPPED (no
    # browser launch, no block) — that run is authed, so this run proceeds straight
    # to research and re-checks auth at push time.
    monkeypatch.setattr(nb, "_NOTEBOOKLM_LOCK_PATH", tmp_path / "nlm.lock")
    monkeypatch.setattr(nb, "_nlm_exe", lambda: "/usr/bin/notebooklm")
    probed = {"n": 0}
    monkeypatch.setattr(
        nb, "_nlm_auth_ok",
        lambda *a, **k: probed.__setitem__("n", probed["n"] + 1) or True,
    )
    held = nb.notebooklm_session_lock(timeout=0)
    held.acquire(timeout=0)
    try:
        _preflight_notebook_auth(_inputs(output="notebook"), _ctx(), force=True)  # no raise
    finally:
        held.release()
    assert probed["n"] == 0  # auth probe skipped while the session was busy


def test_preflight_releases_lock_when_authed(monkeypatch, tmp_path):
    monkeypatch.setattr(nb, "_NOTEBOOKLM_LOCK_PATH", tmp_path / "nlm.lock")
    monkeypatch.setattr(nb, "_nlm_exe", lambda: "/usr/bin/notebooklm")
    monkeypatch.setattr(nb, "_nlm_auth_ok", lambda *a, **k: True)
    _preflight_notebook_auth(_inputs(output="notebook"), _ctx())
    # Lock must be free afterwards — the next run can acquire immediately.
    lk = nb.notebooklm_session_lock(timeout=0)
    lk.acquire(timeout=0)
    lk.release()

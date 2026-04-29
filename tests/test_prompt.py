from __future__ import annotations

from pathlib import Path

import pytest

from docent.utils.prompt import NoInteractiveError, prompt_for_path


@pytest.fixture(autouse=True)
def _clear_no_interactive(monkeypatch):
    monkeypatch.delenv("DOCENT_NO_INTERACTIVE", raising=False)


def test_no_interactive_env_raises(monkeypatch):
    monkeypatch.setenv("DOCENT_NO_INTERACTIVE", "1")
    with pytest.raises(NoInteractiveError):
        prompt_for_path("where?")


def test_quote_stripping_regression(monkeypatch):
    """Step 10.5 bug: pasted Windows paths with quotes were persisted verbatim,
    corrupting config. Fix: strip matched outer quotes before returning."""
    monkeypatch.setattr(
        "docent.utils.prompt.Prompt.ask",
        lambda *a, **kw: '"C:\\Users\\x\\Papers"',
    )
    result = prompt_for_path("where?")
    assert result == Path("C:\\Users\\x\\Papers")


def test_single_quote_stripping(monkeypatch):
    monkeypatch.setattr(
        "docent.utils.prompt.Prompt.ask",
        lambda *a, **kw: "'/home/x/papers'",
    )
    result = prompt_for_path("where?")
    assert result == Path("/home/x/papers")


def test_cancel_returns_none(monkeypatch):
    monkeypatch.setattr("docent.utils.prompt.Prompt.ask", lambda *a, **kw: "cancel")
    assert prompt_for_path("where?") is None


def test_empty_returns_none(monkeypatch):
    monkeypatch.setattr("docent.utils.prompt.Prompt.ask", lambda *a, **kw: "")
    assert prompt_for_path("where?") is None


def test_create_scaffolds_default(monkeypatch, tmp_path):
    target = tmp_path / "default-papers"
    monkeypatch.setattr("docent.utils.prompt.Prompt.ask", lambda *a, **kw: "create")
    result = prompt_for_path("where?", default=str(target))
    assert result == target
    assert target.is_dir()

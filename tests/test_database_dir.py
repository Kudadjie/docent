"""Unit tests for ReadingQueue._require_database_dir.

Covers the post-Step-10.7 contract: the method returns
`(path, None)` / `(None, None)` / `(None, error_message)` and never prints.
"""
from __future__ import annotations

from docent.config import load_settings
from docent.core.context import Context
from docent.execution import Executor
from docent.llm import LLMClient
from docent.tools.reading import ReadingQueue
from docent.utils.paths import config_file


def _make_context() -> Context:
    settings = load_settings()
    return Context(settings=settings, llm=LLMClient(settings), executor=Executor())


def test_returns_configured_path(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    ctx = _make_context()
    ctx.settings.reading.database_dir = db

    folder, err = ReadingQueue()._require_database_dir(ctx)

    assert folder == db
    assert err is None


def test_invalid_typed_path_returns_error_and_does_not_persist(
    tmp_docent_home, tmp_path, monkeypatch
):
    """When the user types a non-existent path, return an error message tuple
    and leave config.toml untouched."""
    bogus = tmp_path / "nope"  # never created
    monkeypatch.setattr(
        "docent.tools.reading.prompt_for_path",
        lambda *_a, **_kw: bogus,
    )

    ctx = _make_context()
    assert ctx.settings.reading.database_dir is None

    folder, err = ReadingQueue()._require_database_dir(ctx)

    assert folder is None
    assert err is not None and "doesn't exist" in err
    assert ctx.settings.reading.database_dir is None
    cfg = config_file()
    if cfg.exists():
        assert "database_dir" not in cfg.read_text(encoding="utf-8")

"""Unit tests for _resolve_tavily_key onboarding flow (research_to_notebook/__init__.py)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from docent.config.settings import ResearchSettings, Settings
from docent.core.context import Context


def _make_context(tavily_api_key: str | None = None) -> Context:
    """Build a minimal Context with ResearchSettings for testing."""
    research_settings = ResearchSettings(tavily_api_key=tavily_api_key)
    settings = Settings(research=research_settings)
    from docent.llm import LLMClient
    from docent.execution import Executor
    llm = MagicMock(spec=LLMClient)
    executor = MagicMock(spec=Executor)
    return Context(settings=settings, llm=llm, executor=executor)


@pytest.fixture
def _tty(monkeypatch):
    """Make sys.stdin.isatty() return True so the interactive prompt fires."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)


class TestResolveTavilyKey:
    """Tests for _resolve_tavily_key()."""

    def test_returns_existing_key_when_already_set(self):
        from docent.bundled_plugins.research_to_notebook import _resolve_tavily_key

        ctx = _make_context(tavily_api_key="existing-key-123")
        result = _resolve_tavily_key(ctx)
        assert result == "existing-key-123"

    def test_returns_none_in_non_tty_context(self):
        """In tests/MCP/cron (non-TTY), return None without prompting."""
        from docent.bundled_plugins.research_to_notebook import _resolve_tavily_key

        ctx = _make_context(tavily_api_key=None)
        # By default sys.stdin.isatty() is False in pytest
        result = _resolve_tavily_key(ctx)
        assert result is None

    def test_prompts_and_saves_when_key_is_none(self, _tty, tmp_docent_home):
        from docent.bundled_plugins.research_to_notebook import _resolve_tavily_key
        from docent.utils.paths import config_file

        ctx = _make_context(tavily_api_key=None)

        with patch("typer.prompt", return_value="my-new-tavily-key"):
            result = _resolve_tavily_key(ctx)

        assert result == "my-new-tavily-key"
        raw = config_file().read_text("utf-8")
        assert "my-new-tavily-key" in raw

    def test_prompts_and_saves_when_key_is_empty_string(self, _tty, tmp_docent_home):
        from docent.bundled_plugins.research_to_notebook import _resolve_tavily_key
        from docent.utils.paths import config_file

        ctx = _make_context(tavily_api_key="")

        with patch("typer.prompt", return_value="fresh-key"):
            result = _resolve_tavily_key(ctx)

        assert result == "fresh-key"
        raw = config_file().read_text("utf-8")
        assert "fresh-key" in raw

    def test_returns_none_on_eof_error(self, _tty):
        from docent.bundled_plugins.research_to_notebook import _resolve_tavily_key

        ctx = _make_context(tavily_api_key=None)

        with patch("typer.prompt", side_effect=EOFError):
            result = _resolve_tavily_key(ctx)

        assert result is None

    def test_returns_none_on_keyboard_interrupt(self, _tty):
        from docent.bundled_plugins.research_to_notebook import _resolve_tavily_key

        ctx = _make_context(tavily_api_key=None)

        with patch("typer.prompt", side_effect=KeyboardInterrupt):
            result = _resolve_tavily_key(ctx)

        assert result is None

    def test_returns_none_when_user_enters_blank(self, _tty, tmp_docent_home):
        from docent.bundled_plugins.research_to_notebook import _resolve_tavily_key

        ctx = _make_context(tavily_api_key=None)

        with patch("typer.prompt", return_value="   "):  # whitespace-only input
            result = _resolve_tavily_key(ctx)

        assert result is None

    def test_mutates_in_memory_settings_after_prompt(self, _tty, tmp_docent_home):
        """After prompting, the ResearchSettings object should have the key set."""
        from docent.bundled_plugins.research_to_notebook import _resolve_tavily_key

        ctx = _make_context(tavily_api_key=None)

        with patch("typer.prompt", return_value="session-key"):
            _resolve_tavily_key(ctx)

        assert ctx.settings.research.tavily_api_key == "session-key"

    def test_does_not_prompt_when_key_already_set(self):
        """When key is already present, typer.prompt must not be called."""
        from docent.bundled_plugins.research_to_notebook import _resolve_tavily_key

        ctx = _make_context(tavily_api_key="pre-set-key")

        with patch("typer.prompt") as mock_prompt:
            result = _resolve_tavily_key(ctx)

        mock_prompt.assert_not_called()
        assert result == "pre-set-key"

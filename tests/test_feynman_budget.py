"""Tests for the Feynman budget guard."""
from __future__ import annotations

import inspect
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import docent.bundled_plugins.studio as rtn
from docent.bundled_plugins.studio import (
    DeepInputs,
    FeynmanBudgetExceededError,
    FeynmanNotFoundError,
    ResearchResult,
    StudioTool,
    _extract_feynman_cost,
    _read_daily_spend,
    _run_feynman,
    _write_daily_spend,
)
from docent.config.settings import ResearchSettings, Settings
from docent.core.context import Context


def _drain(maybe_gen: Any) -> Any:
    """Drive a generator action and return its final result."""
    if not inspect.isgenerator(maybe_gen):
        return maybe_gen
    try:
        while True:
            next(maybe_gen)
    except StopIteration as e:
        return e.value


def _mock_context(*, output_dir: Path, budget_usd: float = 0.0) -> Context:
    research = ResearchSettings(
        output_dir=output_dir,
        feynman_budget_usd=budget_usd,
    )
    settings = MagicMock(spec=Settings)
    settings.research = research
    return Context(settings=settings, llm=MagicMock(), executor=MagicMock())


@pytest.fixture(autouse=True)
def reset_spend(tmp_path, monkeypatch):
    """Redirect the spend file to tmp_path so tests don't touch real cache."""
    spend_file = tmp_path / "feynman_spend.json"
    monkeypatch.setattr(rtn, "_spend_file", lambda: spend_file)
    yield spend_file


class TestExtractFeynmanCost:
    def test_extract_cost_dollar_sign(self):
        assert _extract_feynman_cost("Cost: $0.43") == pytest.approx(0.43)

    def test_extract_cost_no_match(self):
        assert _extract_feynman_cost("No cost here") == 0.0

    def test_extract_cost_total_cost_format(self):
        assert _extract_feynman_cost("Total cost: $1.23") == pytest.approx(1.23)


class TestBudgetGuard:
    def _mock_proc(self, returncode: int = 0, stderr: str = "") -> MagicMock:
        """Build a mock Popen object whose communicate() returns (stdout, stderr)."""
        proc = MagicMock()
        proc.communicate.return_value = ("", stderr)
        proc.returncode = returncode
        return proc

    def test_no_budget_no_guard(self, tmp_path: Path):
        _write_daily_spend(9999.0)
        with patch("docent.bundled_plugins.studio.subprocess.Popen", return_value=self._mock_proc(stderr="Cost: $0.43")), \
             patch("docent.bundled_plugins.studio._find_feynman", return_value=["echo"]):
            rc, out, _ = _run_feynman(
                ["echo"], [], tmp_path, tmp_path, "slug", budget_usd=0.0,
            )
        assert rc == 0

    def test_budget_not_exceeded_runs(self, tmp_path: Path):
        with patch("docent.bundled_plugins.studio.subprocess.Popen", return_value=self._mock_proc()), \
             patch("docent.bundled_plugins.studio._find_feynman", return_value=["echo"]):
            rc, out, _ = _run_feynman(
                ["echo"], [], tmp_path, tmp_path, "slug", budget_usd=2.0,
            )
        assert rc == 0

    def test_budget_90_percent_blocks(self, tmp_path: Path):
        _write_daily_spend(1.80)
        with pytest.raises(FeynmanBudgetExceededError):
            _run_feynman(
                ["echo"], [], tmp_path, tmp_path, "slug", budget_usd=2.0,
            )

    def test_budget_accumulates_after_run(self, tmp_path: Path):
        with patch("docent.bundled_plugins.studio.subprocess.Popen", return_value=self._mock_proc(stderr="Cost: $0.50")), \
             patch("docent.bundled_plugins.studio._find_feynman", return_value=["echo"]):
            _run_feynman(
                ["echo"], [], tmp_path, tmp_path, "slug", budget_usd=2.0,
            )
        assert _read_daily_spend() == pytest.approx(0.50)


class TestDeepBudgetExceeded:
    def test_deep_feynman_budget_exceeded_returns_error_result(self, tmp_path: Path):
        tool = StudioTool()
        ctx = _mock_context(output_dir=tmp_path, budget_usd=1.0)
        with patch(
            "docent.bundled_plugins.studio._run_feynman",
            side_effect=FeynmanBudgetExceededError("over budget"),
        ):
            result = _drain(tool.deep_research(DeepInputs(topic="test"), ctx))
        assert result.ok is False
        assert "over budget" in result.message


class TestFindFeynman:
    """Tests for _find_feynman executable resolution."""

    def test_configured_command_found_on_path(self):
        with patch("docent.bundled_plugins.studio.shutil.which", return_value="/usr/local/bin/feynman"):
            result = rtn._find_feynman(["feynman"])
        assert result == ["/usr/local/bin/feynman"]

    def test_configured_command_not_found_raises(self):
        with patch("docent.bundled_plugins.studio.shutil.which", return_value=None):
            with pytest.raises(FeynmanNotFoundError) as exc_info:
                rtn._find_feynman(["feynman"])
            assert "feynman" in str(exc_info.value)

    def test_fallback_to_none_command_finds_on_path(self):
        with patch("docent.bundled_plugins.studio.shutil.which", return_value="/usr/bin/feynman"):
            result = rtn._find_feynman(None)
        assert result == ["/usr/bin/feynman"]

    def test_fallback_to_none_command_windows_npm(self, monkeypatch):
        monkeypatch.setattr("docent.bundled_plugins.studio.shutil.which", lambda _: None)
        monkeypatch.setenv("APPDATA", "/fake/appdata")
        npm_path = Path("/fake/appdata/npm/feynman.cmd")
        monkeypatch.setattr(
            "docent.bundled_plugins.studio.Path.is_file",
            lambda self: str(self).endswith("feynman.cmd"),
        )
        result = rtn._find_feynman(None)
        assert result[0].endswith("feynman.cmd")

    def test_nothing_found_raises(self, monkeypatch):
        monkeypatch.setattr("docent.bundled_plugins.studio.shutil.which", lambda _: None)
        monkeypatch.delenv("APPDATA", raising=False)
        with pytest.raises(FeynmanNotFoundError) as exc_info:
            rtn._find_feynman(None)
        assert "npm install -g feynman" in str(exc_info.value)


class TestFeynmanNotFoundError:
    """Tests for FeynmanNotFoundError in action methods."""

    def test_deep_feynman_not_found_returns_error_result(self, tmp_path: Path):
        tool = StudioTool()
        ctx = _mock_context(output_dir=tmp_path)
        with patch(
            "docent.bundled_plugins.studio._run_feynman",
            side_effect=FeynmanNotFoundError(["feynman"]),
        ):
            result = _drain(tool.deep_research(DeepInputs(topic="test"), ctx))
        assert result.ok is False
        assert "not found" in result.message


class TestSummarizeFeynmanError:
    def test_quota_exhausted_json_lines(self):
        from docent.bundled_plugins.studio import _summarize_feynman_error
        stderr = (
            '{"model":"gemini-3.1-pro","errorMessage":"{\\"error\\":{\\"code\\":429,\\"status\\":\\"RESOURCE_EXHAUSTED\\"}}"}\n'
        )
        msg = _summarize_feynman_error(stderr)
        assert "quota exhausted" in msg.lower()
        assert "gemini-3.1-pro" in msg
        assert "docent studio config-set --key feynman_model" in msg

    def test_auth_failure(self):
        from docent.bundled_plugins.studio import _summarize_feynman_error
        stderr = (
            '{"model":"anthropic/claude-sonnet-4-5","errorMessage":"{\\"error\\":{\\"code\\":401}}"}\n'
        )
        msg = _summarize_feynman_error(stderr)
        assert "auth" in msg.lower()
        assert "feynman setup" in msg.lower()

    def test_unknown_error(self):
        from docent.bundled_plugins.studio import _summarize_feynman_error
        stderr = (
            '{"model":"openai/gpt-4o","errorMessage":"{\\"error\\":{\\"code\\":500,\\"message\\":\\"server error\\"}}"}\n'
        )
        msg = _summarize_feynman_error(stderr)
        assert "code 500" in msg
        assert "openai/gpt-4o" in msg

    def test_empty_stderr(self):
        from docent.bundled_plugins.studio import _summarize_feynman_error
        msg = _summarize_feynman_error("")
        assert "feynman" in msg.lower()
        assert "Model attempted" in msg  # model attribution now shown via _model_note

    def test_invalid_model(self):
        from docent.bundled_plugins.studio import _summarize_feynman_error
        stderr = (
            '{"model":"openai/gpt-5","errorMessage":"{\\"error\\":{\\"code\\":400,\\"message\\":\\"model not found\\"}}"}\n'
        )
        msg = _summarize_feynman_error(stderr)
        assert "model" in msg.lower()
        assert "feynman model list" in msg.lower()

    def test_server_error(self):
        from docent.bundled_plugins.studio import _summarize_feynman_error
        stderr = (
            '{"model":"anthropic/claude-sonnet-4-5","errorMessage":"{\\"error\\":{\\"code\\":503}}"}\n'
        )
        msg = _summarize_feynman_error(stderr)
        assert "server error" in msg.lower()
        assert "anthropic" in msg.lower()

    def test_rate_limited(self):
        from docent.bundled_plugins.studio import _summarize_feynman_error
        stderr = (
            '{"model":"openai/gpt-4o","errorMessage":"{\\"error\\":{\\"code\\":429,\\"message\\":\\"rate limit exceeded\\"}}"}\n'
        )
        msg = _summarize_feynman_error(stderr)
        assert "rate-limited" in msg.lower()

    def test_timeout(self):
        from docent.bundled_plugins.studio import _summarize_feynman_error
        stderr = (
            '{"model":"openai/gpt-4o","errorMessage":"{\\"error\\":{\\"code\\":0,\\"message\\":\\"request timeout\\"}}"}\n'
        )
        msg = _summarize_feynman_error(stderr)
        assert "timed out" in msg.lower()

    def test_with_configured_model(self):
        from docent.bundled_plugins.studio import _summarize_feynman_error
        stderr = (
            '{"model":"gemini-3.1-pro","errorMessage":"{\\"error\\":{\\"code\\":429,\\"status\\":\\"RESOURCE_EXHAUSTED\\"}}"}\n'
        )
        msg = _summarize_feynman_error(stderr, configured_model="anthropic/claude-sonnet-4-5")
        assert "Docent configured" in msg
        assert "anthropic/claude-sonnet-4-5" in msg
        assert "gemini-3.1-pro" in msg

    def test_raw_text_fallback(self):
        from docent.bundled_plugins.studio import _summarize_feynman_error
        # Plain text with no recognizable patterns — falls back to showing tail
        stderr = 'Error: something went wrong with the agent runtime'
        msg = _summarize_feynman_error(stderr)
        assert "Feynman exited with an error" in msg
        assert "something went wrong" in msg
        assert "Model attempted" in msg  # model attribution via _model_note (even if unknown)

    def test_footer_includes_feynman_cli_hint(self):
        """Every error message should include the Feynman CLI adjustment hint."""
        from docent.bundled_plugins.studio import _summarize_feynman_error
        stderr = (
            '{"model":"openai/gpt-4o","errorMessage":"{\\"error\\":{\\"code\\":429,\\"status\\":\\"RESOURCE_EXHAUSTED\\"}}"}\n'
        )
        msg = _summarize_feynman_error(stderr)
        assert "Adjust Feynman settings via its CLI" in msg
        assert "Feynman-native options" in msg

    def test_regex_fallback_extracts_model(self):
        """Regex fallback should show the model extracted from stderr text."""
        from docent.bundled_plugins.studio import _summarize_feynman_error
        stderr = 'some log text... {"model":"openai/gpt-4o","code":429} ...traceback...'
        msg = _summarize_feynman_error(stderr)
        assert "openai/gpt-4o" in msg
        assert "Model attempted" in msg

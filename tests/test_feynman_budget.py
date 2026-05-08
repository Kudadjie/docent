"""Tests for the Feynman budget guard."""
from __future__ import annotations

import inspect
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import docent.bundled_plugins.research_to_notebook as rtn
from docent.bundled_plugins.research_to_notebook import (
    DeepInputs,
    FeynmanBudgetExceededError,
    ResearchResult,
    ResearchTool,
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
    def test_no_budget_no_guard(self, tmp_path: Path):
        _write_daily_spend(9999.0)
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with patch("docent.bundled_plugins.research_to_notebook.subprocess.run", return_value=mock_result):
            rc, out = _run_feynman(
                ["echo"], tmp_path, tmp_path, "slug", budget_usd=0.0,
            )
        assert rc == 0

    def test_budget_not_exceeded_runs(self, tmp_path: Path):
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with patch("docent.bundled_plugins.research_to_notebook.subprocess.run", return_value=mock_result):
            rc, out = _run_feynman(
                ["echo"], tmp_path, tmp_path, "slug", budget_usd=2.0,
            )
        assert rc == 0

    def test_budget_90_percent_blocks(self, tmp_path: Path):
        _write_daily_spend(1.80)
        with pytest.raises(FeynmanBudgetExceededError):
            _run_feynman(
                ["echo"], tmp_path, tmp_path, "slug", budget_usd=2.0,
            )

    def test_budget_accumulates_after_run(self, tmp_path: Path):
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Cost: $0.50", stderr=""
        )
        with patch("docent.bundled_plugins.research_to_notebook.subprocess.run", return_value=mock_result):
            _run_feynman(
                ["echo"], tmp_path, tmp_path, "slug", budget_usd=2.0,
            )
        assert _read_daily_spend() == pytest.approx(0.50)


class TestDeepBudgetExceeded:
    def test_deep_feynman_budget_exceeded_returns_error_result(self, tmp_path: Path):
        tool = ResearchTool()
        ctx = _mock_context(output_dir=tmp_path, budget_usd=1.0)
        with patch(
            "docent.bundled_plugins.research_to_notebook._run_feynman",
            side_effect=FeynmanBudgetExceededError("over budget"),
        ):
            result = _drain(tool.deep(DeepInputs(topic="test"), ctx))
        assert result.ok is False
        assert "over budget" in result.message
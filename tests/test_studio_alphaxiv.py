"""Tests for the alphaXiv search-papers and get-paper studio actions."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docent.config.settings import ResearchSettings, Settings
from docent.core.context import Context
from docent.core.shapes import ErrorShape, LinkShape, MessageShape, MetricShape
from docent.bundled_plugins.studio import (
    GetPaperInputs,
    GetPaperResult,
    SearchPapersInputs,
    SearchPapersResult,
    StudioTool,
)
from docent.bundled_plugins.studio.alphaxiv_client import AlphaXivAuthError


def _mock_context(*, alphaxiv_api_key: str | None = None) -> Context:
    research = ResearchSettings(
        output_dir=Path("/tmp/docent-test"),
        alphaxiv_api_key=alphaxiv_api_key,
    )
    settings = MagicMock(spec=Settings)
    settings.research = research
    return Context(settings=settings, llm=MagicMock(), executor=MagicMock())


SAMPLE_PAPERS = [
    {
        "arxiv_id": "2401.00001",
        "title": "Storm Surge Modelling in Coastal Ghana",
        "abstract": "This paper studies storm surge...",
        "authors": ["A. Author", "B. Coauthor"],
        "topics": ["coastal engineering", "storm surge"],
        "arxiv_url": "https://arxiv.org/abs/2401.00001",
        "github_url": None,
        "published": "2024-01-15",
    },
    {
        "arxiv_id": "2401.00002",
        "title": "Wave Dynamics in the Gulf of Guinea",
        "abstract": "We analyse wave dynamics...",
        "authors": ["C. Researcher"],
        "topics": ["oceanography"],
        "arxiv_url": "https://arxiv.org/abs/2401.00002",
        "github_url": "https://github.com/example/waves",
        "published": "2024-01-20",
    },
]

SAMPLE_OVERVIEW = {
    "arxiv_id": "2401.00001",
    "title": "Storm Surge Modelling in Coastal Ghana",
    "abstract": "This paper studies storm surge in the coastal regions of Ghana.",
    "overview": "# Overview\n\nThis paper presents a comprehensive model...",
}


# ---------------------------------------------------------------------------
# search-papers
# ---------------------------------------------------------------------------

class TestSearchPapers:
    def test_happy_path_returns_papers(self):
        tool = StudioTool()
        ctx = _mock_context(alphaxiv_api_key="test-key")
        with patch("docent.bundled_plugins.studio.alphaxiv_client.search_papers", return_value=SAMPLE_PAPERS) as mock_search:
            result = tool.search_papers(SearchPapersInputs(query="storm surge Ghana"), ctx)
        assert result.ok is True
        assert result.count == 2
        assert result.papers == SAMPLE_PAPERS
        assert "storm surge Ghana" in result.message
        mock_search.assert_called_once_with(
            "storm surge Ghana", api_key="test-key", max_results=10
        )

    def test_respects_max_results(self):
        tool = StudioTool()
        ctx = _mock_context(alphaxiv_api_key="key")
        with patch("docent.bundled_plugins.studio.alphaxiv_client.search_papers", return_value=SAMPLE_PAPERS[:1]):
            result = tool.search_papers(SearchPapersInputs(query="test", max_results=1), ctx)
        assert result.count == 1

    def test_auth_error_returns_ok_false(self):
        tool = StudioTool()
        ctx = _mock_context()
        with patch(
            "docent.bundled_plugins.studio.alphaxiv_client.search_papers",
            side_effect=AlphaXivAuthError("No key configured."),
        ):
            result = tool.search_papers(SearchPapersInputs(query="test"), ctx)
        assert result.ok is False
        assert "No key configured" in result.message
        assert result.count == 0

    def test_api_error_returns_ok_false(self):
        tool = StudioTool()
        ctx = _mock_context(alphaxiv_api_key="key")
        with patch(
            "docent.bundled_plugins.studio.alphaxiv_client.search_papers",
            side_effect=RuntimeError("connection timeout"),
        ):
            result = tool.search_papers(SearchPapersInputs(query="test"), ctx)
        assert result.ok is False
        assert "Search failed" in result.message

    def test_empty_results(self):
        tool = StudioTool()
        ctx = _mock_context(alphaxiv_api_key="key")
        with patch("docent.bundled_plugins.studio.alphaxiv_client.search_papers", return_value=[]):
            result = tool.search_papers(SearchPapersInputs(query="obscure topic xyz"), ctx)
        assert result.ok is True
        assert result.count == 0

    def test_passes_none_api_key_when_not_configured(self):
        tool = StudioTool()
        ctx = _mock_context()  # no key
        with patch("docent.bundled_plugins.studio.alphaxiv_client.search_papers", return_value=[]) as mock_search:
            tool.search_papers(SearchPapersInputs(query="test"), ctx)
        mock_search.assert_called_once_with("test", api_key=None, max_results=10)


# ---------------------------------------------------------------------------
# get-paper
# ---------------------------------------------------------------------------

class TestGetPaper:
    def test_happy_path(self):
        tool = StudioTool()
        ctx = _mock_context(alphaxiv_api_key="test-key")
        with patch(
            "docent.bundled_plugins.studio.alphaxiv_client.get_paper_overview",
            return_value=SAMPLE_OVERVIEW,
        ) as mock_get:
            result = tool.get_paper(GetPaperInputs(arxiv_id="2401.00001"), ctx)
        assert result.ok is True
        assert result.arxiv_id == "2401.00001"
        assert result.title == SAMPLE_OVERVIEW["title"]
        assert result.overview == SAMPLE_OVERVIEW["overview"]
        mock_get.assert_called_once_with("2401.00001", api_key="test-key")

    def test_normalises_arxiv_url(self):
        tool = StudioTool()
        ctx = _mock_context(alphaxiv_api_key="key")
        with patch(
            "docent.bundled_plugins.studio.alphaxiv_client.get_paper_overview",
            return_value=SAMPLE_OVERVIEW,
        ) as mock_get:
            tool.get_paper(GetPaperInputs(arxiv_id="https://arxiv.org/abs/2401.00001"), ctx)
        mock_get.assert_called_once_with("2401.00001", api_key="key")

    def test_normalises_trailing_slash(self):
        tool = StudioTool()
        ctx = _mock_context(alphaxiv_api_key="key")
        with patch(
            "docent.bundled_plugins.studio.alphaxiv_client.get_paper_overview",
            return_value=SAMPLE_OVERVIEW,
        ) as mock_get:
            tool.get_paper(GetPaperInputs(arxiv_id="https://arxiv.org/abs/2401.00001/"), ctx)
        mock_get.assert_called_once_with("2401.00001", api_key="key")

    def test_auth_error_returns_ok_false(self):
        tool = StudioTool()
        ctx = _mock_context()
        with patch(
            "docent.bundled_plugins.studio.alphaxiv_client.get_paper_overview",
            side_effect=AlphaXivAuthError("No key."),
        ):
            result = tool.get_paper(GetPaperInputs(arxiv_id="2401.00001"), ctx)
        assert result.ok is False
        assert "No key" in result.message

    def test_api_error_returns_ok_false(self):
        tool = StudioTool()
        ctx = _mock_context(alphaxiv_api_key="key")
        with patch(
            "docent.bundled_plugins.studio.alphaxiv_client.get_paper_overview",
            side_effect=RuntimeError("404 not found"),
        ):
            result = tool.get_paper(GetPaperInputs(arxiv_id="9999.99999"), ctx)
        assert result.ok is False
        assert "Failed to fetch" in result.message


# ---------------------------------------------------------------------------
# AlphaXivAuthError — _build_client
# ---------------------------------------------------------------------------

class TestAlphaXivAuthError:
    def test_raises_when_no_key_and_saved_key_fails(self):
        from docent.bundled_plugins.studio.alphaxiv_client import _build_client
        with patch(
            "docent.bundled_plugins.studio.alphaxiv_client.AlphaXivClient.from_saved_api_key",
            side_effect=ValueError("no key"),
        ):
            with pytest.raises(AlphaXivAuthError) as exc_info:
                _build_client(None)
        assert "alphaxiv_api_key" in str(exc_info.value)

    def test_uses_explicit_key_without_saved_lookup(self):
        from docent.bundled_plugins.studio.alphaxiv_client import _build_client
        with patch(
            "docent.bundled_plugins.studio.alphaxiv_client.AlphaXivClient.from_api_key",
        ) as mock_from_key:
            _build_client("my-api-key")
        mock_from_key.assert_called_once_with("my-api-key")


# ---------------------------------------------------------------------------
# to_shapes
# ---------------------------------------------------------------------------

class TestToShapes:
    def test_search_ok_emits_metrics_and_links(self):
        result = SearchPapersResult(
            ok=True, query="test", papers=SAMPLE_PAPERS, count=2,
            message="Found 2 paper(s).",
        )
        shapes = result.to_shapes()
        assert any(isinstance(s, MessageShape) for s in shapes)
        assert any(isinstance(s, MetricShape) for s in shapes)
        assert any(isinstance(s, LinkShape) for s in shapes)

    def test_search_fail_emits_error_shape(self):
        result = SearchPapersResult(ok=False, query="test", papers=[], count=0, message="Auth failed.")
        shapes = result.to_shapes()
        assert len(shapes) == 1
        assert isinstance(shapes[0], ErrorShape)

    def test_get_paper_ok_emits_link_and_preview(self):
        result = GetPaperResult(
            ok=True, arxiv_id="2401.00001",
            title="Storm Surge", abstract="Abstract text.",
            overview="# Overview\n\nDetails here.",
            message="Retrieved overview.",
        )
        shapes = result.to_shapes()
        assert any(isinstance(s, LinkShape) for s in shapes)
        assert any(isinstance(s, MetricShape) for s in shapes)

    def test_get_paper_fail_emits_error_shape(self):
        result = GetPaperResult(
            ok=False, arxiv_id="bad-id", title=None,
            abstract="", overview="", message="Not found.",
        )
        shapes = result.to_shapes()
        assert len(shapes) == 1
        assert isinstance(shapes[0], ErrorShape)

"""Tests for studio scholarly-search action and scholarly_client backends."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docent.config.settings import ResearchSettings, Settings
from docent.core.context import Context
from docent.core.shapes import ErrorShape, LinkShape, MessageShape, MetricShape
from docent.bundled_plugins.studio import (
    ScholarlySearchInputs,
    ScholarlySearchResult,
    StudioTool,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _mock_context(*, ss_key: str | None = None) -> Context:
    research = ResearchSettings(
        output_dir=Path("/tmp/docent-test"),
        semantic_scholar_api_key=ss_key,
    )
    settings = MagicMock(spec=Settings)
    settings.research = research
    return Context(settings=settings, llm=MagicMock(), executor=MagicMock())


GS_PAPERS = [
    {
        "title": "Storm Surge in West Africa",
        "authors": ["A. Author", "B. Coauthor"],
        "year": "2023",
        "doi": "",
        "url": "https://example.com/paper1",
        "abstract": "We study storm surge...",
        "source": "google_scholar",
    },
]

SS_PAPERS = [
    {
        "title": "Coastal Flooding Models",
        "authors": ["C. Researcher"],
        "year": "2022",
        "doi": "10.1234/cf",
        "url": "https://doi.org/10.1234/cf",
        "abstract": "A coastal flooding paper.",
        "source": "semantic_scholar",
    },
]

CR_PAPERS = [
    {
        "title": "CrossRef Result Paper",
        "authors": ["D. Scholar"],
        "year": "2021",
        "doi": "10.9999/crp",
        "url": "https://doi.org/10.9999/crp",
        "abstract": "",
        "source": "crossref",
    },
]


# ── scholarly_client unit tests ───────────────────────────────────────────────

class TestSearchScholarlyClient:
    def test_returns_google_scholar_when_available(self):
        from docent.bundled_plugins.studio.scholarly_client import search_scholarly
        with patch(
            "docent.bundled_plugins.studio.scholarly_client._search_google_scholar",
            return_value=GS_PAPERS,
        ):
            papers, backend = search_scholarly("storm surge Ghana")
        assert backend == "google_scholar"
        assert papers == GS_PAPERS

    def test_falls_back_to_semantic_scholar_on_gs_error(self):
        from docent.bundled_plugins.studio.scholarly_client import search_scholarly
        with (
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_google_scholar",
                side_effect=Exception("bot detected"),
            ),
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_semantic_scholar",
                return_value=SS_PAPERS,
            ),
        ):
            papers, backend = search_scholarly("storm surge Ghana")
        assert backend == "semantic_scholar"
        assert papers == SS_PAPERS

    def test_falls_back_to_crossref_on_gs_and_ss_error(self):
        from docent.bundled_plugins.studio.scholarly_client import search_scholarly
        with (
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_google_scholar",
                side_effect=Exception("rate limited"),
            ),
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_semantic_scholar",
                side_effect=Exception("429"),
            ),
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_crossref",
                return_value=CR_PAPERS,
            ),
        ):
            papers, backend = search_scholarly("storm surge Ghana")
        assert backend == "crossref"
        assert papers == CR_PAPERS

    def test_raises_runtime_error_when_all_backends_fail(self):
        from docent.bundled_plugins.studio.scholarly_client import search_scholarly
        with (
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_google_scholar",
                side_effect=Exception("blocked"),
            ),
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_semantic_scholar",
                side_effect=Exception("timeout"),
            ),
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_crossref",
                side_effect=Exception("500"),
            ),
        ):
            with pytest.raises(RuntimeError, match="All search backends"):
                search_scholarly("impossible query")

    def test_gs_empty_triggers_ss_fallback(self):
        """GS returning [] (no results) also triggers the next backend."""
        from docent.bundled_plugins.studio.scholarly_client import search_scholarly
        with (
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_google_scholar",
                return_value=[],
            ),
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_semantic_scholar",
                return_value=SS_PAPERS,
            ),
        ):
            papers, backend = search_scholarly("niche topic")
        assert backend == "semantic_scholar"

    def test_passes_ss_api_key(self):
        from docent.bundled_plugins.studio.scholarly_client import search_scholarly
        with (
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_google_scholar",
                side_effect=Exception("blocked"),
            ),
            patch(
                "docent.bundled_plugins.studio.scholarly_client._search_semantic_scholar",
                return_value=SS_PAPERS,
            ) as mock_ss,
        ):
            search_scholarly("test", semantic_scholar_api_key="s2-key")
        mock_ss.assert_called_once_with("test", 10, api_key="s2-key")


# ── action tests ─────────────────────────────────────────────────────────────

class TestScholarlySearchAction:
    def test_happy_path_google_scholar(self):
        tool = StudioTool()
        ctx = _mock_context()
        with patch(
            "docent.bundled_plugins.studio.scholarly_client.search_scholarly",
            return_value=(GS_PAPERS, "google_scholar"),
        ):
            result = tool.scholarly_search(
                ScholarlySearchInputs(query="storm surge Ghana"), ctx
            )
        assert result.ok is True
        assert result.backend_used == "google_scholar"
        assert result.count == 1
        assert "google_scholar" in result.message

    def test_happy_path_semantic_scholar_fallback(self):
        tool = StudioTool()
        ctx = _mock_context(ss_key="s2-abc")
        with patch(
            "docent.bundled_plugins.studio.scholarly_client.search_scholarly",
            return_value=(SS_PAPERS, "semantic_scholar"),
        ):
            result = tool.scholarly_search(
                ScholarlySearchInputs(query="coastal flooding"), ctx
            )
        assert result.ok is True
        assert result.backend_used == "semantic_scholar"

    def test_all_backends_fail_returns_error(self):
        tool = StudioTool()
        ctx = _mock_context()
        with patch(
            "docent.bundled_plugins.studio.scholarly_client.search_scholarly",
            side_effect=RuntimeError("All search backends (Google Scholar, Semantic Scholar, CrossRef) failed for query: 'x'"),
        ):
            result = tool.scholarly_search(
                ScholarlySearchInputs(query="x"), ctx
            )
        assert result.ok is False
        assert result.backend_used == "none"
        assert "All search backends" in result.message

    def test_no_results_returns_error(self):
        tool = StudioTool()
        ctx = _mock_context()
        with patch(
            "docent.bundled_plugins.studio.scholarly_client.search_scholarly",
            return_value=([], "semantic_scholar"),
        ):
            result = tool.scholarly_search(
                ScholarlySearchInputs(query="obscure topic xyz"), ctx
            )
        assert result.ok is False
        assert "No results" in result.message

    def test_unexpected_exception_returns_error(self):
        tool = StudioTool()
        ctx = _mock_context()
        with patch(
            "docent.bundled_plugins.studio.scholarly_client.search_scholarly",
            side_effect=ValueError("unexpected"),
        ):
            result = tool.scholarly_search(
                ScholarlySearchInputs(query="test"), ctx
            )
        assert result.ok is False
        assert "Search failed" in result.message

    def test_passes_ss_key_from_context(self):
        tool = StudioTool()
        ctx = _mock_context(ss_key="s2-test-key")
        with patch(
            "docent.bundled_plugins.studio.scholarly_client.search_scholarly",
            return_value=(GS_PAPERS, "google_scholar"),
        ) as mock_search:
            tool.scholarly_search(ScholarlySearchInputs(query="test"), ctx)
        mock_search.assert_called_once_with(
            "test", 10, semantic_scholar_api_key="s2-test-key"
        )


# ── to_shapes tests ───────────────────────────────────────────────────────────

class TestScholarlySearchResultShapes:
    def test_ok_result_shapes(self):
        result = ScholarlySearchResult(
            ok=True,
            query="storm surge",
            papers=GS_PAPERS,
            count=1,
            backend_used="google_scholar",
            message="Found 1 paper(s) (via google_scholar).",
        )
        shapes = result.to_shapes()
        types = [type(s).__name__ for s in shapes]
        assert "MessageShape" in types
        assert "MetricShape" in types
        assert any(isinstance(s, MetricShape) and s.label == "Backend" for s in shapes)

    def test_ok_result_includes_link_when_url_present(self):
        result = ScholarlySearchResult(
            ok=True,
            query="coastal",
            papers=SS_PAPERS,
            count=1,
            backend_used="semantic_scholar",
            message="Found 1.",
        )
        shapes = result.to_shapes()
        assert any(isinstance(s, LinkShape) for s in shapes)

    def test_error_result_shapes(self):
        result = ScholarlySearchResult(
            ok=False,
            query="test",
            papers=[],
            count=0,
            backend_used="none",
            message="All backends failed.",
        )
        shapes = result.to_shapes()
        assert len(shapes) == 1
        assert isinstance(shapes[0], ErrorShape)

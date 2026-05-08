"""Unit tests for pipeline.py (run_deep, _parse_json)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docent.bundled_plugins.research_to_notebook.oc_client import OcClient
from docent.bundled_plugins.research_to_notebook.pipeline import (
    _parse_json,
    run_deep,
)


def _make_oc_client(responses: dict | None = None) -> MagicMock:
    """Create a mock OcClient whose .call() returns preset responses in order."""
    client = MagicMock(spec=OcClient)
    client.is_available.return_value = True
    if responses is not None:
        client.call.side_effect = list(responses.values())
    return client


PLANNER_JSON = """{
    "web_queries": ["climate change impacts", "global warming data"],
    "paper_queries": ["climate change review"],
    "domain_queries": ["IPCC climate report"]
}"""

GAP_SUFFICIENT_JSON = """{
    "sufficient": true,
    "coverage_score": 0.8,
    "missing_angles": [],
    "additional_queries": []
}"""

GAP_INSUFFICIENT_JSON = """{
    "sufficient": false,
    "coverage_score": 0.4,
    "missing_angles": ["regional data"],
    "additional_queries": ["regional climate impacts Africa"]
}"""

WRITER_OUTPUT = """## Executive Summary\nClimate change is real.\n"""

VERIFIER_OUTPUT = """## Executive Summary\nClimate change is real. [Source 1]\n\n## Sources\n[1] Test — https://example.com"""

REVIEWER_OUTPUT = """## Peer Review\n\n### Verdict\nREVISE"""


class TestParseJson:
    def test_parse_json_strips_markdown_fences(self):
        text = '```json\n{"key": "value"}\n```'
        result = _parse_json(text)
        assert result == {"key": "value"}

    def test_parse_json_plain(self):
        text = '{"key": "value"}'
        result = _parse_json(text)
        assert result == {"key": "value"}

    def test_parse_json_with_whitespace(self):
        text = '  \n{"key": "value"}\n  '
        result = _parse_json(text)
        assert result == {"key": "value"}


class TestRunDeep:
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.web_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.paper_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.fetch_page")
    def test_run_deep_happy_path(self, mock_fetch, mock_paper, mock_web):
        mock_web.return_value = [
            {"title": "Web Result", "url": "https://example.com", "snippet": "A snippet"},
        ]
        mock_paper.return_value = [
            {
                "title": "Paper Result",
                "url": "https://arxiv.org/abs/2401.12345",
                "snippet": "Abstract",
                "authors": "Smith, J",
                "year": 2024,
            },
        ]
        mock_fetch.return_value = "Full page content"

        oc = _make_oc_client(
            {
                "planner": PLANNER_JSON,
                "gap_eval": GAP_SUFFICIENT_JSON,
                "writer": WRITER_OUTPUT,
                "verifier": VERIFIER_OUTPUT,
                "reviewer": REVIEWER_OUTPUT,
            }
        )

        result = run_deep("climate change", oc)

        assert result["ok"] is True
        assert result["topic"] == "climate change"
        assert result["draft"] == VERIFIER_OUTPUT
        assert result["review"] == REVIEWER_OUTPUT
        assert result["error"] is None
        assert result["rounds"] >= 1
        assert len(result["sources"]) > 0

    def test_run_deep_planner_failure(self):
        oc = MagicMock(spec=OcClient)
        oc.is_available.return_value = True
        oc.call.side_effect = Exception("LLM down")

        result = run_deep("climate change", oc)

        assert result["ok"] is False
        assert "Search planner failed" in result["error"]

    @patch("docent.bundled_plugins.research_to_notebook.pipeline.web_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.paper_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.fetch_page")
    def test_run_deep_writer_failure(self, mock_fetch, mock_paper, mock_web):
        mock_web.return_value = []
        mock_paper.return_value = []
        mock_fetch.return_value = ""

        oc = MagicMock(spec=OcClient)
        oc.is_available.return_value = True
        oc.call.side_effect = [
            PLANNER_JSON,       # planner
            GAP_SUFFICIENT_JSON,  # gap eval
            Exception("Writer LLM failed"),  # writer
        ]

        result = run_deep("climate change", oc)

        assert result["ok"] is False
        assert "Writer failed" in result["error"]

    @patch("docent.bundled_plugins.research_to_notebook.pipeline.web_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.paper_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.fetch_page")
    def test_run_deep_verifier_failure_falls_back_to_draft(
        self, mock_fetch, mock_paper, mock_web
    ):
        mock_web.return_value = [
            {"title": "Web Result", "url": "https://example.com", "snippet": "A snippet"},
        ]
        mock_paper.return_value = []
        mock_fetch.return_value = ""

        oc = MagicMock(spec=OcClient)
        oc.is_available.return_value = True
        oc.call.side_effect = [
            PLANNER_JSON,        # planner
            GAP_SUFFICIENT_JSON,  # gap eval
            WRITER_OUTPUT,        # writer
            Exception("Verifier LLM down"),  # verifier fails
            REVIEWER_OUTPUT,      # reviewer
        ]

        result = run_deep("climate change", oc)

        assert result["ok"] is True
        assert result["draft"] == WRITER_OUTPUT

    @patch("docent.bundled_plugins.research_to_notebook.pipeline.web_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.paper_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.fetch_page")
    def test_run_deep_gap_eval_loops(self, mock_fetch, mock_paper, mock_web):
        mock_web.return_value = [
            {"title": "Initial", "url": "https://example.com/1", "snippet": "S1"},
        ]
        mock_paper.return_value = []
        mock_fetch.return_value = ""

        oc = MagicMock(spec=OcClient)
        oc.is_available.return_value = True
        oc.call.side_effect = [
            PLANNER_JSON,          # planner
            GAP_INSUFFICIENT_JSON,  # gap eval round 1: not sufficient
            GAP_SUFFICIENT_JSON,    # gap eval round 2: sufficient
            WRITER_OUTPUT,
            VERIFIER_OUTPUT,
            REVIEWER_OUTPUT,
        ]

        result = run_deep("climate change", oc)

        assert result["ok"] is True
        assert result["rounds"] == 2

    @patch("docent.bundled_plugins.research_to_notebook.pipeline.web_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.paper_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.fetch_page")
    def test_run_deep_gap_eval_sufficient_stops_loop(
        self, mock_fetch, mock_paper, mock_web
    ):
        mock_web.return_value = [
            {"title": "Web Result", "url": "https://example.com", "snippet": "S"},
        ]
        mock_paper.return_value = []
        mock_fetch.return_value = ""

        oc = MagicMock(spec=OcClient)
        oc.is_available.return_value = True
        oc.call.side_effect = [
            PLANNER_JSON,
            GAP_SUFFICIENT_JSON,
            WRITER_OUTPUT,
            VERIFIER_OUTPUT,
            REVIEWER_OUTPUT,
        ]

        result = run_deep("climate change", oc)

        assert result["ok"] is True
        assert result["rounds"] == 1

    @patch("docent.bundled_plugins.research_to_notebook.pipeline.web_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.paper_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.fetch_page")
    def test_run_deep_deduplicates_sources(self, mock_fetch, mock_paper, mock_web):
        mock_web.return_value = [
            {"title": "Dup", "url": "https://example.com", "snippet": "S1"},
            {"title": "Dup", "url": "https://example.com", "snippet": "S2"},
            {"title": "Unique", "url": "https://other.com", "snippet": "S3"},
        ]
        mock_paper.return_value = []
        mock_fetch.return_value = ""

        oc = MagicMock(spec=OcClient)
        oc.is_available.return_value = True
        oc.call.side_effect = [
            PLANNER_JSON,
            GAP_SUFFICIENT_JSON,
            WRITER_OUTPUT,
            VERIFIER_OUTPUT,
            REVIEWER_OUTPUT,
        ]

        result = run_deep("climate change", oc)

        urls = [s.get("url") for s in result["sources"]]
        assert urls.count("https://example.com") == 1
        assert urls.count("https://other.com") == 1

    def test_run_deep_on_progress_callback(self):
        oc = MagicMock(spec=OcClient)
        oc.is_available.return_value = True
        oc.call.side_effect = Exception("fail immediately")

        events: list[tuple[str, str]] = []

        def on_progress(phase: str, message: str) -> None:
            events.append((phase, message))

        run_deep("test topic", oc, on_progress=on_progress)

        assert len(events) >= 1
        assert events[0][0] == "search_plan"

    @patch("docent.bundled_plugins.research_to_notebook.pipeline.web_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.paper_search")
    @patch("docent.bundled_plugins.research_to_notebook.pipeline.fetch_page")
    def test_second_fetch_round_does_not_refetch_existing_pages(
        self, mock_fetch, mock_paper, mock_web
    ):
        """Regression: round-2 _fetch_round must not re-fetch URLs already fetched in round 1.

        Setup: exactly 5 unique URLs so round 1 fills the budget completely.
        Round 2 (triggered by insufficient gap eval) returns the same 5 URLs —
        all already fetched — so fetch_page must not be called again.
        """
        mock_web.return_value = [
            {"title": f"Result {i}", "url": f"https://example.com/{i}", "snippet": "S"}
            for i in range(5)  # exactly 5 URLs — fills the 5-fetch budget in round 1
        ]
        mock_paper.return_value = []
        mock_fetch.return_value = "fetched content"

        oc = MagicMock(spec=OcClient)
        oc.is_available.return_value = True
        oc.call.side_effect = [
            PLANNER_JSON,
            GAP_INSUFFICIENT_JSON,   # triggers second fetch round with same URLs
            GAP_SUFFICIENT_JSON,
            WRITER_OUTPUT,
            VERIFIER_OUTPUT,
            REVIEWER_OUTPUT,
        ]

        run_deep("climate change", oc)

        # Round 1 fetched 5 pages. Round 2 encounters the same URLs already in
        # full_text — should add 0 new fetches. Total must remain 5.
        assert mock_fetch.call_count == 5
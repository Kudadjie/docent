"""Unit tests for pipeline.py (run_deep, _parse_json)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from docent.bundled_plugins.studio.backend import StudioBackend
from docent.bundled_plugins.studio.pipeline import (
    _fetch_artifact,
    _parse_json,
    run_deep,
    run_lit,
    run_review,
)
from docent.bundled_plugins.studio.search_adapter import FakeSearchAdapter
from docent.core import ProgressEvent

# ── shared fake adapter ────────────────────────────────────────────────────────

_WEB_RESULT = {"title": "Web Result", "url": "https://example.com", "snippet": "A snippet"}
_PAPER_RESULT = {
    "title": "Paper Result", "url": "https://arxiv.org/abs/2401.12345",
    "snippet": "Abstract", "authors": "Smith, J", "year": 2024,
}


def _fake_adapter(**overrides) -> FakeSearchAdapter:
    defaults = dict(
        web_results=[_WEB_RESULT],
        paper_results=[_PAPER_RESULT],
        page_content="Full page content",
    )
    defaults.update(overrides)
    return FakeSearchAdapter(**defaults)


def _make_oc_client(responses: dict | None = None) -> MagicMock:
    """Create a mock OcClient whose .call() returns preset responses in order."""
    client = MagicMock(spec=StudioBackend)
    client.is_available.return_value = True
    if responses is not None:
        client.call.side_effect = list(responses.values())
    return client


def _drain(gen):
    """Drive a generator to completion, collecting ProgressEvents, returning final value."""
    events = []
    try:
        while True:
            value = next(gen)
            if isinstance(value, ProgressEvent):
                events.append(value)
    except StopIteration as e:
        return e.value, events


PLANNER_JSON = """{
    "web_queries": ["climate change impacts", "global warming data"],
    "paper_queries": [],
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

# All output constants must be >= 300 chars to pass the writer length guard.
WRITER_OUTPUT = (
    "## Executive Summary\n\n"
    "Climate change is a critical global issue driven by greenhouse gas emissions. "
    "Scientific evidence confirms rising temperatures, shifting precipitation patterns, "
    "and increased frequency of extreme weather events. Immediate action is required "
    "to limit warming to 1.5°C above pre-industrial levels. This research synthesises "
    "key findings from recent literature to inform policy and adaptation strategies.\n"
)

VERIFIER_OUTPUT = (
    "## Executive Summary\n\n"
    "Climate change is a critical global issue driven by greenhouse gas emissions. [Source 1]\n"
    "Scientific evidence confirms rising temperatures and shifting precipitation patterns. [Source 1]\n"
    "Immediate action is required to limit warming to 1.5°C above pre-industrial levels.\n"
    "This research synthesises key findings from recent literature. [Source 1]\n\n"
    "## Sources\n"
    "[1] Test Source — https://example.com [web]\n"
)

REVIEWER_OUTPUT = (
    "## Peer Review\n\n"
    "### Verdict\nREVISE\n\n"
    "### Strengths\n"
    "- Clear executive summary with appropriate citations.\n"
    "- Well-structured synthesis of climate change evidence.\n\n"
    "### Weaknesses\n"
    "- Some claims could be strengthened with additional sources.\n"
    "- Regional impacts deserve more detail.\n"
)

REFINER_OUTPUT = (
    "## Executive Summary\n\n"
    "Climate change is a critical global issue well-documented in the literature. [Source 1]\n"
    "Scientific evidence confirms rising temperatures, shifting precipitation patterns, "
    "and increased frequency of extreme weather events. [Source 1]\n"
    "Immediate action is required to limit warming to 1.5°C above pre-industrial levels.\n"
    "This refined synthesis incorporates reviewer feedback on regional impacts.\n\n"
    "## Sources\n"
    "[1] Test Source — https://example.com [web]\n"
)


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
    @pytest.fixture(autouse=True)
    def patch_network(self, monkeypatch):
        import docent.bundled_plugins.studio.helpers as _h
        monkeypatch.setattr(_h, "_check_connectivity", lambda *a, **kw: True)

    def test_run_deep_happy_path(self):
        oc = _make_oc_client({
            "planner": PLANNER_JSON,
            "gap_eval": GAP_SUFFICIENT_JSON,
            "writer": WRITER_OUTPUT,
            "verifier": VERIFIER_OUTPUT,
            "reviewer": REVIEWER_OUTPUT,
            "refiner": REFINER_OUTPUT,
        })
        result, events = _drain(run_deep("climate change", oc, adapter=_fake_adapter()))

        assert result["ok"] is True
        assert result["topic"] == "climate change"
        assert result["draft"] == REFINER_OUTPUT
        assert result["review"] == REVIEWER_OUTPUT
        assert result["error"] is None
        assert result["rounds"] >= 1
        assert len(result["sources"]) > 0
        phases = [e.phase for e in events]
        assert "search_plan" in phases
        assert "write" in phases

    def test_run_deep_planner_failure(self):
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = Exception("LLM down")

        result, _ = _drain(run_deep("climate change", oc, adapter=_fake_adapter()))

        assert result["ok"] is False
        assert "Search planner failed" in result["error"]

    def test_run_deep_writer_failure(self):
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = [PLANNER_JSON, GAP_SUFFICIENT_JSON, Exception("Writer LLM failed")]

        result, _ = _drain(run_deep("climate change", oc, adapter=_fake_adapter()))

        assert result["ok"] is False
        assert "Writer failed" in result["error"]

    def test_run_deep_verifier_failure_falls_back_to_draft(self):
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = [
            PLANNER_JSON, GAP_SUFFICIENT_JSON, WRITER_OUTPUT,
            Exception("Verifier LLM down"), REVIEWER_OUTPUT, REFINER_OUTPUT,
        ]
        result, _ = _drain(run_deep("climate change", oc, adapter=_fake_adapter()))

        assert result["ok"] is True
        assert result["draft"] == REFINER_OUTPUT

    def test_run_deep_gap_eval_loops(self):
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = [
            PLANNER_JSON, GAP_INSUFFICIENT_JSON,
            WRITER_OUTPUT, VERIFIER_OUTPUT, REVIEWER_OUTPUT, REFINER_OUTPUT,
        ]
        result, _ = _drain(run_deep("climate change", oc, adapter=_fake_adapter()))

        assert result["ok"] is True
        assert result["rounds"] == 2

    def test_run_deep_gap_eval_sufficient_stops_loop(self):
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = [
            PLANNER_JSON, GAP_SUFFICIENT_JSON,
            WRITER_OUTPUT, VERIFIER_OUTPUT, REVIEWER_OUTPUT, REFINER_OUTPUT,
        ]
        result, _ = _drain(run_deep("climate change", oc, adapter=_fake_adapter()))

        assert result["ok"] is True
        assert result["rounds"] == 1

    def test_run_deep_deduplicates_sources(self):
        adapter = _fake_adapter(web_results=[
            {"title": "Dup", "url": "https://example.com", "snippet": "S1"},
            {"title": "Dup", "url": "https://example.com", "snippet": "S2"},
            {"title": "Unique", "url": "https://other.com", "snippet": "S3"},
        ])
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = [
            PLANNER_JSON, GAP_SUFFICIENT_JSON,
            WRITER_OUTPUT, VERIFIER_OUTPUT, REVIEWER_OUTPUT, REFINER_OUTPUT,
        ]
        result, _ = _drain(run_deep("climate change", oc, adapter=adapter))

        urls = [s.get("url") for s in result["sources"]]
        assert urls.count("https://example.com") == 1
        assert urls.count("https://other.com") == 1

    def test_run_deep_yields_progress_events(self):
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = Exception("fail immediately")

        gen = run_deep("test topic", oc, adapter=_fake_adapter())
        events = []
        try:
            while True:
                v = next(gen)
                if isinstance(v, ProgressEvent):
                    events.append(v)
        except StopIteration:
            pass

        assert len(events) >= 1
        assert events[0].phase == "search_plan"

    def test_second_fetch_round_does_not_refetch_existing_pages(self):
        """Round-2 must not re-fetch URLs already fetched in round 1."""
        five_urls = [
            {"title": f"Result {i}", "url": f"https://example.com/{i}", "snippet": "S"}
            for i in range(5)
        ]
        adapter = FakeSearchAdapter(web_results=five_urls, page_content="fetched content")
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = [
            PLANNER_JSON, GAP_INSUFFICIENT_JSON, GAP_SUFFICIENT_JSON,
            WRITER_OUTPUT, VERIFIER_OUTPUT, REVIEWER_OUTPUT, REFINER_OUTPUT,
        ]
        _drain(run_deep("climate change", oc, adapter=adapter))

        # Round 1 fetched 5 pages; round 2 sees same URLs (already fetched) → 0 new fetches.
        assert len(adapter.fetch_calls) == 5


LIT_PLANNER_JSON = """{
    "web_queries": ["climate change systematic review"],
    "paper_queries": ["climate change meta-analysis", "global warming literature review"],
    "domain_queries": []
}"""


class TestRunLit:
    @pytest.fixture(autouse=True)
    def patch_network(self, monkeypatch):
        import docent.bundled_plugins.studio.helpers as _h
        monkeypatch.setattr(_h, "_check_connectivity", lambda *a, **kw: True)

    def test_run_lit_happy_path(self):
        oc = _make_oc_client({
            "planner": LIT_PLANNER_JSON,
            "gap_eval": GAP_SUFFICIENT_JSON,
            "writer": WRITER_OUTPUT,
            "verifier": VERIFIER_OUTPUT,
            "reviewer": REVIEWER_OUTPUT,
            "refiner": REFINER_OUTPUT,
        })
        result, _ = _drain(run_lit("climate change", oc, adapter=_fake_adapter()))

        assert result["ok"] is True
        assert result["topic"] == "climate change"
        assert result["draft"] == REFINER_OUTPUT
        assert result["review"] == REVIEWER_OUTPUT
        assert result["error"] is None
        assert result["rounds"] >= 1
        assert len(result["sources"]) > 0

    def test_run_lit_planner_failure(self):
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = Exception("LLM down")

        result, _ = _drain(run_lit("climate change", oc, adapter=_fake_adapter()))

        assert result["ok"] is False
        assert "Search planner failed" in result["error"]

    def test_run_lit_uses_lit_prompts(self):
        oc = _make_oc_client({
            "planner": LIT_PLANNER_JSON,
            "gap_eval": GAP_SUFFICIENT_JSON,
            "writer": WRITER_OUTPUT,
            "verifier": VERIFIER_OUTPUT,
            "reviewer": REVIEWER_OUTPUT,
            "refiner": REFINER_OUTPUT,
        })
        result, _ = _drain(run_lit("climate change", oc, adapter=_fake_adapter()))
        assert result["ok"] is True

        first_call_args = oc.call.call_args_list[0]
        first_prompt = first_call_args[0][0]
        assert "climate change" in first_prompt
        assert "literature review" in first_prompt.lower()

    def test_run_lit_writer_failure(self):
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = [LIT_PLANNER_JSON, GAP_SUFFICIENT_JSON, Exception("Writer LLM failed")]

        result, _ = _drain(run_lit("climate change", oc, adapter=_fake_adapter()))

        assert result["ok"] is False
        assert "Writer failed" in result["error"]

    def test_fake_adapter_records_calls(self):
        """FakeSearchAdapter call counters enable fine-grained test assertions."""
        adapter = _fake_adapter()
        oc = _make_oc_client({
            "planner": LIT_PLANNER_JSON,
            "gap_eval": GAP_SUFFICIENT_JSON,
            "writer": WRITER_OUTPUT,
            "verifier": VERIFIER_OUTPUT,
            "reviewer": REVIEWER_OUTPUT,
            "refiner": REFINER_OUTPUT,
        })
        _drain(run_lit("climate change", oc, adapter=adapter))

        # LIT_PLANNER_JSON has 1 web query and 2 paper queries
        assert len(adapter.web_search_calls) >= 1
        assert len(adapter.academic_search_calls) >= 1


class TestFetchArtifact:
    def test_arxiv_id_fetches_url(self):
        with patch("docent.bundled_plugins.studio.pipeline.fetch_page") as mock_fetch:
            mock_fetch.return_value = "ArXiv page content"
            result = _fetch_artifact("2401.12345")
            mock_fetch.assert_called_with("https://arxiv.org/abs/2401.12345", max_chars=6000)
            assert result == "ArXiv page content"

    def test_arxiv_id_with_version(self):
        with patch("docent.bundled_plugins.studio.pipeline.fetch_page") as mock_fetch:
            mock_fetch.return_value = "Content"
            result = _fetch_artifact("2401.12345v2")
            mock_fetch.assert_called_with("https://arxiv.org/abs/2401.12345v2", max_chars=6000)

    def test_url_artifact(self):
        with patch("docent.bundled_plugins.studio.pipeline.fetch_page") as mock_fetch:
            mock_fetch.return_value = "Web page content"
            result = _fetch_artifact("https://example.com/paper")
            mock_fetch.assert_called_with("https://example.com/paper", max_chars=6000)
            assert result == "Web page content"

    def test_http_url_artifact(self):
        with patch("docent.bundled_plugins.studio.pipeline.fetch_page") as mock_fetch:
            mock_fetch.return_value = "Content"
            result = _fetch_artifact("http://example.com/paper")
            mock_fetch.assert_called_with("http://example.com/paper", max_chars=6000)

    def test_unknown_artifact_returns_error_string(self):
        result = _fetch_artifact("not-a-url-or-arxiv")
        assert "Could not fetch" in result


class TestRunReview:
    @patch("docent.bundled_plugins.studio.pipeline.fetch_page")
    def test_run_review_arxiv_id_fetches_url(self, mock_fetch):
        mock_fetch.return_value = "ArXiv page content"
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = ["Researcher notes", "Review result"]

        result, _ = _drain(run_review("2401.12345", oc))

        mock_fetch.assert_any_call("https://arxiv.org/abs/2401.12345", max_chars=6000)
        assert result["ok"] is True

    @patch("docent.bundled_plugins.studio.pipeline.fetch_page")
    def test_run_review_url_artifact(self, mock_fetch):
        mock_fetch.return_value = "Web page content"
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = ["Researcher notes", "Review result"]

        result, _ = _drain(run_review("https://example.com/paper", oc))

        mock_fetch.assert_called_with("https://example.com/paper", max_chars=6000)
        assert result["ok"] is True

    @patch("docent.bundled_plugins.studio.pipeline.fetch_page")
    def test_run_review_happy_path(self, mock_fetch):
        mock_fetch.return_value = "Artifact content here"
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = ["Researcher notes output", "Review output"]

        result, _ = _drain(run_review("2401.12345", oc))

        assert result["ok"] is True
        assert result["artifact"] == "2401.12345"
        assert result["artifact_content"] == "Artifact content here"
        assert result["researcher_notes"] == "Researcher notes output"
        assert result["review"] == "Review output"
        assert result["error"] is None

    @patch("docent.bundled_plugins.studio.pipeline.fetch_page")
    def test_run_review_researcher_failure(self, mock_fetch):
        mock_fetch.return_value = "Some content"
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = Exception("Researcher LLM down")

        result, _ = _drain(run_review("2401.12345", oc))

        assert result["ok"] is False
        assert "Researcher failed" in result["error"]

    @patch("docent.bundled_plugins.studio.pipeline.fetch_page")
    def test_run_review_reviewer_failure_returns_ok(self, mock_fetch):
        mock_fetch.return_value = "Some content"
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = ["Researcher notes", Exception("Reviewer LLM down")]

        result, _ = _drain(run_review("2401.12345", oc))

        assert result["ok"] is True
        assert "(Reviewer unavailable)" in result["review"]


class TestZeroSourceAbort:
    """Tests for the early-abort guard when web_search returns 0 sources."""

    @pytest.fixture(autouse=True)
    def patch_network(self, monkeypatch):
        import docent.bundled_plugins.studio.helpers as _h
        monkeypatch.setattr(_h, "_check_connectivity", lambda *a, **kw: True)

    def test_zero_sources_returns_error(self):
        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        oc.call.side_effect = [PLANNER_JSON, GAP_SUFFICIENT_JSON]

        empty_adapter = FakeSearchAdapter(web_results=[], paper_results=[])
        result, _ = _drain(run_deep("climate change", oc, adapter=empty_adapter))

        assert result["ok"] is False
        assert "0 sources" in result["error"]


class TestTavilyResearchPipeline:
    """Tests for the Tavily research path in run_deep / run_lit."""

    @pytest.fixture(autouse=True)
    def patch_network(self, monkeypatch):
        import docent.bundled_plugins.studio.helpers as _h
        monkeypatch.setattr(_h, "_check_connectivity", lambda *a, **kw: True)

    @patch("docent.bundled_plugins.studio.pipeline.academic_search_parallel", return_value=[])
    @patch("docent.bundled_plugins.studio.pipeline.tavily_research")
    def test_deep_uses_tavily_when_key_provided(self, mock_research, mock_academic):
        tavily_content = (
            "## Climate Change Overview\n\n"
            "Climate change represents one of the most significant challenges of our time. "
            "Rising global temperatures, driven by increasing concentrations of greenhouse "
            "gases in the atmosphere, are causing widespread impacts across ecosystems and "
            "human societies. The Intergovernmental Panel on Climate Change (IPCC) reports "
            "that limiting warming to 1.5°C requires rapid, far-reaching transitions in "
            "energy, land use, transport, and industry. Sea level rise, increased frequency "
            "of extreme weather events, and biodiversity loss are among the key risks. "
            "International cooperation and ambitious national climate policies are essential."
        )

        def research_gen(*args, **kwargs):
            yield ProgressEvent(phase="research", message="Starting Tavily research")
            return {
                "content": tavily_content,
                "sources": [{"title": "S1", "url": "https://s1.com", "snippet": "s1 text"}],
                "request_id": "req-123",
            }
        mock_research.side_effect = research_gen

        refined_output = (
            "## Climate Change Overview (Refined)\n\n"
            "Climate change represents one of the most significant challenges of our time. "
            "Rising global temperatures, driven by greenhouse gas emissions, are causing "
            "widespread impacts. The IPCC reports that limiting warming to 1.5°C requires "
            "rapid transitions in energy, land, and industry. Sea level rise and extreme "
            "weather are key risks. International cooperation and ambitious national climate "
            "policies are essential for effective mitigation and adaptation strategies."
        )

        oc = MagicMock(spec=StudioBackend)
        oc.is_available.return_value = True
        # First call: reviewer, second call: refiner
        oc.call.side_effect = ["Review: ACCEPT — well-structured synthesis.", refined_output]

        result, events = _drain(run_deep("climate change", oc, tavily_api_key="tvly-test"))

        assert result["ok"] is True
        assert result["draft"] == refined_output
        assert len(result["sources"]) == 1
        mock_research.assert_called_once()
        mock_academic.assert_called_once()
        # Reviewer + refiner both called
        assert oc.call.call_count == 2

    @patch("docent.bundled_plugins.studio.pipeline.tavily_research")
    def test_deep_tavily_failure_falls_back_to_manual(self, mock_research):
        """When tavily_research raises, run_deep falls back to manual pipeline."""
        mock_research.side_effect = RuntimeError("Tavily research start failed: API error")

        oc = _make_oc_client({
            "planner": PLANNER_JSON,
            "gap_eval": GAP_SUFFICIENT_JSON,
            "writer": WRITER_OUTPUT,
            "verifier": VERIFIER_OUTPUT,
            "reviewer": REVIEWER_OUTPUT,
        })
        result, events = _drain(
            run_deep("climate change", oc, tavily_api_key="tvly-test", adapter=_fake_adapter())
        )

        assert result["ok"] is True
        fallback_events = [e for e in events if e.phase == "tavily" and e.level == "warn"]
        assert len(fallback_events) >= 1

    def test_deep_no_tavily_key_uses_manual(self):
        """When no Tavily key, run_deep uses the manual pipeline."""
        oc = _make_oc_client({
            "planner": PLANNER_JSON,
            "gap_eval": GAP_SUFFICIENT_JSON,
            "writer": WRITER_OUTPUT,
            "verifier": VERIFIER_OUTPUT,
            "reviewer": REVIEWER_OUTPUT,
        })
        result, _ = _drain(run_deep("climate change", oc, tavily_api_key=None, adapter=_fake_adapter()))

        assert result["ok"] is True
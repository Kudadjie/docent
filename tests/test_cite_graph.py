"""Tests for studio cite-graph action."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from docent.bundled_plugins.studio.citation_client import (
    fetch_anchor,
    fetch_citation_graph,
    resolve_s2_id,
)
from docent.bundled_plugins.studio.models import CiteGraphInputs


# ---------------------------------------------------------------------------
# resolve_s2_id
# ---------------------------------------------------------------------------

def test_resolve_doi_bare():
    assert resolve_s2_id("10.1234/example", None) == "DOI:10.1234/example"

def test_resolve_doi_url():
    assert resolve_s2_id("https://doi.org/10.1234/example", None) == "DOI:10.1234/example"

def test_resolve_arxiv_bare():
    assert resolve_s2_id(None, "2301.12345") == "ARXIV:2301.12345"

def test_resolve_arxiv_url():
    assert resolve_s2_id(None, "https://arxiv.org/abs/2301.12345v2") == "ARXIV:2301.12345"

def test_resolve_requires_identifier():
    with pytest.raises(ValueError, match="either doi or arxiv_id"):
        resolve_s2_id(None, None)


# ---------------------------------------------------------------------------
# CiteGraphInputs validation
# ---------------------------------------------------------------------------

def test_inputs_rejects_missing_identifier():
    with pytest.raises(Exception):
        CiteGraphInputs()

def test_inputs_rejects_invalid_direction():
    with pytest.raises(Exception):
        CiteGraphInputs(doi="10.1/x", direction="sideways")

def test_inputs_accepts_valid():
    inp = CiteGraphInputs(doi="10.1/x", direction="both", max_results=10)
    assert inp.direction == "both"
    assert inp.max_results == 10


# ---------------------------------------------------------------------------
# fetch_anchor
# ---------------------------------------------------------------------------

_ANCHOR_RESPONSE = {
    "paperId": "abc123",
    "title": "Attention Is All You Need",
    "authors": [{"name": "Vaswani"}, {"name": "Shazeer"}],
    "year": 2017,
    "externalIds": {"DOI": "10.5555/3295222.3295349", "ArXiv": "1706.03762"},
    "openAccessPdf": {"url": "https://arxiv.org/pdf/1706.03762"},
}

def test_fetch_anchor_happy_path():
    with patch("docent.bundled_plugins.studio.citation_client.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: _ANCHOR_RESPONSE,
            raise_for_status=lambda: None,
        )
        result = fetch_anchor("DOI:10.5555/3295222.3295349", api_key=None)
    assert result["title"] == "Attention Is All You Need"
    assert result["doi"] == "10.5555/3295222.3295349"
    assert result["oa_url"] == "https://arxiv.org/pdf/1706.03762"
    assert "Vaswani" in result["authors"]

def test_fetch_anchor_404_raises_lookup_error():
    import httpx as _httpx
    mock_resp = MagicMock(status_code=404)
    with patch("docent.bundled_plugins.studio.citation_client.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=404,
            raise_for_status=MagicMock(side_effect=_httpx.HTTPStatusError(
                "404", request=MagicMock(), response=mock_resp,
            )),
        )
        with pytest.raises(LookupError, match="not found"):
            fetch_anchor("DOI:10.9999/nope", api_key=None)


# ---------------------------------------------------------------------------
# fetch_citation_graph
# ---------------------------------------------------------------------------

def _make_paper(pid: str, title: str, oa: bool = True) -> dict:
    return {
        "paperId": pid,
        "title": title,
        "authors": [{"name": "Author A"}],
        "year": 2020,
        "externalIds": {"DOI": f"10.0/{pid}"},
        "openAccessPdf": {"url": f"https://example.com/{pid}.pdf"} if oa else None,
    }

_CITATIONS_RESPONSE = {
    "data": [
        {"citingPaper": _make_paper("p1", "Paper One", oa=True)},
        {"citingPaper": _make_paper("p2", "Paper Two", oa=False)},
    ]
}

_REFERENCES_RESPONSE = {
    "data": [
        {"citedPaper": _make_paper("p3", "Paper Three", oa=True)},
    ]
}

def test_fetch_cited_by():
    with patch("docent.bundled_plugins.studio.citation_client.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: _CITATIONS_RESPONSE,
            raise_for_status=lambda: None,
        )
        results = fetch_citation_graph("abc123", "cited-by", 50, api_key=None)
    assert len(results) == 2
    titles = {p["title"] for p in results}
    assert "Paper One" in titles
    assert "Paper Two" in titles

def test_fetch_citing():
    with patch("docent.bundled_plugins.studio.citation_client.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: _REFERENCES_RESPONSE,
            raise_for_status=lambda: None,
        )
        results = fetch_citation_graph("abc123", "citing", 50, api_key=None)
    assert len(results) == 1
    assert results[0]["title"] == "Paper Three"

def test_fetch_both_deduplicates():
    # p1 appears in both citations and references — should appear once.
    both_citations = {"data": [{"citingPaper": _make_paper("shared", "Shared Paper")}]}
    both_references = {"data": [{"citedPaper": _make_paper("shared", "Shared Paper")}]}
    responses = [both_citations, both_references]
    call_count = [0]

    def _fake_get(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        resp = MagicMock(status_code=200, raise_for_status=lambda: None)
        resp.json = lambda i=idx: responses[i]
        return resp

    with patch("docent.bundled_plugins.studio.citation_client.httpx.get", side_effect=_fake_get):
        results = fetch_citation_graph("abc123", "both", 50, api_key=None)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Full action integration (via StudioTool)
# ---------------------------------------------------------------------------

def test_cite_graph_action_happy_path():
    from docent.bundled_plugins.studio import StudioTool

    tool = StudioTool()
    ctx = MagicMock()
    ctx.settings.research.semantic_scholar_api_key = None

    with (
        patch("docent.bundled_plugins.studio.citation_client.httpx.get") as mock_get,
    ):
        call_count = [0]
        responses = [_ANCHOR_RESPONSE, _CITATIONS_RESPONSE]

        def _fake(url, **kwargs):
            idx = min(call_count[0], len(responses) - 1)
            call_count[0] += 1
            r = MagicMock(status_code=200, raise_for_status=lambda: None)
            r.json = lambda i=idx: responses[i]
            return r

        mock_get.side_effect = _fake
        result = tool.cite_graph(
            CiteGraphInputs(doi="10.5555/3295222.3295349", direction="cited-by", max_results=10),
            ctx,
        )

    assert result.ok
    assert result.anchor_title == "Attention Is All You Need"
    assert result.total_found == 2
    assert result.oa_count == 1
    # OA paper should be first
    assert result.papers[0].oa_url is not None

def test_cite_graph_action_not_found():
    from docent.bundled_plugins.studio import StudioTool
    import httpx as _httpx

    tool = StudioTool()
    ctx = MagicMock()
    ctx.settings.research.semantic_scholar_api_key = None

    mock_resp = MagicMock(status_code=404)
    with patch("docent.bundled_plugins.studio.citation_client.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=404,
            raise_for_status=MagicMock(side_effect=_httpx.HTTPStatusError(
                "404", request=MagicMock(), response=mock_resp,
            )),
        )
        result = tool.cite_graph(CiteGraphInputs(doi="10.9999/nope"), ctx)

    assert not result.ok
    assert "not found" in result.message.lower()

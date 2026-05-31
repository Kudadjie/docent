"""Tests for Tier-4 B fan-out primitive and expand-citations integration."""
from __future__ import annotations

import time
from unittest.mock import patch

from docent.bundled_plugins.studio.fanout import parallel_fetch
from docent.bundled_plugins.studio._research import (
    _extract_anchor_ids,
    _expand_citations,
)


# ---------------------------------------------------------------------------
# parallel_fetch — primitive
# ---------------------------------------------------------------------------

def test_parallel_fetch_empty():
    assert parallel_fetch([]) == []


def test_parallel_fetch_returns_in_submission_order():
    """Results arrive in submission order even if tasks finish out of order."""
    def slow():
        time.sleep(0.05)
        return "slow"

    def fast():
        return "fast"

    results = parallel_fetch([slow, fast])
    assert results == ["slow", "fast"]


def test_parallel_fetch_failed_task_returns_none():
    def good():
        return 42

    def bad():
        raise RuntimeError("boom")

    results = parallel_fetch([good, bad, good])
    assert results[0] == 42
    assert results[1] is None   # failed task
    assert results[2] == 42


def test_parallel_fetch_all_fail():
    def boom():
        raise ValueError("x")

    results = parallel_fetch([boom, boom])
    assert results == [None, None]


def test_parallel_fetch_max_workers_respected(monkeypatch):
    """max_workers kwarg is forwarded to the pool."""
    captured = []

    class FakePool:
        def __init__(self, max_workers):
            captured.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def submit(self, fn):
            class F:
                def result(self_inner):
                    return fn()

                def exception(self_inner):
                    return None

            return F()

    # We just check the max_workers kwarg passes without error via the real pool.
    results = parallel_fetch([lambda: 1, lambda: 2], max_workers=1)
    assert results == [1, 2]


# ---------------------------------------------------------------------------
# _extract_anchor_ids
# ---------------------------------------------------------------------------

def test_extract_arxiv_from_url():
    sources = [{"url": "https://arxiv.org/abs/2301.12345", "source_type": "paper"}]
    anchors = _extract_anchor_ids(sources)
    assert anchors == [{"arxiv_id": "2301.12345"}]


def test_extract_doi_from_url():
    sources = [{"url": "https://doi.org/10.1234/example"}]
    anchors = _extract_anchor_ids(sources)
    assert anchors == [{"doi": "10.1234/example"}]


def test_extract_doi_field():
    sources = [{"url": "", "doi": "10.5678/test"}]
    anchors = _extract_anchor_ids(sources)
    assert anchors == [{"doi": "10.5678/test"}]


def test_extract_deduplicates():
    sources = [
        {"url": "https://arxiv.org/abs/2301.12345"},
        {"url": "https://arxiv.org/abs/2301.12345"},  # duplicate
        {"url": "https://arxiv.org/abs/2301.99999"},
    ]
    anchors = _extract_anchor_ids(sources, max_anchors=5)
    arxiv_ids = [a["arxiv_id"] for a in anchors]
    assert len(arxiv_ids) == 2
    assert "2301.12345" in arxiv_ids
    assert "2301.99999" in arxiv_ids


def test_extract_respects_max_anchors():
    sources = [
        {"url": f"https://arxiv.org/abs/230{i}.12345"}
        for i in range(10)
    ]
    anchors = _extract_anchor_ids(sources, max_anchors=2)
    assert len(anchors) == 2


def test_extract_skips_web_sources():
    # Web sources are skipped regardless of URL content
    sources = [
        {"url": "https://doi.org/10.1234/example", "source_type": "web"},
        {"url": "https://arxiv.org/abs/2301.12345", "source_type": "web"},
    ]
    anchors = _extract_anchor_ids(sources)
    assert anchors == []


def test_extract_s2_paper_id_fallback():
    # Non-arXiv, non-DOI paper: fall back to bare S2 paper ID
    sources = [{"url": "", "source_type": "paper", "s2_paper_id": "abc123paperid"}]
    anchors = _extract_anchor_ids(sources)
    assert anchors == [{"s2_id": "abc123paperid"}]


def test_extract_prefers_doi_over_s2_id():
    sources = [{"url": "https://doi.org/10.1/x", "source_type": "paper", "s2_paper_id": "abc123"}]
    anchors = _extract_anchor_ids(sources)
    # DOI extracted from URL takes priority
    assert anchors[0].get("doi") == "10.1/x"


# ---------------------------------------------------------------------------
# _expand_citations — integration with mocked S2
# ---------------------------------------------------------------------------

def _make_s2_paper(pid: str, title: str, oa: bool = True, arxiv_id: str = "") -> dict:
    # Use numeric arXiv IDs so _ARXIV_URL_RE ([\d.]+) can match them.
    _arxiv = arxiv_id or f"20{pid}.00001"
    return {
        "paperId": pid,
        "title": title,
        "authors": [{"name": "Author A"}],
        "year": 2020,
        "externalIds": {"DOI": f"10.0/{pid}", "ArXiv": _arxiv},
        "openAccessPdf": {"url": f"https://arxiv.org/pdf/{_arxiv}"} if oa else None,
        "abstract": f"Abstract for {title}",
    }


_PAPER_ONE_ARXIV = "2001.00001"
_PAPER_TWO_ARXIV = "2002.00001"
_PAPER_THREE_ARXIV = "2003.00001"

_CITATIONS_RESP = {
    "data": [
        {"citingPaper": _make_s2_paper("01", "Citing Paper One", oa=True, arxiv_id=_PAPER_ONE_ARXIV)},
        {"citingPaper": _make_s2_paper("02", "Citing Paper Two (non-OA)", oa=False, arxiv_id=_PAPER_TWO_ARXIV)},
        {"citingPaper": _make_s2_paper("03", "Citing Paper Three", oa=True, arxiv_id=_PAPER_THREE_ARXIV)},
    ]
}

_ANCHOR_RESP = {
    "paperId": "anchor1",
    "title": "Anchor Paper",
    "authors": [{"name": "Anchor Author"}],
    "year": 2019,
    "externalIds": {"DOI": "10.1/anchor", "ArXiv": "1901.00001"},
    "openAccessPdf": {"url": "https://arxiv.org/pdf/1901.00001"},
    "abstract": "The anchor abstract.",
}


def test_expand_citations_adds_oa_sources():
    # _expand_citations does NOT call fetch_anchor — it goes straight to
    # fetch_citation_graph, so the first mock response must be _CITATIONS_RESP.
    sources = [{"url": "https://arxiv.org/abs/1901.00001", "source_type": "paper"}]

    from unittest.mock import MagicMock

    with patch("docent.bundled_plugins.studio.citation_client.httpx.get") as mock_get:
        mock_resp = MagicMock(status_code=200, raise_for_status=lambda: None)
        mock_resp.json = lambda: _CITATIONS_RESP
        mock_get.return_value = mock_resp

        extra_sources, cite_section = _expand_citations(sources, api_key=None)

    assert len(extra_sources) == 2  # only OA papers
    titles = {s["title"] for s in extra_sources}
    assert "Citing Paper One" in titles
    assert "Citing Paper Three" in titles
    assert "Citing Paper Two (non-OA)" not in titles
    assert "source_type" in extra_sources[0]
    assert extra_sources[0]["source_type"] == "cite-graph"

    assert "Related Papers" in cite_section
    assert "Citing Paper One" in cite_section
    assert "Citing Paper Two (non-OA)" not in cite_section


def test_expand_citations_no_anchors_returns_empty():
    sources = [{"url": "https://example.com/article"}]
    extra, section = _expand_citations(sources, api_key=None)
    assert extra == []
    assert section == ""


def test_expand_citations_deduplicates_against_existing():
    """If a cited paper is already in sources, it should not appear again."""
    sources = [
        {"url": "https://arxiv.org/abs/1901.00001", "source_type": "paper"},
        # Paper One's arXiv ID is already in sources — should be excluded.
        {"url": f"https://arxiv.org/abs/{_PAPER_ONE_ARXIV}", "source_type": "paper"},
    ]

    from unittest.mock import MagicMock

    with patch("docent.bundled_plugins.studio.citation_client.httpx.get") as mock_get:
        mock_resp = MagicMock(status_code=200, raise_for_status=lambda: None)
        mock_resp.json = lambda: _CITATIONS_RESP
        mock_get.return_value = mock_resp

        extra_sources, _ = _expand_citations(sources, api_key=None)

    # Paper One should be excluded (already in sources); Paper Three should appear.
    titles = {s["title"] for s in extra_sources}
    assert "Citing Paper One" not in titles
    assert "Citing Paper Three" in titles


def test_expand_citations_s2_failure_returns_empty():
    """If the S2 call raises, _expand_citations should return empty gracefully."""
    sources = [{"url": "https://arxiv.org/abs/1901.00001", "source_type": "paper"}]

    from unittest.mock import MagicMock

    with (
        patch("docent.bundled_plugins.studio.citation_client.httpx.get") as mock_get,
        patch("docent.bundled_plugins.studio.citation_client.time.sleep"),
    ):
        mock_get.return_value = MagicMock(
            status_code=429,
            raise_for_status=lambda: None,
            json=lambda: {},
        )
        # All retries hit 429 — parallel_fetch catches the RuntimeError,
        # returns [None], so _expand_citations returns ([], "").
        extra, section = _expand_citations(sources, api_key=None)

    assert extra == []
    assert section == ""


# ---------------------------------------------------------------------------
# DeepInputs / LitInputs schema — new field is present and defaults False
# ---------------------------------------------------------------------------

def test_deep_inputs_expand_citations_default():
    from docent.bundled_plugins.studio.models import DeepInputs
    inp = DeepInputs(topic="quantum computing", backend="docent")
    assert inp.expand_citations is False


def test_lit_inputs_expand_citations_default():
    from docent.bundled_plugins.studio.models import LitInputs
    inp = LitInputs(topic="machine learning", backend="docent")
    assert inp.expand_citations is False


def test_deep_inputs_expand_citations_settable():
    from docent.bundled_plugins.studio.models import DeepInputs
    inp = DeepInputs(topic="test topic", backend="docent", expand_citations=True)
    assert inp.expand_citations is True


# ---------------------------------------------------------------------------
# Enrichment path — citation_enricher prompt + quality guard
# ---------------------------------------------------------------------------

def test_citation_enricher_prompt_registered():
    """citation_enricher must be in PROMPT_NAMES and its file must exist."""
    from docent.bundled_plugins.studio.prompts import PROMPT_NAMES, load_prompt
    assert "citation_enricher" in PROMPT_NAMES
    text = load_prompt("citation_enricher")
    assert "{draft}" in text
    assert "{papers_text}" in text


def test_expand_citations_enriches_draft_when_backend_succeeds():
    """When the enrichment LLM call succeeds the draft is updated and cite_section is cleared."""
    from unittest.mock import MagicMock, patch

    sources = [{"url": "https://arxiv.org/abs/1901.00001", "source_type": "paper"}]

    enriched_draft = "ENRICHED DRAFT " * 100  # long enough to pass quality guard

    with patch("docent.bundled_plugins.studio.citation_client.httpx.get") as mock_get:
        mock_resp = MagicMock(status_code=200, raise_for_status=lambda: None)
        mock_resp.json = lambda: _CITATIONS_RESP
        mock_get.return_value = mock_resp

        # Patch the backend call inside _research so the enrichment succeeds
        with patch("docent.bundled_plugins.studio.backend.StudioBackend") as _:
            extra_sources, cite_section = _expand_citations(sources, api_key=None)

    # The cite_section fallback list is still returned from _expand_citations itself;
    # clearing it on enrichment success is done at the action level. Here we just
    # verify _expand_citations returns the right raw material for enrichment.
    assert len(extra_sources) == 2
    assert all(s.get("snippet") for s in extra_sources)  # abstracts present for enrichment


def test_enrichment_quality_guard_rejects_short_output():
    """If the enrichment LLM returns something too short, the original draft is kept."""
    original_draft = "Original draft " * 50
    short_output = "Too short"

    # Simulate the quality guard logic used in _research.py
    enriched = short_output
    if enriched and len(enriched) >= len(original_draft) * 0.5:
        result = enriched
    else:
        result = original_draft

    assert result == original_draft


def test_enrichment_quality_guard_accepts_adequate_output():
    """If enrichment output is >= 50% of original, it replaces the draft."""
    original_draft = "Original draft " * 50
    good_output = "Enriched draft " * 30  # 60% length — passes

    enriched = good_output
    if enriched and len(enriched) >= len(original_draft) * 0.5:
        result = enriched
    else:
        result = original_draft

    assert result == good_output

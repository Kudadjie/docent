from __future__ import annotations

import pytest

from docent.tools.paper import AddInputs
from docent.tools.paper_metadata import resolve_metadata


class _DummyExecutor:
    """resolve_metadata only touches `executor` inside crossref_lookup, which we
    monkeypatch in every test below — so a stub is enough."""

    def run(self, *args, **kwargs):
        raise AssertionError("crossref_lookup should be patched, not called")


def test_doi_to_crossref_hit(monkeypatch):
    monkeypatch.setattr(
        "docent.tools.paper_metadata.crossref_lookup",
        lambda doi, executor: {
            "title": "T", "authors": "A", "year": 2020, "doi": "10.1/x",
        },
    )
    monkeypatch.setattr(
        "docent.tools.paper_metadata.extract_pdf_metadata",
        lambda pdf_path: pytest.fail("PDF path should not be touched"),
    )

    meta, source = resolve_metadata(AddInputs(doi="10.1/x"), _DummyExecutor())
    assert source == "doi-crossref"
    assert meta["title"] == "T"


def test_pdf_doi_to_crossref(monkeypatch):
    monkeypatch.setattr(
        "docent.tools.paper_metadata.crossref_lookup",
        lambda doi, executor: {
            "title": "From-PDF-DOI", "authors": "X", "year": 2021, "doi": "10.2/y",
        },
    )
    monkeypatch.setattr(
        "docent.tools.paper_metadata.extract_pdf_metadata",
        lambda pdf_path: {"doi": "10.2/y", "title": "PDF-Title"},
    )

    meta, source = resolve_metadata(AddInputs(pdf="/fake.pdf"), _DummyExecutor())
    assert source == "pdf-doi-crossref"
    assert meta["title"] == "From-PDF-DOI"


def test_pdf_metadata_when_crossref_misses(monkeypatch):
    monkeypatch.setattr(
        "docent.tools.paper_metadata.crossref_lookup",
        lambda doi, executor: None,
    )
    monkeypatch.setattr(
        "docent.tools.paper_metadata.crossref_title_search",
        lambda title, executor, threshold=0.92: None,
    )
    monkeypatch.setattr(
        "docent.tools.paper_metadata.extract_pdf_metadata",
        lambda pdf_path: {"title": "Embedded Title", "authors": "Embedded"},
    )

    meta, source = resolve_metadata(AddInputs(pdf="/fake.pdf"), _DummyExecutor())
    assert source == "pdf-metadata"
    assert meta["title"] == "Embedded Title"
    assert meta["authors"] == "Embedded"


def test_pdf_title_search_hit(monkeypatch):
    """No DOI in PDF, but /Title resolves via CrossRef title-search — we should
    prefer the CrossRef-authoritative authors/year/doi over the raw PDF info."""
    monkeypatch.setattr(
        "docent.tools.paper_metadata.crossref_lookup",
        lambda doi, executor: None,
    )
    monkeypatch.setattr(
        "docent.tools.paper_metadata.extract_pdf_metadata",
        lambda pdf_path: {"title": "Wave Runup on Beaches", "authors": "Bad/garbled"},
    )
    monkeypatch.setattr(
        "docent.tools.paper_metadata.crossref_title_search",
        lambda title, executor, threshold=0.92: {
            "title": "Wave Runup on Beaches",
            "authors": "Smith, J., Doe, A.",
            "year": 2018,
            "doi": "10.99/wave",
        },
    )

    meta, source = resolve_metadata(AddInputs(pdf="/fake.pdf"), _DummyExecutor())
    assert source == "pdf-title-crossref"
    assert meta["doi"] == "10.99/wave"
    assert meta["authors"] == "Smith, J., Doe, A."
    assert meta["year"] == 2018


def test_pdf_title_search_rejected_falls_through(monkeypatch):
    """Title-search returning None (fuzzy guard fired) must fall through to
    the raw `pdf-metadata` source — same as if the helper didn't exist."""
    monkeypatch.setattr(
        "docent.tools.paper_metadata.crossref_lookup",
        lambda doi, executor: None,
    )
    monkeypatch.setattr(
        "docent.tools.paper_metadata.extract_pdf_metadata",
        lambda pdf_path: {"title": "Ambiguous Short Title"},
    )
    monkeypatch.setattr(
        "docent.tools.paper_metadata.crossref_title_search",
        lambda title, executor, threshold=0.92: None,
    )

    meta, source = resolve_metadata(AddInputs(pdf="/fake.pdf"), _DummyExecutor())
    assert source == "pdf-metadata"
    assert meta["title"] == "Ambiguous Short Title"


def test_filename_fallback(monkeypatch):
    monkeypatch.setattr(
        "docent.tools.paper_metadata.crossref_lookup",
        lambda doi, executor: None,
    )
    monkeypatch.setattr(
        "docent.tools.paper_metadata.extract_pdf_metadata",
        lambda pdf_path: None,
    )

    meta, source = resolve_metadata(
        AddInputs(pdf="/some/dir/Smith-2019-topic-paper.pdf"), _DummyExecutor()
    )
    assert source == "filename"
    assert meta["title"] == "Smith 2019 topic paper"
    assert meta["year"] == 2019


def test_filename_fallback_underscore_separated(monkeypatch):
    """Mendeley-style export: `Smith_2019_topic.pdf`. `_` is a Python word char,
    so a naive `\\b(?:19|20)\\d{2}\\b` against the raw stem would miss the year;
    `filename_heuristic` runs the year regex against the normalized title to
    avoid that trap."""
    monkeypatch.setattr(
        "docent.tools.paper_metadata.crossref_lookup",
        lambda doi, executor: None,
    )
    monkeypatch.setattr(
        "docent.tools.paper_metadata.extract_pdf_metadata",
        lambda pdf_path: None,
    )

    meta, source = resolve_metadata(
        AddInputs(pdf="/some/dir/Smith_2019_topic_paper.pdf"), _DummyExecutor()
    )
    assert source == "filename"
    assert meta["title"] == "Smith 2019 topic paper"
    assert meta["year"] == 2019


def test_explicit_overrides_extracted(monkeypatch):
    monkeypatch.setattr(
        "docent.tools.paper_metadata.crossref_lookup",
        lambda doi, executor: {
            "title": "FromDOI", "authors": "X", "year": 2020, "doi": "10.1/x",
        },
    )

    meta, source = resolve_metadata(
        AddInputs(doi="10.1/x", title="Override", year=2099), _DummyExecutor()
    )
    assert source == "doi-crossref"
    assert meta["title"] == "Override"
    assert meta["year"] == 2099


# ---- crossref_title_search direct unit tests --------------------------------

import json as _json
from types import SimpleNamespace

from docent.tools.paper_metadata import (
    _extract_title_by_font_size,
    crossref_title_search,
)


class _CrossRefStubExecutor:
    """Returns a canned CrossRef /works?query.bibliographic= response."""

    def __init__(self, items: list[dict]):
        self._payload = _json.dumps({"message": {"items": items}})

    def run(self, *args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=self._payload, stderr="")


def test_crossref_title_search_accepts_near_exact():
    items = [{
        "title": ["Wave Runup on Sandy Beaches: A Review"],
        "author": [{"family": "Smith", "given": "J."}],
        "issued": {"date-parts": [[2018]]},
        "DOI": "10.99/wave",
    }]
    out = crossref_title_search("Wave Runup on Sandy Beaches A Review", _CrossRefStubExecutor(items))
    assert out is not None
    assert out["doi"] == "10.99/wave"
    assert out["year"] == 2018


def test_crossref_title_search_rejects_low_similarity():
    """Fuzzy guard must reject CrossRef's top-ranked candidate when it isn't
    actually the paper we asked about (the Step 11.2 failure mode)."""
    items = [{
        "title": ["Completely Unrelated Paper About Mitochondria"],
        "author": [{"family": "Other"}],
        "issued": {"date-parts": [[2010]]},
        "DOI": "10.99/wrong",
    }]
    assert crossref_title_search("Wave Runup on Sandy Beaches", _CrossRefStubExecutor(items)) is None


def test_crossref_title_search_empty_query():
    assert crossref_title_search("", _CrossRefStubExecutor([])) is None
    assert crossref_title_search("   ", _CrossRefStubExecutor([])) is None


# ---- font-size title heuristic ----------------------------------------------

class _FakePage:
    def __init__(self, runs: list[tuple[float, str]]):
        self._runs = runs

    def extract_text(self, visitor_text=None):
        if visitor_text is None:
            return ""
        for size, text in self._runs:
            visitor_text(text, None, None, None, size)
        return ""


class _FakeReader:
    def __init__(self, pages: list[_FakePage]):
        self.pages = pages


def test_font_size_title_picks_largest_run():
    reader = _FakeReader([_FakePage([
        (24.0, "A Long Important Title About Things"),
        (10.0, "Smith, J.; Doe, A."),
        (10.0, "University of Somewhere"),
        (12.0, "Abstract: this paper discusses..."),
    ])])
    assert _extract_title_by_font_size(reader) == "A Long Important Title About Things"


def test_font_size_title_skips_too_short_runs():
    """Largest-size text might be a single letter logo or page number — guard
    against that with a min-length floor."""
    reader = _FakeReader([_FakePage([
        (40.0, "X"),
        (24.0, "The Real Title Goes Here Below"),
        (10.0, "body text body text"),
    ])])
    assert _extract_title_by_font_size(reader) == "The Real Title Goes Here Below"


def test_font_size_title_returns_none_on_empty_page():
    assert _extract_title_by_font_size(_FakeReader([_FakePage([])])) is None

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
        "docent.tools.paper_metadata.extract_pdf_metadata",
        lambda pdf_path: {"title": "Embedded Title", "authors": "Embedded"},
    )

    meta, source = resolve_metadata(AddInputs(pdf="/fake.pdf"), _DummyExecutor())
    assert source == "pdf-metadata"
    assert meta["title"] == "Embedded Title"
    assert meta["authors"] == "Embedded"


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

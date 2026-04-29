from __future__ import annotations

import pytest

from docent.tools.paper import AddInputs, PaperPipeline


class _DummyContext:
    """_resolve_metadata only touches context.executor inside _crossref_lookup,
    which we monkeypatch in every test below — so a stub is enough."""
    executor = None


def test_doi_to_crossref_hit(monkeypatch):
    monkeypatch.setattr(
        PaperPipeline, "_crossref_lookup",
        lambda self, doi, executor: {
            "title": "T", "authors": "A", "year": 2020, "doi": "10.1/x",
        },
    )
    monkeypatch.setattr(
        PaperPipeline, "_extract_pdf_metadata",
        staticmethod(lambda pdf_path: pytest.fail("PDF path should not be touched")),
    )

    meta, source = PaperPipeline()._resolve_metadata(
        AddInputs(doi="10.1/x"), _DummyContext()
    )
    assert source == "doi-crossref"
    assert meta["title"] == "T"


def test_pdf_doi_to_crossref(monkeypatch):
    monkeypatch.setattr(
        PaperPipeline, "_crossref_lookup",
        lambda self, doi, executor: {
            "title": "From-PDF-DOI", "authors": "X", "year": 2021, "doi": "10.2/y",
        },
    )
    monkeypatch.setattr(
        PaperPipeline, "_extract_pdf_metadata",
        staticmethod(lambda pdf_path: {"doi": "10.2/y", "title": "PDF-Title"}),
    )

    meta, source = PaperPipeline()._resolve_metadata(
        AddInputs(pdf="/fake.pdf"), _DummyContext()
    )
    assert source == "pdf-doi-crossref"
    assert meta["title"] == "From-PDF-DOI"


def test_pdf_metadata_when_crossref_misses(monkeypatch):
    monkeypatch.setattr(
        PaperPipeline, "_crossref_lookup",
        lambda self, doi, executor: None,
    )
    monkeypatch.setattr(
        PaperPipeline, "_extract_pdf_metadata",
        staticmethod(lambda pdf_path: {"title": "Embedded Title", "authors": "Embedded"}),
    )

    meta, source = PaperPipeline()._resolve_metadata(
        AddInputs(pdf="/fake.pdf"), _DummyContext()
    )
    assert source == "pdf-metadata"
    assert meta["title"] == "Embedded Title"
    assert meta["authors"] == "Embedded"


def test_filename_fallback(monkeypatch):
    monkeypatch.setattr(
        PaperPipeline, "_crossref_lookup",
        lambda self, doi, executor: None,
    )
    monkeypatch.setattr(
        PaperPipeline, "_extract_pdf_metadata",
        staticmethod(lambda pdf_path: None),
    )

    meta, source = PaperPipeline()._resolve_metadata(
        AddInputs(pdf="/some/dir/Smith-2019-topic-paper.pdf"), _DummyContext()
    )
    assert source == "filename"
    assert meta["title"] == "Smith 2019 topic paper"
    assert meta["year"] == 2019


def test_filename_fallback_underscore_separated(monkeypatch):
    """Mendeley-style export: `Smith_2019_topic.pdf`. `_` is a Python word char,
    so a naive `\\b(?:19|20)\\d{2}\\b` against the raw stem would miss the year;
    `_filename_heuristic` runs the year regex against the normalized title to
    avoid that trap."""
    monkeypatch.setattr(
        PaperPipeline, "_crossref_lookup",
        lambda self, doi, executor: None,
    )
    monkeypatch.setattr(
        PaperPipeline, "_extract_pdf_metadata",
        staticmethod(lambda pdf_path: None),
    )

    meta, source = PaperPipeline()._resolve_metadata(
        AddInputs(pdf="/some/dir/Smith_2019_topic_paper.pdf"), _DummyContext()
    )
    assert source == "filename"
    assert meta["title"] == "Smith 2019 topic paper"
    assert meta["year"] == 2019


def test_explicit_overrides_extracted(monkeypatch):
    monkeypatch.setattr(
        PaperPipeline, "_crossref_lookup",
        lambda self, doi, executor: {
            "title": "FromDOI", "authors": "X", "year": 2020, "doi": "10.1/x",
        },
    )

    meta, source = PaperPipeline()._resolve_metadata(
        AddInputs(doi="10.1/x", title="Override", year=2099), _DummyContext()
    )
    assert source == "doi-crossref"
    assert meta["title"] == "Override"
    assert meta["year"] == 2099

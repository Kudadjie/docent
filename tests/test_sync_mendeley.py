"""Tests for `paper sync-mendeley` (Step 11.4).

Generator action: cross-checks promoted entries against the Mendeley
library via the `mcp` SDK. The wrapper module functions
(`mendeley_lookup_doi`, `mendeley_search_library`) are monkeypatched at
the import site in `docent.tools.paper` — no real subprocess, no real
MCP traffic.
"""
from __future__ import annotations

import inspect
from datetime import datetime
from pathlib import Path

import pytest

from docent.config import load_settings
from docent.core.context import Context
from docent.execution import Executor
from docent.llm import LLMClient
from docent.tools.paper import (
    AddInputs,
    PaperPipeline,
    SyncMendeleyInputs,
)


def _ctx() -> Context:
    settings = load_settings()
    return Context(settings=settings, llm=LLMClient(settings), executor=Executor())


def _drain(maybe_gen):
    if not inspect.isgenerator(maybe_gen):
        return maybe_gen
    try:
        while True:
            next(maybe_gen)
    except StopIteration as e:
        return e.value


def _add_promoted(tool: PaperPipeline, ctx: Context, *, doi: str | None, title: str = "Foo",
                  pdf_name: str = "smith-2024-foo.pdf", tmp_path: Path | None = None) -> str:
    """Add an entry, then mark it promoted (skipping the actual move)."""
    pdf = (tmp_path or Path.cwd()) / pdf_name
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4\n")
    tool.add(AddInputs(pdf=str(pdf), title=title, authors="Smith, J", year=2024, doi=doi), ctx)
    queue = tool._store.load_queue()
    queue[0]["promoted_at"] = datetime.now().isoformat()
    tool._store.save_queue(queue)
    return queue[0]["id"]


def _patch_mcp(monkeypatch, *, doi_resp=None, search_resp=None):
    """Install fake mendeley_lookup_doi / mendeley_search_library on the paper module."""
    calls = {"doi": [], "search": []}

    def fake_doi(doi, launch_command=None):
        calls["doi"].append(doi)
        if doi_resp is None:
            return {"items": [], "error": None}
        return doi_resp(doi) if callable(doi_resp) else doi_resp

    def fake_search(query, launch_command=None, limit=20):
        calls["search"].append((query, limit))
        if search_resp is None:
            return {"items": [], "error": None}
        return search_resp(query) if callable(search_resp) else search_resp

    monkeypatch.setattr("docent.tools.paper.mendeley_lookup_doi", fake_doi)
    monkeypatch.setattr("docent.tools.paper.mendeley_search_library", fake_search)
    return calls


def test_doi_hit_links(tmp_docent_home, tmp_path, monkeypatch):
    tool = PaperPipeline()
    ctx = _ctx()
    eid = _add_promoted(tool, ctx, doi="10.1234/foo", tmp_path=tmp_path)

    _patch_mcp(monkeypatch,
               doi_resp={"items": [{"id": "MENDELEY-ABC", "title": "Foo"}], "error": None})

    result = _drain(tool.sync_mendeley(SyncMendeleyInputs(), ctx))
    assert result.linked == [{"id": eid, "mendeley_id": "MENDELEY-ABC"}]
    assert tool._store.load_queue()[0]["mendeley_id"] == "MENDELEY-ABC"


def test_doi_miss_falls_back_to_title_search(tmp_docent_home, tmp_path, monkeypatch):
    tool = PaperPipeline()
    ctx = _ctx()
    eid = _add_promoted(tool, ctx, doi="10.9999/missing", tmp_path=tmp_path)

    calls = _patch_mcp(monkeypatch,
                       doi_resp={"items": [], "error": None},
                       search_resp={"items": [{"id": "MENDELEY-XYZ", "title": "Foo"}], "error": None})

    result = _drain(tool.sync_mendeley(SyncMendeleyInputs(), ctx))
    assert result.linked == [{"id": eid, "mendeley_id": "MENDELEY-XYZ"}]
    assert calls["search"], "title fallback should have fired"


def test_title_search_ambiguous_does_not_link(tmp_docent_home, tmp_path, monkeypatch):
    tool = PaperPipeline()
    ctx = _ctx()
    eid = _add_promoted(tool, ctx, doi=None, tmp_path=tmp_path)

    _patch_mcp(monkeypatch, search_resp={
        "items": [
            {"id": "M1", "title": "Foo (variant A)", "year": 2024},
            {"id": "M2", "title": "Foo (variant B)", "year": 2023},
        ],
        "error": None,
    })

    result = _drain(tool.sync_mendeley(SyncMendeleyInputs(), ctx))
    assert result.linked == []
    assert len(result.ambiguous) == 1
    assert result.ambiguous[0]["id"] == eid
    assert len(result.ambiguous[0]["candidates"]) == 2
    # Did not persist
    assert tool._store.load_queue()[0].get("mendeley_id") in (None, "")


def test_no_match_buckets_as_not_found(tmp_docent_home, tmp_path, monkeypatch):
    tool = PaperPipeline()
    ctx = _ctx()
    eid = _add_promoted(tool, ctx, doi="10.1234/foo", tmp_path=tmp_path)

    _patch_mcp(monkeypatch, doi_resp={"items": [], "error": None},
               search_resp={"items": [], "error": None})

    result = _drain(tool.sync_mendeley(SyncMendeleyInputs(), ctx))
    assert result.linked == []
    assert len(result.not_found) == 1
    assert result.not_found[0]["id"] == eid


def test_already_linked_skipped(tmp_docent_home, tmp_path, monkeypatch):
    tool = PaperPipeline()
    ctx = _ctx()
    eid = _add_promoted(tool, ctx, doi="10.1234/foo", tmp_path=tmp_path)
    queue = tool._store.load_queue()
    queue[0]["mendeley_id"] = "PRE-LINKED"
    tool._store.save_queue(queue)

    def boom(*a, **kw):
        raise AssertionError("MCP must not be called for already-linked entries")
    monkeypatch.setattr("docent.tools.paper.mendeley_lookup_doi", boom)
    monkeypatch.setattr("docent.tools.paper.mendeley_search_library", boom)

    result = _drain(tool.sync_mendeley(SyncMendeleyInputs(), ctx))
    assert result.already_linked == [eid]
    assert result.linked == []


def test_not_promoted_skipped_in_auto_mode(tmp_docent_home, tmp_path, monkeypatch):
    tool = PaperPipeline()
    ctx = _ctx()
    # Add an entry but DO NOT mark promoted.
    pdf = tmp_path / "smith-2024-foo.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    tool.add(AddInputs(pdf=str(pdf), title="Foo", authors="Smith, J", year=2024, doi="10.1234/foo"), ctx)

    def boom(*a, **kw):
        raise AssertionError("MCP must not be called for non-promoted entries")
    monkeypatch.setattr("docent.tools.paper.mendeley_lookup_doi", boom)
    monkeypatch.setattr("docent.tools.paper.mendeley_search_library", boom)

    result = _drain(tool.sync_mendeley(SyncMendeleyInputs(), ctx))
    assert result.linked == []
    assert len(result.not_eligible) == 1
    assert "not promoted" in result.not_eligible[0]["reason"]


def test_id_override_bypasses_promoted_filter(tmp_docent_home, tmp_path, monkeypatch):
    tool = PaperPipeline()
    ctx = _ctx()
    pdf = tmp_path / "smith-2024-foo.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    tool.add(AddInputs(pdf=str(pdf), title="Foo", authors="Smith, J", year=2024, doi="10.1234/foo"), ctx)
    eid = tool._store.load_queue()[0]["id"]

    _patch_mcp(monkeypatch,
               doi_resp={"items": [{"id": "M-FORCED"}], "error": None})

    result = _drain(tool.sync_mendeley(SyncMendeleyInputs(id=eid), ctx))
    assert result.linked == [{"id": eid, "mendeley_id": "M-FORCED"}]


def test_dry_run_does_not_persist(tmp_docent_home, tmp_path, monkeypatch):
    tool = PaperPipeline()
    ctx = _ctx()
    eid = _add_promoted(tool, ctx, doi="10.1234/foo", tmp_path=tmp_path)

    _patch_mcp(monkeypatch,
               doi_resp={"items": [{"id": "M-DRY"}], "error": None})

    result = _drain(tool.sync_mendeley(SyncMendeleyInputs(dry_run=True), ctx))
    assert result.linked == []
    assert result.dry_run_link == [{"id": eid, "mendeley_id": "M-DRY"}]
    assert tool._store.load_queue()[0].get("mendeley_id") in (None, "")


def test_auth_failure_surfaces_login_hint(tmp_docent_home, tmp_path, monkeypatch):
    tool = PaperPipeline()
    ctx = _ctx()
    eid = _add_promoted(tool, ctx, doi="10.1234/foo", tmp_path=tmp_path)

    _patch_mcp(monkeypatch,
               doi_resp={"items": [], "error": "auth: token expired"})

    result = _drain(tool.sync_mendeley(SyncMendeleyInputs(), ctx))
    assert len(result.failed) == 1
    assert result.failed[0]["id"] == eid
    assert "mendeley-auth login" in result.failed[0]["error"]
    assert "mendeley-auth login" in result.summary


def test_transport_failure_buckets_as_failed(tmp_docent_home, tmp_path, monkeypatch):
    tool = PaperPipeline()
    ctx = _ctx()
    _add_promoted(tool, ctx, doi="10.1234/foo", tmp_path=tmp_path)

    _patch_mcp(monkeypatch,
               doi_resp={"items": [], "error": "transport: launch command not found ([Errno 2])"})

    result = _drain(tool.sync_mendeley(SyncMendeleyInputs(), ctx))
    assert len(result.failed) == 1
    assert "uv tool install mendeley-mcp" in result.failed[0]["error"]


def test_doi_prefix_stripped_before_lookup(tmp_docent_home, tmp_path, monkeypatch):
    """Real-data regression: queue can hold DOIs in URL form
    (`https://doi.org/10.1515/geo-2019-0013`); Mendeley's catalog endpoint
    accepts only the bare `10.xxxx/...` form. The wrapper must normalize.
    """
    from docent.tools.mendeley_client import _normalize_doi
    assert _normalize_doi("https://doi.org/10.1515/geo-2019-0013") == "10.1515/geo-2019-0013"
    assert _normalize_doi("http://doi.org/10.1234/x") == "10.1234/x"
    assert _normalize_doi("doi:10.1234/x") == "10.1234/x"
    assert _normalize_doi("10.1234/x") == "10.1234/x"
    assert _normalize_doi("  https://doi.org/10.1234/x  ") == "10.1234/x"


def test_no_targets_without_id(tmp_docent_home, tmp_path, monkeypatch):
    tool = PaperPipeline()
    ctx = _ctx()
    _patch_mcp(monkeypatch)
    result = _drain(tool.sync_mendeley(SyncMendeleyInputs(id="nope-2024-x"), ctx))
    assert "No entry with id" in result.message

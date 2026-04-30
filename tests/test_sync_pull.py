"""Tests for `paper sync-pull` (Step 11.2).

Generator action: tries Unpaywall (and CrossRef title fallback) for queue
entries missing a PDF. Network calls go through `Context.executor`, so we
inject a fake executor here — no real curl, no real Unpaywall.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docent.config import load_settings
from docent.core.context import Context
from docent.execution.executor import ProcessResult
from docent.llm import LLMClient
from docent.tools.paper import (
    AddInputs,
    PaperPipeline,
    SyncPullInputs,
)


@dataclass
class FakeExecutor:
    """Pattern-matches curl args and returns canned ProcessResult.

    Each handler is a callable `(args: list[str]) -> ProcessResult | None`;
    returning None means "not my command, try next." First match wins.
    """

    handlers: list[Any]

    def run(self, args, *, timeout=None, cwd=None, env=None, check=True):
        for h in self.handlers:
            r = h(args)
            if r is not None:
                if check and r.returncode != 0:
                    raise RuntimeError(f"fake exec failed: {args}")
                return r
        return ProcessResult(args=list(args), returncode=1, stdout="", stderr="no handler", duration=0.0)


def _ok(args, body: str, status: int = 200) -> ProcessResult:
    """Mimic curl -w "\\n__HTTP_STATUS__%{http_code}" output."""
    if "-w" in args:
        stdout = body + f"\n__HTTP_STATUS__{status}"
    else:
        stdout = body
    return ProcessResult(args=list(args), returncode=0, stdout=stdout, stderr="", duration=0.0)


def _ctx(database_dir: Path | None = None, email: str | None = "test@example.com",
         executor: Any | None = None) -> Context:
    settings = load_settings()
    if database_dir is not None:
        settings.paper.database_dir = database_dir
    settings.paper.unpaywall_email = email
    return Context(settings=settings, llm=LLMClient(settings), executor=executor or FakeExecutor(handlers=[]))


def _drain(maybe_gen):
    """Run a generator-or-result through to completion. Returns final value."""
    import inspect
    if not inspect.isgenerator(maybe_gen):
        return maybe_gen
    try:
        while True:
            next(maybe_gen)
    except StopIteration as e:
        return e.value


def test_missing_email_returns_message(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    ctx = _ctx(database_dir=db, email=None)
    result = _drain(PaperPipeline().sync_pull(SyncPullInputs(), ctx))
    assert result.message and "unpaywall_email" in result.message
    assert result.downloaded == []


def test_already_has_file(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = db / "smith-2024-x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db)
    tool.add(AddInputs(title="X", authors="Smith, J", year=2024, pdf=str(pdf)), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(), ctx))
    # No targets had missing files, so already_has_file is empty here too
    # (the bucket only fires when a specific id is requested, since auto-mode
    # filters out present-file entries upfront). Smoke-test: nothing was tried.
    assert result.downloaded == []
    assert result.no_oa == []
    assert result.network_error == []


def test_already_has_file_when_id_targeted(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()
    pdf = db / "smith-2024-x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    tool = PaperPipeline()
    ctx = _ctx(database_dir=db)
    tool.add(AddInputs(title="X", authors="Smith, J", year=2024, pdf=str(pdf)), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(id="smith-2024-x"), ctx))
    assert result.already_has_file == ["smith-2024-x"]


def test_happy_doi_path_downloads_and_updates_entry(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()

    def unpaywall(args):
        if any("api.unpaywall.org" in a for a in args):
            return _ok(args, json.dumps({
                "is_oa": True,
                "doi_url": "https://doi.org/10.1234/foo",
                "journal_name": "Open J",
                "best_oa_location": {"url_for_pdf": "https://example.org/foo.pdf"},
            }))
        return None

    def download(args):
        if "-o" in args:
            dest = args[args.index("-o") + 1]
            Path(dest).write_bytes(b"%PDF-1.4\nfake-downloaded\n")
            return ProcessResult(args=list(args), returncode=0, stdout="", stderr="", duration=0.1)
        return None

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[unpaywall, download]))
    tool = PaperPipeline()
    # Add a metadata-only entry (no pdf, has DOI).
    tool.add(AddInputs(title="Foo", authors="Smith, J", year=2024, doi="10.1234/foo"), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(), ctx))
    assert len(result.downloaded) == 1
    assert result.downloaded[0]["id"].startswith("smith-2024")
    assert Path(result.downloaded[0]["path"]).exists()

    # Persistence: queue entry now has pdf_path + file_status="found".
    queue = tool._store.load_queue()
    assert queue[0]["pdf_path"] == result.downloaded[0]["path"]
    assert queue[0]["file_status"] == "found"


def test_no_oa_surfaces_doi_url_for_institutional_access(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()

    def unpaywall(args):
        if any("api.unpaywall.org" in a for a in args):
            return _ok(args, json.dumps({
                "is_oa": False,
                "doi_url": "https://doi.org/10.1038/closed",
                "journal_name": "Nature Closed",
                "best_oa_location": None,
            }))
        return None

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[unpaywall]))
    tool = PaperPipeline()
    tool.add(AddInputs(title="Closed", authors="Smith, J", year=2024, doi="10.1038/closed"), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(), ctx))
    assert result.downloaded == []
    assert len(result.no_oa) == 1
    assert result.no_oa[0]["doi_url"] == "https://doi.org/10.1038/closed"
    assert result.no_oa[0]["journal"] == "Nature Closed"


def test_doi_not_in_unpaywall_buckets_as_not_found(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()

    def unpaywall(args):
        if any("api.unpaywall.org" in a for a in args):
            return _ok(args, "{}", status=404)
        return None

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[unpaywall]))
    tool = PaperPipeline()
    tool.add(AddInputs(title="Ghost", authors="Smith, J", year=2024, doi="10.9999/nope"), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(), ctx))
    assert result.network_error == []
    assert len(result.not_found) == 1
    assert "Unpaywall" in result.not_found[0]["reason"]


def test_network_error_buckets_correctly(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()

    def fail(args):
        return ProcessResult(args=list(args), returncode=6, stdout="", stderr="curl: (6) Could not resolve host", duration=0.0)

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[fail]))
    tool = PaperPipeline()
    tool.add(AddInputs(title="X", authors="Smith, J", year=2024, doi="10.1234/x"), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(), ctx))
    assert len(result.network_error) == 1
    assert result.downloaded == []


def test_title_fallback_resolves_doi_then_pulls(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()

    def crossref(args):
        if any("api.crossref.org/works?" in a for a in args):
            return _ok(args, json.dumps({
                "message": {"items": [
                    {"DOI": "10.1234/resolved", "title": ["Resolved Topic"]}
                ]}
            }))
        return None

    def unpaywall(args):
        if any("api.unpaywall.org" in a for a in args):
            assert "10.1234/resolved" in args[-1]
            return _ok(args, json.dumps({
                "is_oa": True,
                "doi_url": "https://doi.org/10.1234/resolved",
                "journal_name": "OA J",
                "best_oa_location": {"url_for_pdf": "https://example.org/r.pdf"},
            }))
        return None

    def download(args):
        if "-o" in args:
            Path(args[args.index("-o") + 1]).write_bytes(b"%PDF-1.4\n")
            return ProcessResult(args=list(args), returncode=0, stdout="", stderr="", duration=0.0)
        return None

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[crossref, unpaywall, download]))
    tool = PaperPipeline()
    tool.add(AddInputs(title="Resolved Topic", authors="Doe, A", year=2023), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(), ctx))
    assert len(result.downloaded) == 1
    queue = tool._store.load_queue()
    assert queue[0]["doi"] == "10.1234/resolved"


def test_filename_stub_with_no_doi_fails_fast(tmp_docent_home, tmp_path):
    """Bug 1: identifier-free entries (no DOI, title from filename) must not
    trigger CrossRef title search — that's what fetched the wrong Arabic paper
    in real-data testing."""
    db = tmp_path / "Papers"
    db.mkdir()

    crossref_called = {"flag": False}

    def crossref(args):
        if any("api.crossref.org" in a for a in args):
            crossref_called["flag"] = True
            return _ok(args, json.dumps({"message": {"items": []}}))
        return None

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[crossref]))
    tool = PaperPipeline()
    tool._store.save_queue([{
        "id": "unknown-nd-01",
        "title": "some_random_filename_stub",
        "authors": "Unknown",
        "year": None,
        "doi": None,
        "added": "2026-04-30",
        "status": "queued",
        "priority": "medium",
        "tags": [],
        "notes": "",
        "file_status": "missing",
        "keep_in_mendeley": False,
        "pdf_path": None,
        "title_is_filename_stub": True,
    }])

    result = _drain(tool.sync_pull(SyncPullInputs(id="unknown-nd-01"), ctx))
    assert crossref_called["flag"] is False, "CrossRef must not be called for filename-stub entries"
    assert len(result.not_found) == 1
    assert "insufficient-identifiers" in result.not_found[0]["reason"]


def test_crossref_title_search_rejects_unrelated_match(tmp_docent_home, tmp_path):
    """Bug 1: even when a title is provided, CrossRef's top hit must be
    rejected if it has nothing to do with the query (the fuzzy guard)."""
    db = tmp_path / "Papers"
    db.mkdir()

    def crossref(args):
        if any("api.crossref.org/works?" in a for a in args):
            return _ok(args, json.dumps({
                "message": {"items": [
                    {"DOI": "10.9999/garbage", "title": ["Quantum Field Theory in Curved Spacetime"]}
                ]}
            }))
        return None

    def unpaywall(args):
        if any("api.unpaywall.org" in a for a in args):
            raise AssertionError("Unpaywall must not be called when CrossRef returned a non-matching title")
        return None

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[crossref, unpaywall]))
    tool = PaperPipeline()
    tool.add(AddInputs(title="Vehicle Dynamics Control Survey", authors="Doe, J", year=2021), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(), ctx))
    assert result.downloaded == []
    assert len(result.not_found) == 1
    assert "no confident match" in result.not_found[0]["reason"]


def test_crossref_title_search_accepts_close_match(tmp_docent_home, tmp_path):
    """Bug 1 regression guard: subtitle additions must still pass the fuzzy gate."""
    db = tmp_path / "Papers"
    db.mkdir()

    def crossref(args):
        if any("api.crossref.org/works?" in a for a in args):
            return _ok(args, json.dumps({
                "message": {"items": [
                    {"DOI": "10.1234/match", "title": ["Transformers for Computer Vision: A Comprehensive Survey"]}
                ]}
            }))
        return None

    def unpaywall(args):
        if any("api.unpaywall.org" in a for a in args):
            return _ok(args, json.dumps({
                "is_oa": True,
                "doi_url": "https://doi.org/10.1234/match",
                "journal_name": "OA",
                "best_oa_location": {"url_for_pdf": "https://example.org/m.pdf"},
            }))
        return None

    def download(args):
        if "-o" in args:
            Path(args[args.index("-o") + 1]).write_bytes(b"%PDF-1.4\n")
            return ProcessResult(args=list(args), returncode=0, stdout="application/pdf", stderr="", duration=0.0)
        return None

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[crossref, unpaywall, download]))
    tool = PaperPipeline()
    tool.add(AddInputs(title="Transformers for Computer Vision", authors="Doe, J", year=2023), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(), ctx))
    assert len(result.downloaded) == 1


def test_no_oa_summary_includes_institutional_hint(tmp_docent_home, tmp_path):
    """Bug 2: closed-access summary should suggest institutional access."""
    db = tmp_path / "Papers"
    db.mkdir()

    def unpaywall(args):
        if any("api.unpaywall.org" in a for a in args):
            return _ok(args, json.dumps({
                "is_oa": False,
                "doi_url": "https://doi.org/10.1038/closed",
                "journal_name": "Nature",
                "best_oa_location": None,
            }))
        return None

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[unpaywall]))
    tool = PaperPipeline()
    tool.add(AddInputs(title="Closed", authors="X, Y", year=2024, doi="10.1038/closed"), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(), ctx))
    assert "institutional access" in result.summary.lower()


def test_download_rejects_html_landing_page(tmp_docent_home, tmp_path):
    """Bug 3: Unpaywall pdf_url returning HTML must be discarded, not persisted as a 1KB '.pdf'."""
    db = tmp_path / "Papers"
    db.mkdir()

    def unpaywall(args):
        if any("api.unpaywall.org" in a for a in args):
            return _ok(args, json.dumps({
                "is_oa": True,
                "doi_url": "https://doi.org/10.3390/vehicles3040047",
                "journal_name": "Vehicles",
                "best_oa_location": {"url_for_pdf": "https://example.org/landing"},
            }))
        return None

    def download(args):
        if "-o" in args:
            Path(args[args.index("-o") + 1]).write_bytes(b"<!DOCTYPE html><html>\n")
            return ProcessResult(args=list(args), returncode=0, stdout="text/html; charset=utf-8", stderr="", duration=0.0)
        return None

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[unpaywall, download]))
    tool = PaperPipeline()
    tool.add(AddInputs(title="Vehicles", authors="X, Y", year=2021, doi="10.3390/vehicles3040047"), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(), ctx))
    assert result.downloaded == []
    assert len(result.network_error) == 1
    # Discarded file must not linger on disk.
    expected = next((p for p in db.iterdir() if p.suffix == ".pdf"), None)
    assert expected is None


def test_download_rejects_pdf_magic_mismatch(tmp_docent_home, tmp_path):
    """Bug 3: Content-Type can be missing/wrong — magic-byte check must still catch non-PDFs."""
    db = tmp_path / "Papers"
    db.mkdir()

    def unpaywall(args):
        if any("api.unpaywall.org" in a for a in args):
            return _ok(args, json.dumps({
                "is_oa": True,
                "doi_url": "https://doi.org/10.1234/x",
                "journal_name": "OA",
                "best_oa_location": {"url_for_pdf": "https://example.org/x.pdf"},
            }))
        return None

    def download(args):
        if "-o" in args:
            # Server omits Content-Type but sends garbage bytes.
            Path(args[args.index("-o") + 1]).write_bytes(b"NOPDF garbage stream")
            return ProcessResult(args=list(args), returncode=0, stdout="", stderr="", duration=0.0)
        return None

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[unpaywall, download]))
    tool = PaperPipeline()
    tool.add(AddInputs(title="X", authors="X, Y", year=2024, doi="10.1234/x"), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(), ctx))
    assert result.downloaded == []
    assert len(result.network_error) == 1


def test_dry_run_resolves_oa_but_does_not_download(tmp_docent_home, tmp_path):
    db = tmp_path / "Papers"
    db.mkdir()

    def unpaywall(args):
        if any("api.unpaywall.org" in a for a in args):
            return _ok(args, json.dumps({
                "is_oa": True,
                "doi_url": "https://doi.org/10.1234/foo",
                "journal_name": "OA",
                "best_oa_location": {"url_for_pdf": "https://example.org/x.pdf"},
            }))
        return None

    def download(args):
        # Should NOT be called in dry-run; raise to make it loud if it is.
        if "-o" in args:
            raise AssertionError("download invoked during dry-run")
        return None

    ctx = _ctx(database_dir=db, executor=FakeExecutor(handlers=[unpaywall, download]))
    tool = PaperPipeline()
    tool.add(AddInputs(title="X", authors="Smith, J", year=2024, doi="10.1234/foo"), ctx)

    result = _drain(tool.sync_pull(SyncPullInputs(dry_run=True), ctx))
    assert result.downloaded == []
    assert len(result.dry_run_oa) == 1
    assert result.dry_run_oa[0]["pdf_url"] == "https://example.org/x.pdf"
    queue = tool._store.load_queue()
    assert queue[0].get("pdf_path") in (None, "")

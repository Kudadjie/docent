"""Sync helpers for paper pipeline — Unpaywall lookup + PDF download.

Extracted from `paper.py` at the Step 11.3 carve-out. Step 11.3's `sync-promote`
helpers (DB -> Mendeley Watch copy-and-stop) will land here too.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def unpaywall_lookup(doi: str, email: str, executor: Any) -> dict[str, Any] | None:
    """Shell out to curl for Unpaywall. Returns a dict on success, None on transport failure.

    Success dict keys: `is_oa: bool`, `pdf_url: str | None`, `doi_url: str`,
    `journal: str | None`. A 404 (DOI not indexed) returns
    `{"status": "not_found"}` rather than None — we want to bucket it as
    not-found, not as a network error.
    """
    clean = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if clean.lower().startswith(prefix):
            clean = clean[len(prefix):]
            break
    url = f"https://api.unpaywall.org/v2/{clean}?email={email}"
    try:
        result = executor.run(
            ["curl", "-sS", "--max-time", "15",
             "-w", "\n__HTTP_STATUS__%{http_code}",
             "-H", "User-Agent: docent/0.1.0",
             url],
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    body, _, status_line = result.stdout.rpartition("\n__HTTP_STATUS__")
    try:
        status_code = int(status_line.strip())
    except ValueError:
        status_code = 0
    if status_code == 404:
        return {"status": "not_found"}
    if status_code != 200:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    best = data.get("best_oa_location") or {}
    journal = data.get("journal_name")
    return {
        "is_oa": bool(data.get("is_oa")),
        "pdf_url": best.get("url_for_pdf"),
        "doi_url": data.get("doi_url") or f"https://doi.org/{clean}",
        "journal": journal,
    }


def download_pdf(url: str, dest: Path, executor: Any) -> bool:
    """Download `url` to `dest`. Returns True iff curl succeeded AND the
    response is actually a PDF.

    Real-data test (10.3390/vehicles3040047) showed Unpaywall pdf_urls can
    redirect to HTML landing pages; without validation we'd silently write
    a 1KB HTML file with `.pdf` extension. We check both Content-Type
    (returned via curl `-w %{content_type}`) and the `%PDF-` magic bytes;
    either failing discards the file.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = executor.run(
            ["curl", "-sSL", "--max-time", "60",
             "-H", "User-Agent: docent/0.1.0",
             "-w", "%{content_type}",
             "-o", str(dest),
             url],
            check=False,
        )
    except Exception:
        return False

    def _discard() -> bool:
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        return False

    if result.returncode != 0:
        return _discard()
    if not dest.exists() or dest.stat().st_size == 0:
        return _discard()

    content_type = (result.stdout or "").strip().lower()
    if content_type and "pdf" not in content_type:
        return _discard()

    try:
        with dest.open("rb") as f:
            head = f.read(5)
    except OSError:
        return _discard()
    if head != b"%PDF-":
        return _discard()
    return True

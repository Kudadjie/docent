"""Metadata resolution for `paper add` — DOI → CrossRef → PDF info → filename.

Extracted from `paper.py` at the Step 11.3 carve-out. Pure functions of
(inputs, executor) — no PaperPipeline state. All helpers swallow exceptions and
return None on failure so the chain falls through cleanly.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from docent.tools.paper import AddInputs


def resolve_metadata(inputs: "AddInputs", executor: Any) -> tuple[dict[str, Any], str]:
    """Run fallback chain. Returns (metadata-dict, source-tag).

    Chain (Step 11.5):
        explicit-doi → CrossRef           (`doi-crossref`)
        PDF DOI (scans up to 20 pages)    → CrossRef (`pdf-doi-crossref`)
        PDF title → CrossRef title-search → fuzzy-guarded (`pdf-title-crossref`)
        PDF title (raw, no CrossRef hit)  (`pdf-metadata`)
        filename heuristic                (`filename`)

    Explicit fields on `inputs` (title/authors/year/doi) are folded in last and
    always win over extracted values.
    """
    extracted: dict[str, Any] = {}
    source = "none"

    if inputs.doi:
        cr = crossref_lookup(inputs.doi, executor)
        if cr:
            extracted = cr
            source = "doi-crossref"

    if not extracted and inputs.pdf:
        pdf_meta = extract_pdf_metadata(inputs.pdf)
        if pdf_meta and pdf_meta.get("doi"):
            cr = crossref_lookup(pdf_meta["doi"], executor)
            if cr:
                extracted = cr
                source = "pdf-doi-crossref"
        if not extracted and pdf_meta and pdf_meta.get("title"):
            cr2 = crossref_title_search(pdf_meta["title"], executor)
            if cr2:
                extracted = cr2
                source = "pdf-title-crossref"
        if not extracted and pdf_meta and pdf_meta.get("title"):
            extracted = {k: v for k, v in pdf_meta.items() if k != "doi"}
            if pdf_meta.get("doi"):
                extracted["doi"] = pdf_meta["doi"]
            source = "pdf-metadata"
        if not extracted.get("title"):
            fallback = filename_heuristic(inputs.pdf)
            extracted = {**fallback, **extracted}
            source = "filename"

    explicit: dict[str, Any] = {}
    if inputs.title:
        explicit["title"] = inputs.title
    if inputs.authors:
        explicit["authors"] = inputs.authors
    if inputs.year is not None:
        explicit["year"] = inputs.year
    if inputs.doi:
        explicit["doi"] = inputs.doi

    merged = {**extracted, **explicit}
    if source == "none" and explicit:
        source = "explicit"
    return merged, source


def crossref_lookup(doi: str, executor: Any) -> dict[str, Any] | None:
    """Shell out to curl for CrossRef. Returns {title, authors, year, doi} or None."""
    clean = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if clean.lower().startswith(prefix):
            clean = clean[len(prefix):]
            break
    url = f"https://api.crossref.org/works/{clean}"
    try:
        result = executor.run(
            ["curl", "-sS", "--max-time", "10",
             "-H", "User-Agent: docent/0.1.0",
             url],
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    msg = data.get("message")
    if not isinstance(msg, dict):
        return None
    title_list = msg.get("title") or []
    title = title_list[0].strip() if title_list else None
    if not title:
        return None
    authors_list = msg.get("author") or []
    authors_str = ", ".join(
        " ".join(filter(None, [a.get("family"), a.get("given")])) for a in authors_list
    ) or "Unknown"
    year = None
    issued = (msg.get("issued") or {}).get("date-parts") or []
    if issued and isinstance(issued[0], list) and issued[0]:
        try:
            year = int(issued[0][0])
        except (TypeError, ValueError):
            pass
    return {"title": title, "authors": authors_str, "year": year, "doi": clean}


PDF_DOI_PAGE_CAP = 20


def extract_pdf_metadata(pdf_path: str) -> dict[str, Any] | None:
    """Read PDF info dict + scan up to 20 pages for a DOI. Returns dict or None.

    Step 11.5: page cap bumped 5 → 20 (many journals only print the DOI in the
    last-page footer). When the info dict lacks `/Title`, fall back to a
    largest-font-size heuristic on page 1.
    """
    p = Path(pdf_path)
    if not p.is_file():
        return None
    try:
        from pypdf import PdfReader  # lazy import; keeps pypdf out of import-time cost
        reader = PdfReader(str(p))
    except Exception:
        return None
    out: dict[str, Any] = {}
    info = getattr(reader, "metadata", None)
    if info is not None:
        try:
            title = info.get("/Title")
            author = info.get("/Author")
        except Exception:
            title = author = None
        if title:
            out["title"] = str(title).strip()
        if author:
            out["authors"] = str(author).strip()
    if not out.get("title"):
        font_title = _extract_title_by_font_size(reader)
        if font_title:
            out["title"] = font_title
    doi_re = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)
    try:
        pages = reader.pages[:PDF_DOI_PAGE_CAP]
    except Exception:
        pages = []
    for page in pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        m = doi_re.search(text)
        if m:
            out["doi"] = m.group(0).rstrip(".,;)")
            break
    return out or None


def _extract_title_by_font_size(reader: Any) -> str | None:
    """Largest-font-size text run on page 1, joined and whitespace-collapsed.

    Used only when the PDF info dict has no `/Title`. pypdf's `visitor_text`
    callback exposes font_size per text run; we group runs by size and pick
    the largest size with at least 10 chars of text.
    """
    try:
        page = reader.pages[0]
    except Exception:
        return None
    runs: list[tuple[float, str]] = []

    def visitor(text, cm, tm, font_dict, font_size):  # noqa: ARG001
        try:
            size = float(font_size) if font_size is not None else 0.0
        except (TypeError, ValueError):
            size = 0.0
        if text and text.strip():
            runs.append((size, text))

    try:
        page.extract_text(visitor_text=visitor)
    except Exception:
        return None
    if not runs:
        return None
    by_size: dict[float, list[str]] = {}
    for size, text in runs:
        by_size.setdefault(size, []).append(text)
    for size in sorted(by_size.keys(), reverse=True):
        if size <= 0:
            continue
        joined = re.sub(r"\s+", " ", "".join(by_size[size])).strip()
        low = joined.lower()
        if len(joined) >= 10 and not low.startswith(("doi", "http", "www", "©")):
            return joined
    return None


def crossref_title_search(
    title: str, executor: Any, threshold: float = 0.92
) -> dict[str, Any] | None:
    """CrossRef bibliographic title search with strict fuzzy guard.

    Returns a metadata dict only when the best of the top-5 candidates' titles
    fuzzy-matches `title` at SequenceMatcher ratio >= `threshold`. The 11.2
    sync-pull batch removed an unguarded version of this helper after CrossRef
    returned wrong papers on real data; the threshold here is deliberately
    strict (near-exact match required, tolerates only subtitle/punctuation
    drift).
    """
    if not title or not title.strip():
        return None
    q = urllib.parse.quote_plus(title.strip())
    url = f"https://api.crossref.org/works?query.bibliographic={q}&rows=5"
    try:
        result = executor.run(
            ["curl", "-sS", "--max-time", "10",
             "-H", "User-Agent: docent/0.1.0",
             url],
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    items = (data.get("message") or {}).get("items") or []
    norm_target = _normalize_for_match(title)
    best: tuple[float, dict[str, Any]] | None = None
    for it in items:
        cand_titles = it.get("title") or []
        if not cand_titles:
            continue
        ratio = SequenceMatcher(None, norm_target, _normalize_for_match(cand_titles[0])).ratio()
        if best is None or ratio > best[0]:
            best = (ratio, it)
    if best is None or best[0] < threshold:
        return None
    msg = best[1]
    cand_title = (msg.get("title") or [None])[0]
    if not cand_title:
        return None
    authors_list = msg.get("author") or []
    authors_str = ", ".join(
        " ".join(filter(None, [a.get("family"), a.get("given")])) for a in authors_list
    ) or "Unknown"
    year = None
    issued = (msg.get("issued") or {}).get("date-parts") or []
    if issued and isinstance(issued[0], list) and issued[0]:
        try:
            year = int(issued[0][0])
        except (TypeError, ValueError):
            pass
    return {
        "title": cand_title.strip(),
        "authors": authors_str,
        "year": year,
        "doi": msg.get("DOI"),
    }


def _normalize_for_match(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


def filename_heuristic(pdf_path: str) -> dict[str, Any]:
    """Last-resort: title from filename stem, year from any 4-digit number.

    Year regex runs against the *normalized* title (underscores/hyphens
    collapsed to spaces) so Mendeley-style `Smith_2019_topic.pdf` resolves
    to year=2019 — `_` is a Python word char and would otherwise defeat `\\b`.
    """
    stem = Path(pdf_path).stem
    title = re.sub(r"[_\-]+", " ", stem).strip()
    year_match = re.search(r"\b(?:19|20)\d{2}\b", title)
    year = int(year_match.group(0)) if year_match else None
    return {"title": title or "Untitled", "authors": "Unknown", "year": year}

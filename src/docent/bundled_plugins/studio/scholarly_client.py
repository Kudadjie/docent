"""Google Scholar → Semantic Scholar → CrossRef search fallback chain.

Backends are tried in order; the first one that returns results wins.
``scholarly`` (Google Scholar) is the primary but rate-limits frequently,
so callers should not be surprised when Semantic Scholar or CrossRef answers.
"""
from __future__ import annotations

from typing import Any

import httpx

# Shared paper dict shape returned by all three backends:
#   title, authors (list[str], max 5), year (str), doi (str),
#   url (str), abstract (str), source (str)


def search_scholarly(
    query: str,
    max_results: int = 10,
    *,
    semantic_scholar_api_key: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Search academic papers. Returns (papers, backend_used).

    Tries Google Scholar first, then Semantic Scholar, then CrossRef.
    Raises RuntimeError only when all three backends fail.
    """
    try:
        papers = _search_google_scholar(query, max_results)
        if papers:
            return papers, "google_scholar"
    except Exception:
        pass

    try:
        papers = _search_semantic_scholar(
            query, max_results, api_key=semantic_scholar_api_key
        )
        if papers:
            return papers, "semantic_scholar"
    except Exception:
        pass

    try:
        papers = _search_crossref(query, max_results)
        if papers:
            return papers, "crossref"
    except Exception:
        pass

    raise RuntimeError(
        f"All search backends (Google Scholar, Semantic Scholar, CrossRef) "
        f"failed for query: {query!r}"
    )


# ── Google Scholar ────────────────────────────────────────────────────────────

def _search_google_scholar(query: str, max_results: int) -> list[dict[str, Any]]:
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=SyntaxWarning, module="scholarly")
        from scholarly import scholarly  # lazy: ~200 ms import, only when needed
    scholarly.set_timeout(5)
    gen = scholarly.search_pubs(query)
    results: list[dict[str, Any]] = []
    for _ in range(max_results):
        try:
            pub = next(gen)
        except StopIteration:
            break
        bib = pub.get("bib", {})
        authors_raw = bib.get("author", [])
        if isinstance(authors_raw, str):
            authors = [a.strip() for a in authors_raw.split(" and ")]
        elif isinstance(authors_raw, list):
            authors = [str(a) for a in authors_raw]
        else:
            authors = []
        url = pub.get("pub_url") or pub.get("eprint_url") or ""
        results.append({
            "title": bib.get("title", ""),
            "authors": authors[:5],
            "year": str(bib.get("pub_year", "")),
            "doi": "",
            "url": url,
            "abstract": bib.get("abstract", ""),
            "source": "google_scholar",
        })
    return results


# ── Semantic Scholar ──────────────────────────────────────────────────────────

def _search_semantic_scholar(
    query: str,
    max_results: int,
    *,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key
    r = httpx.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={
            "query": query,
            "fields": "title,authors,year,externalIds,abstract,url",
            "limit": max_results,
        },
        headers=headers,
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    results: list[dict[str, Any]] = []
    for p in data.get("data", []):
        doi = (p.get("externalIds") or {}).get("DOI", "")
        authors = [a["name"] for a in (p.get("authors") or [])[:5]]
        url = p.get("url") or (f"https://doi.org/{doi}" if doi else "")
        results.append({
            "title": p.get("title", ""),
            "authors": authors,
            "year": str(p.get("year", "")),
            "doi": doi,
            "url": url,
            "abstract": (p.get("abstract") or ""),
            "source": "semantic_scholar",
        })
    return results


# ── CrossRef ─────────────────────────────────────────────────────────────────

def _search_crossref(query: str, max_results: int) -> list[dict[str, Any]]:
    r = httpx.get(
        "https://api.crossref.org/works",
        params={
            "query": query,
            "rows": max_results,
            "select": "title,author,published,DOI,abstract,URL",
        },
        headers={"User-Agent": "Docent-CLI/1 (mailto:docent-bot@example.com)"},
        timeout=15,
    )
    r.raise_for_status()
    items = r.json().get("message", {}).get("items", [])
    results: list[dict[str, Any]] = []
    for item in items:
        title = (item.get("title") or [""])[0]
        authors = [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in (item.get("author") or [])[:5]
        ]
        date_parts = (
            (item.get("published") or {})
            .get("date-parts", [[None]])[0]
        )
        year = str(date_parts[0]) if date_parts and date_parts[0] else ""
        doi = item.get("DOI", "")
        url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
        results.append({
            "title": title,
            "authors": authors,
            "year": year,
            "doi": doi,
            "url": url,
            "abstract": (item.get("abstract") or ""),
            "source": "crossref",
        })
    return results

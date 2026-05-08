"""Web search, academic paper search, and page fetching for the research pipeline."""
from __future__ import annotations

import re

import httpx
from duckduckgo_search import DDGS

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_S2_FIELDS = "title,abstract,authors,year,externalIds"


def web_search(query: str, max_results: int = 8) -> list[dict]:
    """Search the web via DuckDuckGo. Returns list of {title, url, snippet}."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
    except Exception:
        return []


def paper_search(query: str, max_results: int = 5) -> list[dict]:
    """Search Semantic Scholar for academic papers.

    Returns list of {title, url, snippet, authors, year}.
    """
    try:
        resp = httpx.get(
            f"{_S2_BASE}/paper/search",
            params={"query": query, "fields": _S2_FIELDS, "limit": max_results},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results: list[dict] = []
        for p in data.get("data", []):
            authors = ", ".join(
                a.get("name", "") for a in (p.get("authors") or [])[:3]
            )
            arxiv_id = (p.get("externalIds") or {}).get("ArXiv")
            url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
            results.append(
                {
                    "title": p.get("title") or "",
                    "url": url,
                    "snippet": (p.get("abstract") or "")[:500],
                    "authors": authors,
                    "year": p.get("year"),
                }
            )
        return results
    except Exception:
        return []


def fetch_page(url: str, max_chars: int = 3000) -> str:
    """Fetch a URL, strip HTML tags, return first *max_chars* chars of text."""
    if not url:
        return ""
    try:
        resp = httpx.get(
            url,
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Docent/1.0"},
        )
        resp.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return ""
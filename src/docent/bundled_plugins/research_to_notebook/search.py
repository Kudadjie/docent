"""Web search, academic paper search, and page fetching for the research pipeline."""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

import httpx

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_S2_FIELDS = "title,abstract,authors,year,externalIds"


def _tavily_spend_file() -> Path:
    from docent.utils.paths import cache_dir
    return cache_dir() / "research" / "tavily_spend.json"


def _read_tavily_daily_requests() -> int:
    today = datetime.date.today().isoformat()
    try:
        data = json.loads(_tavily_spend_file().read_text(encoding="utf-8"))
        if data.get("date") == today:
            return int(data.get("requests", 0))
    except Exception:
        pass
    return 0


def _write_tavily_daily_requests(count: int) -> None:
    today = datetime.date.today().isoformat()
    _tavily_spend_file().parent.mkdir(parents=True, exist_ok=True)
    _tavily_spend_file().write_text(
        json.dumps({"date": today, "requests": count}, indent=2),
        encoding="utf-8",
    )


def web_search(query: str, max_results: int = 8, api_key: str | None = None) -> list[dict]:
    """Search the web via Tavily. Returns list of {title, url, snippet}.

    Requires a Tavily API key (free tier: 1,000 calls/month).
    Set via config: docent research config-set tavily_api_key <key>
    Or env: DOCENT_RESEARCH__TAVILY_API_KEY
    """
    if not api_key:
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=max_results)
        # Increment daily request counter
        try:
            current = _read_tavily_daily_requests()
            _write_tavily_daily_requests(current + 1)
        except Exception:
            pass
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in response.get("results", [])
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

"""Sync facades over the async alphaxiv-py SDK.

Each public function runs a self-contained asyncio event loop so callers
(Typer CLI, MCP handler, tests) don't need to manage async state.

When no alphaXiv API key is configured, ``search_papers`` falls back to the
free arXiv API (no key required).  The alphaxiv path adds GitHub links, topic
tags, and AI overviews — the arXiv fallback returns the same dict shape with
those fields set to None/[].
"""

from __future__ import annotations

import asyncio
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from alphaxiv import AlphaXivClient


class AlphaXivAuthError(RuntimeError):
    """Raised when no alphaXiv API key is configured or the key is invalid."""


def _build_client(api_key: str | None) -> AlphaXivClient:
    """Return an AlphaXivClient, trying docent config key then saved env/file key."""
    if api_key:
        return AlphaXivClient.from_api_key(api_key)
    try:
        return AlphaXivClient.from_saved_api_key()
    except (ValueError, Exception):
        raise AlphaXivAuthError(
            "No alphaXiv API key configured.\n"
            "Get a free key at https://alphaxiv.org/settings and set it with:\n"
            "  docent studio config-set --key alphaxiv_api_key --value <key>\n"
            "Or set the ALPHAXIV_API_KEY environment variable."
        )


# ── arXiv free-API fallback ───────────────────────────────────────────────────

_ARXIV_API = "https://export.arxiv.org/api/query"
_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"


def _search_arxiv(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Query the free arXiv API and return results in the same dict shape as alphaXiv."""
    params = urllib.parse.urlencode(
        {
            "search_query": f"all:{query}",
            "max_results": max_results,
            "sortBy": "relevance",
        }
    )
    url = f"{_ARXIV_API}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"arXiv API unreachable: {e}") from e

    root = ET.fromstring(raw)
    results: list[dict[str, Any]] = []
    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        # entry bound as a default arg so the closure captures the current
        # iteration's element, not the loop variable's final value (B023).
        def _text(tag: str, ns: str = _ATOM_NS, entry: Any = entry) -> str:
            el = entry.find(f"{{{ns}}}{tag}")
            return el.text.strip() if el is not None and el.text else ""

        arxiv_id_url = _text("id")
        # ID looks like https://arxiv.org/abs/2301.12345v2 — extract just the ID
        arxiv_id = arxiv_id_url.rsplit("/", 1)[-1].split("v")[0] if arxiv_id_url else ""

        authors = [
            a.find(f"{{{_ATOM_NS}}}name").text.strip()
            for a in entry.findall(f"{{{_ATOM_NS}}}author")
            if a.find(f"{{{_ATOM_NS}}}name") is not None
        ]

        published = _text("published")[:10]  # YYYY-MM-DD
        abstract = _text("summary").replace("\n", " ")[:400]

        results.append(
            {
                "arxiv_id": arxiv_id,
                "title": _text("title").replace("\n", " "),
                "abstract": abstract,
                "authors": authors,
                "topics": [],
                "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
                "github_url": None,
                "published": published,
            }
        )

    return results


# ── alphaXiv async helpers ────────────────────────────────────────────────────


async def _search_async(client: AlphaXivClient, query: str) -> list[dict[str, Any]]:
    async with client:
        results = await client.search.papers_rich(query)
    return [
        {
            "arxiv_id": r.canonical_id or r.id,
            "title": r.title,
            "abstract": r.abstract[:400] if r.abstract else "",
            "authors": [a.name for a in r.authors] if r.authors else [],
            "topics": r.topics or [],
            "arxiv_url": (f"https://arxiv.org/abs/{r.canonical_id}" if r.canonical_id else None),
            "github_url": r.github_url,
            "published": (r.publication_date or "")[:10],
        }
        for r in results
    ]


async def _overview_async(client: AlphaXivClient, arxiv_id: str) -> dict[str, Any]:
    async with client:
        overview = await client.papers.overview(arxiv_id)
    return {
        "arxiv_id": arxiv_id,
        "title": overview.title,
        "abstract": overview.abstract,
        "overview": overview.overview_markdown,
    }


# ── Public API ────────────────────────────────────────────────────────────────


def search_papers(
    query: str,
    *,
    api_key: str | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Search for papers matching *query*.

    Uses alphaXiv (richer results: topics, GitHub links, AI overviews) when an
    API key is configured.  Falls back to the free arXiv API automatically when
    no key is available — no error, no prompt.
    """
    try:
        client = _build_client(api_key)
    except AlphaXivAuthError:
        # No key — silently use arXiv free API instead.
        return _search_arxiv(query, max_results=max_results)

    results = asyncio.run(_search_async(client, query))
    return results[:max_results]


def _get_paper_arxiv(arxiv_id: str) -> dict[str, Any]:
    """Fetch basic paper metadata from the free arXiv API (no key required)."""
    params = urllib.parse.urlencode({"id_list": arxiv_id, "max_results": 1})
    url = f"{_ARXIV_API}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"arXiv API unreachable: {e}") from e

    root = ET.fromstring(raw)
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    if entry is None:
        raise RuntimeError(f"No paper found for arXiv ID: {arxiv_id}")

    def _text(tag: str) -> str:
        el = entry.find(f"{{{_ATOM_NS}}}{tag}")
        return el.text.strip() if el is not None and el.text else ""

    authors = [
        a.find(f"{{{_ATOM_NS}}}name").text.strip()
        for a in entry.findall(f"{{{_ATOM_NS}}}author")
        if a.find(f"{{{_ATOM_NS}}}name") is not None
    ]

    return {
        "arxiv_id": arxiv_id,
        "title": _text("title").replace("\n", " "),
        "abstract": _text("summary").replace("\n", " "),
        "overview": None,  # AI overview requires alphaXiv key
        "authors": authors,
        "published": _text("published")[:10],
    }


def get_paper_overview(
    arxiv_id: str,
    *,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch paper details for *arxiv_id*.

    Uses alphaXiv for an AI-generated overview when a key is configured.
    Falls back to the free arXiv API (title + abstract only, no overview) otherwise.
    """
    try:
        client = _build_client(api_key)
    except AlphaXivAuthError:
        return _get_paper_arxiv(arxiv_id)
    return asyncio.run(_overview_async(client, arxiv_id))

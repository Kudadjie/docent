"""Sync facades over the async alphaxiv-py SDK.

Each public function runs a self-contained asyncio event loop so callers
(Typer CLI, MCP handler, tests) don't need to manage async state.
"""
from __future__ import annotations

import asyncio
from typing import Any

from alphaxiv import AlphaXivClient
from alphaxiv.exceptions import APIError


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
            "arxiv_url": (
                f"https://arxiv.org/abs/{r.canonical_id}" if r.canonical_id else None
            ),
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


def search_papers(
    query: str,
    *,
    api_key: str | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Search alphaXiv for papers matching *query*. Returns up to *max_results* dicts."""
    client = _build_client(api_key)
    results = asyncio.run(_search_async(client, query))
    return results[:max_results]


def get_paper_overview(
    arxiv_id: str,
    *,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch the AI-generated overview for *arxiv_id*. Returns a dict with title/abstract/overview."""
    client = _build_client(api_key)
    return asyncio.run(_overview_async(client, arxiv_id))

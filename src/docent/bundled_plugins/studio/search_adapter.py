"""SearchAdapter — dependency-injectable search interface for the research pipeline.

Decouples the pipeline from concrete search implementations so unit tests can
inject a FakeSearchAdapter instead of monkeypatching individual functions.

Usage (production)::

    from .search_adapter import DefaultSearchAdapter
    adapter = DefaultSearchAdapter(api_key=..., ss_key=..., alphaxiv_key=...)

Usage (tests)::

    from .search_adapter import FakeSearchAdapter
    adapter = FakeSearchAdapter(
        web_results=[...],
        paper_results=[...],
        page_content="full page text",
    )
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SearchAdapter(Protocol):
    """Protocol satisfied by any object that provides the four search primitives."""

    def web_search(self, query: str, max_results: int = 8) -> list[dict[str, Any]]:
        """Search the web. Returns [{title, url, snippet}]."""
        ...

    def paper_search(self, query: str, max_results: int = 8) -> list[dict[str, Any]]:
        """Search academic papers via Semantic Scholar. Returns [{title, url, snippet, ...}]."""
        ...

    def academic_search_parallel(self, queries: list[str]) -> list[dict[str, Any]]:
        """Parallel arXiv + Semantic Scholar search. Returns merged [{title, url, snippet, ...}]."""
        ...

    def fetch_page(self, url: str, max_chars: int = 3000) -> str:
        """Fetch and strip a URL. Returns first *max_chars* characters of body text."""
        ...


class DefaultSearchAdapter:
    """Production adapter that delegates to the concrete functions in search.py."""

    def __init__(
        self,
        api_key: str | None = None,
        semantic_scholar_api_key: str | None = None,
        alphaxiv_api_key: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._ss_key = semantic_scholar_api_key
        self._alphaxiv_key = alphaxiv_api_key

    def web_search(self, query: str, max_results: int = 8) -> list[dict[str, Any]]:
        from .search import web_search
        return web_search(query, max_results=max_results, api_key=self._api_key)

    def paper_search(self, query: str, max_results: int = 8) -> list[dict[str, Any]]:
        from .search import paper_search
        return paper_search(
            query,
            max_results=max_results,
            api_key=self._ss_key,
        )

    def academic_search_parallel(self, queries: list[str]) -> list[dict[str, Any]]:
        from .search import academic_search_parallel
        return academic_search_parallel(
            queries,
            semantic_scholar_api_key=self._ss_key,
            alphaxiv_api_key=self._alphaxiv_key,
        )

    def fetch_page(self, url: str, max_chars: int = 3000) -> str:
        from .search import fetch_page
        return fetch_page(url, max_chars=max_chars)


class FakeSearchAdapter:
    """Deterministic test double — returns pre-configured results, no network I/O."""

    def __init__(
        self,
        web_results: list[dict[str, Any]] | None = None,
        paper_results: list[dict[str, Any]] | None = None,
        academic_results: list[dict[str, Any]] | None = None,
        page_content: str = "fetched content",
    ) -> None:
        self._web = web_results or []
        self._papers = paper_results or []
        self._academic = academic_results or []
        self._page = page_content

        # Call counters for assertions in tests
        self.web_search_calls: list[str] = []
        self.paper_search_calls: list[str] = []
        self.academic_search_calls: list[list[str]] = []
        self.fetch_calls: list[str] = []

    def web_search(self, query: str, max_results: int = 8) -> list[dict[str, Any]]:
        self.web_search_calls.append(query)
        return list(self._web)[:max_results]

    def paper_search(self, query: str, max_results: int = 8) -> list[dict[str, Any]]:
        self.paper_search_calls.append(query)
        return list(self._papers)[:max_results]

    def academic_search_parallel(self, queries: list[str]) -> list[dict[str, Any]]:
        self.academic_search_calls.append(list(queries))
        return list(self._academic)

    def fetch_page(self, url: str, max_chars: int = 3000) -> str:
        self.fetch_calls.append(url)
        return self._page[:max_chars]

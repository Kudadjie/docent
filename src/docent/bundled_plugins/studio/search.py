"""Web search, academic paper search, page fetching, and Tavily research for the research pipeline."""
from __future__ import annotations

import datetime
import json
import logging
import re
import time
from pathlib import Path
from typing import Generator

import httpx

from docent.core import ProgressEvent

try:
    from tavily.errors import InvalidAPIKeyError, UsageLimitExceededError
except ImportError:  # tavily-python not installed
    InvalidAPIKeyError = RuntimeError  # type: ignore[misc,assignment]
    UsageLimitExceededError = RuntimeError  # type: ignore[misc,assignment]

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_S2_FIELDS = "title,abstract,authors,year,externalIds"

logger = logging.getLogger(__name__)


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
    Set via config: docent studio config-set tavily_api_key <key>
    Or env: DOCENT_RESEARCH__TAVILY_API_KEY
    """
    if not api_key:
        return []
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query,
            max_results=max_results,
            search_depth="advanced",
        )
        # Increment daily request counter
        try:
            current = _read_tavily_daily_requests()
            _write_tavily_daily_requests(current + 1)
        except Exception:
            pass
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in response.get("results", [])
        ]
        if not results:
            logger.warning("Tavily search for %r returned 0 results (response keys: %s)",
                           query, list(response.keys()))
        return results
    except (InvalidAPIKeyError, UsageLimitExceededError):
        # Auth/rate-limit errors should not be silently swallowed.
        raise
    except Exception as e:
        logger.warning("Tavily search for %r failed: %s: %s", query, type(e).__name__, e)
        return []


def paper_search(
    query: str,
    max_results: int = 5,
    api_key: str | None = None,
) -> list[dict]:
    """Search Semantic Scholar for academic papers.

    Returns list of {title, url, snippet, authors, year}.

    An optional Semantic Scholar API key can be provided for higher rate
    limits (free at https://www.semanticscholar.org/product/api#api-key-form).
    When unauthenticated, the public API allows ~100 requests per 5 minutes.
    """
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key

    # Retry on 429 with exponential backoff (5s, 10s)
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            resp = httpx.get(
                f"{_S2_BASE}/paper/search",
                params={"query": query, "fields": _S2_FIELDS, "limit": max_results},
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 429 and attempt < max_retries:
                wait = 5 * (attempt + 1)
                logger.warning(
                    "Semantic Scholar rate-limited for %r, retrying in %ds (attempt %d/%d)",
                    query, wait, attempt + 1, max_retries,
                )
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        except Exception as e:
            logger.warning(
                "Semantic Scholar search for %r failed: %s: %s",
                query, type(e).__name__, e,
            )
            return []
    else:
        # All retries exhausted on 429
        logger.warning("Semantic Scholar search for %r failed after %d retries (429)", query, max_retries)
        return []

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
    except Exception as e:
        logger.debug("Failed to fetch %s: %s", url, e)
        return ""


def tavily_research(
    topic: str,
    api_key: str,
    *,
    model: str = "pro",
    citation_format: str = "numbered",
    poll_interval: float = 5.0,
    timeout: float = 600.0,
) -> Generator[ProgressEvent, None, dict]:
    """Run Tavily deep research and return the result dict.

    Uses the Tavily Research API which produces a fully cited report.
    Yields ProgressEvent items while polling; returns a dict with
    ``content`` (the report text) and ``sources`` (list of source dicts).

    Raises ``InvalidAPIKeyError`` on auth failure, ``TimeoutError`` on
    timeout, and re-raises other Tavily errors.
    """
    from tavily import TavilyClient
    from tavily.errors import InvalidAPIKeyError, UsageLimitExceededError

    client = TavilyClient(api_key=api_key)

    yield ProgressEvent(
        phase="research",
        message=f"Starting Tavily research on: {topic!r}",
    )

    # Start the research task
    try:
        task = client.research(
            input=topic,
            model=model,
            citation_format=citation_format,
            timeout=90,
        )
    except (InvalidAPIKeyError, UsageLimitExceededError):
        raise
    except Exception as e:
        raise RuntimeError(f"Tavily research start failed: {e}") from e

    request_id = task.get("request_id")
    if not request_id:
        raise RuntimeError(f"Tavily research returned no request_id: {task}")

    yield ProgressEvent(
        phase="research",
        message=f"Research task created (id: {request_id[:8]}...), polling for results...",
    )

    # Poll until complete
    start = time.time()
    poll_count = 0
    while True:
        elapsed = time.time() - start
        if elapsed > timeout:
            raise TimeoutError(
                f"Tavily research timed out after {timeout:.0f}s "
                f"(request {request_id})"
            )

        try:
            result = client.get_research(request_id)
        except (InvalidAPIKeyError, UsageLimitExceededError):
            raise
        except Exception as e:
            logger.warning("Tavily get_research poll failed: %s: %s", type(e).__name__, e)
            time.sleep(poll_interval)
            continue

        status = result.get("status", "unknown")
        poll_count += 1

        if status == "completed":
            # Increment daily request counter
            try:
                current = _read_tavily_daily_requests()
                _write_tavily_daily_requests(current + 1)
            except Exception:
                pass

            sources = []
            for s in result.get("sources", []):
                sources.append({
                    "title": s.get("title", ""),
                    "url": s.get("url", ""),
                    "snippet": s.get("content", "")[:500] if s.get("content") else "",
                    "source_type": "web",
                })

            yield ProgressEvent(
                phase="research",
                message=f"Tavily research complete ({len(sources)} sources, {elapsed:.0f}s)",
            )

            return {
                "content": result.get("content", ""),
                "sources": sources,
                "request_id": request_id,
            }

        elif status in ("failed", "error"):
            error_msg = result.get("error") or result.get("message") or status
            raise RuntimeError(f"Tavily research failed: {error_msg}")

        # Still in progress — yield progress and wait
        yield ProgressEvent(
            phase="research",
            message=f"Research in progress (status: {status}, {elapsed:.0f}s elapsed)...",
        )
        time.sleep(poll_interval)
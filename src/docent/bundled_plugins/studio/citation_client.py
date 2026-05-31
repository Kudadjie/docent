"""Semantic Scholar citation graph client.

Fetches the papers that cite (or are cited by) an anchor paper and returns
normalized dicts ready for CiteGraphResult. No PDF downloading — metadata
is the reference manager's job.
"""

from __future__ import annotations

import logging
import time

import httpx

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_PAPER_FIELDS = "title,abstract,authors,year,externalIds,openAccessPdf"

logger = logging.getLogger(__name__)


def resolve_s2_id(doi: str | None, arxiv_id: str | None) -> str:
    """Convert a user-supplied DOI or arXiv ID to a Semantic Scholar paper ID."""
    if doi:
        doi = doi.strip()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/"):
            if doi.startswith(prefix):
                doi = doi[len(prefix) :]
                break
        return f"DOI:{doi}"
    if arxiv_id:
        arxiv_id = arxiv_id.strip()
        if "arxiv.org/abs/" in arxiv_id:
            arxiv_id = arxiv_id.rsplit("/", 1)[-1]
        if "v" in arxiv_id and arxiv_id[-1].isdigit():
            arxiv_id = arxiv_id.split("v")[0]
        return f"ARXIV:{arxiv_id}"
    raise ValueError("Provide either doi or arxiv_id.")


_RATE_LIMIT_MSG = (
    "Semantic Scholar rate limit hit. "
    "Get a free API key at semanticscholar.org/product/api and add it in "
    "Settings → API keys → Semantic Scholar, then try again."
)

_RETRY_DELAYS = [5, 15, 30]  # seconds between attempts


def _s2_get(path: str, params: dict, api_key: str | None) -> dict:
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            logger.warning(
                "Semantic Scholar rate-limited, retrying in %ds (attempt %d)", delay, attempt
            )
            time.sleep(delay)
        try:
            resp = httpx.get(f"{_S2_BASE}{path}", params=params, headers=headers, timeout=20)
            if resp.status_code == 429:
                last_exc = RuntimeError(_RATE_LIMIT_MSG)
                continue
            if resp.status_code == 404:
                raise LookupError(f"Paper not found in Semantic Scholar: {path}")
            resp.raise_for_status()
            return resp.json()
        except LookupError:
            raise
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Semantic Scholar error {e.response.status_code}: {path}") from e
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Semantic Scholar request failed: {e}") from e
    raise last_exc or RuntimeError(_RATE_LIMIT_MSG)


def _parse_authors(authors: list[dict]) -> str:
    return ", ".join(a.get("name", "") for a in (authors or [])[:3])


def _parse_paper(raw: dict) -> dict:
    ext = raw.get("externalIds") or {}
    oa = raw.get("openAccessPdf") or {}
    s2_id = raw.get("paperId", "")
    abstract = raw.get("abstract") or ""
    return {
        "title": raw.get("title") or "",
        "abstract": abstract[:600] if abstract else "",  # cap at 600 chars
        "authors": _parse_authors(raw.get("authors") or []),
        "year": raw.get("year"),
        "doi": ext.get("DOI"),
        "arxiv_id": ext.get("ArXiv"),
        "oa_url": oa.get("url"),
        "s2_url": f"https://www.semanticscholar.org/paper/{s2_id}" if s2_id else "",
        "_s2_id": s2_id,
    }


def fetch_anchor(s2_id: str, api_key: str | None) -> dict:
    """Fetch and normalize metadata for the anchor paper."""
    data = _s2_get(f"/paper/{s2_id}", {"fields": _PAPER_FIELDS}, api_key)
    return _parse_paper(data)


def fetch_citation_graph(
    s2_id: str,
    direction: str,
    limit: int,
    api_key: str | None,
) -> list[dict]:
    """Return normalized paper dicts from the citation graph.

    direction: 'cited-by' (who cites this), 'citing' (what this cites), 'both'.
    Papers are deduplicated by S2 paper ID.
    """
    seen: dict[str, dict] = {}

    def _fetch(endpoint: str, field: str) -> None:
        data = _s2_get(
            f"/paper/{s2_id}/{endpoint}",
            {"fields": _PAPER_FIELDS, "limit": limit},
            api_key,
        )
        for item in data.get("data", []):
            raw = item.get(field) or {}
            if not raw.get("paperId"):
                continue
            p = _parse_paper(raw)
            seen.setdefault(p["_s2_id"], p)

    if direction in ("cited-by", "both"):
        _fetch("citations", "citingPaper")
    if direction in ("citing", "both"):
        _fetch("references", "citedPaper")

    return list(seen.values())

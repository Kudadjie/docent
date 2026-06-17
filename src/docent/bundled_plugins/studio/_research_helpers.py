"""Citation-graph anchoring and expansion helpers for the research actions.

Split out of _research.py (re-exported there).
"""

from __future__ import annotations

import functools
import logging
import re
from collections.abc import Callable
from typing import Any, cast

logger = logging.getLogger(__name__)

_ARXIV_URL_RE = re.compile(r"arxiv\.org/abs/([\d.]+)")
_DOI_URL_RE = re.compile(r"doi\.org/(.+)")


def _extract_anchor_ids(sources: list[dict], max_anchors: int = 2) -> list[dict]:
    """Extract identifiers from sources for cite-graph anchoring.

    Priority: arXiv ID > DOI (URL or field) > bare S2 paper ID.
    Returns a list of dicts each with an 'arxiv_id', 'doi', or 's2_id' key,
    up to max_anchors. Only paper-type sources are considered.
    """
    seen: set[str] = set()
    anchors: list[dict] = []
    for s in sources:
        if len(anchors) >= max_anchors:
            break
        # Skip pure web sources — they rarely resolve in S2
        if s.get("source_type") == "web":
            continue
        url = s.get("url", "")
        m = _ARXIV_URL_RE.search(url)
        if m:
            arxiv_id = m.group(1)
            if arxiv_id not in seen:
                seen.add(arxiv_id)
                anchors.append({"arxiv_id": arxiv_id})
            continue
        m = _DOI_URL_RE.search(url)
        if m:
            doi = m.group(1).rstrip("/")
            if doi not in seen:
                seen.add(doi)
                anchors.append({"doi": doi})
            continue
        doi = s.get("doi")
        if doi and doi not in seen:
            seen.add(doi)
            anchors.append({"doi": doi})
            continue
        # Last resort: bare S2 paper ID (for non-arXiv, non-DOI papers)
        s2_id = s.get("s2_paper_id")
        if s2_id and s2_id not in seen:
            seen.add(s2_id)
            anchors.append({"s2_id": s2_id})
    return anchors


def _expand_citations(
    sources: list[dict],
    api_key: str | None,
    *,
    max_anchors: int = 2,
) -> tuple[list[dict], str]:
    """Parallel cite-graph expansion on anchor papers.

    1. Extracts up to max_anchors arXiv/DOI identifiers from sources.
    2. Fetches citation graphs concurrently via S2 (cited-by direction).
    3. Returns (extra_sources, citation_section_markdown).
       extra_sources are OA papers not already in sources; the markdown section
       is a formatted list suitable for appending to the research draft.
    """
    from .citation_client import fetch_citation_graph, resolve_s2_id
    from .fanout import parallel_fetch

    anchors = _extract_anchor_ids(sources, max_anchors)
    if not anchors:
        return [], ""

    # Build set of existing identifiers for deduplication.
    existing_ids: set[str] = set()
    for s in sources:
        url = s.get("url", "")
        m = _ARXIV_URL_RE.search(url)
        if m:
            existing_ids.add(m.group(1))
        m = _DOI_URL_RE.search(url)
        if m:
            existing_ids.add(m.group(1).rstrip("/"))
        doi = s.get("doi")
        if doi:
            existing_ids.add(doi)

    def _fetch_one(anchor: dict) -> list[dict]:
        # Bare S2 paper IDs skip resolve_s2_id — they're already the right format
        if anchor.get("s2_id"):
            s2_id = anchor["s2_id"]
        else:
            s2_id = resolve_s2_id(anchor.get("doi"), anchor.get("arxiv_id"))
        return fetch_citation_graph(s2_id, "cited-by", 20, api_key)

    tasks = cast(
        list[Callable[[], Any]],
        [functools.partial(_fetch_one, anchor) for anchor in anchors],
    )
    raw_results = parallel_fetch(tasks)

    # Collect unique OA papers not already in sources.
    oa_papers: list[dict] = []
    seen: set[str] = set(existing_ids)
    for result in raw_results:
        if not isinstance(result, list):
            continue
        for p in result:
            if not p.get("oa_url"):
                continue
            key = p.get("arxiv_id") or p.get("doi") or p.get("title", "")
            if key and key not in seen:
                seen.add(key)
                oa_papers.append(p)

    if not oa_papers:
        return [], ""

    capped = oa_papers[:15]

    extra_sources = [
        {
            "title": p["title"],
            "url": p.get("oa_url") or "",
            "snippet": (p.get("abstract") or "")[:500],
            "authors": p.get("authors", ""),
            "year": p.get("year"),
            "source_type": "cite-graph",
        }
        for p in capped
    ]

    lines = [
        "## Related Papers (Citation Discovery)",
        "",
        f"*{len(capped)} open-access papers discovered via Semantic Scholar "
        f"citation graph (cited-by, {len(anchors)} anchor paper(s)).*",
        "",
    ]
    for p in capped:
        title = p.get("title", "Untitled")
        authors = p.get("authors", "")
        year = p.get("year")
        oa_url = p.get("oa_url", "")
        doi = p.get("doi", "")
        meta = " | ".join(filter(None, [authors, str(year) if year else ""]))
        link = oa_url or (f"https://doi.org/{doi}" if doi else "")
        suffix = f" — {meta}" if meta else ""
        if link:
            lines.append(f"- [{title}]({link}){suffix}")
        else:
            lines.append(f"- **{title}**{suffix}")

    return extra_sources, "\n".join(lines)

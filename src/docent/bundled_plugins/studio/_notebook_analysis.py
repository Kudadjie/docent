"""Answer parsing, topic derivation, and source scoring/ranking for to-notebook.

Split out of _notebook.py (re-exported there).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from ._notebook_learning import _domain_from_url

# ---------------------------------------------------------------------------
# Quality-gate parsing
# ---------------------------------------------------------------------------

_FOLLOWUP_PATTERN = re.compile(
    r"\n+\s*(?:Would you like(?: me)? to|Do you (?:want|need)(?: me)? to|"
    r"Shall I|Is there anything else|Let me know if|Can I help you|"
    r"If you(?:'d like| want)|Feel free to ask)[\s\S]*$",
    re.IGNORECASE,
)


def _strip_followup(text: str) -> str:
    """Remove trailing conversational follow-up questions from a NLM response."""
    return _FOLLOWUP_PATTERN.sub("", text).rstrip()


def _extract_section(answer: str, section_name: str, max_chars: int = 500) -> str:
    """Extract the body of a ### SECTION_NAME block, truncated to max_chars."""
    m = re.search(
        rf"###\s*{re.escape(section_name)}\s*\n(.*?)(?=###|\Z)",
        answer,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return ""
    text = m.group(1).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text


def _extract_gaps(answer: str) -> list[str]:
    """Extract gap items from the GAPS section of a quality gate answer."""
    match = re.search(r"###\s*GAPS\s*\n(.*?)(?=###|\Z)", answer, re.DOTALL | re.IGNORECASE)
    if not match:
        return []
    section = match.group(1).strip()
    items = re.findall(r"(?m)^(?:\d+\.\s*|[-*•]\s*)(.+?)$", section)
    return [i.strip() for i in items if i.strip()][:5]


def _parse_quality_gate(answer: str) -> dict[str, Any]:
    """Parse quality gate answer into a structured dict."""
    answer = _strip_followup(answer)
    validation = "unknown"
    val_m = re.search(r"###\s*VALIDATION\s*\n(.*?)(?=###|\Z)", answer, re.DOTALL | re.IGNORECASE)
    if val_m:
        t = val_m.group(1).strip().lower()
        validation = (
            "clean"
            if re.search(r"\bclean\b|\bno issues\b|\bwell.?supported\b|\bfully supported\b", t)
            else "issues found"
        )

    contradictions = 0
    con_m = re.search(
        r"###\s*CONTRADICTIONS\s*\n(.*?)(?=###|\Z)", answer, re.DOTALL | re.IGNORECASE
    )
    if con_m:
        t = con_m.group(1).strip()
        if not re.search(
            r"\bnone\b|\bno contradictions\b|\bno source.?vs.?source\b", t, re.IGNORECASE
        ):
            numbered = re.findall(r"(?m)^\d+\.", t)
            contradictions = len(numbered) if numbered else 1

    return {
        "validation": validation,
        "contradictions": contradictions,
        "gaps": _extract_gaps(answer),
        "raw": answer,
    }


def _parse_perspectives(answer: str) -> dict[str, str]:
    """Parse multi-perspective answer into {practitioner, skeptic, beginner}."""
    answer = _strip_followup(answer)
    out: dict[str, str] = {}
    for key in ("PRACTITIONER", "SKEPTIC", "BEGINNER"):
        m = re.search(rf"###\s*{key}\s*\n(.*?)(?=###|\Z)", answer, re.DOTALL | re.IGNORECASE)
        out[key.lower()] = m.group(1).strip() if m else ""
    return out


# ---------------------------------------------------------------------------
# Topic / source helpers
# ---------------------------------------------------------------------------

_BACKEND_SUFFIXES = ("-free", "-feynman", "-docent")
_WORKFLOW_SUFFIXES = (
    "-deep",
    "-lit",
    "-review",
    "-compare",
    "-replicate",
    "-audit",
    "-draft",
    "-update",
    "-verify",
    "-analysis",
)


def _derive_topic(out_path: Path) -> str:
    """Derive a human-readable topic from a research output file.

    Reads the first # heading from the file content when available — this is
    always more accurate than the filename, especially for renamed or generic
    files (e.g. "test 2.md" whose heading is "Plastic Pollution in Coastal
    West Africa").  Strips Docent's own workflow/tier prefixes from the heading
    (e.g. "Deep Research (Free Tier): " → bare topic).  Falls back to
    stripping backend/workflow suffixes from the stem when no heading is found.
    """
    _HEADING_PREFIX = re.compile(
        r"^(?:Deep Research|Literature Review|Peer Review|Research|Analysis)"
        r"(?:\s*\([^)]*\))?\s*:\s*",
        re.IGNORECASE,
    )

    # Prefer heading from file content
    try:
        for line in out_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip()
                heading = _HEADING_PREFIX.sub("", heading).strip()
                if heading:
                    return heading
    except OSError:
        pass

    # Fallback: derive from filename
    stem = out_path.stem
    for suffix in _BACKEND_SUFFIXES:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    for suffix in _WORKFLOW_SUFFIXES:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem.replace("-", " ").replace("_", " ")


# ---------------------------------------------------------------------------
# Source scoring helpers
# ---------------------------------------------------------------------------

# Domains whose content is treated as inherently authoritative.
# Score 1.0 = top tier (intergovernmental, peer-reviewed journals, major health agencies).
# Score 0.6 = reputable tier (established journalism, policy think-tanks).
# Anything else defaults to 0.3.
_AUTHORITY_TOP = frozenset(
    {
        # Health / science agencies
        "who.int",
        "cdc.gov",
        "nih.gov",
        "ncbi.nlm.nih.gov",
        "pubmed.ncbi.nlm.nih.gov",
        "emro.who.int",
        "afro.who.int",
        "euro.who.int",
        # Intergovernmental
        "un.org",
        "undp.org",
        "unep.org",
        "worldbank.org",
        "imf.org",
        "oecd.org",
        "ipcc.ch",
        "iea.org",
        "fao.org",
        "ifad.org",
        "wfp.org",
        # Peer-reviewed journals
        "nature.com",
        "science.org",
        "thelancet.com",
        "nejm.org",
        "cell.com",
        "bmj.com",
        "jamanetwork.com",
        "plos.org",
        "plosone.org",
        "mdpi.com",
        "frontiersin.org",
        "wiley.com",
        "springer.com",
        "elsevier.com",
        "oxfordjournals.org",
        "cambridge.org",
        "tandfonline.com",
        # Preprint / open access
        "arxiv.org",
        "biorxiv.org",
        "medrxiv.org",
        "ssrn.com",
        "researchgate.net",
        "semanticscholar.org",
    }
)

_AUTHORITY_REPUTABLE = frozenset(
    {
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "bbc.co.uk",
        "theguardian.com",
        "ft.com",
        "economist.com",
        "nytimes.com",
        "washingtonpost.com",
        "theatlantic.com",
        "brookings.edu",
        "cfr.org",
        "rand.org",
        "chathamhouse.org",
        "pewresearch.org",
        "statista.com",
    }
)

_CURRENT_YEAR = 2026
_MAX_PER_DOMAIN = 3  # never allocate more than this many slots to one domain


def _parse_year(year_val: Any) -> int | None:
    """Return an integer year or None."""
    if isinstance(year_val, int):
        return year_val
    if isinstance(year_val, str) and year_val[:4].isdigit():
        return int(year_val[:4])
    return None


def _domain_authority(domain: str) -> float:
    """Return 0.0–1.0 authority score for a bare domain (no www.)."""
    bare = domain.removeprefix("www.")
    if bare in _AUTHORITY_TOP:
        return 1.0
    # .gov and .edu TLDs are unconditionally authoritative
    if bare.endswith(".gov") or bare.endswith(".edu") or bare.endswith(".ac.uk"):
        return 1.0
    if bare in _AUTHORITY_REPUTABLE:
        return 0.6
    return 0.3


def _score_source(source: dict, year_min: int | None, year_range: int) -> float:
    """Compute a ranking score for one source.

    Tier boundaries are wide apart so tier order never flips, but within each
    tier sources are ordered by *relative* recency (papers) or domain authority
    (web).

    Recency is computed relative to the year spread of the current paper batch,
    not against today — so a 2013 paper in a 2005–2015 query scores the same
    as a 2023 paper in a 2015–2025 query.  This respects explicit year-range
    searches and avoids penalising foundational older work.

    Score bands:
      Papers             100 – 120  (+ up to 20 for relative recency)
      Web with full text  50 –  80  (+ up to 30 for domain authority)
      Web snippet          0 –  30  (+ up to 30 for domain authority)
    """
    stype = source.get("source_type")
    url = source.get("url", "")
    domain = _domain_from_url(url).removeprefix("www.")

    if stype == "paper":
        base = 100.0
        if year_min is not None and year_range > 0:
            year = _parse_year(source.get("year"))
            if year is not None:
                relative_recency = (year - year_min) / year_range
                base += relative_recency * 20.0
        return base

    if stype == "web":
        base = 50.0 if source.get("full_text") else 0.0
        base += _domain_authority(domain) * 30.0
        return base

    return 0.0


def _rank_sources(sources: list[dict], max_sources: int) -> list[dict]:
    """Rank sources by tier, recency, and domain authority; deduplicate by domain.

    Priority order:
      1. Papers (peer-reviewed / preprint) — sorted by relative recency within
         the batch's own year range (honours explicit year-range queries).
      2. Web sources with full page text — sorted by domain authority.
      3. Web sources with snippet only — sorted by domain authority.

    Within each tier, no single domain supplies more than _MAX_PER_DOMAIN slots
    so one over-represented source doesn't crowd out everything else.
    """
    # URL-level deduplication first
    seen_urls: set[str] = set()
    unique: list[dict] = []
    for s in sources:
        url = (s.get("url") or "").rstrip("/")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(s)

    # Compute year range across all papers in this batch for relative recency
    paper_years = [
        y
        for s in unique
        if s.get("source_type") == "paper"
        for y in [_parse_year(s.get("year"))]
        if y is not None
    ]
    year_min = min(paper_years) if paper_years else None
    year_max = max(paper_years) if paper_years else None
    year_range = (year_max - year_min) if (year_min is not None and year_max is not None) else 0

    # Score and sort
    scored = sorted(unique, key=lambda s: _score_source(s, year_min, year_range), reverse=True)

    # Domain-level deduplication: keep at most _MAX_PER_DOMAIN per domain
    domain_counts: dict[str, int] = {}
    result: list[dict] = []
    for s in scored:
        if len(result) >= max_sources:
            break
        domain = _domain_from_url(s.get("url", "")).removeprefix("www.")
        if domain_counts.get(domain, 0) >= _MAX_PER_DOMAIN:
            continue
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        result.append(s)

    return result

"""Citation verification via public academic APIs.

Extracts DOIs and arXiv IDs from a research draft and checks each one
against CrossRef (for DOIs) and Semantic Scholar (for arXiv IDs). Appends
a ## Citation Verification report to the draft so downstream reviewers
can see which citations resolve to real papers and which could not be confirmed.

No new dependencies — uses only stdlib urllib. The Semantic Scholar api_key
parameter is reserved for future authenticated calls; unauthenticated requests
work for most use cases.

Verification pattern inspired by Academic Research Skills (Cheng-I Wu, CC-BY-NC 4.0):
  https://github.com/Imbad0202/academic-research-skills
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Matches DOIs like 10.1000/xyz123, stopping at whitespace or common punctuation
_DOI_RE = re.compile(
    r"\b(10\.\d{4,}(?:\.\d+)*/\S+?)(?=[,;\s\]\)\"\']|$)",
    re.IGNORECASE,
)
# Matches arXiv IDs: NNNN.NNNNN or NNNN.NNNNNvN
_ARXIV_RE = re.compile(r"\b(\d{4}\.\d{4,5}(?:v\d+)?)\b")


@dataclass
class CitationResult:
    identifier: str
    id_type: str  # "doi" | "arxiv"
    found: bool
    resolved_title: str = ""
    error: str = ""


@dataclass
class CitationReport:
    verified: list[CitationResult] = field(default_factory=list)
    unverified: list[CitationResult] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.unverified)

    def as_markdown(self) -> str:
        lines = ["## Citation Verification\n"]
        total = len(self.verified) + len(self.unverified)
        if total == 0:
            lines.append("*No citable identifiers (DOIs or arXiv IDs) found in this document.*\n")
            return "\n".join(lines)

        lines.append(
            f"*{len(self.verified)}/{total} identifiers verified against "
            f"CrossRef / Semantic Scholar.*\n"
        )

        if self.verified:
            lines.append("### Verified")
            for r in self.verified:
                title_note = f" — {r.resolved_title}" if r.resolved_title else ""
                lines.append(f"- `{r.identifier}` ({r.id_type}){title_note}")
            lines.append("")

        if self.unverified:
            lines.append("### Could Not Verify")
            lines.append(
                "> These identifiers did not resolve against CrossRef or Semantic Scholar."
            )
            lines.append(
                "> They may be hallucinated, misprinted, or not yet indexed — review carefully."
            )
            for r in self.unverified:
                err_note = f" — {r.error}" if r.error else ""
                lines.append(f"- `{r.identifier}` ({r.id_type}){err_note}")
            lines.append("")

        return "\n".join(lines)


def _extract_identifiers(text: str) -> list[tuple[str, str]]:
    """Return deduped (identifier, type) pairs — DOIs before arXiv IDs."""
    seen: set[str] = set()
    results: list[tuple[str, str]] = []

    for m in _DOI_RE.finditer(text):
        doi = m.group(1).rstrip(".")
        if doi not in seen:
            seen.add(doi)
            results.append((doi, "doi"))

    for m in _ARXIV_RE.finditer(text):
        arxiv_id = m.group(1)
        if arxiv_id not in seen:
            seen.add(arxiv_id)
            results.append((arxiv_id, "arxiv"))

    return results


def _verify_doi_crossref(doi: str) -> tuple[bool, str, str]:
    """Check DOI against CrossRef API. Returns (found, resolved_title, error)."""
    import json
    import urllib.error
    import urllib.request

    url = f"https://api.crossref.org/works/{doi}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Docent/1.0 (mailto:docent-bot@example.com)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            titles = data.get("message", {}).get("title", [])
            title = titles[0] if titles else ""
            return True, title, ""
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "", "not found in CrossRef"
        return False, "", f"CrossRef HTTP {e.code}"
    except Exception as e:
        return False, "", f"CrossRef error: {type(e).__name__}"


def _verify_arxiv_semantic_scholar(
    arxiv_id: str, ss_key: str | None = None
) -> tuple[bool, str, str]:
    """Check arXiv ID against Semantic Scholar. Returns (found, resolved_title, error)."""
    import json
    import urllib.error
    import urllib.request

    url = f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}?fields=title"
    headers: dict[str, str] = {"User-Agent": "Docent/1.0"}
    if ss_key:
        headers["x-api-key"] = ss_key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            title = data.get("title", "")
            return True, title, ""
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "", "not found in Semantic Scholar"
        if e.code == 429:
            return False, "", "Semantic Scholar rate-limited — skipped"
        return False, "", f"Semantic Scholar HTTP {e.code}"
    except Exception as e:
        return False, "", f"Semantic Scholar error: {type(e).__name__}"


def verify_citations(
    draft: str,
    ss_key: str | None = None,
    max_checks: int = 20,
    delay: float = 0.3,
) -> CitationReport:
    """Extract and verify all DOIs and arXiv IDs found in draft text.

    Checks at most max_checks identifiers to avoid long delays on large documents.
    A 0.3s inter-request delay keeps Docent within CrossRef's polite pool limits.
    """
    identifiers = _extract_identifiers(draft)[:max_checks]
    report = CitationReport()

    for identifier, id_type in identifiers:
        try:
            if id_type == "doi":
                found, title, error = _verify_doi_crossref(identifier)
            else:
                found, title, error = _verify_arxiv_semantic_scholar(identifier, ss_key)

            result = CitationResult(
                identifier=identifier,
                id_type=id_type,
                found=found,
                resolved_title=title[:120] if title else "",
                error=error,
            )
            if found:
                report.verified.append(result)
            else:
                report.unverified.append(result)
        except Exception as e:
            logger.warning("Citation check failed for %s: %s", identifier, e)
            report.unverified.append(
                CitationResult(
                    identifier=identifier,
                    id_type=id_type,
                    found=False,
                    error=f"check failed: {e}",
                )
            )

        if delay > 0:
            time.sleep(delay)

    return report

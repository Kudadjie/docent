"""NotebookLM integration — helpers and full 4-phase pipeline for the to-notebook action.

Phases:
  0  Auth (auto-login on expiry)
  1  NLM web research arm  (source add-research --no-wait, then poll + manual-add)
  2  Populate              (synthesis doc + Feynman URLs, stabilise, delete errors)
  3  Quality gate          (validation + contradictions + gap-fill)
  4  Perspectives          (practitioner / skeptic / beginner)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator
from urllib.parse import parse_qsl, urlencode, urlparse

from pydantic import BaseModel, Field

from docent.core import ProgressEvent
from docent.core.shapes import ErrorShape, LinkShape, MessageShape, MetricShape, Shape

if TYPE_CHECKING:
    from docent.core import Context

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SKILL_DIR = Path.home() / ".claude" / "skills" / "research-to-notebook"
_SKILL_COMPAT_PATH = _SKILL_DIR / "source-compat.json"
_SKILL_RUN_LOG_PATH = _SKILL_DIR / "run-log.jsonl"
_SKILL_OVERRIDES_PATH = _SKILL_DIR / "active-overrides.json"

_NOTEBOOK_MAP_FILENAME = ".notebook-map.json"


def _find_sources_path(out_path: Path) -> Path | None:
    """Return the sources JSON path for a research output file, or None.

    Checks both naming conventions used by different Docent backends:
      • Docent/Feynman: {stem}-sources.json
      • Free-tier:      {stem}.sources.json  (via Path.with_suffix)
    """
    dash_form = out_path.parent / f"{out_path.stem}-sources.json"
    dot_form = out_path.with_suffix(".sources.json")
    if dash_form.exists():
        return dash_form
    if dot_form.exists():
        return dot_form
    return None

_QUALITY_GATE_PROMPT = (
    "Analyze this notebook and answer in THREE clearly-headed sections.\n\n"
    "### VALIDATION\n"
    "Compare the synthesis document against the other sources. Flag any claims in the synthesis "
    "that are NOT supported by the sources, or that misrepresent them. Quote the problematic "
    "claim and explain the discrepancy. If clean, say so explicitly.\n\n"
    "### CONTRADICTIONS\n"
    "List source-vs-source contradictions. For each, cite the specific claims and the sources "
    "that disagree. If none, say so.\n\n"
    "### GAPS\n"
    "List the most important subtopics or perspectives a researcher studying {topic} would "
    "expect but that the current sources do NOT cover. Be specific about what is absent."
)

_PERSPECTIVES_PROMPT = (
    "Produce THREE summaries with clear headers.\n\n"
    "### PRACTITIONER\n"
    "Key findings as a practitioner who needs to apply this work. Actionable takeaways.\n\n"
    "### SKEPTIC\n"
    "Key findings as a skeptical peer reviewer. Main weaknesses and what you would push back on.\n\n"
    "### BEGINNER\n"
    "Plain-language overview for someone with no background in this field."
)

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _nlm_exe() -> str | None:
    """Return the notebooklm executable path, or None if not on PATH."""
    return shutil.which("notebooklm")


def _nlm_run(args: list[str], timeout: float = 30) -> tuple[int, str, str]:
    """Run a notebooklm command. Returns (returncode, stdout, stderr)."""
    exe = _nlm_exe()
    if not exe:
        return -1, "", "notebooklm not found on PATH"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(
            [exe] + args, capture_output=True, text=True, timeout=timeout, env=env
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout after {timeout:.0f}s"
    except OSError as e:
        return -1, "", str(e)


def _nlm_login(timeout: float = 120) -> tuple[bool, str]:
    """Run `notebooklm login` interactively (inherits terminal). Returns (success, message).

    We do NOT capture output — the user needs to see what notebooklm prints
    and interact with the browser it opens.  Whether login truly succeeded is
    determined by the caller via a follow-up _nlm_auth_ok() check, so an
    exit code of 1 (e.g. the Playwright redirect-on-already-logged-in case)
    is handled there rather than here.
    """
    exe = _nlm_exe()
    if not exe:
        return False, "notebooklm not found on PATH"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run([exe, "login"], timeout=timeout, env=env)
        if result.returncode == 0:
            return True, ""
        return False, f"notebooklm login exited with code {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"Login timed out after {timeout:.0f}s"
    except OSError as e:
        return False, str(e)


def _nlm_auth_ok(retries: int = 2, retry_delay: float = 2.0) -> bool:
    """Return True if notebooklm is installed and authenticated.

    Retries once to guard against a transient CLI hiccup, but keeps the
    total wait short (2 × 15 s = 30 s max) so a genuine auth failure doesn't
    block the pipeline for a minute.
    """
    exe = _nlm_exe()
    if not exe:
        return False
    for attempt in range(retries):
        rc, stdout, _ = _nlm_run(["list", "--json"], timeout=15)
        if rc == 0:
            try:
                data = json.loads(stdout)
                if not (isinstance(data, dict) and data.get("error")):
                    return True
            except (json.JSONDecodeError, ValueError):
                pass
        if attempt < retries - 1:
            time.sleep(retry_delay)
    return False


def _nlm_create_notebook(title: str) -> str | None:
    """Create a notebook. Returns notebook ID on success, None on failure."""
    rc, stdout, _ = _nlm_run(["create", title, "--json"], timeout=30)
    if rc != 0:
        return None
    try:
        data = json.loads(stdout)
        # CLI returns {"notebook": {"id": "..."}}; also accept flat {"id": ...}
        return (
            data.get("notebook", {}).get("id")
            or data.get("id")
            or data.get("notebook_id")
        )
    except (json.JSONDecodeError, ValueError):
        return None


def _nlm_add_source(source: str, notebook_id: str) -> tuple[int, str]:
    """Add one source (URL or file path). Returns (returncode, error_message)."""
    rc, _, stderr = _nlm_run(
        ["source", "add", source, "-n", notebook_id, "--json"], timeout=60
    )
    return rc, stderr


def _nlm_source_list(notebook_id: str) -> list[dict]:
    """Return the current source list for a notebook."""
    rc, stdout, _ = _nlm_run(["source", "list", "-n", notebook_id, "--json"], timeout=30)
    if rc != 0:
        return []
    try:
        data = json.loads(stdout)
        return data.get("sources", [])
    except (json.JSONDecodeError, ValueError):
        return []


def _nlm_source_delete(source_id: str, notebook_id: str) -> bool:
    """Delete a single source. Returns True on success."""
    rc, _, _ = _nlm_run(["source", "delete", source_id, "-n", notebook_id, "-y"], timeout=30)
    return rc == 0


def _nlm_wait_stable(
    notebook_id: str, max_wait: float = 90, interval: float = 5
) -> dict[str, Any]:
    """Poll source list until no sources are in 'preparing' state.

    Returns {stable, waited_s, error_ids, counts, total}.
    """
    start = time.monotonic()
    last: dict[str, Any] = {"counts": {}, "error_ids": [], "total": 0}
    while time.monotonic() - start < max_wait:
        sources = _nlm_source_list(notebook_id)
        if sources:
            counts: dict[str, int] = {"ready": 0, "error": 0, "preparing": 0, "other": 0}
            error_ids: list[str] = []
            for s in sources:
                st = (s.get("status") or "").lower()
                if st in counts:
                    counts[st] += 1
                else:
                    counts["other"] += 1
                if st == "error":
                    error_ids.append(s["id"])
            last = {"counts": counts, "error_ids": error_ids, "total": len(sources)}
            if counts["preparing"] == 0:
                return {"stable": True, "waited_s": round(time.monotonic() - start, 1), **last}
        time.sleep(interval)
    return {"stable": False, "waited_s": round(time.monotonic() - start, 1), **last}


def _nlm_start_research(query: str, notebook_id: str) -> bool:
    """Fire off NLM web research (--no-wait). Returns True if the command succeeded."""
    rc, _, _ = _nlm_run(
        ["source", "add-research", query, "--mode", "fast", "--no-wait", "-n", notebook_id],
        timeout=60,
    )
    return rc == 0


def _nlm_poll_research(notebook_id: str, poll_timeout: float = 300) -> list[str]:
    """Poll research status until complete. Returns list of found source URLs."""
    deadline = time.monotonic() + poll_timeout
    while time.monotonic() < deadline:
        rc, stdout, _ = _nlm_run(
            ["research", "status", "-n", notebook_id, "--json"], timeout=30
        )
        if rc == 0:
            try:
                data = json.loads(stdout)
                status = data.get("status", "")
                if status == "completed":
                    sources = data.get("sources", [])
                    urls = []
                    for s in sources:
                        url = (
                            s.get("url")
                            or s.get("link")
                            or s.get("href")
                            or (s.get("metadata") or {}).get("url")
                        )
                        if url and url.startswith("http"):
                            urls.append(url)
                    return list(dict.fromkeys(urls))
                elif status == "no_research":
                    return []
            except (json.JSONDecodeError, ValueError):
                pass
        time.sleep(10)
    return []


def _poll_research_gen(
    notebook_id: str,
    poll_timeout: float = 300,
    phase: str = "nlm-research",
    label: str = "",
) -> Iterator[ProgressEvent]:
    """Generator version of _nlm_poll_research.

    Yields a ProgressEvent every poll cycle so the UI stays alive during long waits.
    Returns the found URL list via StopIteration.value — use with ``yield from``:

        urls = yield from _poll_research_gen(notebook_id, ...)
    """
    deadline = time.monotonic() + poll_timeout
    start = time.monotonic()
    prefix = f"{label}: " if label else ""
    while time.monotonic() < deadline:
        rc, stdout, _ = _nlm_run(
            ["research", "status", "-n", notebook_id, "--json"], timeout=30
        )
        if rc == 0:
            try:
                data = json.loads(stdout)
                status = data.get("status", "")
                if status == "completed":
                    sources = data.get("sources", [])
                    urls = []
                    for s in sources:
                        url = (
                            s.get("url")
                            or s.get("link")
                            or s.get("href")
                            or (s.get("metadata") or {}).get("url")
                        )
                        if url and url.startswith("http"):
                            urls.append(url)
                    return list(dict.fromkeys(urls))
                elif status == "no_research":
                    return []
            except (json.JSONDecodeError, ValueError):
                pass
        elapsed = round(time.monotonic() - start)
        yield ProgressEvent(phase=phase, message=f"{prefix}Polling ({elapsed}s elapsed)...")
        time.sleep(10)
    return []


def _nlm_ask(question: str, notebook_id: str, timeout: float = 180) -> str | None:
    """Ask the notebook a question. Returns answer text or None on failure."""
    rc, stdout, _ = _nlm_run(["ask", question, "-n", notebook_id, "--json"], timeout=timeout)
    if rc != 0:
        return None
    try:
        data = json.loads(stdout)
        return data.get("answer")
    except (json.JSONDecodeError, ValueError):
        # Rich may emit non-JSON; try raw stdout
        return stdout.strip() or None


# ---------------------------------------------------------------------------
# URL utilities
# ---------------------------------------------------------------------------

def _strip_utm(url: str) -> str:
    """Strip utm_* tracking parameters from a URL."""
    try:
        p = urlparse(url)
        qs = [(k, v) for k, v in parse_qsl(p.query) if not k.startswith("utm_")]
        return p._replace(query=urlencode(qs)).geturl()
    except Exception:
        return url


def _nlm_compat_filter(urls: list[str]) -> list[str]:
    """Filter URLs from known-bad domains using the skill's source-compat.json."""
    if not _SKILL_COMPAT_PATH.exists():
        return urls
    try:
        compat = json.loads(_SKILL_COMPAT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return urls
    always_skip = set(compat.get("always_skip", []))
    domains_data = compat.get("domains", {})
    result = []
    for url in urls:
        try:
            domain = urlparse(url).netloc.lower().removeprefix("www.")
        except Exception:
            result.append(url)
            continue
        if domain in always_skip:
            continue
        rate = domains_data.get(domain, {}).get("rate", -1)
        if rate != -1 and rate < 0.3:
            continue
        result.append(url)
    return result


def _update_compat(outcomes: list[tuple[str, bool]]) -> None:
    """Update source-compat.json with per-domain success/fail outcomes from this run."""
    if not outcomes or not _SKILL_COMPAT_PATH.exists():
        return
    try:
        compat = json.loads(_SKILL_COMPAT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    domains_data = compat.setdefault("domains", {})
    for domain, success in outcomes:
        if not domain:
            continue
        entry = domains_data.setdefault(domain, {"success": 0, "fail": 0, "rate": -1, "notes": ""})
        if success:
            entry["success"] += 1
        else:
            entry["fail"] += 1
        total = entry["success"] + entry["fail"]
        entry["rate"] = round(entry["success"] / total, 2) if total else -1
    import datetime
    compat["last_updated"] = datetime.date.today().isoformat()
    try:
        _SKILL_COMPAT_PATH.write_text(
            json.dumps(compat, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def _append_run_log(entry: dict[str, Any]) -> None:
    """Append one run entry to run-log.jsonl. Silent on failure."""
    try:
        with _SKILL_RUN_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _read_overrides() -> dict[str, Any]:
    """Read active-overrides.json. Returns defaults if missing or unreadable."""
    defaults: dict[str, Any] = {
        "wait_stable_max": 90,
        "feynman_skip": False,
        "youtube_min_views_low": False,
        "youtube_skip_followup": False,
        "skip_gap_analysis": False,
    }
    if not _SKILL_OVERRIDES_PATH.exists():
        return defaults
    try:
        data = json.loads(_SKILL_OVERRIDES_PATH.read_text(encoding="utf-8"))
        return {**defaults, **data}
    except (json.JSONDecodeError, OSError):
        return defaults


def _domain_from_url(url: str) -> str:
    """Extract bare domain (no www.) from a URL."""
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _nlm_deduplicate(urls: list[str], notebook_id: str) -> list[str]:
    """Remove URLs already present in the notebook."""
    existing = _nlm_source_list(notebook_id)
    existing_urls = {(s.get("url") or "").rstrip("/").lower() for s in existing if s.get("url")}
    return [u for u in urls if u.rstrip("/").lower() not in existing_urls]


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
        answer, re.DOTALL | re.IGNORECASE,
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
        if not re.search(r"\bnone\b|\bno contradictions\b|\bno source.?vs.?source\b", t, re.IGNORECASE):
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
        m = re.search(
            rf"###\s*{key}\s*\n(.*?)(?=###|\Z)", answer, re.DOTALL | re.IGNORECASE
        )
        out[key.lower()] = m.group(1).strip() if m else ""
    return out


# ---------------------------------------------------------------------------
# Topic / source helpers
# ---------------------------------------------------------------------------

_BACKEND_SUFFIXES = ("-free", "-feynman", "-docent")
_WORKFLOW_SUFFIXES = ("-deep", "-lit", "-review", "-compare", "-replicate", "-audit", "-draft", "-update", "-verify", "-analysis")


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
_AUTHORITY_TOP = frozenset({
    # Health / science agencies
    "who.int", "cdc.gov", "nih.gov", "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov",
    "emro.who.int", "afro.who.int", "euro.who.int",
    # Intergovernmental
    "un.org", "undp.org", "unep.org", "worldbank.org", "imf.org", "oecd.org",
    "ipcc.ch", "iea.org", "fao.org", "ifad.org", "wfp.org",
    # Peer-reviewed journals
    "nature.com", "science.org", "thelancet.com", "nejm.org", "cell.com",
    "bmj.com", "jamanetwork.com", "plos.org", "plosone.org",
    "mdpi.com", "frontiersin.org", "wiley.com", "springer.com", "elsevier.com",
    "oxfordjournals.org", "cambridge.org", "tandfonline.com",
    # Preprint / open access
    "arxiv.org", "biorxiv.org", "medrxiv.org", "ssrn.com",
    "researchgate.net", "semanticscholar.org",
})

_AUTHORITY_REPUTABLE = frozenset({
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "theguardian.com", "ft.com", "economist.com",
    "nytimes.com", "washingtonpost.com", "theatlantic.com",
    "brookings.edu", "cfr.org", "rand.org", "chathamhouse.org",
    "pewresearch.org", "statista.com",
})

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
        y for s in unique
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


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ToNotebookInputs(BaseModel):
    output_file: str | None = Field(
        None,
        description=(
            "Path to a research output .md file (e.g. 'storm-surge-ghana-deep.md'). "
            "If omitted, the most recent output in research.output_dir is used."
        ),
    )
    sources_file: str | None = Field(
        None,
        description=(
            "Path to a sources JSON file (e.g. 'my-research.sources.json'). "
            "If omitted, Docent looks for a matching file next to output_file. "
            "Use this when the sources file has a different name from the output file."
        ),
    )
    topic: str | None = Field(
        None,
        description=(
            "Research topic for NotebookLM's web research arm and quality gate prompts. "
            "Derived from the output file heading if omitted."
        ),
    )
    max_sources: int = Field(
        20,
        description="Maximum number of Feynman/lit sources to include (default 20).",
    )
    notebook_id: str | None = Field(
        None,
        description=(
            "NotebookLM notebook ID (from the URL when viewing the notebook). "
            "Overrides research.notebooklm_notebook_id in config."
        ),
    )
    guide_files: list[str] = Field(
        default_factory=list,
        description=(
            "Path(s) to files (PDF, .md, .txt) that guide the notebook population — "
            "each is added as a source and used to focus the NLM research query. "
            "Pass the flag multiple times to supply several files."
        ),
    )
    run_nlm_research: bool = Field(
        True,
        description=(
            "Run NotebookLM's built-in web research arm (fast mode) to find additional "
            "sources beyond those from Feynman/lit. Runs concurrently while Feynman "
            "sources are being added."
        ),
    )
    run_quality_gate: bool = Field(
        True,
        description=(
            "After populating, run the 3-section quality gate: validation, "
            "contradictions, and gap analysis. Gaps trigger targeted follow-up research."
        ),
    )
    run_perspectives: bool = Field(
        True,
        description=(
            "After the quality gate, generate 3 summaries: practitioner, skeptic, beginner."
        ),
    )
    output_files: list[str] = Field(
        default_factory=list,
        description=(
            "Additional research output files to add as sources alongside output_file. "
            "Populated by the interactive picker when the user selects multiple files; "
            "not normally set directly."
        ),
    )


class ToNotebookResult(BaseModel):
    ok: bool
    output_file: str | None
    sources_file: str | None
    package_dir: str | None
    sources_count: int
    sources_added: int = 0
    sources_failed: int = 0
    sources_from_feynman: int = 0
    sources_from_nlm: int = 0
    notebook_id: str | None = None
    quality_gate: dict | None = None
    perspectives: dict | None = None
    message: str

    def to_shapes(self) -> list[Shape]:
        from docent.core.shapes import MarkdownShape
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]

        # ── Metrics ──────────────────────────────────────────────────────────
        if self.notebook_id:
            shapes.append(MetricShape(label="Notebook ID", value=self.notebook_id))
        if self.sources_added:
            shapes.append(MetricShape(label="Sources added", value=str(self.sources_added)))
        if self.sources_from_nlm:
            shapes.append(MetricShape(label="From NLM research", value=str(self.sources_from_nlm)))
        if self.sources_failed:
            shapes.append(MetricShape(label="Sources failed", value=str(self.sources_failed)))

        # ── Quality gate detail ───────────────────────────────────────────────
        if self.quality_gate:
            qg = self.quality_gate
            validation = qg.get("validation", "?")
            contradictions = qg.get("contradictions", 0)
            gaps: list[str] = qg.get("gaps", [])
            gaps_filled: int = qg.get("gaps_filled", 0)
            raw: str = qg.get("raw", "")

            shapes.append(MetricShape(label="Validation", value=validation))
            shapes.append(MetricShape(label="Contradictions", value=str(contradictions)))
            if gaps_filled:
                shapes.append(MetricShape(label="Gaps filled", value=str(gaps_filled)))

            md: list[str] = []

            # Validation issues snippet
            if validation == "issues found" and raw:
                snippet = _extract_section(raw, "VALIDATION", max_chars=400)
                if snippet:
                    md.append(f"**Validation issues:**\n\n{snippet}")

            # Contradictions snippet
            if contradictions and raw:
                snippet = _extract_section(raw, "CONTRADICTIONS", max_chars=400)
                if snippet:
                    md.append(f"**Contradictions ({contradictions}):**\n\n{snippet}")

            # Gaps list
            if gaps:
                bullets = "\n".join(f"- {g[:120]}" for g in gaps)
                filled_note = f" ({gaps_filled} filled by follow-up research)" if gaps_filled else ""
                md.append(f"**Gaps identified{filled_note}:**\n\n{bullets}")

            if md:
                shapes.append(MarkdownShape(content="\n\n---\n\n".join(md)))

        # ── Perspectives ──────────────────────────────────────────────────────
        if self.perspectives:
            persp = self.perspectives
            md_persp: list[str] = []
            for key, label in (
                ("practitioner", "Practitioner takeaways"),
                ("skeptic", "Skeptic's view"),
                ("beginner", "Beginner overview"),
            ):
                text = (persp.get(key) or "").strip()
                if text:
                    if len(text) > 350:
                        text = text[:350].rsplit(" ", 1)[0] + "…"
                    md_persp.append(f"**{label}:**\n\n{text}")
            if md_persp:
                shapes.append(MarkdownShape(content="\n\n---\n\n".join(md_persp)))

        if self.package_dir:
            shapes.append(LinkShape(url=self.package_dir, label="Local package"))
        return shapes


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

_EMPTY_PIPELINE_RESULT: dict[str, Any] = {
    "ok": False, "notebook_id": None,
    "sources_added": 0, "sources_failed": 0,
    "sources_from_feynman": 0, "sources_from_nlm": 0,
    "quality_gate": None, "perspectives": None,
    "message": "",
}


def _notebook_remaining_capacity(notebook_id: str, limit: int) -> tuple[int, int]:
    """Return (current_source_count, remaining_slots) for a notebook.

    Uses the live source list so the count is always accurate even on re-runs
    where sources were already added in a previous session.
    """
    current = len(_nlm_source_list(notebook_id))
    return current, max(0, limit - current)


def _read_notebook_map(output_dir: Path) -> dict[str, str]:
    """Read stem→notebook_id map from output_dir/.notebook-map.json."""
    p = output_dir / _NOTEBOOK_MAP_FILENAME
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_notebook_map(output_dir: Path, stem: str, notebook_id: str) -> None:
    """Persist stem→notebook_id into output_dir/.notebook-map.json."""
    p = output_dir / _NOTEBOOK_MAP_FILENAME
    nmap = _read_notebook_map(output_dir)
    nmap[stem] = notebook_id
    try:
        p.write_text(json.dumps(nmap, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _nlm_push(
    out_path: Path,
    sources_path: Path | None,
    context: "Context",
    max_sources: int = 20,
    topic: str | None = None,
    guide_files: list[Path] | None = None,
    extra_synthesis_docs: list[Path] | None = None,
    run_nlm_research: bool = True,
    run_quality_gate: bool = True,
    run_perspectives: bool = True,
) -> Iterator[ProgressEvent]:
    """Full 4-phase NotebookLM pipeline.

    Yields ProgressEvents. Returns a result dict via StopIteration.value
    (call with ``result = yield from _nlm_push(...)``).
    """
    # ── Phase 0: Auth ──────────────────────────────────────────────────────
    yield ProgressEvent(phase="nlm-check", message="Checking NotebookLM auth...")
    if not _nlm_auth_ok():
        yield ProgressEvent(phase="nlm-login", message="Auth expired -- running notebooklm login...")
        login_ok, login_err = _nlm_login()
        # Always re-check auth after login regardless of exit code — a code-1
        # exit can mean "already authenticated" (Playwright redirect case).
        if not _nlm_auth_ok(retries=1, retry_delay=1.0):
            detail = f": {login_err}" if login_err else ""
            return {
                **_EMPTY_PIPELINE_RESULT,
                "message": (
                    f"NotebookLM auth expired{detail}. "
                    "Run `notebooklm login` manually then retry."
                ),
            }
        yield ProgressEvent(phase="nlm-login", message="Login successful.")

    # ── Resolve topic early (needed for notebook title + quality-gate) ───────
    effective_topic = topic or _derive_topic(out_path)

    # ── Resolve / create notebook ──────────────────────────────────────────
    notebook_id = context.settings.research.notebooklm_notebook_id
    _stem = out_path.stem
    _output_dir = out_path.parent

    if not notebook_id:
        # Check per-file map before creating a new notebook
        _nmap = _read_notebook_map(_output_dir)
        notebook_id = _nmap.get(_stem)
        if notebook_id:
            yield ProgressEvent(
                phase="nlm-notebook",
                message=f"Reusing existing notebook '{effective_topic}': {notebook_id}",
            )

    if not notebook_id:
        title = f"Docent Studio: {effective_topic}"
        yield ProgressEvent(phase="nlm-notebook", message=f"Creating notebook '{title}'...")
        notebook_id = _nlm_create_notebook(title)
        if not notebook_id:
            return {
                **_EMPTY_PIPELINE_RESULT,
                "message": "Failed to create NotebookLM notebook.",
            }
        yield ProgressEvent(phase="nlm-notebook", message=f"Created notebook {notebook_id}")

    # ── Source capacity check ─────────────────────────────────────────────
    _source_limit = context.settings.research.notebooklm_source_limit
    _current_count, _remaining = _notebook_remaining_capacity(notebook_id, _source_limit)
    if _current_count > 0:
        yield ProgressEvent(
            phase="nlm-notebook",
            message=f"Notebook has {_current_count}/{_source_limit} sources — {_remaining} slot(s) remaining.",
        )
    if _remaining == 0:
        tier_hint = (
            "If you're on NotebookLM Plus (100 sources), run `docent setup` to update your plan."
            if _source_limit == 50 else
            f"Notebook is at the {_source_limit}-source limit for your plan."
        )
        return {
            **_EMPTY_PIPELINE_RESULT,
            "notebook_id": notebook_id,
            "message": f"Notebook is full ({_current_count}/{_source_limit} sources). {tier_hint}",
        }
    if _remaining <= 10:
        yield ProgressEvent(
            phase="nlm-notebook",
            message=(
                f"[Warning] Only {_remaining} slot(s) left (limit: {_source_limit}). "
                "On NotebookLM Plus? Run `docent setup` to update your plan."
            ),
        )

    # ── Read active overrides (auto-tune from past run history) ───────────
    overrides = _read_overrides()
    stable_max_wait = float(overrides.get("wait_stable_max", 90))
    if overrides.get("skip_gap_analysis"):
        yield ProgressEvent(
            phase="nlm-quality",
            message="Gap analysis disabled by active-overrides (skip_gap_analysis=true).",
        )

    # ── Run tracking ──────────────────────────────────────────────────────
    import datetime as _dt
    _run_start = time.monotonic()
    _url_outcomes: list[tuple[str, bool]] = []  # (domain, success)
    _errors: list[str] = []
    _errors_deleted = 0

    # ── Resolve guide files ───────────────────────────────────────────────
    _guide_paths: list[Path] = []
    for _gf in (guide_files or []):
        _gp = Path(_gf).expanduser()
        if _gp.exists():
            _guide_paths.append(_gp)
        else:
            yield ProgressEvent(
                phase="nlm-guide", message=f"Guide file not found: {_gp} -- ignoring."
            )

    # ── Phase 1: Start NLM web research (non-blocking) ────────────────────
    # Enrich query with guide file keywords if available
    research_query = effective_topic
    if _guide_paths:
        try:
            guide_snippet = " ".join(
                gp.read_text(encoding="utf-8")[:300].replace("\n", " ")
                for gp in _guide_paths
            )
            research_query = f"{effective_topic} -- {guide_snippet}"
        except OSError:
            pass

    nlm_research_started = False
    if run_nlm_research:
        yield ProgressEvent(
            phase="nlm-research",
            message=f"Starting NLM web research: '{effective_topic}'...",
        )
        nlm_research_started = _nlm_start_research(research_query, notebook_id)
        if not nlm_research_started:
            yield ProgressEvent(
                phase="nlm-research",
                message="NLM research start failed -- continuing without it.",
            )

    # ── Phase 2a: Add synthesis document ─────────────────────────────────
    added = 0
    failed = 0
    feynman_added = 0

    if _remaining > 0:
        yield ProgressEvent(phase="nlm-push", message="Adding synthesis document...")
        rc, err = _nlm_add_source(str(out_path), notebook_id)
        if rc == 0:
            added += 1
            feynman_added += 1
            _remaining -= 1
        else:
            failed += 1
            yield ProgressEvent(
                phase="nlm-push", message=f"Warning: synthesis doc failed: {err[:80]}"
            )
        time.sleep(1)

    # ── Extra synthesis docs (from multi-file picker) ─────────────────────
    for _extra in (extra_synthesis_docs or []):
        if _remaining <= 0:
            yield ProgressEvent(
                phase="nlm-push",
                message=f"Source limit reached ({_source_limit}) — skipping {_extra.name}.",
            )
            break
        yield ProgressEvent(phase="nlm-push", message=f"Adding synthesis document: {_extra.name}...")
        rc, err = _nlm_add_source(str(_extra), notebook_id)
        if rc == 0:
            added += 1
            feynman_added += 1
            _remaining -= 1
        else:
            yield ProgressEvent(phase="nlm-push", message=f"Warning: {_extra.name} failed: {err[:80]}")
        time.sleep(1)

    # ── Guide files as sources ────────────────────────────────────────────
    for guide_path in _guide_paths:
        if _remaining <= 0:
            yield ProgressEvent(
                phase="nlm-push",
                message=f"Source limit reached ({_source_limit}) — skipping guide file {guide_path.name}.",
            )
            break
        yield ProgressEvent(phase="nlm-push", message=f"Adding guide file: {guide_path.name}...")
        rc, err = _nlm_add_source(str(guide_path), notebook_id)
        if rc == 0:
            added += 1
            _remaining -= 1
        else:
            yield ProgressEvent(phase="nlm-push", message=f"Guide file add failed: {err[:80]}")
        time.sleep(1)

    # ── Phase 2b: Add Feynman / lit URL sources ───────────────────────────
    if sources_path and sources_path.exists():
        raw_sources: list[dict] = json.loads(sources_path.read_text(encoding="utf-8"))
        selected = _rank_sources(raw_sources, max_sources)
        url_sources = [s for s in selected if s.get("url")]

        # Strip utm params, compat-filter, deduplicate against notebook
        urls = [_strip_utm(s["url"]) for s in url_sources]
        urls = _nlm_compat_filter(urls)
        urls = _nlm_deduplicate(urls, notebook_id)
        urls = urls[:_remaining]  # never exceed remaining capacity

        total = len(urls)
        for i, url in enumerate(urls, 1):
            title_short = url[:60]
            yield ProgressEvent(
                phase="nlm-push",
                message=f"[{i}/{total}] {title_short}",
                current=i,
                total=total,
            )
            rc, _ = _nlm_add_source(url, notebook_id)
            ok = rc == 0
            _url_outcomes.append((_domain_from_url(url), ok))
            if ok:
                added += 1
                feynman_added += 1
                _remaining -= 1
            else:
                failed += 1
            time.sleep(1)

    # ── Phase 1 completion: poll NLM research, add found URLs ─────────────
    nlm_added = 0
    nlm_sources_found = 0
    snap: dict[str, Any] = {}  # will be set by wait_stable; init here for run-log safety
    if run_nlm_research and nlm_research_started:
        nlm_urls = yield from _poll_research_gen(
            notebook_id, poll_timeout=300, phase="nlm-research", label="NLM research"
        )
        nlm_sources_found = len(nlm_urls)
        if nlm_urls:
            nlm_urls = _nlm_compat_filter(nlm_urls)
            nlm_urls = _nlm_deduplicate(nlm_urls, notebook_id)
            nlm_urls = nlm_urls[:_remaining]  # cap to remaining capacity
            total_nlm = len(nlm_urls)
            yield ProgressEvent(
                phase="nlm-research",
                message=f"NLM research found {total_nlm} new source(s). Adding...",
            )
            for i, url in enumerate(nlm_urls, 1):
                yield ProgressEvent(
                    phase="nlm-research",
                    message=f"NLM [{i}/{total_nlm}] {url[:60]}",
                    current=i,
                    total=total_nlm,
                )
                rc, _ = _nlm_add_source(url, notebook_id)
                ok = rc == 0
                _url_outcomes.append((_domain_from_url(url), ok))
                if ok:
                    added += 1
                    nlm_added += 1
                    _remaining -= 1
                else:
                    failed += 1
                time.sleep(1)
            # Clear the progress bar — emit a final summary without current/total
            yield ProgressEvent(
                phase="nlm-research",
                message=f"NLM research done: {nlm_added} source(s) added.",
            )
        else:
            yield ProgressEvent(
                phase="nlm-research", message="NLM research completed (no additional sources)."
            )

    # ── Phase 2 completion: stabilise + delete errors ─────────────────────
    yield ProgressEvent(phase="nlm-stabilise", message="Waiting for sources to stabilise...")
    snap = _nlm_wait_stable(notebook_id, max_wait=max(stable_max_wait, 120))
    waited = snap.get("waited_s", 0)
    counts = snap.get("counts", {})
    yield ProgressEvent(
        phase="nlm-stabilise",
        message=(
            f"Stable after {waited:.0f}s: "
            f"ready: {counts.get('ready', 0)}, "
            f"error: {counts.get('error', 0)}, "
            f"preparing: {counts.get('preparing', 0)}"
        ),
    )

    error_ids: list[str] = snap.get("error_ids", [])
    if error_ids:
        yield ProgressEvent(
            phase="nlm-stabilise",
            message=f"Deleting {len(error_ids)} errored source(s)...",
        )
        for eid in error_ids:
            _nlm_source_delete(eid, notebook_id)
        _errors_deleted += len(error_ids)

    # ── Phase 3: Quality gate ─────────────────────────────────────────────
    quality_gate: dict | None = None
    gaps_filled = 0

    if run_quality_gate:
        yield ProgressEvent(phase="nlm-quality", message="Running quality gate (validation + contradictions + gaps)...")
        gate_prompt = _QUALITY_GATE_PROMPT.format(topic=effective_topic)
        gate_answer = _nlm_ask(gate_prompt, notebook_id, timeout=180)

        if gate_answer:
            quality_gate = _parse_quality_gate(gate_answer)
            quality_gate["gaps_filled"] = 0

            gaps = quality_gate.get("gaps", [])
            yield ProgressEvent(
                phase="nlm-quality",
                message=(
                    f"Quality gate: {quality_gate['validation']}, "
                    f"{quality_gate['contradictions']} contradiction(s), "
                    f"{len(gaps)} gap(s) identified."
                ),
            )

            # Fill each gap (unless override says skip)
            if overrides.get("skip_gap_analysis") and gaps:
                yield ProgressEvent(phase="nlm-quality", message="Gap analysis skipped (active-overrides).")
                gaps = []

            total_gaps = len(gaps)
            for gap_idx, gap in enumerate(gaps, 1):
                yield ProgressEvent(
                    phase="nlm-quality",
                    message=f"Gap {gap_idx}/{total_gaps}: '{gap[:60]}'...",
                    current=gap_idx,
                    total=total_gaps,
                )
                started = _nlm_start_research(gap, notebook_id)
                if started:
                    gap_urls = yield from _poll_research_gen(
                        notebook_id,
                        poll_timeout=180,
                        phase="nlm-quality",
                        label=f"Gap {gap_idx}/{total_gaps}",
                    )
                    gap_urls = _nlm_compat_filter(gap_urls)
                    gap_urls = _nlm_deduplicate(gap_urls, notebook_id)
                    for url in gap_urls[:min(5, _remaining)]:  # cap per-gap and respect limit
                        rc, _ = _nlm_add_source(url, notebook_id)
                        ok = rc == 0
                        _url_outcomes.append((_domain_from_url(url), ok))
                        if ok:
                            added += 1
                            nlm_added += 1
                            _remaining -= 1
                        time.sleep(1)
                    if gap_urls:
                        gaps_filled += 1

            if gaps_filled:
                yield ProgressEvent(
                    phase="nlm-stabilise",
                    message=f"Re-stabilising after {gaps_filled} gap fill(s)...",
                )
                snap2 = _nlm_wait_stable(notebook_id, max_wait=stable_max_wait)
                gap_err_ids = snap2.get("error_ids", [])
                for eid in gap_err_ids:
                    _nlm_source_delete(eid, notebook_id)
                _errors_deleted += len(gap_err_ids)

            quality_gate["gaps_filled"] = gaps_filled
        else:
            yield ProgressEvent(
                phase="nlm-quality", message="Quality gate failed (no response from notebook)."
            )

    # ── Phase 4: Perspectives ─────────────────────────────────────────────
    perspectives: dict | None = None

    if run_perspectives:
        yield ProgressEvent(
            phase="nlm-perspectives",
            message="Generating practitioner / skeptic / beginner summaries...",
        )
        persp_answer = _nlm_ask(_PERSPECTIVES_PROMPT, notebook_id, timeout=180)
        if persp_answer:
            perspectives = _parse_perspectives(persp_answer)
            yield ProgressEvent(
                phase="nlm-perspectives", message="Perspectives generated."
            )
        else:
            yield ProgressEvent(
                phase="nlm-perspectives",
                message="Perspectives failed (no response from notebook).",
            )

    # ── Build summary message ─────────────────────────────────────────────
    parts = [f"Notebook ready: {added} source(s) added"]
    if nlm_added:
        parts.append(f"{nlm_added} from NLM research")
    if failed:
        parts.append(f"{failed} failed")
    if quality_gate:
        parts.append(f"quality gate: {quality_gate['validation']}")
        if gaps_filled:
            parts.append(f"{gaps_filled} gap(s) filled")
    if perspectives:
        parts.append("perspectives generated")
    parts.append(f"notebook: {notebook_id}")

    # ── Persist stem→notebook_id mapping for future runs ─────────────────
    _save_notebook_map(_output_dir, _stem, notebook_id)

    # ── Post-run: update source-compat.json + write run log ───────────────
    _update_compat(_url_outcomes)

    _nlm_hit_rate = (
        round(sum(1 for _, ok in _url_outcomes if ok) / len(_url_outcomes), 2)
        if _url_outcomes else 0.0
    )
    _append_run_log({
        "timestamp": _dt.datetime.now().isoformat(),
        "mode": "research",
        "topic": effective_topic[:120],
        "notebook_id": notebook_id,
        "duration_min": round((time.monotonic() - _run_start) / 60, 1),
        "sources_final": added,
        "sources_added_manual": feynman_added,
        "sources_from_nlm_research": nlm_added,
        "sources_errors_deleted": _errors_deleted,
        "nlm_research_mode": "fast",
        "nlm_sources_found": nlm_sources_found,
        "nlm_source_hit_rate": _nlm_hit_rate,
        "stabilization_wait_s": snap.get("waited_s", 0),
        "quality_gate": {
            "combined_ask_used": True,
            "validation": quality_gate.get("validation", "skipped") if quality_gate else "skipped",
            "contradictions": quality_gate.get("contradictions", 0) if quality_gate else 0,
            "gaps_filled": gaps_filled,
            "multi_perspective_combined": perspectives is not None,
        },
        "auth_expired_mid_run": False,
        "errors": _errors,
        "auto_tune_overrides": [k for k, v in overrides.items() if v and k != "wait_stable_max"],
        "guide_files": [str(gp) for gp in _guide_paths],
    })

    return {
        "ok": True,
        "notebook_id": notebook_id,
        "sources_added": added,
        "sources_failed": failed,
        "sources_from_feynman": feynman_added,
        "sources_from_nlm": nlm_added,
        "quality_gate": quality_gate,
        "perspectives": perspectives,
        "message": ", ".join(parts),
    }

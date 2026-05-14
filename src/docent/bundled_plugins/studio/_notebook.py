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
    """Run `notebooklm login` interactively (inherits terminal). Returns (success, message)."""
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


def _nlm_auth_ok() -> bool:
    """Return True if notebooklm is installed and authenticated."""
    exe = _nlm_exe()
    if not exe:
        return False
    rc, stdout, _ = _nlm_run(["list", "--json"], timeout=20)
    if rc != 0:
        return False
    try:
        data = json.loads(stdout)
        return not (isinstance(data, dict) and data.get("error"))
    except (json.JSONDecodeError, ValueError):
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

def _derive_topic(out_path: Path) -> str:
    """Derive a human-readable topic from a research output filename."""
    stem = out_path.stem
    for suffix in ("-deep", "-lit", "-review", "-update", "-verify", "-analysis"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem.replace("-", " ").replace("_", " ")


def _rank_sources(sources: list[dict], max_sources: int) -> list[dict]:
    """Rank sources: papers first, then web with full text, then snippets."""
    papers = [s for s in sources if s.get("source_type") == "paper" and s.get("url")]
    web_full = [
        s for s in sources
        if s.get("source_type") == "web" and s.get("url") and s.get("full_text")
    ]
    web_snippet = [
        s for s in sources
        if s.get("source_type") == "web" and s.get("url") and not s.get("full_text")
    ]
    ranked = papers + web_full + web_snippet
    seen: set[str] = set()
    unique: list[dict] = []
    for s in ranked:
        url = s.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(s)
    return unique[:max_sources]


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
    topic: str | None = Field(
        None,
        description=(
            "Research topic for NotebookLM's web research arm and quality gate prompts. "
            "Derived from the output filename if omitted."
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
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.notebook_id:
            shapes.append(MetricShape(label="Notebook ID", value=self.notebook_id))
        if self.sources_added:
            shapes.append(MetricShape(label="Sources added", value=str(self.sources_added)))
        if self.sources_from_nlm:
            shapes.append(MetricShape(label="From NLM research", value=str(self.sources_from_nlm)))
        if self.sources_failed:
            shapes.append(MetricShape(label="Sources failed", value=str(self.sources_failed)))
        if self.quality_gate:
            shapes.append(MetricShape(label="Validation", value=self.quality_gate.get("validation", "?")))
            shapes.append(MetricShape(label="Contradictions", value=str(self.quality_gate.get("contradictions", 0))))
            gf = self.quality_gate.get("gaps_filled", 0)
            if gf:
                shapes.append(MetricShape(label="Gaps filled", value=str(gf)))
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


def _nlm_push(
    out_path: Path,
    sources_path: Path | None,
    context: "Context",
    max_sources: int = 20,
    topic: str | None = None,
    guide_files: list[Path] | None = None,
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
        if not login_ok or not _nlm_auth_ok():
            detail = f": {login_err}" if login_err else ""
            return {
                **_EMPTY_PIPELINE_RESULT,
                "message": (
                    f"NotebookLM auth expired{detail}. "
                    "Run `notebooklm login` manually then retry."
                ),
            }
        yield ProgressEvent(phase="nlm-login", message="Login successful.")

    # ── Resolve / create notebook ──────────────────────────────────────────
    notebook_id = context.settings.research.notebooklm_notebook_id
    if not notebook_id:
        title = f"Studio: {out_path.stem}"
        yield ProgressEvent(phase="nlm-notebook", message=f"Creating notebook '{title}'...")
        notebook_id = _nlm_create_notebook(title)
        if not notebook_id:
            return {
                **_EMPTY_PIPELINE_RESULT,
                "message": "Failed to create NotebookLM notebook.",
            }
        yield ProgressEvent(phase="nlm-notebook", message=f"Created notebook {notebook_id}")

    effective_topic = topic or _derive_topic(out_path)

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

    yield ProgressEvent(phase="nlm-push", message="Adding synthesis document...")
    rc, err = _nlm_add_source(str(out_path), notebook_id)
    if rc == 0:
        added += 1
        feynman_added += 1
    else:
        failed += 1
        yield ProgressEvent(
            phase="nlm-push", message=f"Warning: synthesis doc failed: {err[:80]}"
        )
    time.sleep(1)

    # ── Guide files as sources ────────────────────────────────────────────
    for guide_path in _guide_paths:
        yield ProgressEvent(phase="nlm-push", message=f"Adding guide file: {guide_path.name}...")
        rc, err = _nlm_add_source(str(guide_path), notebook_id)
        if rc == 0:
            added += 1
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
            else:
                failed += 1
            time.sleep(1)

    # ── Phase 1 completion: poll NLM research, add found URLs ─────────────
    nlm_added = 0
    nlm_sources_found = 0
    snap: dict[str, Any] = {}  # will be set by wait_stable; init here for run-log safety
    if run_nlm_research and nlm_research_started:
        yield ProgressEvent(phase="nlm-research", message="Polling NLM research status...")
        nlm_urls = _nlm_poll_research(notebook_id, poll_timeout=300)
        nlm_sources_found = len(nlm_urls)
        if nlm_urls:
            nlm_urls = _nlm_compat_filter(nlm_urls)
            nlm_urls = _nlm_deduplicate(nlm_urls, notebook_id)
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
                else:
                    failed += 1
                time.sleep(1)
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

            for gap in gaps:
                yield ProgressEvent(
                    phase="nlm-quality", message=f"Filling gap: '{gap[:60]}'..."
                )
                started = _nlm_start_research(gap, notebook_id)
                if started:
                    gap_urls = _nlm_poll_research(notebook_id, poll_timeout=180)
                    gap_urls = _nlm_compat_filter(gap_urls)
                    gap_urls = _nlm_deduplicate(gap_urls, notebook_id)
                    for url in gap_urls[:5]:  # cap per-gap to avoid bloat
                        rc, _ = _nlm_add_source(url, notebook_id)
                        ok = rc == 0
                        _url_outcomes.append((_domain_from_url(url), ok))
                        if ok:
                            added += 1
                            nlm_added += 1
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

"""Six-stage deep research pipeline powered by OpenCode LLM calls."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Generator

from docent.core import ProgressEvent

from .oc_client import OcClient
from .search import academic_search_parallel, fetch_page, paper_search, web_search, tavily_research

try:
    from tavily.errors import UsageLimitExceededError
except ImportError:
    UsageLimitExceededError = RuntimeError  # type: ignore[misc,assignment]

_AGENTS_DIR = Path(__file__).parent / "agents"

logger = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    return (_AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response, tolerating markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        )
    return json.loads(text)


def _fetch_artifact(artifact: str) -> str:
    """Return text content for an artifact (arXiv ID, URL, or local path)."""
    artifact = artifact.strip()
    if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", artifact):
        url = f"https://arxiv.org/abs/{artifact}"
        return fetch_page(url, max_chars=6000)
    if artifact.startswith("http://") or artifact.startswith("https://"):
        return fetch_page(artifact, max_chars=6000)
    path = Path(artifact)
    if path.exists() and path.suffix == ".pdf":
        return f"(Local PDF: {artifact} — text extraction not yet supported; reviewer will work from metadata only)"
    return f"(Could not fetch artifact: {artifact!r})"


# ---------------------------------------------------------------------------
# Tavily Research pipeline (primary path when API key is available)
# ---------------------------------------------------------------------------

def _run_tavily_pipeline(
    topic: str,
    oc: OcClient,
    *,
    tavily_api_key: str,
    tavily_model: str = "pro",
    model_reviewer: str = "deepseek-v4-pro",
    research_prefix: str = "",
    tavily_research_timeout: float = 600.0,
    semantic_scholar_api_key: str | None = None,
    alphaxiv_api_key: str | None = None,
) -> Generator[ProgressEvent, None, dict]:
    """Run Tavily research + OpenCode adversarial review.

    This replaces stages 1-5 of the manual pipeline with a single Tavily
    Research API call that produces a fully cited report. Then runs an
    OpenCode reviewer (stage 6) for value-add adversarial analysis.

    Yields ProgressEvent items, returns result dict.
    """
    # Phase 1: Tavily research (handles search, synthesis, citations)
    research_input = f"{research_prefix}{topic}" if research_prefix else topic
    try:
        research_result = yield from tavily_research(
            research_input, tavily_api_key, model=tavily_model,
            timeout=tavily_research_timeout,
        )
    except UsageLimitExceededError:
        return {
            "topic": topic,
            "draft": "",
            "review": "",
            "sources": [],
            "rounds": 0,
            "ok": False,
            "error": (
                "Tavily monthly free tier (1,000 calls) has been exceeded. "
                "Wait for the next billing cycle, upgrade your Tavily plan, "
                "or use backend='feynman' which does not require Tavily."
            ),
        }
    except Exception as e:
        return {
            "topic": topic,
            "draft": "",
            "review": "",
            "sources": [],
            "rounds": 0,
            "ok": False,
            "error": f"Tavily research failed: {e}",
        }

    content = research_result.get("content", "")
    sources: list[dict] = list(research_result.get("sources", []))

    if not content:
        return {
            "topic": topic,
            "draft": "",
            "review": "",
            "sources": sources,
            "rounds": 1,
            "ok": False,
            "error": "Tavily research returned empty content.",
        }

    # Augment: scholarly + arXiv in parallel alongside Tavily's web sources
    yield ProgressEvent(phase="fetch", message="Augmenting with academic sources (scholarly + arXiv)...")
    academic = academic_search_parallel(
        [topic],
        semantic_scholar_api_key=semantic_scholar_api_key,
        alphaxiv_api_key=alphaxiv_api_key,
    )
    if academic:
        sources.extend(academic)
        yield ProgressEvent(
            phase="fetch",
            message=f"Added {len(academic)} academic source(s) from scholarly/arXiv.",
        )

    # Phase 2: OpenCode adversarial review
    yield ProgressEvent(phase="review", message="Running adversarial review...")
    reviewer_prompt = _load_prompt("reviewer").replace("{draft}", content)
    try:
        review = oc.call(reviewer_prompt, model=model_reviewer, timeout=300)
    except Exception as e:
        logger.warning("Reviewer call failed: %s: %s", type(e).__name__, e)
        review = f"(Reviewer unavailable: {e})"

    # Phase 3: Refiner — address review findings
    refined_draft = content
    if review and not review.startswith("(Reviewer unavailable"):
        yield ProgressEvent(phase="refine", message="Refining draft based on review...")
        refiner_prompt = (
            _load_prompt("refiner")
            .replace("{draft}", content)
            .replace("{review}", review)
        )
        try:
            refined_result = oc.call(refiner_prompt, model=model_reviewer, timeout=300)
            # Quality guard: if refiner output is suspiciously short, keep original
            if refined_result and content and len(refined_result) < len(content) * 0.5:
                logger.warning(
                    "Refiner output (%d chars) is less than 50%% of original "
                    "(%d chars) — likely returned only edits. Keeping original.",
                    len(refined_result), len(content),
                )
            else:
                refined_draft = refined_result
        except Exception as e:
            logger.warning("Refiner call failed: %s: %s, keeping original", type(e).__name__, e)

    return {
        "topic": topic,
        "draft": refined_draft,
        "review": review,
        "sources": sources,
        "rounds": 1,
        "ok": True,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Manual pipeline (fallback when no Tavily key or Tavily research fails)
# ---------------------------------------------------------------------------

def _run_pipeline(
    topic: str,
    oc: OcClient,
    planner_name: str,
    writer_name: str,
    *,
    model_planner: str = "glm-5.1",
    model_writer: str = "minimax-m2.7",
    model_verifier: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
    tavily_api_key: str | None = None,
    semantic_scholar_api_key: str | None = None,
    alphaxiv_api_key: str | None = None,
) -> Generator[ProgressEvent, None, dict]:
    """Shared search-fetch-write-verify-review pipeline (manual mode).

    Yields ProgressEvent items during execution, returns the result dict.
    """
    sources: list[dict] = []
    rounds = 0

    # Stage 1: Search planner
    yield ProgressEvent(phase="search_plan", message="Generating search strategy...")
    planner_prompt = _load_prompt(planner_name).replace("{topic}", topic)
    try:
        plan_text = oc.call(planner_prompt, model=model_planner)
        plan = _parse_json(plan_text)
    except Exception as e:
        return {
            "topic": topic,
            "draft": "",
            "review": "",
            "sources": [],
            "rounds": 0,
            "ok": False,
            "error": f"Search planner failed: {e}",
        }

    web_queries = plan.get("web_queries", [])
    paper_queries = plan.get("paper_queries", [])
    all_queries = web_queries + plan.get("domain_queries", [])

    # Stage 2: Fetch
    def _fetch_round(web_qs: list[str], paper_qs: list[str]) -> Generator[ProgressEvent, None, None]:
        nonlocal sources
        total = len(web_qs) + len(paper_qs)
        yield ProgressEvent(
            phase="fetch",
            message=f"Fetching {len(web_qs)} web + {len(paper_qs)} paper queries...",
            current=0,
            total=total,
        )
        idx = 0
        for q in web_qs:
            idx += 1
            yield ProgressEvent(
                phase="fetch",
                message=f"Searching web: {q}",
                current=idx,
                total=total,
                item=f"web: {q[:50]}",
            )
            results = web_search(q, max_results=6, api_key=tavily_api_key)
            for r in results:
                r["query"] = q
                r["source_type"] = "web"
                sources.append(r)
        if paper_qs:
            yield ProgressEvent(
                phase="fetch",
                message=f"Searching {len(paper_qs)} paper queries (Semantic Scholar + scholarly + arXiv in parallel)...",
                current=idx,
                total=total,
            )
            # Semantic Scholar direct (existing path) + scholarly/arXiv (new) — all parallel
            from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed

            def _ss_query(q: str) -> list[dict]:
                results = paper_search(q, max_results=4, api_key=semantic_scholar_api_key)
                for r in results:
                    r["query"] = q
                    r["source_type"] = "paper"
                return results

            ss_futures_map: dict = {}
            academic_future = None
            with ThreadPoolExecutor(max_workers=len(paper_qs) + 1) as pool:
                for q in paper_qs:
                    ss_futures_map[pool.submit(_ss_query, q)] = q
                academic_future = pool.submit(
                    academic_search_parallel, paper_qs,
                    semantic_scholar_api_key=semantic_scholar_api_key,
                    alphaxiv_api_key=alphaxiv_api_key,
                )
                for f in _as_completed(list(ss_futures_map) + [academic_future]):
                    try:
                        sources.extend(f.result())
                    except Exception:
                        pass
            idx += len(paper_qs)
        # Fetch full text for top web results (first 5 unique URLs not yet fetched).
        seen_urls: set[str] = set()
        fetched = 0
        for s in sources:
            url = s.get("url")
            if not url or s.get("source_type") != "web":
                continue
            if s.get("full_text"):
                seen_urls.add(url)  # already fetched in a prior round
                continue
            if url not in seen_urls and fetched < 5:
                yield ProgressEvent(
                    phase="fetch_page",
                    message=f"Fetching page: {url[:60]}",
                    current=fetched + 1,
                    total=5,
                    item=url[:60],
                )
                s["full_text"] = fetch_page(url)
                seen_urls.add(url)
                fetched += 1

    yield from _fetch_round(all_queries, paper_queries)
    rounds += 1

    # Early-abort guard: if 0 sources after first round, warn and try one more
    if not sources:
        logger.warning(
            "Pipeline collected 0 sources after round 1. "
            "Web search may be failing silently."
        )

    # Stage 3: Gap evaluator (max 2 rounds)
    MAX_ROUNDS = 2
    while rounds < MAX_ROUNDS:
        yield ProgressEvent(
            phase="gap_eval",
            message=f"Evaluating coverage (round {rounds})...",
        )
        snippets_summary = "\n".join(
            f"[{i + 1}] {s.get('title', '?')} — {s.get('snippet', '')[:120]}"
            for i, s in enumerate(sources[:20])
        )
        gap_prompt = (
            _load_prompt("gap_evaluator")
            .replace("{topic}", topic)
            .replace("{snippet_count}", str(len(sources)))
            .replace("{snippets_summary}", snippets_summary)
        )
        try:
            gap_text = oc.call(gap_prompt, model=model_planner)
            gap = _parse_json(gap_text)
        except Exception:
            break
        if gap.get("sufficient", True):
            break
        additional = gap.get("additional_queries", [])
        if not additional:
            break
        yield from _fetch_round(additional, [])
        rounds += 1

    # Early-abort: truly no sources after all rounds
    if not sources:
        return {
            "topic": topic,
            "draft": "",
            "review": "",
            "sources": [],
            "rounds": rounds,
            "ok": False,
            "error": (
                "Pipeline collected 0 sources across all search rounds. "
                "Web search may be failing — check your Tavily API key and "
                "network connectivity."
            ),
        }

    # Deduplicate sources by URL
    seen: set[str] = set()
    unique_sources: list[dict] = []
    for s in sources:
        key = s.get("url") or s.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique_sources.append(s)
    sources = unique_sources[:30]

    # Stage 4: Writer
    yield ProgressEvent(
        phase="write",
        message=f"Synthesising {len(sources)} sources into draft...",
    )
    sources_text = "\n\n".join(
        f"[Source {i + 1}] {s.get('title', 'Untitled')}\n"
        f"URL: {s.get('url', '')}\n"
        f"{'Authors: ' + s.get('authors', '') + chr(10) if s.get('authors') else ''}"
        f"{s.get('full_text') or s.get('snippet', '')}"
        for i, s in enumerate(sources)
    )
    writer_prompt = (
        _load_prompt(writer_name)
        .replace("{topic}", topic)
        .replace("{source_count}", str(len(sources)))
        .replace("{sources}", sources_text)
    )
    try:
        draft = oc.call(writer_prompt, model=model_writer, timeout=600)
    except Exception as e:
        return {
            "topic": topic,
            "draft": "",
            "review": "",
            "sources": sources,
            "rounds": rounds,
            "ok": False,
            "error": f"Writer failed: {e}",
        }

    # Stage 5: Verifier
    yield ProgressEvent(phase="verify", message="Anchoring citations...")
    verifier_prompt = (
        _load_prompt("verifier")
        .replace("{draft}", draft)
        .replace("{sources}", sources_text)
    )
    try:
        verified_draft = oc.call(verifier_prompt, model=model_verifier, timeout=300)
    except Exception:
        verified_draft = draft

    # Quality guard: if the verifier returned something much shorter than the
    # original draft, it likely returned correction notes instead of the full
    # revised draft.  Fall back to the original draft in that case.
    MINIMUM_RATIO = 0.3
    if verified_draft and draft and len(verified_draft) < len(draft) * MINIMUM_RATIO:
        logger.warning(
            "Verifier output (%d chars) is less than %d%% of the original draft "
            "(%d chars) — likely returned correction notes instead of the full "
            "draft. Falling back to original draft.",
            len(verified_draft), int(MINIMUM_RATIO * 100), len(draft),
        )
        verified_draft = draft

    # Stage 6: Reviewer
    yield ProgressEvent(phase="review", message="Running adversarial review...")
    reviewer_prompt = _load_prompt("reviewer").replace("{draft}", verified_draft)
    try:
        review = oc.call(reviewer_prompt, model=model_reviewer, timeout=300)
    except Exception:
        review = "(Reviewer unavailable)"

    # Stage 7: Refiner — address review findings
    if review and review != "(Reviewer unavailable)":
        yield ProgressEvent(phase="refine", message="Refining draft based on review...")
        refiner_prompt = (
            _load_prompt("refiner")
            .replace("{draft}", verified_draft)
            .replace("{review}", review)
        )
        try:
            refined_draft = oc.call(refiner_prompt, model=model_writer, timeout=300)
            # Quality guard: if refiner output is suspiciously short, keep verified draft
            if refined_draft and verified_draft and len(refined_draft) < len(verified_draft) * 0.5:
                logger.warning(
                    "Refiner output (%d chars) is less than 50%% of verified draft "
                    "(%d chars) — likely returned only edits, not full draft. "
                    "Keeping verified draft.",
                    len(refined_draft), len(verified_draft),
                )
                refined_draft = verified_draft
        except Exception:
            logger.warning("Refiner call failed, keeping verified draft")
            refined_draft = verified_draft
    else:
        refined_draft = verified_draft

    return {
        "topic": topic,
        "draft": refined_draft,
        "review": review,
        "sources": sources,
        "rounds": rounds,
        "ok": True,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _run_with_tavily_fallback(
    topic: str,
    oc: OcClient,
    planner_name: str,
    writer_name: str,
    research_prefix: str,
    *,
    model_planner: str = "glm-5.1",
    model_writer: str = "minimax-m2.7",
    model_verifier: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
    tavily_api_key: str | None = None,
    semantic_scholar_api_key: str | None = None,
    alphaxiv_api_key: str | None = None,
    tavily_research_timeout: float = 600.0,
) -> Generator[ProgressEvent, None, dict]:
    """Tavily Research API primary path with manual pipeline fallback.

    Shared by run_deep and run_lit — both follow the identical pattern:
    1. Try Tavily Research API (replaces stages 1-5)
    2. If ok, return
    3. If quota exhausted, return error (manual fallback won't help)
    4. If Tavily failed, fall back to _run_pipeline
    5. If no Tavily key, go directly to _run_pipeline
    """
    if tavily_api_key:
        result = yield from _run_tavily_pipeline(
            topic, oc,
            tavily_api_key=tavily_api_key,
            tavily_model="pro",
            model_reviewer=model_reviewer,
            research_prefix=research_prefix,
            tavily_research_timeout=tavily_research_timeout,
            semantic_scholar_api_key=semantic_scholar_api_key,
            alphaxiv_api_key=alphaxiv_api_key,
        )
        if result.get("ok"):
            return result
        # Quota exhaustion — fallback won't help either (also uses Tavily)
        if "monthly free tier" in (result.get("error") or ""):
            return result
        # Other Tavily failures — try manual fallback
        if result.get("error", "").startswith("Tavily research"):
            err_detail = result.get("error", "")
            logger.warning(
                "Tavily research failed (%s), falling back to manual pipeline",
                err_detail,
            )
            yield ProgressEvent(
                phase="warning",
                message=f"Tavily failed ({err_detail[:120]}), falling back to manual search...",
            )
            result = yield from _run_pipeline(
                topic, oc, planner_name, writer_name,
                model_planner=model_planner, model_writer=model_writer,
                model_verifier=model_verifier, model_reviewer=model_reviewer,
                tavily_api_key=tavily_api_key,
                semantic_scholar_api_key=semantic_scholar_api_key,
                alphaxiv_api_key=alphaxiv_api_key,
            )
        return result

    # Fallback: manual pipeline (no Tavily key)
    result = yield from _run_pipeline(
        topic, oc, planner_name, writer_name,
        model_planner=model_planner, model_writer=model_writer,
        model_verifier=model_verifier, model_reviewer=model_reviewer,
        tavily_api_key=tavily_api_key,
        semantic_scholar_api_key=semantic_scholar_api_key,
        alphaxiv_api_key=alphaxiv_api_key,
    )
    return result


def run_deep(
    topic: str,
    oc: OcClient,
    *,
    model_planner: str = "glm-5.1",
    model_writer: str = "minimax-m2.7",
    model_verifier: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
    tavily_api_key: str | None = None,
    semantic_scholar_api_key: str | None = None,
    alphaxiv_api_key: str | None = None,
    tavily_research_timeout: float = 600.0,
) -> Generator[ProgressEvent, None, dict]:
    """Run the full deep research pipeline. Yields ProgressEvent, returns result dict."""
    return (yield from _run_with_tavily_fallback(
        topic, oc,
        planner_name="search_planner", writer_name="writer",
        research_prefix="Deep research: ",
        model_planner=model_planner, model_writer=model_writer,
        model_verifier=model_verifier, model_reviewer=model_reviewer,
        tavily_api_key=tavily_api_key,
        semantic_scholar_api_key=semantic_scholar_api_key,
        alphaxiv_api_key=alphaxiv_api_key,
        tavily_research_timeout=tavily_research_timeout,
    ))


def run_lit(
    topic: str,
    oc: OcClient,
    *,
    model_planner: str = "glm-5.1",
    model_writer: str = "minimax-m2.7",
    model_verifier: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
    tavily_api_key: str | None = None,
    semantic_scholar_api_key: str | None = None,
    alphaxiv_api_key: str | None = None,
    tavily_research_timeout: float = 600.0,
) -> Generator[ProgressEvent, None, dict]:
    """Run the literature review pipeline. Yields ProgressEvent, returns result dict."""
    return (yield from _run_with_tavily_fallback(
        topic, oc,
        planner_name="lit_planner", writer_name="lit_writer",
        research_prefix="Literature review: ",
        model_planner=model_planner, model_writer=model_writer,
        model_verifier=model_verifier, model_reviewer=model_reviewer,
        tavily_api_key=tavily_api_key,
        semantic_scholar_api_key=semantic_scholar_api_key,
        alphaxiv_api_key=alphaxiv_api_key,
        tavily_research_timeout=tavily_research_timeout,
    ))


def run_compare(
    artifact_a: str,
    artifact_b: str,
    oc: OcClient,
    *,
    model_researcher: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
) -> Generator[ProgressEvent, None, dict]:
    """Compare two artifacts side by side. Yields ProgressEvent, returns result dict."""
    yield ProgressEvent(phase="fetch", message=f"Fetching {artifact_a!r}...")
    content_a = _fetch_artifact(artifact_a)
    yield ProgressEvent(phase="fetch", message=f"Fetching {artifact_b!r}...")
    content_b = _fetch_artifact(artifact_b)

    yield ProgressEvent(phase="compare", message="Comparing artifacts...")
    compare_prompt = (
        _load_prompt("compare_researcher")
        .replace("{artifact_a}", artifact_a)
        .replace("{artifact_b}", artifact_b)
        .replace("{artifact_a_content}", content_a)
        .replace("{artifact_b_content}", content_b)
    )
    try:
        comparison = oc.call(compare_prompt, model=model_researcher, timeout=300)
    except Exception as e:
        return {"ok": False, "error": f"Compare failed: {e}", "comparison": "", "review": ""}

    yield ProgressEvent(phase="review", message="Running adversarial review...")
    reviewer_prompt = _load_prompt("reviewer").replace("{draft}", comparison)
    try:
        review = oc.call(reviewer_prompt, model=model_reviewer, timeout=300)
    except Exception:
        review = "(Reviewer unavailable)"

    return {"ok": True, "comparison": comparison, "review": review, "error": None}


def run_draft(
    topic: str,
    oc: OcClient,
    *,
    guide_context: str = "",
    model_writer: str = "minimax-m2.7",
) -> Generator[ProgressEvent, None, dict]:
    """Draft a paper section on a topic. Yields ProgressEvent, returns result dict."""
    yield ProgressEvent(phase="write", message=f"Drafting: {topic!r}...")
    guide_section = f"\n\n## Guide context\n{guide_context}" if guide_context else ""
    draft_prompt = (
        _load_prompt("draft_writer")
        .replace("{topic}", topic)
        .replace("{guide_context}", guide_section)
    )
    try:
        draft = oc.call(draft_prompt, model=model_writer, timeout=600)
    except Exception as e:
        return {"ok": False, "error": f"Draft failed: {e}", "draft": ""}

    return {"ok": True, "draft": draft, "error": None}


def run_replicate(
    artifact: str,
    oc: OcClient,
    *,
    model_researcher: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
) -> Generator[ProgressEvent, None, dict]:
    """Build a replication guide for a paper. Yields ProgressEvent, returns result dict."""
    yield ProgressEvent(phase="fetch", message=f"Fetching artifact: {artifact!r}...")
    content = _fetch_artifact(artifact)

    yield ProgressEvent(phase="analyze", message="Building replication guide...")
    replicate_prompt = (
        _load_prompt("replicate_researcher")
        .replace("{artifact}", artifact)
        .replace("{artifact_content}", content)
    )
    try:
        guide = oc.call(replicate_prompt, model=model_researcher, timeout=300)
    except Exception as e:
        return {"ok": False, "error": f"Replication analysis failed: {e}", "guide": "", "review": ""}

    yield ProgressEvent(phase="review", message="Reviewing replication guide...")
    reviewer_prompt = _load_prompt("reviewer").replace("{draft}", guide)
    try:
        review = oc.call(reviewer_prompt, model=model_reviewer, timeout=300)
    except Exception:
        review = "(Reviewer unavailable)"

    return {"ok": True, "guide": guide, "review": review, "error": None}


def run_audit(
    artifact: str,
    oc: OcClient,
    *,
    model_researcher: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
) -> Generator[ProgressEvent, None, dict]:
    """Audit a paper for methodology, validity, and reproducibility. Yields ProgressEvent, returns result dict."""
    yield ProgressEvent(phase="fetch", message=f"Fetching artifact: {artifact!r}...")
    content = _fetch_artifact(artifact)

    yield ProgressEvent(phase="audit", message="Running audit...")
    audit_prompt = (
        _load_prompt("audit_researcher")
        .replace("{artifact}", artifact)
        .replace("{artifact_content}", content)
    )
    try:
        report = oc.call(audit_prompt, model=model_researcher, timeout=300)
    except Exception as e:
        return {"ok": False, "error": f"Audit failed: {e}", "report": "", "review": ""}

    yield ProgressEvent(phase="review", message="Reviewing audit findings...")
    reviewer_prompt = _load_prompt("reviewer").replace("{draft}", report)
    try:
        review = oc.call(reviewer_prompt, model=model_reviewer, timeout=300)
    except Exception:
        review = "(Reviewer unavailable)"

    return {"ok": True, "report": report, "review": review, "error": None}


def run_review(
    artifact: str,
    oc: OcClient,
    *,
    model_researcher: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
) -> Generator[ProgressEvent, None, dict]:
    """Run the peer review pipeline. Yields ProgressEvent, returns result dict."""
    # Stage 1: Fetch artifact content
    yield ProgressEvent(phase="fetch", message=f"Fetching artifact: {artifact!r}...")
    artifact_content = _fetch_artifact(artifact)

    # Stage 2: Researcher
    yield ProgressEvent(phase="research", message="Gathering evidence...")
    researcher_prompt = (
        _load_prompt("review_researcher")
        .replace("{artifact}", artifact)
        .replace("{artifact_content}", artifact_content)
    )
    try:
        researcher_notes = oc.call(researcher_prompt, model=model_researcher, timeout=300)
    except Exception as e:
        return {
            "artifact": artifact,
            "artifact_content": artifact_content,
            "researcher_notes": "",
            "review": "",
            "ok": False,
            "error": f"Researcher failed: {e}",
        }

    # Stage 3: Reviewer
    yield ProgressEvent(phase="review", message="Running adversarial review...")
    combined = f"## Artifact\n\n{artifact_content}\n\n## Researcher Notes\n\n{researcher_notes}"
    reviewer_prompt = _load_prompt("reviewer").replace("{draft}", combined)
    try:
        review = oc.call(reviewer_prompt, model=model_reviewer, timeout=300)
    except Exception:
        review = "(Reviewer unavailable)"

    return {
        "artifact": artifact,
        "artifact_content": artifact_content,
        "researcher_notes": researcher_notes,
        "review": review,
        "ok": True,
        "error": None,
    }
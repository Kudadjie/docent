"""Six-stage deep research pipeline powered by OpenCode LLM calls."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from .oc_client import OcClient
from .search import fetch_page, paper_search, web_search

_AGENTS_DIR = Path(__file__).parent / "agents"


def _load_prompt(name: str) -> str:
    return (_AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _progress(
    on_progress: Callable[[str, str], None] | None, phase: str, message: str
) -> None:
    if on_progress is not None:
        on_progress(phase, message)


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


def _run_pipeline(
    topic: str,
    oc: OcClient,
    planner_name: str,
    writer_name: str,
    *,
    on_progress: Callable[[str, str], None] | None = None,
    model_planner: str = "glm-5.1",
    model_writer: str = "minimax-m2.7",
    model_verifier: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
    tavily_api_key: str | None = None,
) -> dict:
    """Shared search-fetch-write-verify-review pipeline."""
    sources: list[dict] = []
    rounds = 0

    # Stage 1: Search planner
    _progress(on_progress, "search_plan", "Generating search strategy...")
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
    def _fetch_round(web_qs: list[str], paper_qs: list[str]) -> None:
        nonlocal sources
        _progress(
            on_progress,
            "fetch",
            f"Fetching {len(web_qs)} web + {len(paper_qs)} paper queries...",
        )
        for q in web_qs:
            results = web_search(q, max_results=6, api_key=tavily_api_key)
            for r in results:
                r["query"] = q
                r["source_type"] = "web"
                sources.append(r)
        for q in paper_qs:
            results = paper_search(q, max_results=4)
            for r in results:
                r["query"] = q
                r["source_type"] = "paper"
                sources.append(r)
        # Fetch full text for top web results (first 5 unique URLs not yet fetched).
        # Sources with existing full_text are marked seen so their URL doesn't
        # count against the budget in a subsequent round either.
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
                s["full_text"] = fetch_page(url)
                seen_urls.add(url)
                fetched += 1

    _fetch_round(all_queries, paper_queries)
    rounds += 1

    # Stage 3: Gap evaluator (max 2 rounds)
    MAX_ROUNDS = 2
    while rounds < MAX_ROUNDS:
        _progress(on_progress, "gap_eval", f"Evaluating coverage (round {rounds})...")
        snippets_summary = "\n".join(
            f"[{i + 1}] {s.get('title', '?')} \u2014 {s.get('snippet', '')[:120]}"
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
        _fetch_round(additional, [])
        rounds += 1

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
    _progress(
        on_progress, "write", f"Synthesising {len(sources)} sources into draft..."
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
    _progress(on_progress, "verify", "Anchoring citations...")
    verifier_prompt = (
        _load_prompt("verifier")
        .replace("{draft}", draft)
        .replace("{sources}", sources_text)
    )
    try:
        verified_draft = oc.call(verifier_prompt, model=model_verifier, timeout=300)
    except Exception:
        verified_draft = draft

    # Stage 6: Reviewer
    _progress(on_progress, "review", "Running adversarial review...")
    reviewer_prompt = _load_prompt("reviewer").replace("{draft}", verified_draft)
    try:
        review = oc.call(reviewer_prompt, model=model_reviewer, timeout=300)
    except Exception:
        review = "(Reviewer unavailable)"

    return {
        "topic": topic,
        "draft": verified_draft,
        "review": review,
        "sources": sources,
        "rounds": rounds,
        "ok": True,
        "error": None,
    }


def run_deep(
    topic: str,
    oc: OcClient,
    *,
    on_progress: Callable[[str, str], None] | None = None,
    model_planner: str = "glm-5.1",
    model_writer: str = "minimax-m2.7",
    model_verifier: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
    tavily_api_key: str | None = None,
) -> dict:
    """Run the full deep research pipeline. Returns result dict."""
    return _run_pipeline(
        topic, oc, "search_planner", "writer",
        on_progress=on_progress,
        model_planner=model_planner, model_writer=model_writer,
        model_verifier=model_verifier, model_reviewer=model_reviewer,
        tavily_api_key=tavily_api_key,
    )


def run_lit(
    topic: str,
    oc: OcClient,
    *,
    on_progress: Callable[[str, str], None] | None = None,
    model_planner: str = "glm-5.1",
    model_writer: str = "minimax-m2.7",
    model_verifier: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
    tavily_api_key: str | None = None,
) -> dict:
    """Run the literature review pipeline. Returns result dict."""
    return _run_pipeline(
        topic, oc, "lit_planner", "lit_writer",
        on_progress=on_progress,
        model_planner=model_planner, model_writer=model_writer,
        model_verifier=model_verifier, model_reviewer=model_reviewer,
        tavily_api_key=tavily_api_key,
    )


def run_review(
    artifact: str,
    oc: OcClient,
    *,
    on_progress: Callable[[str, str], None] | None = None,
    model_researcher: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
) -> dict:
    """Run the peer review pipeline. Returns result dict."""
    # Stage 1: Fetch artifact content
    _progress(on_progress, "fetch", f"Fetching artifact: {artifact!r}...")
    artifact_content = _fetch_artifact(artifact)

    # Stage 2: Researcher
    _progress(on_progress, "research", "Gathering evidence...")
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
    _progress(on_progress, "review", "Running adversarial review...")
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
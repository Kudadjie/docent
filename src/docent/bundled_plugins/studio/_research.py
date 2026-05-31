"""Research workflow action mixins: deep-research, lit, review, compare, draft, replicate, audit."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from docent.bundled_plugins.studio.feynman import (
    FeynmanNotFoundError,
    _run_feynman,
    _summarize_feynman_error,
)
from docent.bundled_plugins.studio.helpers import (
    _append_references,
    _artifact_slug,
    _read_guide_files,
    _slugify,
)
from docent.bundled_plugins.studio.models import (
    AuditInputs,
    CompareInputs,
    DeepInputs,
    DraftInputs,
    LitInputs,
    ReplicateInputs,
    ResearchResult,
    ReviewInputs,
)
from docent.bundled_plugins.studio.preflights import (
    _preflight_docent,
    _preflight_oc_only,
    _route_output,
)
from docent.core import Context, ProgressEvent, action

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

    tasks = [lambda a=anchor: _fetch_one(a) for anchor in anchors]
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


class ResearchMixin:
    """Mixin providing research actions for StudioTool."""

    @action(
        description="Deep research on a topic.",
        input_schema=DeepInputs,
        preflight=_preflight_docent,
    )
    def deep_research(self, inputs: DeepInputs, context: Context):
        from .backend import DOCENT_BACKEND_NAMES

        if inputs.backend in DOCENT_BACKEND_NAMES:
            from .backend import get_backend
            from .pipeline import run_deep

            backend = get_backend(context.settings, override=inputs.backend)
            tavily_key = context.settings.research.tavily_api_key

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(inputs.topic) + "-deep"

            guide_ctx = _read_guide_files(inputs.guide_files)
            effective_topic = inputs.topic
            if guide_ctx:
                names = ", ".join(Path(p).name for p in inputs.guide_files)
                effective_topic = f"{inputs.topic}\n\n## Guide context ({names})\n{guide_ctx}"

            try:
                result_data = yield from run_deep(
                    effective_topic,
                    backend,
                    tavily_api_key=tavily_key,
                    semantic_scholar_api_key=context.settings.research.semantic_scholar_api_key,
                    alphaxiv_api_key=context.settings.research.alphaxiv_api_key,
                    tavily_research_timeout=context.settings.research.tavily_research_timeout,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="deep",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="deep",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=result_data.get("error") or "Pipeline failed.",
                )

            # Expand citations: parallel cite-graph on top anchor papers.
            cite_section = ""
            if inputs.expand_citations:
                yield ProgressEvent(
                    phase="expand_citations",
                    message="Expanding citation graph on anchor papers...",
                )
                try:
                    extra_sources, cite_section = _expand_citations(
                        result_data.get("sources", []),
                        context.settings.research.semantic_scholar_api_key,
                    )
                    if extra_sources:
                        result_data["sources"] = result_data.get("sources", []) + extra_sources
                        yield ProgressEvent(
                            phase="expand_citations",
                            message=f"Added {len(extra_sources)} open-access related paper(s) from citation graph.",
                        )
                        papers_text = "\n\n".join(
                            f"**{s['title']}** ({s.get('year', '?')})\n{s['snippet']}"
                            for s in extra_sources
                            if s.get("snippet")
                        )
                        if papers_text:
                            yield ProgressEvent(
                                phase="expand_citations",
                                message="Enriching draft with citation graph insights...",
                            )
                            try:
                                from .prompts import load_prompt as _load_prompt

                                enrich_prompt = (
                                    _load_prompt("citation_enricher")
                                    .replace("{draft}", result_data["draft"])
                                    .replace("{papers_text}", papers_text)
                                )
                                enriched = backend.call(enrich_prompt, role="writer", timeout=600)
                                if enriched and len(enriched) >= len(result_data["draft"]) * 0.5:
                                    result_data["draft"] = enriched
                                    cite_section = ""  # insights absorbed into draft
                            except Exception as _ee:
                                logger.warning("Citation enrichment call failed: %s", _ee)
                except Exception as _ce:
                    logger.warning("Citation expansion failed: %s", _ce)

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            sources_file = output_dir / f"{slug}-sources.json"

            draft_text = result_data["draft"]
            if cite_section:  # only appended when enrichment was skipped or failed
                draft_text = draft_text + "\n\n" + cite_section
            draft_with_refs = _append_references(draft_text, result_data.get("sources", []))
            out_file.write_text(draft_with_refs, encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")
            sources_file.write_text(
                json.dumps(result_data.get("sources", []), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            yield ProgressEvent(phase="done", message="Completed")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, sources_file, context, "deep-research"
            )
            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Deep research complete. {result_data['rounds']} search round(s), {len(result_data['sources'])} sources.{extra}",
            )

        # Free-tier branch
        if inputs.backend == "free":
            from .free_research import run_free_deep

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(inputs.topic) + "-deep-free"
            out_file = output_dir / f"{slug}.md"
            guide_ctx = _read_guide_files(inputs.guide_files)

            try:
                result_data = yield from run_free_deep(
                    inputs.topic,
                    guide_ctx,
                    tavily_key=context.settings.research.tavily_api_key,
                    ss_key=context.settings.research.semantic_scholar_api_key,
                    output_path=out_file,
                    via_mcp=context.via_mcp,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="free",
                    workflow="deep",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=f"Free-tier pipeline error: {e}",
                )

            sources_file = (
                Path(result_data.get("sources_file", ""))
                if result_data.get("sources_file")
                else None
            )
            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, sources_file, context, "deep-research"
            )
            return ResearchResult(
                ok=True,
                backend="free",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Free-tier deep research complete.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(
            phase="start",
            message=f"Starting Feynman deep research: {inputs.topic!r}",
        )
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        slug = _slugify(inputs.topic) + "-deep"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/deepresearch {inputs.topic}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd,
                cmd_args,
                workspace_dir,
                output_dir,
                slug,
                timeout=context.settings.research.feynman_timeout,
            )
        except FeynmanNotFoundError as e:
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=None,
                returncode=None,
                message=str(e),
            )

        if returncode != 0 or output_file is None:
            # Feynman sometimes exits 0 on credit/quota errors (no output written).
            # Treat "no output file" as a failure regardless of returncode.
            msg = _summarize_feynman_error(
                stderr_output, configured_model=context.settings.research.feynman_model
            )
            if output_file is None and returncode == 0:
                msg = (
                    "Feynman ran but produced no output file.\n"
                    "The actual error was likely printed above (streamed to stdout).\n"
                    "Common cause: exhausted API credits (Feynman may exit 0 on credit errors).\n\n"
                ) + msg
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=None,
                returncode=returncode,
                message=msg,
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "deep-research"
        )
        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="deep",
            topic_or_artifact=inputs.topic,
            output_file=output_file,
            returncode=returncode,
            notebook_id=notebook_id,
            vault_path=vault_path,
            message=f"Deep research completed for {inputs.topic!r}.{extra}",
        )

    @action(
        description="Literature review on a topic.",
        input_schema=LitInputs,
        preflight=_preflight_docent,
    )
    def lit(self, inputs: LitInputs, context: Context):
        from .backend import DOCENT_BACKEND_NAMES

        if inputs.backend in DOCENT_BACKEND_NAMES:
            from .backend import get_backend
            from .pipeline import run_lit

            backend = get_backend(context.settings, override=inputs.backend)
            tavily_key = context.settings.research.tavily_api_key

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(inputs.topic) + "-lit"

            guide_ctx = _read_guide_files(inputs.guide_files)
            effective_topic = inputs.topic
            if guide_ctx:
                names = ", ".join(Path(p).name for p in inputs.guide_files)
                effective_topic = f"{inputs.topic}\n\n## Guide context ({names})\n{guide_ctx}"

            try:
                result_data = yield from run_lit(
                    effective_topic,
                    backend,
                    tavily_api_key=tavily_key,
                    semantic_scholar_api_key=context.settings.research.semantic_scholar_api_key,
                    alphaxiv_api_key=context.settings.research.alphaxiv_api_key,
                    tavily_research_timeout=context.settings.research.tavily_research_timeout,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="lit",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="lit",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=result_data.get("error") or "Pipeline failed.",
                )

            # Expand citations: parallel cite-graph on top anchor papers.
            cite_section = ""
            if inputs.expand_citations:
                yield ProgressEvent(
                    phase="expand_citations",
                    message="Expanding citation graph on anchor papers...",
                )
                try:
                    extra_sources, cite_section = _expand_citations(
                        result_data.get("sources", []),
                        context.settings.research.semantic_scholar_api_key,
                    )
                    if extra_sources:
                        result_data["sources"] = result_data.get("sources", []) + extra_sources
                        yield ProgressEvent(
                            phase="expand_citations",
                            message=f"Added {len(extra_sources)} open-access related paper(s) from citation graph.",
                        )
                        papers_text = "\n\n".join(
                            f"**{s['title']}** ({s.get('year', '?')})\n{s['snippet']}"
                            for s in extra_sources
                            if s.get("snippet")
                        )
                        if papers_text:
                            yield ProgressEvent(
                                phase="expand_citations",
                                message="Enriching draft with citation graph insights...",
                            )
                            try:
                                from .prompts import load_prompt as _load_prompt

                                enrich_prompt = (
                                    _load_prompt("citation_enricher")
                                    .replace("{draft}", result_data["draft"])
                                    .replace("{papers_text}", papers_text)
                                )
                                enriched = backend.call(enrich_prompt, role="writer", timeout=600)
                                if enriched and len(enriched) >= len(result_data["draft"]) * 0.5:
                                    result_data["draft"] = enriched
                                    cite_section = ""  # insights absorbed into draft
                            except Exception as _ee:
                                logger.warning("Citation enrichment call failed: %s", _ee)
                except Exception as _ce:
                    logger.warning("Citation expansion failed: %s", _ce)

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            sources_file = output_dir / f"{slug}-sources.json"

            draft_text = result_data["draft"]
            if cite_section:  # only appended when enrichment was skipped or failed
                draft_text = draft_text + "\n\n" + cite_section
            draft_with_refs = _append_references(draft_text, result_data.get("sources", []))
            out_file.write_text(draft_with_refs, encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")
            sources_file.write_text(
                json.dumps(result_data.get("sources", []), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            yield ProgressEvent(phase="done", message="Completed")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, sources_file, context, "lit"
            )
            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Literature review complete. {result_data['rounds']} search round(s), {len(result_data['sources'])} sources.{extra}",
            )

        # Free-tier branch
        if inputs.backend == "free":
            from .free_research import run_free_lit

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(inputs.topic) + "-lit-free"
            out_file = output_dir / f"{slug}.md"
            guide_ctx = _read_guide_files(inputs.guide_files)

            try:
                result_data = yield from run_free_lit(
                    inputs.topic,
                    guide_ctx,
                    ss_key=context.settings.research.semantic_scholar_api_key,
                    output_path=out_file,
                    via_mcp=context.via_mcp,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="free",
                    workflow="lit",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=f"Free-tier pipeline error: {e}",
                )

            sources_file = (
                Path(result_data.get("sources_file", ""))
                if result_data.get("sources_file")
                else None
            )
            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, sources_file, context, "lit"
            )
            return ResearchResult(
                ok=True,
                backend="free",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Free-tier literature review complete.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(
            phase="start",
            message=f"Starting Feynman literature review: {inputs.topic!r}",
        )
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        slug = _slugify(inputs.topic) + "-lit"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/lit {inputs.topic}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd,
                cmd_args,
                workspace_dir,
                output_dir,
                slug,
                timeout=context.settings.research.feynman_timeout,
            )
        except FeynmanNotFoundError as e:
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=None,
                returncode=None,
                message=str(e),
            )

        if returncode != 0 or output_file is None:
            msg = _summarize_feynman_error(
                stderr_output, configured_model=context.settings.research.feynman_model
            )
            if output_file is None and returncode == 0:
                msg = (
                    "Feynman ran but produced no output file.\n"
                    "The actual error was likely printed above (streamed to stdout).\n"
                    "Common cause: exhausted API credits (Feynman may exit 0 on credit errors).\n\n"
                ) + msg
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=None,
                returncode=returncode,
                message=msg,
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "lit"
        )
        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="lit",
            topic_or_artifact=inputs.topic,
            output_file=output_file,
            returncode=returncode,
            notebook_id=notebook_id,
            vault_path=vault_path,
            message=f"Literature review completed for {inputs.topic!r}.{extra}",
        )

    @action(
        description="Peer review of an artifact (arXiv ID, PDF path, or URL).",
        input_schema=ReviewInputs,
        preflight=_preflight_oc_only,
    )
    def review(self, inputs: ReviewInputs, context: Context):
        from .backend import DOCENT_BACKEND_NAMES

        if inputs.backend in DOCENT_BACKEND_NAMES:
            from .backend import get_backend
            from .pipeline import run_review

            backend = get_backend(context.settings, override=inputs.backend)

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(_artifact_slug(inputs.artifact)) + "-review"

            try:
                result_data = yield from run_review(inputs.artifact, backend)
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="review",
                    topic_or_artifact=inputs.artifact,
                    output_file=None,
                    returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="review",
                    topic_or_artifact=inputs.artifact,
                    output_file=None,
                    returncode=None,
                    message=result_data.get("error") or "Review failed.",
                )

            out_file = output_dir / f"{slug}.md"
            out_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message="Completed")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "review"
            )
            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="review",
                topic_or_artifact=inputs.artifact,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Peer review complete for {inputs.artifact!r}.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(
            phase="start",
            message=f"Starting Feynman review: {inputs.artifact!r}",
        )
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        slug = _slugify(_artifact_slug(inputs.artifact)) + "-review"
        cmd_args = ["--prompt", f"/review {inputs.artifact}"]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd,
                cmd_args,
                workspace_dir,
                output_dir,
                slug,
                timeout=context.settings.research.feynman_timeout,
            )
        except FeynmanNotFoundError as e:
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="review",
                topic_or_artifact=inputs.artifact,
                output_file=None,
                returncode=None,
                message=str(e),
            )

        if returncode != 0 or output_file is None:
            msg = _summarize_feynman_error(
                stderr_output, configured_model=context.settings.research.feynman_model
            )
            if output_file is None and returncode == 0:
                msg = (
                    "Feynman ran but produced no output file.\n"
                    "The actual error was likely printed above (streamed to stdout).\n"
                    "Common cause: exhausted API credits (Feynman may exit 0 on credit errors).\n\n"
                ) + msg
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="review",
                topic_or_artifact=inputs.artifact,
                output_file=None,
                returncode=returncode,
                message=msg,
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "review"
        )
        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="review",
            topic_or_artifact=inputs.artifact,
            output_file=output_file,
            returncode=returncode,
            notebook_id=notebook_id,
            vault_path=vault_path,
            message=f"Review completed for {inputs.artifact!r}.{extra}",
        )

    @action(
        description="Compare two research artifacts (arXiv IDs, PDFs, or URLs) side by side.",
        input_schema=CompareInputs,
        preflight=_preflight_oc_only,
    )
    def compare(self, inputs: CompareInputs, context: Context):
        topic_label = f"{inputs.artifact_a} vs {inputs.artifact_b}"
        slug = (
            _slugify(_artifact_slug(inputs.artifact_a) + "-vs-" + _artifact_slug(inputs.artifact_b))
            + "-compare"
        )

        from .backend import DOCENT_BACKEND_NAMES

        if inputs.backend in DOCENT_BACKEND_NAMES:
            from .backend import get_backend
            from .pipeline import run_compare

            backend = get_backend(context.settings, override=inputs.backend)
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                result_data = yield from run_compare(
                    inputs.artifact_a,
                    inputs.artifact_b,
                    backend,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="compare",
                    topic_or_artifact=topic_label,
                    output_file=None,
                    returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="compare",
                    topic_or_artifact=topic_label,
                    output_file=None,
                    returncode=None,
                    message=result_data.get("error") or "Compare failed.",
                )

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            out_file.write_text(result_data["comparison"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message="Completed")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "compare"
            )
            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="compare",
                topic_or_artifact=topic_label,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Comparison complete.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(phase="start", message=f"Starting Feynman compare: {topic_label!r}")
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/compare {inputs.artifact_a} {inputs.artifact_b}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd,
                cmd_args,
                workspace_dir,
                output_dir,
                slug,
                timeout=context.settings.research.feynman_timeout,
            )
        except FeynmanNotFoundError as e:
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="compare",
                topic_or_artifact=topic_label,
                output_file=None,
                returncode=None,
                message=str(e),
            )

        if returncode != 0 or output_file is None:
            msg = _summarize_feynman_error(
                stderr_output, configured_model=context.settings.research.feynman_model
            )
            if output_file is None and returncode == 0:
                msg = (
                    "Feynman ran but produced no output file.\n"
                    "The actual error was likely printed above (streamed to stdout).\n"
                    "Common cause: exhausted API credits (Feynman may exit 0 on credit errors).\n\n"
                ) + msg
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="compare",
                topic_or_artifact=topic_label,
                output_file=None,
                returncode=returncode,
                message=msg,
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "compare"
        )
        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="compare",
            topic_or_artifact=topic_label,
            output_file=output_file,
            returncode=returncode,
            notebook_id=notebook_id,
            vault_path=vault_path,
            message=f"Compare completed for {topic_label!r}.{extra}",
        )

    @action(
        description="Draft a paper section or document on a topic.",
        input_schema=DraftInputs,
        preflight=_preflight_oc_only,
    )
    def draft(self, inputs: DraftInputs, context: Context):
        slug = _slugify(inputs.topic) + "-draft"

        from .backend import DOCENT_BACKEND_NAMES

        if inputs.backend in DOCENT_BACKEND_NAMES:
            from .backend import get_backend
            from .pipeline import run_draft

            backend = get_backend(context.settings, override=inputs.backend)
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            guide_ctx = _read_guide_files(inputs.guide_files)

            try:
                result_data = yield from run_draft(
                    inputs.topic,
                    backend,
                    guide_context=guide_ctx,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="draft",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="draft",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=result_data.get("error") or "Draft failed.",
                )

            out_file = output_dir / f"{slug}.md"
            out_file.write_text(result_data["draft"], encoding="utf-8")

            yield ProgressEvent(phase="done", message="Completed")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "draft"
            )
            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="draft",
                topic_or_artifact=inputs.topic,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Draft complete.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(phase="start", message=f"Starting Feynman draft: {inputs.topic!r}")
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/draft {inputs.topic}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd,
                cmd_args,
                workspace_dir,
                output_dir,
                slug,
                timeout=context.settings.research.feynman_timeout,
            )
        except FeynmanNotFoundError as e:
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="draft",
                topic_or_artifact=inputs.topic,
                output_file=None,
                returncode=None,
                message=str(e),
            )

        if returncode != 0 or output_file is None:
            msg = _summarize_feynman_error(
                stderr_output, configured_model=context.settings.research.feynman_model
            )
            if output_file is None and returncode == 0:
                msg = (
                    "Feynman ran but produced no output file.\n"
                    "The actual error was likely printed above (streamed to stdout).\n"
                    "Common cause: exhausted API credits (Feynman may exit 0 on credit errors).\n\n"
                ) + msg
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="draft",
                topic_or_artifact=inputs.topic,
                output_file=None,
                returncode=returncode,
                message=msg,
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "draft"
        )
        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="draft",
            topic_or_artifact=inputs.topic,
            output_file=output_file,
            returncode=returncode,
            notebook_id=notebook_id,
            vault_path=vault_path,
            message=f"Draft completed for {inputs.topic!r}.{extra}",
        )

    @action(
        description="Build a replication guide for a paper (arXiv ID, PDF, or URL).",
        input_schema=ReplicateInputs,
        preflight=_preflight_oc_only,
    )
    def replicate(self, inputs: ReplicateInputs, context: Context):
        slug = _slugify(_artifact_slug(inputs.artifact)) + "-replicate"

        from .backend import DOCENT_BACKEND_NAMES

        if inputs.backend in DOCENT_BACKEND_NAMES:
            from .backend import get_backend
            from .pipeline import run_replicate

            backend = get_backend(context.settings, override=inputs.backend)
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                result_data = yield from run_replicate(inputs.artifact, backend)
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="replicate",
                    topic_or_artifact=inputs.artifact,
                    output_file=None,
                    returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="replicate",
                    topic_or_artifact=inputs.artifact,
                    output_file=None,
                    returncode=None,
                    message=result_data.get("error") or "Replication analysis failed.",
                )

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            out_file.write_text(result_data["guide"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message="Completed")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "replicate"
            )
            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="replicate",
                topic_or_artifact=inputs.artifact,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Replication guide complete.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(
            phase="start", message=f"Starting Feynman replicate: {inputs.artifact!r}"
        )
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/replicate {inputs.artifact}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd,
                cmd_args,
                workspace_dir,
                output_dir,
                slug,
                timeout=context.settings.research.feynman_timeout,
            )
        except FeynmanNotFoundError as e:
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="replicate",
                topic_or_artifact=inputs.artifact,
                output_file=None,
                returncode=None,
                message=str(e),
            )

        if returncode != 0 or output_file is None:
            msg = _summarize_feynman_error(
                stderr_output, configured_model=context.settings.research.feynman_model
            )
            if output_file is None and returncode == 0:
                msg = (
                    "Feynman ran but produced no output file.\n"
                    "The actual error was likely printed above (streamed to stdout).\n"
                    "Common cause: exhausted API credits (Feynman may exit 0 on credit errors).\n\n"
                ) + msg
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="replicate",
                topic_or_artifact=inputs.artifact,
                output_file=None,
                returncode=returncode,
                message=msg,
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "replicate"
        )
        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="replicate",
            topic_or_artifact=inputs.artifact,
            output_file=output_file,
            returncode=returncode,
            notebook_id=notebook_id,
            vault_path=vault_path,
            message=f"Replicate completed for {inputs.artifact!r}.{extra}",
        )

    @action(
        description="Audit a paper (arXiv ID, PDF, or URL) for methodology, claim validity, and reproducibility.",
        input_schema=AuditInputs,
        preflight=_preflight_oc_only,
    )
    def audit(self, inputs: AuditInputs, context: Context):
        slug = _slugify(_artifact_slug(inputs.artifact)) + "-audit"

        from .backend import DOCENT_BACKEND_NAMES

        if inputs.backend in DOCENT_BACKEND_NAMES:
            from .backend import get_backend
            from .pipeline import run_audit

            backend = get_backend(context.settings, override=inputs.backend)
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                result_data = yield from run_audit(inputs.artifact, backend)
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="audit",
                    topic_or_artifact=inputs.artifact,
                    output_file=None,
                    returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="audit",
                    topic_or_artifact=inputs.artifact,
                    output_file=None,
                    returncode=None,
                    message=result_data.get("error") or "Audit failed.",
                )

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            out_file.write_text(result_data["report"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message="Completed")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "audit"
            )
            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="audit",
                topic_or_artifact=inputs.artifact,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Audit complete.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(phase="start", message=f"Starting Feynman audit: {inputs.artifact!r}")
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/audit {inputs.artifact}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd,
                cmd_args,
                workspace_dir,
                output_dir,
                slug,
                timeout=context.settings.research.feynman_timeout,
            )
        except FeynmanNotFoundError as e:
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="audit",
                topic_or_artifact=inputs.artifact,
                output_file=None,
                returncode=None,
                message=str(e),
            )

        if returncode != 0 or output_file is None:
            msg = _summarize_feynman_error(
                stderr_output, configured_model=context.settings.research.feynman_model
            )
            if output_file is None and returncode == 0:
                msg = (
                    "Feynman ran but produced no output file.\n"
                    "The actual error was likely printed above (streamed to stdout).\n"
                    "Common cause: exhausted API credits (Feynman may exit 0 on credit errors).\n\n"
                ) + msg
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="audit",
                topic_or_artifact=inputs.artifact,
                output_file=None,
                returncode=returncode,
                message=msg,
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "audit"
        )
        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="audit",
            topic_or_artifact=inputs.artifact,
            output_file=output_file,
            returncode=returncode,
            notebook_id=notebook_id,
            vault_path=vault_path,
            message=f"Audit completed for {inputs.artifact!r}.{extra}",
        )

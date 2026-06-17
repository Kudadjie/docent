"""Core research actions: deep-research and lit.

Split out of _research.py; composed back into ResearchMixin there.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from docent.bundled_plugins.studio.feynman import (
    FeynmanNotFoundError,
    _summarize_feynman_error,
)
from docent.bundled_plugins.studio.helpers import (
    _append_references,
    _read_guide_files,
    _slugify,
)
from docent.bundled_plugins.studio.models import (
    DeepInputs,
    LitInputs,
    ResearchResult,
)
from docent.bundled_plugins.studio.preflights import (
    _preflight_docent,
    _route_output,
)
from docent.core import Context, ProgressEvent, action

logger = logging.getLogger(__name__)

from ._research_helpers import (  # noqa: E402, F401
    _expand_citations,
    _extract_anchor_ids,
)


def _run_feynman(*args, **kwargs):
    """Delegate through the _research facade at call time.

    Tests patch ``docent.bundled_plugins.studio._research._run_feynman``; the
    action bodies live here, so a direct import would bypass those patches
    (and run the real Feynman CLI). Resolving through the facade keeps the
    single historical patch point working.
    """
    from docent.bundled_plugins.studio import _research

    return _research._run_feynman(*args, **kwargs)


class ResearchCoreActions:
    """deep-research and lit actions (mixed into StudioTool via ResearchMixin)."""

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
            sources_file: Path | None = output_dir / f"{slug}-sources.json"

            draft_text = result_data["draft"]
            if cite_section:  # only appended when enrichment was skipped or failed
                draft_text = draft_text + "\n\n" + cite_section
            draft_with_refs = _append_references(draft_text, result_data.get("sources", []))
            out_file.write_text(draft_with_refs, encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")
            assert sources_file is not None
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
            sources_file_lit: Path | None = output_dir / f"{slug}-sources.json"

            draft_text = result_data["draft"]
            if cite_section:  # only appended when enrichment was skipped or failed
                draft_text = draft_text + "\n\n" + cite_section
            draft_with_refs = _append_references(draft_text, result_data.get("sources", []))
            out_file.write_text(draft_with_refs, encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")
            assert sources_file_lit is not None
            sources_file_lit.write_text(
                json.dumps(result_data.get("sources", []), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            yield ProgressEvent(phase="done", message="Completed")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, sources_file_lit, context, "lit"
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

"""Research tool: run deep research, literature reviews, and peer reviews via Feynman."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from docent.config import write_setting
from docent.core import Context, ProgressEvent, Tool, action, register_tool

from ._notebook import _nlm_push, _rank_sources, _find_sources_path, ToNotebookInputs, ToNotebookResult  # noqa: F401
from .feynman import (
    FeynmanBudgetExceededError,
    FeynmanNotFoundError,
    _extract_feynman_cost,  # noqa: F401 — re-exported for tests
    _find_feynman,
    _feynman_version_from_package_json,
    _read_daily_spend,
    _run_feynman,
    _summarize_feynman_error,
    _write_daily_spend,  # noqa: F401 — re-exported for tests
)
from .helpers import (
    _append_references,
    _artifact_slug,
    _build_references_section,  # noqa: F401 — re-exported for tests
    _read_guide_files,
    _slugify,
    _strip_references_section,  # noqa: F401 — re-exported for tests
)
from .models import (
    AuditInputs,
    CompareInputs,
    ConfigSetInputs,
    ConfigSetResult,
    ConfigShowInputs,
    ConfigShowResult,
    DeepInputs,
    DraftInputs,
    GetPaperInputs,
    GetPaperResult,
    LitInputs,
    ReplicateInputs,
    ResearchResult,
    ReviewInputs,
    ScholarlySearchInputs,
    ScholarlySearchResult,
    SearchPapersInputs,
    SearchPapersResult,
    ToLocalInputs,
    ToLocalResult,
    UsageInputs,
    UsageResult,
)
from .preflights import (  # noqa: F401
    _preflight_docent,
    _preflight_oc_only,
    _preflight_to_notebook,
    _resolve_tavily_key,
    _route_output,
    _write_to_vault,
)


_KNOWN_RESEARCH_KEYS = {
    "output_dir",
    "feynman_budget_usd",
    "feynman_model",
    "feynman_timeout",
    "oc_provider",
    "oc_model_planner",
    "oc_model_writer",
    "oc_model_verifier",
    "oc_model_reviewer",
    "oc_model_researcher",
    "oc_budget_usd",
    "tavily_api_key",
    "tavily_research_timeout",
    "semantic_scholar_api_key",
    "notebooklm_notebook_id",
    "notebooklm_source_limit",
    "obsidian_vault",
    "alphaxiv_api_key",
}


@register_tool
class StudioTool(Tool):
    """Run research workflows (deep research, literature review, peer review) via Feynman."""

    name = "studio"
    description = "Run research workflows (deep research, literature review, peer review) via Feynman."
    category = "studio"

    @action(
        description="Deep research on a topic.",
        input_schema=DeepInputs,
        preflight=_preflight_docent,
    )
    def deep_research(self, inputs: DeepInputs, context: Context):
        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_deep

            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            tavily_key = context.settings.research.tavily_api_key

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(inputs.topic) + "-deep"

            guide_ctx = _read_guide_files(inputs.guide_files)
            effective_topic = inputs.topic
            if guide_ctx:
                names = ", ".join(Path(p).name for p in inputs.guide_files)
                effective_topic = (
                    f"{inputs.topic}\n\n"
                    f"## Guide context ({names})\n{guide_ctx}"
                )

            try:
                result_data = yield from run_deep(
                    effective_topic, oc,
                    model_planner=context.settings.research.oc_model_planner,
                    model_writer=context.settings.research.oc_model_writer,
                    model_verifier=context.settings.research.oc_model_verifier,
                    model_reviewer=context.settings.research.oc_model_reviewer,
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

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            sources_file = output_dir / f"{slug}-sources.json"

            draft_with_refs = _append_references(
                result_data["draft"], result_data.get("sources", [])
            )
            out_file.write_text(draft_with_refs, encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")
            sources_file.write_text(
                json.dumps(result_data.get("sources", []), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            yield ProgressEvent(
                phase="done", message=f"Output written to {out_file}"
            )

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
                    ok=False, backend="free", workflow="deep",
                    topic_or_artifact=inputs.topic, output_file=None,
                    returncode=None, message=f"Free-tier pipeline error: {e}",
                )

            sources_file = Path(result_data.get("sources_file", "")) if result_data.get("sources_file") else None
            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, sources_file, context, "deep-research"
            )
            return ResearchResult(
                ok=True, backend="free", workflow="deep",
                topic_or_artifact=inputs.topic, output_file=str(out_file),
                returncode=0, notebook_id=notebook_id, vault_path=vault_path,
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
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="deep",
                topic_or_artifact=inputs.topic, output_file=None, returncode=None,
                message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=output_file,
                returncode=returncode,
                message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True,
                backend="feynman",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=None,
                returncode=returncode,
                message=f"Deep research completed for {inputs.topic!r}, but no output file was found.",
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
        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_lit

            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            tavily_key = context.settings.research.tavily_api_key

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(inputs.topic) + "-lit"

            guide_ctx = _read_guide_files(inputs.guide_files)
            effective_topic = inputs.topic
            if guide_ctx:
                names = ", ".join(Path(p).name for p in inputs.guide_files)
                effective_topic = (
                    f"{inputs.topic}\n\n"
                    f"## Guide context ({names})\n{guide_ctx}"
                )

            try:
                result_data = yield from run_lit(
                    effective_topic, oc,
                    model_planner=context.settings.research.oc_model_planner,
                    model_writer=context.settings.research.oc_model_writer,
                    model_verifier=context.settings.research.oc_model_verifier,
                    model_reviewer=context.settings.research.oc_model_reviewer,
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

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            sources_file = output_dir / f"{slug}-sources.json"

            draft_with_refs = _append_references(
                result_data["draft"], result_data.get("sources", [])
            )
            out_file.write_text(draft_with_refs, encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")
            sources_file.write_text(
                json.dumps(result_data.get("sources", []), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

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
                    ok=False, backend="free", workflow="lit",
                    topic_or_artifact=inputs.topic, output_file=None,
                    returncode=None, message=f"Free-tier pipeline error: {e}",
                )

            sources_file = Path(result_data.get("sources_file", "")) if result_data.get("sources_file") else None
            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, sources_file, context, "lit"
            )
            return ResearchResult(
                ok=True, backend="free", workflow="lit",
                topic_or_artifact=inputs.topic, output_file=str(out_file),
                returncode=0, notebook_id=notebook_id, vault_path=vault_path,
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
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="lit",
                topic_or_artifact=inputs.topic, output_file=None, returncode=None,
                message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=output_file,
                returncode=returncode,
                message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True,
                backend="feynman",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=None,
                returncode=returncode,
                message=f"Literature review completed for {inputs.topic!r}, but no output file was found.",
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
        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_review

            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(_artifact_slug(inputs.artifact)) + "-review"

            try:
                result_data = yield from run_review(
                    inputs.artifact, oc,
                    model_researcher=context.settings.research.oc_model_researcher,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                )
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

            yield ProgressEvent(phase="done", message=f"Review written to {out_file}")

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
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="review",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="review",
                topic_or_artifact=inputs.artifact,
                output_file=output_file,
                returncode=returncode,
                message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True,
                backend="feynman",
                workflow="review",
                topic_or_artifact=inputs.artifact,
                output_file=None,
                returncode=returncode,
                message=f"Review completed for {inputs.artifact!r}, but no output file was found.",
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
        description=(
            "Populate a new or existing NotebookLM notebook with research sources, then run "
            "the full quality pipeline: NLM web research arm, source stabilisation, quality "
            "gate (validation + contradictions + gap-fill), and 3-perspective summaries "
            "(practitioner / skeptic / beginner). Mirrors the research-to-notebook skill. "
            "Falls back to local package export + browser open if NLM is unavailable."
        ),
        input_schema=ToNotebookInputs,
        name="to-notebook",
        preflight=_preflight_to_notebook,
    )
    def to_notebook(self, inputs: ToNotebookInputs, context: Context):
        output_dir = context.settings.research.output_dir.expanduser()

        # Preflight has already resolved output_file; just build the Path.
        out_path = Path(inputs.output_file)
        if not out_path.is_absolute():
            out_path = output_dir / inputs.output_file

        # Extra synthesis docs selected by the multi-file picker
        extra_synthesis_docs: list[Path] = []
        for extra_str in (inputs.output_files or []):
            ep = Path(extra_str)
            if not ep.is_absolute():
                ep = output_dir / extra_str
            if ep.exists():
                extra_synthesis_docs.append(ep)

        stem = out_path.stem
        if inputs.sources_file:
            _explicit_src = Path(inputs.sources_file)
            if not _explicit_src.is_absolute():
                _explicit_src = output_dir / inputs.sources_file
            sources_path = _explicit_src
        else:
            sources_path = _find_sources_path(out_path) or (out_path.parent / f"{stem}-sources.json")

        has_sources = sources_path.exists()

        # Merge sources JSON from extra files (multi-file picker "all" case)
        extra_sources_raw: list[dict] = []
        for extra_doc in extra_synthesis_docs:
            extra_src = _find_sources_path(extra_doc)
            if extra_src and extra_src.exists():
                try:
                    extra_sources_raw.extend(
                        json.loads(extra_src.read_text(encoding="utf-8"))
                    )
                except (json.JSONDecodeError, OSError):
                    pass

        primary_raw = (
            json.loads(sources_path.read_text(encoding="utf-8")) if has_sources else []
        )
        all_raw = primary_raw + extra_sources_raw
        selected = _rank_sources(all_raw, inputs.max_sources) if all_raw else []

        # Write merged sources to a combined sources file for the package
        if extra_sources_raw and all_raw:
            merged_src_path = out_path.parent / f"{stem}-combined-sources.json"
            merged_src_path.write_text(
                json.dumps(all_raw, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            sources_path = merged_src_path
            has_sources = True

        package_dir = out_path.parent / f"{stem}-notebook"
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "sources_urls.txt").write_text(
            "\n".join(s["url"] for s in selected if s.get("url")),
            encoding="utf-8",
        )
        shutil.copy2(out_path, package_dir / out_path.name)
        yield ProgressEvent(phase="package", message=f"Local package written to {package_dir}")

        if inputs.notebook_id:
            context.settings.research.notebooklm_notebook_id = inputs.notebook_id

        nlm = yield from _nlm_push(
            out_path=out_path,
            sources_path=sources_path if has_sources else None,
            context=context,
            max_sources=inputs.max_sources,
            topic=inputs.topic,
            guide_files=[Path(p).expanduser() for p in inputs.guide_files],
            extra_synthesis_docs=extra_synthesis_docs or None,
            run_nlm_research=inputs.run_nlm_research,
            run_quality_gate=inputs.run_quality_gate,
            run_perspectives=inputs.run_perspectives,
        )

        sources_file_str = str(sources_path) if has_sources else None

        # ── Write quality report to package dir ───────────────────────────────
        qg = nlm.get("quality_gate")
        persp = nlm.get("perspectives")
        if qg or persp:
            report_parts: list[str] = ["# Docent Studio — Quality Report\n"]
            if qg and qg.get("raw"):
                report_parts.append(qg["raw"])
            if persp:
                report_parts.append("\n## Perspectives\n")
                for key, label in (
                    ("practitioner", "Practitioner"),
                    ("skeptic", "Skeptic"),
                    ("beginner", "Beginner"),
                ):
                    if persp.get(key):
                        report_parts.append(f"### {label}\n\n{persp[key]}\n")
            report_path = package_dir / "quality-report.md"
            report_path.write_text("\n".join(report_parts), encoding="utf-8")
            yield ProgressEvent(
                phase="package", message=f"Quality report: {report_path}"
            )

        if not nlm["ok"]:
            import webbrowser
            webbrowser.open("https://notebooklm.google.com")
            return ToNotebookResult(
                ok=True,
                output_file=str(out_path), sources_file=sources_file_str,
                package_dir=str(package_dir), sources_count=len(selected),
                sources_added=0, sources_failed=0,
                message=f"{nlm['message']} -- opened browser. Local package at {package_dir}.",
            )

        nb_id = nlm["notebook_id"]
        save_hint = ""
        if nb_id and nb_id != context.settings.research.notebooklm_notebook_id:
            save_hint = f" Save with: docent studio config-set --key notebooklm_notebook_id --value {nb_id}"

        return ToNotebookResult(
            ok=True,
            output_file=str(out_path),
            sources_file=sources_file_str,
            package_dir=str(package_dir),
            sources_count=len(selected),
            sources_added=nlm["sources_added"],
            sources_failed=nlm["sources_failed"],
            sources_from_feynman=nlm["sources_from_feynman"],
            sources_from_nlm=nlm["sources_from_nlm"],
            notebook_id=nb_id,
            quality_gate=nlm["quality_gate"],
            perspectives=nlm["perspectives"],
            message=nlm["message"] + save_hint,
        )

    @action(
        description=(
            "Package an existing research output as a local directory: copies the synthesis "
            "document, writes a sources URL list, and optionally copies to your Obsidian vault. "
            "Use this when you want a self-contained local record without pushing to NotebookLM."
        ),
        input_schema=ToLocalInputs,
        name="to-local",
    )
    def to_local(self, inputs: ToLocalInputs, context: Context) -> ToLocalResult:
        output_dir = context.settings.research.output_dir.expanduser()

        if inputs.output_file:
            out_path = Path(inputs.output_file)
            if not out_path.is_absolute():
                out_path = output_dir / inputs.output_file
        else:
            candidates = [
                p for p in output_dir.glob("*.md")
                if not p.name.endswith("-review.md")
            ] if output_dir.is_dir() else []
            if not candidates:
                return ToLocalResult(
                    ok=False, output_file=None, sources_file=None,
                    package_dir=None, sources_count=0,
                    message=(
                        f"No research output found in {output_dir}. "
                        "Run `docent studio deep-research` or `docent studio lit` first."
                    ),
                )
            out_path = max(candidates, key=lambda p: p.stat().st_mtime)

        stem = out_path.stem
        sources_path = out_path.parent / f"{stem}-sources.json"

        has_sources = sources_path.exists()
        selected = (
            _rank_sources(
                json.loads(sources_path.read_text(encoding="utf-8")), 200
            )
            if has_sources else []
        )

        package_dir = out_path.parent / f"{stem}-local"
        package_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_path, package_dir / out_path.name)

        urls_text = "\n".join(s["url"] for s in selected if s.get("url"))
        (package_dir / "sources_urls.txt").write_text(urls_text, encoding="utf-8")

        if has_sources:
            shutil.copy2(sources_path, package_dir / sources_path.name)

        for gf_str in inputs.guide_files:
            gf = Path(gf_str).expanduser()
            if gf.exists():
                shutil.copy2(gf, package_dir / gf.name)

        vault_path: str | None = None
        if inputs.to_vault:
            vault = context.settings.research.obsidian_vault
            if vault:
                vault_dir = Path(vault).expanduser()
                vault_dir.mkdir(parents=True, exist_ok=True)
                dest = vault_dir / out_path.name
                shutil.copy2(out_path, dest)
                vault_path = str(dest)
            else:
                return ToLocalResult(
                    ok=True,
                    output_file=str(out_path),
                    sources_file=str(sources_path) if has_sources else None,
                    package_dir=str(package_dir),
                    sources_count=len(selected),
                    message=(
                        f"Package written to {package_dir}. "
                        "Vault copy skipped: obsidian_vault not configured "
                        "(set with: docent studio config-set --key obsidian_vault --value <path>)."
                    ),
                )

        parts = [f"Local package: {package_dir}", f"{len(selected)} source URL(s)"]
        if vault_path:
            parts.append(f"vault: {vault_path}")

        return ToLocalResult(
            ok=True,
            output_file=str(out_path),
            sources_file=str(sources_path) if has_sources else None,
            package_dir=str(package_dir),
            sources_count=len(selected),
            vault_path=vault_path,
            message=" -- ".join(parts),
        )

    @action(
        description="Search academic papers on alphaXiv by topic or keyword.",
        input_schema=SearchPapersInputs,
        name="search-papers",
    )
    def search_papers(self, inputs: SearchPapersInputs, context: Context) -> SearchPapersResult:
        from .alphaxiv_client import AlphaXivAuthError, search_papers as _search
        try:
            papers = _search(
                inputs.query,
                api_key=context.settings.research.alphaxiv_api_key,
                max_results=inputs.max_results,
            )
        except AlphaXivAuthError as e:
            return SearchPapersResult(ok=False, query=inputs.query, papers=[], count=0, message=str(e))
        except Exception as e:
            return SearchPapersResult(ok=False, query=inputs.query, papers=[], count=0, message=f"Search failed: {e}")
        return SearchPapersResult(
            ok=True,
            query=inputs.query,
            papers=papers,
            count=len(papers),
            message=f"Found {len(papers)} paper(s) for '{inputs.query}'.",
        )

    @action(
        description="Get AI-generated overview and abstract for an arXiv paper.",
        input_schema=GetPaperInputs,
        name="get-paper",
    )
    def get_paper(self, inputs: GetPaperInputs, context: Context) -> GetPaperResult:
        from .alphaxiv_client import AlphaXivAuthError, get_paper_overview
        arxiv_id = inputs.arxiv_id.strip().rstrip("/")
        if "/" in arxiv_id:
            arxiv_id = arxiv_id.rsplit("/", 1)[-1]
        try:
            data = get_paper_overview(
                arxiv_id,
                api_key=context.settings.research.alphaxiv_api_key,
            )
        except AlphaXivAuthError as e:
            return GetPaperResult(ok=False, arxiv_id=arxiv_id, title=None, abstract="", overview="", message=str(e))
        except Exception as e:
            return GetPaperResult(ok=False, arxiv_id=arxiv_id, title=None, abstract="", overview="", message=f"Failed to fetch paper: {e}")
        return GetPaperResult(
            ok=True,
            arxiv_id=arxiv_id,
            title=data["title"],
            abstract=data["abstract"],
            overview=data["overview"],
            message=f"Retrieved overview for {arxiv_id}.",
        )

    @action(
        description="Search academic papers via Google Scholar (with Semantic Scholar and CrossRef as fallbacks).",
        input_schema=ScholarlySearchInputs,
        name="scholarly-search",
    )
    def scholarly_search(self, inputs: ScholarlySearchInputs, context: Context) -> ScholarlySearchResult:
        from .scholarly_client import search_scholarly
        try:
            papers, backend = search_scholarly(
                inputs.query,
                inputs.max_results,
                semantic_scholar_api_key=context.settings.research.semantic_scholar_api_key,
            )
        except RuntimeError as e:
            return ScholarlySearchResult(
                ok=False, query=inputs.query, papers=[], count=0,
                backend_used="none", message=str(e),
            )
        except Exception as e:
            return ScholarlySearchResult(
                ok=False, query=inputs.query, papers=[], count=0,
                backend_used="none", message=f"Search failed: {e}",
            )
        if not papers:
            return ScholarlySearchResult(
                ok=False, query=inputs.query, papers=[], count=0,
                backend_used=backend,
                message=f"No results found for '{inputs.query}' (via {backend}).",
            )
        return ScholarlySearchResult(
            ok=True,
            query=inputs.query,
            papers=papers,
            count=len(papers),
            backend_used=backend,
            message=f"Found {len(papers)} paper(s) for '{inputs.query}' (via {backend}).",
        )

    @action(
        description="Show research settings.",
        input_schema=ConfigShowInputs,
        name="config-show",
    )
    def config_show(self, inputs: ConfigShowInputs, context: Context) -> ConfigShowResult:
        from docent.utils.paths import config_file
        rs = context.settings.research
        return ConfigShowResult(
            config_path=str(config_file()),
            output_dir=str(rs.output_dir),
            feynman_command=rs.feynman_command or ["feynman"],
            oc_provider=rs.oc_provider,
            oc_model_planner=rs.oc_model_planner,
            oc_model_writer=rs.oc_model_writer,
            oc_model_verifier=rs.oc_model_verifier,
            oc_model_reviewer=rs.oc_model_reviewer,
            oc_model_researcher=rs.oc_model_researcher,
            oc_budget_usd=rs.oc_budget_usd,
            tavily_api_key=rs.tavily_api_key,
            tavily_research_timeout=rs.tavily_research_timeout,
            semantic_scholar_api_key=rs.semantic_scholar_api_key,
            feynman_model=rs.feynman_model,
            feynman_timeout=rs.feynman_timeout,
            notebooklm_notebook_id=rs.notebooklm_notebook_id,
            obsidian_vault=str(rs.obsidian_vault) if rs.obsidian_vault else None,
            alphaxiv_api_key=rs.alphaxiv_api_key,
        )

    @action(
        description="Set a research setting (output_dir).",
        input_schema=ConfigSetInputs,
        name="config-set",
    )
    def config_set(self, inputs: ConfigSetInputs, context: Context) -> ConfigSetResult:
        from docent.utils.paths import config_file
        if inputs.key not in _KNOWN_RESEARCH_KEYS:
            return ConfigSetResult(
                ok=False,
                key=inputs.key,
                value=inputs.value,
                config_path=str(config_file()),
                message=f"Unknown key {inputs.key!r}. Known: {sorted(_KNOWN_RESEARCH_KEYS)}.",
            )
        path = write_setting(f"research.{inputs.key}", inputs.value)
        return ConfigSetResult(
            ok=True,
            key=inputs.key,
            value=inputs.value,
            config_path=str(path),
            message=f"Set research.{inputs.key} = {inputs.value!r} in {path}.",
        )

    @action(
        description="Compare two research artifacts (arXiv IDs, PDFs, or URLs) side by side.",
        input_schema=CompareInputs,
        preflight=_preflight_oc_only,
    )
    def compare(self, inputs: CompareInputs, context: Context):
        topic_label = f"{inputs.artifact_a} vs {inputs.artifact_b}"
        slug = _slugify(_artifact_slug(inputs.artifact_a) + "-vs-" + _artifact_slug(inputs.artifact_b)) + "-compare"

        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_compare

            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                result_data = yield from run_compare(
                    inputs.artifact_a, inputs.artifact_b, oc,
                    model_researcher=context.settings.research.oc_model_researcher,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False, backend="docent", workflow="compare",
                    topic_or_artifact=topic_label, output_file=None, returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False, backend="docent", workflow="compare",
                    topic_or_artifact=topic_label, output_file=None, returncode=None,
                    message=result_data.get("error") or "Compare failed.",
                )

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            out_file.write_text(result_data["comparison"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "compare"
            )
            return ResearchResult(
                ok=True, backend="docent", workflow="compare",
                topic_or_artifact=topic_label, output_file=str(out_file), returncode=0,
                notebook_id=notebook_id, vault_path=vault_path,
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
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="compare",
                topic_or_artifact=topic_label, output_file=None, returncode=None, message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False, backend="feynman", workflow="compare",
                topic_or_artifact=topic_label, output_file=output_file, returncode=returncode, message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True, backend="feynman", workflow="compare",
                topic_or_artifact=topic_label, output_file=None, returncode=returncode,
                message=f"Compare completed for {topic_label!r}, but no output file was found.",
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "compare"
        )
        return ResearchResult(
            ok=True, backend="feynman", workflow="compare",
            topic_or_artifact=topic_label, output_file=output_file, returncode=returncode,
            notebook_id=notebook_id, vault_path=vault_path,
            message=f"Compare completed for {topic_label!r}.{extra}",
        )

    @action(
        description="Draft a paper section or document on a topic.",
        input_schema=DraftInputs,
        preflight=_preflight_oc_only,
    )
    def draft(self, inputs: DraftInputs, context: Context):
        slug = _slugify(inputs.topic) + "-draft"

        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_draft

            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            guide_ctx = _read_guide_files(inputs.guide_files)

            try:
                result_data = yield from run_draft(
                    inputs.topic, oc,
                    guide_context=guide_ctx,
                    model_writer=context.settings.research.oc_model_writer,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False, backend="docent", workflow="draft",
                    topic_or_artifact=inputs.topic, output_file=None, returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False, backend="docent", workflow="draft",
                    topic_or_artifact=inputs.topic, output_file=None, returncode=None,
                    message=result_data.get("error") or "Draft failed.",
                )

            out_file = output_dir / f"{slug}.md"
            out_file.write_text(result_data["draft"], encoding="utf-8")

            yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "draft"
            )
            return ResearchResult(
                ok=True, backend="docent", workflow="draft",
                topic_or_artifact=inputs.topic, output_file=str(out_file), returncode=0,
                notebook_id=notebook_id, vault_path=vault_path,
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
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="draft",
                topic_or_artifact=inputs.topic, output_file=None, returncode=None, message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False, backend="feynman", workflow="draft",
                topic_or_artifact=inputs.topic, output_file=output_file, returncode=returncode, message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True, backend="feynman", workflow="draft",
                topic_or_artifact=inputs.topic, output_file=None, returncode=returncode,
                message=f"Draft completed for {inputs.topic!r}, but no output file was found.",
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "draft"
        )
        return ResearchResult(
            ok=True, backend="feynman", workflow="draft",
            topic_or_artifact=inputs.topic, output_file=output_file, returncode=returncode,
            notebook_id=notebook_id, vault_path=vault_path,
            message=f"Draft completed for {inputs.topic!r}.{extra}",
        )

    @action(
        description="Build a replication guide for a paper (arXiv ID, PDF, or URL).",
        input_schema=ReplicateInputs,
        preflight=_preflight_oc_only,
    )
    def replicate(self, inputs: ReplicateInputs, context: Context):
        slug = _slugify(_artifact_slug(inputs.artifact)) + "-replicate"

        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_replicate

            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                result_data = yield from run_replicate(
                    inputs.artifact, oc,
                    model_researcher=context.settings.research.oc_model_researcher,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False, backend="docent", workflow="replicate",
                    topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False, backend="docent", workflow="replicate",
                    topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                    message=result_data.get("error") or "Replication analysis failed.",
                )

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            out_file.write_text(result_data["guide"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "replicate"
            )
            return ResearchResult(
                ok=True, backend="docent", workflow="replicate",
                topic_or_artifact=inputs.artifact, output_file=str(out_file), returncode=0,
                notebook_id=notebook_id, vault_path=vault_path,
                message=f"Replication guide complete.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(phase="start", message=f"Starting Feynman replicate: {inputs.artifact!r}")
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
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="replicate",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=None, message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False, backend="feynman", workflow="replicate",
                topic_or_artifact=inputs.artifact, output_file=output_file, returncode=returncode, message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True, backend="feynman", workflow="replicate",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=returncode,
                message=f"Replicate completed for {inputs.artifact!r}, but no output file was found.",
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "replicate"
        )
        return ResearchResult(
            ok=True, backend="feynman", workflow="replicate",
            topic_or_artifact=inputs.artifact, output_file=output_file, returncode=returncode,
            notebook_id=notebook_id, vault_path=vault_path,
            message=f"Replicate completed for {inputs.artifact!r}.{extra}",
        )

    @action(
        description="Audit a paper (arXiv ID, PDF, or URL) for methodology, claim validity, and reproducibility.",
        input_schema=AuditInputs,
        preflight=_preflight_oc_only,
    )
    def audit(self, inputs: AuditInputs, context: Context):
        slug = _slugify(_artifact_slug(inputs.artifact)) + "-audit"

        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_audit

            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                result_data = yield from run_audit(
                    inputs.artifact, oc,
                    model_researcher=context.settings.research.oc_model_researcher,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False, backend="docent", workflow="audit",
                    topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False, backend="docent", workflow="audit",
                    topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                    message=result_data.get("error") or "Audit failed.",
                )

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            out_file.write_text(result_data["report"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "audit"
            )
            return ResearchResult(
                ok=True, backend="docent", workflow="audit",
                topic_or_artifact=inputs.artifact, output_file=str(out_file), returncode=0,
                notebook_id=notebook_id, vault_path=vault_path,
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
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="audit",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=None, message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False, backend="feynman", workflow="audit",
                topic_or_artifact=inputs.artifact, output_file=output_file, returncode=returncode, message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True, backend="feynman", workflow="audit",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=returncode,
                message=f"Audit completed for {inputs.artifact!r}, but no output file was found.",
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "audit"
        )
        return ResearchResult(
            ok=True, backend="feynman", workflow="audit",
            topic_or_artifact=inputs.artifact, output_file=output_file, returncode=returncode,
            notebook_id=notebook_id, vault_path=vault_path,
            message=f"Audit completed for {inputs.artifact!r}.{extra}",
        )

    @action(
        description="Show today's Feynman and OpenCode spend against configured budgets.",
        input_schema=UsageInputs,
    )
    def usage(self, inputs: UsageInputs, context: Context) -> UsageResult:
        import datetime
        from .oc_client import _read_oc_daily_spend
        from .search import _read_tavily_daily_requests
        feynman_spend = _read_daily_spend()
        oc_spend = _read_oc_daily_spend()
        tavily_requests = _read_tavily_daily_requests()
        rs = context.settings.research
        today = datetime.date.today().isoformat()
        return UsageResult(
            feynman_spend_usd=feynman_spend,
            oc_spend_usd=oc_spend,
            feynman_budget_usd=rs.feynman_budget_usd,
            oc_budget_usd=rs.oc_budget_usd,
            date=today,
            message=(
                f"Today ({today}): Feynman ${feynman_spend:.4f}"
                + (f" / ${rs.feynman_budget_usd:.2f}" if rs.feynman_budget_usd > 0 else "")
                + f", OpenCode ${oc_spend:.4f}"
                + (f" / ${rs.oc_budget_usd:.2f}" if rs.oc_budget_usd > 0 else "")
                + f", Tavily {tavily_requests} reqs"
                + " / 1000/mo free"
            ),
        )


def on_startup(context) -> None:  # noqa: ARG001
    """Check for Feynman updates once per day and notify the user."""
    import re
    from docent.utils.update_check import check_github_release
    from docent.ui import get_console

    try:
        cmd = _find_feynman(context.settings.research.feynman_command)
        raw = _feynman_version_from_package_json(cmd)
        m = re.search(r"\d+\.\d+(?:\.\d+)?", raw)
        current = m.group() if m else None
    except FeynmanNotFoundError:
        return

    info = check_github_release(
        "companion-inc/feynman",
        current_version=current,
        upgrade_cmd="npm install -g @companion-ai/feynman@latest",
    )
    if info:
        get_console().print(
            f"[yellow]UPDATE AVAILABLE:[/] feynman {info.latest} is available "
            f"(run: {info.upgrade_cmd})"
        )

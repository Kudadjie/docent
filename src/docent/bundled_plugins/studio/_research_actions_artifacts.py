"""Artifact-centric research actions: review, compare, draft, replicate, audit.

Split out of _research.py; composed back into ResearchMixin there.
"""

from __future__ import annotations

import logging
from pathlib import Path

from docent.bundled_plugins.studio.feynman import (
    FeynmanNotFoundError,
    _summarize_feynman_error,
)
from docent.bundled_plugins.studio.helpers import (
    _artifact_slug,
    _read_guide_files,
    _slugify,
)
from docent.bundled_plugins.studio.models import (
    AuditInputs,
    CompareInputs,
    DraftInputs,
    ReplicateInputs,
    ResearchResult,
    ReviewInputs,
)
from docent.bundled_plugins.studio.preflights import (
    _preflight_oc_only,
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


class ResearchArtifactActions:
    """review/compare/draft/replicate/audit actions (mixed into StudioTool)."""

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

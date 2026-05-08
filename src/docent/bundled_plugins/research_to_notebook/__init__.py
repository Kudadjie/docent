"""Research tool: run deep research, literature reviews, and peer reviews via Feynman."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from docent.config import write_setting
from docent.core import Context, ProgressEvent, Tool, action, register_tool
from docent.core.shapes import (
    ErrorShape,
    LinkShape,
    MessageShape,
    MetricShape,
    Shape,
)


def _slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric with hyphens, collapse runs."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    return s.strip("-")[:60]


def _artifact_slug(artifact: str) -> str:
    """Derive a slug from an artifact identifier (URL, arXiv ID, or path)."""
    s = artifact.strip()
    if "/" in s:
        s = s.rstrip("/").rsplit("/", 1)[-1]
    return s


def _run_feynman(
    cmd: list[str],
    workspace_dir: Path,
    output_dir: Path,
    slug: str,
) -> tuple[int, str | None]:
    """Run feynman and return (returncode, output_file_path | None)."""
    workspace_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir = workspace_dir / "outputs"

    before: set[Path] = set(outputs_dir.glob("*.md")) if outputs_dir.is_dir() else set()

    result = subprocess.run(cmd, cwd=workspace_dir)

    after: set[Path] = set(outputs_dir.glob("*.md")) if outputs_dir.is_dir() else set()
    new_files = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)

    if not new_files:
        return result.returncode, None

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / f"{slug}.md"
    shutil.copy2(new_files[0], dest)
    return result.returncode, str(dest)


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class DeepInputs(BaseModel):
    topic: str = Field(..., description="Research topic or question.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default). 'docent' is planned.")


class LitInputs(BaseModel):
    topic: str = Field(..., description="Research topic or question.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default). 'docent' is planned.")


class ReviewInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, local PDF path, or URL to review.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default). 'docent' is planned.")


class ConfigShowInputs(BaseModel):
    pass


class ConfigSetInputs(BaseModel):
    key: str = Field(..., description="Setting key under [research]: 'output_dir'.")
    value: str = Field(..., description="New value.")


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

class ResearchResult(BaseModel):
    ok: bool
    backend: str
    workflow: str
    topic_or_artifact: str
    output_file: str | None
    returncode: int | None
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.output_file is not None:
            shapes.append(LinkShape(url=self.output_file, label="Output file"))
        return shapes

    def __rich_console__(self, console, options):
        from docent.ui.renderers import render_shapes
        render_shapes(self.to_shapes(), console)
        yield from ()


class ConfigShowResult(BaseModel):
    config_path: str
    output_dir: str
    feynman_command: list[str]

    def to_shapes(self) -> list[Shape]:
        return [
            MetricShape(label="Config", value=self.config_path),
            MetricShape(label="output_dir", value=self.output_dir),
            MetricShape(label="feynman_command", value=" ".join(self.feynman_command)),
        ]

    def __rich_console__(self, console, options):
        from docent.ui.renderers import render_shapes
        render_shapes(self.to_shapes(), console)
        yield from ()


class ConfigSetResult(BaseModel):
    ok: bool
    key: str
    value: str
    config_path: str
    message: str

    def to_shapes(self) -> list[Shape]:
        return [
            MessageShape(text=self.message, level="success" if self.ok else "error"),
        ]

    def __rich_console__(self, console, options):
        from docent.ui.renderers import render_shapes
        render_shapes(self.to_shapes(), console)
        yield from ()


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

_KNOWN_RESEARCH_KEYS = {"output_dir"}


@register_tool
class ResearchTool(Tool):
    """Run research workflows (deep research, literature review, peer review) via Feynman."""

    name = "research"
    description = "Run research workflows (deep research, literature review, peer review) via Feynman."
    category = "research"

    @action(
        description="Deep research on a topic.",
        input_schema=DeepInputs,
    )
    def deep(self, inputs: DeepInputs, context: Context):
        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_deep

            oc = OcClient()
            if not oc.is_available():
                yield ProgressEvent(
                    phase="start",
                    message="OpenCode server is not running. Start it with: opencode serve --port 4096",
                )
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="deep",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message="OpenCode server is not running. Start it with: opencode serve --port 4096",
                )

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(inputs.topic) + "-deep"

            progress_events: list[tuple[str, str]] = []

            def _capture_progress(phase: str, message: str) -> None:
                progress_events.append((phase, message))

            yield ProgressEvent(
                phase="start",
                message=f"Starting Docent deep research on: {inputs.topic!r}",
            )

            try:
                result_data = run_deep(inputs.topic, oc, on_progress=_capture_progress)
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

            for phase, message in progress_events:
                yield ProgressEvent(phase=phase, message=message)

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
            out_file.write_text(result_data["draft"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(
                phase="done", message=f"Output written to {out_file}"
            )

            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=str(out_file),
                returncode=0,
                message=f"Deep research complete. {result_data['rounds']} search round(s), {len(result_data['sources'])} sources.",
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
        cmd = [*feynman_cmd, "deepresearch", inputs.topic]

        returncode, output_file = _run_feynman(cmd, workspace_dir, output_dir, slug)

        if returncode != 0:
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=output_file,
                returncode=returncode,
                message=f"Feynman deep research exited with code {returncode}.",
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

        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="deep",
            topic_or_artifact=inputs.topic,
            output_file=output_file,
            returncode=returncode,
            message=f"Deep research completed for {inputs.topic!r}.",
        )

    @action(
        description="Literature review on a topic.",
        input_schema=LitInputs,
    )
    def lit(self, inputs: LitInputs, context: Context):
        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_lit

            oc = OcClient()
            if not oc.is_available():
                yield ProgressEvent(
                    phase="start",
                    message="OpenCode server is not running. Start it with: opencode serve --port 4096",
                )
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="lit",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message="OpenCode server is not running. Start it with: opencode serve --port 4096",
                )

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(inputs.topic) + "-lit"
            progress_events: list[tuple[str, str]] = []

            def _capture(phase: str, message: str) -> None:
                progress_events.append((phase, message))

            yield ProgressEvent(
                phase="start",
                message=f"Starting Docent literature review: {inputs.topic!r}",
            )

            try:
                result_data = run_lit(inputs.topic, oc, on_progress=_capture)
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

            for phase, message in progress_events:
                yield ProgressEvent(phase=phase, message=message)

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
            out_file.write_text(result_data["draft"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=str(out_file),
                returncode=0,
                message=f"Literature review complete. {result_data['rounds']} search round(s), {len(result_data['sources'])} sources.",
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
        cmd = [*feynman_cmd, "lit", inputs.topic]

        returncode, output_file = _run_feynman(cmd, workspace_dir, output_dir, slug)

        if returncode != 0:
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=output_file,
                returncode=returncode,
                message=f"Feynman literature review exited with code {returncode}.",
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

        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="lit",
            topic_or_artifact=inputs.topic,
            output_file=output_file,
            returncode=returncode,
            message=f"Literature review completed for {inputs.topic!r}.",
        )

    @action(
        description="Peer review of an artifact (arXiv ID, PDF path, or URL).",
        input_schema=ReviewInputs,
    )
    def review(self, inputs: ReviewInputs, context: Context):
        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_review

            oc = OcClient()
            if not oc.is_available():
                yield ProgressEvent(
                    phase="start",
                    message="OpenCode server is not running. Start it with: opencode serve --port 4096",
                )
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="review",
                    topic_or_artifact=inputs.artifact,
                    output_file=None,
                    returncode=None,
                    message="OpenCode server is not running. Start it with: opencode serve --port 4096",
                )

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(_artifact_slug(inputs.artifact)) + "-review"
            progress_events: list[tuple[str, str]] = []

            def _capture(phase: str, message: str) -> None:
                progress_events.append((phase, message))

            yield ProgressEvent(
                phase="start",
                message=f"Starting Docent peer review: {inputs.artifact!r}",
            )

            try:
                result_data = run_review(inputs.artifact, oc, on_progress=_capture)
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

            for phase, message in progress_events:
                yield ProgressEvent(phase=phase, message=message)

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

            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="review",
                topic_or_artifact=inputs.artifact,
                output_file=str(out_file),
                returncode=0,
                message=f"Peer review complete for {inputs.artifact!r}.",
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
        cmd = [*feynman_cmd, "review", inputs.artifact]

        returncode, output_file = _run_feynman(cmd, workspace_dir, output_dir, slug)

        if returncode != 0:
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="review",
                topic_or_artifact=inputs.artifact,
                output_file=output_file,
                returncode=returncode,
                message=f"Feynman review exited with code {returncode}.",
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

        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="review",
            topic_or_artifact=inputs.artifact,
            output_file=output_file,
            returncode=returncode,
            message=f"Review completed for {inputs.artifact!r}.",
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



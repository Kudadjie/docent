"""Research tool: run deep research, literature reviews, and peer reviews via Feynman."""
from __future__ import annotations

import json
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


def _rank_sources(sources: list[dict], max_sources: int) -> list[dict]:
    """Rank sources: papers first (have abstracts), then web with full_text, then rest."""
    papers = [s for s in sources if s.get("source_type") == "paper" and s.get("url")]
    web_with_text = [
        s for s in sources
        if s.get("source_type") == "web" and s.get("url") and s.get("full_text")
    ]
    web_snippet_only = [
        s for s in sources
        if s.get("source_type") == "web" and s.get("url") and not s.get("full_text")
    ]
    ranked = papers + web_with_text + web_snippet_only
    seen: set[str] = set()
    unique: list[dict] = []
    for s in ranked:
        url = s.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(s)
    return unique[:max_sources]


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


class ToNotebookInputs(BaseModel):
    output_file: str | None = Field(
        None,
        description=(
            "Path to a research output .md file (e.g. 'storm-surge-ghana-deep.md'). "
            "If omitted, the most recent output in research.output_dir is used."
        ),
    )
    max_sources: int = Field(
        20,
        description="Maximum number of sources to include in the notebook package (default 20).",
    )


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


class ToNotebookResult(BaseModel):
    ok: bool
    output_file: str | None
    sources_file: str | None
    package_dir: str | None
    sources_count: int
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.package_dir:
            shapes.append(LinkShape(url=self.package_dir, label="Notebook package"))
        return shapes

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
            sources_file = output_dir / f"{slug}-sources.json"
            out_file.write_text(result_data["draft"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")
            sources_file.write_text(
                json.dumps(result_data.get("sources", []), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

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
            sources_file = output_dir / f"{slug}-sources.json"
            out_file.write_text(result_data["draft"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")
            sources_file.write_text(
                json.dumps(result_data.get("sources", []), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

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
        description=(
            "Prepare research sources for NotebookLM and open the browser. "
            "Reads the sources collected by the Docent pipeline (deep or lit) "
            "and writes a notebook-ready package."
        ),
        input_schema=ToNotebookInputs,
        name="to-notebook",
    )
    def to_notebook(self, inputs: ToNotebookInputs, context: Context) -> ToNotebookResult:
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
                return ToNotebookResult(
                    ok=False, output_file=None, sources_file=None,
                    package_dir=None, sources_count=0,
                    message=(
                        f"No research output found in {output_dir}. "
                        "Run `docent research deep` or `docent research lit` first."
                    ),
                )
            out_path = max(candidates, key=lambda p: p.stat().st_mtime)

        stem = out_path.stem
        sources_path = out_path.parent / f"{stem}-sources.json"

        if not sources_path.exists():
            return ToNotebookResult(
                ok=False, output_file=str(out_path), sources_file=None,
                package_dir=None, sources_count=0,
                message=(
                    f"No sources file found at {sources_path}. "
                    "Sources are only saved when using backend='docent'. "
                    "The Feynman backend does not expose individual sources."
                ),
            )

        sources: list[dict] = json.loads(sources_path.read_text(encoding="utf-8"))
        selected = _rank_sources(sources, inputs.max_sources)

        import webbrowser

        package_dir = out_path.parent / f"{stem}-notebook"
        package_dir.mkdir(parents=True, exist_ok=True)

        urls_file = package_dir / "sources_urls.txt"
        urls_file.write_text(
            "\n".join(s["url"] for s in selected if s.get("url")),
            encoding="utf-8",
        )

        shutil.copy2(out_path, package_dir / out_path.name)

        guide_lines = [
            "# NotebookLM Setup Guide",
            "",
            f"Research: {out_path.name}",
            f"Sources: {len(selected)} selected",
            "",
            "## Steps",
            "",
            "1. Open https://notebooklm.google.com and create a new notebook",
            f"2. Add the research draft as a source: drag `{out_path.name}` into the Sources panel",
            "3. Add each URL below as a 'Website' source (copy/paste one at a time):",
            "",
        ]
        for i, s in enumerate(selected, 1):
            title = s.get("title", "Untitled")[:80]
            url = s.get("url", "")
            stype = s.get("source_type", "web")
            guide_lines.append(f"   [{i}] [{stype}] {title}")
            guide_lines.append(f"       {url}")
            guide_lines.append("")

        guide_lines += [
            "## Tips",
            "",
            "- Add the draft first so NotebookLM can cross-reference it with sources",
            "- Use the 'Notebook guide' feature to get an overview after adding all sources",
            "- Generate a podcast or study guide once sources are loaded",
        ]
        (package_dir / "guide.md").write_text("\n".join(guide_lines), encoding="utf-8")

        webbrowser.open("https://notebooklm.google.com")

        return ToNotebookResult(
            ok=True,
            output_file=str(out_path),
            sources_file=str(sources_path),
            package_dir=str(package_dir),
            sources_count=len(selected),
            message=(
                f"Notebook package ready: {len(selected)} sources. "
                f"NotebookLM opened in browser. "
                f"Follow the guide in {package_dir / 'guide.md'}."
            ),
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



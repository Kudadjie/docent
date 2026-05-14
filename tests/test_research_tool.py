"""Tests for the research tool (Feynman backend)."""
from __future__ import annotations

import inspect
import json
import webbrowser
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer

from docent.config.settings import ResearchSettings, Settings
from docent.core.context import Context
from docent.core.shapes import ErrorShape, LinkShape, MessageShape
from docent.bundled_plugins.studio import (
    AuditInputs,
    CompareInputs,
    ConfigSetInputs,
    ConfigShowInputs,
    ConfigShowResult,
    ConfigSetResult,
    DeepInputs,
    DraftInputs,
    LitInputs,
    ReplicateInputs,
    ReviewInputs,
    ResearchResult,
    StudioTool,
    ToNotebookInputs,
    ToNotebookResult,
    UsageInputs,
    UsageResult,
    _slugify,
    _artifact_slug,
    _rank_sources,
    _preflight_docent,
    _preflight_oc_only,
)


def _drain(maybe_gen: Any) -> Any:
    """Drive a generator action and return its final result."""
    if not inspect.isgenerator(maybe_gen):
        return maybe_gen
    try:
        while True:
            next(maybe_gen)
    except StopIteration as e:
        return e.value


def _fake_pipeline_gen(result_dict: dict):
    """Create a generator that yields no events and returns result_dict.

    Used to mock run_deep / run_lit / run_review which are now generators.
    """
    return result_dict
    yield  # noqa: unreachable — makes this a generator


def _make_nlm_push(
    *,
    ok: bool = True,
    notebook_id: str | None = "test-nb",
    sources_added: int = 2,
    sources_failed: int = 0,
    message: str | None = None,
):
    """Return a generator function that stands in for _nlm_push.

    Patches the whole 4-phase NLM pipeline so tests don't hit real HTTP
    calls or subprocess spawns inside _nlm_push's internals.
    """
    from docent.core import ProgressEvent
    _msg = message or f"Notebook ready. {notebook_id}"

    def _push(*args, **kwargs):
        yield ProgressEvent(phase="nlm-check", message="mock")
        return {
            "ok": ok,
            "notebook_id": notebook_id,
            "sources_added": sources_added,
            "sources_failed": sources_failed,
            "sources_from_feynman": 0,
            "sources_from_nlm": 0,
            "quality_gate": {},
            "perspectives": {},
            "message": _msg,
        }

    return _push


def _mock_context(
    *,
    output_dir: Path | None = None,
    feynman_command: list[str] | None = None,
    tavily_api_key: str | None = None,
    notebooklm_notebook_id: str | None = None,
    obsidian_vault: Path | None = None,
) -> Context:
    research = ResearchSettings(
        output_dir=output_dir or Path("/tmp/docent-test-research"),
        feynman_command=feynman_command,
        tavily_api_key=tavily_api_key,
        notebooklm_notebook_id=notebooklm_notebook_id,
        obsidian_vault=obsidian_vault,
    )
    settings = MagicMock(spec=Settings)
    settings.research = research
    return Context(settings=settings, llm=MagicMock(), executor=MagicMock())


class TestSlugify:
    def test_basic(self):
        assert _slugify("Storm Surge Ghana") == "storm-surge-ghana"

    def test_collapses_hyphens(self):
        assert _slugify("hello   world") == "hello-world"

    def test_strips_leading_trailing_hyphens(self):
        assert _slugify("---hello-world---") == "hello-world"

    def test_truncates_to_60(self):
        long = "a" * 100
        assert len(_slugify(long)) == 60

    def test_artifact_slug_url(self):
        assert _artifact_slug("https://arxiv.org/abs/2401.12345") == "2401.12345"

    def test_artifact_slug_plain(self):
        assert _artifact_slug("2401.12345") == "2401.12345"


class TestStripReferencesSection:
    """Tests for _strip_references_section and _append_references."""

    def test_strip_removes_trailing_references(self):
        from docent.bundled_plugins.studio import (
            _strip_references_section,
        )
        draft = "Introduction\n\n## References\n1. **Paper A** — https://example.com [web]"
        result = _strip_references_section(draft)
        assert "## References" not in result
        assert "Introduction" in result
        assert "Paper A" not in result

    def test_strip_preserves_draft_without_references(self):
        from docent.bundled_plugins.studio import (
            _strip_references_section,
        )
        draft = "Just a regular draft with no references section."
        result = _strip_references_section(draft)
        assert result == draft

    def test_append_references_strips_existing(self):
        from docent.bundled_plugins.studio import (
            _append_references,
        )
        sources = [
            {"title": "Source A", "url": "https://a.com", "source_type": "web"},
            {"title": "Source B", "url": "https://b.com", "source_type": "paper"},
        ]
        # Draft that already has a references section from Tavily
        draft = "Content\n\n## References\n1. Tavily source - https://tavily.com [web]"
        result = _append_references(draft, sources)
        # Should have exactly one ## References section
        assert result.count("## References") == 1
        assert "Source A" in result
        assert "Source B" in result
        assert "Tavily source" not in result

    def test_append_references_adds_to_draft_without(self):
        from docent.bundled_plugins.studio import (
            _append_references,
        )
        sources = [
            {"title": "Source A", "url": "https://a.com", "source_type": "web"},
        ]
        draft = "Just a draft with no references."
        result = _append_references(draft, sources)
        assert "## References" in result
        assert "Source A" in result


class TestDeepFeynman:
    def test_deep_feynman_happy_path(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        fake_output = str(output_dir / "storm-surge-ghana-deep.md")
        with patch(
            "docent.bundled_plugins.studio._run_feynman",
            return_value=(0, fake_output, ""),
        ):
            result = _drain(tool.deep_research(DeepInputs(topic="storm surge Ghana"), ctx))

        assert result.ok is True
        assert result.backend == "feynman"
        assert result.workflow == "deep"
        assert result.topic_or_artifact == "storm surge Ghana"
        assert result.output_file == fake_output
        assert result.output_file.endswith("storm-surge-ghana-deep.md")
        assert result.returncode == 0

    def test_deep_feynman_no_output_file(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        with patch(
            "docent.bundled_plugins.studio._run_feynman",
            return_value=(0, None, ""),
        ):
            result = _drain(tool.deep_research(DeepInputs(topic="storm surge Ghana"), ctx))

        assert result.ok is True
        assert result.output_file is None
        assert "no output file was found" in result.message

    def test_deep_feynman_nonzero_exit(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        with patch(
            "docent.bundled_plugins.studio._run_feynman",
            return_value=(1, None, "quota exceeded"),
        ):
            result = _drain(tool.deep_research(DeepInputs(topic="storm surge Ghana"), ctx))

        assert result.ok is False
        assert result.returncode == 1
        assert "quota exhausted" in result.message.lower()
        assert "docent studio config-set" in result.message

    def test_deep_docent_backend_server_unavailable(self, tmp_path):
        output_dir = tmp_path / "research"
        ctx = _mock_context(output_dir=output_dir)

        with patch(
            "docent.bundled_plugins.studio.oc_client.OcClient"
        ) as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = False
            MockOc.return_value = mock_oc_instance

            with pytest.raises(typer.Exit):
                _preflight_docent(DeepInputs(topic="test", backend="docent"), ctx)


class TestLitFeynman:
    def test_lit_feynman_happy_path(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        fake_output = str(output_dir / "climate-change-lit.md")
        with patch(
            "docent.bundled_plugins.studio._run_feynman",
            return_value=(0, fake_output, ""),
        ):
            result = _drain(tool.lit(LitInputs(topic="climate change"), ctx))

        assert result.ok is True
        assert result.workflow == "lit"
        assert result.topic_or_artifact == "climate change"
        assert result.output_file is not None
        assert result.output_file.endswith("climate-change-lit.md")


class TestReviewFeynman:
    def test_review_feynman_happy_path(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        fake_output = str(output_dir / "2401-12345-review.md")
        with patch(
            "docent.bundled_plugins.studio._run_feynman",
            return_value=(0, fake_output, ""),
        ):
            result = _drain(tool.review(ReviewInputs(artifact="2401.12345"), ctx))

        assert result.ok is True
        assert result.workflow == "review"
        assert result.topic_or_artifact == "2401.12345"
        assert result.output_file is not None
        assert result.output_file.endswith("2401-12345-review.md")


class TestConfigActions:
    def test_config_show(self, tmp_path):
        tool = StudioTool()
        ctx = _mock_context(
            output_dir=Path("~/Documents/Docent/research"),
            feynman_command=["feynman"],
        )

        with patch("docent.utils.paths.config_file", return_value=Path("/fake/config.toml")):
            result = tool.config_show(ConfigShowInputs(), ctx)

        assert isinstance(result, ConfigShowResult)
        assert result.config_path == str(Path("/fake/config.toml"))
        assert "Docent" in result.output_dir and "research" in result.output_dir
        assert result.feynman_command == ["feynman"]

    def test_config_set_unknown_key(self, tmp_path):
        tool = StudioTool()
        ctx = _mock_context(output_dir=tmp_path)

        with patch("docent.utils.paths.config_file", return_value=Path("/fake/config.toml")):
            result = tool.config_set(ConfigSetInputs(key="bad_key", value="x"), ctx)

        assert result.ok is False
        assert isinstance(result, ConfigSetResult)
        assert "Unknown key" in result.message
        assert "bad_key" in result.message

    def test_config_set_output_dir_happy_path(self, tmp_path):
        tool = StudioTool()
        ctx = _mock_context(output_dir=tmp_path)
        fake_config = Path("/fake/config.toml")

        with patch("docent.bundled_plugins.studio.write_setting", return_value=fake_config) as mock_ws, \
             patch("docent.utils.paths.config_file", return_value=fake_config):
            result = tool.config_set(ConfigSetInputs(key="output_dir", value="/new/path"), ctx)

        assert result.ok is True
        assert result.key == "output_dir"
        assert result.value == "/new/path"
        mock_ws.assert_called_once_with("research.output_dir", "/new/path")


class TestToShapes:
    def test_to_shapes_ok_true_returns_message_and_link(self):
        result = ResearchResult(
            ok=True,
            backend="feynman",
            workflow="deep",
            topic_or_artifact="storm surge Ghana",
            output_file="/some/storm-surge-ghana-deep.md",
            returncode=0,
            message="Deep research completed for 'storm surge Ghana'.",
        )
        shapes = result.to_shapes()
        types = [type(s) for s in shapes]
        assert MessageShape in types
        assert LinkShape in types

    def test_to_shapes_ok_false_returns_error_shape(self):
        result = ResearchResult(
            ok=False,
            backend="feynman",
            workflow="deep",
            topic_or_artifact="storm surge Ghana",
            output_file=None,
            returncode=1,
            message="Feynman deep research exited with code 1.",
        )
        shapes = result.to_shapes()
        assert len(shapes) == 1
        assert isinstance(shapes[0], ErrorShape)
        assert "exited with code 1" in shapes[0].reason

    def test_to_shapes_ok_true_no_output_file_omits_link(self):
        result = ResearchResult(
            ok=True,
            backend="feynman",
            workflow="deep",
            topic_or_artifact="test",
            output_file=None,
            returncode=0,
            message="Completed, but no output file was found.",
        )
        shapes = result.to_shapes()
        assert any(isinstance(s, MessageShape) for s in shapes)
        assert not any(isinstance(s, LinkShape) for s in shapes)


class TestLitDocent:
    def test_lit_docent_server_unavailable(self, tmp_path):
        output_dir = tmp_path / "research"
        ctx = _mock_context(output_dir=output_dir)

        with patch(
            "docent.bundled_plugins.studio.oc_client.OcClient"
        ) as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = False
            MockOc.return_value = mock_oc_instance

            with pytest.raises(typer.Exit):
                _preflight_docent(LitInputs(topic="test", backend="docent"), ctx)

    @patch("docent.bundled_plugins.studio.pipeline.run_lit")
    def test_lit_docent_happy_path(self, mock_run_lit, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, tavily_api_key="test-key")

        mock_run_lit.return_value = _fake_pipeline_gen({
            "ok": True,
            "topic": "climate change",
            "draft": "Literature review content",
            "review": "Review content",
            "sources": [{"title": "Source 1"}],
            "rounds": 1,
            "error": None,
        })

        with patch(
            "docent.bundled_plugins.studio.oc_client.OcClient"
        ) as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = True
            MockOc.return_value = mock_oc_instance

            result = _drain(
                tool.lit(LitInputs(topic="climate change", backend="docent"), ctx)
            )

        assert result.ok is True
        assert result.backend == "docent"
        assert result.workflow == "lit"
        assert result.output_file is not None


class TestReviewDocent:
    def test_review_docent_server_unavailable(self, tmp_path):
        output_dir = tmp_path / "research"
        ctx = _mock_context(output_dir=output_dir)

        with patch(
            "docent.bundled_plugins.studio.oc_client.OcClient"
        ) as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = False
            MockOc.return_value = mock_oc_instance

            with pytest.raises(typer.Exit):
                _preflight_oc_only(ReviewInputs(artifact="2401.12345", backend="docent"), ctx)

    @patch("docent.bundled_plugins.studio.pipeline.run_review")
    def test_review_docent_happy_path(self, mock_run_review, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)

        mock_run_review.return_value = _fake_pipeline_gen({
            "ok": True,
            "artifact": "2401.12345",
            "artifact_content": "Paper content",
            "researcher_notes": "Notes",
            "review": "Review content",
            "error": None,
        })

        with patch(
            "docent.bundled_plugins.studio.oc_client.OcClient"
        ) as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = True
            MockOc.return_value = mock_oc_instance

            result = _drain(
                tool.review(ReviewInputs(artifact="2401.12345", backend="docent"), ctx)
            )

        assert result.ok is True
        assert result.backend == "docent"
        assert result.workflow == "review"
        assert result.output_file is not None


SAMPLE_SOURCES = [
    {"title": "Paper A", "url": "https://arxiv.org/abs/2401.00001", "source_type": "paper", "snippet": "Abstract A"},
    {"title": "Web B", "url": "https://example.com/b", "source_type": "web", "full_text": "Full text B", "snippet": "Snippet B"},
    {"title": "Web C", "url": "https://example.com/c", "source_type": "web", "snippet": "Snippet C"},
    {"title": "Paper D", "url": "https://arxiv.org/abs/2401.00002", "source_type": "paper", "snippet": "Abstract D"},
]


class TestToNotebook:
    def _write_research_files(self, output_dir: Path, slug: str = "test-deep") -> tuple[Path, Path]:
        """Helper: write .md + -sources.json in output_dir."""
        output_dir.mkdir(parents=True, exist_ok=True)
        md_file = output_dir / f"{slug}.md"
        sources_file = output_dir / f"{slug}-sources.json"
        md_file.write_text("# Research Draft\n\nContent here.", encoding="utf-8")
        sources_file.write_text(json.dumps(SAMPLE_SOURCES), encoding="utf-8")
        return md_file, sources_file

    def _run(self, tool, inputs, ctx):
        return _drain(tool.to_notebook(inputs, ctx))

    def test_to_notebook_no_output_dir(self, tmp_path):
        tool = StudioTool()
        ctx = _mock_context(output_dir=tmp_path / "nonexistent")
        result = self._run(tool, ToNotebookInputs(), ctx)
        assert result.ok is False
        assert "No research output found" in result.message

    def test_to_notebook_no_md_files(self, tmp_path):
        output_dir = tmp_path / "research"
        output_dir.mkdir()
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)
        result = self._run(tool, ToNotebookInputs(), ctx)
        assert result.ok is False
        assert "No research output found" in result.message

    def test_to_notebook_no_sources_json_feynman_output(self, tmp_path):
        # Feynman outputs have no -sources.json; to-notebook should still proceed
        # (just push the markdown doc, no URL sources).
        output_dir = tmp_path / "research"
        output_dir.mkdir()
        md_file = output_dir / "test-deep.md"
        md_file.write_text("# Draft", encoding="utf-8")
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch(
            "docent.bundled_plugins.studio._nlm_push",
            new=_make_nlm_push(notebook_id="nb-feynman", sources_added=1),
        ):
            result = self._run(tool, ToNotebookInputs(), ctx)
        assert result.ok is True
        assert result.sources_count == 0
        assert result.sources_added == 1
        assert result.sources_file is None

    def test_to_notebook_creates_notebook_when_no_id(self, tmp_path):
        output_dir = tmp_path / "research"
        md_file, _ = self._write_research_files(output_dir)
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch(
            "docent.bundled_plugins.studio._nlm_push",
            new=_make_nlm_push(notebook_id="new-nb-id", sources_added=2,
                               message="Notebook ready. new-nb-id"),
        ):
            result = self._run(tool, ToNotebookInputs(), ctx)
        assert result.ok is True
        assert "new-nb-id" in result.message
        assert result.sources_added > 0
        pkg = Path(result.package_dir)
        assert (pkg / "sources_urls.txt").exists()
        assert (pkg / md_file.name).exists()

    def test_to_notebook_uses_specified_output_file(self, tmp_path):
        output_dir = tmp_path / "research"
        md_file, _ = self._write_research_files(output_dir, slug="climate-lit")
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch("docent.bundled_plugins.studio._nlm_push", new=_make_nlm_push(notebook_id="nb-x")):
            result = self._run(tool, ToNotebookInputs(output_file=str(md_file)), ctx)
        assert result.ok is True
        assert "climate-lit" in result.output_file

    def test_to_notebook_ranks_papers_first(self, tmp_path):
        output_dir = tmp_path / "research"
        self._write_research_files(output_dir)
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch("docent.bundled_plugins.studio._nlm_push", new=_make_nlm_push(notebook_id="nb-x")):
            result = self._run(tool, ToNotebookInputs(), ctx)
        urls_content = (Path(result.package_dir) / "sources_urls.txt").read_text()
        lines = [l for l in urls_content.strip().splitlines() if l]
        assert "arxiv.org" in lines[0]

    def test_to_notebook_respects_max_sources(self, tmp_path):
        output_dir = tmp_path / "research"
        self._write_research_files(output_dir)
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch("docent.bundled_plugins.studio._nlm_push", new=_make_nlm_push(notebook_id="nb-x")):
            result = self._run(tool, ToNotebookInputs(max_sources=2), ctx)
        assert result.sources_count == 2
        urls_content = (Path(result.package_dir) / "sources_urls.txt").read_text()
        assert len(urls_content.strip().splitlines()) == 2

    def test_to_notebook_pushes_with_existing_notebook_id(self, tmp_path):
        output_dir = tmp_path / "research"
        self._write_research_files(output_dir)
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch(
            "docent.bundled_plugins.studio._nlm_push",
            new=_make_nlm_push(notebook_id="nb-abc123", sources_added=2, sources_failed=0),
        ):
            result = self._run(tool, ToNotebookInputs(notebook_id="nb-abc123"), ctx)
        assert result.ok is True
        assert result.sources_added == 2
        assert result.sources_failed == 0

    def test_to_notebook_exe_not_found_falls_back(self, tmp_path):
        output_dir = tmp_path / "research"
        self._write_research_files(output_dir)
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)
        with (
            patch("docent.bundled_plugins.studio._nlm_push",
                  new=_make_nlm_push(ok=False, notebook_id=None, sources_added=0,
                                     message="NLM not found")),
            patch("webbrowser.open") as mock_browser,
        ):
            result = self._run(tool, ToNotebookInputs(notebook_id="nb-abc123"), ctx)
        assert result.ok is True
        assert result.sources_added == 0
        mock_browser.assert_called_once_with("https://notebooklm.google.com")
        assert "not found" in result.message

    def test_to_notebook_auth_expired_falls_back(self, tmp_path):
        output_dir = tmp_path / "research"
        self._write_research_files(output_dir)
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)
        with (
            patch("docent.bundled_plugins.studio._nlm_push",
                  new=_make_nlm_push(ok=False, notebook_id=None, sources_added=0,
                                     message="Auth expired")),
            patch("webbrowser.open") as mock_browser,
        ):
            result = self._run(tool, ToNotebookInputs(notebook_id="nb-abc123"), ctx)
        assert result.ok is True
        assert result.sources_added == 0
        mock_browser.assert_called_once_with("https://notebooklm.google.com")
        assert "auth expired" in result.message.lower()

    def test_to_notebook_tracks_partial_failures(self, tmp_path):
        output_dir = tmp_path / "research"
        self._write_research_files(output_dir)
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch(
            "docent.bundled_plugins.studio._nlm_push",
            new=_make_nlm_push(notebook_id="nb-abc123", sources_added=1, sources_failed=5),
        ):
            result = self._run(tool, ToNotebookInputs(notebook_id="nb-abc123"), ctx)
        assert result.ok is True
        assert result.sources_added == 1
        assert result.sources_failed > 0

    def test_to_notebook_notebook_id_from_config(self, tmp_path):
        output_dir = tmp_path / "research"
        self._write_research_files(output_dir)
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, notebooklm_notebook_id="config-nb-id")
        with patch(
            "docent.bundled_plugins.studio._nlm_push",
            new=_make_nlm_push(notebook_id="config-nb-id",
                               message="Notebook ready: config-nb-id"),
        ):
            result = self._run(tool, ToNotebookInputs(), ctx)
        assert result.ok is True
        assert "config-nb-id" in result.message


class TestOutputDestinations:
    """Tests for --output local|notebook|vault on deep-research / lit / review."""

    FAKE_MD = "# Research Draft\n\nContent here."

    def _run_deep(self, ctx, extra_inputs=None, feynman_output=None):
        tool = StudioTool()
        output_dir = ctx.settings.research.output_dir.expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        fake_path = output_dir / "test-deep.md"
        fake_path.write_text(self.FAKE_MD, encoding="utf-8")
        inputs = DeepInputs(topic="test topic", **(extra_inputs or {}))
        with patch("docent.bundled_plugins.studio._run_feynman",
                   return_value=(0, feynman_output or str(fake_path), "")):
            return _drain(tool.deep_research(inputs, ctx))

    def test_output_local_default(self, tmp_path):
        ctx = _mock_context(output_dir=tmp_path / "r")
        result = self._run_deep(ctx)
        assert result.ok is True
        assert result.notebook_id is None
        assert result.vault_path is None

    def test_output_notebook_pushes(self, tmp_path):
        output_dir = tmp_path / "r"
        ctx = _mock_context(output_dir=output_dir)
        with patch("docent.bundled_plugins.studio._nlm_push",
                   new=_make_nlm_push(notebook_id="new-nb")):
            result = self._run_deep(ctx, extra_inputs={"output": "notebook"})
        assert result.ok is True
        assert result.notebook_id == "new-nb"
        assert result.vault_path is None

    def test_output_vault_writes_frontmatter(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        ctx = _mock_context(output_dir=tmp_path / "r", obsidian_vault=vault)
        result = self._run_deep(ctx, extra_inputs={"output": "vault"})
        assert result.ok is True
        assert result.vault_path is not None
        note = Path(result.vault_path)
        assert note.exists()
        content = note.read_text(encoding="utf-8")
        assert "tags:" in content
        assert "docent/studio" in content
        assert "date:" in content
        assert "topic:" in content

    def test_output_vault_not_configured(self, tmp_path):
        ctx = _mock_context(output_dir=tmp_path / "r")  # no obsidian_vault
        result = self._run_deep(ctx, extra_inputs={"output": "vault"})
        assert result.ok is True
        assert result.vault_path is None
        assert "obsidian_vault is not configured" in result.message

    def test_output_vault_creates_studio_subfolder(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        ctx = _mock_context(output_dir=tmp_path / "r", obsidian_vault=vault)
        self._run_deep(ctx, extra_inputs={"output": "vault"})
        assert (vault / "Studio").is_dir()


class TestUsageAction:
    def test_usage_zero_spend(self, tmp_path, monkeypatch):
        import docent.bundled_plugins.studio as mod
        import docent.bundled_plugins.studio.oc_client as oc_mod
        monkeypatch.setattr(mod, "_read_daily_spend", lambda: 0.0)
        monkeypatch.setattr(oc_mod, "_read_oc_daily_spend", lambda: 0.0)

        tool = StudioTool()
        ctx = _mock_context()
        result = tool.usage(UsageInputs(), ctx)
        assert isinstance(result, UsageResult)
        assert result.feynman_spend_usd == 0.0
        assert result.oc_spend_usd == 0.0

    def test_usage_shows_correct_spend(self, tmp_path, monkeypatch):
        import docent.bundled_plugins.studio as mod
        import docent.bundled_plugins.studio.oc_client as oc_mod
        monkeypatch.setattr(mod, "_read_daily_spend", lambda: 1.23)
        monkeypatch.setattr(oc_mod, "_read_oc_daily_spend", lambda: 0.45)

        tool = StudioTool()
        ctx = _mock_context()
        result = tool.usage(UsageInputs(), ctx)
        assert isinstance(result, UsageResult)
        assert result.feynman_spend_usd == pytest.approx(1.23)
        assert result.oc_spend_usd == pytest.approx(0.45)


# ---------------------------------------------------------------------------
# Phase E: compare, draft, replicate, audit
# ---------------------------------------------------------------------------

class TestCompareAction:
    def test_compare_feynman_happy_path(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        fake_output = str(output_dir / "2401-12345-vs-2402-67890-compare.md")
        with patch("docent.bundled_plugins.studio._run_feynman", return_value=(0, fake_output, "")):
            result = _drain(
                tool.compare(CompareInputs(artifact_a="2401.12345", artifact_b="2402.67890"), ctx)
            )

        assert result.ok is True
        assert result.workflow == "compare"
        assert "2401.12345" in result.topic_or_artifact
        assert "2402.67890" in result.topic_or_artifact

    def test_compare_feynman_error(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        with patch("docent.bundled_plugins.studio._run_feynman", return_value=(1, None, '{"errorMessage": "{}"}')) :
            result = _drain(
                tool.compare(CompareInputs(artifact_a="2401.12345", artifact_b="2402.67890"), ctx)
            )

        assert result.ok is False
        assert result.backend == "feynman"

    def test_compare_feynman_no_output_file(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        with patch("docent.bundled_plugins.studio._run_feynman", return_value=(0, None, "")):
            result = _drain(
                tool.compare(CompareInputs(artifact_a="2401.12345", artifact_b="2402.67890"), ctx)
            )

        assert result.ok is True
        assert result.output_file is None
        assert "no output file" in result.message

    @patch("docent.bundled_plugins.studio.pipeline.run_compare")
    def test_compare_docent_happy_path(self, mock_run_compare, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)

        mock_run_compare.return_value = _fake_pipeline_gen({
            "ok": True,
            "comparison": "Comparison content",
            "review": "Review content",
            "error": None,
        })

        with patch("docent.bundled_plugins.studio.oc_client.OcClient") as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = True
            MockOc.return_value = mock_oc_instance

            result = _drain(
                tool.compare(CompareInputs(artifact_a="2401.12345", artifact_b="2402.67890", backend="docent"), ctx)
            )

        assert result.ok is True
        assert result.backend == "docent"
        assert result.workflow == "compare"
        assert result.output_file is not None

    def test_compare_inputs_topic_property(self):
        inp = CompareInputs(artifact_a="2401.12345", artifact_b="2402.67890")
        assert inp.topic == "2401.12345 vs 2402.67890"


class TestDraftAction:
    def test_draft_feynman_happy_path(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        fake_output = str(output_dir / "storm-surge-draft.md")
        with patch("docent.bundled_plugins.studio._run_feynman", return_value=(0, fake_output, "")):
            result = _drain(tool.draft(DraftInputs(topic="storm surge modelling"), ctx))

        assert result.ok is True
        assert result.workflow == "draft"
        assert result.topic_or_artifact == "storm surge modelling"

    def test_draft_feynman_error(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        with patch("docent.bundled_plugins.studio._run_feynman", return_value=(1, None, '{"errorMessage": "{}"}')):
            result = _drain(tool.draft(DraftInputs(topic="storm surge modelling"), ctx))

        assert result.ok is False

    @patch("docent.bundled_plugins.studio.pipeline.run_draft")
    def test_draft_docent_happy_path(self, mock_run_draft, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)

        mock_run_draft.return_value = _fake_pipeline_gen({
            "ok": True,
            "draft": "Draft content here",
            "error": None,
        })

        with patch("docent.bundled_plugins.studio.oc_client.OcClient") as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = True
            MockOc.return_value = mock_oc_instance

            result = _drain(
                tool.draft(DraftInputs(topic="storm surge modelling", backend="docent"), ctx)
            )

        assert result.ok is True
        assert result.backend == "docent"
        assert result.workflow == "draft"
        assert result.output_file is not None

    @patch("docent.bundled_plugins.studio.pipeline.run_draft")
    def test_draft_docent_pipeline_error(self, mock_run_draft, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)

        mock_run_draft.return_value = _fake_pipeline_gen({
            "ok": False,
            "draft": "",
            "error": "Writer failed: timeout",
        })

        with patch("docent.bundled_plugins.studio.oc_client.OcClient") as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = True
            MockOc.return_value = mock_oc_instance

            result = _drain(
                tool.draft(DraftInputs(topic="storm surge modelling", backend="docent"), ctx)
            )

        assert result.ok is False
        assert "Writer failed" in result.message


class TestReplicateAction:
    def test_replicate_feynman_happy_path(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        fake_output = str(output_dir / "2401-12345-replicate.md")
        with patch("docent.bundled_plugins.studio._run_feynman", return_value=(0, fake_output, "")):
            result = _drain(tool.replicate(ReplicateInputs(artifact="2401.12345"), ctx))

        assert result.ok is True
        assert result.workflow == "replicate"
        assert result.topic_or_artifact == "2401.12345"

    def test_replicate_feynman_no_output_file(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        with patch("docent.bundled_plugins.studio._run_feynman", return_value=(0, None, "")):
            result = _drain(tool.replicate(ReplicateInputs(artifact="2401.12345"), ctx))

        assert result.ok is True
        assert result.output_file is None

    @patch("docent.bundled_plugins.studio.pipeline.run_replicate")
    def test_replicate_docent_happy_path(self, mock_run_replicate, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)

        mock_run_replicate.return_value = _fake_pipeline_gen({
            "ok": True,
            "guide": "Replication guide content",
            "review": "Review notes",
            "error": None,
        })

        with patch("docent.bundled_plugins.studio.oc_client.OcClient") as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = True
            MockOc.return_value = mock_oc_instance

            result = _drain(
                tool.replicate(ReplicateInputs(artifact="2401.12345", backend="docent"), ctx)
            )

        assert result.ok is True
        assert result.backend == "docent"
        assert result.workflow == "replicate"
        assert result.output_file is not None


class TestAuditAction:
    def test_audit_feynman_happy_path(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        fake_output = str(output_dir / "2401-12345-audit.md")
        with patch("docent.bundled_plugins.studio._run_feynman", return_value=(0, fake_output, "")):
            result = _drain(tool.audit(AuditInputs(artifact="2401.12345"), ctx))

        assert result.ok is True
        assert result.workflow == "audit"
        assert result.topic_or_artifact == "2401.12345"

    def test_audit_feynman_error(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        with patch("docent.bundled_plugins.studio._run_feynman", return_value=(1, None, '{"errorMessage": "{}"}')):
            result = _drain(tool.audit(AuditInputs(artifact="2401.12345"), ctx))

        assert result.ok is False
        assert result.backend == "feynman"

    @patch("docent.bundled_plugins.studio.pipeline.run_audit")
    def test_audit_docent_happy_path(self, mock_run_audit, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)

        mock_run_audit.return_value = _fake_pipeline_gen({
            "ok": True,
            "report": "Audit report content",
            "review": "Reviewer notes",
            "error": None,
        })

        with patch("docent.bundled_plugins.studio.oc_client.OcClient") as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = True
            MockOc.return_value = mock_oc_instance

            result = _drain(
                tool.audit(AuditInputs(artifact="2401.12345", backend="docent"), ctx)
            )

        assert result.ok is True
        assert result.backend == "docent"
        assert result.workflow == "audit"
        assert result.output_file is not None

    @patch("docent.bundled_plugins.studio.pipeline.run_audit")
    def test_audit_docent_pipeline_error(self, mock_run_audit, tmp_path):
        output_dir = tmp_path / "research"
        tool = StudioTool()
        ctx = _mock_context(output_dir=output_dir)

        mock_run_audit.return_value = _fake_pipeline_gen({
            "ok": False,
            "report": "",
            "review": "",
            "error": "Audit failed: timeout",
        })

        with patch("docent.bundled_plugins.studio.oc_client.OcClient") as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = True
            MockOc.return_value = mock_oc_instance

            result = _drain(
                tool.audit(AuditInputs(artifact="2401.12345", backend="docent"), ctx)
            )

        assert result.ok is False
        assert "Audit failed" in result.message
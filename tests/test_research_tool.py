"""Tests for the research tool (Feynman backend)."""
from __future__ import annotations

import inspect
import json
import webbrowser
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from docent.config.settings import ResearchSettings, Settings
from docent.core.context import Context
from docent.core.shapes import ErrorShape, LinkShape, MessageShape
from docent.bundled_plugins.research_to_notebook import (
    ConfigSetInputs,
    ConfigShowInputs,
    ConfigShowResult,
    ConfigSetResult,
    DeepInputs,
    LitInputs,
    ReviewInputs,
    ResearchResult,
    ResearchTool,
    ToNotebookInputs,
    ToNotebookResult,
    _slugify,
    _artifact_slug,
    _rank_sources,
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


def _mock_context(
    *,
    output_dir: Path | None = None,
    feynman_command: list[str] | None = None,
) -> Context:
    research = ResearchSettings(
        output_dir=output_dir or Path("/tmp/docent-test-research"),
        feynman_command=feynman_command,
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


class TestDeepFeynman:
    def test_deep_feynman_happy_path(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        fake_output = str(output_dir / "storm-surge-ghana-deep.md")
        with patch(
            "docent.bundled_plugins.research_to_notebook._run_feynman",
            return_value=(0, fake_output),
        ):
            result = _drain(tool.deep(DeepInputs(topic="storm surge Ghana"), ctx))

        assert result.ok is True
        assert result.backend == "feynman"
        assert result.workflow == "deep"
        assert result.topic_or_artifact == "storm surge Ghana"
        assert result.output_file == fake_output
        assert result.output_file.endswith("storm-surge-ghana-deep.md")
        assert result.returncode == 0

    def test_deep_feynman_no_output_file(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        with patch(
            "docent.bundled_plugins.research_to_notebook._run_feynman",
            return_value=(0, None),
        ):
            result = _drain(tool.deep(DeepInputs(topic="storm surge Ghana"), ctx))

        assert result.ok is True
        assert result.output_file is None
        assert "no output file was found" in result.message

    def test_deep_feynman_nonzero_exit(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        with patch(
            "docent.bundled_plugins.research_to_notebook._run_feynman",
            return_value=(1, None),
        ):
            result = _drain(tool.deep(DeepInputs(topic="storm surge Ghana"), ctx))

        assert result.ok is False
        assert result.returncode == 1
        assert "exited with code 1" in result.message

    def test_deep_docent_backend_server_unavailable(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)

        with patch(
            "docent.bundled_plugins.research_to_notebook.oc_client.OcClient"
        ) as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = False
            MockOc.return_value = mock_oc_instance

            result = _drain(
                tool.deep(DeepInputs(topic="test", backend="docent"), ctx)
            )

        assert isinstance(result, ResearchResult)
        assert result.ok is False
        assert result.backend == "docent"
        assert "not running" in result.message


class TestLitFeynman:
    def test_lit_feynman_happy_path(self, tmp_path):
        output_dir = tmp_path / "research"
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        fake_output = str(output_dir / "climate-change-lit.md")
        with patch(
            "docent.bundled_plugins.research_to_notebook._run_feynman",
            return_value=(0, fake_output),
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
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir, feynman_command=["feynman"])

        fake_output = str(output_dir / "2401-12345-review.md")
        with patch(
            "docent.bundled_plugins.research_to_notebook._run_feynman",
            return_value=(0, fake_output),
        ):
            result = _drain(tool.review(ReviewInputs(artifact="2401.12345"), ctx))

        assert result.ok is True
        assert result.workflow == "review"
        assert result.topic_or_artifact == "2401.12345"
        assert result.output_file is not None
        assert result.output_file.endswith("2401-12345-review.md")


class TestConfigActions:
    def test_config_show(self, tmp_path):
        tool = ResearchTool()
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
        tool = ResearchTool()
        ctx = _mock_context(output_dir=tmp_path)

        with patch("docent.utils.paths.config_file", return_value=Path("/fake/config.toml")):
            result = tool.config_set(ConfigSetInputs(key="bad_key", value="x"), ctx)

        assert result.ok is False
        assert isinstance(result, ConfigSetResult)
        assert "Unknown key" in result.message
        assert "bad_key" in result.message

    def test_config_set_output_dir_happy_path(self, tmp_path):
        tool = ResearchTool()
        ctx = _mock_context(output_dir=tmp_path)
        fake_config = Path("/fake/config.toml")

        with patch("docent.bundled_plugins.research_to_notebook.write_setting", return_value=fake_config) as mock_ws, \
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
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)

        with patch(
            "docent.bundled_plugins.research_to_notebook.oc_client.OcClient"
        ) as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = False
            MockOc.return_value = mock_oc_instance

            result = _drain(
                tool.lit(LitInputs(topic="test", backend="docent"), ctx)
            )

        assert isinstance(result, ResearchResult)
        assert result.ok is False
        assert result.backend == "docent"
        assert "not running" in result.message

    @patch("docent.bundled_plugins.research_to_notebook.pipeline.run_lit")
    def test_lit_docent_happy_path(self, mock_run_lit, tmp_path):
        output_dir = tmp_path / "research"
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)

        mock_run_lit.return_value = {
            "ok": True,
            "topic": "climate change",
            "draft": "Literature review content",
            "review": "Review content",
            "sources": [{"title": "Source 1"}],
            "rounds": 1,
            "error": None,
        }

        with patch(
            "docent.bundled_plugins.research_to_notebook.oc_client.OcClient"
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
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)

        with patch(
            "docent.bundled_plugins.research_to_notebook.oc_client.OcClient"
        ) as MockOc:
            mock_oc_instance = MagicMock()
            mock_oc_instance.is_available.return_value = False
            MockOc.return_value = mock_oc_instance

            result = _drain(
                tool.review(ReviewInputs(artifact="2401.12345", backend="docent"), ctx)
            )

        assert isinstance(result, ResearchResult)
        assert result.ok is False
        assert result.backend == "docent"
        assert "not running" in result.message

    @patch("docent.bundled_plugins.research_to_notebook.pipeline.run_review")
    def test_review_docent_happy_path(self, mock_run_review, tmp_path):
        output_dir = tmp_path / "research"
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)

        mock_run_review.return_value = {
            "ok": True,
            "artifact": "2401.12345",
            "artifact_content": "Paper content",
            "researcher_notes": "Notes",
            "review": "Review content",
            "error": None,
        }

        with patch(
            "docent.bundled_plugins.research_to_notebook.oc_client.OcClient"
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

    def test_to_notebook_no_output_dir(self, tmp_path):
        tool = ResearchTool()
        ctx = _mock_context(output_dir=tmp_path / "nonexistent")
        result = tool.to_notebook(ToNotebookInputs(), ctx)
        assert result.ok is False
        assert "No research output found" in result.message

    def test_to_notebook_no_md_files(self, tmp_path):
        output_dir = tmp_path / "research"
        output_dir.mkdir()
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        result = tool.to_notebook(ToNotebookInputs(), ctx)
        assert result.ok is False
        assert "No research output found" in result.message

    def test_to_notebook_no_sources_json(self, tmp_path):
        output_dir = tmp_path / "research"
        output_dir.mkdir()
        (output_dir / "test-deep.md").write_text("# Draft", encoding="utf-8")
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        result = tool.to_notebook(ToNotebookInputs(), ctx)
        assert result.ok is False
        assert "No sources file" in result.message

    def test_to_notebook_happy_path(self, tmp_path):
        output_dir = tmp_path / "research"
        md_file, _ = self._write_research_files(output_dir)
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch("webbrowser.open") as mock_browser:
            result = tool.to_notebook(ToNotebookInputs(), ctx)
        assert result.ok is True
        assert result.sources_count == len(SAMPLE_SOURCES)
        assert result.package_dir is not None
        pkg = Path(result.package_dir)
        assert (pkg / "sources_urls.txt").exists()
        assert (pkg / "guide.md").exists()
        assert (pkg / md_file.name).exists()
        mock_browser.assert_called_once_with("https://notebooklm.google.com")

    def test_to_notebook_uses_specified_output_file(self, tmp_path):
        output_dir = tmp_path / "research"
        md_file, _ = self._write_research_files(output_dir, slug="climate-lit")
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch("webbrowser.open"):
            result = tool.to_notebook(ToNotebookInputs(output_file=str(md_file)), ctx)
        assert result.ok is True
        assert "climate-lit" in result.output_file

    def test_to_notebook_ranks_papers_first(self, tmp_path):
        output_dir = tmp_path / "research"
        self._write_research_files(output_dir)
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch("webbrowser.open"):
            result = tool.to_notebook(ToNotebookInputs(), ctx)
        urls_content = (Path(result.package_dir) / "sources_urls.txt").read_text()
        lines = [l for l in urls_content.strip().splitlines() if l]
        assert "arxiv.org" in lines[0]

    def test_to_notebook_respects_max_sources(self, tmp_path):
        output_dir = tmp_path / "research"
        self._write_research_files(output_dir)
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch("webbrowser.open"):
            result = tool.to_notebook(ToNotebookInputs(max_sources=2), ctx)
        assert result.sources_count == 2
        urls_content = (Path(result.package_dir) / "sources_urls.txt").read_text()
        assert len(urls_content.strip().splitlines()) == 2
"""Path-traversal / absolute-path denial tests for studio.read_output and save_synthesis."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docent.bundled_plugins.studio import StudioTool
from docent.bundled_plugins.studio.models import ReadOutputInputs, SaveSynthesisInputs
from docent.core.context import Context


@pytest.fixture
def studio():
    return StudioTool()


@pytest.fixture
def ctx():
    return MagicMock(spec=Context)


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """
    Set up isolated directories:
      docent_home/     — DOCENT_HOME, and the approved Docent root
      docent_home/research/  — research output_dir (also approved)
      outside/         — completely outside, should be denied
    """
    docent_home = tmp_path / "docent_home"
    docent_home.mkdir()
    output_dir = docent_home / "research"
    output_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    monkeypatch.setenv("DOCENT_HOME", str(docent_home))
    for key in list(os.environ):
        if key.startswith("DOCENT_") and key != "DOCENT_HOME":
            monkeypatch.delenv(key, raising=False)

    return docent_home, output_dir, outside


def _settings_patch(output_dir: Path):
    settings = MagicMock()
    settings.research.output_dir = output_dir
    return patch("docent.config.load_settings", return_value=settings)


class TestReadOutputPathSecurity:
    def test_absolute_path_outside_home_is_denied(self, studio, ctx, isolated_dirs):
        docent_home, output_dir, outside = isolated_dirs
        target = outside / "secret.txt"
        target.write_text("secret")

        with _settings_patch(output_dir):
            result = studio.read_output(ReadOutputInputs(output_file=str(target)), ctx)

        assert result.ok is False
        assert "Access denied" in result.message

    def test_dotdot_traversal_out_of_output_dir_is_denied(self, studio, ctx, isolated_dirs):
        docent_home, output_dir, outside = isolated_dirs
        # Looks like it's inside output_dir but resolves outside
        traversal = str(output_dir / ".." / ".." / "outside" / "passwd")

        with _settings_patch(output_dir):
            result = studio.read_output(ReadOutputInputs(output_file=traversal), ctx)

        assert result.ok is False
        assert "Access denied" in result.message

    def test_file_inside_output_dir_is_allowed(self, studio, ctx, isolated_dirs):
        docent_home, output_dir, outside = isolated_dirs
        good = output_dir / "report.md"
        good.write_text("# Report")

        with _settings_patch(output_dir):
            result = studio.read_output(ReadOutputInputs(output_file=str(good)), ctx)

        assert result.ok is True
        assert "# Report" in result.content

    def test_file_inside_docent_home_is_allowed(self, studio, ctx, isolated_dirs):
        docent_home, output_dir, outside = isolated_dirs
        home_file = docent_home / "data" / "cache.md"
        home_file.parent.mkdir(parents=True, exist_ok=True)
        home_file.write_text("# Cache")

        with _settings_patch(output_dir):
            result = studio.read_output(ReadOutputInputs(output_file=str(home_file)), ctx)

        assert result.ok is True

    def test_missing_file_inside_output_dir_returns_not_found(self, studio, ctx, isolated_dirs):
        docent_home, output_dir, outside = isolated_dirs
        missing = output_dir / "missing.md"

        with _settings_patch(output_dir):
            result = studio.read_output(ReadOutputInputs(output_file=str(missing)), ctx)

        assert result.ok is False
        assert "not found" in result.message.lower()


class TestSaveSynthesisPathSecurity:
    def test_source_outside_approved_root_is_denied(self, studio, ctx, isolated_dirs):
        docent_home, output_dir, outside = isolated_dirs
        evil_source = outside / "source.md"
        evil_source.write_text("evil source")

        with _settings_patch(output_dir):
            result = studio.save_synthesis(
                SaveSynthesisInputs(
                    source_output_file=str(evil_source),
                    content="synthesis",
                    summary="brief",
                ),
                ctx,
            )

        assert result.ok is False
        assert "Access denied" in result.message

    def test_dotdot_traversal_in_source_is_denied(self, studio, ctx, isolated_dirs):
        docent_home, output_dir, outside = isolated_dirs
        traversal = str(output_dir / ".." / ".." / "outside" / "source.md")

        with _settings_patch(output_dir):
            result = studio.save_synthesis(
                SaveSynthesisInputs(
                    source_output_file=traversal,
                    content="synthesis",
                    summary="brief",
                ),
                ctx,
            )

        assert result.ok is False
        assert "Access denied" in result.message

    def test_source_inside_output_dir_saves_synthesis(self, studio, ctx, isolated_dirs):
        docent_home, output_dir, outside = isolated_dirs
        source = output_dir / "report-free.md"
        source.write_text("original")

        with _settings_patch(output_dir):
            result = studio.save_synthesis(
                SaveSynthesisInputs(
                    source_output_file=str(source),
                    content="synthesis content",
                    summary="brief summary",
                ),
                ctx,
            )

        assert result.ok is True
        saved = Path(result.saved_file)
        assert saved.exists()
        assert saved.parent == output_dir
        assert saved.read_text() == "synthesis content"

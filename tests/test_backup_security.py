"""Tests for backup archive creation and restoration, with focus on path traversal prevention."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from docent.bundled_plugins.backup.manager import (
    create_archive,
    restore_archive,
    read_manifest,
)


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "docent_home"
    home.mkdir()
    (home / "config.toml").write_text("[reading]\n")
    data = home / "data" / "reading"
    data.mkdir(parents=True)
    (data / "queue.json").write_text("[]")
    return home


@pytest.fixture
def fake_research(tmp_path):
    rd = tmp_path / "research_output"
    rd.mkdir()
    (rd / "draft.md").write_text("# Draft")
    return rd


def _craft_malicious_zip(tmp_path: Path, prefix: str, traversal: str) -> Path:
    """Build a zip with a path-traversal entry."""
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(f"{prefix}/{traversal}", "pwned")
    return archive


class TestPathTraversal:
    def test_home_dotdot_blocked(self, tmp_path, fake_home):
        archive = _craft_malicious_zip(tmp_path, "home", "../../outside.txt")
        with pytest.raises(ValueError, match="resolves outside docent home"):
            restore_archive(archive, dest_home=fake_home)
        assert not (tmp_path / "outside.txt").exists()

    def test_research_dotdot_blocked(self, tmp_path, fake_home, fake_research, monkeypatch):
        archive = _craft_malicious_zip(tmp_path, "research", "../../outside.txt")
        monkeypatch.setattr(
            "docent.bundled_plugins.backup.manager._research_output_dir",
            lambda: fake_research,
        )
        with pytest.raises(ValueError, match="resolves outside research dir"):
            restore_archive(archive, dest_home=fake_home)
        assert not (tmp_path / "outside.txt").exists()

    def test_absolute_path_in_home_blocked(self, tmp_path, fake_home):
        archive = tmp_path / "evil.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("home/../../../tmp/evil.txt", "pwned")
        with pytest.raises(ValueError, match="resolves outside docent home"):
            restore_archive(archive, dest_home=fake_home)

    def test_legitimate_nested_path_allowed(self, tmp_path, fake_home):
        archive = tmp_path / "good.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("home/data/reading/queue.json", "[]")
        restore_archive(archive, dest_home=fake_home)
        assert (fake_home / "data" / "reading" / "queue.json").read_text() == "[]"


class TestDecompressionBomb:
    def test_oversized_entry_rejected(self, tmp_path, fake_home, monkeypatch):
        # Shrink the cap so we don't have to write 100 MB to trip the guard.
        monkeypatch.setattr(
            "docent.bundled_plugins.backup.manager.MAX_FILE_BYTES", 16
        )
        archive = tmp_path / "bomb.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("home/data/big.bin", b"x" * 1024)  # > 16-byte cap
        with pytest.raises(ValueError, match="exceeds the .* limit"):
            restore_archive(archive, dest_home=fake_home)
        assert not (fake_home / "data" / "big.bin").exists()

    def test_under_cap_entry_allowed(self, tmp_path, fake_home, monkeypatch):
        monkeypatch.setattr(
            "docent.bundled_plugins.backup.manager.MAX_FILE_BYTES", 1024
        )
        archive = tmp_path / "ok.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("home/data/small.bin", b"x" * 8)
        restore_archive(archive, dest_home=fake_home)
        assert (fake_home / "data" / "small.bin").read_bytes() == b"x" * 8


class TestRoundTrip:
    def test_create_and_restore(self, tmp_path, fake_home, monkeypatch):
        monkeypatch.setattr(
            "docent.bundled_plugins.backup.manager._docent_home", lambda: fake_home
        )
        monkeypatch.setattr(
            "docent.bundled_plugins.backup.manager._research_output_dir", lambda: None
        )
        archive = tmp_path / "backup.zip"
        manifest = create_archive(archive)
        assert manifest["files_included"] >= 2
        assert archive.exists()

        dest = tmp_path / "restored_home"
        dest.mkdir()
        restore_archive(archive, dest_home=dest)
        assert (dest / "config.toml").read_text() == "[reading]\n"
        assert (dest / "data" / "reading" / "queue.json").read_text() == "[]"

    def test_manifest_readable(self, tmp_path, fake_home, monkeypatch):
        monkeypatch.setattr(
            "docent.bundled_plugins.backup.manager._docent_home", lambda: fake_home
        )
        monkeypatch.setattr(
            "docent.bundled_plugins.backup.manager._research_output_dir", lambda: None
        )
        archive = tmp_path / "backup.zip"
        create_archive(archive)
        m = read_manifest(archive)
        assert "timestamp" in m
        assert "docent_version" in m

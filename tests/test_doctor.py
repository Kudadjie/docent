"""Tests for docent doctor and setup CLI commands."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docent.cli import (
    _check_cli_tool,
    _check_mendeley_mcp,
    _check_profile,
    _check_reading_db,
    _check_semantic_scholar,
    _check_tavily,
    _dir_size_gb,
)
from docent.config.settings import ReadingSettings, ResearchSettings, Settings


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_settings(
    *,
    tavily_key: str | None = None,
    ss_key: str | None = None,
    db_dir: str | None = None,
    mendeley_cmd: list[str] | None = None,
) -> Settings:
    rs = ResearchSettings(tavily_api_key=tavily_key, semantic_scholar_api_key=ss_key)
    reading = ReadingSettings(
        database_dir=Path(db_dir) if db_dir else None,
        mendeley_mcp_command=mendeley_cmd,
    )
    return Settings(research=rs, reading=reading)


# ─── _check_profile ───────────────────────────────────────────────────────────

def test_check_profile_ok(tmp_path: Path) -> None:
    user_file = tmp_path / "user.json"
    user_file.write_text(
        json.dumps({"name": "Ada Lovelace", "level": "PhD", "program": "Mathematics"}),
        encoding="utf-8",
    )
    label, status, version, detail = _check_profile(user_file)
    assert status == "OK"
    assert "Ada Lovelace" in detail
    assert "PhD" in detail


def test_check_profile_missing_file(tmp_path: Path) -> None:
    label, status, _version, detail = _check_profile(tmp_path / "no_user.json")
    assert status == "WARN"
    assert "docent setup" in detail


def test_check_profile_empty_name(tmp_path: Path) -> None:
    user_file = tmp_path / "user.json"
    user_file.write_text(json.dumps({"name": "", "level": "PhD"}), encoding="utf-8")
    label, status, _version, _detail = _check_profile(user_file)
    assert status == "WARN"


# ─── _check_cli_tool ──────────────────────────────────────────────────────────

def test_check_cli_tool_ok() -> None:
    mock_result = MagicMock()
    mock_result.stdout = "3.11.9\n"
    mock_result.stderr = ""
    with patch("shutil.which", return_value="/usr/bin/python"), \
         patch("subprocess.run", return_value=mock_result):
        label, status, version, detail = _check_cli_tool("Python", ["python", "--version"], "install hint")
    assert status == "OK"
    assert "3.11.9" in version


def test_check_cli_tool_not_found() -> None:
    with patch("shutil.which", return_value=None):
        label, status, version, detail = _check_cli_tool("mytool", ["mytool", "--version"], "install mytool")
    assert status == "FAIL"
    assert "install mytool" in detail


def test_check_cli_tool_timeout() -> None:
    with patch("shutil.which", return_value="/usr/bin/mytool"), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="mytool", timeout=8)):
        label, status, version, detail = _check_cli_tool("mytool", ["mytool", "--version"], "hint")
    assert status == "WARN"
    assert "timed out" in detail


# ─── _check_tavily ────────────────────────────────────────────────────────────

def test_check_tavily_key_set() -> None:
    settings = _make_settings(tavily_key="tvly-abcdefghijklmnop")
    label, status, _version, detail = _check_tavily(settings)
    assert status == "OK"
    assert "configured" in detail


def test_check_tavily_key_missing() -> None:
    settings = _make_settings()
    label, status, _version, detail = _check_tavily(settings)
    assert status == "WARN"
    assert "tavily.com" in detail


# ─── _check_semantic_scholar ──────────────────────────────────────────────────

def test_check_semantic_scholar_skip() -> None:
    settings = _make_settings()
    label, status, _version, detail = _check_semantic_scholar(settings)
    assert status == "SKIP"
    assert "optional" in detail.lower()


def test_check_semantic_scholar_ok() -> None:
    settings = _make_settings(ss_key="abc123")
    label, status, _version, _detail = _check_semantic_scholar(settings)
    assert status == "OK"


# ─── _check_reading_db ────────────────────────────────────────────────────────

def test_check_reading_db_ok(tmp_path: Path) -> None:
    settings = _make_settings(db_dir=str(tmp_path))
    label, status, _version, detail = _check_reading_db(settings)
    assert status == "OK"
    assert str(tmp_path) in detail


def test_check_reading_db_not_configured() -> None:
    settings = _make_settings()
    label, status, _version, detail = _check_reading_db(settings)
    assert status == "WARN"
    assert "Not configured" in detail


def test_check_reading_db_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent"
    settings = _make_settings(db_dir=str(missing))
    label, status, _version, detail = _check_reading_db(settings)
    assert status == "WARN"
    assert "does not exist" in detail


# ─── _check_mendeley_mcp ──────────────────────────────────────────────────────

def test_check_mendeley_mcp_ok() -> None:
    settings = _make_settings()
    with patch("shutil.which", return_value="/usr/bin/uvx"):
        label, status, _version, detail = _check_mendeley_mcp(settings)
    assert status == "OK"
    assert "found" in detail


def test_check_mendeley_mcp_not_found() -> None:
    settings = _make_settings()
    with patch("shutil.which", return_value=None):
        label, status, _version, detail = _check_mendeley_mcp(settings)
    assert status == "FAIL"
    assert "not found" in detail


# ─── _dir_size_gb ─────────────────────────────────────────────────────────────

def test_dir_size_gb_empty(tmp_path: Path) -> None:
    result = _dir_size_gb(tmp_path)
    assert result == pytest.approx(0.0, abs=1e-9)


def test_dir_size_gb_nonexistent(tmp_path: Path) -> None:
    result = _dir_size_gb(tmp_path / "missing")
    assert result is None


def test_dir_size_gb_with_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"x" * 1024)
    (tmp_path / "b.txt").write_bytes(b"y" * 2048)
    result = _dir_size_gb(tmp_path)
    assert result is not None
    assert result == pytest.approx(3072 / (1024 ** 3), rel=0.01)

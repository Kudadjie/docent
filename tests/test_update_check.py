"""Tests for the update check utility."""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from docent.utils.update_check import (
    UpdateInfo,
    _is_newer,
    _load_cache,
    _save_cache,
    check_npm,
    check_github_release,
)


def test_is_newer_detects_patch():
    assert _is_newer("1.0.0", "1.0.1") is True


def test_is_newer_same_version():
    assert _is_newer("1.2.3", "1.2.3") is False


def test_is_newer_none_current():
    assert _is_newer(None, "1.0.0") is True


def test_is_newer_older_latest():
    assert _is_newer("2.0.0", "1.9.9") is False


def test_load_cache_miss_on_stale_date(tmp_path: Path):
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    cache_file = tmp_path / "test.json"
    cache_file.write_text(json.dumps({"latest": "2.0.0", "fetched": yesterday}), encoding="utf-8")
    assert _load_cache(cache_file) is None


def test_load_cache_hit_today(tmp_path: Path):
    today = datetime.date.today().isoformat()
    cache_file = tmp_path / "test.json"
    data = {"latest": "2.0.0", "fetched": today}
    cache_file.write_text(json.dumps(data), encoding="utf-8")
    result = _load_cache(cache_file)
    assert result is not None
    assert result["latest"] == "2.0.0"


def test_check_npm_returns_update_when_newer(tmp_path: Path):
    with patch("docent.utils.update_check._fetch_npm_latest", return_value="9.9.9"):
        result = check_npm("feynman", current_version="1.0.0", cache_dir=tmp_path)
    assert result is not None
    assert result.latest == "9.9.9"
    assert result.current == "1.0.0"
    assert result.tool == "feynman"


def test_check_npm_returns_none_when_current(tmp_path: Path):
    with patch("docent.utils.update_check._fetch_npm_latest", return_value="1.0.0"):
        result = check_npm("feynman", current_version="1.0.0", cache_dir=tmp_path)
    assert result is None


def test_check_npm_uses_cache(tmp_path: Path):
    today = datetime.date.today().isoformat()
    cache_dir = tmp_path / "updates"
    cache_dir.mkdir()
    cache_file = cache_dir / "feynman.json"
    cache_file.write_text(json.dumps({"latest": "2.0.0", "fetched": today}), encoding="utf-8")

    with patch("docent.utils.update_check._fetch_npm_latest") as mock_fetch:
        result = check_npm("feynman", current_version="1.0.0", cache_dir=cache_dir)
        mock_fetch.assert_not_called()

    assert result is not None
    assert result.latest == "2.0.0"


def test_check_npm_silent_on_network_failure(tmp_path: Path):
    with patch("docent.utils.update_check._fetch_npm_latest", return_value=None):
        result = check_npm("feynman", current_version="1.0.0", cache_dir=tmp_path)
    assert result is None
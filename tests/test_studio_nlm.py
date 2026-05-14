"""Unit tests for NotebookLM CLI helpers in the studio plugin."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from docent.bundled_plugins.studio._notebook import (
    _nlm_auth_ok,
    _nlm_create_notebook,
    _nlm_add_source,
    _nlm_run,
    _nlm_exe,
)


# ---------------------------------------------------------------------------
# _nlm_run
# ---------------------------------------------------------------------------

class TestNlmRun:
    def test_returns_minus1_when_exe_not_found(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_exe", return_value=None):
            rc, out, err = _nlm_run(["list"])
        assert rc == -1
        assert "not found" in err

    def test_captures_stdout_and_stderr(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_exe", return_value="/bin/notebooklm"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"notebooks": []}'
            mock_run.return_value.stderr = ""
            rc, out, err = _nlm_run(["list", "--json"])
        assert rc == 0
        assert out == '{"notebooks": []}'

    def test_returns_minus1_on_timeout(self):
        import subprocess
        with patch("docent.bundled_plugins.studio._notebook._nlm_exe", return_value="/bin/notebooklm"), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["notebooklm"], 30)):
            rc, out, err = _nlm_run(["list"], timeout=30)
        assert rc == -1
        assert "Timeout" in err

    def test_returns_minus1_on_os_error(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_exe", return_value="/bin/notebooklm"), \
             patch("subprocess.run", side_effect=OSError("permission denied")):
            rc, out, err = _nlm_run(["list"])
        assert rc == -1
        assert "permission denied" in err


# ---------------------------------------------------------------------------
# _nlm_auth_ok
# ---------------------------------------------------------------------------

class TestNlmAuthOk:
    def test_returns_false_when_exe_not_found(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_exe", return_value=None):
            assert _nlm_auth_ok() is False

    def test_returns_false_on_nonzero_returncode(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run", return_value=(1, "", "auth error")):
            assert _nlm_auth_ok() is False

    def test_returns_true_when_list_succeeds_with_array(self):
        notebooks = [{"id": "nb1", "title": "My Notebook"}]
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(0, json.dumps(notebooks), "")):
            assert _nlm_auth_ok() is True

    def test_returns_true_when_list_returns_empty_array(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(0, "[]", "")):
            assert _nlm_auth_ok() is True

    def test_returns_false_when_response_has_error_flag(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(0, json.dumps({"error": True, "message": "not logged in"}), "")):
            assert _nlm_auth_ok() is False

    def test_returns_false_on_invalid_json(self):
        # Unparseable output is treated conservatively as auth failure
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(0, "not json", "")):
            assert _nlm_auth_ok() is False


# ---------------------------------------------------------------------------
# _nlm_create_notebook
# ---------------------------------------------------------------------------

class TestNlmCreateNotebook:
    def test_returns_id_from_json_response(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(0, json.dumps({"id": "abc123"}), "")):
            result = _nlm_create_notebook("My Notebook")
        assert result == "abc123"

    def test_accepts_notebook_id_key(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(0, json.dumps({"notebook_id": "xyz789"}), "")):
            result = _nlm_create_notebook("My Notebook")
        assert result == "xyz789"

    def test_returns_none_on_nonzero_returncode(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(1, "", "failed")):
            result = _nlm_create_notebook("My Notebook")
        assert result is None

    def test_returns_none_on_invalid_json(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(0, "not json", "")):
            result = _nlm_create_notebook("My Notebook")
        assert result is None

    def test_passes_title_and_json_flag(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(0, json.dumps({"id": "nb1"}), "")) as mock_run:
            _nlm_create_notebook("Storm Surge Research")
        args = mock_run.call_args[0][0]
        assert "create" in args
        assert "Storm Surge Research" in args
        assert "--json" in args


# ---------------------------------------------------------------------------
# _nlm_add_source
# ---------------------------------------------------------------------------

class TestNlmAddSource:
    def test_returns_zero_on_success(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(0, "", "")):
            rc, err = _nlm_add_source("https://example.com", "nb123")
        assert rc == 0
        assert err == ""

    def test_returns_nonzero_on_failure(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(1, "", "source add failed")):
            rc, err = _nlm_add_source("https://bad.com", "nb123")
        assert rc == 1
        assert "failed" in err

    def test_passes_notebook_id_flag(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(0, "", "")) as mock_run:
            _nlm_add_source("https://example.com", "my-notebook-id")
        args = mock_run.call_args[0][0]
        assert "-n" in args
        assert "my-notebook-id" in args

    def test_passes_json_flag(self):
        with patch("docent.bundled_plugins.studio._notebook._nlm_run",
                   return_value=(0, "", "")) as mock_run:
            _nlm_add_source("https://example.com", "nb123")
        args = mock_run.call_args[0][0]
        assert "--json" in args

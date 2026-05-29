"""NotebookLM source-add error surfacing, notebook existence check, and stale-id
forgetting — the pieces that fix "synthesis doc failed" against a deleted notebook.
"""
from __future__ import annotations

import docent.bundled_plugins.studio._notebook as nb


# ── _extract_cli_error ─────────────────────────────────────────────────────────

def test_extract_cli_error_from_stdout_json():
    assert nb._extract_cli_error('{"error": "notebook not found"}', "") == "notebook not found"


def test_extract_cli_error_message_key():
    assert nb._extract_cli_error('{"message": "bad request"}', "") == "bad request"


def test_extract_cli_error_stderr_fallback():
    assert nb._extract_cli_error("", "boom on stderr") == "boom on stderr"


def test_extract_cli_error_unknown_when_blank():
    assert nb._extract_cli_error("", "") == "unknown error"


# ── _nlm_add_source ────────────────────────────────────────────────────────────

def test_add_source_success_returns_empty_error(monkeypatch):
    monkeypatch.setattr(nb, "_nlm_run", lambda *a, **k: (0, '{"ok": true}', ""))
    assert nb._nlm_add_source("x", "nb1") == (0, "")


def test_add_source_failure_surfaces_stdout_error(monkeypatch):
    # The CLI reports the failure in stdout JSON, not stderr — must not be blank.
    monkeypatch.setattr(
        nb, "_nlm_run", lambda *a, **k: (1, '{"error": "notebook 01842 not found"}', "")
    )
    rc, err = nb._nlm_add_source("x", "nb1")
    assert rc == 1
    assert "not found" in err


# ── _nlm_notebook_exists ───────────────────────────────────────────────────────

def test_notebook_exists_true_on_rc0(monkeypatch):
    monkeypatch.setattr(nb, "_nlm_run", lambda *a, **k: (0, '{"sources": []}', ""))
    assert nb._nlm_notebook_exists("nb1") is True


def test_notebook_exists_false_on_failure(monkeypatch):
    monkeypatch.setattr(nb, "_nlm_run", lambda *a, **k: (1, "", "not found"))
    assert nb._nlm_notebook_exists("nb1") is False


# ── _forget_notebook ───────────────────────────────────────────────────────────

def test_forget_removes_matching_map_entry(tmp_path):
    nb._save_notebook_map(tmp_path, "stem1", "id-123")
    assert nb._read_notebook_map(tmp_path).get("stem1") == "id-123"
    nb._forget_notebook(tmp_path, "stem1", "id-123", from_config=False)
    assert "stem1" not in nb._read_notebook_map(tmp_path)


def test_forget_keeps_other_entries(tmp_path):
    nb._save_notebook_map(tmp_path, "stem1", "id-1")
    nb._save_notebook_map(tmp_path, "stem2", "id-2")
    nb._forget_notebook(tmp_path, "stem1", "id-1", from_config=False)
    m = nb._read_notebook_map(tmp_path)
    assert "stem1" not in m
    assert m.get("stem2") == "id-2"


def test_forget_clears_config_when_from_config(monkeypatch, tmp_path):
    calls = []
    import docent.config as cfg
    monkeypatch.setattr(cfg, "write_setting", lambda k, v: calls.append((k, v)))
    nb._forget_notebook(tmp_path, "stem1", "id-1", from_config=True)
    assert ("research.notebooklm_notebook_id", "") in calls


def test_forget_does_not_clear_config_when_from_map(monkeypatch, tmp_path):
    calls = []
    import docent.config as cfg
    monkeypatch.setattr(cfg, "write_setting", lambda k, v: calls.append((k, v)))
    nb._save_notebook_map(tmp_path, "stem1", "id-1")
    nb._forget_notebook(tmp_path, "stem1", "id-1", from_config=False)
    assert calls == []

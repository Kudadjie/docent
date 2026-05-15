"""Tests for Executor: happy path, non-zero exit, timeout + process-group kill."""
from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, call, patch

import pytest

from docent.execution.executor import Executor, ProcessExecutionError, _kill_tree


# ─── happy path ───────────────────────────────────────────────────────────────

def test_run_returns_process_result():
    ex = Executor()
    result = ex.run([sys.executable, "-c", "print('hello')"])
    assert result.returncode == 0
    assert "hello" in result.stdout
    assert result.duration >= 0


def test_run_captures_stderr():
    ex = Executor()
    result = ex.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('err')"],
        check=False,
    )
    assert "err" in result.stderr


def test_run_nonzero_no_raise_when_check_false():
    ex = Executor()
    result = ex.run([sys.executable, "-c", "raise SystemExit(2)"], check=False)
    assert result.returncode == 2


def test_run_nonzero_raises_when_check_true():
    ex = Executor()
    with pytest.raises(ProcessExecutionError) as exc_info:
        ex.run([sys.executable, "-c", "raise SystemExit(3)"])
    assert exc_info.value.result.returncode == 3
    assert "3" in str(exc_info.value)


# ─── timeout ──────────────────────────────────────────────────────────────────

def test_run_timeout_raises_timeout_expired():
    ex = Executor()
    with pytest.raises(subprocess.TimeoutExpired):
        ex.run([sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.1)


def test_run_timeout_calls_kill_tree():
    """On timeout, _kill_tree must be called before re-raising TimeoutExpired."""
    mock_proc = MagicMock()
    mock_proc.__enter__ = lambda s: s
    mock_proc.__exit__ = MagicMock(return_value=False)
    mock_proc.communicate.side_effect = [subprocess.TimeoutExpired(cmd=[], timeout=1), ("", "")]
    mock_proc.returncode = -1

    with patch("docent.execution.executor.subprocess.Popen", return_value=mock_proc), \
         patch("docent.execution.executor._kill_tree") as mock_kill:
        with pytest.raises(subprocess.TimeoutExpired):
            Executor().run(["dummy"], timeout=1)
        mock_kill.assert_called_once_with(mock_proc)


# ─── _kill_tree ───────────────────────────────────────────────────────────────

def test_kill_tree_on_posix_calls_proc_kill():
    mock_proc = MagicMock()
    with patch("docent.execution.executor.sys") as mock_sys:
        mock_sys.platform = "linux"
        _kill_tree(mock_proc)
    mock_proc.kill.assert_called_once()


def test_kill_tree_on_windows_sends_ctrl_break():
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    with patch("docent.execution.executor.sys") as mock_sys, \
         patch("docent.execution.executor.os.kill") as mock_os_kill, \
         patch("docent.execution.executor.signal") as mock_signal:
        mock_sys.platform = "win32"
        mock_signal.CTRL_BREAK_EVENT = 1
        _kill_tree(mock_proc)
    mock_os_kill.assert_called_once_with(12345, 1)


def test_kill_tree_on_windows_falls_back_on_oserror():
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    with patch("docent.execution.executor.sys") as mock_sys, \
         patch("docent.execution.executor.os.kill", side_effect=OSError("denied")), \
         patch("docent.execution.executor.signal") as mock_signal:
        mock_sys.platform = "win32"
        mock_signal.CTRL_BREAK_EVENT = 1
        _kill_tree(mock_proc)
    mock_proc.kill.assert_called_once()

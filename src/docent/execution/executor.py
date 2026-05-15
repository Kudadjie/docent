from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration: float


class ProcessExecutionError(RuntimeError):
    """Raised by `Executor.run` when `check=True` and the process exits non-zero."""

    def __init__(self, result: ProcessResult) -> None:
        self.result = result
        super().__init__(
            f"Command {result.args!r} exited with {result.returncode} "
            f"after {result.duration:.2f}s"
        )


# On Windows, launch child processes in their own process group so that a
# timeout can kill the entire tree (including grandchildren like pandoc workers)
# rather than only the direct child.  On POSIX, no special flag is needed —
# proc.kill() sends SIGKILL to the process which the kernel propagates.
_CREATION_FLAGS = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill `proc` and its entire process subtree."""
    if sys.platform == "win32":
        try:
            # CTRL_BREAK_EVENT targets the whole console process group.
            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
        except (OSError, AttributeError):
            proc.kill()
    else:
        proc.kill()


class Executor:
    """Run external commands and return structured results.

    Commands are always given as `list[str]` - never a shell string - so there
    is no shell-injection surface. For tools that truly need shell features,
    pass `["bash", "-c", "..."]` (or `["cmd", "/c", "..."]`) explicitly.
    """

    def run(
        self,
        args: list[str],
        *,
        timeout: float | None = None,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> ProcessResult:
        start = time.perf_counter()

        with subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env,
            creationflags=_CREATION_FLAGS,
        ) as proc:
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                proc.communicate()  # drain so the Popen context manager can clean up
                raise

        duration = time.perf_counter() - start
        result = ProcessResult(
            args=list(args),
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            duration=duration,
        )

        if check and proc.returncode != 0:
            raise ProcessExecutionError(result)

        return result

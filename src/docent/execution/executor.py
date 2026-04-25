from __future__ import annotations

import subprocess
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
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
            check=False,
        )
        duration = time.perf_counter() - start

        result = ProcessResult(
            args=list(args),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration=duration,
        )

        if check and completed.returncode != 0:
            raise ProcessExecutionError(result)

        return result

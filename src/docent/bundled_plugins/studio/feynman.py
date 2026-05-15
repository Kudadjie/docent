"""Feynman CLI wrapper: error classes, executable resolution, spend tracking, runner."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from docent.errors import ToolNotFoundError, UsageLimitError


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class FeynmanBudgetExceededError(UsageLimitError):
    """Raised when Feynman session spend reaches 90% of the configured budget."""


class FeynmanNotFoundError(ToolNotFoundError):
    """Raised when the feynman executable cannot be found on PATH or known locations."""

    def __init__(self, cmd: list[str], details: str = "") -> None:
        self.cmd = cmd
        msg = (
            f"Feynman executable not found: {cmd[0]!r}. "
            f"Install with: npm install -g @companion-ai/feynman\n"
            f"Or set the full path via: "
            f"docent studio config-set --key feynman_command --value <path-to-feynman>"
        )
        if details:
            msg += f"\nDetails: {details}"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Spend tracking
# ---------------------------------------------------------------------------

def _spend_file() -> Path:
    from docent.utils.paths import cache_dir
    return cache_dir() / "research" / "feynman_spend.json"


def _read_daily_spend() -> float:
    """Return today's accumulated Feynman spend in USD. Resets automatically at midnight."""
    import datetime
    today = datetime.date.today().isoformat()
    try:
        data = json.loads(_spend_file().read_text(encoding="utf-8"))
        if data.get("date") == today:
            return float(data.get("spend_usd", 0.0))
    except Exception:
        pass
    return 0.0


def _write_daily_spend(spend: float) -> None:
    """Persist today's accumulated Feynman spend to disk."""
    import datetime
    p = _spend_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"date": datetime.date.today().isoformat(), "spend_usd": round(spend, 6)}),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Executable resolution
# ---------------------------------------------------------------------------

def _find_feynman(configured_command: list[str] | None) -> list[str]:
    """Resolve the feynman executable, with Windows npm path detection.

    Resolution order:
    1. If the user explicitly set feynman_command in config, use it as-is.
    2. Try ``shutil.which("feynman")`` (works on Linux/Mac and Windows
       if the npm bin is on PATH).
    3. Fall back to the standard Windows npm global bin location:
       ``%APPDATA%\\npm\\feynman.cmd``.

    Raises FeynmanNotFoundError if no executable is found.
    """
    if configured_command:
        resolved = shutil.which(configured_command[0])
        if resolved:
            return [resolved] + configured_command[1:]
        raise FeynmanNotFoundError(
            configured_command,
            f"Configured command {configured_command[0]!r} not found on PATH.",
        )

    resolved = shutil.which("feynman")
    if resolved:
        return [resolved]

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        npm_feynman = Path(appdata) / "npm" / "feynman.cmd"
        if npm_feynman.is_file():
            return [str(npm_feynman)]

    raise FeynmanNotFoundError(["feynman"])


def _feynman_version_from_package_json(cmd: list[str]) -> str:
    """Read feynman version from its npm package.json — no subprocess, instant.

    Checks both the bare ``feynman`` and scoped ``@companion-ai/feynman`` layouts.
    Returns "?" if the file cannot be found or parsed.
    """
    path = Path(cmd[0]).resolve()
    npm_roots = [
        path.parent / "node_modules",
        path.parent.parent / "lib" / "node_modules",
    ]
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        npm_roots.append(Path(appdata) / "npm" / "node_modules")
    for root in npm_roots:
        for pkg_path in (
            root / "feynman" / "package.json",
            root / "@companion-ai" / "feynman" / "package.json",
        ):
            try:
                data = json.loads(pkg_path.read_text(encoding="utf-8"))
                v = data.get("version")
                if v:
                    return str(v)
            except Exception:
                pass
    return "?"


def _extract_feynman_cost(output: str) -> float:
    """Parse Feynman's stdout/stderr for a cost line. Returns 0.0 if not found."""
    match = re.search(r'\$(\d+(?:\.\d+)?)', output)
    return float(match.group(1)) if match else 0.0


# ---------------------------------------------------------------------------
# Error message helpers
# ---------------------------------------------------------------------------

def _model_note(last_model: str | None, configured_model: str | None) -> str:
    """Build a human-readable model note for error messages."""
    if configured_model:
        actual = f"`{last_model}`" if last_model else "unknown"
        return f"\n  Docent configured: `{configured_model}`\n  Feynman attempted: {actual}"
    if last_model:
        return f"\n  Model attempted: `{last_model}` (feynman default)"
    return "\n  Model attempted: unknown (feynman default)"


def _summarize_feynman_error(stderr: str, configured_model: str | None = None) -> str:
    """Parse feynman's JSON session stream and extract a user-friendly error summary."""
    _DOCS_LINK = "https://feynman.is/docs"
    _DOCS_FOOTER = (
        f"Docs: {_DOCS_LINK}\n"
        f"\n"
        f"Adjust Feynman settings via its CLI in a separate terminal.\n"
        f"See {_DOCS_LINK} for more Feynman-native options."
    )

    last_model = None
    last_error_raw = None

    for line in reversed(stderr.splitlines()):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(obj.get("model"), str):
            last_model = last_model or obj["model"]
        err = obj.get("errorMessage")
        if isinstance(err, str):
            last_error_raw = err
            break

    if last_error_raw is None:
        m_code = re.search(r'"code"\s*:\s*(\d+)', stderr)
        code = int(m_code.group(1)) if m_code else None
        m_model = re.search(r'"model"\s*:\s*"([^"]+)"', stderr)
        found_model = m_model.group(1) if m_model else None
        stderr_lower = stderr.lower()

        model_note = _model_note(found_model, configured_model)

        if "quota" in stderr_lower or "RESOURCE_EXHAUSTED" in stderr or code == 429:
            return (
                f"Feynman API quota exhausted.{model_note}\n"
                "To fix:\n"
                "  1. Add API credits to your provider account, or\n"
                "  2. Switch to a model with available credits:\n"
                f"     docent studio config-set --key feynman_model --value <provider/model>\n"
                "  (e.g. anthropic/claude-sonnet-4-5, openai/gpt-4o)\n"
                f"{_DOCS_FOOTER}"
            )
        if "auth" in stderr_lower or "unauthorized" in stderr_lower or code in (401, 403):
            return (
                f"Feynman API authentication failed.{model_note}\n"
                "Run `feynman setup` to configure your API keys.\n"
                f"{_DOCS_FOOTER}"
            )
        if code in (500, 502, 503):
            return (
                f"Feynman received a server error (code {code}).{model_note}\n"
                "This is usually temporary. Retry or switch models.\n"
                f"{_DOCS_FOOTER}"
            )

        tail = stderr.strip()[-500:] if stderr.strip() else "(no output)"
        return (
            f"Feynman exited with an error.{model_note}\n"
            f"{tail}\n"
            f"{_DOCS_FOOTER}"
        )

    try:
        inner = json.loads(last_error_raw)
    except json.JSONDecodeError:
        inner = {}

    err_obj = inner.get("error", {})
    code = err_obj.get("code", 0)
    msg = err_obj.get("message", last_error_raw)
    status = err_obj.get("status", "")

    model_note = _model_note(last_model, configured_model)

    if "rate" in msg.lower() or "limit" in msg.lower():
        return (
            f"Feynman API rate-limited.{model_note}\n"
            "Wait 30-60 seconds and retry, or switch to a different model:\n"
            f"  docent studio config-set --key feynman_model --value <provider/model>\n"
            f"{_DOCS_FOOTER}"
        )

    if code == 429 or "RESOURCE_EXHAUSTED" in str(status):
        return (
            f"Feynman API quota exhausted.{model_note}\n"
            "To fix:\n"
            "  1. Add API credits to your provider account, or\n"
            "  2. Switch to a model with available credits:\n"
            f"     docent studio config-set --key feynman_model --value <provider/model>\n"
            "  (e.g. anthropic/claude-sonnet-4-5, openai/gpt-4o)\n"
            f"{_DOCS_FOOTER}"
        )

    if code in (401, 403) or "auth" in msg.lower():
        return (
            f"Feynman API authentication failed.{model_note}\n"
            "Run `feynman setup` to configure your API keys.\n"
            f"{_DOCS_FOOTER}"
        )

    if code == 400 or "invalid" in msg.lower():
        hint = ""
        if "model" in msg.lower():
            hint = (
                "\n  The model name may be invalid. Check available models with\n"
                "  `feynman model list` or see:\n"
                f"  {_DOCS_LINK}"
            )
        return (
            f"Feynman invalid request (400).{model_note}{hint}\n"
            f"{_DOCS_FOOTER}"
        )

    if code in (500, 502, 503):
        provider = last_model.split("/")[0] if last_model else "the provider"
        return (
            f"Feynman received a server error from {provider} (code {code}).{model_note}\n"
            "This is usually temporary. Wait a minute and retry, or switch models:\n"
            f"  docent studio config-set --key feynman_model --value <provider/model>\n"
            f"{_DOCS_FOOTER}"
        )

    if "timeout" in msg.lower():
        return (
            f"Feynman API call timed out.{model_note}\n"
            "The model provider may be overloaded. Retry or switch models.\n"
            f"{_DOCS_FOOTER}"
        )

    if "not found" in msg.lower() and "model" in msg.lower():
        return (
            f"Feynman could not find the requested model.{model_note}\n"
            "Check available models with `feynman model list` or `feynman setup`.\n"
            f"{_DOCS_FOOTER}"
        )

    return (
        f"Feynman error (code {code}).{model_note}\n"
        f"Details: {msg[:400]}\n"
        f"{_DOCS_FOOTER}"
    )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def _run_feynman(
    configured_command: list[str],
    subcommand_args: list[str],
    workspace_dir: Path,
    output_dir: Path,
    slug: str,
    *,
    budget_usd: float = 0.0,
    timeout: float = 900.0,
) -> tuple[int, str | None, str]:
    """Run feynman and return (returncode, output_file_path | None, stderr).

    Resolves the feynman executable via _find_feynman() before running.
    Raises FeynmanNotFoundError if feynman is not installed.
    Captures only stderr (for error surfacing); stdout goes to terminal for real-time progress.
    """
    if budget_usd > 0:
        current_spend = _read_daily_spend()
        if current_spend >= budget_usd * 0.9:
            raise FeynmanBudgetExceededError(
                f"Feynman daily budget nearly exhausted "
                f"(${current_spend:.2f} of ${budget_usd:.2f} today). "
                f"Increase with `docent studio config-set feynman_budget_usd <amount>` "
                f"or use backend='docent'."
            )

    resolved_cmd = _find_feynman(configured_command)
    full_cmd = resolved_cmd + subcommand_args

    workspace_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir = workspace_dir / "outputs"

    before: set[Path] = set(outputs_dir.glob("*.md")) if outputs_dir.is_dir() else set()

    stderr_output = ""
    returncode: int

    import platform

    popen_kwargs: dict = {}
    if platform.system() == "Windows":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        proc = subprocess.Popen(
            full_cmd, cwd=workspace_dir,
            stderr=subprocess.PIPE, text=True,
            **popen_kwargs,
        )
    except FileNotFoundError:
        raise FeynmanNotFoundError(
            resolved_cmd,
            "The feynman executable was found but could not be started. "
            "This may indicate a corrupt installation. Try reinstalling: "
            "npm install -g @companion-ai/feynman",
        )

    try:
        _, stderr_output_raw = proc.communicate(timeout=timeout)
        returncode = proc.returncode
        stderr_output = stderr_output_raw or ""
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        returncode = -1
        stderr_output = (
            f"Feynman timed out after {timeout:.0f}s. "
            "The research task may still be running in the background. "
            "Try increasing the timeout with: "
            "docent studio config-set --key feynman_timeout --value <seconds>"
        )
    except KeyboardInterrupt:
        if platform.system() == "Windows":
            import signal as _signal
            try:
                os.kill(proc.pid, _signal.CTRL_BREAK_EVENT)
            except Exception:
                pass
        else:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise

    if budget_usd > 0:
        cost = _extract_feynman_cost(stderr_output)
        if cost > 0:
            _write_daily_spend(_read_daily_spend() + cost)

    after: set[Path] = set(outputs_dir.glob("*.md")) if outputs_dir.is_dir() else set()
    new_files = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)

    if not new_files:
        return returncode, None, stderr_output

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / f"{slug}.md"
    shutil.copy2(new_files[0], dest)
    return returncode, str(dest), stderr_output

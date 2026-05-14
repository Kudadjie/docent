"""Research tool: run deep research, literature reviews, and peer reviews via Feynman."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from docent.config import write_setting
from docent.core import Context, ProgressEvent, Tool, action, register_tool
from docent.core.shapes import (
    ErrorShape,
    LinkShape,
    MessageShape,
    MetricShape,
    Shape,
)


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


def _resolve_tavily_key(context: Context) -> str | None:
    """Ensure a Tavily API key is available. Prompt interactively if missing.

    Must be called OUTSIDE any Rich Progress context — i.e. from the preflight,
    not from inside a generator action.  Rich Progress steals stdin and will
    abort typer.prompt() calls.
    """
    rs = context.settings.research
    if rs.tavily_api_key:
        return rs.tavily_api_key

    # Don't prompt in non-TTY contexts (tests, MCP, cron)
    import sys
    if not sys.stdin.isatty():
        return None

    try:
        import typer
        key = typer.prompt(
            "\nTavily API key (free at https://tavily.com — 1,000 calls/month)",
            default="",
            show_default=False,
        ).strip()
    except (EOFError, KeyboardInterrupt, typer.Abort):
        return None

    if not key:
        return None

    write_setting("research.tavily_api_key", key)
    # Mutate the in-memory settings so we don't prompt again this session
    rs.tavily_api_key = key
    return key


class FeynmanBudgetExceededError(RuntimeError):
    """Raised when Feynman session spend reaches 90% of the configured budget."""


class FeynmanNotFoundError(RuntimeError):
    """Raised when the feynman executable cannot be found on PATH or known locations."""

    def __init__(self, cmd: list[str], details: str = ""):
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
    # 1. User-configured command takes priority
    if configured_command:
        resolved = shutil.which(configured_command[0])
        if resolved:
            return [resolved] + configured_command[1:]
        # User explicitly set a path that doesn't exist — raise immediately
        raise FeynmanNotFoundError(
            configured_command,
            f"Configured command {configured_command[0]!r} not found on PATH.",
        )

    # 2. Try standard PATH lookup
    resolved = shutil.which("feynman")
    if resolved:
        return [resolved]

    # 3. Windows npm global bin fallback
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
    import json as _json
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
                data = _json.loads(pkg_path.read_text(encoding="utf-8"))
                v = data.get("version")
                if v:
                    return str(v)
            except Exception:
                pass
    return "?"


def _extract_feynman_cost(output: str) -> float:
    """Parse Feynman's stdout/stderr for a cost line. Returns 0.0 if not found.

    Feynman prints lines like: 'Cost: $0.43' or 'Total cost: $1.23'
    Uses a lenient regex — format may change across Feynman versions.
    """
    match = re.search(r'\$(\d+(?:\.\d+)?)', output)
    return float(match.group(1)) if match else 0.0


def _slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric with hyphens, collapse runs."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    return s.strip("-")[:60]


def _read_guide_file(path: str | None) -> str:
    """Read a single guide file. Returns '' if missing/unreadable."""
    if not path:
        return ""
    p = Path(path).expanduser()
    if not p.exists():
        return ""
    try:
        if p.suffix.lower() == ".pdf":
            try:
                from pdfminer.high_level import extract_text
                return extract_text(str(p))
            except ImportError:
                return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_guide_files(paths: list[str]) -> str:
    """Read one or more guide files and concatenate their content.

    Each file's content is prefixed with a header so the LLM can distinguish
    sources. Files that are missing or unreadable are silently skipped.
    """
    if not paths:
        return ""
    if len(paths) == 1:
        return _read_guide_file(paths[0])
    parts: list[str] = []
    for path in paths:
        text = _read_guide_file(path)
        if text:
            name = Path(path).name
            parts.append(f"### {name}\n\n{text}")
    return "\n\n".join(parts)


def _artifact_slug(artifact: str) -> str:
    """Derive a slug from an artifact identifier (URL, arXiv ID, or path)."""
    s = artifact.strip()
    if "/" in s:
        s = s.rstrip("/").rsplit("/", 1)[-1]
    return s


def _summarize_feynman_error(stderr: str, configured_model: str | None = None) -> str:
    """Parse feynman's JSON session stream and extract a user-friendly error summary.

    Feynman in headless mode emits a JSON Lines stream (one JSON object per line).
    When a model call fails, the last line(s) contain an errorMessage with the API
    error. This function extracts the last parseable error and returns a clean,
    actionable message instead of dumping the raw 50KB transcript.
    """
    import json as _json

    _DOCS_LINK = "https://feynman.is/docs"
    _DOCS_FOOTER = (
        f"Docs: {_DOCS_LINK}\n"
        f"\n"
        f"Adjust Feynman settings via its CLI in a separate terminal.\n"
        f"See {_DOCS_LINK} for more Feynman-native options."
    )

    last_model = None
    last_error_raw = None
    last_code = None

    for line in reversed(stderr.splitlines()):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = _json.loads(line)
        except _json.JSONDecodeError:
            continue

        if isinstance(obj.get("model"), str):
            last_model = last_model or obj["model"]
        err = obj.get("errorMessage")
        if isinstance(err, str):
            last_error_raw = err
            break

    # Fall back to regex extraction from unstructured stderr.
    # Feynman in text mode produces error output that contains JSON fragments
    # but isn't clean JSON Lines. Extract what we can and categorize.
    if last_error_raw is None:
        import re

        # Try to pull code + model from any JSON-ish fragments in the text
        m_code = re.search(r'"code"\s*:\s*(\d+)', stderr)
        code = int(m_code.group(1)) if m_code else None
        m_model = re.search(r'"model"\s*:\s*"([^"]+)"', stderr)
        found_model = m_model.group(1) if m_model else None
        stderr_lower = stderr.lower()

        model_note = _model_note(found_model, configured_model)

        # ── Categorize from regex hits ──────────────────────────────────
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

        # ── Nothing recognized — show cleaned-up last 500 chars ─────────
        tail = stderr.strip()[-500:] if stderr.strip() else "(no output)"
        return (
            f"Feynman exited with an error.{model_note}\n"
            f"{tail}\n"
            f"{_DOCS_FOOTER}"
        )

    # Parse structured JSON Lines error
    try:
        inner = _json.loads(last_error_raw)
    except _json.JSONDecodeError:
        inner = {}

    err_obj = inner.get("error", {})
    code = err_obj.get("code", 0)
    msg = err_obj.get("message", last_error_raw)
    status = err_obj.get("status", "")

    model_note = _model_note(last_model, configured_model)

    # ── Known error codes ────────────────────────────────────────────────
    # Rate-limit is a 429 with "rate" in the message (per-request throttle,
    # not quota exhaustion). Check before the generic 429 quota path.
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

    # ── Generic: we have a code + message, surface both ───────────────────
    return (
        f"Feynman error (code {code}).{model_note}\n"
        f"Details: {msg[:400]}\n"
        f"{_DOCS_FOOTER}"
    )


def _model_note(last_model: str | None, configured_model: str | None) -> str:
    """Build a human-readable model note for error messages."""
    if configured_model:
        actual = f"`{last_model}`" if last_model else "unknown"
        return f"\n  Docent configured: `{configured_model}`\n  Feynman attempted: {actual}"
    if last_model:
        return f"\n  Model attempted: `{last_model}` (feynman default)"
    return "\n  Model attempted: unknown (feynman default)"


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
    # Pre-run guard
    if budget_usd > 0:
        current_spend = _read_daily_spend()
        if current_spend >= budget_usd * 0.9:
            raise FeynmanBudgetExceededError(
                f"Feynman daily budget nearly exhausted "
                f"(${current_spend:.2f} of ${budget_usd:.2f} today). "
                f"Increase with `docent studio config-set feynman_budget_usd <amount>` "
                f"or use backend='docent'."
            )

    # Resolve the executable — raises FeynmanNotFoundError if not found
    resolved_cmd = _find_feynman(configured_command)
    full_cmd = resolved_cmd + subcommand_args

    workspace_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir = workspace_dir / "outputs"

    before: set[Path] = set(outputs_dir.glob("*.md")) if outputs_dir.is_dir() else set()

    stderr_output = ""
    returncode: int

    import platform

    # On Windows, start feynman in its own process group so that pressing
    # Ctrl+C only interrupts Python (not feynman via the console event).
    # We then explicitly kill feynman ourselves on KeyboardInterrupt.
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
        # _find_feynman already validates the executable, so a FileNotFoundError
        # here means PATH/sys resolution succeeded but the binary itself failed
        # to start (e.g. missing interpreter on a .cmd wrapper on Windows).
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
        # Explicitly kill feynman — it's in its own process group on Windows
        # so it did not receive the CTRL_C_EVENT from the console.
        if platform.system() == "Windows":
            import os, signal as _signal
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

    # Post-run cost capture — persist to daily store
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


from ._notebook import (
    _nlm_auth_ok,
    _nlm_push,
    _rank_sources,
    ToNotebookInputs,
    ToNotebookResult,
)


def _build_references_section(sources: list[dict]) -> str:
    """Build a markdown References section from source dicts.

    Each source gets a numbered entry with title, URL, and source type.
    Skips sources without a URL.
    """
    lines = ["\n\n## References\n"]
    idx = 0
    for s in sources:
        url = s.get("url", "")
        if not url:
            continue
        idx += 1
        title = s.get("title", "Untitled")
        stype = s.get("source_type", "web")
        authors = s.get("authors", "")
        author_tag = f" — {authors}" if authors else ""
        lines.append(f"{idx}. **{title}**{author_tag} — {url} [{stype}]")
    if idx == 0:
        return ""
    return "\n".join(lines) + "\n"


def _strip_references_section(draft: str) -> str:
    """Remove any existing ## References section from the end of a draft.

    The Tavily Research API sometimes includes its own references/citations
    section in the output.  When we append our own, we need to strip any
    pre-existing one to avoid duplicates.
    """
    # Match a trailing ## References heading plus everything after it.
    # Handles both ## References\n... and ## References\r\n...
    stripped = re.sub(r"\n## References\s*[\r\n].*$", "", draft, flags=re.DOTALL)
    return stripped.rstrip()


def _append_references(draft: str, sources: list[dict]) -> str:
    """Strip any existing References section, then append our own."""
    cleaned = _strip_references_section(draft)
    return cleaned + _build_references_section(sources)


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

_OUTPUT_CHOICES = "'local' (default), 'notebook' (push to NotebookLM), 'vault' (write to Obsidian vault)."


_GUIDE_FILES_FIELD = Field(
    default_factory=list,
    description=(
        "Optional path(s) to files (.md, .txt, PDF) that guide the research — "
        "their content is injected into the research brief to focus the output. "
        "Pass the flag multiple times to supply several files."
    ),
)


class DeepInputs(BaseModel):
    topic: str = Field(..., description="Research topic or question.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class LitInputs(BaseModel):
    topic: str = Field(..., description="Research topic or question.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class ReviewInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, local PDF path, or URL to review.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class ConfigShowInputs(BaseModel):
    pass


class ConfigSetInputs(BaseModel):
    key: str = Field(..., description="Setting key under [research]: 'output_dir'.")
    value: str = Field(..., description="New value.")


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

class ResearchResult(BaseModel):
    ok: bool
    backend: str
    workflow: str
    topic_or_artifact: str
    output_file: str | None
    returncode: int | None
    message: str
    notebook_id: str | None = None
    vault_path: str | None = None

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.output_file is not None:
            shapes.append(LinkShape(url=self.output_file, label="Output file"))
        if self.notebook_id is not None:
            shapes.append(MetricShape(label="NotebookLM notebook", value=self.notebook_id))
        if self.vault_path is not None:
            shapes.append(LinkShape(url=self.vault_path, label="Obsidian vault note"))
        return shapes



class ConfigShowResult(BaseModel):
    config_path: str
    output_dir: str
    feynman_command: list[str]
    oc_provider: str
    oc_model_planner: str
    oc_model_writer: str
    oc_model_verifier: str
    oc_model_reviewer: str
    oc_model_researcher: str
    oc_budget_usd: float
    tavily_api_key: str | None = None
    tavily_research_timeout: float = 600.0
    semantic_scholar_api_key: str | None = None
    feynman_model: str | None = None
    feynman_timeout: float = 900.0
    notebooklm_notebook_id: str | None = None
    obsidian_vault: str | None = None
    alphaxiv_api_key: str | None = None

    def to_shapes(self) -> list[Shape]:
        # Mask sensitive API keys for display
        def _mask(key: str | None) -> str:
            if not key:
                return "(not set)"
            if len(key) <= 8:
                return "***"
            return key[:4] + "..." + key[-4:]

        return [
            MetricShape(label="Config", value=self.config_path),
            MetricShape(label="output_dir", value=self.output_dir),
            MetricShape(label="feynman_command", value=" ".join(self.feynman_command)),
            MetricShape(label="oc_provider", value=self.oc_provider),
            MetricShape(label="oc_model_planner", value=self.oc_model_planner),
            MetricShape(label="oc_model_writer", value=self.oc_model_writer),
            MetricShape(label="oc_model_verifier", value=self.oc_model_verifier),
            MetricShape(label="oc_model_reviewer", value=self.oc_model_reviewer),
            MetricShape(label="oc_model_researcher", value=self.oc_model_researcher),
            MetricShape(label="oc_budget_usd", value=str(self.oc_budget_usd)),
            MetricShape(label="tavily_api_key", value=_mask(self.tavily_api_key)),
            MetricShape(label="tavily_research_timeout", value=f"{self.tavily_research_timeout:.0f}s"),
            MetricShape(label="semantic_scholar_api_key", value=_mask(self.semantic_scholar_api_key)),
            MetricShape(label="feynman_model", value=self.feynman_model or "(feynman default)"),
            MetricShape(label="feynman_timeout", value=f"{self.feynman_timeout:.0f}s"),
            MetricShape(label="notebooklm_notebook_id", value=self.notebooklm_notebook_id or "(not set)"),
            MetricShape(label="obsidian_vault", value=self.obsidian_vault or "(not set)"),
            MetricShape(label="alphaxiv_api_key", value=_mask(self.alphaxiv_api_key)),
        ]



class ConfigSetResult(BaseModel):
    ok: bool
    key: str
    value: str
    config_path: str
    message: str

    def to_shapes(self) -> list[Shape]:
        return [
            MessageShape(text=self.message, level="success" if self.ok else "error"),
        ]



class ToLocalInputs(BaseModel):
    output_file: str | None = Field(
        None,
        description=(
            "Path to a research output .md file. "
            "If omitted, the most recent output in research.output_dir is used."
        ),
    )
    guide_files: list[str] = _GUIDE_FILES_FIELD
    to_vault: bool = Field(
        False,
        description="Also copy to Obsidian vault if research.obsidian_vault is configured.",
    )


class ToLocalResult(BaseModel):
    ok: bool
    output_file: str | None
    sources_file: str | None
    package_dir: str | None
    sources_count: int
    vault_path: str | None = None
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.package_dir:
            shapes.append(LinkShape(url=self.package_dir, label="Local package"))
        if self.vault_path:
            shapes.append(LinkShape(url=self.vault_path, label="Obsidian note"))
        if self.sources_count:
            shapes.append(MetricShape(label="Sources in package", value=str(self.sources_count)))
        return shapes


class SearchPapersInputs(BaseModel):
    query: str = Field(..., description="Search query for academic papers on alphaXiv.")
    max_results: int = Field(10, description="Maximum number of results to return (default 10).")


class SearchPapersResult(BaseModel):
    ok: bool
    query: str
    papers: list[dict]
    count: int
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        for p in self.papers:
            authors = ", ".join(p.get("authors", [])[:3])
            if len(p.get("authors", [])) > 3:
                authors += " et al."
            year = (p.get("published") or "")[:4] or "?"
            shapes.append(MetricShape(
                label=f"{p['title']} ({year})",
                value=authors or "Unknown authors",
            ))
            if p.get("arxiv_url"):
                shapes.append(LinkShape(url=p["arxiv_url"], label=p["arxiv_id"]))
        return shapes


class GetPaperInputs(BaseModel):
    arxiv_id: str = Field(..., description="arXiv paper ID (e.g. '2401.12345') or arXiv URL.")


class GetPaperResult(BaseModel):
    ok: bool
    arxiv_id: str
    title: str | None
    abstract: str
    overview: str
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.title:
            shapes.append(MetricShape(label="Title", value=self.title))
        shapes.append(LinkShape(
            url=f"https://arxiv.org/abs/{self.arxiv_id}",
            label=self.arxiv_id,
        ))
        preview = self.overview[:600] + ("…" if len(self.overview) > 600 else "")
        shapes.append(MessageShape(text=preview, level="info"))
        return shapes


class ScholarlySearchInputs(BaseModel):
    query: str = Field(..., description="Search query for academic papers (Google Scholar / Semantic Scholar / CrossRef).")
    max_results: int = Field(10, description="Maximum results to return (default 10).")


class ScholarlySearchResult(BaseModel):
    ok: bool
    query: str
    papers: list[dict]
    count: int
    backend_used: str
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [
            MessageShape(text=self.message, level="success"),
            MetricShape(label="Backend", value=self.backend_used),
        ]
        for p in self.papers:
            authors = ", ".join(p.get("authors", [])[:3])
            if len(p.get("authors", [])) > 3:
                authors += " et al."
            year = p.get("year") or "?"
            shapes.append(MetricShape(
                label=f"{p['title']} ({year})",
                value=authors or "Unknown authors",
            ))
            url = p.get("url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else None)
            if url:
                label = p.get("doi") or url[:60]
                shapes.append(LinkShape(url=url, label=label))
        return shapes


class CompareInputs(BaseModel):
    artifact_a: str = Field(..., description="First artifact: arXiv ID, PDF path, or URL.")
    artifact_b: str = Field(..., description="Second artifact: arXiv ID, PDF path, or URL.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD

    @property
    def topic(self) -> str:
        return f"{self.artifact_a} vs {self.artifact_b}"


class DraftInputs(BaseModel):
    topic: str = Field(..., description="Topic or section title to draft.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class ReplicateInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, PDF path, or URL of the paper to replicate.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class AuditInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, PDF path, or URL of the paper to audit.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default) or 'docent'.")
    output: str = Field("local", description=f"Output destination: {_OUTPUT_CHOICES}")
    guide_files: list[str] = _GUIDE_FILES_FIELD


class UsageInputs(BaseModel):
    pass


class UsageResult(BaseModel):
    feynman_spend_usd: float
    oc_spend_usd: float
    feynman_budget_usd: float
    oc_budget_usd: float
    date: str
    message: str

    def to_shapes(self) -> list[Shape]:
        shapes: list[Shape] = [
            MetricShape(label="Date", value=self.date),
            MetricShape(label="Feynman spend today", value=f"${self.feynman_spend_usd:.4f}",
                       unit=f"/ ${self.feynman_budget_usd:.2f} budget" if self.feynman_budget_usd > 0 else "(no limit)"),
            MetricShape(label="OpenCode spend today", value=f"${self.oc_spend_usd:.4f}",
                       unit=f"/ ${self.oc_budget_usd:.2f} budget" if self.oc_budget_usd > 0 else "(no limit)"),
        ]
        return shapes



# NLM helpers live in _notebook.py (imported above)


def _route_output(inputs: Any, out_path: Path, sources_path: Path | None, context: "Context", workflow: str):
    """Generator helper: handles --output routing after local file is written.

    Yields ProgressEvents from _nlm_push when output='notebook'.
    Returns (notebook_id, vault_path, extra_message) as a tuple.
    """
    if inputs.output == "notebook":
        topic = getattr(inputs, "topic", None)
        gf_list = getattr(inputs, "guide_files", []) or []
        result = yield from _nlm_push(
            out_path, sources_path, context,
            topic=topic,
            guide_files=[Path(p).expanduser() for p in gf_list],
        )
        if result["ok"]:
            return result["notebook_id"], None, f" {result['message']}"
        return None, None, f" (NotebookLM push failed: {result['message']})"

    if inputs.output == "vault":
        vault = context.settings.research.obsidian_vault
        if not vault:
            return None, None, (
                " (vault output requested but obsidian_vault is not configured — "
                "set it with: docent studio config-set --key obsidian_vault --value <path>)"
            )
        topic = getattr(inputs, "topic", None) or getattr(inputs, "artifact", "")
        dest = _write_to_vault(out_path, topic, workflow, inputs.backend, vault)
        return None, str(dest), f" Written to Obsidian vault: {dest.name}"

    return None, None, ""


def _write_to_vault(
    out_path: Path,
    topic_or_artifact: str,
    workflow: str,
    backend: str,
    vault: Path,
) -> Path:
    """Write a research output to the Obsidian vault under {vault}/Studio/.

    Adds YAML frontmatter compatible with Obsidian, Dataview, and Citations plugin.
    Returns the destination path.
    """
    import datetime
    studio_dir = vault.expanduser() / "Studio"
    studio_dir.mkdir(parents=True, exist_ok=True)

    dest = studio_dir / out_path.name
    content = out_path.read_text(encoding="utf-8")

    date_str = datetime.date.today().isoformat()
    tag = f"docent/studio/{workflow}"
    frontmatter = (
        f"---\n"
        f"tags: [docent/studio, {tag}]\n"
        f"date: {date_str}\n"
        f"topic: \"{topic_or_artifact.replace(chr(34), chr(39))}\"\n"
        f"backend: {backend}\n"
        f"source_file: {out_path.name}\n"
        f"---\n\n"
    )

    dest.write_text(frontmatter + content, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

_KNOWN_RESEARCH_KEYS = {
    "output_dir",
    "feynman_budget_usd",
    "feynman_model",
    "feynman_timeout",
    "oc_provider",
    "oc_model_planner",
    "oc_model_writer",
    "oc_model_verifier",
    "oc_model_reviewer",
    "oc_model_researcher",
    "oc_budget_usd",
    "tavily_api_key",
    "tavily_research_timeout",
    "semantic_scholar_api_key",
    "notebooklm_notebook_id",
    "obsidian_vault",
    "alphaxiv_api_key",
}


def _preflight_docent(inputs: BaseModel, context: Context) -> None:
    """Pre-flight check for deep/lit actions with ``backend='docent'``.

    Runs *before* the generator is created (and therefore before Rich
    Progress takes over stdin).  Checks:
      1. OpenCode server is running.
      2. The planner model is usable (has credits, valid auth) — makes a
         minimal test call so the task never starts on an exhausted model.
      3. Tavily API key is available.

    Non-docent backends are a no-op so the same preflight can be used
    for all actions.
    """
    if getattr(inputs, "backend", None) != "docent":
        return

    import typer
    from docent.ui.console import get_console
    from docent.utils.model_health import verify_opencode_model
    from .oc_client import OcClient, OcModelError, OcUnavailableError

    oc = OcClient(
        provider=context.settings.research.oc_provider,
        budget_usd=context.settings.research.oc_budget_usd,
    )
    if not oc.is_available():
        get_console().print(
            "[red]Error:[/] OpenCode server is not running. "
            "Start it with: [cyan]opencode serve --port 4096[/]"
        )
        raise typer.Exit(1)

    # Verify the planner model has available credits before starting the task.
    # Every failure is a hard block — running the pipeline when the model is
    # unreachable, quota-exhausted, or unresponsive wastes time and produces
    # a worse error message than stopping here.
    planner = context.settings.research.oc_model_planner
    console = get_console()
    try:
        with console.status(f"Checking model availability: [cyan]{planner}[/]..."):
            verify_opencode_model(planner, provider=context.settings.research.oc_provider)
        console.print(f"[green]✓[/] Model [cyan]{planner}[/] is available")
    except OcModelError as e:
        console.print(
            f"[red]✗[/] Model [cyan]{planner}[/] is not usable: {e}\n"
            "Use [cyan]--backend feynman[/] to run without OpenCode, or "
            "fix the model issue above then retry."
        )
        raise typer.Exit(1)
    except OcUnavailableError as e:
        console.print(
            f"[red]✗[/] OpenCode server became unreachable during model check: {e}\n"
            "Use [cyan]--backend feynman[/] or restart the OpenCode server."
        )
        raise typer.Exit(1)
    except Exception as e:
        # Covers timeouts and any unexpected failure from the test call.
        # A timeout here is the most common signal that the model's quota
        # is exhausted — providers often silently queue/drop requests rather
        # than returning a quota-exceeded error.  There is no OpenCode API
        # for checking remaining quota directly; the test call is the check.
        console.print(
            f"[red]✗[/] Model check failed for [cyan]{planner}[/] ({e})\n"
            "Most likely cause: quota exhausted on the provider — many providers\n"
            "silently drop requests rather than returning an explicit error.\n"
            "Diagnose with: [cyan]opencode stats[/]\n"
            "Options:\n"
            "  • Switch to [cyan]--backend feynman[/] (no OpenCode required)\n"
            "  • Change model: [cyan]docent studio config-set --key oc_model_planner --value <model>[/]\n"
            "  • Top up your OpenCode subscription and retry"
        )
        raise typer.Exit(1)

    tavily_key = _resolve_tavily_key(context)
    if not tavily_key:
        get_console().print(
            "[red]Error:[/] Tavily API key is required for web search. "
            "Get one at https://tavily.com (free tier: 1,000 calls/month)."
        )
        raise typer.Exit(1)


def _preflight_oc_only(inputs: BaseModel, context: Context) -> None:
    """Pre-flight check for review action (needs OcClient but not Tavily)."""
    if getattr(inputs, "backend", None) != "docent":
        return

    import typer
    from docent.ui.console import get_console
    from docent.utils.model_health import verify_opencode_model
    from .oc_client import OcClient, OcModelError, OcUnavailableError

    oc = OcClient(
        provider=context.settings.research.oc_provider,
        budget_usd=context.settings.research.oc_budget_usd,
    )
    if not oc.is_available():
        get_console().print(
            "[red]Error:[/] OpenCode server is not running. "
            "Start it with: [cyan]opencode serve --port 4096[/]"
        )
        raise typer.Exit(1)

    reviewer = context.settings.research.oc_model_reviewer
    console = get_console()
    try:
        with console.status(f"Checking model availability: [cyan]{reviewer}[/]..."):
            verify_opencode_model(reviewer, provider=context.settings.research.oc_provider)
        console.print(f"[green]✓[/] Model [cyan]{reviewer}[/] is available")
    except OcModelError as e:
        console.print(
            f"[red]✗[/] Model [cyan]{reviewer}[/] is not usable: {e}\n"
            "Use [cyan]--backend feynman[/] to run without OpenCode, or "
            "fix the model issue above then retry."
        )
        raise typer.Exit(1)
    except OcUnavailableError as e:
        console.print(
            f"[red]✗[/] OpenCode server became unreachable during model check: {e}\n"
            "Use [cyan]--backend feynman[/] or restart the OpenCode server."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(
            f"[red]✗[/] Model check failed for [cyan]{reviewer}[/] ({e})\n"
            "Most likely cause: quota exhausted on the provider — many providers\n"
            "silently drop requests rather than returning an explicit error.\n"
            "Diagnose with: [cyan]opencode stats[/]\n"
            "Options:\n"
            "  • Switch to [cyan]--backend feynman[/] (no OpenCode required)\n"
            "  • Change model: [cyan]docent studio config-set --key oc_model_reviewer --value <model>[/]\n"
            "  • Top up your OpenCode subscription and retry"
        )
        raise typer.Exit(1)


@register_tool
class StudioTool(Tool):
    """Run research workflows (deep research, literature review, peer review) via Feynman."""

    name = "studio"
    description = "Run research workflows (deep research, literature review, peer review) via Feynman."
    category = "studio"

    @action(
        description="Deep research on a topic.",
        input_schema=DeepInputs,
        preflight=_preflight_docent,
    )
    def deep_research(self, inputs: DeepInputs, context: Context):
        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_deep

            # OcClient availability and Tavily key are guaranteed by preflight;
            # read the key from settings (mutated by _resolve_tavily_key).
            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            tavily_key = context.settings.research.tavily_api_key

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(inputs.topic) + "-deep"

            guide_ctx = _read_guide_files(inputs.guide_files)
            effective_topic = inputs.topic
            if guide_ctx:
                names = ", ".join(Path(p).name for p in inputs.guide_files)
                effective_topic = (
                    f"{inputs.topic}\n\n"
                    f"## Guide context ({names})\n{guide_ctx}"
                )

            try:
                result_data = yield from run_deep(
                    effective_topic, oc,
                    model_planner=context.settings.research.oc_model_planner,
                    model_writer=context.settings.research.oc_model_writer,
                    model_verifier=context.settings.research.oc_model_verifier,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                    tavily_api_key=tavily_key,
                    semantic_scholar_api_key=context.settings.research.semantic_scholar_api_key,
                    alphaxiv_api_key=context.settings.research.alphaxiv_api_key,
                    tavily_research_timeout=context.settings.research.tavily_research_timeout,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="deep",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="deep",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=result_data.get("error") or "Pipeline failed.",
                )

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            sources_file = output_dir / f"{slug}-sources.json"

            # Append references section (stripping any pre-existing one from Tavily)
            draft_with_refs = _append_references(
                result_data["draft"], result_data.get("sources", [])
            )
            out_file.write_text(draft_with_refs, encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")
            sources_file.write_text(
                json.dumps(result_data.get("sources", []), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            yield ProgressEvent(
                phase="done", message=f"Output written to {out_file}"
            )

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, sources_file, context, "deep-research"
            )
            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Deep research complete. {result_data['rounds']} search round(s), {len(result_data['sources'])} sources.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(
            phase="start",
            message=f"Starting Feynman deep research: {inputs.topic!r}",
        )
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        slug = _slugify(inputs.topic) + "-deep"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/deepresearch {inputs.topic}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="deep",
                topic_or_artifact=inputs.topic, output_file=None, returncode=None,
                message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=output_file,
                returncode=returncode,
                message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True,
                backend="feynman",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=None,
                returncode=returncode,
                message=f"Deep research completed for {inputs.topic!r}, but no output file was found.",
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "deep-research"
        )
        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="deep",
            topic_or_artifact=inputs.topic,
            output_file=output_file,
            returncode=returncode,
            notebook_id=notebook_id,
            vault_path=vault_path,
            message=f"Deep research completed for {inputs.topic!r}.{extra}",
        )

    @action(
        description="Literature review on a topic.",
        input_schema=LitInputs,
        preflight=_preflight_docent,
    )
    def lit(self, inputs: LitInputs, context: Context):
        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_lit

            # OcClient availability and Tavily key are guaranteed by preflight;
            # read the key from settings (mutated by _resolve_tavily_key).
            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            tavily_key = context.settings.research.tavily_api_key

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(inputs.topic) + "-lit"

            guide_ctx = _read_guide_files(inputs.guide_files)
            effective_topic = inputs.topic
            if guide_ctx:
                names = ", ".join(Path(p).name for p in inputs.guide_files)
                effective_topic = (
                    f"{inputs.topic}\n\n"
                    f"## Guide context ({names})\n{guide_ctx}"
                )

            try:
                result_data = yield from run_lit(
                    effective_topic, oc,
                    model_planner=context.settings.research.oc_model_planner,
                    model_writer=context.settings.research.oc_model_writer,
                    model_verifier=context.settings.research.oc_model_verifier,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                    tavily_api_key=tavily_key,
                    semantic_scholar_api_key=context.settings.research.semantic_scholar_api_key,
                    alphaxiv_api_key=context.settings.research.alphaxiv_api_key,
                    tavily_research_timeout=context.settings.research.tavily_research_timeout,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="lit",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="lit",
                    topic_or_artifact=inputs.topic,
                    output_file=None,
                    returncode=None,
                    message=result_data.get("error") or "Pipeline failed.",
                )

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            sources_file = output_dir / f"{slug}-sources.json"

            # Append references section (stripping any pre-existing one from Tavily)
            draft_with_refs = _append_references(
                result_data["draft"], result_data.get("sources", [])
            )
            out_file.write_text(draft_with_refs, encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")
            sources_file.write_text(
                json.dumps(result_data.get("sources", []), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, sources_file, context, "lit"
            )
            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Literature review complete. {result_data['rounds']} search round(s), {len(result_data['sources'])} sources.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(
            phase="start",
            message=f"Starting Feynman literature review: {inputs.topic!r}",
        )
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        slug = _slugify(inputs.topic) + "-lit"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/lit {inputs.topic}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="lit",
                topic_or_artifact=inputs.topic, output_file=None, returncode=None,
                message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=output_file,
                returncode=returncode,
                message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True,
                backend="feynman",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=None,
                returncode=returncode,
                message=f"Literature review completed for {inputs.topic!r}, but no output file was found.",
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "lit"
        )
        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="lit",
            topic_or_artifact=inputs.topic,
            output_file=output_file,
            returncode=returncode,
            notebook_id=notebook_id,
            vault_path=vault_path,
            message=f"Literature review completed for {inputs.topic!r}.{extra}",
        )

    @action(
        description="Peer review of an artifact (arXiv ID, PDF path, or URL).",
        input_schema=ReviewInputs,
        preflight=_preflight_oc_only,
    )
    def review(self, inputs: ReviewInputs, context: Context):
        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_review

            # OcClient availability is guaranteed by preflight.
            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )

            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            slug = _slugify(_artifact_slug(inputs.artifact)) + "-review"

            try:
                result_data = yield from run_review(
                    inputs.artifact, oc,
                    model_researcher=context.settings.research.oc_model_researcher,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="review",
                    topic_or_artifact=inputs.artifact,
                    output_file=None,
                    returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False,
                    backend="docent",
                    workflow="review",
                    topic_or_artifact=inputs.artifact,
                    output_file=None,
                    returncode=None,
                    message=result_data.get("error") or "Review failed.",
                )

            out_file = output_dir / f"{slug}.md"
            out_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message=f"Review written to {out_file}")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "review"
            )
            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="review",
                topic_or_artifact=inputs.artifact,
                output_file=str(out_file),
                returncode=0,
                notebook_id=notebook_id,
                vault_path=vault_path,
                message=f"Peer review complete for {inputs.artifact!r}.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(
            phase="start",
            message=f"Starting Feynman review: {inputs.artifact!r}",
        )
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        slug = _slugify(_artifact_slug(inputs.artifact)) + "-review"
        cmd_args = ["--prompt", f"/review {inputs.artifact}"]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="review",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False,
                backend="feynman",
                workflow="review",
                topic_or_artifact=inputs.artifact,
                output_file=output_file,
                returncode=returncode,
                message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True,
                backend="feynman",
                workflow="review",
                topic_or_artifact=inputs.artifact,
                output_file=None,
                returncode=returncode,
                message=f"Review completed for {inputs.artifact!r}, but no output file was found.",
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "review"
        )
        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="review",
            topic_or_artifact=inputs.artifact,
            output_file=output_file,
            returncode=returncode,
            notebook_id=notebook_id,
            vault_path=vault_path,
            message=f"Review completed for {inputs.artifact!r}.{extra}",
        )

    @action(
        description=(
            "Populate a new or existing NotebookLM notebook with research sources, then run "
            "the full quality pipeline: NLM web research arm, source stabilisation, quality "
            "gate (validation + contradictions + gap-fill), and 3-perspective summaries "
            "(practitioner / skeptic / beginner). Mirrors the research-to-notebook skill. "
            "Falls back to local package export + browser open if NLM is unavailable."
        ),
        input_schema=ToNotebookInputs,
        name="to-notebook",
    )
    def to_notebook(self, inputs: ToNotebookInputs, context: Context):
        output_dir = context.settings.research.output_dir.expanduser()

        # ── Resolve output file ──────────────────────────────────────────────
        if inputs.output_file:
            out_path = Path(inputs.output_file)
            if not out_path.is_absolute():
                out_path = output_dir / inputs.output_file
        else:
            candidates = [
                p for p in output_dir.glob("*.md")
                if not p.name.endswith("-review.md")
            ] if output_dir.is_dir() else []
            if not candidates:
                return ToNotebookResult(
                    ok=False, output_file=None, sources_file=None,
                    package_dir=None, sources_count=0,
                    message=(
                        f"No research output found in {output_dir}. "
                        "Run `docent studio deep-research` or `docent studio lit` first."
                    ),
                )
            out_path = max(candidates, key=lambda p: p.stat().st_mtime)

        stem = out_path.stem
        sources_path = out_path.parent / f"{stem}-sources.json"

        has_sources = sources_path.exists()
        selected = (
            _rank_sources(
                json.loads(sources_path.read_text(encoding="utf-8")), inputs.max_sources
            )
            if has_sources else []
        )

        # ── Write local package ───────────────────────────────────────────────
        package_dir = out_path.parent / f"{stem}-notebook"
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "sources_urls.txt").write_text(
            "\n".join(s["url"] for s in selected if s.get("url")),
            encoding="utf-8",
        )
        shutil.copy2(out_path, package_dir / out_path.name)
        yield ProgressEvent(phase="package", message=f"Local package written to {package_dir}")

        # ── Override notebook_id from inputs if provided ─────────────────────
        if inputs.notebook_id:
            context.settings.research.notebooklm_notebook_id = inputs.notebook_id

        # ── Full pipeline ─────────────────────────────────────────────────────
        nlm = yield from _nlm_push(
            out_path=out_path,
            sources_path=sources_path if has_sources else None,
            context=context,
            max_sources=inputs.max_sources,
            topic=inputs.topic,
            guide_files=[Path(p).expanduser() for p in inputs.guide_files],
            run_nlm_research=inputs.run_nlm_research,
            run_quality_gate=inputs.run_quality_gate,
            run_perspectives=inputs.run_perspectives,
        )

        sources_file_str = str(sources_path) if has_sources else None

        if not nlm["ok"]:
            import webbrowser
            webbrowser.open("https://notebooklm.google.com")
            return ToNotebookResult(
                ok=True,
                output_file=str(out_path), sources_file=sources_file_str,
                package_dir=str(package_dir), sources_count=len(selected),
                sources_added=0, sources_failed=0,
                message=f"{nlm['message']} -- opened browser. Local package at {package_dir}.",
            )

        nb_id = nlm["notebook_id"]
        save_hint = ""
        if nb_id and nb_id != context.settings.research.notebooklm_notebook_id:
            save_hint = f" Save with: docent studio config-set --key notebooklm_notebook_id --value {nb_id}"

        return ToNotebookResult(
            ok=True,
            output_file=str(out_path),
            sources_file=sources_file_str,
            package_dir=str(package_dir),
            sources_count=len(selected),
            sources_added=nlm["sources_added"],
            sources_failed=nlm["sources_failed"],
            sources_from_feynman=nlm["sources_from_feynman"],
            sources_from_nlm=nlm["sources_from_nlm"],
            notebook_id=nb_id,
            quality_gate=nlm["quality_gate"],
            perspectives=nlm["perspectives"],
            message=nlm["message"] + save_hint,
        )

    @action(
        description=(
            "Package an existing research output as a local directory: copies the synthesis "
            "document, writes a sources URL list, and optionally copies to your Obsidian vault. "
            "Use this when you want a self-contained local record without pushing to NotebookLM."
        ),
        input_schema=ToLocalInputs,
        name="to-local",
    )
    def to_local(self, inputs: ToLocalInputs, context: Context) -> ToLocalResult:
        output_dir = context.settings.research.output_dir.expanduser()

        # ── Resolve output file ──────────────────────────────────────────────
        if inputs.output_file:
            out_path = Path(inputs.output_file)
            if not out_path.is_absolute():
                out_path = output_dir / inputs.output_file
        else:
            candidates = [
                p for p in output_dir.glob("*.md")
                if not p.name.endswith("-review.md")
            ] if output_dir.is_dir() else []
            if not candidates:
                return ToLocalResult(
                    ok=False, output_file=None, sources_file=None,
                    package_dir=None, sources_count=0,
                    message=(
                        f"No research output found in {output_dir}. "
                        "Run `docent studio deep-research` or `docent studio lit` first."
                    ),
                )
            out_path = max(candidates, key=lambda p: p.stat().st_mtime)

        stem = out_path.stem
        sources_path = out_path.parent / f"{stem}-sources.json"

        has_sources = sources_path.exists()
        selected = (
            _rank_sources(
                json.loads(sources_path.read_text(encoding="utf-8")), 200
            )
            if has_sources else []
        )

        # ── Build local package ───────────────────────────────────────────────
        package_dir = out_path.parent / f"{stem}-local"
        package_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_path, package_dir / out_path.name)

        urls_text = "\n".join(s["url"] for s in selected if s.get("url"))
        (package_dir / "sources_urls.txt").write_text(urls_text, encoding="utf-8")

        if has_sources:
            shutil.copy2(sources_path, package_dir / sources_path.name)

        # ── Include guide files in package ───────────────────────────────────
        for gf_str in inputs.guide_files:
            gf = Path(gf_str).expanduser()
            if gf.exists():
                shutil.copy2(gf, package_dir / gf.name)

        # ── Optional Obsidian vault copy ─────────────────────────────────────
        vault_path: str | None = None
        if inputs.to_vault:
            vault = context.settings.research.obsidian_vault
            if vault:
                vault_dir = Path(vault).expanduser()
                vault_dir.mkdir(parents=True, exist_ok=True)
                dest = vault_dir / out_path.name
                shutil.copy2(out_path, dest)
                vault_path = str(dest)
            else:
                return ToLocalResult(
                    ok=True,
                    output_file=str(out_path),
                    sources_file=str(sources_path) if has_sources else None,
                    package_dir=str(package_dir),
                    sources_count=len(selected),
                    message=(
                        f"Package written to {package_dir}. "
                        "Vault copy skipped: obsidian_vault not configured "
                        "(set with: docent studio config-set --key obsidian_vault --value <path>)."
                    ),
                )

        parts = [f"Local package: {package_dir}", f"{len(selected)} source URL(s)"]
        if vault_path:
            parts.append(f"vault: {vault_path}")

        return ToLocalResult(
            ok=True,
            output_file=str(out_path),
            sources_file=str(sources_path) if has_sources else None,
            package_dir=str(package_dir),
            sources_count=len(selected),
            vault_path=vault_path,
            message=" -- ".join(parts),
        )

    @action(
        description="Search academic papers on alphaXiv by topic or keyword.",
        input_schema=SearchPapersInputs,
        name="search-papers",
    )
    def search_papers(self, inputs: SearchPapersInputs, context: Context) -> SearchPapersResult:
        from .alphaxiv_client import AlphaXivAuthError, search_papers as _search
        try:
            papers = _search(
                inputs.query,
                api_key=context.settings.research.alphaxiv_api_key,
                max_results=inputs.max_results,
            )
        except AlphaXivAuthError as e:
            return SearchPapersResult(ok=False, query=inputs.query, papers=[], count=0, message=str(e))
        except Exception as e:
            return SearchPapersResult(ok=False, query=inputs.query, papers=[], count=0, message=f"Search failed: {e}")
        return SearchPapersResult(
            ok=True,
            query=inputs.query,
            papers=papers,
            count=len(papers),
            message=f"Found {len(papers)} paper(s) for '{inputs.query}'.",
        )

    @action(
        description="Get AI-generated overview and abstract for an arXiv paper.",
        input_schema=GetPaperInputs,
        name="get-paper",
    )
    def get_paper(self, inputs: GetPaperInputs, context: Context) -> GetPaperResult:
        from .alphaxiv_client import AlphaXivAuthError, get_paper_overview
        # Normalize: strip arXiv URL to bare ID
        arxiv_id = inputs.arxiv_id.strip().rstrip("/")
        if "/" in arxiv_id:
            arxiv_id = arxiv_id.rsplit("/", 1)[-1]
        try:
            data = get_paper_overview(
                arxiv_id,
                api_key=context.settings.research.alphaxiv_api_key,
            )
        except AlphaXivAuthError as e:
            return GetPaperResult(ok=False, arxiv_id=arxiv_id, title=None, abstract="", overview="", message=str(e))
        except Exception as e:
            return GetPaperResult(ok=False, arxiv_id=arxiv_id, title=None, abstract="", overview="", message=f"Failed to fetch paper: {e}")
        return GetPaperResult(
            ok=True,
            arxiv_id=arxiv_id,
            title=data["title"],
            abstract=data["abstract"],
            overview=data["overview"],
            message=f"Retrieved overview for {arxiv_id}.",
        )

    @action(
        description="Search academic papers via Google Scholar (with Semantic Scholar and CrossRef as fallbacks).",
        input_schema=ScholarlySearchInputs,
        name="scholarly-search",
    )
    def scholarly_search(self, inputs: ScholarlySearchInputs, context: Context) -> ScholarlySearchResult:
        from .scholarly_client import search_scholarly
        try:
            papers, backend = search_scholarly(
                inputs.query,
                inputs.max_results,
                semantic_scholar_api_key=context.settings.research.semantic_scholar_api_key,
            )
        except RuntimeError as e:
            return ScholarlySearchResult(
                ok=False, query=inputs.query, papers=[], count=0,
                backend_used="none", message=str(e),
            )
        except Exception as e:
            return ScholarlySearchResult(
                ok=False, query=inputs.query, papers=[], count=0,
                backend_used="none", message=f"Search failed: {e}",
            )
        if not papers:
            return ScholarlySearchResult(
                ok=False, query=inputs.query, papers=[], count=0,
                backend_used=backend,
                message=f"No results found for '{inputs.query}' (via {backend}).",
            )
        return ScholarlySearchResult(
            ok=True,
            query=inputs.query,
            papers=papers,
            count=len(papers),
            backend_used=backend,
            message=f"Found {len(papers)} paper(s) for '{inputs.query}' (via {backend}).",
        )

    @action(
        description="Show research settings.",
        input_schema=ConfigShowInputs,
        name="config-show",
    )
    def config_show(self, inputs: ConfigShowInputs, context: Context) -> ConfigShowResult:
        from docent.utils.paths import config_file
        rs = context.settings.research
        return ConfigShowResult(
            config_path=str(config_file()),
            output_dir=str(rs.output_dir),
            feynman_command=rs.feynman_command or ["feynman"],
            oc_provider=rs.oc_provider,
            oc_model_planner=rs.oc_model_planner,
            oc_model_writer=rs.oc_model_writer,
            oc_model_verifier=rs.oc_model_verifier,
            oc_model_reviewer=rs.oc_model_reviewer,
            oc_model_researcher=rs.oc_model_researcher,
            oc_budget_usd=rs.oc_budget_usd,
            tavily_api_key=rs.tavily_api_key,
            tavily_research_timeout=rs.tavily_research_timeout,
            semantic_scholar_api_key=rs.semantic_scholar_api_key,
            feynman_model=rs.feynman_model,
            feynman_timeout=rs.feynman_timeout,
            notebooklm_notebook_id=rs.notebooklm_notebook_id,
            obsidian_vault=str(rs.obsidian_vault) if rs.obsidian_vault else None,
            alphaxiv_api_key=rs.alphaxiv_api_key,
        )

    @action(
        description="Set a research setting (output_dir).",
        input_schema=ConfigSetInputs,
        name="config-set",
    )
    def config_set(self, inputs: ConfigSetInputs, context: Context) -> ConfigSetResult:
        from docent.utils.paths import config_file
        if inputs.key not in _KNOWN_RESEARCH_KEYS:
            return ConfigSetResult(
                ok=False,
                key=inputs.key,
                value=inputs.value,
                config_path=str(config_file()),
                message=f"Unknown key {inputs.key!r}. Known: {sorted(_KNOWN_RESEARCH_KEYS)}.",
            )
        path = write_setting(f"research.{inputs.key}", inputs.value)
        return ConfigSetResult(
            ok=True,
            key=inputs.key,
            value=inputs.value,
            config_path=str(path),
            message=f"Set research.{inputs.key} = {inputs.value!r} in {path}.",
        )

    @action(
        description="Compare two research artifacts (arXiv IDs, PDFs, or URLs) side by side.",
        input_schema=CompareInputs,
        preflight=_preflight_oc_only,
    )
    def compare(self, inputs: CompareInputs, context: Context):
        topic_label = f"{inputs.artifact_a} vs {inputs.artifact_b}"
        slug = _slugify(_artifact_slug(inputs.artifact_a) + "-vs-" + _artifact_slug(inputs.artifact_b)) + "-compare"

        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_compare

            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                result_data = yield from run_compare(
                    inputs.artifact_a, inputs.artifact_b, oc,
                    model_researcher=context.settings.research.oc_model_researcher,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False, backend="docent", workflow="compare",
                    topic_or_artifact=topic_label, output_file=None, returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False, backend="docent", workflow="compare",
                    topic_or_artifact=topic_label, output_file=None, returncode=None,
                    message=result_data.get("error") or "Compare failed.",
                )

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            out_file.write_text(result_data["comparison"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "compare"
            )
            return ResearchResult(
                ok=True, backend="docent", workflow="compare",
                topic_or_artifact=topic_label, output_file=str(out_file), returncode=0,
                notebook_id=notebook_id, vault_path=vault_path,
                message=f"Comparison complete.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(phase="start", message=f"Starting Feynman compare: {topic_label!r}")
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/compare {inputs.artifact_a} {inputs.artifact_b}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="compare",
                topic_or_artifact=topic_label, output_file=None, returncode=None, message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False, backend="feynman", workflow="compare",
                topic_or_artifact=topic_label, output_file=output_file, returncode=returncode, message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True, backend="feynman", workflow="compare",
                topic_or_artifact=topic_label, output_file=None, returncode=returncode,
                message=f"Compare completed for {topic_label!r}, but no output file was found.",
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "compare"
        )
        return ResearchResult(
            ok=True, backend="feynman", workflow="compare",
            topic_or_artifact=topic_label, output_file=output_file, returncode=returncode,
            notebook_id=notebook_id, vault_path=vault_path,
            message=f"Compare completed for {topic_label!r}.{extra}",
        )

    @action(
        description="Draft a paper section or document on a topic.",
        input_schema=DraftInputs,
        preflight=_preflight_oc_only,
    )
    def draft(self, inputs: DraftInputs, context: Context):
        slug = _slugify(inputs.topic) + "-draft"

        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_draft

            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            guide_ctx = _read_guide_files(inputs.guide_files)

            try:
                result_data = yield from run_draft(
                    inputs.topic, oc,
                    guide_context=guide_ctx,
                    model_writer=context.settings.research.oc_model_writer,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False, backend="docent", workflow="draft",
                    topic_or_artifact=inputs.topic, output_file=None, returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False, backend="docent", workflow="draft",
                    topic_or_artifact=inputs.topic, output_file=None, returncode=None,
                    message=result_data.get("error") or "Draft failed.",
                )

            out_file = output_dir / f"{slug}.md"
            out_file.write_text(result_data["draft"], encoding="utf-8")

            yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "draft"
            )
            return ResearchResult(
                ok=True, backend="docent", workflow="draft",
                topic_or_artifact=inputs.topic, output_file=str(out_file), returncode=0,
                notebook_id=notebook_id, vault_path=vault_path,
                message=f"Draft complete.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(phase="start", message=f"Starting Feynman draft: {inputs.topic!r}")
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/draft {inputs.topic}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="draft",
                topic_or_artifact=inputs.topic, output_file=None, returncode=None, message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False, backend="feynman", workflow="draft",
                topic_or_artifact=inputs.topic, output_file=output_file, returncode=returncode, message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True, backend="feynman", workflow="draft",
                topic_or_artifact=inputs.topic, output_file=None, returncode=returncode,
                message=f"Draft completed for {inputs.topic!r}, but no output file was found.",
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "draft"
        )
        return ResearchResult(
            ok=True, backend="feynman", workflow="draft",
            topic_or_artifact=inputs.topic, output_file=output_file, returncode=returncode,
            notebook_id=notebook_id, vault_path=vault_path,
            message=f"Draft completed for {inputs.topic!r}.{extra}",
        )

    @action(
        description="Build a replication guide for a paper (arXiv ID, PDF, or URL).",
        input_schema=ReplicateInputs,
        preflight=_preflight_oc_only,
    )
    def replicate(self, inputs: ReplicateInputs, context: Context):
        slug = _slugify(_artifact_slug(inputs.artifact)) + "-replicate"

        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_replicate

            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                result_data = yield from run_replicate(
                    inputs.artifact, oc,
                    model_researcher=context.settings.research.oc_model_researcher,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False, backend="docent", workflow="replicate",
                    topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False, backend="docent", workflow="replicate",
                    topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                    message=result_data.get("error") or "Replication analysis failed.",
                )

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            out_file.write_text(result_data["guide"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "replicate"
            )
            return ResearchResult(
                ok=True, backend="docent", workflow="replicate",
                topic_or_artifact=inputs.artifact, output_file=str(out_file), returncode=0,
                notebook_id=notebook_id, vault_path=vault_path,
                message=f"Replication guide complete.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(phase="start", message=f"Starting Feynman replicate: {inputs.artifact!r}")
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/replicate {inputs.artifact}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="replicate",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=None, message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False, backend="feynman", workflow="replicate",
                topic_or_artifact=inputs.artifact, output_file=output_file, returncode=returncode, message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True, backend="feynman", workflow="replicate",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=returncode,
                message=f"Replicate completed for {inputs.artifact!r}, but no output file was found.",
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "replicate"
        )
        return ResearchResult(
            ok=True, backend="feynman", workflow="replicate",
            topic_or_artifact=inputs.artifact, output_file=output_file, returncode=returncode,
            notebook_id=notebook_id, vault_path=vault_path,
            message=f"Replicate completed for {inputs.artifact!r}.{extra}",
        )

    @action(
        description="Audit a paper (arXiv ID, PDF, or URL) for methodology, claim validity, and reproducibility.",
        input_schema=AuditInputs,
        preflight=_preflight_oc_only,
    )
    def audit(self, inputs: AuditInputs, context: Context):
        slug = _slugify(_artifact_slug(inputs.artifact)) + "-audit"

        if inputs.backend == "docent":
            from .oc_client import OcClient
            from .pipeline import run_audit

            oc = OcClient(
                provider=context.settings.research.oc_provider,
                budget_usd=context.settings.research.oc_budget_usd,
            )
            output_dir = context.settings.research.output_dir.expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                result_data = yield from run_audit(
                    inputs.artifact, oc,
                    model_researcher=context.settings.research.oc_model_researcher,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                )
            except Exception as e:
                return ResearchResult(
                    ok=False, backend="docent", workflow="audit",
                    topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                    message=f"Pipeline error: {e}",
                )

            if not result_data["ok"]:
                return ResearchResult(
                    ok=False, backend="docent", workflow="audit",
                    topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                    message=result_data.get("error") or "Audit failed.",
                )

            out_file = output_dir / f"{slug}.md"
            review_file = output_dir / f"{slug}-review.md"
            out_file.write_text(result_data["report"], encoding="utf-8")
            review_file.write_text(result_data["review"], encoding="utf-8")

            yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

            notebook_id, vault_path, extra = yield from _route_output(
                inputs, out_file, None, context, "audit"
            )
            return ResearchResult(
                ok=True, backend="docent", workflow="audit",
                topic_or_artifact=inputs.artifact, output_file=str(out_file), returncode=0,
                notebook_id=notebook_id, vault_path=vault_path,
                message=f"Audit complete.{extra}",
            )

        # Feynman branch
        yield ProgressEvent(phase="start", message=f"Starting Feynman audit: {inputs.artifact!r}")
        feynman_cmd = context.settings.research.feynman_command or ["feynman"]
        output_dir = context.settings.research.output_dir.expanduser()
        workspace_dir = output_dir / "workspace"
        guide_ctx = _read_guide_files(inputs.guide_files)
        feynman_prompt = f"/audit {inputs.artifact}"
        if guide_ctx:
            names = ", ".join(Path(p).name for p in inputs.guide_files)
            feynman_prompt += f"\n\n## Guide context ({names})\n{guide_ctx}"
        cmd_args = ["--prompt", feynman_prompt]
        if context.settings.research.feynman_model:
            cmd_args = ["--model", context.settings.research.feynman_model] + cmd_args

        try:
            returncode, output_file, stderr_output = _run_feynman(
                feynman_cmd, cmd_args, workspace_dir, output_dir, slug,
                budget_usd=context.settings.research.feynman_budget_usd,
                timeout=context.settings.research.feynman_timeout,
            )
        except (FeynmanBudgetExceededError, FeynmanNotFoundError) as e:
            return ResearchResult(
                ok=False, backend="feynman", workflow="audit",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=None, message=str(e),
            )

        if returncode != 0:
            msg = _summarize_feynman_error(stderr_output, configured_model=context.settings.research.feynman_model)
            return ResearchResult(
                ok=False, backend="feynman", workflow="audit",
                topic_or_artifact=inputs.artifact, output_file=output_file, returncode=returncode, message=msg,
            )

        if output_file is None:
            return ResearchResult(
                ok=True, backend="feynman", workflow="audit",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=returncode,
                message=f"Audit completed for {inputs.artifact!r}, but no output file was found.",
            )

        out_path_obj = Path(output_file)
        notebook_id, vault_path, extra = yield from _route_output(
            inputs, out_path_obj, None, context, "audit"
        )
        return ResearchResult(
            ok=True, backend="feynman", workflow="audit",
            topic_or_artifact=inputs.artifact, output_file=output_file, returncode=returncode,
            notebook_id=notebook_id, vault_path=vault_path,
            message=f"Audit completed for {inputs.artifact!r}.{extra}",
        )

    @action(
        description="Show today's Feynman and OpenCode spend against configured budgets.",
        input_schema=UsageInputs,
    )
    def usage(self, inputs: UsageInputs, context: Context) -> UsageResult:
        import datetime
        from .oc_client import _read_oc_daily_spend
        from .search import _read_tavily_daily_requests
        feynman_spend = _read_daily_spend()
        oc_spend = _read_oc_daily_spend()
        tavily_requests = _read_tavily_daily_requests()
        rs = context.settings.research
        today = datetime.date.today().isoformat()
        return UsageResult(
            feynman_spend_usd=feynman_spend,
            oc_spend_usd=oc_spend,
            feynman_budget_usd=rs.feynman_budget_usd,
            oc_budget_usd=rs.oc_budget_usd,
            date=today,
            message=(
                f"Today ({today}): Feynman ${feynman_spend:.4f}"
                + (f" / ${rs.feynman_budget_usd:.2f}" if rs.feynman_budget_usd > 0 else "")
                + f", OpenCode ${oc_spend:.4f}"
                + (f" / ${rs.oc_budget_usd:.2f}" if rs.oc_budget_usd > 0 else "")
                + f", Tavily {tavily_requests} reqs"
                + " / 1000/mo free"
            ),
        )


def on_startup(context) -> None:  # noqa: ARG001
    """Check for Feynman updates once per day and notify the user."""
    import re
    from docent.utils.update_check import check_github_release
    from docent.ui import get_console

    try:
        cmd = _find_feynman(context.settings.research.feynman_command)
        raw = _feynman_version_from_package_json(cmd)
        m = re.search(r"\d+\.\d+(?:\.\d+)?", raw)
        current = m.group() if m else None
    except FeynmanNotFoundError:
        return  # not installed — doctor handles that; no update nag needed

    info = check_github_release(
        "companion-inc/feynman",
        current_version=current,
        upgrade_cmd="npm install -g @companion-ai/feynman@latest",
    )
    if info:
        get_console().print(
            f"[yellow]UPDATE AVAILABLE:[/] feynman {info.latest} is available "
            f"(run: {info.upgrade_cmd})"
        )



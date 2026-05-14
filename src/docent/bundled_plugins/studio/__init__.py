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
            f"Install with: npm install -g feynman\n"
            f"Or set the full path via: "
            f"docent research config-set --key feynman_command --value <path-to-feynman>"
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
                f"     docent research config-set --key feynman_model --value <provider/model>\n"
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
            f"  docent research config-set --key feynman_model --value <provider/model>\n"
            f"{_DOCS_FOOTER}"
        )

    if code == 429 or "RESOURCE_EXHAUSTED" in str(status):
        return (
            f"Feynman API quota exhausted.{model_note}\n"
            "To fix:\n"
            "  1. Add API credits to your provider account, or\n"
            "  2. Switch to a model with available credits:\n"
            f"     docent research config-set --key feynman_model --value <provider/model>\n"
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
            f"  docent research config-set --key feynman_model --value <provider/model>\n"
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
                f"Increase with `docent research config-set feynman_budget_usd <amount>` "
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

    try:
        result = subprocess.run(
            full_cmd, cwd=workspace_dir,
            stderr=subprocess.PIPE, text=True,
            timeout=timeout,
        )
        returncode = result.returncode
        stderr_output = result.stderr or ""
    except FileNotFoundError:
        # _find_feynman already validates the executable, so a FileNotFoundError
        # here means PATH/sys resolution succeeded but the binary itself failed
        # to start (e.g. missing interpreter on a .cmd wrapper on Windows).
        raise FeynmanNotFoundError(
            resolved_cmd,
            "The feynman executable was found but could not be started. "
            "This may indicate a corrupt installation. Try reinstalling: "
            "npm install -g feynman",
        )
    except subprocess.TimeoutExpired:
        returncode = -1
        stderr_output = (
            f"Feynman timed out after {timeout:.0f}s. "
            "The research task may still be running in the background. "
            "Try increasing the timeout with: "
            "docent research config-set --key feynman_timeout --value <seconds>"
        )

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


def _rank_sources(sources: list[dict], max_sources: int) -> list[dict]:
    """Rank sources: papers first (have abstracts), then web with full_text, then rest."""
    papers = [s for s in sources if s.get("source_type") == "paper" and s.get("url")]
    web_with_text = [
        s for s in sources
        if s.get("source_type") == "web" and s.get("url") and s.get("full_text")
    ]
    web_snippet_only = [
        s for s in sources
        if s.get("source_type") == "web" and s.get("url") and not s.get("full_text")
    ]
    ranked = papers + web_with_text + web_snippet_only
    seen: set[str] = set()
    unique: list[dict] = []
    for s in ranked:
        url = s.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(s)
    return unique[:max_sources]


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

class DeepInputs(BaseModel):
    topic: str = Field(..., description="Research topic or question.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default). 'docent' is planned.")


class LitInputs(BaseModel):
    topic: str = Field(..., description="Research topic or question.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default). 'docent' is planned.")


class ReviewInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, local PDF path, or URL to review.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default). 'docent' is planned.")


class ConfigShowInputs(BaseModel):
    pass


class ConfigSetInputs(BaseModel):
    key: str = Field(..., description="Setting key under [research]: 'output_dir'.")
    value: str = Field(..., description="New value.")


class ToNotebookInputs(BaseModel):
    output_file: str | None = Field(
        None,
        description=(
            "Path to a research output .md file (e.g. 'storm-surge-ghana-deep.md'). "
            "If omitted, the most recent output in research.output_dir is used."
        ),
    )
    max_sources: int = Field(
        20,
        description="Maximum number of sources to include (default 20).",
    )
    notebook_id: str | None = Field(
        None,
        description=(
            "NotebookLM notebook ID (from the URL when viewing the notebook). "
            "Overrides research.notebooklm_notebook_id in config. "
            "If neither is set, falls back to package export + browser open."
        ),
    )


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

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.output_file is not None:
            shapes.append(LinkShape(url=self.output_file, label="Output file"))
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



class ToNotebookResult(BaseModel):
    ok: bool
    output_file: str | None
    sources_file: str | None
    package_dir: str | None
    sources_count: int
    sources_added: int = 0
    sources_failed: int = 0
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.sources_added:
            shapes.append(MetricShape(label="Sources pushed to NotebookLM", value=self.sources_added))
        if self.sources_failed:
            shapes.append(MetricShape(label="Sources failed", value=self.sources_failed))
        if self.package_dir:
            shapes.append(LinkShape(url=self.package_dir, label="Local package"))
        return shapes



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



# ---------------------------------------------------------------------------
# NotebookLM CLI helpers
# ---------------------------------------------------------------------------

def _nlm_exe() -> str | None:
    """Return the path to the notebooklm executable, or None if not on PATH."""
    return shutil.which("notebooklm")


def _nlm_run(args: list[str], timeout: float = 30) -> tuple[int, str, str]:
    """Run a notebooklm command. Returns (returncode, stdout, stderr)."""
    import os
    exe = _nlm_exe()
    if not exe:
        return -1, "", "notebooklm not found on PATH"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(
            [exe] + args, capture_output=True, text=True, timeout=timeout, env=env
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout after {timeout:.0f}s"
    except OSError as e:
        return -1, "", str(e)


def _nlm_auth_ok() -> bool:
    """Return True if notebooklm is installed and authenticated."""
    exe = _nlm_exe()
    if not exe:
        return False
    rc, stdout, _ = _nlm_run(["list", "--json"], timeout=20)
    if rc != 0:
        return False
    try:
        data = json.loads(stdout)
        # Auth failure returns {"error": true, ...}
        return not (isinstance(data, dict) and data.get("error"))
    except (json.JSONDecodeError, ValueError):
        return False


def _nlm_create_notebook(title: str) -> str | None:
    """Create a new NotebookLM notebook. Returns notebook ID on success, None on failure."""
    rc, stdout, _ = _nlm_run(["create", title, "--json"], timeout=30)
    if rc != 0:
        return None
    try:
        data = json.loads(stdout)
        return data.get("id") or data.get("notebook_id")
    except (json.JSONDecodeError, ValueError):
        return None


def _nlm_add_source(source: str, notebook_id: str) -> tuple[int, str]:
    """Add a single source (URL or file path) to a NotebookLM notebook.

    Returns (returncode, error_message). returncode 0 = success.
    """
    rc, _, stderr = _nlm_run(
        ["source", "add", source, "-n", notebook_id, "--json"], timeout=30
    )
    return rc, stderr


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
}


def _preflight_docent(inputs: BaseModel, context: Context) -> None:
    """Pre-flight check for deep/lit actions with ``backend='docent'``.

    Runs *before* the generator is created (and therefore before Rich
    Progress takes over stdin).  Checks OcClient availability and
    interactively resolves the Tavily API key if needed.

    Non-docent backends are a no-op so the same preflight can be used
    for all actions.
    """
    if getattr(inputs, "backend", None) != "docent":
        return

    from .oc_client import OcClient

    oc = OcClient(
        provider=context.settings.research.oc_provider,
        budget_usd=context.settings.research.oc_budget_usd,
    )
    if not oc.is_available():
        import typer
        from docent.ui.console import get_console
        get_console().print(
            "[red]Error:[/] OpenCode server is not running. "
            "Start it with: [cyan]opencode serve --port 4096[/]"
        )
        raise typer.Exit(1)

    tavily_key = _resolve_tavily_key(context)
    if not tavily_key:
        import typer
        from docent.ui.console import get_console
        get_console().print(
            "[red]Error:[/] Tavily API key is required for web search. "
            "Get one at https://tavily.com (free tier: 1,000 calls/month)."
        )
        raise typer.Exit(1)


def _preflight_oc_only(inputs: BaseModel, context: Context) -> None:
    """Pre-flight check for review action (needs OcClient but not Tavily)."""
    if getattr(inputs, "backend", None) != "docent":
        return

    from .oc_client import OcClient

    oc = OcClient(
        provider=context.settings.research.oc_provider,
        budget_usd=context.settings.research.oc_budget_usd,
    )
    if not oc.is_available():
        import typer
        from docent.ui.console import get_console
        get_console().print(
            "[red]Error:[/] OpenCode server is not running. "
            "Start it with: [cyan]opencode serve --port 4096[/]"
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

            try:
                result_data = yield from run_deep(
                    inputs.topic, oc,
                    model_planner=context.settings.research.oc_model_planner,
                    model_writer=context.settings.research.oc_model_writer,
                    model_verifier=context.settings.research.oc_model_verifier,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                    tavily_api_key=tavily_key,
                    semantic_scholar_api_key=context.settings.research.semantic_scholar_api_key,
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

            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="deep",
                topic_or_artifact=inputs.topic,
                output_file=str(out_file),
                returncode=0,
                message=f"Deep research complete. {result_data['rounds']} search round(s), {len(result_data['sources'])} sources.",
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
        cmd_args = ["--prompt", f"/deepresearch {inputs.topic}"]
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

        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="deep",
            topic_or_artifact=inputs.topic,
            output_file=output_file,
            returncode=returncode,
            message=f"Deep research completed for {inputs.topic!r}.",
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

            try:
                result_data = yield from run_lit(
                    inputs.topic, oc,
                    model_planner=context.settings.research.oc_model_planner,
                    model_writer=context.settings.research.oc_model_writer,
                    model_verifier=context.settings.research.oc_model_verifier,
                    model_reviewer=context.settings.research.oc_model_reviewer,
                    tavily_api_key=tavily_key,
                    semantic_scholar_api_key=context.settings.research.semantic_scholar_api_key,
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

            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="lit",
                topic_or_artifact=inputs.topic,
                output_file=str(out_file),
                returncode=0,
                message=f"Literature review complete. {result_data['rounds']} search round(s), {len(result_data['sources'])} sources.",
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
        cmd_args = ["--prompt", f"/lit {inputs.topic}"]
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

        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="lit",
            topic_or_artifact=inputs.topic,
            output_file=output_file,
            returncode=returncode,
            message=f"Literature review completed for {inputs.topic!r}.",
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

            return ResearchResult(
                ok=True,
                backend="docent",
                workflow="review",
                topic_or_artifact=inputs.artifact,
                output_file=str(out_file),
                returncode=0,
                message=f"Peer review complete for {inputs.artifact!r}.",
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

        return ResearchResult(
            ok=True,
            backend="feynman",
            workflow="review",
            topic_or_artifact=inputs.artifact,
            output_file=output_file,
            returncode=returncode,
            message=f"Review completed for {inputs.artifact!r}.",
        )

    @action(
        description=(
            "Create a new NotebookLM notebook and populate it with research sources. "
            "Creates the notebook automatically; no prior setup needed. "
            "Falls back to local package export + browser if the CLI is unavailable or unauthenticated."
        ),
        input_schema=ToNotebookInputs,
        name="to-notebook",
    )
    def to_notebook(self, inputs: ToNotebookInputs, context: Context):
        import time
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

        if not sources_path.exists():
            return ToNotebookResult(
                ok=False, output_file=str(out_path), sources_file=None,
                package_dir=None, sources_count=0,
                message=(
                    f"No sources file found at {sources_path}. "
                    "Sources are only saved when using backend='docent'. "
                    "The Feynman backend does not expose individual sources."
                ),
            )

        sources: list[dict] = json.loads(sources_path.read_text(encoding="utf-8"))
        selected = _rank_sources(sources, inputs.max_sources)

        # ── Write local package (always — useful as a local record) ──────────
        package_dir = out_path.parent / f"{stem}-notebook"
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "sources_urls.txt").write_text(
            "\n".join(s["url"] for s in selected if s.get("url")),
            encoding="utf-8",
        )
        shutil.copy2(out_path, package_dir / out_path.name)
        yield ProgressEvent(phase="package", message=f"Local package written to {package_dir}")

        # ── Check CLI and auth ───────────────────────────────────────────────
        yield ProgressEvent(phase="check", message="Checking NotebookLM CLI and auth...")
        if not _nlm_exe():
            import webbrowser
            webbrowser.open("https://notebooklm.google.com")
            return ToNotebookResult(
                ok=True,
                output_file=str(out_path), sources_file=str(sources_path),
                package_dir=str(package_dir), sources_count=len(selected),
                message=(
                    "notebooklm CLI not found — opened browser. "
                    f"Local package at {package_dir}. "
                    "Install with: pip install notebooklm-py"
                ),
            )

        if not _nlm_auth_ok():
            import webbrowser
            webbrowser.open("https://notebooklm.google.com")
            return ToNotebookResult(
                ok=True,
                output_file=str(out_path), sources_file=str(sources_path),
                package_dir=str(package_dir), sources_count=len(selected),
                message=(
                    "NotebookLM auth expired — opened browser. "
                    "Run `notebooklm login` then retry. "
                    f"Local package at {package_dir}."
                ),
            )

        # ── Resolve or create notebook ───────────────────────────────────────
        notebook_id = inputs.notebook_id or context.settings.research.notebooklm_notebook_id
        created_notebook = False

        if not notebook_id:
            title = f"Studio: {stem}"
            yield ProgressEvent(phase="notebook", message=f"Creating notebook '{title}'...")
            notebook_id = _nlm_create_notebook(title)
            if not notebook_id:
                return ToNotebookResult(
                    ok=False, output_file=str(out_path), sources_file=str(sources_path),
                    package_dir=str(package_dir), sources_count=len(selected),
                    message="Failed to create NotebookLM notebook. Check `notebooklm login`.",
                )
            created_notebook = True
            yield ProgressEvent(phase="notebook", message=f"Notebook created — ID: {notebook_id}")

        # ── Add synthesis doc first, then sources ────────────────────────────
        added = 0
        failed = 0

        yield ProgressEvent(phase="push", message="Adding research synthesis document...")
        rc, _err = _nlm_add_source(str(out_path), notebook_id)
        if rc == 0:
            added += 1
        else:
            failed += 1
        time.sleep(1)

        url_sources = [s for s in selected if s.get("url")]
        total = len(url_sources)
        for i, s in enumerate(url_sources, 1):
            url = s["url"]
            title_short = s.get("title", url)[:60]
            yield ProgressEvent(
                phase="push",
                message=f"[{i}/{total}] {title_short}",
                current=i,
                total=total,
            )
            rc, _err = _nlm_add_source(url, notebook_id)
            if rc == 0:
                added += 1
            else:
                failed += 1
            time.sleep(1)

        msg = f"Notebook ready: {added} source(s) added"
        if failed:
            msg += f" ({failed} failed)"
        if created_notebook:
            msg += f". New notebook ID: {notebook_id} — save it with: docent studio config-set --key notebooklm_notebook_id --value {notebook_id}"
        else:
            msg += f". Notebook: {notebook_id}"

        return ToNotebookResult(
            ok=True,
            output_file=str(out_path),
            sources_file=str(sources_path),
            package_dir=str(package_dir),
            sources_count=len(selected),
            sources_added=added,
            sources_failed=failed,
            message=msg,
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
    from docent.utils.update_check import check_github_release
    from docent.ui import get_console

    info = check_github_release(
        "companion-inc/feynman",
        upgrade_cmd="npm install -g @companion-ai/feynman",
    )
    if info:
        get_console().print(
            f"[yellow]UPDATE AVAILABLE:[/] feynman {info.latest} is available "
            f"(run: {info.upgrade_cmd})"
        )



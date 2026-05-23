"""Research tool: run deep research, literature reviews, and peer reviews via Feynman."""
from __future__ import annotations

from docent.core import Tool, register_tool

# ── Re-exports kept for backward compatibility ────────────────────────────────
# Tests and external callers import these directly from the studio package.
from ._notebook import _nlm_push, _rank_sources, _find_sources_path, ToNotebookInputs, ToNotebookResult  # noqa: F401
from .feynman import (
    FeynmanNotFoundError,
    _extract_feynman_cost,  # noqa: F401 — re-exported for tests
    _find_feynman,
    _feynman_version_from_package_json,
    _run_feynman,  # noqa: F401 — re-exported (tests may patch studio._run_feynman)
    _summarize_feynman_error,  # noqa: F401 — re-exported for tests
)
from .helpers import (
    _append_references,  # noqa: F401 — re-exported for tests
    _artifact_slug,  # noqa: F401
    _build_references_section,  # noqa: F401 — re-exported for tests
    _read_guide_files,  # noqa: F401
    _slugify,  # noqa: F401
    _strip_references_section,  # noqa: F401 — re-exported for tests
)
from .models import (  # noqa: F401
    AuditInputs,
    CompareInputs,
    ConfigSetInputs,
    ConfigSetResult,
    ConfigShowInputs,
    ConfigShowResult,
    DeepInputs,
    DraftInputs,
    GetPaperInputs,
    GetPaperResult,
    LitInputs,
    ReadOutputInputs,
    ReadOutputResult,
    SaveSynthesisInputs,
    SaveSynthesisResult,
    ReplicateInputs,
    ResearchResult,
    ReviewInputs,
    ScholarlySearchInputs,
    ScholarlySearchResult,
    SearchPapersInputs,
    SearchPapersResult,
)
from .preflights import (  # noqa: F401
    _preflight_docent,
    _preflight_oc_only,
    _preflight_to_notebook,
    _resolve_tavily_key,
    _route_output,
    _write_to_vault,
)

# ── Mixin action families ─────────────────────────────────────────────────────
from docent.bundled_plugins.studio._research import ResearchMixin
from docent.bundled_plugins.studio._notebook_actions import NotebookMixin
from docent.bundled_plugins.studio._search_actions import SearchMixin
from docent.bundled_plugins.studio._config_actions import ConfigMixin
from docent.bundled_plugins.studio._studio_shared import _KNOWN_RESEARCH_KEYS, _PRICING_NOTE  # noqa: F401
from docent.bundled_plugins.studio._init_helpers import _path_under  # noqa: F401


@register_tool
class StudioTool(ResearchMixin, NotebookMixin, SearchMixin, ConfigMixin, Tool):
    """Run research workflows (deep research, literature review, peer review) via Feynman."""

    name = "studio"
    description = "Run research workflows (deep research, literature review, peer review) via Feynman."
    category = "studio"


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
        return

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

"""Studio prompt registry — the single load path for every LLM prompt.

Every prompt the studio package sends to a model lives as a markdown file in
``agents/``. Nothing should be an inline prompt string constant anywhere in the
package. Keeping prompts as versioned files means:

  * a prompt change shows up as a clean, reviewable diff;
  * the eval suite (``tests/eval_studio.py``) can be re-run before any change;
  * ``tests/test_prompts_registry.py`` can prove no prompt file is orphaned,
    no registry entry is dangling, and no prompt has been edited without the
    hash manifest (and therefore the eval) being refreshed.

Placeholders use ``{name}`` and are filled by the caller with
``str.replace("{name}", value)`` — NOT ``str.format`` — so a prompt may contain
literal braces. Several do (JSON examples in ``gap_evaluator.md``,
``search_planner.md``), which ``str.format`` would raise on.
"""

from __future__ import annotations

from pathlib import Path

AGENTS_DIR = Path(__file__).parent / "agents"

# Canonical set of every prompt the studio package loads. The registry test
# asserts this set exactly matches the .md files in AGENTS_DIR — add a prompt
# file and you must add its name here, and vice versa.
PROMPT_NAMES: frozenset[str] = frozenset(
    {
        # deep / lit research pipeline
        "search_planner",
        "lit_planner",
        "gap_evaluator",
        "writer",
        "lit_writer",
        "verifier",
        "reviewer",
        "refiner",
        # single-shot studio workflows
        "compare_researcher",
        "draft_writer",
        "replicate_researcher",
        "audit_researcher",
        "review_researcher",
        # NotebookLM quality gates (to-notebook)
        "quality_gate",
        "perspectives",
        # citation graph enrichment (--expand-citations)
        "citation_enricher",
    }
)


def load_prompt(name: str) -> str:
    """Return the text of ``agents/{name}.md`` (UTF-8)."""
    return (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")

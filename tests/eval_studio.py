"""Golden-set eval harness for the studio pipeline.

Run all eval tests:
    uv run pytest tests/eval_studio.py -v

Skip in normal CI (fast suite):
    uv run pytest -m "not eval"

Each test mocks external API calls (Tavily, OcClient, academic search) with
pre-captured fixtures, runs the real pipeline logic end-to-end, and scores the
result against expected structural properties.

Score threshold: >= 0.8 to pass (80% of checks must pass).
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from docent.core import ProgressEvent

_FIXTURES_DIR = Path(__file__).parent / "golden" / "studio" / "fixtures"
_SCORER = Path(__file__).parent / "golden" / "studio" / "scorer.py"

PASS_THRESHOLD = 0.8


# ─── helpers ──────────────────────────────────────────────────────────────────

def _drain(gen: Any) -> Any:
    """Drive a generator to completion and return its StopIteration value."""
    if not inspect.isgenerator(gen):
        return gen
    try:
        while True:
            next(gen)
    except StopIteration as e:
        return e.value


def _load_fixtures() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in _FIXTURES_DIR.glob("*.json")]


def _scorer():
    import importlib.util
    spec = importlib.util.spec_from_file_location("scorer", _SCORER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.score_result


def _make_tavily_gen(mock_result: dict):
    """Return a generator-function that mocks tavily_research."""
    def _fake(topic, api_key, *, model="pro", timeout=600.0):
        yield ProgressEvent(phase="research", message="[mock] Tavily research complete.")
        return mock_result
    return _fake


# ─── pipeline golden tests ─────────────────────────────────────────────────────

@pytest.mark.eval
@pytest.mark.parametrize("fixture", _load_fixtures(), ids=lambda f: f["id"])
def test_pipeline_golden(fixture: dict) -> None:
    """Run the full pipeline with mocked API calls and score the result."""
    from docent.bundled_plugins.studio.pipeline import run_deep, run_lit
    from docent.bundled_plugins.studio.oc_client import OcClient

    mock = fixture["mock"]
    tavily_mock_data = {
        "content": mock["tavily_content"],
        "sources": mock["tavily_sources"],
    }
    academic_sources = mock.get("academic_sources", [])

    oc_responses = iter([mock["oc_review"], mock["oc_refiner"]])

    def fake_oc_call(prompt: str, model: str = "", timeout: float = 300) -> str:
        return next(oc_responses, "(mock fallback)")

    action = fixture["action"]
    pipeline_fn = run_deep if action == "run_deep" else run_lit

    with (
        patch("docent.bundled_plugins.studio.pipeline.tavily_research",
              _make_tavily_gen(tavily_mock_data)),
        patch("docent.bundled_plugins.studio.pipeline.academic_search_parallel",
              return_value=academic_sources),
        patch.object(OcClient, "call", fake_oc_call),
    ):
        oc = OcClient()
        gen = pipeline_fn(fixture["topic"], oc, tavily_api_key="tvly-mock")
        result = _drain(gen)

    score_result = _scorer()
    sc, failures = score_result(result, fixture["expected"])
    assert sc >= PASS_THRESHOLD, (
        f"[{fixture['id']}] Quality score {sc:.2f} below {PASS_THRESHOLD:.2f}. "
        f"Failed checks: {failures}\nResult keys: {list(result.keys())}\n"
        f"Draft preview: {result.get('draft', '')[:200]!r}"
    )


# ─── pure-function unit tests (no mocks needed) ────────────────────────────────

def test_build_references_section_basic() -> None:
    from docent.bundled_plugins.studio import _build_references_section
    sources = [
        {"title": "Paper A", "url": "https://a.com", "source_type": "web"},
        {"title": "Paper B", "url": "https://b.com", "source_type": "arxiv"},
    ]
    out = _build_references_section(sources)
    assert "## References" in out
    assert "Paper A" in out
    assert "https://b.com" in out
    assert "1." in out and "2." in out


def test_build_references_section_skips_no_url() -> None:
    from docent.bundled_plugins.studio import _build_references_section
    sources = [
        {"title": "No URL source", "url": "", "source_type": "web"},
        {"title": "Has URL", "url": "https://example.com", "source_type": "web"},
    ]
    out = _build_references_section(sources)
    assert "No URL source" not in out
    assert "Has URL" in out


def test_build_references_section_empty_returns_empty() -> None:
    from docent.bundled_plugins.studio import _build_references_section
    assert _build_references_section([]) == ""


def test_strip_references_section_removes_trailing_refs() -> None:
    from docent.bundled_plugins.studio import _strip_references_section
    draft = "Main content here.\n\n## References\n1. Source A\n2. Source B\n"
    stripped = _strip_references_section(draft)
    assert "## References" not in stripped
    assert "Main content here" in stripped


def test_strip_references_section_no_refs_unchanged() -> None:
    from docent.bundled_plugins.studio import _strip_references_section
    draft = "Content with no references section."
    assert _strip_references_section(draft) == draft


def test_append_references_replaces_existing_section() -> None:
    from docent.bundled_plugins.studio import _append_references
    draft = "Content.\n\n## References\n1. Old ref [web]"
    sources = [{"title": "New Ref", "url": "https://new.com", "source_type": "web"}]
    result = _append_references(draft, sources)
    assert result.count("## References") == 1
    assert "New Ref" in result
    assert "Old ref" not in result


def test_append_references_adds_section_when_none_exists() -> None:
    from docent.bundled_plugins.studio import _append_references
    draft = "Content without references."
    sources = [{"title": "Source", "url": "https://example.com", "source_type": "web"}]
    result = _append_references(draft, sources)
    assert "## References" in result
    assert "Source" in result


def test_append_references_empty_sources_adds_nothing() -> None:
    from docent.bundled_plugins.studio import _append_references
    draft = "Content."
    result = _append_references(draft, [])
    assert "## References" not in result
    assert result.strip() == draft.strip()

"""Scoring logic for studio pipeline golden-set evaluations.

Each check contributes equally to the score. The final score is the fraction
of checks that pass (0.0-1.0). A score >= 0.8 is the pass threshold.
"""
from __future__ import annotations


def score_result(result: dict, expected: dict) -> tuple[float, list[str]]:
    """Score a pipeline result dict against expected properties.

    Returns (score, list_of_failed_check_names).
    """
    checks: dict[str, bool] = {}

    checks["ok"] = result.get("ok") is True

    draft = result.get("draft", "")
    sources = result.get("sources", [])
    review = result.get("review", "")

    if (min_len := expected.get("min_draft_length")):
        checks["draft_length"] = len(draft) >= min_len

    if expected.get("review_non_empty"):
        checks["review_non_empty"] = bool(review.strip())

    if (min_src := expected.get("min_sources_count")):
        checks["sources_count"] = len(sources) >= min_src

    if expected.get("sources_have_url"):
        checks["sources_have_url"] = all(s.get("url") for s in sources) if sources else False

    for kw in expected.get("contains_keywords", []):
        checks[f"keyword_{kw}"] = kw.lower() in draft.lower()

    if expected.get("error_is_none"):
        checks["error_is_none"] = result.get("error") is None

    if (rounds := expected.get("min_rounds")):
        checks["rounds"] = result.get("rounds", 0) >= rounds

    failures = [k for k, v in checks.items() if not v]
    score = (len(checks) - len(failures)) / len(checks) if checks else 1.0
    return score, failures

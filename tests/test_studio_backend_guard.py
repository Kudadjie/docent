"""The 'free' backend aggregates sources only — it cannot generate text.

These tests pin the guard on the text-generating studio actions: they must
reject backend='free' with a clear message (instead of silently falling through
to the Feynman branch), while deep/lit keep their source-only free tier.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from docent.bundled_plugins.studio.models import (
    AuditInputs,
    CompareInputs,
    DeepInputs,
    DraftInputs,
    LitInputs,
    ReplicateInputs,
    ReviewInputs,
)

# (model, required-kwargs) for every text-generating, AI-only action.
_AI_ONLY = [
    (DraftInputs, {"topic": "X"}),
    (ReviewInputs, {"artifact": "a"}),
    (CompareInputs, {"artifact_a": "a", "artifact_b": "b"}),
    (ReplicateInputs, {"artifact": "a"}),
    (AuditInputs, {"artifact": "a"}),
]


@pytest.mark.parametrize("model, kw", _AI_ONLY)
def test_ai_only_actions_reject_free_backend(model, kw):
    with pytest.raises(ValidationError, match="aggregates sources"):
        model(backend="free", **kw)


@pytest.mark.parametrize("model, kw", _AI_ONLY)
def test_ai_only_actions_accept_ai_backends(model, kw):
    # The UI default and the documented alternatives must all validate.
    for backend in ("docent", "feynman", "groq"):
        assert model(backend=backend, **kw).backend == backend
    # Archived backends still pass via the CLI --backend flag (no enum lock).
    assert model(backend="anthropic", **kw).backend == "anthropic"


@pytest.mark.parametrize("model", [DeepInputs, LitInputs])
def test_deep_and_lit_still_accept_free(model):
    assert model(topic="X", backend="free").backend == "free"


# ── Config-show result must mask secrets before leaving the process ──────────
# The UI subprocess emitter serializes result.to_ui() over the WebSocket to the
# browser; raw API keys must never cross that boundary.


def _config_result(**overrides):
    from docent.bundled_plugins.studio.models import ConfigShowResult

    base = dict(
        config_path="/x/config.toml",
        output_dir="~/docent",
        feynman_command=["feynman"],
        oc_provider="opencode-go",
        oc_model_planner="m",
        oc_model_writer="m",
        oc_model_verifier="m",
        oc_model_reviewer="m",
        oc_model_researcher="m",
    )
    base.update(overrides)
    return ConfigShowResult(**base)


def test_config_show_to_ui_masks_api_keys():
    import json

    r = _config_result(
        tavily_api_key="tvly-secret1234567890",
        semantic_scholar_api_key="ss-anothersecret999",
        alphaxiv_api_key="ax-supersecretkey99",
    )
    data = r.to_ui()

    # Masked: never the raw secret, but a recognisable fragment.
    assert data["tavily_api_key"] == "tvly...7890"
    assert data["semantic_scholar_api_key"] == "ss-a...t999"
    assert data["alphaxiv_api_key"] == "ax-s...ey99"
    # The raw secret must not appear anywhere in the serialized payload.
    blob = json.dumps(data)
    assert "tvly-secret1234567890" not in blob
    assert "ss-anothersecret999" not in blob
    # Non-secret fields pass through untouched.
    assert data["output_dir"] == "~/docent"


def test_config_show_to_ui_handles_unset_keys():
    data = _config_result().to_ui()
    assert data["tavily_api_key"] == "(not set)"
    assert data["alphaxiv_api_key"] == "(not set)"

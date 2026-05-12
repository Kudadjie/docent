# Brief: Phase F2 — OC spend tracking + BYOK config + usage action

## Goal

Three additions to the research tool:
1. Track OpenCode API spend per call and persist daily to disk
2. Expose `oc_provider` and per-stage model config so users can route to their own provider
3. New `usage` action that shows today's Feynman + OC spend side by side

**Files to modify:**
- `src/docent/config/settings.py` — add OC provider/model fields to `ResearchSettings`
- `src/docent/bundled_plugins/research_to_notebook/oc_client.py` — track spend after each call
- `src/docent/bundled_plugins/research_to_notebook/pipeline.py` — use settings for provider/model
- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — new `usage` action, update `config-show`, update `_KNOWN_RESEARCH_KEYS`

**Tests:**
- `tests/test_oc_client.py` — unit tests for OcClient spend tracking
- Add `TestUsageAction` class to `tests/test_research_tool.py`

Do NOT create new files beyond the test file above.

---

## Read first

- `src/docent/config/settings.py` — current `ResearchSettings`
- `src/docent/bundled_plugins/research_to_notebook/oc_client.py` — full file
- `src/docent/bundled_plugins/research_to_notebook/pipeline.py` — how `OcClient.call()` is used
- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — `_read_daily_spend`, `_write_daily_spend` pattern (copy this for OC spend)

---

## Change 1: `src/docent/config/settings.py`

Add to `ResearchSettings`:

```python
# OpenCode provider and per-stage model overrides.
# oc_provider: the OpenCode providerID (default "opencode-go" = Go subscription).
# Set to "anthropic", "openai", etc. for BYOK via OpenCode.
oc_provider: str = "opencode-go"
oc_model_planner: str = "glm-5.1"       # search planner + gap evaluator
oc_model_writer: str = "minimax-m2.7"   # writer stage (long context)
oc_model_verifier: str = "glm-5.1"      # citation verifier
oc_model_reviewer: str = "deepseek-v4-pro"  # adversarial reviewer
oc_model_researcher: str = "glm-5.1"    # review workflow researcher stage
oc_budget_usd: float = 0.0              # 0.0 = no limit. Daily cap for OC calls.
```

Also add all of these to `_KNOWN_RESEARCH_KEYS` in `__init__.py`:
```python
_KNOWN_RESEARCH_KEYS = {
    "output_dir",
    "feynman_budget_usd",
    "oc_provider",
    "oc_model_planner",
    "oc_model_writer",
    "oc_model_verifier",
    "oc_model_reviewer",
    "oc_model_researcher",
    "oc_budget_usd",
}
```

---

## Change 2: `src/docent/bundled_plugins/research_to_notebook/oc_client.py`

### 2a. Add OC spend persistence helpers

Add a spend file path function and read/write helpers — copy the exact pattern from `__init__.py`'s `_spend_file` / `_read_daily_spend` / `_write_daily_spend` but for OC:

```python
def _oc_spend_file() -> Path:
    from docent.utils.paths import cache_dir
    return cache_dir() / "research" / "oc_spend.json"


def _read_oc_daily_spend() -> float:
    import datetime
    import json
    today = datetime.date.today().isoformat()
    try:
        data = json.loads(_oc_spend_file().read_text(encoding="utf-8"))
        if data.get("date") == today:
            return float(data.get("spend_usd", 0.0))
    except Exception:
        pass
    return 0.0


def _write_oc_daily_spend(spend: float) -> None:
    import datetime
    import json
    p = _oc_spend_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"date": datetime.date.today().isoformat(), "spend_usd": round(spend, 6)}),
        encoding="utf-8",
    )
```

These three functions must be module-level in `oc_client.py`, not inside the class.

### 2b. Update `OcClient.__init__` to accept provider override

```python
def __init__(
    self,
    base_url: str = _BASE_URL,
    provider: str = _DEFAULT_PROVIDER,
) -> None:
    self.base_url = base_url
    self.provider = provider
```

This already exists. No change needed here — the provider is already configurable. Good.

### 2c. Update `OcClient.call()` to extract and persist cost

Current `call()` returns the text. Update it to also extract cost from the response and persist:

```python
def call(self, prompt: str, model: str = "glm-5.1", timeout: int = 300) -> str:
    """Create a session, send the prompt, return the text response."""
    session_id = self._api("POST", "/session", {})["id"]
    response = self._api(
        "POST",
        f"/session/{session_id}/message",
        {
            "parts": [{"type": "text", "text": prompt}],
            "role": "user",
            "model": {"modelID": model, "providerID": self.provider},
        },
        timeout=timeout,
    )

    # Persist spend
    try:
        cost = float((response.get("info") or {}).get("cost") or 0.0)
        if cost > 0:
            _write_oc_daily_spend(_read_oc_daily_spend() + cost)
    except Exception:
        pass

    return "\n".join(
        p["text"] for p in response.get("parts", []) if p.get("type") == "text"
    )
```

The try/except around spend tracking is mandatory — never let cost tracking break an API call.

---

## Change 3: `src/docent/bundled_plugins/research_to_notebook/pipeline.py`

### 3a. Update `OcClient` construction to accept provider

`OcClient` already accepts `provider` in `__init__`. The pipeline constructs it implicitly (callers create it before passing). No change needed in `pipeline.py` itself.

### 3b. Thread settings-based model names through `_run_pipeline`

Currently `_run_pipeline` hardcodes model names:
```python
oc.call(planner_prompt, model="glm-5.1")     # planner
oc.call(writer_prompt, model="minimax-m2.7", timeout=600)  # writer
oc.call(verifier_prompt, model="glm-5.1", timeout=300)     # verifier
oc.call(reviewer_prompt, model="deepseek-v4-pro", timeout=300)  # reviewer
```

And `run_review` hardcodes:
```python
oc.call(researcher_prompt, model="glm-5.1", timeout=300)   # researcher
oc.call(reviewer_prompt, model="deepseek-v4-pro", timeout=300)  # reviewer
```

Add model parameters to `_run_pipeline` and `run_review`:

```python
def _run_pipeline(
    topic: str,
    oc: OcClient,
    planner_name: str,
    writer_name: str,
    *,
    on_progress=None,
    model_planner: str = "glm-5.1",
    model_writer: str = "minimax-m2.7",
    model_verifier: str = "glm-5.1",
    model_reviewer: str = "deepseek-v4-pro",
) -> dict:
```

And use these parameters instead of hardcoded strings inside `_run_pipeline`.

Update `run_deep` and `run_lit` to accept and forward these:

```python
def run_deep(topic, oc, *, on_progress=None,
             model_planner="glm-5.1", model_writer="minimax-m2.7",
             model_verifier="glm-5.1", model_reviewer="deepseek-v4-pro") -> dict:
    return _run_pipeline(
        topic, oc, "search_planner", "writer",
        on_progress=on_progress,
        model_planner=model_planner, model_writer=model_writer,
        model_verifier=model_verifier, model_reviewer=model_reviewer,
    )

def run_lit(topic, oc, *, on_progress=None,
            model_planner="glm-5.1", model_writer="minimax-m2.7",
            model_verifier="glm-5.1", model_reviewer="deepseek-v4-pro") -> dict:
    return _run_pipeline(
        topic, oc, "lit_planner", "lit_writer",
        on_progress=on_progress,
        model_planner=model_planner, model_writer=model_writer,
        model_verifier=model_verifier, model_reviewer=model_reviewer,
    )
```

Update `run_review`:
```python
def run_review(artifact, oc, *, on_progress=None,
               model_researcher="glm-5.1", model_reviewer="deepseek-v4-pro") -> dict:
```

And use `model_researcher`/`model_reviewer` inside `run_review`.

---

## Change 4: `src/docent/bundled_plugins/research_to_notebook/__init__.py`

### 4a. Thread model settings into Docent pipeline calls

In `deep()` docent branch:
```python
# After: oc = OcClient()
oc = OcClient(provider=context.settings.research.oc_provider)

# Pass model settings to run_deep:
result_data = run_deep(
    inputs.topic, oc,
    on_progress=_capture_progress,
    model_planner=context.settings.research.oc_model_planner,
    model_writer=context.settings.research.oc_model_writer,
    model_verifier=context.settings.research.oc_model_verifier,
    model_reviewer=context.settings.research.oc_model_reviewer,
)
```

Apply the same pattern in `lit()` (use `oc_model_planner/writer/verifier/reviewer`) and `review()` (use `oc_model_researcher/reviewer`).

### 4b. New `UsageInputs` and `UsageResult` models

```python
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

    def __rich_console__(self, console, options):
        from docent.ui.renderers import render_shapes
        render_shapes(self.to_shapes(), console)
        yield from ()
```

### 4c. New `usage` action

```python
@action(
    description="Show today's Feynman and OpenCode spend against configured budgets.",
    input_schema=UsageInputs,
)
def usage(self, inputs: UsageInputs, context: Context) -> UsageResult:
    import datetime
    from docent.bundled_plugins.research_to_notebook.oc_client import (
        _read_oc_daily_spend,
    )
    feynman_spend = _read_daily_spend()
    oc_spend = _read_oc_daily_spend()
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
        ),
    )
```

### 4d. Update `config-show` to display new settings

Add to `ConfigShowResult`:
```python
oc_provider: str
oc_model_planner: str
oc_model_writer: str
oc_model_verifier: str
oc_model_reviewer: str
oc_model_researcher: str
oc_budget_usd: float
```

And populate them from `context.settings.research` in `config_show()`.

Update `to_shapes()` to include `MetricShape` entries for each new field.

---

## Tests

### `tests/test_oc_client.py` — 5 tests

```python
"""Tests for OcClient spend tracking."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import docent.bundled_plugins.research_to_notebook.oc_client as oc_mod
from docent.bundled_plugins.research_to_notebook.oc_client import (
    OcClient, _read_oc_daily_spend, _write_oc_daily_spend,
)

@pytest.fixture(autouse=True)
def redirect_spend_file(tmp_path, monkeypatch):
    monkeypatch.setattr(oc_mod, "_oc_spend_file", lambda: tmp_path / "oc_spend.json")
```

1. `test_spend_starts_at_zero` — fresh state → `_read_oc_daily_spend() == 0.0`
2. `test_write_and_read_spend` — write 0.42, read back → 0.42
3. `test_spend_resets_for_new_day` — write with yesterday's date manually → read returns 0.0
4. `test_call_accumulates_cost` — mock `_api` to return `{"parts": [{"type":"text","text":"ok"}], "info": {"cost": 0.05}}` → after `call()`, `_read_oc_daily_spend() == 0.05`
5. `test_call_silent_on_missing_cost` — mock `_api` returning no `info` key → `call()` returns text, no exception, spend stays 0.0

### `TestUsageAction` in `tests/test_research_tool.py`

Add import: `UsageInputs, UsageResult` from research_to_notebook.

2 tests:
1. `test_usage_zero_spend` — fresh state → ok=True, both spends 0.0
2. `test_usage_shows_correct_spend` — mock `_read_daily_spend` and `_read_oc_daily_spend` to return known values → UsageResult fields match

---

## Invariants

1. Cost tracking in `OcClient.call()` must be wrapped in `try/except Exception` — NEVER let it raise.
2. `_read_oc_daily_spend` and `_write_oc_daily_spend` are module-level in `oc_client.py` (not class methods).
3. All model names default to current hardcoded values — existing tests must still pass unchanged.
4. `usage` action is NOT a generator — returns `UsageResult` directly.
5. No Rich markup in any `message` or shape `text`/`value` string field.
6. Run `python -m pytest tests/test_oc_client.py tests/test_research_tool.py --tb=short -q` until green.
7. Run `python -m pytest --tb=no -q` for full suite. Report count.

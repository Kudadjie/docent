# Brief: Research Tool — Phase E (Feynman budget guard)

## Goal

Add a spend-aware guard to the Feynman backend so users don't accidentally burn API tokens. Three parts:

1. `feynman_budget_usd: float = 0.0` setting in `ResearchSettings`
2. Post-run cost capture from Feynman's stderr output
3. Pre-run guard in `_run_feynman()`: warn + block at 90% of budget

**Files to modify:**
- `src/docent/config/settings.py` — add `feynman_budget_usd` field
- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — budget guard logic
- `src/docent/config/__init__.py` — no change needed (already exports Settings)

**Tests:**
- `tests/test_feynman_budget.py` — new test file

Do NOT touch `pipeline.py`, `search.py`, `oc_client.py`, or any test file other than the new one.

---

## Read these files first

- `src/docent/config/settings.py` — understand `ResearchSettings`
- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — understand `_run_feynman()` and the Feynman action branches

---

## Change 1: `src/docent/config/settings.py`

Add one field to `ResearchSettings`:

```python
feynman_budget_usd: float = 0.0
# 0.0 = no limit (default). Set to e.g. 2.00 to cap Feynman spend at $2 per session.
```

Also expose it in `config-set` — add `"feynman_budget_usd"` to `_KNOWN_RESEARCH_KEYS` in `__init__.py`.

---

## Change 2: `src/docent/bundled_plugins/research_to_notebook/__init__.py`

### 2a. Module-level spend tracker

Add near the top of the file (after imports, before `_slugify`):

```python
# Session-scoped Feynman spend accumulator. Reset on each process start.
_feynman_session_spend: float = 0.0
```

### 2b. Cost extraction helper

Add as a module-level function:

```python
import re as _re  # already imported — use existing `re` module

def _extract_feynman_cost(output: str) -> float:
    """Parse Feynman's stdout/stderr for a cost line. Returns 0.0 if not found.

    Feynman prints lines like: 'Cost: $0.43' or 'Total cost: $1.23'
    Uses a lenient regex — format may change across Feynman versions.
    """
    match = _re.search(r'\$(\d+(?:\.\d+)?)', output)
    return float(match.group(1)) if match else 0.0
```

### 2c. Update `_run_feynman()` signature and body

Current signature:
```python
def _run_feynman(cmd, workspace_dir, output_dir, slug) -> tuple[int, str | None]:
```

New signature:
```python
def _run_feynman(
    cmd: list[str],
    workspace_dir: Path,
    output_dir: Path,
    slug: str,
    *,
    budget_usd: float = 0.0,
) -> tuple[int, str | None]:
```

New body — add budget guard at the start, cost capture after run:

```python
def _run_feynman(cmd, workspace_dir, output_dir, slug, *, budget_usd=0.0):
    global _feynman_session_spend

    # Pre-run guard
    if budget_usd > 0:
        if _feynman_session_spend >= budget_usd * 0.9:
            raise FeynmanBudgetExceededError(
                f"Feynman budget nearly exhausted "
                f"(${_feynman_session_spend:.2f} of ${budget_usd:.2f} spent). "
                f"Increase with `docent research config-set feynman_budget_usd <amount>` "
                f"or use backend='docent'."
            )

    workspace_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir = workspace_dir / "outputs"
    before: set[Path] = set(outputs_dir.glob("*.md")) if outputs_dir.is_dir() else set()

    result = subprocess.run(cmd, cwd=workspace_dir, capture_output=True, text=True)

    # Post-run cost capture
    if budget_usd > 0:
        combined_output = (result.stdout or "") + (result.stderr or "")
        cost = _extract_feynman_cost(combined_output)
        _feynman_session_spend += cost

    # Print Feynman's output to terminal so user sees it
    if result.stdout:
        import sys
        sys.stdout.write(result.stdout)
    if result.stderr:
        import sys
        sys.stderr.write(result.stderr)

    after: set[Path] = set(outputs_dir.glob("*.md")) if outputs_dir.is_dir() else set()
    new_files = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)

    if not new_files:
        return result.returncode, None

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / f"{slug}.md"
    shutil.copy2(new_files[0], dest)
    return result.returncode, str(dest)
```

**IMPORTANT:** The original `_run_feynman` used `subprocess.run(cmd, cwd=workspace_dir)` with NO `capture_output` — Feynman inherited the terminal. We now need to capture output to parse the cost. But we must still show it to the user. The pattern above (capture + re-print to sys.stdout/stderr) achieves both.

**IMPORTANT:** `sys` is already in stdlib — no new import needed at module level. Use the local import pattern already established in the file.

### 2d. New exception class

Add near the top (after `_feynman_session_spend`):

```python
class FeynmanBudgetExceededError(RuntimeError):
    """Raised when Feynman session spend reaches 90% of the configured budget."""
```

### 2e. Pass `budget_usd` to `_run_feynman` in all three action branches

In `deep()` Feynman branch:
```python
# Before:
returncode, output_file = _run_feynman(cmd, workspace_dir, output_dir, slug)

# After:
returncode, output_file = _run_feynman(
    cmd, workspace_dir, output_dir, slug,
    budget_usd=context.settings.research.feynman_budget_usd,
)
```

Apply the same change in `lit()` and `review()` Feynman branches.

### 2f. Handle `FeynmanBudgetExceededError` in each action branch

Wrap `_run_feynman(...)` calls in the Feynman branches with a try/except:

```python
try:
    returncode, output_file = _run_feynman(
        cmd, workspace_dir, output_dir, slug,
        budget_usd=context.settings.research.feynman_budget_usd,
    )
except FeynmanBudgetExceededError as e:
    return ResearchResult(
        ok=False, backend="feynman", workflow="deep",  # adjust workflow per action
        topic_or_artifact=inputs.topic,  # or inputs.artifact for review
        output_file=None, returncode=None,
        message=str(e),
    )
```

Apply to `deep()`, `lit()`, and `review()` Feynman branches.

### 2g. Add `feynman_budget_usd` to `_KNOWN_RESEARCH_KEYS`

```python
_KNOWN_RESEARCH_KEYS = {"output_dir", "feynman_budget_usd"}
```

---

## Tests: `tests/test_feynman_budget.py`

```python
"""Tests for the Feynman budget guard."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import docent.bundled_plugins.research_to_notebook as rtn
from docent.bundled_plugins.research_to_notebook import (
    DeepInputs,
    FeynmanBudgetExceededError,
    ResearchTool,
    _extract_feynman_cost,
    _run_feynman,
)
from docent.config.settings import ResearchSettings, Settings
from docent.core.context import Context
```

**Helper:**
```python
def _mock_context(*, output_dir, budget_usd=0.0):
    research = ResearchSettings(
        output_dir=output_dir,
        feynman_budget_usd=budget_usd,
    )
    settings = MagicMock(spec=Settings)
    settings.research = research
    return Context(settings=settings, llm=MagicMock(), executor=MagicMock())
```

**Reset tracker between tests:**
```python
@pytest.fixture(autouse=True)
def reset_spend():
    rtn._feynman_session_spend = 0.0
    yield
    rtn._feynman_session_spend = 0.0
```

**8 tests:**

1. `test_extract_cost_dollar_sign` — `_extract_feynman_cost("Cost: $0.43")` → `0.43`
2. `test_extract_cost_no_match` — `_extract_feynman_cost("No cost here")` → `0.0`
3. `test_extract_cost_total_cost_format` — `_extract_feynman_cost("Total cost: $1.23")` → `1.23`
4. `test_no_budget_no_guard` — `budget_usd=0.0` + `_feynman_session_spend=9999` → no error raised (no limit when budget=0)
5. `test_budget_not_exceeded_runs` — `budget_usd=2.0`, spend=`0.0` → `_run_feynman` proceeds (mock subprocess, no budget error)
6. `test_budget_90_percent_blocks` — `budget_usd=2.0`, set `rtn._feynman_session_spend=1.80` (≥90% of $2.00) → `FeynmanBudgetExceededError` raised
7. `test_budget_accumulates_after_run` — mock subprocess returning `stdout="Cost: $0.50"`, `budget_usd=2.0` → after call, `rtn._feynman_session_spend == 0.50`
8. `test_deep_feynman_budget_exceeded_returns_error_result` — wire full action: mock `_run_feynman` to raise `FeynmanBudgetExceededError("over budget")` → `_drain(tool.deep(...))` returns `ResearchResult(ok=False, ...)` with "over budget" in message

For tests 5 and 7, mock `subprocess.run` to return a `CompletedProcess` with `returncode=0`, `stdout="Cost: $0.50"`, `stderr=""`. Also mock the outputs dir glob to return empty (no new .md files) to avoid file system complexity.

**Pattern for test 8:**
```python
def test_deep_feynman_budget_exceeded_returns_error_result(self, tmp_path):
    tool = ResearchTool()
    ctx = _mock_context(output_dir=tmp_path, budget_usd=1.0)
    with patch(
        "docent.bundled_plugins.research_to_notebook._run_feynman",
        side_effect=FeynmanBudgetExceededError("over budget"),
    ):
        result = _drain(tool.deep(DeepInputs(topic="test"), ctx))
    assert result.ok is False
    assert "over budget" in result.message
```

`_drain` is already defined in `tests/test_research_tool.py` — copy or import it here.

---

## Invariants

1. `FeynmanBudgetExceededError` must be module-level (not nested in a function).
2. `_feynman_session_spend` must be module-level (not class-level or instance-level).
3. Budget guard fires at **≥90%** of budget (not >90%). Check is `spend >= budget * 0.9`.
4. When `budget_usd == 0.0`, no guard runs at all — zero means no limit.
5. Feynman output (stdout + stderr) must still reach the terminal even when captured for cost parsing.
6. `_extract_feynman_cost` must return `0.0` (not raise) if no cost line is found.
7. Run `python -m pytest tests/test_feynman_budget.py --tb=short -v` and iterate until all 8 pass.
8. Run `python -m pytest --tb=no -q` — full suite must stay green. Report final count.

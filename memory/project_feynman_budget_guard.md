---
name: Research tool — Feynman budget guard
description: Plan to add a spend-aware guard before Feynman CLI calls (Phase E of research tool). Read before implementing the budget feature.
type: project
---

## Decision

Add a crude budget guard to the Feynman backend of ResearchTool. NOT a full per-tool cost estimator — just a flat session cap with a pre-run confirmation prompt and post-run cost capture.

**Why:** Feynman uses Anthropic API tokens. Without any guard, `docent research deep "topic"` can silently spend money. The memory file `thoughts_review_2026_04_29.md §8` explicitly deferred this to Phase C post-1.0 but the user wants it added now.

**How to apply:** Implement after Phase D (to-notebook) lands, as a focused Phase E change.

---

## Design

### Settings (add to `ResearchSettings` in `src/docent/config/settings.py`)

```python
feynman_budget_usd: float = 0.0
# 0.0 = no limit (default). Set to e.g. 2.00 for a $2 session cap.
```

Also expose in `config-set`: add `feynman_budget_usd` to `_KNOWN_RESEARCH_KEYS`.

### Session spend tracker

A module-level mutable (or a simple file in `cache_dir()`) that accumulates spend within a process session:

```python
_feynman_session_spend: float = 0.0
```

Reset on each new `docent` invocation (since it's module-level).

### Pre-run guard in `_run_feynman()`

Before running the command:
1. If `feynman_budget_usd > 0` and `_feynman_session_spend >= feynman_budget_usd * 0.9`:
   → Raise a clear error: "Feynman budget nearly exhausted ($X of $Y spent). Increase budget with `docent research config-set feynman_budget_usd <amount>` or use backend='docent'."
2. If `feynman_budget_usd > 0` (and under 90%):
   → Print a warning showing current spend and budget before running

### Post-run cost capture

Feynman prints cost to stderr in a line like: `Cost: $0.XX`
Parse it with a regex after `subprocess.run()` completes. Add to `_feynman_session_spend`.

**Risk:** Feynman's output format may change. Use a lenient regex: `r'\$(\d+\.\d+)'`. If parsing fails, log a warning but don't crash.

### Confirmation prompt

When `feynman_budget_usd > 0` and spend < 90% of budget, show:
```
Feynman will use Anthropic API tokens.
Session spend so far: $X.XX / $Y.YY budget
Continue? [y/N]
```

Use `prompt_for_path`-style interaction (check `NoInteractiveError` pattern from reading tool). If not interactive (MCP context), skip the prompt and proceed with a ProgressEvent warning instead.

### Files to modify

- `src/docent/config/settings.py` — add `feynman_budget_usd: float = 0.0`
- `src/docent/bundled_plugins/research_to_notebook/__init__.py`:
  - Add `_feynman_session_spend: float = 0.0` module-level var
  - Modify `_run_feynman()` to accept `budget` param and apply guard
  - Modify all Feynman branches in `deep()`, `lit()`, `review()` to pass budget from context
  - Add `feynman_budget_usd` to `_KNOWN_RESEARCH_KEYS`
- `tests/` — add `test_feynman_budget_guard.py`

---
name: Research tool — Feynman budget guard (SHIPPED)
description: Pre-implementation design doc for feynman_budget_usd spend guard. Feature shipped 2026-05-08. Archived 2026-05-11.
type: project
---

**STATUS: SHIPPED.** `feynman_budget_usd` setting and `_read_daily_spend()` / `_write_daily_spend()` are live in `src/docent/config/settings.py` and `src/docent/bundled_plugins/research_to_notebook/__init__.py`. Budget guard fires at 90% of configured budget; post-run cost is parsed from Feynman stderr and accumulated in `~/.docent/cache/research/feynman_spend.json` (daily rolling).

Archived from `memory/project_feynman_budget_guard.md` on 2026-05-11.

---

## Original design (for historical reference)

Add a crude budget guard to the Feynman backend of ResearchTool. NOT a full per-tool cost estimator — just a flat session cap with a pre-run confirmation prompt and post-run cost capture.

**Why:** Feynman uses Anthropic API tokens. Without any guard, `docent research deep "topic"` can silently spend money. The memory file `thoughts_review_2026_04_29.md §8` explicitly deferred this to Phase C post-1.0 but the user wants it added now.

### Settings
`feynman_budget_usd: float = 0.0` — 0.0 = no limit. Set to e.g. 2.00 for a $2 session cap.

### Guard logic
- Before run: if spend >= 90% of budget → raise with `docent research config-set feynman_budget_usd <amount>` hint
- Post-run: parse `Cost: $0.XX` from Feynman stderr; add to daily file-backed accumulator
- Non-interactive (MCP): skip prompt, emit ProgressEvent warning instead

### Files modified (as shipped)
- `src/docent/config/settings.py` — `feynman_budget_usd: float = 0.0`
- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — `_read_daily_spend`, `_write_daily_spend`, guard in `_run_feynman()`

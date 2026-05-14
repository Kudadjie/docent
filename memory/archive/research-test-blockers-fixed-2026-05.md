---
name: Research tool real-life test blockers (ARCHIVED — ALL FIXED)
description: All bugs fixed 2026-05-11; pipeline quality fixes applied. Archived 2026-05-14.
type: project
---

Archived from `project_research_test_blockers.md` 2026-05-14 — all bugs resolved, pipeline quality baked in.

## Credit model (corrected 2026-05-13)

- **Tavily**: free tier — no credit constraints, tests can run anytime
- **OpenCode model credits**: reset 2026-05-17 17:00 — blocks tests that route through OcClient (`studio deep-research/lit --backend oc` or similar)
- **Feynman API**: paid credits required regardless of model — feynman-backed tests blocked until credits are available

Tests using only the **native Tavily pipeline** are unblocked and can run anytime. OcClient and Feynman-backed tests are blocked on their respective credits.

## Bug 1 — Duplicate tool registration (FIXED 2026-05-11)

Root cause: absolute import `from docent.bundled_plugins.research_to_notebook.oc_client` in `usage()` caused `__init__.py` to execute under different `sys.modules` key. Fix A: relative import. Fix B: registry guard warns + skips on duplicate.

## Bug 2 — Missing `duckduckgo_search` dep (FIXED 2026-05-11)

Replaced DDG with Tavily across all files.

## Bug 3 — 0-sources pipeline producing garbage (FIXED 2026-05-11)

`web_search()` silently swallowed ALL exceptions (`except Exception: return []`). Tavily auth errors, rate limits, and network failures returned `[]` with no logging. Pipeline then fed 0 sources to 4 LLM stages, producing meta-commentary instead of research.

**Fixes:**
- `web_search()` now re-raises `InvalidAPIKeyError`/`UsageLimitExceededError`, logs other errors
- `search_depth="advanced"` added (better results)
- Tavily Research API as primary path (`tavily_research()` replaces stages 1-5)
- Zero-source abort guard in `_run_pipeline()`
- `tavily-python>=0.7.0` pinned in `pyproject.toml`

## Bug 4 — `No module named 'tavily'` on Windows (FIXED 2026-05-11)

`tavily-python` was installed in WSL's `.venv-wsl` but not in the Windows `.venv` that `docent` actually uses. Additionally, the Windows `.venv` had no `pyvenv.cfg` (broken venv).

**Fix:** Deleted and recreated Windows `.venv` from PowerShell:
```powershell
Remove-Item -Recurse -Force .venv
uv venv --python 3.11
uv sync
```

**Lesson:** Docent runs from Windows `.venv`, NOT WSL's `.venv-wsl`. Always sync deps in both environments after adding to `pyproject.toml`.

STATUS: All bugs fixed. 398 tests green (was 282/282 when first fixed, grew with subsequent work).

### F. Duplicate References section in markdown output
The Tavily Research API returns `content` that already includes a `## References` section. Then `__init__.py` blindly appended `_build_references_section(sources)`, producing two `## References` sections. **Fix:** new `_strip_references_section()` regex strips any existing `## References` block from the draft before appending. Called via `_append_references(draft, sources)` which strips first then appends. Both `deep-research` and `lit` action sites updated.

### G. Feynman FileNotFoundError — raw traceback when feynman not on PATH
`_run_feynman()` called `subprocess.run(cmd)` with default `["feynman", ...]`. If feynman isn't on PATH (or not installed), `subprocess.run` raises `FileNotFoundError` — an uncaught traceback, not a friendly error. **Fix:**
- New `FeynmanNotFoundError` exception with install instructions
- New `_find_feynman(configured_command)` that resolves the executable: PATH lookup → Windows npm global fallback (`%APPDATA%\npm\feynman.cmd`) → raises `FeynmanNotFoundError`
- `_run_feynman()` signature changed to accept `configured_command` and `subcommand_args` separately (resolves executable internally)
- `subprocess.run` wrapped in try/except FileNotFoundError → `FeynmanNotFoundError`
- All three action sites (deep-research, lit, review) catch `(FeynmanBudgetExceededError, FeynmanNotFoundError)`

## Pipeline quality fixes (2026-05-11, same session as bugs above)

### A. Tavily Research timeout too short
- Polling timeout: 300s → 600s (configurable via `tavily_research_timeout` setting)
- HTTP POST timeout: 60s → 90s

### B. Semantic Scholar 429 rate limit with no API key
- Added `semantic_scholar_api_key` setting (free key via https://www.semanticscholar.org/product/api#api-key-form)
- `paper_search()` passes `x-api-key` header when key is present
- 429 retry: 2 retries with 5s/10s exponential backoff

### C. Verifier model returning diffs instead of full drafts
- Verifier quality guard: if `len(verified_draft) < 0.3 * len(draft)`, fall back to original draft + log warning
- Verifier prompt tightened: "You must return the COMPLETE revised draft"

### E. Review feedback never fed back into the draft (refiner stage)
- New pipeline stage after review: refiner takes `{draft}` + `{review}`, addresses FATAL/MAJOR findings, returns complete revised draft
- `agents/refiner.md` prompt added
- Quality guard on refiner: if output < 50% of input, keep original
- Both Tavily and manual pipeline paths updated
- `config-show` now displays `tavily_api_key` (masked), `tavily_research_timeout`, `semantic_scholar_api_key` (masked)
- 280/280 tests green (at time of fix; now 398)

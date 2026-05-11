# CONTEXT - resume hint for next session

**Current Task:** v1.2.0 pre-release. Real-life tests #1–#8 PASSED. Tests #9–#19 remaining before release tag.

**Key Changes (2026-05-12):**
- References section appended to `.md` output — `_build_references_section()` in `__init__.py`, numbered entries with title, URL, source type for both `deep` and `lit` actions. `sources.json` kept alongside.
- Tavily quota exhaustion: `UsageLimitExceededError` caught specifically in `pipeline.py`, friendly message ("monthly free tier exceeded…"), skips manual-pipeline fallback (which would also fail). Other Tavily errors still fall back.
- Real-life test checklist updated: tests 1-8 passing, new tests 18 (quota exhaustion) and 19 (references section).
- Project memory files updated: `project_todos.md`, `build_progress.md`, `AI_CONTEXT.md`, `MEMORY.md`, `CONTEXT.md`, `research_tool_real_life_tests.md`.

**Previous session (2026-05-11):**
- Tavily Research API integration, web_search error propagation, zero-source abort, preflight, WSL2 detect, verifier guard, refiner stage, bug 1+2 fixes

**Next Steps:**
1. Run real-life tests #9–#19 (especially #9 lit review, #19 references section, #18 quota test)
2. After all tests pass: tag v1.2.0 release
3. Plan D: `docent doctor` + extended onboarding + `docent setup`

**File paths for this session's changes:**
- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — `_build_references_section()`, `deep()` and `lit()` actions append references
- `src/docent/bundled_plugins/research_to_notebook/pipeline.py` — `UsageLimitExceededError` catch + quota-exhaustion fallback skip
- `memory/tasks/research_tool_real_life_tests.md` — tests 1-8 results added, tests 18-19 new
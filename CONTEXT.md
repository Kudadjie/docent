# CONTEXT - resume hint for next session

**Current Task:** v1.2.0 omnibus release — hardening sprint + v1.3 planning + medium architectural debt ALL ship in v1.2.0. Feynman backend hardened. Real-life tests #1–#9 PASSED. 300 tests green. Tests #10-19 remaining (but not blocking — code fixes done, manual verification can happen anytime).

**Key Changes (2026-05-12):**
- Duplicate References: FIXED (`_strip_references_section()` + `_append_references()`)
- FeynmanNotFoundError: FIXED (`_find_feynman()` with PATH + Windows npm fallback)
- Feynman subprocess hang: FIXED (`--prompt` one-shot mode, removed `capture_output=True`)
- Feynman error summarizer: `_summarize_feynman_error()` — parses JSON Lines or regex-extracts from text, produces categorized actionable messages with model info + docs link
- New config: `feynman_model` (passes `--model` to feynman), `feynman_timeout` (default 900s)
- Storage warning for feynman's ~2GB `.feynman` dir captured for onboarding flow
- v1.2.0 scope expanded: hardening sprint + v1.3 planning + medium debt all ship before v1.2.0 tag

**Next Steps (ordered):**
1. Hardening sprint (items 7-9): UI server fix, reading monolith split, research DRY-up
2. v1.3 planning: `docent doctor` / onboarding command (tooling check, auth status, feynman storage warning)
3. Medium architectural debt (items 10-11): MCP single-action tools, edit --status bypass
4. Run remaining real-life tests #10-19 (can be done in parallel with above)
5. Tag v1.2.0 release

**File paths for this session's changes:**
- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — _summarize_feynman_error, _model_note, _find_feynman, FeynmanNotFoundError, _run_feynman (timeout, stderr PIPE), _strip_references_section, _append_references, --prompt mode
- `src/docent/config/settings.py` — feynman_model, feynman_timeout
- `tests/test_feynman_budget.py` — TestSummarizeFeynmanError (10 tests)
- `tests/test_research_tool.py` — updated assertions, stderr surfacing test
- `memory/` — build_progress, project_todos, roadmap_post_phase1 updated

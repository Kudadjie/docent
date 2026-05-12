# CONTEXT - resume hint for next session

**Current Task:** v1.2.0 omnibus release — hardening sprint + v1.3 planning + medium architectural debt ALL ship in v1.2.0. Feynman backend hardened. Reading monolith split complete. Research tool DRY-up complete. Real-life tests #1–#9 PASSED. 302 tests green. Tests #10-19 remaining (blocked on feynman reinstall + API credits).

**Key Changes (2026-05-12):**
- Duplicate References: FIXED (`_strip_references_section()` + `_append_references()`)
- FeynmanNotFoundError: FIXED (`_find_feynman()` with PATH + Windows npm fallback)
- Feynman subprocess hang: FIXED (`--prompt` one-shot mode, removed `capture_output=True`)
- Feynman error summarizer: `_summarize_feynman_error()` — parses JSON Lines or regex-extracts from text, produces categorized actionable messages with model info + docs link
- Feynman error messages improved: unified model attribution across JSON Lines + regex fallback; added `_DOCS_FOOTER` with "Adjust Feynman settings via its CLI" hint
- New config: `feynman_model` (passes `--model` to feynman), `feynman_timeout` (default 900s)
- Storage warning for feynman's ~2GB `.feynman` dir captured for onboarding flow
- Reading monolith split COMPLETE: `__init__.py` 1271→618 lines (-51%); new `models.py` (371, 23 Pydantic models) + `mendeley_sync.py` (351, 8 sync functions)
- v1.2.0 scope expanded: hardening sprint + v1.3 planning + medium debt all ship before v1.2.0 tag

**Next Steps (ordered):**
1. Hardening sprint (item 7): UI server fix
2. Medium architectural debt (item 11): edit --status bypass
3. v1.3 planning: `docent doctor` / onboarding command (tooling check, auth status, feynman storage warning)
4. Run remaining real-life tests #10-19 (blocked on API credits)
5. Tag v1.2.0 release

**File paths for this session's changes:**
- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — _summarize_feynman_error, _model_note, _DOCS_FOOTER, _find_feynman, FeynmanNotFoundError, _run_feynman, _strip_references_section, _append_references, --prompt mode
- `src/docent/bundled_plugins/reading/__init__.py` — slimmed 1271→618; imports from models.py + mendeley_sync.py
- `src/docent/bundled_plugins/reading/models.py` — NEW: 23 Pydantic models extracted from __init__.py
- `src/docent/bundled_plugins/reading/mendeley_sync.py` — NEW: 8 sync functions (sync_from_mendeley_run + helpers)
- `src/docent/config/settings.py` — feynman_model, feynman_timeout
- `tests/test_feynman_budget.py` — TestSummarizeFeynmanError (12 tests)
- `tests/test_sync_from_mendeley.py` — updated monkeypatch paths for new module structure
- `tests/conftest.py` — derive_id import updated
- `memory/` — build_progress, project_todos updated
- `AI_CONTEXT.md` — §8 updated with session changes

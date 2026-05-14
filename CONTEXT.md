# CONTEXT - resume hint for next session

**Current Task:** Phase 1.5 alpha-research port + PyPI update checks landed. Pre-v1.2.0 tag work.

**Key Decisions:**
- Python bumped 3.11 → 3.13; `alphaxiv-py>=0.5.0` added; 398 tests green
- `studio search-papers` + `get-paper` actions added (alphaxiv-py SDK, async→sync wrapper)
- `docent doctor` now checks `alphaxiv-py` + `notebooklm-py` with PyPI update hints (`check_pypi()`)

**Next Steps:**
1. Real-life tests #10–#19 (credits reset ~2026-05-17 17:00) — still blocked
2. Tag v1.2.0 (after real-life tests pass)
3. `scholarly-search` port (#19) and `literature-review` port (#20)

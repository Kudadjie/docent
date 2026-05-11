# CONTEXT - resume hint for next session

**Current Task:** Added mandatory docs/README update rule to CLAUDE.md; pre-v1.2.0 bugs still pending.

**Key Decisions:**
- Docs rule is MANDATORY: any CLI, feature, config, or behaviour change must update `docs/` and/or `README.md` in the same commit.
- Hermes delegation script (`scripts/hermes_delegate.py`) remains second delegation path.

**Next Steps:**
1. Fix Bug 1: duplicate tool registration (`ValueError` on `docent research usage`).
2. Fix Bug 2: replace `duckduckgo_search` with Tavily + add request count tracking in `usage`.
3. Re-run real-life tests from #3 onward; then tag v1.2.0.

# CONTEXT - resume hint for next session

**Current Task:** Pre-v1.2.0 bugs unresolved; 2 blockers remain before research tool real-life tests 3–17 can run.

**Key Decisions:**
- Model stack confirmed: GLM-5.1 for OpenCode delegation, Sonnet for Claude orchestration, Opus reserved for heavy reasoning only.
- Drop `duckduckgo_search`; switch to Tavily (1,000 req/month free).
- Both Kimi-2.6 and GLM-5.1 reviews saved; top priorities: UI server direct-invocation, reading monolith split, research tool DRY-up.

**Next Steps:**
1. Fix Bug 1: duplicate tool registration (`ValueError` on `docent research usage`).
2. Fix Bug 2: replace `duckduckgo_search` with Tavily + add request count tracking in `usage`.
3. Re-run real-life tests from #3 onward; then tag v1.2.0.

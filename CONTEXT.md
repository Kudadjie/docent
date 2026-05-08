# CONTEXT - resume hint for next session

**Current Task:** Research tool real-life testing started; blocked on 2 bugs before tests 3–17 can run.

**Key Decisions:**
- All 5 pre-v1.2.0 Codex blockers are DONE (Codex completed this pass).
- Drop `duckduckgo_search`; switch to Tavily (1,000 req/month free, purpose-built for agentic pipelines).
- Medium debt items 6 & 7 can be done before real-life testing — no reason to wait.

**Next Steps:**
1. Fix Bug 1: duplicate tool registration (`ValueError` on `docent research usage`).
2. Fix Bug 2: replace `duckduckgo_search` with Tavily + add request count tracking in `usage`.
3. Re-run real-life tests from #3 onward; then tag v1.2.0.

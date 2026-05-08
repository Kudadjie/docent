# CONTEXT — resume hint for next session

**Current Task:** UI polish — responsive layout, grey light mode, global status bar across all pages.

**Key Decisions:**
- StatusBanner is now global: `useDarkMode` hook extracted to `hooks/useDarkMode.ts`; settings page has full StatusBanner with dotState (working/done/error) wired to save/clear/version-check actions; reading-specific stats are optional props
- Light mode grey theme: --bg #f6f5f3, --bg-subtle #ebebea, --bg-card #ffffff; sidebar uses bg-subtle for darker panel feel; all modals use bg-card; borders strengthened to 0.08/0.13
- Research tool real-life test checklist written to memory/tasks/research_tool_real_life_tests.md (17 tests, priority ordered)

**Next Steps:**
1. REAL-LIFE TESTS — run research tool tests from the checklist (priority: #4 docent deep → #5 to-notebook → #13 usage)
2. v1.2.0 release — merge dev → main, tag, publish
3. Any remaining UI pages (dashboard, docs) should also get StatusBanner using the same useDarkMode + DotState pattern from StatusBanner.tsx

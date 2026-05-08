# CONTEXT — resume hint for next session

**Current Task:** UI polish session fully shipped and pushed — global status bar, grey light mode, screen gate, copy fixes, onboarding database folder, research test checklist.

**Key Decisions:**
- StatusBanner on every page (reading/settings/docs/dashboard) via useDarkMode hook; reading stats are optional props; dotState wired to save/clear/version-check on settings
- Light mode: --bg #f6f5f3, --bg-subtle #ebebea, --bg-card #fff; sidebar=bg-subtle, modals=bg-card
- Hard rule saved to memory: full real-life UI testing across entire app required before every release

**Next Steps:**
1. REAL-LIFE UI TESTING — click through all pages, dark/light mode, every action before marking v1.2.0 ready
2. REAL-LIFE RESEARCH TESTS — run checklist in memory/tasks/research_tool_real_life_tests.md (priority: #4 docent deep → #5 to-notebook → #13 usage)
3. v1.2.0 release — merge dev → main, tag, publish (only after both test passes)

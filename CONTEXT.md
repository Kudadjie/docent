# CONTEXT - resume hint for next session

**Current Task:** Reading page real-life test tweaks shipped; Studio + remaining pages still pending.

**Key Decisions:**
- Mendeley backend decoupled via `ReferenceManagerBackend` protocol + `MendeleyBackend` class; sync now flags (not_in_mendeley=True) instead of auto-removing entries
- Light mode fully restored (useDarkMode hook, light CSS vars); sessionStorage added for URL state persistence fix
- Sync = solid green, How to Add = solid purple; column header Paper→Entry; sort + extended filter; not-in-library review modal

**Next Steps:**
1. Restart `docent ui` (backend changed), then run Studio page test checklist against `http://localhost:7432`
2. Continue Ecosystem/Docs/Settings/Sidebar/Notification tests
3. Tag v1.2.0 once all sections pass; then execute p1_decouple_ui_mcp + p1_consolidate_studio_builders

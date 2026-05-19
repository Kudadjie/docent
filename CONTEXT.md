# CONTEXT - resume hint for next session

**Current Task:** UI Tweak Followup.txt — all 21 items shipped (session 5).

**Key Decisions:**
- Docs page: Ecosystem + Plugin Guide sections added; maxWidth removed
- Settings: 2-column grid layout; gradient bleeds full page
- react-markdown used for DocPreview + OutputsPanel (md-preview CSS class)
- Sidebar logo: 48px height (matches StatusBanner) for unified top bar visual
- DnD tab reorder: native HTML5 drag, Dashboard pinned, localStorage persists

**Next Steps:**
1. Run v1.2.0 UI tests from `memory/tasks/v120_ui_tests.md`
2. Investigate #3 (real-time streaming) — test a Feynman/Docent run; verify ProgressEvents emit mid-pipeline
3. Build static export: `python scripts/build_ui.py`, then tag v1.2.0

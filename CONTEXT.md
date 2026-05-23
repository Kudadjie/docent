# CONTEXT - resume hint for next session

**Current Task:** UI test checklist sprint toward v1.2.0 tag + CLI workspace REPL.

**Key Decisions:**
- Workspace REPL: `docent` / `docent <cmd>` enters interactive shell; guards on DOCENT_UI_SUBPROCESS + non-TTY keep UI subprocess safe
- research.output_dir now settable via Settings page and Onboarding modal (was CLI-only)
- sync_from_mendeley tests fixed: monkeypatch target moved to mendeley_client; removed→flagged drift corrected

**Next Steps:**
1. Rebuild frontend (`python scripts/build_ui.py`) — output_dir Settings field needs to land in ui_dist
2. Continue UI test checklist (Studio page items 10–27, then Ecosystem, Docs, Settings, Inbox, Sidebar, User Footer, Cross-cutting)
3. Fix any failures found, then tag v1.2.0
</content>
</invoke>
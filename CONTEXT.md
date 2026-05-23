# CONTEXT - resume hint for next session

**Current Task:** Shipped feynman_model Settings UI + Studio background runs (commit 072ba30 on dev).

**Key Decisions:**
- `feynman_model` exposed in Settings → Studio SectionCard (ConfigRow, not SecretKeyRow). Backend: GET/POST /api/config now returns `feynman_model` unmasked alongside API keys.
- Studio WS+run state lifted to `StudioRunProvider` at layout level (`lib/studio-run-context.tsx`). Removed the `useEffect(() => () => stopRun(), [])` cleanup from Studio page — navigation no longer kills a running task.
- Pre-existing test failures in test_research_tool.py fixed (3 tests asserting ok=True on no-output-file case, now correctly expect ok=False per ff95e61).

**Next Steps:**
1. Continue UI test checklist (Studio page items 10–27, then Ecosystem, Docs, Settings, Inbox, Sidebar, User Footer, Cross-cutting) — `memory/tasks/v120_ui_tests.md`
2. Tag v1.2.0 release once UI test checklist passes
3. Sidebar `currentRun` indicator now works across all pages (reads from StudioRunProvider context)

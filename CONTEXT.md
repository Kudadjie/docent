# CONTEXT - resume hint for next session

**Current Task:** Shipped AppRunContext — generic cross-page activity registry replacing Studio-specific coupling in status indicators (commit 1fc8e27 on dev).

**Key Decisions:**
- `AppRunProvider` (new `lib/app-run-context.tsx`) is the outermost layout wrapper; holds `Record<string, AppActivity|null>` keyed by feature ID. Any page calls `setActivity(id, info)` to register background work.
- `StudioRunProvider` stays nested inside `AppRunProvider`; syncs `status`+`currentPhase` into AppRunContext via `useEffect` (auto-clears after 3 s on done/fail/stopped).
- `Sidebar` + `StatusBanner` now import only `useAppRun()` — zero Studio coupling. Reading sync or any future page can light up the global indicators with one `setActivity()` call.

**Next Steps:**
1. Continue UI test checklist (Studio items 10–27, then Ecosystem, Docs, Settings, Inbox, Sidebar, User Footer, Cross-cutting) — `memory/tasks/v120_ui_tests.md`
2. Tag v1.2.0 release once UI test checklist passes

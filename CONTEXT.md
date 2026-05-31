# CONTEXT - resume hint for next session

**Current Task:** Codex review Wave 4 complete — repo hygiene, naming cleanup, schema migration all shipped on `dev`.

**Key Decisions:**
- Hygiene: Ruff 0 errors (whole repo), ESLint 0 errors, 633 tests. Plugin loader now catches `(Exception, SystemExit)` — lets `KeyboardInterrupt` propagate.
- Naming cleanup: `sync-from-library` is canonical action; `sync-from-mendeley` kept as back-compat alias. `HowToAddModal` + reading page modals now use `refManagerName` prop.
- Schema migration v1→v2: `mendeley_id` → `reference_id`, `not_in_mendeley` → `not_in_library` in `QueueEntry`. Migration runs transparently on load. `mendeley_sync.py` → `sync_engine.py`. Old class names (`SyncFromMendeleyInputs/Result`) kept as back-compat aliases.

**Next Steps:**
- **WSL test run** (mandatory before PR — CI runs Linux). Use `~/docent-venv`.
- Frontend component splitting: `settings/page.tsx` (~1605 lines) and `reading/page.tsx` (~1403 lines) — Wave 5.
- PR `dev` → `main` when WSL green.

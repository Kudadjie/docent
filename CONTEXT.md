# CONTEXT - resume hint for next session

**Current Task:** v1.2.0 omnibus hardening — UI server wired to invoke_action() (todo #1 done) and edit --status lifecycle fix (todo #2 done). 308 tests green.

**Key Decisions:**
- UI server `post_action` now calls `invoke_action()` in-process via `asyncio.to_thread`; no more subprocess-per-action
- `_apply_status_transition` helper extracted; `edit --status` now stamps `started`/`finished` correctly
- Hermes must not modify Windows `.venv` — see `memory/hermes.md`

**Next Steps:**
1. `docent doctor` + extended onboarding (Plan D) — tooling check, auth status, feynman ~2GB warning
2. Real-life tests #10-19 (blocked on credits — reset ~2026-05-17 17:00)
3. Tag v1.2.0

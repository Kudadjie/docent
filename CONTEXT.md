# CONTEXT — resume hint for next session

**Current Task:** UI todos complete — all must-dos, should-dos, and nice-to-haves shipped.

**Key Decisions:**
- Onboarding modal (WelcomeModal) on first load; saves to `~/.docent/user.json`; shared with CLI
- CLI first-run onboarding added to `app.callback()` in `cli.py`; skips silently in non-TTY contexts
- Table sorted by `order` asc; move-up/down now visually reorders rows immediately

**Next Steps:**
1. Cut `ui-v1.0.0` GitHub release — merge `dev` → `main`, tag `ui-v1.0.0`
2. Phase 1.5 — Output Shapes + `docent research` tool (Feynman primary, Claude fallback)
3. Consider `docent ui` command to launch the Next.js frontend from the CLI

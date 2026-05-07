# CONTEXT — resume hint for next session

**Current Task:** README corrected (removed premature "reading page is live" claim); UI shipping strategy decided and saved to memory.

**Key Decisions:**
- UI ships via PyPI (bundled into `docent-cli`), launched with `docent ui` — no separate installer
- Frontend stack: Next.js 16 + React 19 + TypeScript + Tailwind v4 + Lucide React (`frontend/package.json`)
- Commit build artifacts to repo for now; move build step to CI later

**Next Steps:**
1. UI must-dos for `ui-v1.0.0` — export button, edit modal, error toasts, scan/sync feedback (`memory/ui_todos.md`)
2. Cut `ui-v1.0.0` GitHub release — merge `dev` → `main`, tag `ui-v1.0.0`
3. Phase 1.5 — Output Shapes + `docent research` tool (Feynman primary, Claude fallback)

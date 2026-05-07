# CONTEXT — resume hint for next session

**Current Task:** CLI v1.0 shipped to PyPI (`docent-cli`) and GitHub (`v1.0.2`); main/dev branch split done; UI must-dos are next.

**Key Decisions:**
- Package name is `docent-cli` on PyPI (plain `docent` was taken); module name is still `docent`
- `main` = clean public branch (no memory/, oc_briefs/, .mcp.json, scripts/); `dev` = everything; all work goes to `dev`
- GitHub Actions publish triggers on `v*` tags (Trusted Publisher OIDC, no stored secrets)

**Next Steps:**
1. UI must-dos for `ui-v1.0.0` — export button, edit modal, error toasts, scan/sync feedback (`memory/ui_todos.md`)
2. Cut `ui-v1.0.0` GitHub release after must-dos done — merge `dev` → `main`, tag `ui-v1.0.0`
3. Phase 1.5 — Output Shapes + `docent research` tool (Feynman primary, Claude fallback)

# CONTEXT — resume hint for next session

**Current Task:** README fully polished (logo, badges, theme-aware SVG, Mintlify credit, Feynman link, Mendeley MCP note); CLI v1.0 live on PyPI; main/dev split done.

**Key Decisions:**
- Package name is `docent-cli` on PyPI; module name stays `docent`
- `main` = clean public branch; `dev` = everything; all work goes to `dev`, mirror doc-only changes to `main`
- GitHub Actions publishes on `v*` tags (Trusted Publisher OIDC)

**Next Steps:**
1. UI must-dos for `ui-v1.0.0` — export button, edit modal, error toasts, scan/sync feedback (`memory/ui_todos.md`)
2. Cut `ui-v1.0.0` GitHub release — merge `dev` → `main`, tag `ui-v1.0.0`
3. Phase 1.5 — Output Shapes + `docent research` tool (Feynman primary, Claude fallback)

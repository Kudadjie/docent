---
name: Docent release plan
description: Two separate release tracks — CLI releases and UI releases. Each has its own versioning and docs.
type: project
---

Created 2026-05-07 based on user direction.

## Two separate release tracks

### Track 1 — Docent CLI

**v1.0 milestone:** Step 13 complete (MCP adapter shipped 2026-05-07).
- Release as GitHub release with tag `v1.0.0`
- Docs page covering: install, `docent list`, each reading action, `docent serve` + MCP setup
- Changelog from git history

### Track 2 — Docent UI (Reading Page)

**v1.0 milestone:** UI todos in `memory/ui_todos.md` Must-do items complete:
  - Export button wired
  - Edit modal working
  - Error handling surfaced
  - Scan/sync success toast
- Release as separate GitHub release with tag `ui-v1.0.0`
- Docs page: how to run the frontend, feature screenshots

## How to apply

- Treat CLI and UI as independent. A new CLI action doesn't need to wait for UI work to ship, and vice versa.
- Each track gets its own GitHub release; the main README links to both.
- Future versions: `v1.1.0` for CLI when new tools land; `ui-v1.1.0` when significant UI features land.

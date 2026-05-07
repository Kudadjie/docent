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

## UI shipping strategy (decided 2026-05-07)

**Distribution method: bundle into PyPI package, launch via `docent ui`.**

- Frontend stack: Next.js 16 + React 19 + TypeScript + Tailwind CSS v4 + Lucide React (`frontend/package.json`)
- Ship via PyPI alongside CLI — no separate installer. Mirrors how TensorBoard, MLflow, Jupyter do it.
- `next build` output goes into `src/docent/ui_dist/` as package data.
- `docent ui` command starts a local server (FastAPI or stdlib) and opens the browser.
- For now: commit the `ui_dist/` build artifacts to the repo (personal tool, manageable size). Move build step to GitHub Actions CI later.
- One update path for users: `uv tool upgrade docent-cli` gets both CLI and UI.

**Why not an installer?** Users are grad students comfortable with Python tooling; PyPI keeps distribution unified and eliminates code-signing and platform packaging pain.

## How to apply

- Treat CLI and UI as independent. A new CLI action doesn't need to wait for UI work to ship, and vice versa.
- Each track gets its own GitHub release; the main README links to both.
- Future versions: `v1.1.0` for CLI when new tools land; `ui-v1.1.0` when significant UI features land.

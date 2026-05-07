# CONTEXT — resume hint for next session

**Current Task:** UI polish sprint complete (commit 27d690c on dev). Next milestone is bundled release (docent-ui inside docent-cli).

**Key Decisions:**
- Bundled release = FastAPI + Next.js static export; `docent ui` starts uvicorn on localhost:7432, Ctrl+C to stop. Full plan in `memory/project_ui_bundling.md`.
- Entries managed via Mendeley only — delete button removed from UI permanently.
- `__rich_console__` must be generator functions (`yield from ()`) — fixed on all 10 result classes.

**Next Steps:**
1. Bundled release: FastAPI server + `output: 'export'` + `docent ui` command (see memory/project_ui_bundling.md)
2. Fix publish.yml Action SHA pinning before any push to main
3. Phase 1.5-C research-to-notebook plugin (plan in memory/project_feynman_port.md)

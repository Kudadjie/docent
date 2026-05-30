# CONTEXT - resume hint for next session

**Current Task:** Tier-4 A + C DONE + verified on `dev` (uncommitted). Next: bring the Zotero integration into the UI (backend shipped #36, no UI surface yet).

**Key Decisions:**
- Tier-4 A (prompts-as-first-class-code) DONE: `studio/prompts.py` registry, 2 inline `_notebook.py` prompts → `agents/*.md`, `tests/test_prompts_registry.py` hash tripwire. See decisions.md 2026-05-30.
- Tier-4 C (model-facing surface) DONE: 36 shipped MCP descriptors clean; added `tests/test_mcp_surface.py` gate that snapshots/restores the global `_REGISTRY` to dodge sibling-test fixture pollution. No shipped-tool source changes.
- Tier-4 B (fan-out primitive) DEFERRED until citation-scavenger #42 (two-consumer rule).
- Verified green both platforms: Windows 631 passed, WSL 631 passed; ruff clean. Nothing committed yet.

**Next Steps:**
- Zotero → UI: Settings page reference-manager selector (mendeley|zotero) + API-key/library-id fields, wired to `reading.reference_manager` + `zotero_*` config. Read Settings page (`frontend/app/settings/page.tsx`) + `ui_routes/` first; design pass before coding.
- Commit A + C when user asks (not yet committed).
- **WSL testing:** use `~/docent-venv` (native ext4, 3.12+), NOT `.venv-wsl` or `/tmp`. See gotchas.md.

# CONTEXT — resume hint for next session

**Current Task:** MCP adapter fixed (placeholder path → real path in .mcp.json); startup message added to `run_server()`; MCP section in `docs/cli.md` expanded with example use cases.

**Key Decisions:**
- MCP tool naming: `{tool}__{action}` (double underscore, hyphens → underscores)
- Two independent release tracks: CLI (`v1.0.0`) and UI (`ui-v1.0.0`)
- Internal agentic tools (future `research` action) are separate from MCP — Docent calls LLM internally, MCP is for external Claude orchestration

**Next Steps:**
1. CLI v1.0 release — cut GitHub release tag `v1.0.0` with `docs/cli.md` as release notes
2. UI Must-do todos — export button, edit modal, error toasts, scan feedback (memory/ui_todos.md)
3. UI v1.0 release after Must-do done — tag `ui-v1.0.0`

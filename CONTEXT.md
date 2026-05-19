# CONTEXT - resume hint for next session

**Current Task:** Studio backend wired — SSE streaming endpoint live, free research runs end-to-end.

**Key Decisions:**
- `POST /api/studio/run` streams ProgressEvents as SSE; frontend reads with fetch + ReadableStream
- `_preflight_free_backend` now skips interactive prompts when `confirmed=True` (not just `via_mcp`); keeps `via_mcp=False` so output file gets human-readable footer, not MCP synthesis prompt
- `_serialize` imported from `mcp_server` into `ui_server` (was NameError on first live run)

**Next Steps:**
1. Wire result panels — `renderResult()` in `_output.tsx` still shows mock data; parse `done.raw` JSON to show real output file path, sources count, etc.
2. Test non-free backends (Feynman, Groq) through the UI
3. Tag v1.2.0 once Studio backend fully verified

# CONTEXT - resume hint for next session

**Current Task:** UX hardening + real-life test run — 43/45 tests passing, all committed to dev (5e0ae3d).

**Key Decisions:**
- `to-local` action removed (redundant with output_dir; vault push via `--output vault`)
- Budget guards + spend tracking removed; replaced with one-time pricing note (Anthropic callout)
- MCP server now streams log notifications per ProgressEvent — keeps long pipelines alive in Claude Desktop
- `--no-sync` added to Claude Desktop MCP config to prevent file-lock disconnect on startup

**Next Steps:**
1. Complete tests #14 (BYOK/provider config — needs API credits) and #15 (Feynman peer review)
2. Tag v1.2.0 after both pass
3. Tavily Research API `citation_format` param — wire when plan is upgraded

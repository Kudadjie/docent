# CONTEXT - resume hint for next session

**Current Task:** Free-tier studio backend + guide-files UX; MCP synthesis prompt; real-life test checklist updated.

**Key Decisions:**
- `--backend free`: Tavily → DuckDuckGo fallback chain; academic papers always paired; full disclaimer + confirm before running
- `Context.via_mcp=True` injected by MCP server; free-tier output uses `_MCP_SYNTHESIS_PROMPT` footer (AI-directed) vs `_MCP_NOTE_HUMAN` footer (CLI)
- `guide-files` supports individual files and folder expansion; unreadable files warn + confirm before running (preflight)

**Next Steps:**
1. Run studio real-life tests (all results cleared; 45-item checklist in memory/tasks/studio_real_life_tests.md)
2. Tag v1.2.0 after real-life tests pass
3. HTTP + SSE MCP transport added to roadmap (item #44 in project_todos.md) — prerequisite for mobile/remote access

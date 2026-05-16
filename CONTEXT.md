# CONTEXT - resume hint for next session

**Current Task:** to-notebook hardening sprint — committed and pushed to dev (897a2d7).

**Key Decisions:**
- Source ranking: relative recency within batch year range, domain authority tiers, per-domain cap (3); _find_sources_path checks both naming conventions
- NotebookLM tier (free=50 / Plus=100) set once in `docent setup`; notebook reuse via per-file .notebook-map.json
- Preflight guards: .md-only check, empty-file check, heading/filename mismatch → rename offer, sources-missing confirm

**Next Steps:**
1. Run remaining studio real-life tests (checklist in memory/tasks/studio_real_life_tests.md)
2. Tag v1.2.0 after real-life tests pass
3. HTTP + SSE MCP transport still on roadmap (item #44 in project_todos.md)

# CONTEXT — resume hint for next session

**Current Task:** Phase A (GitHub push readiness) complete. Phase 1.5-C next.

**Key Decisions:**
- CSO audit: 1 MEDIUM finding — pin `actions/checkout` + `astral-sh/setup-uv` to commit SHAs before first public push.
- Slash commands added: `/safe-commit`, `/code-reviewer`, `/test-engineer`, `/ui-spec-writer`.
- `oc_delegate.py` now writes UTF-8 via buffer — no more cp1252 choke on Unicode output.

**Next Steps:**
1. Fix publish.yml Action SHA pinning (before pushing to GitHub)
2. Phase 1.5-C: `research-to-notebook` tool port (registered Tool in the registry, MCP-callable)
3. Decide: standalone or bundled plugin? (bundled makes more sense — same pattern as reading tool)

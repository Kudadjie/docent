# CONTEXT — resume hint for next session

**Current Task:** Memory/context/architecture audit + cleanup complete.

**Key Decisions:**
- `decisions.md` now has ADR entries for all steps 11.8 → Phase 1.5-B (was cut off at 11.7).
- `Docent_Architecture.md` Layer 0 tree updated to match actual `src/docent/` layout.
- Stale references fixed: harness trigger, roadmap dead link, build_progress deferred section.

**Next Steps:**
1. Fix publish.yml Action SHA pinning (before pushing to GitHub) — still pending
2. Phase 1.5-C: `research-to-notebook` tool port (bundled plugin, same pattern as reading)
3. Eval harness trigger fires when research-to-notebook makes its first real LLM call

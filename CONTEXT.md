# CONTEXT - resume hint for next session

**Current Task:** Post-v1.2.0 sprint complete (items 13, 14, 16 done). Waiting on real-life tests #10–#19 to tag v1.2.0.

**Key Decisions:**
- Next.js API routes replaced with single `rewrites` rule in `next.config.ts` — dev now requires `docent ui` running at 7432
- `__rich_console__` removed from all 15 result models; CLI renders via `render_shapes(result.to_shapes(), console)` directly
- `tests/test_doc_flags.py` contract test verifies all `--flag` mentions in docs match registered schemas

**Next Steps:**
1. Real-life tests #10–#19 (Feynman credits + OpenCode credits reset ~2026-05-17 17:00)
2. Tag v1.2.0 (after tests pass)
3. Post-v1.2.0 next: Phase 1.5 skill ports (to-notebook, alpha-research, scholarly-search)

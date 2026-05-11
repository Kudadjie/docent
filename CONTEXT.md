# CONTEXT - resume hint for next session

**Current Task:** Hermes WSL delegation integrated; pre-v1.2.0 bugs still pending.

**Key Decisions:**
- Hermes added as second delegation script (`scripts/hermes_delegate.py`) — self-correcting loop, no server needed.
- Loop tasks → deepseek-v4-pro (1M ctx + reasoning); implement → glm-5.1; simple → qwen3.5-plus.
- `HERMES.md` at project root; memory preamble auto-injected for non-simple tasks via `--no-memory` to skip.

**Next Steps:**
1. Fix Bug 1: duplicate tool registration (`ValueError` on `docent research usage`).
2. Fix Bug 2: replace `duckduckgo_search` with Tavily + add request count tracking in `usage`.
3. Re-run real-life tests from #3 onward; then tag v1.2.0.

# CONTEXT - resume hint for next session

**Current Task:** Real-life test run hardening — all fixes committed to dev (8553752).

**Key Decisions:**
- Self-learning files moved from `~/.claude/skills/` → `~/.docent/data/notebook-learning/` (Docent-owned, no Claude skill dependency)
- `NetworkError` (D008) added; connectivity probed at pipeline start + every 30s in OcClient polling loop
- `--to-notebook` / `--to-local` chaining flags added to `deep` and `lit` (alias for `--output notebook/local`)

**Next Steps:**
1. Add `tenacity` to `pyproject.toml` dependencies (currently installed manually into venv)
2. Tavily Research API requires paid plan — wire `citation_format` param when plan is upgraded
3. Tag v1.2.0 after remaining real-life tests pass (`memory/tasks/studio_real_life_tests.md`)

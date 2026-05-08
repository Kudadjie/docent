# CONTEXT — resume hint for next session

**Current Task:** Bundled release shipped (v1.1.0, dev branch). `docent ui` now works out of the box after `pip install docent-cli`.

**Key Decisions:**
- One package, no install-mode split — fastapi/uvicorn bundled unconditionally
- Tag on dev (not main) is fine — git tags are branch-independent, CI triggers regardless
- `memory/` stays on dev; cherry-pick feature commits to main when ready for clean public branch

**Next Steps:**
1. Confirm v1.1.0 published successfully on PyPI (check Actions tab in GitHub)
2. Phase 1.5-C skill ports — `research-to-notebook` first (plan in memory/project_feynman_port.md)
3. Cherry-pick feature commits to main (skip chore(memory) commits) when ready

# CONTEXT — resume hint for next session

**Current Task:** v1.1.1 shipped to PyPI (bundled UI). Main merged from dev. Repo is clean.

**Key Decisions:**
- Wheel-only publish (no sdist) — sdist with ui_dist exceeded PyPI 100MB limit
- memory/ and CONTEXT.md excluded from main via .gitignore; tracked only on dev
- GitHub Release created manually for v1.1.1; future tags auto-create via workflow

**Next Steps:**
1. Phase 1.5-C skill ports — `research-to-notebook` first (plan in memory/project_feynman_port.md)
2. Cherry-pick _version.py gitignore fix to main (or let it ride until next merge)
3. Pin actions/setup-node to a real SHA in publish.yml before next CSO audit

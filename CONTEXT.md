# CONTEXT - resume hint for next session

**Current Task:** Wave 5 frontend split shipped — settings and reading page monoliths split into components.

**Key Decisions:**
- Zotero health check added to `/api/doctor` (UI); API key rows removed from health section (belong in API Keys only). CLI `docent doctor` unchanged.
- pyzotero was missing from tool env (stale install) — fixed with `uv tool install --reinstall --editable .`
- Wave 5: settings/page.tsx 1700→698 lines, reading/page.tsx 1488→973 lines. 12 new component/lib files. Zero TS errors, 633 tests green.

**Next Steps:**
- **WSL test run** (mandatory before PR — CI runs Linux). Use `~/docent-venv`.
- PR `dev` → `main` when WSL green.
- Citation scavenger (#42) — anchor paper → Semantic Scholar/Crossref citation tree → OA filter → download + queue. First consumer for Tier-4 B fan-out primitive.

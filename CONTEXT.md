# CONTEXT - resume hint for next session

**Current Task:** Full Codex review sprint — all 77 items addressed across 4 commits on dev (3cf589b).

**Key Decisions:**
- ui_server.py split: routes now in `src/docent/ui_routes/` via APIRouter (1264→530 lines)
- SearchAdapter: FakeSearchAdapter replaces @patch decorators in all pipeline tests
- Network guard: conftest.py blocks real external sockets in unit tests; integration mark exempts

**Next Steps:**
1. Tag v1.2.0 — run `python scripts/prerelease.py` first to verify, then tag
2. Studio/__init__.py split (item 33, 1490 lines) — deferred; still a single large file
3. Always use `http://localhost:7432`; rebuild with `python scripts/build_ui.py` after frontend changes

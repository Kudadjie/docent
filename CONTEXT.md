# CONTEXT - resume hint for next session

**Current Task:** Studio real-life tests (10-19 pending; 20-34 new pipeline tests added this session). Credits reset ~2026-05-17 17:00.

**Key Decisions:**
- Feynman update notification fixed: `on_startup` now reads installed version before comparing; silences correctly after update
- `docent setup` External Tools section now auto-installs Feynman + OpenCode (npm) and notebooklm-py (pip), with platform-aware Node.js hints
- Rule: every non-Python external tool must have a check in both `docent doctor` and `docent setup`

**Next Steps:**
1. Run studio real-life tests #10–#19 + #20–#34 after credits reset (~2026-05-17)
2. Write `docs/studio_spec.md` (no credits needed — can do anytime)
3. Tag v1.2.0 after real-life tests pass

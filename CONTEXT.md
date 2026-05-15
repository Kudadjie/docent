# CONTEXT - resume hint for next session

**Current Task:** Hardening sprint + pre-v1.2.0 todos; session closed 2026-05-15.

**Key Decisions:**
- Error codes D001-D007 shipped (`src/docent/errors.py`); `OcModelError.code` renamed to `.http_code`
- Eval harness lives in `tests/golden/studio/` — add JSON fixture = add test automatically
- #22 (schema-driven forms) and #23 (live telemetry SSE) are the only remaining batch items

**Next Steps:**
1. Run studio real-life tests #10–#19 (OpenCode credits reset ~2026-05-17 17:00; feynman needs reinstall for #10)
2. Tag v1.2.0 after real-life tests pass
3. Then: #22 schema-driven forms + #23 live telemetry pane (Phase 2 UI)

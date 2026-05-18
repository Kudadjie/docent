# CONTEXT - resume hint for next session

**Current Task:** All studio real-life tests complete. Docs sprint done.

**Key Decisions:**
- `oc_client` now reads OpenCode errors from `response["info"]["error"]["data"]` (not `response["error"]`); credit/balance keywords added; empty body returns `{}` not JSONDecodeError
- `✗` (U+2717) replaced with `FAIL` in preflights.py — not encodable in Windows CP1252
- UI specs in `docs/ui-specs/` (studio + reading); user guides in `docs/guides/` (studio + reading)

**Next Steps:**
1. Tag v1.2.0 (`git tag v1.2.0 && git push origin dev --tags`)
2. Design / build the Studio UI (start from `docs/ui-specs/studio-ui-spec.md`)
3. Design / build the Reading UI (start from `docs/ui-specs/reading-ui-spec.md`)

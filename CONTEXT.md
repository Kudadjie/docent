# CONTEXT - resume hint for next session

**Current Task:** Memory audit + cleanup; confirmed all 4 p1_* briefs were already shipped; cleaned docent install.

**Key Decisions:**
- All 4 architectural refactor briefs (studio split, ui_server split, ui/mcp decouple, builder consolidate) were already done — just not marked so
- Next.js API routes were removed; `next.config.ts` now proxies all /api/* to FastAPI (`ui_routes/`); two-file sync rule is obsolete
- Removed ghost `docent v0.1.0` install; single editable `docent-cli` install is the correct setup

**Next Steps:**
1. Make Mendeley/Zotero coexistence decision — blocks entire v2.1.0 track (Zotero bridge, plugin docs, tag)
2. Fix one open UI test: bell dropdown "mark all as read" (tasks/v120_ui_tests.md)
3. Plugin developer docs — API stable, no docs exist; write before Zotero bridge so bridge is built as a plugin

# CONTEXT - resume hint for next session

**Current Task:** Ploughing through memory audit backlog. Tier 1 + Tier 2 + most of Tier 3 done. Schema-driven forms shipped as a generic /tools page.

**Key Decisions:**
- Schema-driven forms (#22): shipped as a NEW generic `/tools` runner page (auto-form from `model_json_schema()`), NOT a Studio-form rewrite. Studio/Reading untouched. `ui_routes/tools.py` + `app/tools/`. Fixed an asyncio.run-in-loop bug via `asyncio.to_thread`. See decisions.md 2026-05-30.
- Mendeley/Zotero: coexist via `sync_source` toggle; pyzotero over zotero-mcp. Pre-req #35a: swap Mendeley MCP subprocess → direct httpx REST first.
- Plugin developer docs (#35): done — fixed plugin-guide.md §7/§9, added §13 (publish) + §10a (auto UI form).

**Next Steps:**
- Commit this work (not yet committed — on `dev`). Files: ui_routes/tools.py, app/tools/, tests, docs, ui_dist rebuild.
- Tier 3 remaining: Zotero bridge (#35a httpx swap → #36 pyzotero).
- Harness items (before v2.1.0): prompts-as-first-class-code eval, sub-agent fan-out formalization, model-facing surface review.

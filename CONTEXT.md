# CONTEXT — resume hint for next session

**Current Task:** Reading tool rewrite shipped — full rename from `paper` to `reading`, new schema, move actions, deadline notifications.

**Key Decisions:**
- `summary` field dropped from scope — no agentic tooling on the reading tool for now
- `priority` → `order: int` (1-based); `course` → `category + course_name`; `deadline` added with startup notifications
- Sub-collection category detection (Courses/* → category=course) deferred — needs parent_id in Mendeley folder response

**Next Steps:**
1. Step 12: `~/.docent/plugins/` external plugin discovery
2. Memory housekeeping: retire `decisions.md` entries for sync-promote (11.3) and sync-mendeley (11.4)
3. Real-data smoke test of `docent reading sync-from-mendeley` with reconfigured database_dir

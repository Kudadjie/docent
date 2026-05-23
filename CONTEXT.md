# CONTEXT - resume hint for next session

**Current Task:** Tagged v2.0.0 (MAJOR — research→studio rename, [paper]→[reading] config, QueueEntry schema). Blind-review fixes also shipped this session (cli_doctor split, _PRICING_NOTE crash, CI workflow).

**Key Decisions:**
- v2.0.0 not v1.2.0 — breaking changes policy required MAJOR bump (CLI command + config key renames from v1.1.1)
- memory/, CONTEXT.md, .mcp.json correctly excluded from main via .gitignore; resolved as deletions on merge
- cli_doctor.py created as pure side-effect-free module; cli.py imports from it (~260 lines removed)

**Next Steps:**
1. Schema-driven forms — backend exposes `input_schema` as JSON Schema; React generates forms dynamically (v2.1.0)
2. Decide Mendeley/Zotero coexistence policy before starting Zotero bridge (v2.1.0 gate)
3. Plugin developer docs — API is stable, no docs exist yet

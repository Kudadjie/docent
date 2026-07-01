# ADR-004: Queue schema v2 — reference-manager-neutral field names with automatic migration

**Status:** Active
**Date:** 2026-05-31
**Deciders:** John David K. T. Kudadjie

---

## Context

After Zotero support landed (ADR-002), the queue schema was still
"Mendeley-shaped": field `mendeley_id`, flag `not_in_mendeley`, action
`sync-from-mendeley`. External review flagged the naming as misleading now
that two reference managers are supported. But queue files on disk are user
state — a rename must not break existing installations.

## Decision

- **Schema migration v1→v2:** `mendeley_id` → `reference_id`,
  `not_in_mendeley` → `not_in_library`. `_QUEUE_SCHEMA_VERSION = 2` in
  `reading_store.py`; `_infer_schema_version()` does key-based detection
  (sees a `mendeley_id` key → v1) and `_migrate_v1_to_v2()` runs
  automatically inside `load_queue()`.
- **Back-compat aliases everywhere else:** `sync-from-library` added as the
  canonical action alias with `sync-from-mendeley` kept; renamed classes
  (`SyncFromLibraryInputs/Result`) keep the old names as type aliases so
  external importers (MCP clients, scripts) don't break.
- **Genuinely Mendeley-specific code keeps its name:** `mendeley_client.py`,
  `mendeley_cache.py`, and functions that operate on Mendeley API responses
  are not renamed — they *are* Mendeley-specific; renaming would add
  confusion, not clarity.

## Consequences

**Good:**
- The stored schema is manager-neutral; old queue files upgrade transparently
  on first load.
- Key-based version detection is cheap and conservative.

**Trade-offs:**
- Alias surface (`sync-from-mendeley`, old class names) must be carried until
  the next major version.

**Rejected alternatives:**
- **Hard rename without aliases:** breaks external importers and MCP callers.
- **Renaming the Mendeley transport modules too:** those are genuinely
  Mendeley-specific.

## Related

- `src/docent/bundled_plugins/reading/reading_store.py` — version detection + migration
- `tests/test_queue_migration.py` — v1 fixture gate (assert every new field)
- CLAUDE.md "Schema Safety" rules — the standing policy this migration follows

# ADR-002: Zotero support via pyzotero behind the existing ReferenceManagerBackend protocol

**Status:** Active
**Date:** 2026-05-30
**Deciders:** John David K. T. Kudadjie

---

## Context

The reading queue originally synced only from Mendeley, through the `mendeley-mcp`
subprocess (which owns the entire OAuth flow — Docent has zero Mendeley auth code).
Zotero support was initially gated behind a plan to replace the Mendeley MCP
subprocess with direct httpx calls. On inspection, that plan actually meant
reimplementing Mendeley OAuth (app registration, auth-code flow, token store) —
a large task with real onboarding burden — and it was not a prerequisite: a
backend-agnostic `ReferenceManagerBackend` protocol and sync engine already
existed; only the sync action hardcoded `MendeleyBackend`.

## Decision

- New `ZoteroBackend` implementing the existing protocol, built on **pyzotero**
  with a Zotero **Web API key** — no browser flow, no subprocess.
- `reading.reference_manager` config key (`"mendeley" | "zotero"`) selects the
  backend. One reference manager at a time, not both.
- Zotero items are mapped to the same canonical document/folder shape the
  Mendeley path produces, so the sync engine (`sync_engine.py`) and entry
  builder are untouched.
- The per-read metadata overlay is a no-op for Zotero — Zotero entries use
  their sync-time snapshot.

## Consequences

**Good:**
- Reused the abstraction that already existed; zero risk to the Mendeley path.
- API-key auth is far simpler to onboard than Mendeley's OAuth.
- The Web API + named-collection model mirrors the Mendeley collection model,
  so users switch managers without changing their workflow.

**Trade-offs:**
- Zotero item keys are stored in the generic external-ref field (renamed
  `reference_id` in schema v2 — see ADR-004).
- No live-metadata overlay for Zotero (deferred).

**Rejected alternatives:**
- **Own Mendeley OAuth (direct httpx):** big task, onboarding burden, not a
  prerequisite — the protocol abstracts over transport.
- **zotero-mcp subprocess:** another subprocess + OAuth; pyzotero is a stable
  direct-REST library.
- **Watching the local `zotero.sqlite`:** a different sync model that doesn't
  reuse the collection-based engine.

## Related

- `src/docent/bundled_plugins/reading/ref_manager.py` — the protocol
- `src/docent/bundled_plugins/reading/zotero_backend.py`, `zotero_client.py`
- `src/docent/bundled_plugins/reading/sync_engine.py` — backend-agnostic sync
- ADR-004 — queue schema v2 field renames

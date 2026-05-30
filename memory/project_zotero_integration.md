---
name: Zotero integration design
description: Design analysis and key decisions for adding Zotero as an alternative reference manager in the reading queue; v1.3+ work
type: project
---

Source: `txt/zotero-option.txt` + `txt/More Thoughts.txt`, 2026-05-11

## Key decision — CONFIRMED 2026-05-30
One reference manager at a time — user picks **Mendeley OR Zotero** via `sync_source` config toggle. No dual-ID merging. Both bridges maintained in parallel (coexist model). See `decisions.md` 2026-05-30 entry.

**Why:** Researchers are tribal; forced migration has real adoption cost. Toggle is clean, maintenance is bounded.

## Recommended approach

1. Define a `ReferenceManagerClient` protocol — `list_collections()`, `list_items(collection_id)`, plus field normalization to a canonical intermediate format
2. **Pre-requisite (#35a):** Replace `mendeley_client.py` MCP subprocess with direct `httpx` REST calls first — so the protocol is built on a clean foundation.
3. Create `zotero_client.py` using `pyzotero` — **decided over `zotero-mcp`** (2026-05-30): direct REST, no subprocess overhead, stable widely-used library, no OAuth browser dance per call.
3. Refactor Mendeley-specific functions into generic field-mapper pattern: `_build_entry_from_source(doc, field_mapper)`
4. Add `sync_source: Literal["mendeley", "zotero"]` to `ReadingSettings`
5. Reuse `MendeleyCache` — already parameterized via constructor callables; Zotero cache uses the same pattern

## What needs refactoring (Mendeley-specific today)
- `_build_entry_from_mendeley()` — field names like `doc.get("title")`, `doc.get("identifiers", {}).get("doi")`, author dicts with `first_name/last_name`
- `_extract_mendeley_id()` — Mendeley-specific ID fields
- `_normalize_mendeley_authors()` — Mendeley author format

Zotero field equivalents: `data.title`, `data.creators`, `data.date`, `data.DOI`, `data.itemType`.

## Bundled install
Zotero MCP (or pyzotero) should come bundled with docent — not a manual user install. Present limitations of both Mendeley and Zotero during onboarding so user can make an informed choice.

## How to apply
This is v1.3+ work. When starting, use `txt/zotero-option.txt` as the brief foundation. Resolve pyzotero vs zotero-mcp question first.

## SHIPPED 2026-05-30

Implemented as a `ReferenceManagerBackend` (the protocol + backend-agnostic `sync_from_mendeley_run` engine already existed — only the sync action hardcoded Mendeley). New files: `reading/zotero_client.py` (pyzotero wrappers: `make_zotero`, `list_collections`, `list_items` — `auth:`/`transport:` error prefixes matching Mendeley), `reading/zotero_backend.py` (`ZoteroBackend` maps Zotero → canonical folder/doc shape so `build_entry_from_mendeley` is untouched). Wiring: `ReadingQueue._select_backend(context)` picks by `reading.reference_manager`; reader overlay guarded to no-op for Zotero (snapshot-only). Config: `zotero_api_key`/`zotero_library_id`/`zotero_library_type` added to `ReadingSettings` + `_KNOWN_READING_KEYS`. `pyzotero>=1.5` core dep. `docent doctor` Zotero check (`_check_zotero`). **Verified against the LIVE Zotero API** (public group 4507109): API surface, return shapes (collection `data.parentCollection` False→None; item `data.creators` firstName/lastName, `date`→year regex, `DOI`, `itemType` book/bookSection map), and end-to-end ZoteroBackend→build_entry→QueueEntry. 20 backend tests + 4 doctor tests, Win+WSL.

**Field-name wart (acceptable):** Zotero item keys are stored in `QueueEntry.mendeley_id` (the generic "external ref id"). Renaming that field is a breaking schema migration — deferred. **Deferred:** reader overlay for Zotero (per-read fresh metadata), `config-show` doesn't surface zotero fields (doctor does), `docent setup` Zotero prompts. **Deviation from #36:** used the Zotero **Web API (pyzotero)**, not local `zotero.sqlite` file-watching — mirrors the Mendeley collection model and drops into the existing engine with zero changes.

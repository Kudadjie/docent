---
name: Zotero integration design
description: Design analysis and key decisions for adding Zotero as an alternative reference manager in the reading queue; v1.3+ work
type: project
---

Source: `txt/zotero-option.txt` + `txt/More Thoughts.txt`, 2026-05-11

## Key decision
One reference manager at a time — user picks **Mendeley OR Zotero** via `sync_source` config toggle. No dual-ID merging.

**Why:** Dual-source merge is complex and the user explicitly said "Not both."

## Recommended approach

1. Define a `ReferenceManagerClient` protocol — `list_collections()`, `list_items(collection_id)`, plus field normalization to a canonical intermediate format
2. Create `zotero_client.py` — likely using `pyzotero` (REST API, no subprocess needed). Alternatively, wire `zotero-mcp` (https://github.com/54yyyu/zotero-mcp) for consistency with the Mendeley MCP pattern. **Open question: MCP subprocess vs pyzotero library — resolve before touching queue code.**
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

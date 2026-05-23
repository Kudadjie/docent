# Reading Queue — UI Specification

**Tool:** `reading`  
**Version:** Docent v1.2.0  
**Last updated:** 2026-05-18  
**Audience:** Designer / frontend developer

---

## 1. Overview

The reading queue is a ranked, metadata-rich academic paper tracker that syncs with Mendeley. Papers enter via Mendeley (under a configured collection), are pulled into the local SQLite queue via `sync-from-mendeley`, then navigated and managed through 19 actions. The queue tracks reading order, status, deadlines, course categories, tags, and notes. All actions are available both via CLI (`docent reading <action>`) and MCP (`reading__<action>`).

---

## 2. Actions Table

| Action | Input fields | Output type | Notes |
|--------|-------------|-------------|-------|
| `add` | _(none)_ | `AddResult` | Guidance-only — explains the add-via-Mendeley workflow. Never mutates queue. |
| `next` | `category: str\|null` | `MutationResult` | Returns lowest-order queued entry, optionally filtered by category prefix. |
| `show` | `id: str` (req) | `MutationResult` | Full details for one entry. |
| `search` | `query: str` (req) | `SearchResult` | Case-insensitive substring across title, authors, notes, category, id, tags. |
| `stats` | _(none)_ | `StatsResult` | Queue counts by status and category. |
| `edit` | `id: str` (req), `status`, `order`, `type`, `category`, `deadline`, `notes`, `tags` (all optional) | `MutationResult` | Edits user-settable fields only. Mendeley-owned fields (title, authors, year, doi) are read-only. |
| `set-deadline` | `id: str` (req), `deadline: str` (req) | `MutationResult` | Set or clear deadline. Pass `""` to clear. |
| `done` | `id: str` (req) | `MutationResult` | Mark as done. Sets `finished` timestamp. Irreversible. |
| `start` | `id: str` (req) | `MutationResult` | Mark as reading. Sets `started` timestamp. Irreversible. |
| `remove` | `id: str` (req) | `MutationResult` | Remove from queue. Irreversible. |
| `move-up` | `id: str` (req) | `MutationResult` | Decrement position by 1. No-op at position 1. |
| `move-down` | `id: str` (req) | `MutationResult` | Increment position by 1. No-op at last position. |
| `move-to` | `id: str` (req), `position: int ≥ 1` (req) | `MutationResult` | Move to explicit position. Reorders contiguously. |
| `export` | `format: "json"\|"markdown"` (default `json`), `category: str\|null`, `status: str\|null` | `ExportResult` | Export full queue with fresh Mendeley metadata. |
| `sync-from-mendeley` | `dry_run: bool` (default `false`) | `SyncFromMendeleyResult` | Pull from Mendeley collection. Generator — yields progress. |
| `sync-status` | _(none)_ | `SyncStatusResult` | Show queue size vs PDF database stats. |
| `config-show` | _(none)_ | `ConfigShowResult` | Show reading settings. |
| `config-set` | `key: str` (req), `value: str` (req) | `ConfigSetResult` | Set `database_dir`, `queue_collection`, or `mendeley_mcp_command`. |
| `queue-clear` | `yes: bool` (default `false`) | `QueueClearResult` | Wipe all entries. Without `yes=true`, reports count and exits without mutating. |

---

## 3. Primary Flows

### Flow 1 — Add paper and sync
1. User adds a PDF to Mendeley under the `Docent-Queue` collection (or whichever `queue_collection` is configured)
2. User runs `sync-from-mendeley` (or calls `reading__sync_from_mendeley`)
3. Result shows: added count, unchanged count, removed count, failed count
4. Added entries appear in results with `id`, `title`

### Flow 2 — Navigate and work through queue
1. User calls `next` to get their top-priority item
2. User reads the paper
3. User calls `start --id <id>` to mark it as in-progress
4. User finishes reading, calls `done --id <id>`
5. Repeat

### Flow 3 — Search → update entry
1. User calls `search --query "storm surge"` — returns matching entries as a data table
2. User picks an entry id from results
3. User calls `show --id <id>` to see full details
4. User calls `edit --id <id> --notes "Key finding: ..."` or `set-deadline --id <id> --deadline 2026-06-01`

### Flow 4 — Reorder queue
1. User calls `search` or `stats` to identify entry id
2. User calls `move-to --id <id> --position 1` to bring to top
3. Or `move-up` / `move-down` for relative reordering

### Flow 5 — Config and export
1. User calls `config-show` to see current settings
2. User updates paths: `config-set --key database_dir --value ~/Documents/Papers`
3. User exports for a specific course: `export --format markdown --category CES701`

---

## 4. Result Shapes

### QueueEntry (embedded in MutationResult, SearchResult)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique slug, e.g. `"smith-2024-storm-surge"` |
| `title` | `str` | Paper title — Mendeley-owned, refreshed on sync |
| `authors` | `str` | Semicolon-separated authors — Mendeley-owned |
| `year` | `int\|null` | Publication year — Mendeley-owned |
| `doi` | `str\|null` | DOI — Mendeley-owned |
| `type` | `str` | `paper` \| `book` \| `book_chapter` — mapped from Mendeley document type |
| `added` | `str` | ISO date added to queue |
| `status` | `str` | `queued` \| `reading` \| `done` |
| `order` | `int` | 1-based reading position; `0` = unordered |
| `category` | `str\|null` | Mendeley sub-collection path, e.g. `"CES701"` or `"CES701/Topic"` |
| `deadline` | `str\|null` | ISO date deadline (YYYY-MM-DD) |
| `tags` | `list[str]` | User-defined tags |
| `notes` | `str` | User notes |
| `mendeley_id` | `str\|null` | Mendeley internal ID |
| `started` | `str\|null` | ISO timestamp when status → reading |
| `finished` | `str\|null` | ISO timestamp when status → done |

**Invariant:** Every entry requires at least one of `doi` or `mendeley_id`. Entries without either are rejected at creation.

### MutationResult
Used by: `next`, `show`, `edit`, `set-deadline`, `done`, `start`, `remove`, `move-up`, `move-down`, `move-to`

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | Whether the operation succeeded |
| `id` | `str` | Entry id acted on (empty string if failed) |
| `entry` | `QueueEntry\|null` | Full entry data after the mutation; `null` if failed |
| `queue_size` | `int` | Current total queue length after operation |
| `banner` | `BannerCounts` | Counts for UI badge indicators |
| `message` | `str` | Human-readable status or error |

**Shapes rendered:**
- On failure: `ErrorShape(reason=message)`
- On success: `MarkdownShape` with title, authors/year, order/status/category/deadline/doi/notes, then `MessageShape(info)` with the status message

### BannerCounts (embedded in MutationResult, AddResult, QueueClearResult)

| Field | Type | Description |
|-------|------|-------------|
| `queued` | `int` | Entries with status `queued` |
| `reading` | `int` | Entries with status `reading` |
| `overdue` | `int` | Entries past their deadline |
| `due_soon` | `int` | Entries due within 7 days |

### SearchResult

| Field | Type | Description |
|-------|------|-------------|
| `query` | `str` | The search string used |
| `matches` | `list[QueueEntry]` | Matching entries |
| `total` | `int` | Count of matches |
| `queue_size` | `int` | Total queue size |

**Shapes rendered:** `MessageShape` with match count, then `DataTableShape` with columns: `#` (order), Title, Authors, Year, Type, Category, Status.

### StatsResult

| Field | Type | Description |
|-------|------|-------------|
| `total` | `int` | Total entries in queue |
| `by_status` | `dict[str, int]` | Counts per status value |
| `by_category` | `dict[str, int]` | Counts per category (None → `"(none)"`) |
| `banner` | `BannerCounts` | Badge counts |

**Shapes rendered:** `MetricShape(Total)`, `DataTableShape(Status/Count)`, `DataTableShape(Category/Count)`.

### SyncFromMendeleyResult

| Field | Type | Description |
|-------|------|-------------|
| `queue_collection` | `str` | Collection name synced from |
| `folder_id` | `str\|null` | Mendeley folder ID (`null` if collection not found) |
| `added` | `list[dict]` | `{id, mendeley_id, title}` for each added entry |
| `unchanged` | `list[str]` | Entry ids that were already up to date |
| `removed` | `list[str]` | Entry ids removed from queue (no longer in collection) |
| `failed` | `list[dict]` | `{mendeley_id, error}` for entries that failed to sync |
| `dry_run_added` | `list[dict]` | Preview of what would be added (dry-run only) |
| `dry_run_removed` | `list[str]` | Preview of what would be removed (dry-run only) |
| `summary` | `str` | One-line summary |
| `message` | `str` | Early-exit reason (collection missing, MCP error, etc.) |

**Shapes rendered:** If `message` is non-empty (early exit), shows `MessageShape(warning)`. Otherwise: collection name metric, added/unchanged/removed/failed metrics, optional data tables for added and failed entries (capped at 10 rows each).

### ExportResult

| Field | Type | Description |
|-------|------|-------------|
| `format` | `str` | `json` or `markdown` |
| `count` | `int` | Number of exported entries |
| `content` | `str` | Full exported content |

### SyncStatusResult

| Field | Type | Description |
|-------|------|-------------|
| `database_dir` | `str\|null` | Configured PDF database path |
| `queue_size` | `int` | Current queue length |
| `database_pdfs` | `list[str]` | PDF filenames found in database |
| `summary` | `str` | One-line summary |
| `message` | `str` | Warning if database not configured |

### ConfigShowResult

| Field | Type | Description |
|-------|------|-------------|
| `config_path` | `str` | Absolute path to `config.toml` |
| `database_dir` | `str\|null` | PDF database directory |
| `queue_collection` | `str` | Mendeley collection name |
| `mendeley_mcp_command` | `list[str]\|null` | Mendeley MCP launch command |

### ConfigSetResult / AddResult / QueueClearResult

Standard result shapes — `ok: bool`, `message: str`, plus relevant counts/banner.

---

## 5. Edge Cases & Error States

### Entry not found
- All id-based actions: `MutationResult(ok=False, id="", entry=null, message="No entry with id '…'")`

### `add` — guidance only
- `add` never creates an entry — it returns markdown instructions explaining how to add via Mendeley and then run `sync-from-mendeley`. The result `added=false`.

### `queue-clear` without confirmation
- Without `yes=true`: returns `QueueClearResult(cleared=false, removed_count=0, message="Queue has N entries. Pass --yes to clear.")` — no mutation.
- With `yes=true`: wipes all entries, returns count.

### `sync-from-mendeley` — collection not found
- Returns early with `message="Collection '{name}' not found in Mendeley. Check queue_collection config."` and `folder_id=null`. No mutations.

### `sync-from-mendeley` — Mendeley MCP unavailable
- Returns early with `message` containing the MCP connection error. No mutations.

### `set-deadline` — clearing
- Pass `deadline=""` to clear an existing deadline. Clearing a deadline that wasn't set is a no-op (success).

### `export` — empty result
- Returns `ExportResult(count=0, content="[]" or "")` — not an error.

### `edit` — Mendeley-owned fields
- `title`, `authors`, `year`, `doi` are NOT editable via `edit`. The action silently ignores any attempt. These refresh on `sync-from-mendeley`. Only `status`, `order`, `type`, `category`, `deadline`, `notes`, `tags` are user-settable.

### `move-up` at position 1 / `move-down` at last position
- No-op: returns the entry unchanged with `message="Already at top"` or `"Already at bottom"`.

### `move-to` — contiguity
- Moving entry to position N shifts other entries to maintain a contiguous 1-based sequence. The queue never has gaps in order numbers.

---

## 6. Design Invariants

- **Order is 1-based and contiguous.** Positions are integers starting at 1. `move-up`, `move-down`, `move-to` all maintain contiguity — the implementation re-numbers adjacent entries. The UI must not display order values as gaps.
- **Mendeley owns title / authors / year / doi.** These four fields are populated from Mendeley on sync and cannot be edited via `edit`. The UI should render them read-only and note they refresh on sync.
- **`done`, `start`, `remove` are irreversible.** `started` and `finished` timestamps are set once and never overwritten. There is no undo. The UI should present these as destructive actions.
- **`queue-clear` requires `yes=true`.** Without it, the action is a no-op that reports the entry count. The UI must show a confirmation gate.
- **`add` is guidance-only.** Papers enter via Mendeley → `sync-from-mendeley`. The `add` action only returns an explanation. The UI should not present `add` as a way to create entries directly.
- **`sync-from-mendeley` is a generator.** It yields progress events before returning the final result. The UI should stream these as live log lines.
- **`next` filters by category prefix.** Passing `category="CES701"` matches entries with category `"CES701"` or `"CES701/Topic"` or any deeper path starting with that prefix.
- **BannerCounts drive sidebar badges.** Every mutation returns `banner` counts so the UI can update badges (queued count, reading count, overdue, due-soon) without a separate `stats` call.
- **API key masking.** Config values that look like API keys are masked. The UI should not display raw API key values.

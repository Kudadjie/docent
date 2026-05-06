# Reading Tool — Action Spec

This document is aimed at frontend developers, MCP adapter authors, and anyone
building on top of the `reading` tool. It covers the data model, every action's
contract (inputs → outputs → error paths), the Mendeley sync algorithm, and the
persistence layout.

---

## Data model

### `QueueEntry`

The canonical record for a single reading-queue item.

| Field | Type | Default | Notes |
|---|---|---|---|
| `id` | `str` | required | Slug derived from author+year+keyword on sync, e.g. `smith-2024-coastal-surge`. Unique within the queue. |
| `title` | `str` | `""` | Mendeley-owned snapshot. Overlaid with live data on `next`/`show`/`search`/`export`. |
| `authors` | `str` | `""` | Mendeley-owned snapshot. Same overlay behaviour. |
| `year` | `int \| null` | `null` | Publication year. |
| `doi` | `str \| null` | `null` | DOI string (no resolver prefix). |
| `type` | `str` | `"paper"` | `paper` / `book` / `book_chapter`. Mapped from Mendeley document type on sync; user-overridable via `edit`. |
| `added` | `str` | required | ISO date (`YYYY-MM-DD`) when the entry was added to the local queue. |
| `status` | `str` | `"queued"` | `queued` / `reading` / `done` / `removed`. |
| `order` | `int` | `0` | 1-based reading priority. `0` = unordered (sorts last). |
| `category` | `str \| null` | `null` | Mendeley sub-collection path relative to the root collection, e.g. `"CES701"` or `"CES701/Storm Surge"`. `null` = in the root collection. |
| `deadline` | `str \| null` | `null` | ISO date (`YYYY-MM-DD`). Triggers startup warnings when ≤ 3 days away or past. |
| `tags` | `list[str]` | `[]` | User-defined tags. |
| `notes` | `str` | `""` | Free-text notes. |
| `mendeley_id` | `str \| null` | `null` | Mendeley document or catalog id. |
| `started` | `str \| null` | `null` | ISO timestamp stamped when status transitions to `reading`. Never overwritten. |
| `finished` | `str \| null` | `null` | ISO timestamp stamped when status transitions to `done`. Never overwritten. |

**Invariant:** at least one of `doi` or `mendeley_id` must be non-null.
Entries that violate this fail Pydantic validation and are rejected.

### `BannerCounts`

Summary counts written to `state.json` on every queue save.

| Field | Type |
|---|---|
| `queued` | `int` |
| `reading` | `int` |
| `done` | `int` |

---

## Persistence layout

All files live under `~/.docent/data/reading/`.

| File | Format | Description |
|---|---|---|
| `queue.json` | `list[QueueEntry dict]` | Source of truth. Loaded on every read action, written on every mutation. |
| `queue-index.json` | `{id: {title, status, order}}` | Fast lookup index. Recomputed atomically on every `save_queue`. |
| `state.json` | `{queued, reading, done, last_updated}` | Banner counts + timestamp. Recomputed on every `save_queue`. |
| `deadline-seen.json` | `{entry_id: "YYYY-MM-DD"}` | Tracks which deadline alerts have fired today. Updated atomically. |
| `run-log.jsonl` | one JSON record per line | Append-only event log for all mutations (add, remove, edit, etc.). |

All writes use atomic `rename` (write to `.tmp`, then `os.replace`) so a crash
mid-write cannot leave a partial file.

Mendeley cache lives separately at `~/.docent/cache/paper/mendeley_collection.json`:

```json
{
  "__folders__": {"ttl": 1234567890, "map": {"FolderName": "folder-id"}},
  "folder-id": {"ttl": 1234567890, "items": [ ... ]}
}
```

- Document TTL: 300 seconds (5 minutes).
- Folder-ID TTL: 86400 seconds (24 hours).
- `sync-from-mendeley` invalidates the document entry for the affected folder after a
  successful (non-dry) write so the next reader call fetches fresh data.

---

## Actions

### `add`

**Purpose:** Display ingestion instructions. No queue mutation.

**Input schema:** *(no fields)*

**Returns:** `AddResult`

| Field | Type | Notes |
|---|---|---|
| `added` | `bool` | Always `false`. |
| `queue_size` | `int` | Current queue length. |
| `banner` | `BannerCounts` | Current status counts. |
| `message` | `str` | Human-readable instructions. |

**Error paths:** None.

---

### `next`

**Purpose:** Find the highest-priority unread entry.

**Input schema:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `category` | `str \| null` | `null` | If set, restricts to entries whose `category` equals this value or starts with `"<value>/"`. |

**Returns:** `MutationResult`

| Field | Type | Notes |
|---|---|---|
| `ok` | `bool` | `false` when no matching queued entries exist. |
| `id` | `str` | Entry id, or `""` when `ok=false`. |
| `entry` | `QueueEntry \| null` | Full entry (with Mendeley overlay), or `null` when not found. |
| `queue_size` | `int` | Total entries in queue. |
| `banner` | `BannerCounts` | Current status counts. |
| `message` | `str` | Human-readable summary. |

**Sort key:** `(order or 999999, added)` ascending — lowest order + earliest added wins.

**Mendeley overlay:** applied before sorting (live title/authors/year/doi shown).

---

### `show`

**Purpose:** Retrieve full details for one entry by ID.

**Input schema:**

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Entry id. |

**Returns:** `MutationResult` (same shape as `next`).

**Error paths:**
- `ok=false`, `entry=null`, `message="Entry '<id>' not found."` when id does not exist.

**Mendeley overlay:** applied.

---

### `search`

**Purpose:** Full-text substring search across the queue.

**Input schema:**

| Field | Type | Notes |
|---|---|---|
| `query` | `str` | Case-insensitive substring. |

**Haystack per entry:** concatenation of `title + authors + notes + category + id + tags`.

**Returns:** `SearchResult`

| Field | Type | Notes |
|---|---|---|
| `query` | `str` | Echo of the input query. |
| `matches` | `list[QueueEntry]` | Matching entries, sorted by `(order or 999999, added)`. |
| `total` | `int` | `len(matches)`. |
| `queue_size` | `int` | Total entries in queue. |

**Mendeley overlay:** applied before matching.

---

### `stats`

**Purpose:** Counts by status and category.

**Input schema:** *(no fields)*

**Returns:** `StatsResult`

| Field | Type | Notes |
|---|---|---|
| `total` | `int` | Total queue size. |
| `by_status` | `{str: int}` | `{status_value: count}`. |
| `by_category` | `{str: int}` | Category path → count; entries with no category use key `"(root)"`. |
| `banner` | `BannerCounts` | Current status counts. |

**Note:** `stats` does NOT apply the Mendeley overlay (its outputs are all
workflow-owned fields; a live Mendeley round-trip would be wasted traffic).

---

### `remove`

**Purpose:** Permanently delete an entry from the queue.

**Input schema:**

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Entry id. |

**Returns:** `MutationResult` — `entry` is the deleted entry (pre-deletion snapshot).

**Error paths:** `ok=false` when id not found.

**Side effects:** logs `{action: "remove", id, title}` to `run-log.jsonl`.

---

### `edit`

**Purpose:** Update one or more user-settable fields on an existing entry.

**Input schema:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `id` | `str` | required | |
| `status` | `str \| null` | `null` | `queued` / `reading` / `done` |
| `order` | `int \| null` | `null` | |
| `type` | `str \| null` | `null` | `paper` / `book` / `book_chapter` |
| `category` | `str \| null` | `null` | Empty string clears to `null`. |
| `deadline` | `str \| null` | `null` | `YYYY-MM-DD` or `""` to clear. |
| `notes` | `str \| null` | `null` | |
| `tags` | `list[str] \| null` | `null` | Replaces the full tag list. |

Only supplied fields are updated. If no fields are supplied, returns `ok=false`
with message `"No fields supplied; nothing to edit."`.

**Off-limits fields** (Mendeley-owned, silently ignored): `title`, `authors`,
`year`, `doi`, `mendeley_id`, `started`, `finished`, `added`.

**Returns:** `MutationResult` — `entry` is the post-update snapshot.

**Side effects:** logs `{action: "edit", id, fields: [sorted updated field names]}` to
`run-log.jsonl`.

---

### `set-deadline`

**Purpose:** Dedicated shortcut for setting or clearing a deadline.

**Input schema:**

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Entry id. |
| `deadline` | `str` | `YYYY-MM-DD` to set; `""` (empty string) to clear. Whitespace stripped. |

**Returns:** `MutationResult`.

**Error paths:** `ok=false` when id not found.

**Side effects:** logs `{action: "set_deadline", id, deadline}` to `run-log.jsonl`.

---

### `start`

**Purpose:** Transition an entry to `reading` status.

**Input schema:**

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Entry id. |

**Returns:** `MutationResult`.

**Invariant:** `started` is only stamped the first time (never overwritten if already set).

---

### `done`

**Purpose:** Transition an entry to `done` status.

**Input schema:**

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Entry id. |

**Returns:** `MutationResult`.

**Invariant:** `finished` is only stamped the first time (never overwritten if already set).

---

### `move-up`

**Purpose:** Move one position earlier in the reading order.

**Input schema:**

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Entry id. |

**Returns:** `MutationResult`.

**Error paths:**
- `ok=false` if entry already at position 1 (`"already at position 1; can't move up"`).
- `ok=false` if id not found.

**Reorder algorithm:** see `move-to` below.

---

### `move-down`

**Purpose:** Move one position later in the reading order.

**Input schema:**

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Entry id. |

**Returns:** `MutationResult`.

**Error paths:**
- `ok=false` if entry already at the last position.
- `ok=false` if id not found.

---

### `move-to`

**Purpose:** Move to an exact position (1-based).

**Input schema:**

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | `str` | | Entry id. |
| `position` | `int` | `≥ 1` | Target position. |

**Returns:** `MutationResult`.

**Reorder algorithm:** entries with `order > 0` are sorted by their current order.
The target entry is removed from the sequence, then reinserted at the target
position. The sequence is then re-numbered from 1 with no gaps. Unordered
entries (`order = 0`) are not affected.

---

### `export`

**Purpose:** Serialise the queue (or a filtered subset) as JSON or Markdown.

**Input schema:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `format` | `str` | `"json"` | `json` or `markdown`. Raises `ValueError` for unknown values. |
| `category` | `str \| null` | `null` | Exact category path match (not prefix). |
| `status` | `str \| null` | `null` | Exact status match. |

**Sort:** `(order or 999999, added)` ascending.

**Returns:** `ExportResult`

| Field | Type | Notes |
|---|---|---|
| `format` | `str` | Echo of input format. |
| `count` | `int` | Number of entries exported. |
| `content` | `str` | Full serialised content (JSON string or Markdown table string). |

**Mendeley overlay:** applied before filtering and serialisation.

**Markdown columns:** `# | title | authors | year | type | category | status | deadline`

---

### `queue-clear`

**Purpose:** Wipe the entire queue.

**Input schema:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `yes` | `bool` | `false` | Safety guard: must be `true` to actually clear. Without it, action reports queue size and exits. |

**Returns:** `QueueClearResult`

| Field | Type | Notes |
|---|---|---|
| `cleared` | `bool` | `true` only when `yes=true` and the queue was wiped. |
| `removed_count` | `int` | Number of entries removed (0 when dry-run). |
| `queue_size` | `int` | Post-clear queue size (0 after clear, unchanged otherwise). |
| `banner` | `BannerCounts` | Post-clear counts. |
| `message` | `str` | Human-readable summary. |

**Side effects:** logs `{action: "queue_clear", removed: N}` when cleared.

---

### `sync-from-mendeley`

**Type:** generator action (yields `ProgressEvent` records during work).

**Purpose:** Reconcile the local queue with the configured Mendeley collection.

**Input schema:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `dry_run` | `bool` | `false` | Resolve collection and compute diff without writing the queue. |

**Progress phases:**
1. `discover` — listing Mendeley folders to resolve the collection name.
2. `discover` — reading the root collection's documents.
3. `reconcile` — (if sub-folders exist) reading each sub-folder.

**Returns:** `SyncFromMendeleyResult`

| Field | Type | Notes |
|---|---|---|
| `queue_collection` | `str` | Name of the configured Mendeley collection. |
| `folder_id` | `str \| null` | Resolved Mendeley folder id, or `null` on early exit. |
| `added` | `list[{id, mendeley_id, title}]` | Entries added (non-dry). |
| `unchanged` | `list[str]` | Entry ids that already existed and were not modified. |
| `removed` | `list[str]` | Entry ids whose Mendeley doc was no longer in the collection; status set to `"removed"`. |
| `failed` | `list[{mendeley_id, error}]` | Per-document errors (missing id, build failure). |
| `dry_run_added` | `list[{id, mendeley_id, title}]` | Would-be additions (dry-run only). |
| `dry_run_removed` | `list[str]` | Would-be removals (dry-run only). |
| `summary` | `str` | Human-readable summary line. |
| `message` | `str` | Non-empty only on early-exit errors (auth failure, collection not found, etc.). |

**Early-exit paths (message set, all bucket lists empty):**
- Mendeley `list_folders` transport/auth error.
- Collection name not found in Mendeley.
- Duplicate collection names in Mendeley.
- Root collection has no usable id.
- `list_documents` transport error for the root folder.

**Category mapping algorithm:**

For a document in sub-folder `F`:
1. Walk `F → parent → parent → …` until the root collection id is reached.
2. Collect folder names along the walk (excluding the root collection name itself).
3. Join with `/` → `"ParentName/ChildName"`.
4. Documents directly in the root collection get `category = null`.

**New entry construction** (`_build_entry_from_mendeley`):
- `id` = `"{first-author-slug}-{year}-{title-slug}"` (first 3 words of title).
- `title`, `authors`, `year`, `doi` from the Mendeley document payload (no extra round-trip).
- `type` mapped from Mendeley `type` field:
  - `journal_article` → `paper`
  - `book` → `book`
  - `book_section` → `book_chapter`
  - anything else → `paper`
- `status = "queued"`, `order` assigned sequentially after existing max.

**Cache invalidation:** after a successful non-dry sync, the document cache entry
for the affected folder id is deleted so the next reader action fetches fresh data.

---

### `sync-status`

**Purpose:** Report queue size and PDFs sitting in `database_dir`.

**Input schema:** *(no fields)*

**Returns:** `SyncStatusResult`

| Field | Type | Notes |
|---|---|---|
| `database_dir` | `str \| null` | Resolved path, or `null` if not configured. |
| `queue_size` | `int` | Current queue length. |
| `database_pdfs` | `list[str]` | Filenames of all `.pdf` files found recursively in `database_dir`. |
| `summary` | `str` | Human-readable summary. |
| `message` | `str` | Non-empty on error (not configured, dir does not exist). |

---

### `config-show`

**Input schema:** *(no fields)*

**Returns:** `ConfigShowResult`

| Field | Type | Notes |
|---|---|---|
| `config_path` | `str` | Absolute path to `~/.docent/config.toml`. |
| `database_dir` | `str \| null` | Configured path, or `null` if unset. |
| `queue_collection` | `str` | Defaults to `"Docent-Queue"`. |

---

### `config-set`

**Input schema:**

| Field | Type | Notes |
|---|---|---|
| `key` | `str` | Must be one of: `database_dir`, `queue_collection`. |
| `value` | `str` | New value. `""` clears the setting. Paths may use `~`. |

**Returns:** `ConfigSetResult`

| Field | Type | Notes |
|---|---|---|
| `ok` | `bool` | `false` when `key` is not in the known-keys list. |
| `key` | `str` | Echo of input key. |
| `value` | `str` | Echo of input value. |
| `config_path` | `str` | Path to the config file that was written. |
| `message` | `str` | Human-readable summary or error. |

**Note:** `mendeley_mcp_command` is a list-typed setting and cannot be set via
`config-set`. Edit `~/.docent/config.toml` directly.

---

## Startup hook — deadline notifications

`reading_notify.check_deadlines(store_root)` is called once per `docent` invocation
(wired into `cli.py`'s main callback via the plugin `on_startup` hook).

**Logic:**
1. Load `queue.json`. If missing, return empty.
2. Load `deadline-seen.json` (empty dict if missing).
3. For each entry with a non-null `deadline` and `status` not in `{done, removed}`:
   - Skip if `seen[entry_id] == today`.
   - Parse deadline. If `deadline ≤ today + 3 days`:
     - Compute days_left. Build alert line:
       - `days_left < 0` → `[OVERDUE Nd] 'title' — deadline YYYY-MM-DD`
       - `days_left == 0` → `[DUE TODAY] 'title' — deadline YYYY-MM-DD`
       - else → `[DUE IN Nd] 'title' — deadline YYYY-MM-DD`
     - Mark `seen[entry_id] = today`.
4. If `seen` changed, atomically rewrite `deadline-seen.json`.
5. Return alert lines. `cli.py` prints them to the console before running the command.

**Deduplication:** each entry fires at most once per calendar day.

---

## Settings reference (`[reading]` section in `~/.docent/config.toml`)

| Key | Type | Default | Notes |
|---|---|---|---|
| `database_dir` | `Path \| null` | `null` | PDF folder Mendeley watches. First-run prompt if unset and TTY is available. |
| `queue_collection` | `str` | `"Docent-Queue"` | Name of the top-level Mendeley collection to sync. |
| `mendeley_mcp_command` | `list[str]` | `["uvx", "mendeley-mcp"]` | Command used to launch the Mendeley MCP server. Not exposed via `config-set`. |

Environment override pattern: `DOCENT_READING__<KEY_UPPERCASE>` (Pydantic Settings
double-underscore nesting).

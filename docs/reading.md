# Docent Reading Queue — User Guide

The `reading` tool is a personal reading queue that syncs with Mendeley Desktop.
It tracks what you plan to read, what you're currently reading, and what you've
finished — with deadline warnings, priority ordering, and category organisation by
course or project.

---

## Prerequisites

1. **Docent installed.** `docent --version` should print a version number.
2. **Mendeley Desktop** (or Mendeley Reference Manager) installed and logged in.
3. **Mendeley MCP server** available. The tool calls Mendeley via
   `uvx mendeley-mcp` by default; if you use a different command, set
   `reading.mendeley_mcp_command` manually in `~/.docent/config.toml`.

---

## First-time setup

### 1. Point Docent at your PDF folder

This is the folder where Mendeley auto-imports PDFs (usually the same folder
you've already pointed Mendeley's file-organiser at).

```bash
docent reading config-set database_dir ~/Documents/Papers
```

### 2. Create a Mendeley collection named `Docent-Queue`

In Mendeley Desktop, create a top-level collection called `Docent-Queue`. This is
the collection Docent watches. You can change the name if you prefer — just update
the setting to match:

```bash
docent reading config-set queue_collection "My Reading List"
```

### 3. Verify

```bash
docent reading config-show
docent reading sync-status
```

`config-show` prints the current settings. `sync-status` reports how many PDFs
are in your database folder and how many entries are in the local queue.

---

## The workflow

Mendeley is the source of truth for bibliographic metadata (title, authors, year,
DOI). Docent adds workflow metadata on top: reading order, status, deadlines, notes.

```
PDF file                Mendeley Desktop             Docent
---------               ----------------             ------
Drop into               Auto-imports PDF          
database_dir    ──▶     with metadata         
                        
                        Drag into               
                        Docent-Queue       ──▶   sync-from-mendeley
                        collection                adds entry to local queue
                        
                                                  next / start / done
                                                  manage reading progress
```

You never add papers directly through Docent — ingestion always goes through
Mendeley so metadata stays authoritative.

---

## Day-to-day usage

### What to read next

```bash
docent reading next
```

Shows the queued entry with the lowest order number. If all entries are tied (or
unordered), falls back to the earliest `added` date.

Filter to a specific course:

```bash
docent reading next --category CES701
```

### Mark as started / done

```bash
docent reading start smith-2024-coastal-surge
docent reading done  smith-2024-coastal-surge
```

`start` stamps a `started` timestamp and sets status to `reading`.
`done` stamps a `finished` timestamp and sets status to `done`.

### Look up a specific entry

```bash
docent reading show smith-2024-coastal-surge
```

### Search

```bash
docent reading search "storm surge"
```

Case-insensitive substring search across title, authors, notes, category, ID, and
tags. Results are sorted by reading order.

### Queue statistics

```bash
docent reading stats
```

Counts by status (queued / reading / done) and by category.

---

## Priority and ordering

Every entry has an `order` field (integer, 1 = read first). When you
`sync-from-mendeley`, new entries are assigned the next available order number.
Entries with `order=0` sort to the bottom.

### Adjust order

```bash
docent reading move-up   smith-2024-coastal-surge    # one position earlier
docent reading move-down smith-2024-coastal-surge    # one position later
docent reading move-to   smith-2024-coastal-surge --position 1   # read first
docent reading edit      smith-2024-coastal-surge --order 5      # exact position
```

`move-up` / `move-down` / `move-to` shift other entries to make room — they
don't leave gaps in the order sequence.

---

## Deadlines

```bash
docent reading set-deadline smith-2024-coastal-surge --deadline 2026-06-15
docent reading set-deadline smith-2024-coastal-surge --deadline ""   # clear
```

Each time you run any `docent` command, Docent checks for entries due within
3 days or already overdue. A warning is printed once per calendar day per entry:

```
[DUE IN 2d] 'Smith et al. 2024' — deadline 2026-05-08
[OVERDUE 1d] 'Jones 2023' — deadline 2026-05-05
```

---

## Categories (courses / projects)

Categories are automatically detected from your Mendeley sub-collection structure.
If you drag a paper into `Docent-Queue/CES701/LitReview`, the entry gets
`category = "CES701/LitReview"`.

| Mendeley path                        | category value        |
|--------------------------------------|-----------------------|
| `Docent-Queue`                       | *(none)*              |
| `Docent-Queue/CES701`                | `CES701`              |
| `Docent-Queue/CES701/Storm Surge`    | `CES701/Storm Surge`  |

`next` and `search` accept a `--category` prefix:

```bash
docent reading next --category CES701          # matches CES701 and CES701/*
docent reading search "wave" --category CES701 # not yet in CLI, use search + filter
```

Override manually if needed:

```bash
docent reading edit smith-2024 --category "Thesis/Chapter2"
```

---

## Entry types

Papers are automatically typed from their Mendeley document type on sync:

| Mendeley type     | Docent type      |
|-------------------|------------------|
| `journal_article` | `paper`          |
| `book`            | `book`           |
| `book_section`    | `book_chapter`   |
| anything else     | `paper`          |

Override with:

```bash
docent reading edit smith-2024 --type book_chapter
```

---

## Syncing with Mendeley

### Pull from Mendeley

```bash
docent reading sync-from-mendeley
```

Reconciles the configured Mendeley collection with the local queue:

- **Added** — new Mendeley entries appear in the queue.
- **Unchanged** — already in queue, no action.
- **Removed** — entries removed from the Mendeley collection are marked `removed` in the queue.

Preview without writing:

```bash
docent reading sync-from-mendeley --dry-run
```

### Metadata freshness

`next`, `show`, `search`, and `export` all overlay live Mendeley metadata
(title / authors / year / DOI) on top of the local queue snapshot before
displaying. A read-through cache (5-minute TTL) keeps this fast. If Mendeley is
unreachable, the cached snapshot is used transparently.

---

## Editing entries

Only workflow fields are editable through Docent. Bibliographic fields
(title / authors / year / DOI) are Mendeley-owned and refreshed automatically.

```bash
docent reading edit <id> --notes "Key paper for lit review"
docent reading edit <id> --tags coastal flooding inundation
docent reading edit <id> --order 3
docent reading edit <id> --status queued          # manually reset status
docent reading edit <id> --type book_chapter
docent reading edit <id> --category "CES701"
```

Multiple fields can be set in one command:

```bash
docent reading edit smith-2024 --notes "check the appendix" --tags wave setup
```

---

## Exporting

```bash
docent reading export                              # JSON, all entries
docent reading export --format markdown            # Markdown table
docent reading export --format markdown --status queued --category CES701
```

Exported entries are sorted by reading order. Freshly overlaid Mendeley metadata
is used so the export reflects the current bibliographic record.

---

## Full command reference

### Viewing

| Command | Description |
|---|---|
| `docent reading next` | Lowest-order queued entry |
| `docent reading next --category <prefix>` | Next in a category |
| `docent reading show <id>` | Full details for one entry |
| `docent reading search <query>` | Substring search across all text fields |
| `docent reading stats` | Counts by status and category |

### Status transitions

| Command | Description |
|---|---|
| `docent reading start <id>` | Status → reading; stamps `started` |
| `docent reading done <id>` | Status → done; stamps `finished` |
| `docent reading remove <id>` | Delete entry from queue entirely |

### Editing

| Command | Description |
|---|---|
| `docent reading edit <id> [flags]` | Edit one or more user-settable fields |
| `docent reading set-deadline <id> --deadline YYYY-MM-DD` | Set deadline |
| `docent reading set-deadline <id> --deadline ""` | Clear deadline |
| `docent reading move-up <id>` | One position earlier |
| `docent reading move-down <id>` | One position later |
| `docent reading move-to <id> --position N` | Exact position (1 = first) |

### Syncing

| Command | Description |
|---|---|
| `docent reading sync-from-mendeley` | Reconcile local queue with Mendeley collection |
| `docent reading sync-from-mendeley --dry-run` | Preview without writing |
| `docent reading sync-status` | Queue size + PDF count in database_dir |

### Export / config / maintenance

| Command | Description |
|---|---|
| `docent reading export [--format json\|markdown] [--status S] [--category C]` | Export queue |
| `docent reading add` | Print ingestion instructions (no-op — use Mendeley) |
| `docent reading config-show` | Print current reading settings |
| `docent reading config-set <key> <value>` | Update a setting |
| `docent reading queue-clear --yes` | Wipe the entire queue (irreversible) |

### `edit` flags

| Flag | Type | Description |
|---|---|---|
| `--order N` | int | Reading priority (1 = first) |
| `--status S` | str | `queued` / `reading` / `done` |
| `--type T` | str | `paper` / `book` / `book_chapter` |
| `--category C` | str | Override category path |
| `--deadline D` | str | `YYYY-MM-DD` or `""` to clear |
| `--notes TEXT` | str | Free-text notes |
| `--tags T1 T2` | str list | Replace tag list |

---

## Data files

All reading-tool data lives in `~/.docent/data/reading/`:

| File | Contents |
|---|---|
| `queue.json` | Source-of-truth list of all entries |
| `queue-index.json` | Fast lookup index (id → title/status/order) |
| `state.json` | Banner counts (queued/reading/done) |
| `deadline-seen.json` | Tracks which deadline alerts fired today |
| `run-log.jsonl` | Structured event log of all mutations |

Mendeley cache lives at `~/.docent/cache/paper/mendeley_collection.json` (5-min
TTL for documents, 24-hour TTL for folder IDs).

Config lives at `~/.docent/config.toml` under the `[reading]` section.

---

## Troubleshooting

**`sync-from-mendeley` says the collection was not found**

Create a collection in Mendeley Desktop with exactly the name shown in
`docent reading config-show` (default: `Docent-Queue`). Collection names are
case-sensitive.

**Metadata looks stale after editing in Mendeley**

The cache TTL is 5 minutes. Run `sync-from-mendeley` (which invalidates the
cache) or wait for the TTL to expire.

**`database_dir not configured`**

Run `docent reading config-set database_dir <path>` with the absolute path to
your PDF folder.

**Mendeley MCP auth fails**

Run `uvx mendeley-mcp` manually in a terminal to complete the OAuth flow, then
retry.

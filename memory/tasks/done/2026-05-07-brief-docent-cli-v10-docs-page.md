# Brief: Docent CLI v1.0 Docs Page

## Goal

Create `docs/cli.md` — the primary documentation page for Docent CLI v1.0. This will be published as a GitHub Pages site or linked directly from the README.

Do NOT edit `README.md`. Create only `docs/cli.md` (creating the `docs/` folder if it does not exist).

---

## What Docent is

Docent is a personal CLI "control center" for grad-school workflows. Currently ships one tool — the **Reading Queue** (`docent reading …`) — which manages an academic reading list and syncs with a Mendeley library. It also exposes all tools as MCP (Model Context Protocol) tools so Claude Code can call them directly via `docent serve`.

---

## Sections to write

### 1. Installation

```bash
# Requires Python 3.11+. Install with uv (recommended):
pip install uv        # once
uv tool install --editable .    # from the repo root

# Verify:
docent --version
```

Note: after any `pyproject.toml` change, reinstall with `uv tool install --reinstall --editable .`

### 2. Quick start

Show `docent list` output. Then `docent reading --help`.

### 3. The Reading Queue

Explain the workflow:
1. Papers live in Mendeley under a collection called `Docent-Queue`
2. `docent reading sync-from-mendeley` pulls them into the local queue
3. Use `next`, `search`, `stats` to navigate
4. Use `done`, `start`, `edit` to update status
5. Use `set-deadline` to set reading deadlines

#### Reference table of all reading actions

| Command | What it does |
|---------|-------------|

Populate from this list (all `docent reading <action>`):

- `add` — guidance-only; explains the add-via-Mendeley workflow
- `next [--course-name <name>]` — show the next entry to read (lowest order, optionally filtered by course)
- `show --id <id>` — show one entry's full details
- `search --query <q>` — search title/authors/notes/tags
- `stats [--course-name <name>]` — queue statistics by category and status
- `edit --id <id> [--order N] [--status <s>] [--category <c>] [--course-name <n>] [--notes <text>] [--tags <t>] [--type <t>]` — edit user-settable fields (Mendeley-owned fields like title/authors are read-only here)
- `set-deadline --id <id> [--date YYYY-MM-DD]` — set or clear a deadline (omit --date to clear)
- `done --id <id>` — mark as done
- `start --id <id>` — mark as currently reading
- `remove --id <id>` — remove from queue
- `move-up --id <id>` — move one position earlier in reading order
- `move-down --id <id>` — move one position later
- `move-to --id <id> --position N` — move to a specific position
- `export [--format json|markdown] [--status <s>] [--course-name <n>]` — export queue with fresh Mendeley metadata
- `sync-from-mendeley [--dry-run]` — pull entries from the configured Mendeley collection
- `sync-status` — show queue vs database stats
- `config-show` — show current reading settings
- `config-set --key <k> --value <v>` — set `database_dir` or `queue_collection`
- `queue-clear --yes` — wipe the queue (destructive, requires --yes)

### 4. Configuration

Location: `~/.docent/config.toml`

Key settings under `[reading]`:

| Key | Description | Default |
|-----|-------------|---------|
| `database_dir` | Path to your PDF database folder | prompted on first use |
| `queue_collection` | Mendeley collection name to sync from | `"Docent-Queue"` |
| `mendeley_mcp_command` | Command to launch the Mendeley MCP server | `["uvx", "mendeley-mcp"]` |

Set them with:
```bash
docent reading config-set --key database_dir --value ~/Documents/Papers
docent reading config-set --key queue_collection --value "Docent-Queue"
```

### 5. Connecting to Claude Code (MCP)

`docent serve` starts an MCP server over stdio, exposing **every registered Docent action** as an MCP tool. This lets Claude Code (or any MCP client) call `reading__next`, `reading__stats`, `reading__sync_from_mendeley`, etc. directly.

#### Tool naming

MCP tool names follow the pattern `{tool}__{action}`, with hyphens in action names replaced by underscores:

| Docent action | MCP tool name |
|---------------|---------------|
| `reading next` | `reading__next` |
| `reading stats` | `reading__stats` |
| `reading sync-from-mendeley` | `reading__sync_from_mendeley` |
| `reading set-deadline` | `reading__set_deadline` |

#### Setup: `.mcp.json`

Create or edit `.mcp.json` in your Claude Code project root (or `~/.claude/settings.json` for global):

```json
{
  "mcpServers": {
    "docent": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/docent-repo",
        "run",
        "docent",
        "serve"
      ]
    }
  }
}
```

Replace `/absolute/path/to/docent-repo` with the actual path (e.g. `C:/Users/DELL/Desktop/Docent` on Windows).

After saving, reload Claude Code. The Docent MCP server starts automatically when Claude Code needs it.

#### Verify connection

In Claude Code, ask: *"List my reading queue"* — Claude will call `reading__stats` or `reading__next` via MCP.

Or test the server directly:
```bash
docent serve   # starts, waits for JSON-RPC on stdin; Ctrl+C to stop
```

### 6. Plugin system

Drop a `.py` file (or a Python package folder) into `~/.docent/plugins/` and Docent auto-discovers it on next run. Each plugin registers its own `@register_tool` class and gets its own MCP tools automatically.

---

## Tone and formatting rules

- Use plain, direct prose. No marketing fluff.
- Code blocks for every command and config snippet.
- Keep each section skimmable — short paragraphs, tables where sensible.
- No emojis. No "🎉" or "✨" anywhere.
- Target audience: a grad student who is comfortable with a terminal and has Python 3.11+ installed.

---

## Done criteria

`docs/cli.md` exists and covers all 6 sections above. Run no tests. Do not modify any `.py` file. Do not modify `README.md`. Only create `docs/cli.md`.

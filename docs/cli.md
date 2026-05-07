# Docent CLI v1.0

Docent is a personal CLI control center for grad-school workflows. It manages an academic reading queue and syncs with a Mendeley library. All tools are also exposed as MCP (Model Context Protocol) tools so Claude Code can call them directly.

---

## 1. Installation

```bash
# Requires Python 3.11+. Install with uv (recommended):
pip install uv        # once
uv tool install --editable .    # from the repo root

# Verify:
docent --version
```

Note: after any `pyproject.toml` change, reinstall with `uv tool install --reinstall --editable .`

---

## 2. Quick Start

```bash
# List your reading queue
docent list

# Show all reading commands
docent reading --help
```

---

## 3. The Reading Queue

The reading queue tracks academic papers with status, category, course, and deadline metadata.

**Workflow:**

1. Papers live in Mendeley under a collection called `Docent-Queue`
2. `docent reading sync-from-mendeley` pulls them into the local queue
3. Use `next`, `search`, `stats` to navigate
4. Use `done`, `start`, `edit` to update status
5. Use `set-deadline` to set reading deadlines

### Command Reference

| Command | What it does |
|---------|-------------|
| `docent reading add` | Guidance-only; explains the add-via-Mendeley workflow |
| `docent reading next [--course-name <name>]` | Show the next entry to read (lowest order, optionally filtered by course) |
| `docent reading show --id <id>` | Show one entry's full details |
| `docent reading search --query <q>` | Search title, authors, notes, and tags |
| `docent reading stats [--course-name <name>]` | Queue statistics by category and status |
| `docent reading edit --id <id> [--order N] [--status <s>] [--category <c>] [--course-name <n>] [--notes <text>] [--tags <t>] [--type <t>]` | Edit user-settable fields. Mendeley-owned fields (title, authors) are read-only. |
| `docent reading set-deadline --id <id> [--date YYYY-MM-DD]` | Set or clear a deadline. Omit `--date` to clear. |
| `docent reading done --id <id>` | Mark as done |
| `docent reading start --id <id>` | Mark as currently reading |
| `docent reading remove --id <id>` | Remove from queue |
| `docent reading move-up --id <id>` | Move one position earlier in reading order |
| `docent reading move-down --id <id>` | Move one position later |
| `docent reading move-to --id <id> --position N` | Move to a specific position |
| `docent reading export [--format json|markdown] [--status <s>] [--course-name <n>]` | Export queue with fresh Mendeley metadata |
| `docent reading sync-from-mendeley [--dry-run]` | Pull entries from the configured Mendeley collection |
| `docent reading sync-status` | Show queue vs database stats |
| `docent reading config-show` | Show current reading settings |
| `docent reading config-set --key <k> --value <v>` | Set `database_dir` or `queue_collection` |
| `docent reading queue-clear --yes` | Wipe the queue (destructive, requires `--yes`) |

---

## 4. Configuration

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

---

## 5. Connecting to Claude Code (MCP)

`docent serve` starts an MCP server over stdio, exposing every registered Docent action as an MCP tool. This lets Claude Code (or any MCP client) call `reading__next`, `reading__stats`, `reading__sync_from_mendeley`, etc. directly.

### Tool Naming

MCP tool names follow the pattern `{tool}__{action}`, with hyphens in action names replaced by underscores:

| Docent action | MCP tool name |
|---------------|---------------|
| `reading next` | `reading__next` |
| `reading stats` | `reading__stats` |
| `reading sync-from-mendeley` | `reading__sync_from_mendeley` |
| `reading set-deadline` | `reading__set_deadline` |

### Setup: `.mcp.json`

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

Replace `/absolute/path/to/docent-repo` with the actual path. On Windows, for example: `C:/Users/DELL/Desktop/Docent`.

After saving, reload Claude Code. The Docent MCP server starts automatically when Claude Code needs it.

### Verify Connection

In Claude Code, ask: *"List my reading queue"* — Claude will call `reading__stats` or `reading__next` via MCP.

Or test the server directly:

```bash
docent serve   # starts, waits for JSON-RPC on stdin; Ctrl+C to stop
```

---

## 6. Plugin System

Drop a `.py` file (or a Python package folder) into `~/.docent/plugins/` and Docent auto-discovers it on next run. Each plugin registers its own `@register_tool` class and gets its own MCP tools automatically.
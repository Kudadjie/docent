# Docent CLI v1.0

Docent is a personal CLI control center for grad-school workflows. It manages an academic reading queue and syncs with a Mendeley library. All tools are also exposed as MCP (Model Context Protocol) tools so Claude Code can call them directly.

> **Mendeley setup:** Docent connects to your Mendeley library via [mendeley-mcp](https://github.com/pallaprolus/mendeley-mcp). You'll need to register a Mendeley API client (Client ID + Secret) and run through the OAuth flow once before `sync-from-mendeley` works. Full instructions at the link above.

---

## 1. Installation

```bash
# Requires Python 3.11+

# Recommended — uv (fastest):
uv tool install docent-cli

# Or pipx:
pipx install docent-cli

# Or plain pip:
pip install docent-cli

# Verify:
docent --version
```

**Updates:**
```bash
uv tool upgrade docent-cli   # uv
pipx upgrade docent-cli      # pipx
pip install --upgrade docent-cli  # pip
```

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
| `docent reading next [--category <name>]` | Show the next entry to read (lowest order, optionally filtered by category prefix) |
| `docent reading show --id <id>` | Show one entry's full details |
| `docent reading search --query <q>` | Search title, authors, notes, and tags |
| `docent reading stats` | Queue statistics by category and status |
| `docent reading edit --id <id> [--order N] [--status <s>] [--category <c>] [--deadline <d>] [--notes <text>] [--tags <t>] [--type <t>]` | Edit user-settable fields. Mendeley-owned fields (title, authors) are read-only. |
| `docent reading set-deadline --id <id> --deadline YYYY-MM-DD` | Set a deadline. Pass `--deadline ""` to clear. |
| `docent reading done --id <id>` | Mark as done |
| `docent reading start --id <id>` | Mark as currently reading |
| `docent reading remove --id <id>` | Remove from queue |
| `docent reading move-up --id <id>` | Move one position earlier in reading order |
| `docent reading move-down --id <id>` | Move one position later |
| `docent reading move-to --id <id> --position N` | Move to a specific position |
| `docent reading export [--format json|markdown] [--status <s>] [--category <c>]` | Export queue with fresh Mendeley metadata |
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

`docent serve` starts an MCP server over stdio, exposing every registered Docent action as an MCP tool. This lets Claude Code call your reading queue tools directly — no terminal needed.

### Tool Naming

MCP tool names follow the pattern `{tool}__{action}`, with hyphens replaced by underscores:

| Docent action | MCP tool name |
|---------------|---------------|
| `reading next` | `reading__next` |
| `reading stats` | `reading__stats` |
| `reading search` | `reading__search` |
| `reading sync-from-mendeley` | `reading__sync_from_mendeley` |
| `reading set-deadline` | `reading__set_deadline` |
| `reading move-up` | `reading__move_up` |

All registered actions are exposed automatically — run `docent list` to see the full set.

### Setup: `.mcp.json`

Create `.mcp.json` in your Claude Code project root (or add to `~/.claude/settings.json` for global access):

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

Replace `/absolute/path/to/docent-repo` with the actual path. On Windows: `C:/Users/DELL/Desktop/Docent` (forward slashes work fine).

Restart Claude Code after saving — the server starts automatically when needed.

### Verify Connection

Test the server directly first:

```bash
docent serve
# [docent] MCP server ready — 18 tools registered. Waiting for client…
# (blocks on stdin — Ctrl+C to stop)
```

Then in Claude Code, try one of the example prompts below.

### Example Use Cases

**Check your queue without opening a terminal:**
> "What's next on my reading queue?"

Claude calls `reading__next` and returns your top-priority item with its deadline, category, and type.

---

**Get a queue overview before a study session:**
> "Give me a stats summary of my reading queue."

Claude calls `reading__stats` — total items, breakdown by category and type, overdue deadlines.

---

**Find something specific:**
> "Do I have anything in my queue about storm surge or coastal flooding?"

Claude calls `reading__search` with the relevant query and returns matching entries.

---

**Sync your Mendeley library into the queue:**
> "Pull in any new papers from my Mendeley Docent-Queue collection."

Claude calls `reading__sync_from_mendeley` and reports what was added, unchanged, or removed.

---

**Set a deadline mid-conversation:**
> "I need to finish the Komen 2023 paper before my supervisor meeting on Friday — set a deadline."

Claude calls `reading__set_deadline` with the entry id and date. No context-switching required.

---

**Reorder your queue:**
> "Move the storm surge paper to the top of my queue."

Claude calls `reading__search` to find the entry id, then `reading__move_to` with position 1.

---

## 6. Studio

Studio runs deep research, literature reviews, and peer reviews, backed by Feynman CLI or the Docent-native 6-stage pipeline.

| Command | Notes |
|---------|-------|
| `docent studio deep-research "topic" [--backend feynman\|docent] [--output local\|notebook\|vault]` | Full research pipeline |
| `docent studio lit "topic" [--backend feynman\|docent] [--output local\|notebook\|vault]` | Literature-focused (80% paper search bias) |
| `docent studio review "artifact" [--output local\|notebook\|vault]` | 3-stage: fetch → researcher → reviewer |
| `docent studio to-notebook [--output-file <path>] [--max-sources N] [--notebook-id <id>]` | Post-process: push existing research output to NotebookLM |
| `docent studio search-papers "query" [--max-results N]` | Search alphaXiv for academic papers |
| `docent studio get-paper "arxiv-id"` | Fetch AI-generated overview for a paper |
| `docent studio usage` | Show today's Feynman/OpenCode spend + Tavily requests |
| `docent studio config-show` | Show current Studio settings |
| `docent studio config-set --key <k> --value <v>` | Set a Studio config value |

### Output destinations (`--output`)

| Value | Behaviour |
|-------|-----------|
| `local` | Save to `output_dir` only (default) |
| `notebook` | Save locally, then create a new NotebookLM notebook and push all sources. Requires `notebooklm-py` and `notebooklm login`. |
| `vault` | Save locally, then copy to `{obsidian_vault}/Studio/` with YAML frontmatter. Requires `obsidian_vault` config key. |

**Studio config keys:** `output_dir`, `feynman_budget_usd`, `oc_provider`, `oc_model_planner`, `oc_model_writer`, `oc_model_verifier`, `oc_model_reviewer`, `oc_model_researcher`, `oc_budget_usd`, `tavily_api_key`, `notebooklm_notebook_id`, `obsidian_vault`, `alphaxiv_api_key`.

**alphaXiv paper search:** `search-papers` and `get-paper` use the `alphaxiv-py` SDK. Get a free API key at [alphaxiv.org/settings](https://alphaxiv.org/settings) and set it:

```bash
docent studio config-set --key alphaxiv_api_key --value "<key>"
```

Or via `DOCENT_RESEARCH__ALPHAXIV_API_KEY` env var.

**Tavily:** Web search in the docent-native backend uses Tavily (free tier: 1,000 calls/month). Set your API key:

```bash
docent studio config-set --key tavily_api_key --value "tvly-..."
```

Or via `DOCENT_RESEARCH__TAVILY_API_KEY` env var.

---

## 7. Plugin System

Drop a `.py` file (or a Python package folder) into `~/.docent/plugins/` and Docent auto-discovers it on next run. Each plugin registers its own `@register_tool` class and gets its own MCP tools automatically.

**Install a plugin:**
```bash
cp myplugin.py ~/.docent/plugins/
docent list   # your tool appears immediately
```

**What you get automatically:**
- CLI sub-commands: `docent <toolname> <action>`
- MCP tools via `docent serve`: `<toolname>__<action>`
- `--help` output from action descriptions and field names

For the full plugin contract (Tool ABC, `@action`, `to_shapes()`, `on_startup`), see [`docs/plugin-guide.md`](plugin-guide.md).

---

## 8. Maintenance

### `docent doctor`

Check environment health: Python version, Docent version, external tools (feynman, mendeley-mcp), API key presence, and GitHub update availability.

```bash
docent doctor
```

Outputs a table with `OK` / `WARN` / `FAIL` / `SKIP` status for each check. Run this first when something isn't working.

### `docent setup`

Interactive guided setup: Mendeley connection, PDF database directory, API keys (Tavily, Semantic Scholar). Safe to re-run — existing values are shown as defaults.

```bash
docent setup
```

### `docent update`

Upgrade to the latest PyPI release.

```bash
docent update
```

Equivalent to `uv tool upgrade docent-cli`. Only works if Docent was installed via `uv tool install`.

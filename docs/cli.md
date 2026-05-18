# Docent CLI v1.2

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
        "--no-sync",
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
# [docent] MCP server ready — 35 tools registered. Waiting for client…
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
| `docent studio deep-research --topic "..." [--backend <b>] [--output local\|notebook\|vault] [--to-notebook] [--guide-files <path>]` | Full research pipeline |
| `docent studio lit --topic "..." [--backend <b>] [--output local\|notebook\|vault] [--to-notebook] [--guide-files <path>]` | Literature review (Tavily + scholarly + arXiv) |
| `docent studio review --artifact "..." [--backend feynman\|docent] [--output local\|notebook\|vault]` | Peer review of arXiv ID, PDF, or URL |
| `docent studio compare --artifact-a "..." --artifact-b "..." [--backend feynman\|docent]` | Side-by-side comparison of two artifacts |
| `docent studio draft --topic "..." [--backend feynman\|docent]` | Draft a paper section or document |
| `docent studio replicate --artifact "..." [--backend feynman\|docent]` | Build a replication guide for a paper |
| `docent studio audit --artifact "..." [--backend feynman\|docent]` | Audit a paper for methodology and reproducibility |
| `docent studio to-notebook [--output-file <path>] [--max-sources N] [--notebook-id <id>]` | Post-process: push existing research output to NotebookLM |
| `docent studio search-papers --query "..." [--max-results N]` | Search alphaXiv for academic papers |
| `docent studio get-paper --arxiv-id "2401.12345"` | Fetch AI-generated overview for a paper |
| `docent studio scholarly-search --query "..." [--max-results N]` | Search Google Scholar / Semantic Scholar / CrossRef |
| `docent studio usage` | Show today's Feynman/OpenCode spend + Tavily requests |
| `docent studio config-show` | Show current Studio settings |
| `docent studio config-set --key <k> --value <v>` | Set a Studio config value |

**Backends for `deep-research` and `lit` (`--backend <b>`):**

| Backend | How it works | Requires |
|---------|-------------|---------|
| `free` | Docent aggregates sources; the AI assistant synthesises in-conversation. Fast, no API cost. **Best for MCP use.** | Nothing |
| `docent` | 6-stage pipeline via configured provider (default: opencode). **Terminal only — times out via MCP.** | OpenCode server |
| `groq` | 6-stage pipeline via Groq API | `GROQ_API_KEY` |
| `gemini` | 6-stage pipeline via Gemini API | `GEMINI_API_KEY` |
| `openrouter` | 6-stage pipeline via OpenRouter | `OPENROUTER_API_KEY` |
| `mistral` | 6-stage pipeline via Mistral | `MISTRAL_API_KEY` |
| `cerebras` | 6-stage pipeline via Cerebras | `CEREBRAS_API_KEY` |
| `anthropic` | 6-stage pipeline via Anthropic API | `ANTHROPIC_API_KEY` |
| `openai` | 6-stage pipeline via OpenAI API | `OPENAI_API_KEY` |
| `ollama` | 6-stage pipeline via local Ollama | Ollama running locally |
| `lm_studio` | 6-stage pipeline via LM Studio | LM Studio running locally |
| `local` | 6-stage pipeline via any OAI-compatible server | `local_base_url` config |
| `feynman` | Full Feynman CLI deep research (10–30 min). **Terminal only — always times out via MCP.** | Feynman installed |

> **MCP note:** `free` is the only backend reliable via MCP — all AI backends run a multi-minute pipeline that will time out. For AI backends from Claude Desktop, use the terminal command shown when you ask.

### Citation verification

Research output from `deep-research` and `lit` (both `--backend docent` and `--backend feynman`)
automatically includes a **## Citation Verification** section at the end of the document.
Every DOI and arXiv ID found in the draft is checked against CrossRef and Semantic Scholar.
Identifiers that cannot be resolved are flagged — they may be hallucinated, misprinted,
or not yet indexed, and should be checked before citing.

### Output destinations (`--output`)

| Value | Behaviour |
|-------|-----------|
| `local` | Save to `output_dir` only (default) |
| `notebook` | Save locally, then create a new NotebookLM notebook and push all sources. Requires `notebooklm-py` and `notebooklm login`. |
| `vault` | Save locally, then copy to `{obsidian_vault}/Studio/` with YAML frontmatter. Requires `obsidian_vault` config key. |

**Studio config keys:**

| Key | Default | Notes |
|---|---|---|
| `studio_backend` | `opencode` | Active Docent-tier backend: `opencode`, `groq`, `gemini`, `openrouter`, `mistral`, `cerebras`, `anthropic`, `openai`, `ollama`, `lm_studio`, `local` |
| `output_dir` | `~/Documents/Docent/research` | Research output directory |
| `feynman_budget_usd` | `0.0` | Feynman spend cap per session (0 = unlimited) |
| `oc_provider` / `oc_model_*` / `oc_budget_usd` | — | OpenCode backend settings |
| `groq_api_key` / `groq_model` | `llama-3.3-70b-versatile` | [Free at console.groq.com](https://console.groq.com) |
| `gemini_api_key` / `gemini_model` | `gemini-2.0-flash` | [Free at aistudio.google.com](https://aistudio.google.com) |
| `openrouter_api_key` / `openrouter_model` | `meta-llama/llama-3.3-70b-instruct:free` | [Free tier at openrouter.ai](https://openrouter.ai) |
| `mistral_api_key` / `mistral_model` | `mistral-small-latest` | [Free tier at console.mistral.ai](https://console.mistral.ai) |
| `cerebras_api_key` / `cerebras_model` | `llama-3.3-70b` | [Free tier at cloud.cerebras.ai](https://cloud.cerebras.ai) |
| `ollama_base_url` / `ollama_model` | `http://localhost:11434` / `llama3` | Local Ollama server |
| `lm_studio_base_url` / `lm_studio_model` | `http://localhost:1234/v1` / `local-model` | Local LM Studio server |
| `local_base_url` / `local_model` / `local_api_key` | — | Generic OAI-compatible local backend |
| `tavily_api_key` | — | [Free at tavily.com](https://tavily.com) |
| `notebooklm_notebook_id` | — | NotebookLM notebook ID from URL |
| `obsidian_vault` | — | Absolute path to Obsidian vault root |
| `alphaxiv_api_key` | — | [Free at alphaxiv.org/settings](https://alphaxiv.org/settings) |

**alphaXiv paper search:** `search-papers` and `get-paper` use the `alphaxiv-py` SDK. Get a free API key at [alphaxiv.org/settings](https://alphaxiv.org/settings) and set it:

```bash
docent studio config-set --key alphaxiv_api_key --value "<key>"
```

Or via `DOCENT_RESEARCH__ALPHAXIV_API_KEY` env var.

**Tavily:** Docent uses Tavily for web search in the research pipeline. There are two tiers:

- **Free key** (1,000 calls/month) — enables `tavily_search`, which gives better web results than the DuckDuckGo fallback. Get one free at [app.tavily.com](https://app.tavily.com) (no credit card).
- **Paid key** — unlocks the **Tavily Research API** (`tavily_research`), which replaces the 6-stage manual pipeline with a single deep-research call that produces a fully cited report. Significantly faster and higher quality.

Without any key, web search falls back to DuckDuckGo automatically.

```bash
docent studio config-set --key tavily_api_key --value "tvly-..."
```

Or via `DOCENT_RESEARCH__TAVILY_API_KEY` env var.

`docent setup` validates the key against the Tavily API before saving and reports which tier it detected.

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

Each API key is validated against its service before saving. An invalid key shows a red ✗ and offers a "save anyway" prompt rather than silently storing a broken value.

```bash
docent setup
```

### `docent update`

Upgrade to the latest PyPI release.

```bash
docent update
```

Equivalent to `uv tool upgrade docent-cli`. Only works if Docent was installed via `uv tool install`.

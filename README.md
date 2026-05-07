<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="design_handover/assets/logo-light.svg">
    <source media="(prefers-color-scheme: light)" srcset="design_handover/assets/logo.svg">
    <img src="design_handover/assets/logo.svg" alt="Docent" width="200" />
  </picture>
  <br /><br />

  [![PyPI version](https://img.shields.io/pypi/v/docent-cli?color=18E299&label=pypi&style=flat-square)](https://pypi.org/project/docent-cli/)
  [![Python](https://img.shields.io/pypi/pyversions/docent-cli?style=flat-square&color=18E299)](https://pypi.org/project/docent-cli/)
  [![License](https://img.shields.io/github/license/Kudadjie/docent?style=flat-square&color=18E299)](LICENSE)
  [![GitHub stars](https://img.shields.io/github/stars/Kudadjie/docent?style=flat-square&color=18E299)](https://github.com/Kudadjie/docent/stargazers)

  <p>A personal CLI control center for grad-school workflows — papers, research, writing tools, and subprocess wrappers, all behind a single <code>docent &lt;tool&gt;</code> command.</p>
</div>

> **Built with AI, Architected by a Human:** Much of the codebase was written by Claude Code (Opus 4.7) and OpenCode Go subscription models (Kimi K2.6, DeepSeek V4 Pro, Qwen 3.5 Plus, MiniMax M2.7), but the architecture was strictly human-directed — designed, planned, tested, and iterated over many sessions.

## ✨ What works today

- `docent --version`, `docent --help`, `docent list`, `docent info <tool>`
- **Tool contract — two shapes:**
  - *Single-action*: subclass `Tool`, set `input_schema`, override `run()`. CLI: `docent <tool> --flag ...`
  - *Multi-action*: decorate methods with `@action(...)`. CLI: `docent <tool> <action> --flag ...`
  - A tool is one or the other — registry enforces mutual exclusivity at import time.
- **Auto-discovery** — drop a file in `src/docent/tools/`, decorate with `@register_tool`, and Typer commands generate at startup from the Pydantic input schema. No CLI edits.
- **Context plumbing** — `context.settings` (Pydantic + `~/.docent/config.toml` + env overrides), `context.llm` (lazy litellm wrapper), `context.executor` (list-args subprocess, no shell-injection surface).
- **`docent.learning.RunLog`** — per-namespace JSONL run-log with cap-and-roll, for tools that want a "what did I do recently" history.
- **`reading` tool** — reading queue CRUD (`next / show / search / stats / remove / edit / done / start / export`); Mendeley-backed ingestion; deadline notifications at startup; `move-up / move-down / move-to`; MCP-exposed so Claude Code can call it directly.
- **`MendeleyCache`** — read-through file-backed cache (5-min TTL) for fresh metadata on every `next / show / search`. Degrades gracefully to queue snapshot on auth failure.
- **Plugin system** — drop a `.py` file into `~/.docent/plugins/` and Docent auto-discovers it on next run.

## 📦 Install

```bash
# Recommended
uv tool install docent-cli

# Or pipx
pipx install docent-cli

# Or plain pip
pip install docent-cli

# Verify
docent --version
```

**Updates:**
```bash
uv tool upgrade docent-cli
```

## 🏗 Architecture

See [`Docent_Architecture.md`](Docent_Architecture.md) for the full design. The short version:

- **Tool registry** — tools self-register via `@register_tool` at import time. Registry stores the class, not an instance, so nothing runs until the tool is actually invoked.
- **Context object** — frozen dataclass passed to every tool. Provides `settings`, `llm` (lazy litellm), and `executor` (subprocess wrapper).
- **UI / logic boundary** — tools return typed Pydantic data. They never import `docent.ui` and never touch Rich. The CLI renders; the future dashboard will serialize the same data to JSON.
- **Plugin system** — drop a file in `~/.docent/plugins/`, decorate with `@register_tool`, and Typer commands generate at startup. No CLI edits needed.

## 📚 Tools

### `reading` — Reading Queue

Manages your academic reading queue and syncs with Mendeley.

**Workflow:** Drop a PDF in your `database_dir` → Mendeley auto-imports it → drag it into your `Docent-Queue` collection → run `docent reading sync-from-mendeley`. Category is automatically detected from Mendeley sub-collections.

**Queue management**

| Command | Description |
|---|---|
| `docent reading next` | Show the next paper to read (lowest order number) |
| `docent reading next --course-name CES701` | Next paper for a specific course |
| `docent reading show <id>` | Show full details for one entry |
| `docent reading search <query>` | Search by title, authors, notes, tags, or id |
| `docent reading stats` | Counts by status, category, and course |
| `docent reading export` | Export queue as JSON (default) or Markdown table |
| `docent reading export --format markdown --status queued` | Filtered export, sorted by reading order |

**Status transitions**

| Command | Description |
|---|---|
| `docent reading start <id>` | Mark as currently reading (stamps `started` timestamp) |
| `docent reading done <id>` | Mark as finished (stamps `finished` timestamp) |
| `docent reading remove <id>` | Remove entry from queue |

**Editing**

| Command | Description |
|---|---|
| `docent reading edit <id> --order 1` | Set reading priority (1 = read first) |
| `docent reading set-deadline <id> --deadline 2026-06-15` | Set a reading deadline |
| `docent reading set-deadline <id> --deadline ''` | Clear a deadline |
| `docent reading edit <id> --notes "Key paper for lit review"` | Add notes |
| `docent reading edit <id> --tags tag1 tag2` | Set tags |
| `docent reading edit <id> --type book_chapter` | Set entry type (paper / book / book_chapter) |
| `docent reading move-up <id>` | Move one position earlier |
| `docent reading move-down <id>` | Move one position later |
| `docent reading move-to <id> --position 3` | Move to a specific position |

**Deadlines:** Docent prints a startup warning for entries due within 3 days or overdue — once per calendar day.

**Entry types:** Automatically detected from Mendeley document type on sync. Override with `edit --type book_chapter`.

**Mendeley sync**

| Command | Description |
|---|---|
| `docent reading sync-from-mendeley` | Pull from your Mendeley Docent-Queue collection |
| `docent reading sync-from-mendeley --dry-run` | Preview changes without writing |
| `docent reading sync-status` | Report queue size and PDFs in database_dir |

**Configuration**

| Command | Description |
|---|---|
| `docent reading config-show` | Show current reading settings |
| `docent reading config-set database_dir ~/path/to/Papers` | Set the PDF database folder |
| `docent reading config-set queue_collection "Docent-Queue"` | Set the Mendeley collection name |

**Other**

| Command | Description |
|---|---|
| `docent reading queue-clear --yes` | Wipe the entire queue (irreversible) |

## 🔌 MCP — Use Docent from Claude Code

`docent serve` starts an MCP server over stdio, exposing every action as an MCP tool. Claude Code can call your reading queue directly — no terminal needed.

See [`docs/cli.md`](docs/cli.md) for the full setup guide and `.mcp.json` template.

## 🛠 Adding a tool

Single-action tools are the simplest shape:

```python
# src/docent/tools/echo.py
from pydantic import BaseModel, Field
from docent.core import Context, Tool, register_tool


class EchoInputs(BaseModel):
    msg: str = Field(..., description="Message to echo.")
    count: int = Field(1, description="Times to repeat.")


@register_tool
class Echo(Tool):
    name = "echo"
    description = "Repeat a message N times."
    category = "demo"
    input_schema = EchoInputs

    def run(self, inputs: EchoInputs, context: Context) -> str:
        return (inputs.msg + " ") * inputs.count
```

Then `docent echo --msg hi --count 3` just works. No CLI edits, no registration code — the decorator is enough.

For tools with several related operations on shared state, use the multi-action shape — decorate methods with `@action(...)`. See `src/docent/tools/reading.py` for the reference implementation.

## 🚀 Coming Soon

- **`docent research`** — AI-powered research tool: paper search (alphaXiv, Google Scholar), literature review, and multi-source synthesis pipelines. Routes through [Feynman](https://www.feynman.is/) as the primary research agent, with a direct Claude fallback if Feynman isn't available.

- **Web dashboard** — a visual interface over the same tool registry. Browse your reading queue, run actions, and view stats from a browser — no terminal required. The reading page is already live; the full dashboard is next.

- **Omnibox (natural language interface)** — type what you want in plain English and Docent routes it to the right action: *"what should I read next for CES701?"* or *"sync my Mendeley queue"* — no flags, no subcommands.

## 💡 Why

I have a pile of Claude Code skills I actually use (research-to-notebook, paper-pipeline, feynman wrappers, literature-review, etc.) but they only work inside a Claude session. Docent is the terminal-first home for the same workflows — scriptable, pipeable, cron-able, and eventually a dashboard. MCP is not a replacement; Docent can later expose itself *through* MCP, but that's a late-stage adapter, not the core.

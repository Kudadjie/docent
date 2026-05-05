# Docent

A personal CLI control center for grad-school workflows — papers, research, writing tools, subprocess wrappers — all behind a single `docent <tool>` command. Built so a web dashboard can wrap the same tool registry later without rewriting anything.

> **Built with AI, Architected by a Human:** Much of the codebase for Docent was written by Claude Code (Opus 4.7) and OpenCode Go subscription models (Kimi K2.6, DeepSeek V4 Pro, Qwen 3.5 Plus, MiniMax M2.7), but the architecture was strictly human-directed — designed, planned, tested, and iterated over many sessions.

## What works today

- `docent --version`, `docent --help`, `docent list`, `docent info <tool>`
- **Tool contract — two shapes:**
  - *Single-action*: subclass `Tool`, set `input_schema`, override `run()`. CLI: `docent <tool> --flag ...`
  - *Multi-action*: decorate methods with `@action(...)`. CLI: `docent <tool> <action> --flag ...`
  - A tool is one or the other — registry enforces mutual exclusivity at import time.
- **Auto-discovery**: drop a file in `src/docent/tools/`, decorate with `@register_tool`, and Typer commands generate at startup from the Pydantic input schema. No CLI edits.
- **Context plumbing**: `context.settings` (Pydantic + `~/.docent/config.toml` + env overrides), `context.llm` (lazy litellm wrapper), `context.executor` (list-args subprocess, no shell-injection surface).
- **`docent.learning.RunLog`**: per-namespace JSONL run-log with cap-and-roll, for tools that want a "what did I do recently" history (used by `paper`'s mutators).
- **`paper` tool** (the first ported skill — being rewritten as `reading` next): queue CRUD (`next / show / search / stats / remove / edit / done / ready-to-read / export`); `add` (bare guidance mode or `--mendeley-id` upsert); `sync-from-mendeley` (reconciles the `Docent-Queue` Mendeley collection into the sidecar, overlays fresh metadata on display); `sync-pull` (Unpaywall OA download); `sync-status`; `config-show / config-set`; `queue-clear`. Mendeley is the source of truth for title/authors/year/doi — `paper` is a thin workflow layer on top.
- **`PaperQueueStore`**: persistence seam in `paper_store.py`. Actions mutate queue state through the store, never by reaching into JSON directly.
- **`MendeleyCache`**: read-through file-backed cache (5-min TTL) used by `next / show / search` to overlay live Mendeley metadata. Degrades gracefully to queue snapshot on auth/transport failure.
- Themed Rich console singleton; tools never touch it directly (they return typed data; CLI renders).

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync
uv run docent --version
```

For a global install once you want `docent` on your PATH:

```bash
uv tool install .
docent --version
```

## Architecture

See [`Docent_Architecture.md`](Docent_Architecture.md) for the full design. The short version:

- **Tool registry** — tools self-register via `@register_tool` at import time. Registry stores the class, not an instance, so nothing runs until the tool is actually invoked.
- **Context object** — frozen dataclass passed to every tool. Grows one field per build step (settings → logger → llm → executor).
- **UI / logic boundary** — tools return typed data. They never import `docent.ui` and never touch Rich. The CLI renders; the future dashboard will render the same data differently.
- **Strict build order** — the registry hardens first, then LLM, then executor, then real tools, then plugins, then MCP. MCP is the last thing, not the first.

## Build order

- [x] 1. Project skeleton + `docent --version`
- [x] 2. Config loader + Rich console singleton
- [x] 3. Tool base class + registry + `@register_tool` + `Context`
- [x] 4. Dynamic Typer commands + `docent list` / `docent info`
- [x] 5. litellm wrapper (`LLMClient`, lazy-imported, on `Context.llm`)
- [x] 6. Subprocess executor (`Executor`, on `Context.executor`)
- [x] 7a. Multi-action contract extension (`@action` decorator)
- [x] 7b. First real tool: `paper add` stub (validates the contract end-to-end)
- [x] 7c. `docent.learning.RunLog` (per-namespace JSONL run-log; cap-and-roll)
- [x] 8. Simple paper CRUD actions (next/show/search/stats/remove/edit/done/ready-to-read/export)
- [x] 9. PDF-driven `paper add` + `paper scan --folder` (both retired in Step 11.8 after Mendeley-truth pivot)
- [x] 10. Progress streaming (`ProgressEvent` + generator actions + `_drive_progress`); per-tool config; pytest harness; `PaperQueueStore` persistence seam; UI-leak cleanup
- [x] 11. Paper sync ops — pivoted mid-stream to Mendeley-as-truth. Ships: `sync-from-mendeley`, `sync-pull` (Unpaywall), `MendeleyCache` read-through overlay, `sync-status`, trim schema migration. Retired: `sync-promote`, `sync-mendeley`, homegrown PDF extraction.
- [ ] 12. `reading` tool rewrite — graduate `paper` → `reading`; schema fixes (category/deadline/order/summary fields); notification system; books support
- [ ] 13. External `~/.docent/plugins/` discovery
- [ ] 14. Full MCP adapter

## Adding a tool

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

For tools with several related operations on shared state (a reading queue, a research notebook, a browser session), use the multi-action shape — decorate methods with `@action(...)` instead of overriding `run()`. Each action gets its own Pydantic input schema and becomes `docent <tool> <action> --flag ...`. See `src/docent/tools/paper.py` for the reference implementation.

## Why

I have a pile of Claude Code skills I actually use (research-to-notebook, paper-pipeline, feynman wrappers, literature-review, etc.) but they only work inside a Claude session. Docent is the terminal-first home for the same workflows — scriptable, pipeable, cron-able, and eventually a dashboard. MCP is not a replacement; Docent can later expose itself *through* MCP, but that's a late-stage adapter, not the core.

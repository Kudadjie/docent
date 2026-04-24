# Docent

*A Vibe Coded Project*</br>

A personal CLI control center for grad-school workflows — papers, research, writing tools, subprocess wrappers — all behind a single `docent <tool>` command. Built so a web dashboard can wrap the same tool registry later without rewriting anything.

> **Status:** early. Steps 1–4 of a 10-step build are done. No real tools are wired up yet.

> **Heads up:** this is a vibe-coded project. Every design decision gets talked through with Claude in the loop, the code is written in the loop, and the commits land small. It's a working document, not a reference architecture.

## What works today

- `docent --version`, `docent --help`, `docent list`, `docent info <tool>`
- Drop a file in `src/docent/tools/`, subclass `Tool`, decorate with `@register_tool`, and it auto-becomes a subcommand with typed `--flag` arguments generated from its Pydantic input schema.
- Config loader (`~/.docent/config.toml`, overridable via env vars) and a themed Rich console singleton.

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
- [x] 3. Tool base class + registry + `@register_tool` decorator
- [x] 4. Dynamic Typer commands + `docent list` / `docent info`
- [ ] 5. litellm wrapper
- [ ] 6. Subprocess executor
- [ ] 7. First real tool (port easiest skill)
- [ ] 8. Second tool (prove the interface generalizes)
- [ ] 9. External plugin discovery (`~/.docent/plugins/`)
- [ ] 10. MCP adapter

## Adding a tool

Once Step 5+ lands you'll have LLM and subprocess helpers to lean on. Today the minimum is:

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

## Why

I have a pile of Claude Code skills I actually use (research-to-notebook, paper-pipeline, feynman wrappers, literature-review, etc.) but they only work inside a Claude session. Docent is the terminal-first home for the same workflows — scriptable, pipeable, cron-able, and eventually a dashboard. MCP is not a replacement; Docent can later expose itself *through* MCP, but that's a late-stage adapter, not the core.

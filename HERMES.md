# Docent — Hermes Project Instructions

## Project
Python CLI + MCP server for grad-school workflows. Source in `src/docent/`.
Plugin architecture: bundled tools in `src/docent/bundled_plugins/`, external in `~/.docent/plugins/`.
All tool actions use the `@action` decorator and return a Pydantic result model.

## Testing & running
```bash
uv run pytest              # full suite (~3-4s); must be green before task is done
uv run docent --help       # smoke test CLI
uv run docent <tool> <action> --help   # action-level smoke test
```

## Hard rules
- **Memory ownership depends on who is driving:**
  - **Claude Code is the primary driver** and owns `memory/`, `decisions.md`, and `CLAUDE.md`.
  - **When Claude Code's usage limit is hit**, Hermes becomes the main driver and **may** read, update, and maintain memory files (including `AI_CONTEXT.md`). Act as the primary agent — follow the AI_CONTEXT.md navigation and rules fully.
  - **When Claude Code returns**, it resumes ownership. Hermes should note any memory changes made so Claude can review them.
- No new dependencies without explicit instruction in the brief.
- Follow existing patterns (action decorator, Pydantic result models, no `asyncio.run` at top level).
- Run `uv run pytest` as the final verification step. Do not declare success until it is green.

## On complex tasks
Before touching any code, read:
1. `memory/MEMORY.md` — project memory index (short, read it fully)
2. `memory/gotchas.md` — known landmines; check before writing anything that smells familiar

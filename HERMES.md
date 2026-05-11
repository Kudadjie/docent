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
- **Never modify** `memory/`, `decisions.md`, or `CLAUDE.md` — Claude owns these.
- No new dependencies without explicit instruction in the brief.
- Follow existing patterns (action decorator, Pydantic result models, no `asyncio.run` at top level).
- Run `uv run pytest` as the final verification step. Do not declare success until it is green.

## On complex tasks
Before touching any code, read:
1. `memory/MEMORY.md` — project memory index (short, read it fully)
2. `memory/gotchas.md` — known landmines; check before writing anything that smells familiar

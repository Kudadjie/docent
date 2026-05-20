# ADR-001: CLI, MCP, and FastAPI are three surfaces over one core

**Status:** Active  
**Date:** 2026-05-20  
**Deciders:** John David K. T. Kudadjie

---

## Context

Docent needs to be usable from three distinct entry points:
1. **CLI** — `docent <tool> <action>` for interactive terminal use
2. **MCP server** — `docent serve` exposes all tools as MCP tools so Claude can call them
3. **FastAPI UI** — `docent ui` serves a Next.js web interface on `localhost:7432`

Early implementations duplicated serialization logic and business logic across these three paths. The question was: should each surface own its own invocation and serialization, or should there be a shared core?

## Decision

All three surfaces invoke tools through a **single shared core** in `docent.core.invoke`:

```
CLI ────────────────────────────────┐
MCP server (mcp_server.py) ────────┤──► core.invoke.run_action() ──► Tool.__action__()
FastAPI UI (ui_routes/*.py) ────────┘
```

Specifically:
- `core.invoke.run_action(tool, action, args)` — the universal dispatcher; returns raw Python values (Pydantic models, generators, plain values)
- `core.invoke.serialize_result(result)` — converts any result to a JSON string; shared by MCP and FastAPI
- `core.invoke.invoke_action_for_ui(tool, action, args)` — wraps run_action + serialize_result for the FastAPI surface; handles ConfirmationRequired, drains generators

## Consequences

**Good:**
- Tools are written once and immediately available on all three surfaces without any additional wiring
- Adding a new surface (e.g., a gRPC endpoint, a Slack bot) means implementing one thin adapter over `run_action`
- The tool contract (Tool ABC + @action decorator + Pydantic input_schema) is the only thing a plugin author needs to understand

**Trade-offs:**
- MCP and FastAPI cannot easily have surface-specific invocation logic (e.g., different timeout behaviour) without forking from `run_action`
- The MCP server adds post-processing (result annotations, MANDATORY NEXT STEPS prompts) that doesn't exist in the CLI or FastAPI paths — this is handled in `mcp_server.py` after `run_action` returns, not inside the tool

**Rejected alternatives:**
- **Separate invocation paths per surface**: rejected because it causes logic drift (e.g., auth validation, preflight checks in one path but not another)
- **MCP as the canonical surface**: rejected because MCP has its own timeout and serialization constraints that would pollute the tool contract

## Related

- `src/docent/core/invoke.py` — the implementation
- `src/docent/mcp_server.py` — MCP surface (imports from core.invoke)
- `src/docent/ui_routes/` — FastAPI route modules (import from core.invoke)
- `src/docent/cli.py` — CLI surface (uses run_action via Typer callbacks)
- ARCHITECTURE.md §Layer 9, §Layer 10 — design overview

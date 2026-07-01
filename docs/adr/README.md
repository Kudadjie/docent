# Architecture Decision Records

Durable architectural decisions, with context, consequences, and rejected
alternatives. One file per decision, numbered in order.

| ADR | Title | Date |
|-----|-------|------|
| [001](001-cli-mcp-fastapi-surfaces.md) | CLI, MCP, and FastAPI are three surfaces over one core | 2026-05-20 |
| [002](002-reference-manager-protocol-zotero.md) | Zotero via pyzotero behind the ReferenceManagerBackend protocol | 2026-05-30 |
| [003](003-prompts-as-first-class-code.md) | Prompts are first-class code — registry + eval hash tripwire | 2026-05-30 |
| [004](004-queue-schema-v2-reference-id.md) | Queue schema v2 — manager-neutral field names + auto-migration | 2026-05-31 |
| [005](005-dependency-extras-split.md) | Heavy dependencies move to opt-in extras | 2026-07-01 |

## Practice

- New entries are written when a decision has real alternatives and long-term
  consequences — not for routine implementation choices.
- The working decision log lives in the maintainer's local project memory;
  entries are **promoted** here (sanitized: no session state, no test-count
  snapshots) once they prove durable. If you are reading this in a fresh
  clone, this directory plus `ARCHITECTURE.md` is the complete public record.
- Format: Status / Date / Context / Decision / Consequences (good, trade-offs,
  rejected alternatives) / Related files. See ADR-001 as the template.

# AGENTS.md — Docent MCP behavioral contract

This document defines the invariants an agent needs to call Docent tools correctly.
It is not a feature list — read the individual tool descriptions for that.

---

## 1. Calling convention

**Rule 1 — Tool names are `{tool}__{action}` with hyphens replaced by underscores.**
Example: the `sync-from-mendeley` action on the `reading` tool is `reading__sync_from_mendeley`.
All 19 tools follow this pattern; there are no exceptions.

**Rule 2 — Every result is JSON. Generator actions prepend human-readable progress lines.**
Sync actions return a single JSON object. Generator actions (e.g. `reading__sync_from_mendeley`)
return one or more `[phase] message` lines followed by a JSON object on subsequent lines.
Always parse the last JSON block — discard the progress prefix.

**Rule 3 — Invalid or missing required inputs raise a validation error, not JSON.**
Inputs are validated via Pydantic before the action runs. A missing required field returns
an error string, not a `{"ok": false}` result. Check the `inputSchema` of each tool before
calling to know which fields are required.

---

## 2. Reading queue invariants

**Rule 1 — Mendeley is the source of truth for paper metadata.**
The fields `title`, `authors`, `year`, and `doi` on a queue entry are populated from Mendeley
and cannot be changed via `reading__edit`. Editing those fields has no effect. Use
`reading__sync_from_mendeley` to refresh metadata from Mendeley.

**Rule 2 — Queue order is 1-based; `reading__next` returns the entry with the lowest order.**
Positions are contiguous integers starting at 1. `move_up`, `move_down`, and `move_to` shift
entries in-place and recompute all positions. After any move, all orders remain contiguous —
there are no gaps.

**Rule 3 — `reading__add` returns guidance text only; it does not add an entry.**
Papers enter the queue exclusively via `reading__sync_from_mendeley` (by adding them to the
configured Mendeley collection, then syncing). Calling `reading__add` tells the user how to
do this — it never mutates the queue.

---

## 3. Destructive actions

**Rule 1 — `reading__queue_clear` is a no-op without `{"yes": true}`.**
Calling it without the `yes` flag returns the queue size and a warning but clears nothing.
Always confirm the user's intent before calling with `{"yes": true}`.

**Rule 2 — `reading__done`, `reading__start`, and `reading__remove` are irreversible.**
`done` and `start` stamp an ISO timestamp (`finished`, `started`) that is never overwritten.
`remove` deletes the entry entirely. There is no undo.

**Rule 3 — All other mutations (`edit`, `set_deadline`, `move_*`) are safe and reversible.**
Re-calling them with the original values restores prior state exactly.

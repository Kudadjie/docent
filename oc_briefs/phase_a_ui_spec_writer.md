# Brief: Create /ui-spec-writer slash command

Create one file: `.claude/commands/ui-spec-writer.md`

Use the same frontmatter + markdown format as the other commands in `.claude/commands/`
(e.g. `memory-cleanup.md`, `safe-commit.md`).

---

## What the command should do

`/ui-spec-writer <tool-name>` generates a UI spec markdown document for a completed
Docent tool, suitable for handover to a designer or frontend developer.

When invoked with a tool name (e.g. `/ui-spec-writer reading`):

### Step 1 — Gather tool surface
- Inspect the tool's actions via `docent list` and `docent info <tool>` (or equivalent)
- Read the tool's result types to understand what data each action returns
- Read `AGENTS.md` for behavioral invariants

### Step 2 — Generate the spec document
Produce a markdown file at `docs/ui-specs/<tool-name>-ui-spec.md` with these sections:

1. **Overview** — one paragraph: what the tool does and who uses it
2. **Actions table** — columns: Action | Input fields | Output data | Notes
3. **Primary flows** — the 3-5 most common user journeys (e.g. "Add paper → View queue → Mark done"), described as numbered steps
4. **Result shapes** — for each action, list the Output Shape types it returns (from `to_shapes()`)
   and describe what each shape contains
5. **Edge cases & error states** — what happens when things go wrong (entry not found,
   config missing, Mendeley unavailable, etc.)
6. **Design notes** — any constraints or invariants the UI must respect
   (e.g. "order is 1-based and contiguous", "Mendeley owns title/authors/year/doi")

### Step 3 — Report
Print the path to the created file and a one-line summary of what was generated.

---

## Format for the command file

```
---
description: Generate a UI spec document for a completed Docent tool, ready for designer handover.
argument-hint: '<tool-name>'
---

<body>
```

## Constraints

- Do NOT modify any existing files
- Create `docs/ui-specs/` directory if it doesn't exist
- After creating the command file, run `uv run pytest --tb=no -q` to confirm 160 tests pass
- Brief file stays in `oc_briefs/` — no need to move it

---
name: Output Shapes deferred
description: Output Shapes vocabulary for tool returns — design discussed and accepted in principle, but explicitly deferred. Read when picking up the schema-driven UI / Phase 2 thread, or when a new tool's return type feels ad-hoc.
type: project
---

Output Shapes (typed return vocabulary for tool actions) is recognized as needed and the design is roughly settled, but **explicitly deferred** — not now. User said "sounds good but not now, save for later" on 2026-04-25 after a discussion prompted by `Interesting stuff.txt` (the Phase 2 vision doc + reviewer critique).

**Why:** Step 10 (progress streaming) is the immediate priority and is already coupled to the future UI's "Live Telemetry" pane. Adding an Output Shapes retrofit on top of Step 10 widens scope. Defer until paper-pipeline is more complete or until a second complex tool forces the issue.

**How to apply:** Don't quietly start returning typed shapes from new actions in the meantime — that creates half-retrofitted state. Continue the existing `dict | str | list` ad-hoc returns. When the user reopens this thread, the design below is the starting point — don't rebuild it from scratch.

## Starter vocabulary (7 shapes)

The principle: shapes are a **fixed vocabulary** like HTML elements — small set of types, infinite variety of content. You don't add a shape per tool; you compose existing shapes. Adding a new shape is rare and named for a *category* (e.g. `chart`), never for a tool.

| Shape         | What it carries                                  |
| ------------- | ------------------------------------------------ |
| `markdown`    | formatted prose                                  |
| `data_table`  | rows × columns                                   |
| `metric`      | key/value, often with units (counts, stats)      |
| `link`        | pointer to external resource (URL, file path)    |
| `message`     | short status string                              |
| `error`       | something failed, with reason                    |
| `progress`    | streaming event (Step 10 territory)              |

## Composition rule

A single action may return multiple shapes. Decision: **return `list[Shape]`** rendered top-to-bottom. Don't introduce a `panel` / `composite` shape unless explicit grouping (tabs, side-by-side) is later required.

## Test case worked through: research-to-notebook

If/when ported, it composes:
- `markdown` — research summary
- `data_table` — sources (title/author/date/url)
- `link` — NotebookLM notebook URL
- `progress` — streaming events while running

No new shape needed. That composition test is how to know the abstraction is working: if a new tool can't be expressed as a list of existing shapes, *that's* when you extend — for the category.

## When to revisit

Triggers to pull this off the shelf:
- **Right after Step 11 ships** (revised 2026-04-25). Paper alone has earned it: tables (search, stats), bars (scan), single-line mutations (add/done/edit), text blobs (export), and Step 11 adds the canonical "needs Output Shapes" case in `sync-status` (composite of table + warnings + summary). Don't wait for a "second tool" — paper has enough variety on its own.
- Starting any UI/FastAPI work (shapes are the wire format) — but Output Shapes should land before that.
- Reviewer critique on `Interesting stuff.txt` (Phase 2 vision doc) flagged this exact point: "Before you add any more tools, define the Shape vocabulary — even just 4-5 types covers most cases — and retrofit paper to return them."

## Correction note (2026-04-25)

The memory above (under "How to apply") said *"Continue the existing `dict | str | list` ad-hoc returns."* This was inaccurate — paper actions already return typed Pydantic models per action (`AddResult`, `MutationResult`, `SearchResult`, `StatsResult`, `ScanResult`, `ConfigShowResult`, etc.). The actual missing layer is **rendering**, not typing: today the CLI does `console.print(model)` which dumps Rich's repr (functional but ugly). Output Shapes addresses the rendering boundary — give every result a small fixed vocabulary the CLI/UI/MCP renderers can consume — not "make paper typed" (it already is).

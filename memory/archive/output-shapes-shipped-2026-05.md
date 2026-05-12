---
name: Output Shapes — shipped Phase 1.5-A (archived from output_shapes_deferred.md)
description: Original deferred-design document; preserved for historical context. The design shipped 2026-05-07. Live code is the authoritative spec.
type: project
---

**Status: SHIPPED 2026-05-07 as Phase 1.5-A.**
- `src/docent/core/shapes.py` — 7 shape types, discriminated union
- `src/docent/ui/renderers.py` — Rich dispatcher
- All 10 reading result types have `to_shapes()`
- 141 tests covered it at ship; suite at 160 after Phase 1.5-B

This document is the original deferred-design record. Archived because the design is now in the code. If you're reading this to understand the vocabulary decisions, read the source instead.

---

*(original content below — preserved for decision archaeology)*

Output Shapes (typed return vocabulary for tool actions) is recognized as needed and the design is roughly settled, but **explicitly deferred** — not now. User said "sounds good but not now, save for later" on 2026-04-25 after a discussion prompted by `Interesting stuff.txt` (the Phase 2 vision doc + reviewer critique).

**Why:** Step 10 (progress streaming) is the immediate priority and is already coupled to the future UI's "Live Telemetry" pane. Adding an Output Shapes retrofit on top of Step 10 widens scope. Defer until paper-pipeline is more complete or until a second complex tool forces the issue.

**How to apply:** The reading tool already returns typed Pydantic result models with `__rich_console__` renderers (shipped Step 11.T). What remains deferred is the `list[Shape]` *composition vocabulary* for the FastAPI/UI wire format — the layer that lets the frontend render shapes without per-tool special cases. Don't add per-tool frontend components; wait for the Shape vocabulary to land before any UI wiring. When the user reopens this thread, the design below is the starting point — don't rebuild it from scratch.

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

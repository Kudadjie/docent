---
name: Harness engineering principles
description: Reference for harness design as Docent grows. Eval harness shipped 2026-05-15. Remaining deferred items — verification loops, prompt versioning, lifecycle hooks — have live trigger conditions.
type: project
---

## What harness engineering is

The discipline of designing everything *around* an LLM call — context curation, tool design, verification loops, memory, sub-agents, prompts, hooks — rather than tuning the model. Anthropic-popularised. Core thesis: at any model capability level, harness quality determines whether you get 30% or 90% of what the model can do, and good harnesses *compound* with model upgrades.

Docent is structurally a research-oriented harness for Claude. So the frame fits the project unusually well, and most principles are already showing up by instinct.

## Principles + Docent's current state

| Principle | What it means | Status in Docent |
|---|---|---|
| **Tools as typed I/O** | Schemas + structured returns + useful error shapes teach the LLM how to use a tool | ✅ `Tool` ABC + Pydantic schemas + `MutationResult` shared shape |
| **Context as curated channel** | What the tool *sees* is a deliberate decision, not a default | ✅ Frozen `Context`, "add fields only when their step lands", no console for tools |
| **Failures as data, not exceptions** | `ok=False` returns let bulk/agent flows continue without try/except | ✅ `MutationResult.ok=False` for not-found, `added=False` for dup |
| **Memory as a designed layer** | What auto-loads vs. on-demand vs. durable is a harness choice | ✅ `RunLog` per-namespace JSONL, `memory/*.md` reorg (2026-04-25) |
| **Surface separation** | Same tool, different lens (CLI / UI / MCP / model-facing) | ✅ Pydantic-fields → flags → form-inputs uniformity |
| **Sandboxed side effects** | No shell injection, no global state | ✅ `Executor` `list[str]`-only, no `shell=True` |
| **Eval harness** | Golden sets + scoring; the difference between iterating and guessing once LLM calls land | ✅ **Shipped 2026-05-15** — `tests/golden/studio/` (2 JSON fixtures), `scorer.py` (0–1 score, 0.8 threshold), `@pytest.mark.eval` suite |
| **Verification loops act on signals** | Confidence/source fields are useful only if the workflow *uses* them (review queue, retries, gating) | ⏳ Trigger: studio pipeline exposes source quality fields — check if any consumer gates on them |
| **Prompts as first-class code** | Prompt files in repo, versioned, eval'd. No f-string burial | ⏳ Trigger: `studio/agents/*.md` prompt files exist and fire real LLM calls — add to golden eval suite before modifying any prompt |
| **Sub-agent parallelism** | Fan-out search/research; merge in main agent | ⏳ Trigger met (studio ships); formalize fan-out pattern before adding more parallel stages |
| **Lifecycle hooks** | `pre_run`/`post_run`/`on_error` as places to put logging/eval/learning | ⏳ Don't build until a *second* tool wants the same hook (premature framework otherwise) |
| **Model-facing surface design** | Tool descriptions/schemas/error messages are prompt engineering for the next LLM that calls them | ⏳ Trigger met (3+ tools exist: reading + studio + doctor); review cold-call legibility before v2.1.0 |

## Eval harness — shipped 2026-05-15

**Trigger:** the first tool whose `run()` or action makes a real `LLMClient.complete()` call with a non-trivial prompt — the `research-to-notebook` port (Phase 1.5-C) is the current forcing function. `paper add --pdf` was the original candidate but was removed in Step 11.8 (homegrown extraction ripped out; Mendeley owns metadata).

**What to build (minimum viable):**
- `tests/golden/<tool>/` directory with ~10–20 input fixtures + expected outputs
- Pytest that runs the action against each fixture and scores key fields
- Score should be a number between 0 and 1 so changes are comparable across runs
- Run on every PR / before every prompt change

**Why this is the load-bearing piece:** without it, every prompt edit, model swap, or library change is a guess. With it, you can iterate fearlessly and answer "did this help?" in seconds.

**Out of scope for the first version:** fancy frameworks (Inspect AI, Promptfoo, etc.); LLM-as-judge scoring; latency/cost benchmarks. Plain assertions on extracted fields are enough to start.

## When to revisit this file

- Before starting any step that introduces real LLM calls or fan-out (Step 5+ if it gets used; Step 10/11 for research-to-notebook).
- When you catch yourself debugging "why did it work yesterday" without an eval to answer it.
- When a third tool ships and the model-facing surface starts to feel inconsistent.

If none of those happen, leave this file alone. Speculation cost > deferred cost for everything in the ⏳ rows.

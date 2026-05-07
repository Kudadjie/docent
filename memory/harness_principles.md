---
name: Harness engineering principles + deferred eval-harness item
description: Reference for when Docent gets sophisticated enough to need formal harness work. Captures the principle set + the one concrete deferred item (eval harness on first real LLM call).
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
| **Eval harness** | Golden sets + scoring; the difference between iterating and guessing once LLM calls land | ⏳ **Deferred — see trigger below** |
| **Verification loops act on signals** | Confidence/source fields are useful only if the workflow *uses* them (review queue, retries, gating) | ⏳ Trigger when first signal field exists with no consumer |
| **Prompts as first-class code** | Prompt files in repo, versioned, eval'd. No f-string burial | ⏳ Trigger when first tool fires `LLMClient.complete()` with a non-trivial prompt |
| **Sub-agent parallelism** | Fan-out search/research; merge in main agent | ⏳ Trigger when research-to-notebook tool lands |
| **Lifecycle hooks** | `pre_run`/`post_run`/`on_error` as places to put logging/eval/learning | ⏳ Don't build until a *second* tool wants the same hook (premature framework otherwise) |
| **Model-facing surface design** | Tool descriptions/schemas/error messages are prompt engineering for the next LLM that calls them | ⏳ Review when 3+ tools exist; check whether another LLM could pick them up cold |

## Deferred concrete item: eval harness

**Trigger:** the first tool whose `run()` or action makes a real `LLMClient.complete()` call with a non-trivial prompt — likely Step 9's `paper add --pdf` (CrossRef metadata extraction or filename-fallback heuristics), or whenever else gets there first.

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

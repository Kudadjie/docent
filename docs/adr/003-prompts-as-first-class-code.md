# ADR-003: Prompts are first-class code — registry + eval hash tripwire

**Status:** Active
**Date:** 2026-05-30
**Deciders:** John David K. T. Kudadjie

---

## Context

Research quality lives in ~15 pipeline prompts — the highest-leverage,
lowest-visibility code in the project. Most were already external
`studio/agents/*.md` files, but two were buried as inline string constants in
the NotebookLM pipeline, and nothing *enforced* the rule "re-run the eval
before editing a prompt."

## Decision

1. **Single load path:** `studio/prompts.py` exposes `AGENTS_DIR`,
   `load_prompt(name)`, and `PROMPT_NAMES` (frozenset of all prompt names).
   All prompts live as `studio/agents/*.md` files; no inline prompt constants.
2. **Placeholder convention:** `.replace("{topic}", ...)` — not `.format()` —
   so prompts may contain literal braces (several hold JSON examples).
3. **Mechanical gate:** `tests/test_prompts_registry.py` enforces
   registry↔disk parity and a **hash tripwire** — a newline-normalized SHA-256
   manifest (`tests/golden/studio/prompt_hashes.json`). Editing any prompt
   fails the test with instructions to re-run the eval suite, then update the
   manifest deliberately.

## Consequences

**Good:**
- Prompts are tunable *with* an eval signal instead of by guesswork; silent
  prompt drift is impossible.
- Newline-normalized hashing keeps the manifest identical across Windows and
  Linux (CI runs Linux).

**Trade-offs:**
- Every intentional prompt edit costs an eval run + manifest update. That
  friction is the point.

**Rejected alternatives:**
- **Rely on git history:** no enforcement — the entire trigger for this
  decision was adding a gate *before* prompts get edited casually.
- **A full prompt-management framework** (Prompt class, versions, eval
  bindings): premature for ~15 prompts.

## Related

- `src/docent/bundled_plugins/studio/prompts.py`, `studio/agents/`
- `tests/test_prompts_registry.py`, `tests/golden/studio/prompt_hashes.json`
- `tests/eval_studio.py` (`-m eval`)

---
name: Codex review (2026-04-29) — pre-Step 11 takeaways
description: External Codex review of Docent before Step 11; what to act on, what to defer, sequencing options
type: project
---

External Codex review of the codebase before starting Step 11. Source: `codex_review.txt` at repo root. Codex smoke-tested version/list/info/paper add/stats/next/search and read core modules.

**Status (2026-04-30):** all three "Worth acting on" items shipped — tests (Step 10.6), `PaperQueueStore` carve-out (10.7), UI leak (10.8). See `decisions.md` for rationale. The "Pushed back on" guidance is still load-bearing as active deferral. Archive after the next-tier `paper.py` carve-out (`paper_metadata.py` + `paper_sync.py`) lands.

## Worth acting on

- **No test harness, no dev tooling in pyproject.** Biggest practical risk for a CLI that mutates files. Last session caught two Step 10.5 bugs by manual real-data testing — pytest on registry contract, RunLog, queue mutations, write_setting TOML round-trip would catch that class for free.
- **`src/docent/tools/paper.py` is the gravitational center (~750 lines).** Mixes schemas, JSON storage, CrossRef adapter, PDF parsing, prompting, progress, run logging. Every Step 11 sub-action (sync-status / sync-pull / sync-promote / sync-mendeley) piles on more. Carve out **PaperQueueStore** (persistence + state recompute) OR **MetadataResolver** (DOI → CrossRef → PDF DOI → CrossRef → PDF info → filename fallback) as the first deepening pass.
- **UI leak in tools layer:** `paper.py` imports `docent.ui` and prints inside `_require_database_dir`. Same shape as the `gotchas.md` rule "prompts can't run inside generator actions" — the boundary is already documented and already broken.

## Pushed back on (do NOT act on yet)

- **Result rendering / generic repr output (cli.py ~line 207).** Premature. Step 11 `sync-status` is the Output Shapes forcing function per CONTEXT.md — building renderers now means building them twice.
- **Eager tool discovery in `tools/__init__.py`.** Real concern eventually, irrelevant at 2 tools. Defer.
- **`.gitignore` ignoring `memory/` and `CONTEXT.md`.** Worth a separate look but orthogonal to Step 11.

## Sequencing options (pick at next session)

1. **Tests first (1–2 hrs):** add pytest + ruff to pyproject; ~5 tests covering registry contract, RunLog round-trip, queue add/scan, write_setting TOML round-trip, metadata fallback chain (with fake CrossRef adapter). Then Step 11. **Leaning this one** — cheapest insurance, respects "don't pre-build abstractions."
2. **Tests + extract one seam (half day):** option 1 plus pull JSON read/write/recompute out of `paper.py` into `PaperQueueStore`. Step 11 lands on a cleaner base, tests pin the contract.
3. **Straight to Step 11 design narration.** Accept the risk, revisit after `sync-status` ships.

**Why:** Codex's own recommendation matches the project's "don't pause Step 11 for a giant cleanup" instinct — add tests, carve out one seam, continue.
**How to apply:** Open the next session by picking 1/2/3 before any Step 11 narration. If picking 1, the queue store extraction in option 2 still needs to happen before sync-promote (which mutates the queue from a new direction) — flag it then.

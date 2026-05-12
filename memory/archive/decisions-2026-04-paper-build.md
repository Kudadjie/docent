---
name: Docent decisions log — Steps 7a–9 paper-build archive
description: Archived 2026-04-25 entries covering the multi-action contract, paper-pipeline first port (Steps 7a–9), and the data/learning/interaction conventions that came with it. Read when revisiting why the contract or paper has its current shape.
type: project
---

Archived 2026-04-25 from `memory/decisions.md`. All entries below were Active at archival and remain Active unless noted; if any get superseded or reverted, update the relevant entry back in the live `decisions.md` and link here.

---

## 2026-04-24 — Multi-action contract extension (Step 7a)
**Context:** Paper-pipeline has 16 operations on shared state; research-to-notebook has 6 modes on shared pipeline. Flat tooling would mean copy-pasting data model, atomic writes, dedup, banner logic across 16+ files per workflow.
**Decision:** Add a second path to the Tool contract. Single-action tools keep `run()` + `input_schema`. Multi-action tools declare methods with `@action(description=..., input_schema=..., name=None)`. Paths are mutually exclusive — registry enforces.
**Why:** Evidence-based (real skill shapes), not speculation. Shared helpers stay as regular methods on the Tool class — no framework features, no hooks. Maps cleanly to future UI (one card per tool; sub-actions as tabs).
**Alternatives rejected:** (1) Flat + category — leaves 16× code duplication per suite. (2) Mode-as-input-field — 6 mutually-exclusive field combinations, ugly for UI forms. (3) Nested multi-level actions — unnecessary complexity; one level deep is enough.
**Status:** Active.

## 2026-04-24 — `@action` name defaults; path mutual exclusivity
**Context:** Multi-action tool design detail.
**Decision:** Action CLI name defaults to the method name with underscores → dashes (`def ready_to_read` → `ready-to-read`). Override via `@action(name=...)`. A Tool is single-action OR multi-action, never both — registration raises `TypeError` if both are detected.
**Why:** Underscore-to-dash matches the field-name-to-flag convention. Mutual exclusivity avoids ambiguity (what does `run()` do if there are also actions?).
**Alternatives rejected:** Allow both paths on one tool — unclear semantics; worse error messages.
**Status:** Active.

## 2026-04-24 — Progress streaming deferred to Step 10
**Context:** Research-to-notebook pipelines run for minutes; paper `sync-status` walks the database. A synchronous `run() → Any` that returns after 30 min is a bad CLI and worse UI experience.
**Decision:** Do NOT add yield-event support in Step 7a. Defer to Step 10 when the first long-running tool (probably sync-status) forces the design.
**Why:** Orthogonal to multi-action. Designing the event vocabulary now would be speculation — by Step 10 we'll have real tools to inform what events the UI actually wants to render.
**Alternatives rejected:** Bundle streaming into 7a — doubles contract work up-front without evidence.
**Status:** Superseded by 2026-04-25 generator-based streaming entry in live `decisions.md` (Step 10 shipped).

## 2026-04-24 — Interaction model: skill prompts → explicit CLI flags
**Context:** Skills (like paper-pipeline) do interactive mid-operation prompts: "course?", "priority?", "Keep in Mendeley? (yes/no)".
**Decision:** Docent tools never prompt mid-run. Every choice becomes an explicit flag on the action (`--course thesis --priority high --force`).
**Why:** CLI is non-interactive by design; maps 1:1 with the future UI's form-field model.
**Alternatives rejected:** Interactive prompting in the CLI — complicates testing, doesn't translate to the web UI, blocks scripting/cron.
**Status:** Active. Applies to every ported skill. Note: Step 10.5 introduced an *action-scoped first-run prompt* for path config; that's a one-time setup prompt, not mid-operation, and respects `DOCENT_NO_INTERACTIVE`.

## 2026-04-24 — Tool data directory convention
**Context:** Skills store state at `~/.claude/skills/<name>/`. Docent can't reach in there.
**Decision:** Every tool that needs persistent state uses `~/.docent/data/<toolname>/`. Paths configurable via `Settings` fields. Never reach into `~/.claude/`.
**Why:** Clean separation; Docent state survives even if skill dirs are wiped; users can relocate via `DOCENT_HOME`.
**Alternatives rejected:** Share with skill state — couples the two systems; breaks isolation.
**Status:** Active.

## 2026-04-24 — `paper add` dedup: informative skip + `--force` to overwrite (Step 7b)
**Context:** First real action; need a dedup policy when a new add collides with an existing queue entry's derived id.
**Decision:** Default behavior is a silent non-destructive skip: return `AddResult(added=False, ...)` with the existing entry's id and title in the result, plus a message telling the user. With `--force`, replace the existing entry (queue keeps size 1, new fields win).
**Why:** Scriptable — bulk adds in a loop don't abort on dups. Informative — the caller knows whether a dup was detected. Escape hatch — `--force` covers the "yes, I meant to replace" case without a mid-run prompt (we rejected interactive prompts project-wide).
**Alternatives rejected:** Silent skip with no result info (user can't see what's already there); error by default (breaks bulk scripts); update-on-collision (conflates `add` with `edit`); append with numeric suffix (pollutes queue with phantom duplicates).
**Status:** Active.

## 2026-04-24 — Step 8 paper actions: not-found returns `ok=False`, only mutators log, BibTeX deferred
**Context:** 10 new actions on the paper tool, mix of read-only and mutators, plus integration with `docent.learning.RunLog`. Several judgment calls worth recording.
**Decision:**
1. **Not-found returns structured `MutationResult(ok=False, entry=None, message=...)` rather than raising.** Consistent with `add`'s collision pattern (returns `added=False`). Lets callers script bulk operations without try/except.
2. **Only mutators write to the run-log.** `add`, `edit`, `remove`, `done`, `ready-to-read`, `mark-keeping` log; `next`/`show`/`search`/`stats`/`export` do not. Run-log exists to inform future heuristics ("last 5 adds were --priority high"); read-only actions don't change state worth remembering. Revisit if a future heuristic actually needs read history.
3. **`export` supports `json` and `markdown` only; BibTeX deferred to Step 9.** Real BibTeX needs CrossRef-quality metadata (clean author names, normalized titles, journal/booktitle distinctions). Shipping a fake-bibtex now would be misleading. Step 9 brings CrossRef in for `add`; BibTeX export piggybacks on that.
4. **Single shared `MutationResult` schema for next/show/remove/edit/done/ready-to-read/mark-keeping.** Each carries `ok`, `id`, `entry`, `queue_size`, `banner`, `message`. Avoids 7 near-identical result classes; CLI/UI can render them uniformly.
5. **`keep_in_mendeley: bool` field added to `QueueEntry`.** `mark-keeping` flips it; Step 11's `sync-mendeley` reads it. Default `False`, backwards-compatible with existing entries.
**Why:** Each call traces directly to a build-discipline principle: structured errors over exceptions for *expected* user mistakes (matches add's contract); don't log what no consumer reads (karpathy: don't build for hypothetical needs); don't ship fake BibTeX (would tempt users to commit broken citations).
**Alternatives rejected:** Raising on not-found (breaks bulk scripting); logging read actions (no consumer); shipping skeleton BibTeX (misleads users); per-action result classes (boilerplate without payoff at this stage).
**Status:** Active. (3) was resolved at Step 9 — BibTeX still not shipped because Step 9 used deterministic CrossRef parsing rather than rebuilding the export path; revisit when a user actually wants BibTeX output. (2) still pending a heuristic consumer.

## 2026-04-24 — `docent.learning.RunLog`: JSONL, per-namespace, not on Context (Step 7c)
**Context:** Several future tools want a "what did I do recently" history (paper-pipeline auto-overrides priority/course from last-5 entries; research-to-notebook will likely want similar). Need a shared helper that's not bespoke per tool.
**Decision:** Build `docent.learning.RunLog(namespace, max_lines=50)`. Storage at `~/.docent/data/<namespace>/run-log.jsonl`. Append is one line write; tail reads last N; rollover atomically rewrites when cap is hit. Free-form dict entries; `timestamp` auto-stamped if absent. **Not** added to `Context` — tools instantiate `RunLog(self.name)` directly.
**Why:** (1) JSONL beats JSON list because append is constant-cost vs. linear-in-log-size full read-parse-write. Tail-only reads are also cheap. (2) Per-namespace storage matches the per-tool data-dir convention (2026-04-24 paper decision). (3) Not on `Context` because only paper consumes it in Step 8; promoting to Context means plumbing through CLI + every test that builds a Context, for one consumer. Tools have `self.name` already — `RunLog(self.name)` is a one-liner with no plumbing. Revisit if a second tool wants it.
**Alternatives rejected:** JSON list (linear-cost append); global cross-tool log (couples isolated tool histories; harder to clean up); Context field now (premature plumbing for one consumer); auto-override heuristics inside `learning` (per-tool concern — `learning` serves data, tools decide what to do).
**Status:** Active.

## 2026-04-24 — `paper` id derivation: `<lastname>-<year>-<first-title-word>` (Step 7b)
**Context:** The skill spec says `<firstauthor-lastname>-<year>-<first-significant-keyword>` with "significant keyword" filtering (skip stopwords like "the", "a", "of").
**Decision:** For step 7b, simplified to literal first word of title (no stopword filtering). "First author last name" is the first word of the first comma-separated author chunk, stripped to alphanumeric and lowercased. Year absent → `"nd"`.
**Why:** Step 7b is about shaking out the contract end-to-end. Stopword filtering is a tiny, additive change in step 9 when CrossRef arrives (we'll have cleaner author/title data then anyway). Karpathy simplicity-first.
**Alternatives rejected:** Full stopword filter now (speculation — we don't know which stopwords bite until we see real data); UUID-based ids (loses the human-readable property the skill relies on).
**Status:** Active. Step 9 added family-first author formatting (see live `decisions.md`) which fixed the CrossRef-derived-id bug; stopword filter still not added because no real-data dup pattern has appeared.

## 2026-04-25 — PDF reference-only (no copy); `scan` supersedes `process_inbox`; metadata fallback chain (Step 9)
**Context:** Step 9 brings PDFs into `paper add`. Two design calls: (a) does Docent copy the PDF or reference it? (b) the skill had a `process_inbox` action that walked `inbox/*.json` metadata files — what's the Docent equivalent?
**Decision:**
1. **Reference-only.** `QueueEntry.pdf_path` stores the absolute path. No copy is made. At add-time the result message embeds a "don't move/rename" warning. A `paper relink` action is deferred until a path actually breaks.
2. **`scan --folder` replaces `process_inbox`.** Walks `*.pdf` recursively and calls `add` per file. The skill's inbox/JSON-metadata flow doesn't fit Docent's PDF-driven model.
3. **Metadata fallback chain (first hit wins, explicit CLI args always override):** explicit `--doi` → CrossRef → PDF embedded DOI → CrossRef → PDF `/Title` `/Author` → filename heuristic. Each step swallows exceptions and falls through. Filename heuristic is the universal catch-all (always returns *some* title).
4. **CrossRef via `context.executor` + `curl --max-time 10`.** Anonymous User-Agent for now; add an email-bearing UA only if rate-limited.
5. **`AddResult.metadata_source: str` surfaces provenance** (`explicit | doi-crossref | pdf-doi-crossref | pdf-metadata | filename | none`) so the CLI/UI/run-log can show where data came from.
6. **`pypdf` is lazy-imported** inside `_extract_pdf_metadata` (same pattern as litellm). Verified: `pypdf` not in `sys.modules` after `from docent.cli import app`.
7. **CrossRef authors formatted family-first** (`"Kucsko G, Maurer P, ..."`) so the existing `_derive_id` (which takes the first whitespace-token of the first author chunk) lands on the surname. Without this, ids derived from CrossRef would key off the given-name initial.
**Why:** (1) Mendeley owns the canonical PDF eventually (Step 11) — Docent shouldn't be a second file manager. Copying creates annotation-drift bugs and turns a queue tracker into a storage layer. (2) `inbox/*.json` was a skill-era workaround for not having direct PDF parsing; with pypdf we go straight to the source. (3) The chain ordering favors the most reliable source (CrossRef) and falls through gracefully — caught the "PDF /Author but no /Title" edge case in smoke tests and fixed by making filename heuristic the universal floor. (4) Curl-via-executor is the same pattern Step 6 was built for; no httpx/requests needed. (5) `metadata_source` is cheap to add and saves debugging "why did it pick that title?" later.
**Alternatives rejected:** Copy-by-default (annotation drift, disk bloat, conflicts with Mendeley's role); `--copy` opt-in flag (premature speculation, no consumer); port `process_inbox` literally (the inbox-JSON shape is skill-internal); reusing `requests`/`httpx` (would pull a transitive HTTP stack into Docent for one endpoint); given-first author formatting (broke `_derive_id`).
**Status:** Active. Revisit (1) when a user actually moves a PDF and `paper relink` becomes necessary; revisit (4) UA if CrossRef rate-limits.

## 2026-04-25 — Three smoke-test bugs caught by Step 9 happy-path runs
**Context:** Step 9 smoke tests exposed real bugs the architecture review didn't catch. Worth recording as evidence that smoke tests > pure code review.
**Decision:** Document the three bugs and their root causes here, not as separate decisions:
1. **`add --doi` alone was rejected** by the "must supply title or pdf" check. Root cause: validation lagged the contract — DOI is itself a metadata source. Fix: require at least one of title/doi/pdf.
2. **`_derive_id` produced single-letter prefixes** for CrossRef-fetched papers (`g-2013-...` instead of `kucsko-2013-...`). Root cause: CrossRef returns `{given: "G", family: "Kucsko"}` and we joined them given-first. Fix: format family-first.
3. **PDFs with `/Author` but no `/Title`** got stuck — pdf-metadata path matched on author alone, blocking the filename fallback. Root cause: chain branched on "has any field" instead of "has title". Fix: filename heuristic always wins last.
**Why:** Recording these so future steps remember that the fallback chain has subtle ordering issues, and that any new metadata source must guarantee a title or fall through.
**Status:** Fixed. Tests in commit history.

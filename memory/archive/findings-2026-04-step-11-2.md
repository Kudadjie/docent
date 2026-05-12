---
name: Step 11.2 real-world test findings
description: Three sync-pull bugs found in real-world testing + design pivot to drop identifier-free paper adds; agreed direction before coding
type: project
---

User ran `paper sync-pull` against a real Mendeley-watch queue on 2026-04-30 and surfaced three bugs plus a design call. Direction agreed but not yet implemented — pick up here next session.

**Why:** the bugs are not isolated — bug #1 (Arabic paper fetched for a DOI-less entry) is the symptom of a deeper design issue (identifier-free queue entries), so the fix sequence matters.

**How to apply:** start with the three bug fixes in this order, then the design cleanup. Don't bundle them.

### Bug 1 — sync-pull on no-DOI entry fetched random Arabic paper
- Root cause: CrossRef title-search fallback in the metadata chain matches top hit with no confidence gate. Entry `unknown-nd-01` had None DOI and a filename-stub title, so the search returned garbage and we trusted it.
- Fix: (a) add fuzzy-match gate between query title and CrossRef returned title (token-set ratio ≥ 0.85 or similar); (b) if entry has neither DOI nor a confident title, sync-pull fails fast with `insufficient-identifiers`, doesn't try.

### Bug 2 — closed-access summary too terse
- `SyncPullResult` just shows "1 closed-access". User wants a one-liner suggesting institutional access (and eventually a hook for proxy/OpenAthens routing).
- Fix: message-only change in the result formatter.

### Bug 3 — open-access PDF corrupt (1KB file)
- DOI `10.3390/vehicles3040047` (fadairo-2021-a). Unpaywall almost certainly returned an HTML landing page or redirect; we wrote bytes blindly.
- Fix: validate before persist — check `Content-Type: application/pdf` AND magic bytes (`%PDF-`) on first 5 bytes. If either fails, discard and report `download-failed`. ~10 lines, prevents a whole class of silent corruption.

### Plus: `docent paper queue-clear`
- Small command, add `--yes` to skip confirm. User asked for it.

### Design pivot — drop identifier-free adds (agreed)
- Real problem isn't "manual add" — it's **identifier-free** add. The title-only fallback in the metadata chain is what let `unknown-nd-01` exist as a ghost entry that bug #1 then operated on.
- New invariant: `paper add` requires **PDF OR DOI/arXiv ID**. Kill the "title + maybe authors" path entirely. Preserves "I have a DOI but no PDF yet" use case.
- Cascade: drop title-search branch in metadata fallback chain → drop title-only add mode in CLI → tighten `QueueEntry` so rows without `pdf_path` AND without `doi/arxiv_id` can't be persisted.
- "Suggest similar / paper search" is explicitly out of scope — Scholar's job.

### Sequencing call (agreed)
Fix the three bugs + queue-clear first as one batch (small, surgical, unblocks real use). Then a separate step for the manual-add removal (touches CLI, store invariants, metadata chain — bigger blast radius, deserves its own commit + narration).

### Source
`Step 11.2 Real World Test.txt` in repo root (uncommitted, can delete after these fixes ship).

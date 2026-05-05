---
name: Reading Tool Rewrite Spec
description: Scope doc for graduating paper.py into a reading tool — domain model, actions, category structure, deadline/notification shape
type: project
---

# Reading Tool Rewrite — Scope Spec

**Status:** Planned. Tackle next session after queue is cleared.
**Why:** paper.py is a gravity well (Codex review); user scope has grown beyond papers to books + chapters; domain model (priority as string, edit exposes Mendeley-owned fields, dead BannerCounts) has real correctness debt.

---

## IN

### Rename
- Tool name: `reading` (not `paper`)
- CLI: `docent reading <action>`
- Category: `reading` (not `research`)
- Queue file: keep existing, migrate in place

### Schema changes
- Remove `migrate-to-mendeley-truth` action (one-time, already run)
- Remove `sync-pull` action (user won't use it; Mendeley handles PDF import)
- Remove `BannerCounts.db_files` and `BannerCounts.mendeley_linked` (always zero — delete or compute)
- Add `category` field: enum `course | thesis | personal` (replaces free-text; maps to Mendeley sub-collection)
- Add `course_name` field: string, only relevant when category=course (e.g. "CES701"). Populated from Mendeley sub-collection name on sync.
- Add `deadline` field: ISO date string, optional. User-settable; shown in list + triggers notifications.
- Replace `priority` string with `order` integer: position in reading queue (1 = next to read). Actions: `move-up`, `move-down`, `move-to <n>`.
- Fix: `edit` must NOT expose `title / authors / year / doi` — those are Mendeley-owned. Editable fields: `status`, `order`, `deadline`, `notes`, `tags`, `category`, `course_name`.
- Fix: `export` must apply Mendeley overlay before serialising (same as display path).

### Notifications
- At-startup check: on first `docent` invocation of the day, print any entries with `deadline` within 3 days or past due.
- Notification inbox: store seen notifications in queue store; don't repeat same alert in same day.
- Warn user on `sync` that Mendeley-owned fields (title/authors/year/doi) will be overwritten — suggest editing in Mendeley.

### Category / sub-collection sync
- On `sync`, detect Mendeley sub-collection hierarchy: parent `Courses` → child is `course_name`.
- Populate `category=course` and `course_name` automatically from sub-collection membership.
- Same pattern for `Thesis` parent → `category=thesis`.
- Anything else → `category=personal`.

### Summary field (agentic, Phase 2)
- Add `summary` field: string, optional. Machine-generated; separate from user-written `notes`.
- Populated by a future `reading enrich` action that calls OpenCode (not Anthropic API).
- `edit` must NOT expose `summary` — it's LLM-owned, same as Mendeley owns title/authors.
- Display in `list --verbose` and `show` if non-empty.
- Schema: add now. `enrich` action: deferred to after rewrite ships.

### Books support
- No schema change needed — books are just entries with no DOI.
- `notes` field is the progress field for books (e.g. "Chapters 1-3 done, reading Ch 4").
- `add` action should not require DOI; fall back gracefully to title + author if no DOI found.

### Docs
- Write user-facing docs for the `reading` tool after rewrite ships.
- UI spec sheet deferred to after docs.

---

## OUT (explicitly deferred)

- `sync-pull` (downloading PDFs via OA) — user already has PDFs via Mendeley
- `migrate-to-mendeley-truth` — already run, remove the action
- Any UI beyond CLI (web/TUI) — post-Phase 1
- Automated Mendeley API write-back (editing Mendeley from Docent) — Mendeley is source of truth; edits go there directly
- Bulk deadline import from course syllabus — future

---

## Pre-work
- Clear the current queue (`docent paper queue-clear --yes`) before starting the rewrite session.
- The rewrite is a rename + domain-model fix, not a patch. Plan to touch: `paper.py` → split into `reading_queue.py` + `reading_sync.py` + `reading_notify.py` (or similar), update registry, CLI synthesis, tests.

---
name: Paper-Pipeline Port Plan (archived)
description: Planning doc for Step 11 sync ops (11.1–11.10). All steps shipped 2026-05-02. Archived because the planning work is complete and the live decisions.md + build_progress.md are the authoritative record going forward.
type: project
archived: 2026-05-05
---

> **Archived 2026-05-05.** All Step 11 substeps (11.1–11.10) shipped. Rationale for each sub-step lives in `decisions.md` (2026-04-30 through 2026-05-02 entries). Build status lives in `build_progress.md`. This file is preserved as a historical record of the original plan and the Mendeley-as-truth pivot.

---

Steps 7a–10.5 are done — see `build_progress.md` for the checklist and `archive/decisions-2026-04-paper-build.md` for the rationale behind contract + paper choices already made. This file is now scoped to Step 11 and the skill-side facts that survive the port.

## Step 11 plan — sync ops + minimal MCP adapter

Four actions to add to `PaperPipeline`. Order is from least-Mendeley-coupled to most:

1. **`sync-status`** — ✅ **Shipped 2026-04-30 (Step 11.1) as single-shot, local-only.** Two deviations from the original plan, see `decisions.md` 2026-04-30: (a) non-generator (sub-100ms with no slow phase; revisit when one lands), (b) no Semantic Scholar batching (deferred to a `--identify-orphans` flag). Buckets: `in_queue_with_file` / `in_queue_missing_file` / `orphan_pdfs` / `promotable` / `in_watch`. Promoted-state detected by Watch-filename match — `promoted_at` field deferred to Step 11.3. Result is a plain `SyncStatusResult` BaseModel; no renderer abstraction. The "Output Shapes forcing function" framing was abandoned (codex agreed; user pushed back).
2. **`sync-pull`** — ✅ **Shipped 2026-04-30 (Step 11.2) as generator action.** Two-stage chain: DOI direct → Unpaywall; or CrossRef bibliographic title-search resolves DOI first (resolved DOI persisted on entry) → Unpaywall. New required `paper.unpaywall_email` config (hard-fail with `config-set` instructions, not first-run prompt). Closed-access entries surface `doi_url` + `journal` in the `no_oa` bucket so user can route to institutional access. In-place queue mutation tracked by `mutated_ids` set, reconciled against fresh load before save. See `decisions.md` 2026-04-30 entry for full rationale + alternatives rejected. **Real-data validated 2026-04-30.** Three bugs fixed post-validation (CrossRef title-match, institutional-access hint, PDF magic-byte) — see `archive/findings-2026-04-step-11-2.md`.
3. **`sync-promote`** — ✅ **Shipped 2026-05-01 (Step 11.3) as generator action. Retired in Step 11.9.** **Move, not copy** — DB → Watch via `shutil.move`; user preference for no duplicate PDFs (see `decisions.md` 2026-05-01 entry; supersedes the copy half of the 2026-04-25 watch-cleanup decision). Auto-mode targets entries with `keep_in_mendeley=True` + has-file + `promoted_at is None` + filename not already in Watch. New `QueueEntry.promoted_at` field. Two heal branches handle inconsistent prior state. Collisions hard-fail. Real-data validated.
4. **`sync-mendeley`** — ✅ **Shipped 2026-05-01 (Step 11.4). Retired in Step 11.9** (subsumed by `sync-from-mendeley`). Was a pure read/cross-check that called Mendeley MCP to populate `mendeley_id` on promoted entries.

**MCP adapter (minimal):** Step 11 only needs to *call* Mendeley MCP from inside Docent (Docent as MCP client). Full bidirectional adapter (Docent tools exposed as MCP server) is Step 13.

## Skill paths (reference only — DO NOT reach into these from Docent)

- Skill root: `C:\Users\DELL\.claude\skills\paper-pipeline\`
- Database: `C:\Users\DELL\Desktop\Paper Database\` (user-configured via `paper.database_dir` since Step 10.5)
- Watch folder: retired in Step 11.9 — `database_dir` IS the Mendeley watch folder now
- Docent's own state: `~/.docent/data/paper/` (queue.json, queue-index.json, state.json — owned by Docent)

## External dependencies Step 11 pulled in

- **CrossRef** — already in (Step 9, via curl).
- **Unpaywall** — added for `sync-pull`. REST API, anonymous works for low volume; `curl --max-time 10` pattern reuses Step 6's executor convention.
- **Semantic Scholar batch API** — planned but deferred; never landed.
- **Mendeley MCP** — added for `sync-mendeley` (Step 11.4). In-process MCP client via official `mcp` SDK. Harness (`mendeley_client.py`) survives; the caller actions (`sync-mendeley`, `sync-promote`) were retired in Step 11.9.
- **pypdf** — added in Step 9, dropped in Step 11.8 (Mendeley owns PDF metadata now; homegrown extraction retired).

## Things deferred (as of Step 11 completion)

- **`paper relink`** — when a tracked PDF moves and breaks `pdf_path`. Deferred; field itself removed in Step 11.10.
- **`paper clean-watch`** — retired concept; watch-folder (`mendeley_watch_subdir`) removed in Step 11.9. `database_dir` is the watch folder now; Mendeley handles import.
- **BibTeX export** — needs CrossRef-clean metadata. Still deferred.
- **Stopword filter in `_derive_id`** — not needed yet.
- **CrossRef email-bearing User-Agent** — only if rate-limited.

---

## Step 11.6+ — Mendeley-as-truth pivot (approved 2026-05-01)

### Why we pivoted

Step 11.5 shipped (page-cap bump, font-size title heuristic, fuzzy-guarded CrossRef title-search) and **failed real-data validation hard**: most PDFs got author lists used as the title; some concatenated section headings + authors. Meanwhile, dropping the same PDFs into Mendeley produced clean metadata for every one. The lesson is decisive: **Mendeley already solves PDF metadata extraction; us writing heuristics is a losing strategy.** Rather than iterate on font-size + extra heuristics, we let Mendeley be the metadata oracle and shrink docent to a workflow layer on top of it.

### New architecture

- **Single watch folder.** `database_dir` IS the Mendeley watch folder. `mendeley_watch_subdir` is removed. Drop a PDF in `database_dir` → Mendeley auto-imports + extracts metadata (async, ~30s–several min — accepted).
- **Mendeley owns metadata.** `title`, `authors`, `year`, `doi`, `abstract` are read fresh from Mendeley on demand (with short-TTL cache for `next` / `stats` UX). They are no longer stored in `queue.json`.
- **Collection defines queue membership.** The user maintains a `Docent-Queue` collection in the Mendeley app and drags papers they intend to read into it. `paper next/show/stats/search` operate on `mendeley_list_documents(folder=<configured queue collection>)`.
- **Sidecar holds docent-only workflow state.** `queue.json` shrinks to `{mendeley_id, status, priority, course, notes, added, started, finished}` — keyed on `mendeley_id`. Anything Mendeley owns is dropped.
- **Course = docent-side field, not nested Mendeley collection.**

### MCP capability constraints (load-bearing)

The Mendeley MCP exposes 7 tools: `mendeley_search_library`, `mendeley_get_document`, `mendeley_list_documents` (filterable by folder), `mendeley_list_folders`, `mendeley_search_catalog`, `mendeley_get_by_doi`, `mendeley_add_document`. **There is no tool for creating folders, moving documents between folders, or editing tags.** All collection management happens in the Mendeley desktop app. Docent reads collection state; never writes it.

### Steps executed

1. **Step 11.6 — `sync-from-mendeley`** ✅ Shipped 2026-05-02.
2. **Step 11.7 — Read-through metadata cache** ✅ Shipped 2026-05-02. File-backed (not in-process — across-CLI persistence is the whole point). TTL 300s for documents, 24h for folder-id map.
3. **Step 11.8 — Rip out homegrown extraction + collapse `add`** ✅ Shipped 2026-05-02. Deleted `paper_metadata.py` + `tests/test_metadata_resolver.py`. Dropped `pypdf`. `paper add` is now a guidance shim or `--mendeley-id` upsert.
4. **Step 11.9 — Collapse `mendeley_watch_subdir` + retire `sync-promote` + `sync-mendeley`** ✅ Shipped 2026-05-02 (commit `6e6a155`).
5. **Step 11.10 — Sidecar migration** ✅ Shipped 2026-05-02 (commit `b7d5e77`). `paper migrate-to-mendeley-truth [--yes]` wipes old schema; user ran it against live queue — clean.

### What survives from original Step 11

- `mendeley_client.py` MCP harness + lazy SDK import + sync-facade pattern (Step 11.4).
- `sync-pull` (Unpaywall OA download) — orthogonal to metadata; still useful when a queue entry has DOI but no PDF.
- `paper config-show` / `config-set` / first-run prompt scaffolding (Step 10.5).
- `RunLog` integration (Step 7c).
- The progress-event + generator-action pattern (Step 10).

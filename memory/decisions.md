---
name: Docent decisions log
description: Append-only architectural-decision record; read when asking "why did we choose X" or when a new call needs its own entry
type: project
---

Append-only. Newest at the bottom. One entry per architectural call where alternatives were considered. Format:

```
## YYYY-MM-DD — Short title
**Context:** one or two lines on the situation
**Decision:** the chosen path
**Why:** the reasoning
**Alternatives rejected:** what we didn't do and why
**Status:** Active | Superseded by <link> | Reverted
```

**Archived:**
- Steps 1–6 foundation (2026-04-23) → `archive/decisions-2026-04-foundation.md`
- Steps 7a–9 paper-build + contract conventions (2026-04-24/25) → `archive/decisions-2026-04-paper-build.md`

Live entries below cover the most recent work; older active decisions are still authoritative in the archives — read those when revisiting why the contract or paper has its current shape.

---

## 2026-04-25 — Step 10 progress streaming via generator + return-value
**Context:** `paper scan` is mildly long-running today; Step 11 `sync-status` will be worse (walks the whole database, batches Semantic Scholar, checks Mendeley). The single-shot `run() -> Result` contract goes silent during the wait. Need to extend the Tool/action contract so an action can yield events while running, without breaking single-action or existing multi-action shapes.
**Decision:**
1. **Generator-based streaming.** A multi-action method that wants to stream becomes a generator: `yield ProgressEvent(...)` zero or more times, then `return Result`. The CLI dispatcher detects via `inspect.isgenerator(...)` and drives it; non-generator actions take the existing path unchanged.
2. **Final result via `StopIteration.value`,** not a sentinel event. Keeps event types and result types disjoint; matches Python coroutine idiom; composes via `result = yield from sub_action(...)` later.
3. **Single `ProgressEvent` shape** (`phase`, `message`, `current`, `total`, `item`, `level`). No event subclasses. Renderer rules: `(current, total)` drives a Rich `Progress` bar; phase change swaps the task; `level=warn|error` prints a console line; events without total/message are ignored visually.
4. **Migrated only `paper scan`.** No retrofit of other actions. `sync-status` is the next forcing function (Step 11).
**Why:** (Generator over callback) action stays data-shaped, no UI coupling on Context, trivial to test (collect into list). (Generator over event bus) one CLI consumer per process — bus is overpowered. (`StopIteration.value` over final-yield sentinel) clean type disjointness, future `yield from` composition. (Single shape) speculative subclasses without consumers; can split when reality demands. (Migrate only `scan`) every other action is sub-second.
**Alternatives rejected:** Callback `context.progress(...)` — couples Context to UI, hides streaming from the type signature, harder to test. Event bus / pub-sub — premature for one consumer. Async generators — sync is enough until MCP needs it. Event subclass hierarchy — speculative.
**Status:** Active.

## 2026-04-25 — Step 10.5: paper config (database_dir + mendeley_watch_subdir)
**Context:** Step 11's sync ops need a stable answer to "where's the database?" without taking it as a flag every call. Don't impose a Docent-private folder (would force duplication of user's existing library and fight Mendeley for ownership). Don't prompt on every command (hostile UX). Today the user already has a Paper Database folder with a Mendeley Watch subfolder inside.
**Decision:**
1. **Two settings under nested `paper.*` block on Settings:** `database_dir: Path | None`, `mendeley_watch_subdir: str | None` (relative path inside database). Env-overridable as `DOCENT_PAPER__<KEY>` via pydantic-settings `env_nested_delimiter="__"`.
2. **`mendeley_watch_subdir` is relative, validated at set-time.** Encodes the structural truth that Watch lives inside the database; rejects absolute paths with a clear message.
3. **Two actions, `config-show` and `config-set`,** rather than one cleverly-dispatching `config` action. Multi-action contract is exactly the right shape for "small set of related ops."
4. **First-run prompt is action-scoped, not startup-scoped.** When an action needs `database_dir` and it's unset, `_require_database_dir` prompts once, persists via `write_setting`, mutates in-memory settings for this run. `DOCENT_NO_INTERACTIVE=1` raises `NoInteractiveError` instead of prompting (CI escape hatch).
5. **TOML round-trip writes via `tomli_w`** (new dep). Single source-of-truth file at `~/.docent/config.toml`.
6. **`paper.PaperSettings` is a typed nested model on Settings,** not stuffed into the existing `tools: dict` field. The dict is for Step-12 plugin-discovery free-form config; first-party tools get typed nested settings.
7. **`scan --folder` becomes optional;** falls back to configured database, then to first-run prompt.
**Why:** (Typed model over dict) env override + type safety, sets precedent for future first-party tools. (Relative subdir) prevents misconfiguring Watch as a path with no relationship to database. (Action-scoped prompt) avoids polluting non-paper commands. (NO_INTERACTIVE escape) honest contract for CI/scripts. (`write_setting` over manual TOML edit) one-step config = the whole point of having `config-set`.
**Alternatives rejected:** Stuff `paper` settings into existing `tools: dict[str, dict]` — loses type safety, no env-nested-delimiter support for arbitrary dict keys, blurs first-party vs plugin line. Two absolute paths (database + watch) — would let users misconfigure them as unrelated. Startup-time prompt — bad UX for non-paper commands. `.env` file alongside TOML — two-file complexity for no benefit. Manual TOML serializer — brittle for one save of dependency cost.
**Status:** Active.


## 2026-04-29 — Step 10.6: pytest harness (pre-Step 11 insurance)
**Context:** Codex review (`memory/archive/codex-review-2026-04-29.md`) flagged the absence of a test harness as the biggest practical risk before Step 11, which adds four new sync actions that mutate the queue + filesystem from new angles. Step 10.5 caught two real bugs only by manual real-data testing. Need cheap, fast unit tests that pin current behavior without pre-committing to abstractions.
**Decision:**
1. **pytest only**, via `[dependency-groups] dev` (PEP 735); `[tool.uv] default-groups = ["dev"]` so `uv run pytest` just works without an explicit `--group` flag.
2. **Six test files, ~30 unit tests, all using `tmp_path` + a `tmp_docent_home` fixture** that redirects `~/.docent` via the existing `DOCENT_HOME` env var. No mocks of internal state — point the env var at tmp and let `paths.root_dir()` do the work.
3. **`isolated_registry` fixture snapshots `_REGISTRY`** so tests calling `@register_tool` don't leak into subsequent tests.
4. **Mock the metadata fallback chain at the seam between resolver and adapters** (`_crossref_lookup`, `_extract_pdf_metadata`) — never hit CrossRef, never read a real PDF. Tests assert the chain logic only; adapter correctness is for real-data validation.
5. **Real bug surfaced by tests, then fixed in same step:** `_filename_heuristic` regex `\b(?:19|20)\d{2}\b` failed on underscore-separated filenames (`Smith_2019_topic`) because `_` is a Python word char. Fix: run the year regex against the *normalized* title (`re.sub(r"[_\-]+", " ", stem)`) instead of the raw stem. Mendeley exports use underscores universally — the test (`test_filename_fallback_underscore_separated`) now positively asserts `year=2019`.
**Why:** (pytest only, no ruff) ruff would force a fix-up pass on existing code unrelated to Step 11; defer to its own micro-step. (`tmp_docent_home` over monkeypatching `paths`) the env var is the public-facing isolation knob; using it tests the same path real users use. (Mock at seam, not at network) keeps tests under 1 second total, removes flakiness, decouples from CrossRef availability. (Fix the underscore bug in this step) one-line change in the same regex, surfaced by the same suite — splitting it across steps adds bookkeeping with no upside.
**Alternatives rejected:** ruff in same step (scope creep into unrelated code style fixes). Typer `CliRunner` integration tests (haven't seen a bug only catchable end-to-end yet; cost/value bad). Real CrossRef integration test (network flake, 1-2s slowdown per run). pytest-cov + coverage gate (premature; first job is having tests at all). Refactoring `paper.py` to be more testable (that's option 2 from the Codex memo; explicitly skipped).
**Status:** Active. Suite runs in ~0.6s; 30/30 green. (PaperQueueStore carve-out shipped in Step 10.7.)

## 2026-04-29 — Step 10.7: PaperQueueStore extraction
**Context:** Codex review (`memory/archive/codex-review-2026-04-29.md`, option 2) recommended carving out `PaperQueueStore` (persistence + state recompute) before Step 11 lands `sync-promote`, which mutates the queue from a new direction (`keep_in_mendeley` flag, future `watch_files` / `mendeley_linked` counts). `paper.py` had grown to ~890 lines mixing schemas, JSON storage, the metadata fallback chain, the prompting layer, progress events, and run-logging. State-recompute zeros out three filesystem-derived fields today; Step 11 needs to populate them without scattering filesystem-walk logic across each new sync action.
**Decision:**
1. **Instance-bearing class** `PaperQueueStore(root: Path)` with public methods `load_queue` / `load_index` / `save_queue` / `banner_counts`. `PaperPipeline.__init__` constructs `self._store = PaperQueueStore(data_dir() / "paper")` once.
2. **Self-initializing on write** — `save_queue` does `root.mkdir(parents=True, exist_ok=True)` and atomic-renames each JSON file. Reads return `[]` / `{}` / `BannerCounts()` on missing files. The old `_ensure_dirs` (which seeded empty files at action entry) is gone — same end state via lazy defaults + write-time mkdir.
3. **`BannerCounts` schema moved into `paper_store.py`** (it's the state-file shape, owned by the store). `paper.py` re-imports it for use in result models.
4. **`_find_entry`, `_set_status`, `_not_found`, `_log_event`, `_derive_id`, metadata helpers stay in `paper.py`** — they're action-shaped, not persistence-shaped. Same with `_require_database_dir` (UI/prompt; will be its own future micro-step).
5. **State-recompute interface unchanged for now.** `_write_state` still hard-codes `db_files=0`, `watch_files=0`, `mendeley_linked=0`. Step 11 will add an explicit method (`update_filesystem_counts(...)` or similar) when sync-status needs to populate them. Not pre-building.
**Why:** (Instance class over module-level functions) `data_dir` would otherwise thread through every call site (~25), no real win. (Self-init on write) eliminates the "did somebody remember to call _ensure_dirs?" footgun and matches the lazy-default behavior the read methods already had. (BannerCounts in store, QueueEntry in paper.py) BannerCounts is state-file shape; QueueEntry is action-result domain. Owners differ. (Don't pre-build sync hooks) we don't yet know whether sync ops want a single `update_filesystem_counts` call or piecewise increments — wait for the call site to demand a shape.
**Alternatives rejected:** Pure functions in a `paper_persistence.py` module — worse ergonomics, threads `data_dir` through every call. Move `_resolve_metadata` into the same store carve-out — different concern (network/PDF I/O vs filesystem persistence); separate future split. Bundle the `_require_database_dir` UI-leak fix into this step — would expand scope and the fix shape depends on how the prompt layer wants to be tested. Keep `_ensure_dirs` to seed empty files — pointless writes; reads handle missing fine.
**Status:** Active. Suite at 37 tests, ~0.6s; `paper.py` 887 → 799 LOC.


## 2026-04-30 — Step 10.8: UI-leak cleanup in `_require_database_dir`
**Context:** Codex review (`memory/codex_review_2026_04_29.md`) flagged `paper.py` importing `docent.ui` and calling `get_console().print(...)` directly inside `_require_database_dir`. Layering violation: tools should return data, the CLI should render. Step 10.7 explicitly deferred this fix because the fix shape depended on how the prompt layer wanted to be tested.
**Decision:** Change `_require_database_dir` signature to `tuple[Path | None, str | None]` — `(path, None)` on success, `(None, None)` on user cancel, `(None, error_message)` on invalid input (typed-path-doesn't-exist). The sole caller (`_resolve_scan_folder`) folds the error message into `ScanResult.message`. Drop `from docent.ui import get_console`. New `tests/test_database_dir.py` with 2 tests covering the configured-path and invalid-path branches.
**Why:** (Tuple return over typed exception) one call site doesn't justify a new exception class; tuple keeps everything inline. (Plain text over Rich markup in the error message) result models render via default Pydantic repr — markup like `[yellow]...[/]` would print as literal text. Accepts a tiny cosmetic regression on the rare typo path in exchange for removing the layering violation. (No `console_messages: list[str]` field on ScanResult / no renderer abstraction) premature; codex agreed and the user pushed back on rendering cleanup as a forcing function.
**Alternatives rejected:** New `InvalidDatabaseDir` exception — boilerplate for one call site. Add a `messages: list[str]` field to all result models so tools can attach UI hints — speculative; no second consumer. Migrate ScanResult to a custom Rich renderer that interprets markup — expands scope, kicks the renderer-abstraction question right back open.
**Status:** Active. Suite 37 → 39 green.

## 2026-04-30 — Step 11.1: ship `sync-status` non-generator + local-only
**Context:** `paper_pipeline_port_plan.md` originally specified `sync-status` as a generator action with three phases (`walk` / `scholar` / `compare`) — Semantic Scholar batching to identify orphan PDFs being the slow phase justifying the streaming. The plan also called sync-status the "Output Shapes forcing function." But the user already pushed back on rendering cleanup as premature (CONTEXT.md, codex review), and the local cross-tab is what ships actionable value to the user — Semantic Scholar identification is QoL on top.
**Decision:**
1. **Single-shot action, not generator,** for the first cut. With no slow phase, the local cross-tab is sub-100ms even on libraries of a few hundred PDFs.
2. **Local-only buckets:** `in_queue_with_file` / `in_queue_missing_file` / `orphan_pdfs` (under `database_dir` minus `mendeley_watch_subdir`) / `promotable` (`keep_in_mendeley=True` + file present + name not in Watch) / `in_watch`. Plus `summary` line, resolved paths, and a `message` field for unconfigured-database early-exit.
3. **No Semantic Scholar orphan identification.** Add as `sync-status --identify-orphans` later when forced.
4. **Promoted-state detection by Watch-folder filename match,** not by a `promoted_at` field. Avoids a schema change before `sync-promote` actually exists; entries already in Watch fall out of `promotable` automatically. `sync-promote` will add the field.
5. **`PaperQueueStore.list_database_pdfs(database_dir, watch_subdir)` static method** — pure function returning `(db_pdfs, watch_pdfs)`. The filesystem-counts hook the 10.7 decision flagged. Static (not instance) because it operates on the user's database, not the store's `self.root`.
6. **`SyncStatusResult` is a plain pydantic BaseModel with default repr.** No renderer abstraction.
7. **Sub-stepped Step 11** into 11.1 (sync-status), 11.2 (sync-pull), 11.3 (sync-promote), 11.4 (sync-mendeley + MCP). MCP-client wiring shape stays undecided until 11.4 actually demands it.
**Why:** (Single-shot over generator) every feature deferred is one we didn't build wrong; the streaming shape was justified only by the slow phase, and we're not shipping the slow phase. Migrating sync-status to a generator later is a 10-minute mechanical change once a slow phase exists. (Local-only over Semantic Scholar) the actionable output is the cross-tab; identification is icing. (Watch-filename match over `promoted_at`) zero schema churn now; `sync-promote` will add the field as part of its own design. (Static method on store over module function) keeps filesystem operations colocated with persistence in `paper_store.py`. (Default repr over renderer abstraction) codex flagged premature; user agreed.
**Alternatives rejected:** Generator with `walk` + `compare` phases anyway — speculative streaming for a sub-100ms op. Semantic Scholar in first cut — half a session of HTTP/batching/rate-limit work for a non-load-bearing feature. Add `promoted_at` field now — schema change without the consumer that needs it. Custom Rich renderer for `SyncStatusResult` — kicks the renderer-abstraction question open without forcing function.
**Status:** Active. Real-data validated against user's Paper Database (5 matched, 2 missing surfaced as actionable). Suite 39 → 47 tests, ~0.9s. Deferred: Semantic Scholar identification, generator migration, `.index.json` hash cache.

---

## 2026-04-30 — Step 11.2 sync-pull design (Unpaywall + CrossRef title fallback)
**Context:** Queue often holds entries with metadata but no PDF (added by DOI, or by title from a search). Step 11.2 needs to fetch open-access copies into `database_dir` so they show up as `in_queue_with_file` in sync-status. Closed-access papers are common; user may have institutional access via student email.
**Decision:**
1. **Generator-based action** (unlike sync-status) — Unpaywall + download is genuinely slow per entry; per-DOI `ProgressEvent` is justified.
2. **Two-stage chain**: if entry has DOI → Unpaywall directly; if not → CrossRef bibliographic title search resolves DOI first, then Unpaywall. Resolved DOI is persisted on the entry.
3. **`unpaywall_email` is a hard-required config.** Hard-fail with `paper config-set unpaywall_email <addr>` instructions instead of wiring up the Step 10.5 first-run prompt. Cheaper coupling; one-line setup.
4. **No PDF validation beyond curl exit-code + non-empty file.** No magic-byte sniff, no pypdf open. Add only after real-data testing reveals publishers handing back paywall-HTML.
5. **Closed-access surfaces `doi_url` + `journal`** in the `no_oa` bucket so the user can click through and check institutional access. No "detect institutional access" logic, no auto-open in browser, no caching the URL on the entry (derivable from DOI).
6. **In-place queue mutation tracked by `mutated_ids` set** — load fresh queue at end, reconcile by id, save once. Avoids over-writing on dry-run, avoids relying on dict-identity between `targets` and a freshly loaded queue.
7. **Filename convention `{id}.pdf`** in `database_dir` — matches the canonical handle, plays naturally with `sync-status` orphan detection (the file becomes `in_queue_with_file` once `pdf_path` is set).
8. **Filtering rule for auto-mode**: only entries where pdf_path missing OR pointed file doesn't exist. `--id` mode bypasses this filter so users can force-retry an entry that already has a file recorded.
**Why:** (Generator over single-shot) network is the exact case the streaming primitive exists for. (Title fallback included) user explicitly asked; cost is one extra helper. (Hard-fail on email) Unpaywall ToS requires a real address — prompting machinery would land us with a fake-default. (No magic-byte sniff) speculation; codify only when data forces it. (Mutated-ids set) caught a bug-shaped pattern in the first draft where dry-run could trigger persistence based on pre-existing `doi` keys.
**Alternatives rejected:** Title search via Semantic Scholar (different rate-limit regime, different match quality — CrossRef is already in the codebase). Sci-Hub fallback (legal/ethical scope outside the project's lane). Automatic browser-open on `no_oa` (intrusive in headless/SSH). Concurrent downloads (rate-limit complexity for negligible UX gain at <50 entries). Per-entry retry loop (premature; rerun is free).
**Status:** Active. Suite 47 → 56 tests, ~1.4s. Real-data validation pending — needs a queued entry with a known-OA DOI + Unpaywall account.
**Validation (2026-04-30):** Confirmed — OA DOI queued, sync-pull wrote a real PDF. Three edge-case bugs fixed post-validation (CrossRef fuzzy guard, institutional-access hint, PDF magic-byte check); re-validated after both fix batches. Suite 65 → 63 green (net: −3 obsolete + 1 new).

---

## 2026-05-01 — Pivot to Mendeley as metadata source of truth

**Context:** Step 11.5 shipped three improvements to PDF metadata extraction (page-cap 5→20 for DOI scan, font-size title heuristic on page 1, fuzzy-guarded CrossRef title-search). Real-data validation against the user's Paper Database failed badly: most PDFs ended up with the author list as the title; some concatenated section headings with author lists. Meanwhile, dropping the same PDFs into Mendeley produced clean metadata for every paper. The hard signal: Mendeley already does this job perfectly; us writing heuristics is a losing strategy.
**Decision:** Pivot the architecture so Mendeley owns metadata and docent is a thin workflow layer on top.
1. **Single watch folder.** `database_dir` IS the Mendeley watch folder; `mendeley_watch_subdir` retired. Drop a PDF in `database_dir` → Mendeley auto-imports + extracts.
2. **Mendeley owns metadata.** `title`/`authors`/`year`/`doi`/`abstract` read fresh from Mendeley on demand (with short-TTL in-process cache for `next`/`stats` UX). Not snapshotted into `queue.json`.
3. **Collection defines queue membership.** User maintains a `Docent-Queue` collection in the Mendeley app and drags papers into it. `paper next/show/stats/search` operate on `mendeley_list_documents(folder=<queue collection>)`. New `paper.queue_collection` setting.
4. **Sidecar for docent state only.** `queue.json` shrinks to `{mendeley_id, status, priority, course, notes, added, started, finished}` keyed on `mendeley_id`. Mendeley-owned fields removed.
5. **Course = docent-side field, not nested Mendeley collection.** Simpler; doesn't depend on `mendeley_list_folders` returning hierarchy. Revisit if real use feels backwards.
6. **What gets retired:** `paper_metadata.py` extraction logic (Step 9 + 11.5), `sync-promote` action + `move_to_watch` (Step 11.3), `sync-mendeley` action (Step 11.4 — subsumed by `sync-from-mendeley`), `pypdf` dep, `mendeley_watch_subdir` setting, `QueueEntry.{promoted_at, pdf_path, file_status, title_is_filename_stub}`. Roughly half of Step 11's shipped code.
7. **What survives:** `mendeley_client.py` MCP harness (Step 11.4 in-process SDK decision is unchanged), `sync-pull` (orthogonal to metadata; still useful for OA download by DOI), config + first-run scaffolding (Step 10.5), RunLog (7c), generator-action pattern (Step 10).
**Why:** Mendeley has 15 years of PDF metadata heuristics + a global catalog; we cannot beat it with regex + font-size tricks. Real-data signal was unambiguous. The MCP exposes 7 read tools (`mendeley_list_folders`, `mendeley_list_documents(folder=...)`, `mendeley_get_document`, etc.); collection-as-queue is directly supported. The "drag-into-collection" UI step sounds like a UX cost but is actually how Mendeley users already triage — not a new burden. Throwing away half of Step 11 is honest accounting: it was solving the wrong problem. The pivot collapses architecture (one folder, one source of truth) and removes our worst liability (homegrown metadata extraction).
**Alternatives rejected:**
- **Iterate on font-size heuristic + add author-block parsing.** Was the obvious next step; rejected because the failure mode (heading + authors mashed into title) shows the underlying problem is structural — there's no single layout signal that survives across journals. Mendeley fights this battle with heuristics + a global catalog; we'd need both.
- **Hybrid (docent owns queue, polls Mendeley for metadata after a `paper add --pdf`).** Avoids the manual collection-drag step but requires fragile filename/title matching to figure out which Mendeley doc corresponds to the just-dropped PDF. The MCP doesn't expose "find the doc with file path X." Rejected on matching fragility + 5s polling latency.
- **DOI-only adds (Option C from the plan).** Would work but kills the "drop a PDF and forget" flow the user actually wants. The whole point of having a PDF database is dropping PDFs in.
- **Mendeley collections for course distinction (nested `Docent-Queue/CIVE-501`).** Confirmed Mendeley supports nesting and the user is willing — but pushes a UI bottleneck (drag to right child collection every time) for marginal benefit over a `--course` flag. Defer; revisit if real use proves it.
- **Keep `sync-mendeley` as separate from `sync-from-mendeley`.** No reason to split: every queue entry is keyed on `mendeley_id`, so the linking step is the same as the discovery step. Merging is the simplification the new architecture invites.
**Status:** Approved 2026-05-01. Detailed step list (11.6 sync-from-mendeley → 11.7 read-through cache → 11.8 rip out extraction → 11.9 collapse watch-subdir/sync-promote/sync-mendeley → 11.10 sidecar migration) lives in `paper_pipeline_port_plan.md` under "Step 11.6+ — Mendeley-as-truth pivot." Step 11.5 work (page-cap, font-size title, title-search) reverted-in-spirit; code stays in tree until Step 11.8 deletion lands so we have one clean diff. Step 11.6 shipped 2026-05-02 (first concrete pivot code).

## 2026-05-02 — Step 11.6 — sync-from-mendeley shape + scope-narrowing + folder_id-not-name

**Context:** First concrete code in the 2026-05-01 Mendeley-as-truth pivot. The plan paired 11.6 (sync action) with 11.7 (read-through cache) and I'd initially proposed bundling them ("11.6 unusable without the cache"). On reading the actual MCP response, that framing was wrong: `mendeley_list_documents` returns title/authors/year/identifiers per doc for free, so 11.6 can snapshot them at creation time and existing `next`/`show`/`stats`/`search` keep working unchanged — no cache required to ship a useful 11.6. Three calls had to be made: scope of this PR, folder name vs id, and how to handle the new sidecar-vs-legacy QueueEntry shape.
**Decision:**
1. **Narrow scope to 11.6 only.** Snapshot title/authors/year/doi from the `list_documents` payload onto new entries; defer `MendeleyCache` + rewiring `next`/`show`/`stats`/`search` to read-through to a real 11.7. Building cache scaffolding without a consumer is the kind of speculation karpathy-guidelines warn against.
2. **Folder name → folder_id resolution via `list_folders` first.** Live MCP probe revealed `mendeley_list_documents(folder_id=..., limit=50, sort_by=...)` takes a `folder_id`, not a name. So `sync-from-mendeley` makes two MCP calls per run: one `list_folders` (filter to `name == queue_collection`), then `list_documents(folder_id=...)`. Bumped default limit from MCP's 50 to 200 — a reading queue can plausibly hold that many.
3. **Three error/ambiguity paths surfaced as `message` early-exits:** missing collection (with create-it-in-Mendeley hint), >1 collection sharing the configured name (asks user to rename — Mendeley supports nested folders sharing names across parents), and `list_folders` / `list_documents` transport/auth errors (reused `_mendeley_failure_hint` from Step 11.4).
4. **Validator relax: `_require_pdf_or_doi` → `_require_identifier`.** `mendeley_id` is now a third valid identifier alongside `pdf_path` and `doi`. Mendeley-keyed entries created by sync-from-mendeley don't always have a DOI (live data confirms — many real entries return `identifiers: null`), and `mendeley_id` itself is a stable, definitive identifier — the original Step 11.2 invariant ("identifier-free entries cause sync-pull to fetch random papers") still holds because random papers can't be Mendeley docs.
5. **Snapshot strategy is write-only / fallback-only.** `_build_entry_from_mendeley` snapshots title/authors/year/doi from the payload. The 11.7 read-through cache will eventually replace these reads, but the snapshot is *not* load-bearing for correctness — it's just there so 11.6 ships a working feature today. When 11.7 lands, snapshot fields stay (cheap, harmless) but reads prefer the cache.
6. **Status="queued" not plan's "to-read".** The plan's "to-read" was a forward-looking new-sidecar-shape label tied to Step 11.10. Until then, existing `next` and `stats` filter on `"queued"`, so using "queued" keeps everything working without rewiring.
7. **Status="removed" for entries that left the collection.** User confirmed naming preference. Entries already at `status="removed"` don't re-bucket on subsequent runs (no churn). Legacy entries with no `mendeley_id` are NEVER touched by the removed branch (they aren't part of the Mendeley-keyed reconciliation).
8. **id collisions handled with mendeley_id suffix.** When two Mendeley docs derive the same `_derive_id` slug (e.g. same first author + year + first title word), the second gets a `-{mendeley_id[:8]}` suffix so both can coexist. Idempotent re-run (same mendeley_id already on that id) is a no-op via the unchanged branch.
**Why:** (Narrow vs bundle) Cache without a consumer is dead code; 11.6 is fully usable on its own once you realize the snapshot is essentially free. (Folder_id roundtrip) only way the MCP works; one extra cheap call per run is the right cost. (Validator relax) the original 11.2 invariant survives in spirit — "no identifier-free entries" — just with a third allowed identifier. (Snapshot is write-only) decouples 11.6 from 11.7; you can read this PR end-to-end without thinking about caches. (status="queued" not "to-read") avoid churning the next/stats filter logic for a label that's going to change again at 11.10. (Suffix on id collision) the queue's primary key in the new world will be `mendeley_id` anyway (Step 11.10); the legacy `id` is just a slug, so a less-pretty form for collisions is fine.
**Alternatives rejected:**
- **Bundle 11.6 + 11.7.** Originally my Q1 framing — withdrawn after seeing list_documents already returns enough metadata for the snapshot. The cache earns its own PR with a clear consumer.
- **Snapshot AND read-through cache, with snapshot as fallback.** Option (b) from the Q1 discussion. Defensible but builds the read-through plumbing in two places — once as defensive fallback, again at 11.7. Single-shape reads (snapshot now, cache later) is cleaner.
- **Status enum.** Considered formalizing status to a Pydantic enum (queued/reading/done/removed). Held off — the existing code uses bare strings and an enum migration would touch every callsite. 11.10's full schema flip is the right place for it.
- **`mendeley_id` as the primary key in queue.json today.** Plan calls for this at 11.10. Doing it in 11.6 means migrating every existing entry, breaking show/edit/remove (which use the legacy `id`), and forcing the schema flip into the same PR as the new sync action. Defer.
- **Surface "Mendeley not running" hint when transport errors occur.** The plan's open question. Real-data validation hit a clean OAuth path (Mendeley desktop app was running), so we have no concrete failure-mode signature to detect against. Punt to first real failure.
**Status:** Active. Real-data validated 2026-05-02 (live MCP, OAuth refresh, folders GET, missing-collection hint surfaced as designed). 23 new tests; suite 94 → 117 green. Next session: Step 11.7 (read-through MendeleyCache wired into next/show/stats/search) — that's where the cache scaffolding earns its keep.

## 2026-05-02 — Step 11.7 file-backed read-through Mendeley cache (in-memory deferred indefinitely)
**Context:** `next` / `show` / `stats` / `search` need fresh Mendeley metadata (title/authors/year/doi) over the queue.json snapshot. Plan said in-process 5-min TTL cache. But every `docent paper ...` is a fresh Python process, so an in-process cache only helps inside one command — across commands the cache dies every invocation, defeating the "feels instant" UX the plan promised.
**Decision:** File-backed cache at `<cache_dir>/paper/mendeley_collection.json`, TTL 300s, atomic write. Wraps `mendeley_list_documents` only — not `get_document` (no current reader needs the fields it adds). Three readers wired (`next`/`show`/`search`); `stats` skipped because none of its outputs are Mendeley-owned. `sync-from-mendeley` invalidates the relevant `folder_id` after a successful write so the next reader pulls fresh data. On any MCP failure (transport / auth / missing collection / ambiguous), the overlay returns None and readers fall through to the snapshot — silent fallback, no warning printed.
**Why:** (file vs in-memory) Same code volume; lands the actual UX promise; survives across CLI calls. (`list_documents` only) The bulk endpoint already returns title/authors/year/doi fresh; per-doc round-trips are pure cost until a consumer needs abstract/attachments. Smaller surface, fewer round-trips. (skip `stats`) Stats reads no Mendeley fields, so wiring it would mean paying for a list_documents call to overlay nothing. (silent fallback) Reader UX trumps loud failure-reporting; warnings would litter `search` output. (cache injects `list_documents` from paper.py at construction) Without this, monkeypatching the import-site alias misses the cache — caught by initial test failure.
**Alternatives rejected:**
- **In-memory, per-plan.** Ships the name, not the UX — fresh process per CLI call. Useful only inside `stats`/`search` loops, but those are millisecond-cheap anyway.
- **No cache, refresh snapshot inside `sync-from-mendeley`.** Smallest possible diff. Rejected because the snapshot would only be as fresh as the last sync; readers couldn't pick up changes the user made in Mendeley between syncs.
- **Wrap `get_document` too.** Adds per-id round-trip path with no current consumer. Defer until a consumer asks (likely Step 11.8 when `add` collapses and `--mendeley-id` upserts arrive).
- **Wire `stats` for symmetry with the plan.** Wasted MCP call per `stats` invocation for zero output difference. Plan deviation, documented.
- **Expose `--no-cache` flag / `paper cache-clear` action.** No real consumer yet. Manual file delete works; revisit if it bites.
**Status:** Active. Real-data validation pending. 20 new tests; suite 117 → 137 green in ~20s.
**Validation (2026-05-02):** Confirmed — overlay correctness verified; readers displayed fresh Mendeley metadata from Docent-Queue collection. Performance bug found (folder-id fetched on every reader call, ~5s each) → fixed in Step 11.7-followup (folder-id cached 24h TTL; warm `paper next` sub-second).

---

## 2026-05-02 — Steps 11.8+11.9: rip out homegrown extraction + collapse watch architecture

**Context:** Step 11.5 shipped font-size title heuristics + CrossRef title search. Real-data validation failed badly — most PDFs got the author list as title, some concatenated section headings with authors. Meanwhile Mendeley auto-imported the same PDFs with clean metadata. The hard signal: we were solving a problem Mendeley already solves better. Step 11.7 had already established Mendeley as the metadata source of truth for the reading layer; 11.8 was the cleanup pass — delete the extraction code that the pivot made obsolete. Step 11.9 followed immediately: the `mendeley_watch_subdir` setting and `sync-promote`/`sync-mendeley` actions existed to manage a two-folder model (database + watch subfolder), but the new architecture makes `database_dir` the watch folder directly.
**Decision:**
1. **Delete `paper_metadata.py` entirely** (~296 LOC: `resolve_metadata`, `extract_pdf_metadata`, `_extract_title_by_font_size`, `crossref_lookup`, `crossref_title_search`, `_filename_heuristic`) and its 14 tests. Drop `pypdf` from `pyproject.toml`.
2. **`paper add` collapses to two modes:** bare `add` returns guidance text only ("Drop PDF → drag into Docent-Queue → sync-from-mendeley"); `add --mendeley-id <id>` upserts a stub entry. `AddInputs` slimmed to `mendeley_id/priority/course/notes/force`.
3. **`scan` action deleted** (folder-walk + per-PDF add no longer makes sense; Mendeley owns ingestion).
4. **Retire `mendeley_watch_subdir` setting** — `database_dir` is the watch folder. One folder, no subdir. Removes a configuration concept that confused the architecture.
5. **Retire `sync-promote`** (moving PDFs to watch — no longer needed, they're already there) and **`sync-mendeley`** (replaced entirely by `sync-from-mendeley`).
6. **`sync-status` simplified** — dropped `watch_dir`, `promotable`, `in_watch` fields that referenced the now-dead two-folder model.
**Why:** (Delete over keep-dormant) dead code is the worst kind — it passes every test, looks like it works, and silently misleads future readers. (Add as guidance-only) `add --pdf` was the entry point for everything the pivot killed; keeping it as a stub that redirects to the correct workflow costs nothing and prevents the inevitable "why doesn't this work anymore?" question. (Single folder) removing the two-folder model eliminates the `mendeley_watch_subdir` footgun and simplifies sync-status irreversibly. (Retire sync-promote/sync-mendeley together with 11.8) they share the same dead concept; one PR is cleaner than two.
**Alternatives rejected:** Keep extraction code as a fallback for Mendeley failures — the fallback is worse than the failure; showing an error beats showing a wrong title. Keep `sync-promote` for the "move to watch" pattern with the new single-folder model — no movement needed when the folder is one. Keep `mendeley_watch_subdir` as deprecated-but-wired — silent config debt; better to break loudly once.
**Status:** Active. Net diff −1074 / +28 LOC. Suite 143 → 128 → 102 green.

---

## 2026-05-02 — Step 11.10: one-shot sidecar migration + schema trim

**Context:** With Mendeley as truth, several `QueueEntry` fields that tracked filesystem and Mendeley-linking state (`pdf_path`, `file_status`, `keep_in_mendeley`, `promoted_at`, `title_is_filename_stub`) were now either dead (filesystem) or subsumed by `mendeley_id`. Carrying them created confusion ("why does this entry have pdf_path if we don't manage files?") and bloated the serialized JSON. A migration action was needed to wipe live data to the new shape.
**Decision:**
1. **`paper migrate-to-mendeley-truth [--yes]` action** backs up `queue.json` → `queue.json.bak` and rewrites entries to the trimmed schema. Guarded by `--yes` to prevent accidental wipes.
2. **Dropped fields:** `pdf_path`, `file_status`, `keep_in_mendeley`, `promoted_at`, `title_is_filename_stub`. Dropped `mark-keeping` action (its field is gone). Dropped `StatsResult.keeping` + `BannerCounts.watch_files`.
3. **Added fields:** `started` / `finished` ISO timestamps, stamped on first transition to `reading` / `done` respectively, never overwritten.
4. **`sync-pull` no longer mutates the queue** — downloads to `database_dir/{eid}.pdf` and trusts Mendeley to pick it up; "already_has_file" keys on filename existence rather than a recorded `pdf_path`.
5. **`_require_identifier` tightened:** `mendeley_id` or `doi` only (`pdf_path` field gone).
**Why:** (One-shot migration action over incremental migration) the fields were load-bearing in Step 11.9 tests; removing them one at a time would have left the schema in a half-trimmed state. One action, one backup, one schema state. (started/finished timestamps) natural replacement for `promoted_at` that was tracking workflow progress, but oriented toward the reading workflow (started reading, finished reading) rather than the ingestion workflow. (sync-pull no longer writes queue) decouples download from queue state; Mendeley is the integration point.
**Alternatives rejected:** Keep the dropped fields as nullable with `None` defaults — schema rot; every reader would need to handle both old and new field presence. Migrate incrementally per-action — three or four PRs for what was one consistent schema change. Drop `sync-pull` entirely — still useful for OA download by DOI, orthogonal to the metadata pivot.
**Status:** Active. Suite 101 → 107 green. Real-data validated: user ran `migrate-to-mendeley-truth --yes` against live queue — clean.

---

## 2026-05-06 — Step 11.R: reading tool rewrite (`paper` → `reading`)

**Context:** The tool had been called `paper-pipeline` in the gstack skill and `paper` in Docent's registry. After the Mendeley pivot, the remaining actions (queue management, Mendeley sync, deadline tracking) are a reading workflow tool, not a paper metadata pipeline. The name `paper` was a carry-over from when the tool managed PDF ingestion. With ingestion fully delegated to Mendeley, the name was wrong. Separately, several schema fields (`priority: str`, `course: str | None`) had accumulated meaning that deserved richer modeling.
**Decision:**
1. **Rename**: `paper.py` → `reading.py`, `paper_store.py` → `reading_store.py`, `PaperPipeline` → `ReadingQueue`, registry name `"paper"` → `"reading"`, config section `[paper]` → `[reading]`, `PaperSettings` → `ReadingSettings`, `Settings.paper` → `Settings.reading`.
2. **Schema changes**: `priority: str` → `order: int` (1-based position in reading order); `course: str | None` → `category: str` (one of `paper|book|book_chapter`) + `course_name: str | None`; `+deadline: str | None`.
3. **Actions removed**: `migrate-to-mendeley-truth` (one-shot, done), `sync-pull` (removed).
4. **Actions added**: `move-up`, `move-down`, `move-to` (order management); `set-deadline` (explicit deadline action rather than burying in `edit`).
5. **`ready-to-read` renamed `start`** — verb is clearer; transitions status to `reading` + stamps `started` timestamp.
6. **New `reading_notify.py`** — deadline check at CLI startup, daily dedup via a timestamp file, wired into `cli.py` main callback.
7. **Config migration required**: user runs `docent reading config-set database_dir <path>` once; old `[paper]` section is silently ignored.
**Why:** (Rename now, not later) the wrong name would have been carried into Step 12 (plugin discovery) and Step 13 (MCP), embedding `paper` in external-facing surface like MCP tool names. Better to rename before those steps lock the surface. (order: int over priority: str) the queue is ordered; a bare priority string like `"high"` doesn't capture position. Integer order is sortable, composable with move-up/down/to, and unambiguous. (category + course_name split) `course` was overloaded — sometimes a course code, sometimes "personal" or "thesis". Two fields with defined semantics are cleaner. (deadline as explicit action) deadline is a first-class property that needs its own UX; burying it in a generic `edit` obscures it. (notify at startup) passive, non-blocking; fires once per day at most; user sees upcoming deadlines without having to remember to run `docent reading stats`.
**Alternatives rejected:** Keep `paper` as the name for backwards compat — no external users exist yet; cost of name-debt is higher than cost of migration. Use `priority` enum (low/medium/high) instead of integer order — enum doesn't encode relative position; two "high" entries have undefined order. Use a separate `docent notify` command — adds a new entry point for functionality that only matters in the reading context; startup hook is simpler and automatic.
**Status:** Active. Suite 107 → 93 green (−14 deleted tests, +1 new). User completed config migration.

---

## 2026-05-07 — Step 12: `~/.docent/plugins/` external discovery + bundled_plugins

**Context:** Step 7a defined the registry + `@register_tool` decorator. Tools were discovered by walking `src/docent/tools/`. By Step 11.R the reading tool was the only real tool there, and it had grown large enough to warrant its own package (multiple modules: `reading.py`, `reading_store.py`, `mendeley_client.py`, etc.). Step 12 was designed to (a) allow users to drop plugin files into `~/.docent/plugins/` without editing the package, and (b) move the reading tool out of `tools/` into a structured location that supports multi-module plugins.
**Decision:**
1. **New `src/docent/core/plugin_loader.py`** with `load_plugins()` and `run_startup_hooks()`. Loads from two sources in order: `src/docent/bundled_plugins/` (first-party, packaged), then `~/.docent/plugins/` (user-installed, external). Supports flat files (single `.py`) and packages (directory with `__init__.py`).
2. **`on_startup` lifecycle hook** — if a plugin module defines `on_startup(context)`, `run_startup_hooks()` calls it after all plugins load. Used by the reading tool to fire deadline notifications.
3. **Reading tool migrated to `src/docent/bundled_plugins/reading/`** — multi-module package (`reading.py`, `reading_store.py`, `mendeley_client.py`, `mendeley_cache.py`, `reading_notify.py`). `__init__.py` re-exports the `ReadingQueue` class.
4. **`src/docent/tools/` becomes a pass-through** — `__init__.py` kept for future single-file tools dropped there by the framework, but no real tools live there anymore.
5. **`on_startup` wired for the reading tool**: `reading_notify.check_deadlines(context)` runs once at startup.
**Why:** (bundled_plugins separate from tools/) bundled tools are multi-module packages that need their own directory structure; a flat `tools/` directory can't host them without a naming mess. (External discovery via `~/.docent/plugins/`) this was planned since Step 7a ("Later, add a second discovery path"); doing it at Step 12 before the MCP adapter locks the registry surface. (Lifecycle hook over startup action) deadline checking doesn't belong as a user-invoked command; it belongs to the startup path where it's passive. (Load bundled before external) first-party tools take precedence; name collisions with external plugins produce a clear error, not silent replacement.
**Alternatives rejected:** Keep reading tool flat in `tools/reading.py` and extract submodules there — naming conflicts with future single-file tools in the same directory; the multi-module package model is cleaner. Build `~/.docent/plugins/` discovery as a separate step — it was already planned and trivially cheap to wire at the same time as the bundled loader.
**Status:** Active. 9 new tests; suite 100 green.

---

## 2026-05-07 — Step 13: full MCP adapter (`docent serve`)

**Context:** Step 11.4 added an in-process MCP client (Docent calling Mendeley's MCP server). Step 13 is the inverse: Docent as an MCP server, so Claude Code and other MCP hosts can call Docent's reading actions as tools. The registry already holds typed schemas for every action; the MCP adapter's job is to expose them without duplicating that structure.
**Decision:**
1. **New `src/docent/mcp_server.py`** (~130 LOC). `build_mcp_tools()` introspects the registry → one `types.Tool` per (tool, action) pair, named `{tool}__{action}` (hyphens → underscores, double-underscore separator). `invoke_action()` dispatches sync and generator actions, drains generators to completion, serializes Pydantic results as JSON text. `run_server()` wires `list_tools` + `call_tool` handlers into a stdio MCP server.
2. **`docent serve` command** in `cli.py` — lazy-imports `mcp_server` (keeps `docent --version` and all other commands free of the `mcp` SDK's startup cost). `mcp >= 1.0, < 2` already in deps from Step 11.4.
3. **`.mcp.json` template** at repo root — shows the `{"mcpServers": {"docent": {"command": "docent", "args": ["serve"]}}}` stanza users copy into their Claude Code config.
4. **Generator actions fully supported** — `invoke_action()` detects generators, drains them (discarding `ProgressEvent` records), and returns the final result. The MCP protocol has no streaming concept at the tool-call level; progress events are irrelevant from an MCP caller's perspective.
5. **Tool naming convention**: `reading__next`, `reading__show`, `reading__sync_from_mendeley`, etc. Double-underscore unambiguously separates tool and action (no tool or action name contains `__`); underscores replace hyphens to satisfy MCP tool name constraints.
**Why:** (Introspect registry over handwritten tool list) the registry already has everything; duplication is bug surface. (Separate `mcp_server.py` + lazy import) adding `import mcp` at module level would slow every invocation including `docent --version`. (Drain generators for MCP callers) the MCP protocol's `call_tool` is synchronous from the host's perspective; streaming would require SSE or WebSocket transport which the `mcp` SDK doesn't support in stdio mode. (`.mcp.json` template at root) Claude Code looks for it there by convention; a template with the right shape saves the user a lookup.
**Alternatives rejected:** Expose only single-action tools over MCP, skip multi-action — would hide most of Docent's surface. Use `{tool}/{action}` naming — slashes are not valid in MCP tool names. Stream ProgressEvents as intermediate tool results — not supported by the stdio MCP transport. Build the MCP adapter as a separate package — no external users yet; keeping it in-package avoids a deployment split.
**Status:** Active. 10 new tests; suite 100 → 110 green. Smoke-tested: `docent serve` in `--help`; tool list returns reading actions.

---

## 2026-05-07 — Phase 1.5-A: Output Shapes vocabulary + `ui/renderers.py`

**Context:** Every result type (`MutationResult`, `SearchResult`, `SyncStatusResult`, etc.) had its own ad-hoc `__rich_console__` implementation. Two problems: (1) the CLI, future web UI, and MCP all needed result data, but there was no typed contract for what shape the data came in — a web renderer would have to parse Rich markup strings; (2) `__rich_console__` on result models is a layering violation (tool result knows about UI library). Output Shapes defines a typed intermediate representation between "tool returned this" and "UI rendered this."
**Decision:**
1. **`src/docent/core/shapes.py`** — `OutputShape` base + six leaf types: `MarkdownShape`, `DataTableShape`, `MetricShape`, `LinkShape`, `MessageShape`, `ErrorShape`. Each is a plain Pydantic model with no Rich imports.
2. **`to_shapes() -> list[OutputShape]`** — result models implement this instead of (or alongside) `__rich_console__`. Content strings are plain text; no markup. The renderer is responsible for styling.
3. **`src/docent/ui/renderers.py`** — `render_shapes(shapes, console)` dispatches per shape type to typed Rich render functions. `cli.py` calls this after invoking any action. One central place for all visual styling decisions.
4. **`ui/theme.py`** — centralized color tokens (`ACCENT`, `DIM`, `SUCCESS`, `WARNING`, `ERROR`) referenced by `renderers.py`. Changing the whole CLI theme is a one-file change.
5. **Retrofitted `reading` tool results** — all reading result types implement `to_shapes()`. `__rich_console__` retained as a compatibility shim on result models that need it, but deprecated in favor of shapes.
**Why:** (Shapes over ad-hoc __rich_console__) shapes are serializable to JSON (for the future web UI) and testable without a Rich console. The MCP adapter already serializes results as JSON; without shapes, the web UI would have to parse Rich markup. (Plain text content in shapes) styling is the renderer's job, not the data model's. (renderers.py as the single render registry) if we ever swap Rich for Textual or a web renderer, there's one file to change. (Retrofit reading tool now) with two consumers (CLI + MCP) already live, deferring the retrofit means the shape contract diverges before it has any traction.
**Alternatives rejected:** Keep `__rich_console__` on result models and add a separate `to_json()` method — two parallel serialization paths that drift; any new field added to the model needs to be added in both. Use dataclasses instead of Pydantic for shapes — lose free JSON serialization and schema introspection that the future web UI will use. Build shapes as an abstract Shape protocol rather than concrete leaf types — too much indirection for the concrete use case.
**Status:** Active. Suite unaffected (shapes are tested through reading tool result tests).

---

## 2026-05-07 — Phase 1.5-B: contract tests + AGENTS.md

**Context:** With the registry and dispatcher being the load-bearing seam for CLI, MCP, and future web UI, a regression in the Tool ABC or dispatcher would silently break all three. The existing test suite covered per-action behavior (reading queue operations) but not the framework contract itself. AGENTS.md was flagged in Phase 1.5-C's roadmap entry ("AGENTS.md — three rules max, not a document") as a cheap architectural invariant record.
**Decision:**
1. **`tests/test_tool_abc.py`** (13 tests) — Tool ABC invariants: `run()` raises `NotImplementedError` by default, `collect_actions()` returns decorated methods only, `@register_tool` rejects reserved names (`list`, `info`, `config`, `version`), double-registration raises, multi-action tool with no actions raises at registration.
2. **`tests/test_dispatcher.py`** (6 tests) — `invoke_action()` paths: sync action returns result, generator action drains and returns final result, unknown action raises, action raises exception, input validation failure.
3. **`AGENTS.md` at repo root** — three-section behavioral contract: (a) calling convention for reading actions (identifier formats, required fields, action semantics); (b) reading queue invariants (order is 1-based, no gaps; mendeley_id or doi required; category is one of paper/book/book_chapter); (c) destructive action rules (queue-clear requires `--yes`, migrate-to-mendeley-truth requires `--yes`, dry-run is always safe). Written as a reference for Claude Code sessions and future MCP callers.
**Why:** (Contract tests separate from reading tests) if a future tool breaks the ABC, the reading tests won't catch it — the contract tests will. Separation of concerns in the test suite mirrors the separation of concerns in the code. (AGENTS.md at repo root) Claude Code reads it on every session start; three sections is the right density — enough to prevent the two most likely session-start mistakes (wrong identifier format, wrong destructive action pattern) without becoming documentation that no one reads. (6 dispatcher tests) covers the paths the MCP adapter actually exercises; more is premature without more callers.
**Alternatives rejected:** Add contract assertions inside `@register_tool` only — catches registration-time errors but not the structural invariants (ABC method behavior, collect_actions correctness). Put AGENTS.md content in CLAUDE.md — CLAUDE.md is Claude Code config; AGENTS.md is for any LLM caller, including future MCP hosts that don't have CLAUDE.md. Write AGENTS.md as full documentation — the "three rules max" constraint was explicit in the roadmap; a long doc gets ignored.
**Status:** Active. Suite 141 → 160 green.

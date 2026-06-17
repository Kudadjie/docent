# Changelog

All notable changes to Docent are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and Docent uses
[semantic versioning](https://semver.org/).

This file is the **single source of truth** for "What's New":

- The CLI shows the current version's `### What's New` bullets as a banner for a
  few runs after an update (`docent whatsnew` shows the full entry on demand).
- The web UI surfaces them as a dismissible toast on first load after an update.
- The README "What's New" section and the GitHub release body are derived from
  the entry for the released version.

**Release process:** before tagging `vX.Y.Z`, rename the `[Unreleased]` heading
below to `[X.Y.Z] - YYYY-MM-DD`. The heading version must match the package
version exactly so the runtime can find the entry. Keep a `### What's New`
subsection with 2–5 user-facing highlights — those are what the banner shows.

## [Unreleased]

## [2.2.0] - 2026-06-17

### What's New
- **A fresh look** — the whole app got a design pass: Schibsted Grotesk + serif
  headings, a cleaner white/ink palette, green primary actions, and a collapsible
  sidebar.
- **Always-on MCP server** — Docent now speaks MCP over HTTP + SSE (`/mcp/sse`,
  bearer-key auth), so long-running and remote clients can connect, not just stdio.
- **Clearer reading-sync errors** — when Zotero or Mendeley can't be reached you
  get a plain-language "check your connection" message instead of a raw HTTP
  error, and a dropped connection mid-sync can no longer falsely mark papers as
  removed from your queue.
- **`docent update` works everywhere** — it detects whether you installed via uv,
  pipx, or pip and runs the right upgrader (no more silent failures for non-uv
  installs).

### Added
- HTTP + SSE MCP transport at `/mcp/sse` with bearer-key auth. `serve.api_key` is
  auto-generated on first `docent ui`; new `serve.host` and
  `serve.http_mcp_enabled` settings.
- Artifact viewer in the web UI, plus an `update-next-release` maintenance hook.

### Changed
- Design overhaul: new type system (Schibsted Grotesk body + serif display),
  white/ink color system, green CTAs, and a collapsible sidebar with size-aware
  icons and tinted page-heading icon chips.
- `ui_server.py` slimmed to app assembly — shared helpers moved to
  `ui_routes/_shared.py`, studio form builders to `ui_routes/_studio_request.py`
  (re-exported for compatibility); the studio plugin monolith was split into
  focused modules.
- Reading sync surfaces friendly transport-error messages for both Zotero and
  Mendeley; if a sub-collection can't be fetched mid-sync, the removal-flagging
  pass is skipped so a flaky connection can't corrupt queue state.

### Security
- Per-session token (`X-Docent-Token`) is now required on all mutating web-UI API
  requests; the WebSocket handshake carries it in its first message, and a new
  `GET /api/auth/token` issues it. Closes a localhost cross-port
  `tools/invoke` → arbitrary-code seam.

### Fixed
- Auto-sync on a stale reading queue no longer shows a spurious green
  "An unexpected response was received" toast — the manual and auto-sync paths now
  share a single result interpreter.
- `docent update` detects the install method from `sys.executable`; on Windows it
  shows a "file in use — restart your terminal" hint instead of a generic error
  when the running process locks the executable.
- The "What's New" toast now fires for dev builds (once per tagged release) and
  shows a "See more" affordance whenever any bullet is truncated.
- Duplicate tool-registration warning is routed through logging instead of stderr;
  `_version_at_least` now uses `packaging.version`.
- Tightened `pyproject.toml` dependency bounds to `~=` for critical dependencies so
  `docent update` can't pull a breaking major version; corrected the stale `ddgs`
  floor to `~=9.0`.

## [2.1.2] - 2026-06-01

### What's New
- **Docs page** — all guide sections now load in packaged installs (was 404 in v2.1.1
  due to a packaging error; `docs/` files are now correctly bundled in the wheel).
- **`docent whatsnew`** and the UI "What's New" toast now correctly show release
  highlights after an update (v2.1.1 bundled the wrong `CHANGELOG.md`).
- **Dev builds** — `docent whatsnew` now shows the latest tagged release notes
  instead of "No release notes found" when the `[Unreleased]` section is empty.

### Fixed
- v2.1.1 was tagged before its packaging fixes (`force-include` for `docs/` and
  the renamed `[2.1.1]` CHANGELOG entry) landed on `main`, producing a wheel that
  silently shipped without bundled docs or correct release metadata. v2.1.2 is a
  corrected re-release of the same changes.

## [2.1.1] - 2026-06-01

### Changed
- `mypy` type gate now covers all of `src/docent/` (previously scoped to `core`,
  `config`, `llm`, `execution` only). All pre-existing type errors across
  `cli.py`, `mcp_server.py`, `ui_server.py`, `_banner.py`, the UI-route modules,
  and the `bundled_plugins` sub-tree have been resolved (generator return types,
  `None`-guard gaps, shadowed variables, wrong argument types, and more).

### Fixed
- `docent whatsnew` no longer shows the post-update banner *and* the full entry
  at the same time — the startup banner is now suppressed when `whatsnew` is the
  invoked subcommand.
- Release highlights were truncated to the first line of each bullet; multi-line
  continuation lines in `CHANGELOG.md` are now joined so full bullet text is
  preserved.
- Raw markdown syntax (`**bold**`, `` `code` ``) no longer appears literally in
  the CLI banner and `docent whatsnew` output — it is converted to Rich markup
  before rendering.
- Docs page showed "404 Not Found" for all sections in a packaged install because
  the `docs/` files were never included in the wheel; they are now bundled via
  `force-include` in `pyproject.toml`.
- The "What's New" UI toast displayed raw markdown text and truncated bullets
  with no way to read the full entry; bullets are now rendered as plain text
  (stripped of markdown), and a "See all →" link opens a modal with the full
  changelog entry rendered as markdown.

## [2.1.0] - 2026-05-31

### What's New
- **Citation graph** — `docent studio cite-graph` scavenges the full citation
  network of a seed paper; the web UI shows the result as a browsable paper list
  with abstracts.
- **`--expand-citations`** — pass this flag to `deep-research` or `lit` to
  automatically enrich the output with synthesised citation-graph context.
- **Concurrent Studio runs** — start multiple research jobs simultaneously; the
  UI shows a run switcher and auto-queues jobs when all backends are busy.
- **Zotero integration** — connect your Zotero library via `pyzotero`; sync,
  browse, and queue papers directly from the web UI.
- **What's New, everywhere** — release highlights now appear in the CLI (a brief
  post-update banner + `docent whatsnew`) and as a dismissible web-UI toast.
- **Faster web UI** — settings are cached so the dashboard and Studio respond
  quicker (no config re-parse on every request).

### Added
- `docent studio cite-graph` — citation scavenger action (API + UI); retries on
  429 with exponential back-off and surfaces the API-key hint on exhaustion.
- `--expand-citations` flag on `deep-research` and `lit`; fan-out fetches run in
  parallel via a new `parallel_fetch()` primitive; an enrichment LLM pass
  synthesises open-access abstracts into the draft with a quality guard.
- Anchor-paper lookup now works for non-arXiv academic fields (DOI/title
  fallback).
- Concurrent Studio runs: client admission control, auto-queue, frontend
  run-manager with switcher panel (Slice 1).
- Zotero bridge via `pyzotero`; reference-manager toggle + credential fields in
  Settings; Zotero status in `docent doctor`.
- NotebookLM: upfront auth check, slow-chat recovery via history polling,
  notebook-existence pre-flight.
- Schema-driven `/tools` runner page in the web UI.
- Tavily credit usage tracking + display in Settings.
- Reference-manager setup card shown to new users on the Reading page.
- Docs served via API and rendered with `react-markdown` (single source of
  truth).
- `docent whatsnew` CLI command; What's New toast in the web UI.
- Tier-4 harness: prompts as first-class code + MCP surface gate.

### Fixed
- Cross-site WebSocket hijack (security — Origin header validation).
- Backup-restore path traversal hardening; UI reads routed through
  `ReadingQueue` to prevent direct-file exposure.
- Hardened page fetching — research requests now refuse non-public /
  redirect-to-internal URLs (SSRF protection).
- Duplicate `StudioRunBody` definition removed; import unified.
- NotebookLM: concurrent-run crash fixed via serialised auth + research-push;
  notebook reuse validated before use; empty-push now fails loudly.

### Changed
- Reference-manager field names in `ReadingQueue` renamed to be
  manager-agnostic (Mendeley → generic names); backwards-compatible.
- Studio form handling unified behind a single request builder — in-process and
  subprocess paths can no longer drift.
- Clearer non-interactive vs. auto-confirm behaviour for MCP and UI callers.
- Settings and Reading page frontends split into focused modules (Wave 4 & 5
  refactors).

### Internal
- mypy type-check gate and stricter ruff linting added to CI.
- Frontend Vitest suite added as a merge gate.
- First-run setup wizard extracted from `cli.py` into `cli_setup.py`.
- Test jobs labelled "CLI (Python)" and "Frontend" in CI output.

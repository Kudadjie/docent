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

### What's New
- **Faster web UI** — settings are cached, so the dashboard and Studio respond
  quicker (no config re-parse on every request).
- **Hardened page fetching** — research page fetches now refuse non-public/
  redirect-to-internal URLs (SSRF protection).
- **What's New, everywhere** — release highlights now show up in the CLI (a brief
  post-update banner + `docent whatsnew`) and the web UI.

### Changed
- Studio form handling is unified behind a single request builder, so the
  in-process and subprocess paths can no longer drift.
- Clearer non-interactive vs. auto-confirm behaviour for MCP and UI callers.

### Internal
- Added a type-check (mypy) gate and stricter linting/formatting in CI.
- Extracted the first-run setup wizard out of `cli.py` into `cli_setup.py`.

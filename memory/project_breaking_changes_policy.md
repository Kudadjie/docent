---
name: breaking-changes-policy
description: Versioning and deprecation policy for Docent — what triggers a MAJOR/MINOR/PATCH bump, how external tool breakage is handled, how state migrations work.
metadata:
  type: project
---

Decided 2026-05-14. Applies from current version forward.

## Semver rules

| Change type | Version bump |
|---|---|
| CLI command/flag rename or removal | MAJOR |
| Config key rename or removal | MAJOR |
| Plugin API change (Tool ABC, `@action` signature, shape type structure) | MAJOR |
| State file format change requiring migration | MAJOR |
| New CLI commands, config keys, plugin APIs, shape types (additive) | MINOR |
| Bug fixes, internal refactors with no user-visible change | PATCH |

## Deprecation window

One MINOR version of visible warnings before any MAJOR removal. Warnings appear in:
- CLI output on deprecated usage
- `docent doctor` output

## External tools (feynman, mendeley-mcp, zotero-mcp)

Docent does not control external tool versioning. Policy:
- Pin tested version ranges in `pyproject.toml` extras
- `docent doctor` warns when installed version deviates from pinned range
- External tool breaking changes are **not** a Docent MAJOR bump — they are a `WARN` in doctor

## State file migrations

- Add a `version` field to any state file the first time it needs migration
- Auto-migration script runs on startup (non-destructive: backup old file, write new)
- Never require manual user intervention for a migration

**Why:** [[feedback_external_tool_registration]] — external tools are treated as dependency, not part of Docent's own API surface.

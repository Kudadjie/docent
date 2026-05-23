---
name: Docent release plan
description: Single bundled release track; v2.0.0 shipped 2026-05-23 (omnibus — Studio, doctor, setup, full MCP, bundled UI hardening)
type: project
---

Created 2026-05-07 based on user direction.

## Single bundled release track (actual model)

The two-track plan (separate CLI and UI tags) was superseded before it was executed. CLI and UI ship together in one PyPI wheel.

### Shipped releases

| Tag | Date | Notes |
|-----|------|-------|
| `v1.1.0` | 2026-05-08 | First public release — CLI + bundled UI (FastAPI + Next.js static export) |
| `v1.1.1` | 2026-05-08 | Wheel-only fix — sdist with `ui_dist/` exceeded PyPI 100 MB limit |
| `v2.0.0` | 2026-05-23 | **MAJOR** — Studio tool, doctor/setup, full MCP, reading queue rewrite, plugin system, dashboard, error codes, CI |

### Distribution model

- **PyPI package:** `docent-cli` wheel contains both CLI and `ui_dist/` static files. `docent ui` starts FastAPI on `localhost:7432`.
- **No sdist:** sdist is skipped in `publish.yml` (size limit). Wheel only.
- **GitHub Releases:** auto-created on tag push via `publish.yml` workflow (added `aeb62f1`). v1.1.0 was created manually; v1.1.1+ are automatic.
- Architecture details (FastAPI endpoints, two-file sync cost) → `project_ui_bundling.md`.

## How to apply

- CLI and UI ship together; bump the version once for both.
- Next version: `v2.1.0` — schema-driven forms, Zotero bridge (gate on coexistence decision), plugin developer docs.
- `actions/setup-node` SHA-pinned 2026-05-07 (Phase A CSO fix): `@49933ea5288caeca8642d1e84afbd3f7d6820020`

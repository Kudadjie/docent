---
name: Docent release plan
description: Single bundled release track; v1.1.0 shipped 2026-05-08; next: v1.2.0 on research bug fixes + Tavily
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

### Distribution model

- **PyPI package:** `docent-cli` wheel contains both CLI and `ui_dist/` static files. `docent ui` starts FastAPI on `localhost:7432`.
- **No sdist:** sdist is skipped in `publish.yml` (size limit). Wheel only.
- **GitHub Releases:** auto-created on tag push via `publish.yml` workflow (added `aeb62f1`). v1.1.0 was created manually; v1.1.1+ are automatic.
- Architecture details (FastAPI endpoints, two-file sync cost) → `project_ui_bundling.md`.

## How to apply

- CLI and UI ship together; bump the version once for both.
- Next version: `v1.2.0` — research bug fixes (DDG→Tavily, registry warn+skip, Tavily key onboarding). Ready to tag.
- `actions/setup-node` SHA-pinned 2026-05-07 (Phase A CSO fix): `@49933ea5288caeca8642d1e84afbd3f7d6820020`

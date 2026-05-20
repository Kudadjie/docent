---
name: UI Bundling Strategy — Option B (IMPLEMENTED 2026-05)
description: Archived — plan fully implemented. FastAPI + Next.js static export ships in PyPI wheel.
type: project
originSessionId: 05b13373-5268-4541-a962-9020399ec752
archived: true
---
Chosen approach: **Option B — FastAPI backend + Next.js static export**.

Fully implemented as of 2026-05 (ui_server.py, src/docent/ui_dist/, frontend/out/ all exist).
`docent ui` serves the app at localhost:7432. Wheel includes ui_dist/ as package data.

**Why:** No Node.js dependency for end users. Everything ships in the `docent-cli` PyPI wheel.

**Decision confirmed by user on 2026-05-07.** Implementation completed in the same sprint.

> Archived because the plan is fully executed. The "deferred" language no longer applies.

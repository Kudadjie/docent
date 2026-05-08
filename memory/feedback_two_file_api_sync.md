---
name: Every new API endpoint needs two implementations
description: New API routes must be added in both the Next.js dev route and the FastAPI server — remind the user to do both
type: feedback
---

Every new API endpoint lives in two places:

1. `frontend/src/app/api/<name>/route.ts` — Next.js route used by the dev server (`npm run dev`)
2. `src/docent/ui_server.py` — FastAPI endpoint used by the bundled `docent ui` release

**Why:** The dev server (Next.js) and the bundled release (FastAPI) are separate stacks. Adding to only one causes the two environments to diverge silently. The user discovered this the hard way and explicitly asked to be reminded.

**How to apply:** Whenever a new API route is added during a session, immediately flag that the FastAPI counterpart also needs to be written before the task is considered done. Don't wait until the end — cross-check as each route is created.

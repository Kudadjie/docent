---
name: New API routes go in ui_routes/ only — Next.js proxies automatically
description: FastAPI (ui_routes/) is the only API backend; Next.js dev proxies all /api/* to FastAPI via next.config.ts rewrites — no duplicate Next.js route needed
type: feedback
---

New API endpoints have exactly **one** implementation: a FastAPI route in `src/docent/ui_routes/<module>.py`.

The Next.js dev server (`npm run dev`) proxies all `/api/:path*` requests to `http://127.0.0.1:7432/api/:path*` via a `rewrites()` rule in `frontend/next.config.ts`. No Next.js API route file is needed.

**Why:** The original two-file sync rule (add route in both `frontend/src/app/api/` AND `ui_server.py`) was correct when Next.js API routes existed. After the ui_routes/ split and the Next.js proxy adoption, the `frontend/src/app/api/` directory was removed entirely. The proxy eliminates the sync cost: one FastAPI implementation serves both the bundled release and the Next.js dev server.

**How to apply:** When adding a new API endpoint:
1. Add the route to the appropriate `ui_routes/` module (`reading.py`, `studio.py`, `config.py`, `doctor.py`, `filesystem.py`, `opencode.py`) or create a new module.
2. Import and register the router/routes at the bottom of `ui_server.py` if a new module.
3. No Next.js route file needed — the proxy handles dev automatically.
4. Verify with `docent ui` (bundled mode) AND `npm run dev` (proxy mode) that the route is reachable in both environments.

**Supersedes:** The old "two-file API sync" rule (add in Next.js + FastAPI) — that rule applied before `frontend/src/app/api/` was removed and `next.config.ts` rewrites were adopted.

---
name: UI Bundling Strategy — Option B
description: Decided architecture for bundling docent-ui into the Python CLI package (FastAPI + Next.js static export)
type: project
---

Chosen approach: **Option B — FastAPI backend + Next.js static export**.

**Why:** No Node.js dependency for end users. Everything ships in the `docent-cli` PyPI wheel. User experience mirrors Jupyter/MLflow/TensorBoard.

**How to apply:** When the user is ready to implement, this is the full plan:

### Build side (CI / release)
1. `next build` with `output: 'export'` in `next.config.ts` → produces `frontend/out/` (static HTML/CSS/JS, no Node runtime needed)
2. Copy `frontend/out/` → `src/docent/ui_dist/` (tracked as package data in `pyproject.toml`)
3. `uv build` picks up `ui_dist/` in the wheel

### Runtime side (Python)
4. New `docent/ui_server.py` — FastAPI app that:
   - Mounts `ui_dist/` as static files at `/`
   - Reimplements the four API routes as FastAPI endpoints:
     - `GET /api/queue` → reads `~/.docent/data/reading/queue.json`
     - `POST /api/actions` → spawns `docent reading <action>` subprocess
     - `GET /POST /api/user` → reads/writes `~/.docent/user.json`
     - `GET/POST /api/config` → reads/writes `~/.docent/config.toml`
5. New `docent ui` CLI command → starts uvicorn on `localhost:7432` (configurable via `--port`), opens browser with `webbrowser.open()`

### `docent ui` server UX
Print on startup:
```
Docent UI is running at http://localhost:7432
Press Ctrl+C to stop.
```
No silent background daemon. Stop = Ctrl+C.

### pyproject.toml additions
- Add `fastapi`, `uvicorn[standard]` to dependencies
- Add package data include for `src/docent/ui_dist/**`

### Next.js changes needed
- Set `output: 'export'` in `next.config.ts`
- API routes folder removed (replaced by FastAPI) — local dev still uses them via `npm run dev`

### Ongoing maintenance cost (per new API endpoint)
Add it in **two places**: `frontend/src/app/api/<name>/route.ts` (Next.js, for local dev) AND `src/docent/ui_server.py` (FastAPI, for bundled release). Same logic, copy-paste job. Keep them in sync or local dev diverges from the release build.

**Why:** Confirmed by user on 2026-05-07. Deferred to next release milestone after current UI polish sprint.

# Brief: Split ui_server.py into route modules (item 28)

## Goal
`src/docent/ui_server.py` is 1250+ lines owning: reading-queue action routes, config routes, doctor/tooling routes, filesystem routes, Studio SSE streaming routes, Studio WebSocket subprocess routes, OpenCode process management routes, and static-file mounting. The review calls it "the worst case" for drift. Split it into focused modules.

## Target structure

```
src/docent/
├── ui_server.py          ← keep only: app creation, middleware, static mount, run_server()
├── ui_routes/
│   ├── __init__.py       ← empty
│   ├── reading.py        ← /api/reading/* action endpoints (post_action)
│   ├── config.py         ← /api/config GET+POST, /api/user GET+POST
│   ├── doctor.py         ← /api/doctor, /api/tooling
│   ├── filesystem.py     ← /api/fs/read, /api/fs/open, /api/fs/pick, /api/studio/outputs
│   ├── studio.py         ← /api/studio/run SSE streaming + StudioRunBody/ActionBody models
│   └── opencode.py       ← /api/opencode/start, /api/opencode/stop, /ws/studio/run WebSocket
```

## Rules
1. **Keep the FastAPI `app` object in `ui_server.py`** — each route module imports it and registers routes via `router = APIRouter(); app.include_router(router)` OR just `from docent.ui_server import app` and decorates directly. The simplest approach: each module imports `app` from `ui_server` and uses `@app.get/post` directly, no APIRouter needed.
2. **Shared helpers stay in `ui_server.py`**: `_docent_dir`, `_queue_file`, `_state_file`, `_config_file`, `_user_file`, `_read_json`, `_read_config_reading`, `_read_config_research`, `_mask_key`, `_run_command`, `_run`, `_version_at_least`, `_check_approved_path`, `_path_under`, `_audit`, `_LocalhostGuard`, `_SESSION_TOKEN`, `_audit_logger`, `_BACKEND_NORM`, `_STUDIO_ACTION_MAP`, and the Studio body parsing helpers (`_parse_studio_body`, `_args_to_cli`, `_build_studio_cmd`, `_form_to_studio_args`, `_stream_studio_run`). These are referenced by multiple route modules.
3. **Route modules import what they need from `ui_server`** — they must NOT import from each other.
4. **Route modules are imported at the bottom of `ui_server.py`** (after `app` is created) to trigger route registration.
5. **All existing routes must remain at the same URL paths** — this is a pure refactor with zero behavior change.
6. **Run `uv run pytest -x -q` after each module is extracted** to catch import errors early.

## Which endpoints go where

### `ui_routes/reading.py`
All routes that involve the reading tool:
- `POST /api/action` (post_action) — dispatches reading queue actions
- `GET /api/reading/queue`
- `GET /api/reading/state`

### `ui_routes/config.py`
- `GET /api/config`
- `POST /api/config`
- `GET /api/user`
- `POST /api/user`

### `ui_routes/doctor.py`
- `GET /api/doctor`
- `GET /api/tooling`

### `ui_routes/filesystem.py`
- `GET /api/fs/read`
- `POST /api/fs/open`
- `POST /api/fs/pick`
- `GET /api/studio/outputs`

### `ui_routes/studio.py`
- `GET /api/studio/run` (SSE streaming endpoint: `studio_run_sse`)
- `POST /api/studio/run` if any
- Body models: `StudioRunBody`, `ActionBody` (if not already in ui_server)

### `ui_routes/opencode.py`
- `POST /api/opencode/start`
- `POST /api/opencode/stop`
- `GET /api/opencode/status`
- `WebSocket /ws/studio/run` (subprocess streaming)

## Important: circular import avoidance
`ui_routes/*.py` files import from `ui_server.py` (for `app` and shared helpers). `ui_server.py` imports from `ui_routes/*.py` at the BOTTOM of the file, after everything is defined. Python handles this fine — just no top-level cross-imports between route modules.

## Verification
```bash
uv run pytest -x -q
python -c "from docent.ui_server import app, run_server; print('OK')"
```
All 502 tests must pass. No route paths may change.

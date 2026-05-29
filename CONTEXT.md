# CONTEXT - resume hint for next session

**Current Task:** Concurrent Studio runs (v1.3, Slice 1) — built and hardened. Client run-manager (`Map<runId>`) + server-side machine-level NotebookLM mutex; notebook-bound runs now research concurrently and only take turns at the brief NLM auth/push moments. All on `dev`, working tree clean.

**Key Decisions:**
- NLM exclusivity is enforced **server-side only** (filelock around auth in `_preflight_notebook_auth` + push in `_route_output`/`to_notebook`), NOT client-side — so research runs concurrently. Preflight auth is non-blocking (skips the probe when the session is busy).
- Pushes can't parallelize even to different notebooks: the shared Chromium **profile** (ProcessSingleton), not the notebook, is the constraint.
- Also shipped this session: draft `--confirmed` fix, free-backend guard, real Studio result panels (masked config), CI test-job relabel.

**Next Steps:**
- User: restart `docent ui` and verify two concurrent `deep → notebook` runs research in parallel.
- Slice 2 (future): server-side JobManager for true fire-and-forget queue that survives tab close (`memory/tasks/briefs/concurrent-studio-runs-design.md`).
- If GitHub branch protection requires a status check named `test`, rename it to "CLI (Python)" in repo settings.

# CONTEXT - resume hint for next session

**Current Task:** Feynman integration hardening — Windows subprocess hygiene, live stderr streaming, mtime-aware output detection, task-aware heads-up message. Council initially recommended stripping Feynman; investigation showed all failures were Docent-side bugs. Decision logged in `memory/decisions.md`.

**Key Decisions:**
- Keep Feynman; harden it. Fixes in `_run_feynman`: stdin=DEVNULL, UTF-8 encoding, streaming thread w/ exception capture, rglob + mtime snapshot, task-aware heads-up
- Default `feynman_timeout` bumped 900s → 1800s (empirical floor for `/review` with code-repo access)
- End-to-end smoke test green via no-cost `--version`; real `/review` validation deferred to next API-credit window

**Next Steps:**
1. Real `/review` validation when credits replenish — verify mtime detection copies output to `Research/<slug>.md`
2. File issue upstream re: `Promise.try` crash in `pi-web-access/unpdf` + broken npm package (`@aws-sdk/middleware-eventstream@^3.972.12` doesn't exist)
3. Tag v1.2.0 after real-life tests pass (`memory/tasks/studio_real_life_tests.md`)

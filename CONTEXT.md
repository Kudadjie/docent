# CONTEXT - resume hint for next session

**Current Task:** UI Tweak Followup (21 items) + live streaming shipped. Commit fd9f6b8 on dev.

**Key Decisions:**
- Live streaming: WebSocket + CLI subprocess pipe (`DOCENT_UI_SUBPROCESS=1`). Structured `\x00DOCENT_RESULT\x00` marker in stdout gives output_file without scraping wrapped Rich output.
- Phase log colours: violet=search, blue=write/plan, green=compile, teal=done, amber=warn, red=error.
- Phase filter: `^[a-z][a-z0-9_]*$` drops Feynman update notices and all non-pipeline stdout noise.

**Next Steps:**
1. Run v1.2.0 UI tests (`memory/tasks/v120_ui_tests.md`) — all UI items shipped, streaming works
2. Tag v1.2.0 and build release wheel: `python scripts/build_ui.py` then tag
3. Always use `http://localhost:7432` (not :3000) — the build step copies to `ui_dist`

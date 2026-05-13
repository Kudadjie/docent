# CONTEXT - resume hint for next session

**Current Task:** Plan D complete — `docent doctor` + `docent setup` shipped (commit 81feaa6 on dev). 326 tests green.

**Key Decisions:**
- Doctor: 10 checks in parallel (ThreadPoolExecutor); subprocess-free for feynman (package.json) and mendeley-mcp (shutil.which) to avoid Windows pipe-hang
- Plugin loader: bundled plugins imported as `docent.bundled_plugins.<name>` — fixes duplicate @register_tool warning
- Feynman package is `@companion-ai/feynman`; update source = GitHub releases (`companion-inc/feynman`)

**Next Steps:**
1. Real-life tests #10-19 (credits reset ~2026-05-17 17:00)
2. Tag v1.2.0 (after tests pass)
3. `docent doctor` auto-install idea (post-v1.2.0) — user wants doctor to offer installing missing tools

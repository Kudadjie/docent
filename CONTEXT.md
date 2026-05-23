# CONTEXT - resume hint for next session

**Current Task:** NotebookLM auth UX fixes shipped; UI test checklist sprint toward v1.2.0 tag continues.

**Key Decisions:**
- to-notebook pre-flight: blocks silently-failing runs at the WS layer before subprocess spawns; sends `nlm_auth_required` error directing user to Settings
- Settings NotebookLM section: detects missing Playwright Chromium binary and shows `playwright install chromium` fix inline (recurs after notebooklm updates — documented in UI)
- ResultFailure component fixed: was hardcoded "Anthropic 401" on every failure; now shows actual error-phase log text

**Next Steps:**
1. Run `uv run playwright install chromium` to unblock local NLM auth, then verify to-notebook end-to-end
2. Continue UI test checklist (Studio page items 10–27, then Ecosystem, Docs, Settings, Inbox, Sidebar, User Footer, Cross-cutting)
3. Fix any failures found, then tag v1.2.0

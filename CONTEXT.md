# CONTEXT - resume hint for next session

**Current Task:** Studio plugin split complete (2460→1379 lines in __init__.py); performance profiling done.

**Key Decisions:**
- Studio split: feynman.py (415L), helpers.py (88L), models.py (336L), preflights.py (246L); 316 tests green
- Warm-cache reader path is fast (2.7ms avg); cold cache (~10s Mendeley MCP) is the real UX problem
- Pre-existing test failure: test_output_notebook_pushes (Playwright not installed on Windows)

**Next Steps:**
1. Run studio real-life tests #10–#19 (OpenCode credits reset ~2026-05-17 17:00)
2. Tag v1.2.0 after real-life tests pass
3. Cold cache UX: add spinner/message when Mendeley MCP is warming up on first call

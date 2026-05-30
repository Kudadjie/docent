# CONTEXT - resume hint for next session

**Current Task:** Backlog session wrapped. Tier 1–3 all done + committed on `dev`. Working tree clean (only `_version.py` build artifact + `.gstack` log).

**Key Decisions:**
- Zotero bridge (#36) SHIPPED + committed (6fbb363): `ZoteroBackend` (pyzotero, API key) behind the existing `ReferenceManagerBackend` protocol; `reading.reference_manager` toggle. Verified against LIVE Zotero API. #35a (Mendeley httpx swap) DROPPED. See decisions.md 2026-05-30.
- Schema-driven forms (#22): generic `/tools` page (9c5b6f6 + 047043c). Plugin docs (#35): done.
- Both full suites GREEN on Windows + WSL. Fixed 2 non-hermetic NLM tests (620ae05) + recorded WSL-venv gotcha (c76749c).

**Next Steps (future session — Tier 4+):**
- Tier 4 harness items (before v2.1.0): prompts-as-first-class-code eval, sub-agent fan-out formalization, model-facing surface review.
- Tier 5/6: Obsidian, Overleaf, HTTP+SSE MCP, Omnibox, citation scavenger.
- **WSL testing:** use `~/docent-venv` (native ext4, 3.12+), NOT `.venv-wsl` (3.11, on slow /mnt/c) or `/tmp` (wiped on idle). See gotchas.md.

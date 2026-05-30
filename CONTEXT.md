# CONTEXT - resume hint for next session

**Current Task:** Backlog: Tier 1–3 done, incl. schema-driven `/tools` page AND the Zotero bridge. Zotero is uncommitted on `dev`.

**Key Decisions:**
- Zotero bridge (#36): SHIPPED. `ZoteroBackend` (pyzotero, API key) behind the existing `ReferenceManagerBackend` protocol; `reading.reference_manager` toggle. #35a (Mendeley httpx swap) DROPPED — it means reimplementing Mendeley OAuth and isn't a prerequisite. **Verified against LIVE Zotero API.** See decisions.md 2026-05-30.
- Schema-driven forms (#22): generic `/tools` page (committed: 9c5b6f6 + 047043c).
- Plugin docs (#35): done.

**Next Steps:**
- Commit the Zotero work (uncommitted on `dev`): settings.py, reading/ (zotero_client/backend, __init__, mendeley_sync), cli.py, cli_doctor.py, pyproject (pyzotero dep), docs, tests. Run safe-commit/build not needed (no frontend change).
- Tier 4 harness items (before v2.1.0): prompts-as-first-class-code eval, sub-agent fan-out formalization, model-facing surface review.
- Note: `.venv-wsl` was stale (missing alphaxiv/notebooklm) — synced via `pip install -e .`.

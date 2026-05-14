# CONTEXT - resume hint for next session

**Current Task:** Studio output destinations + notebooklm-py integration landed. Pre-v1.2.0 tag work.

**Key Decisions:**
- `research` tool renamed → `studio`; `deep` → `deep-research`; plugin dir renamed with git history
- `to-notebook` now creates new NLM notebooks via `notebooklm-py` CLI (package: `notebooklm-py`)
- `--output local|notebook|vault` added to `deep-research`, `lit`, `review`
- `config.toml [research]` section intentionally NOT renamed (breaking change deferred)
- uv.lock not updated for `notebooklm-py` (file lock on docent.exe); will resolve on next free sync

**Next Steps:**
1. Real-life tests #10–#19 (Feynman/OpenCode credits reset ~2026-05-17 17:00) — still blocked
2. UI spec for Studio tool (`/ui-spec-writer studio`)
3. Tag v1.2.0 (after real-life tests pass)

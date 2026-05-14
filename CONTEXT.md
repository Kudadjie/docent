# CONTEXT - resume hint for next session

**Current Task:** Studio `to-notebook` full pipeline port + self-learning hooks. New `_notebook.py` (749+ lines).

**Key Decisions:**
- `to-notebook` now runs full 4-phase pipeline mirroring `research-to-notebook` skill (NLM research arm, stabilise, quality gate, perspectives)
- Self-learning: writes back to `source-compat.json` (per-domain outcomes), `run-log.jsonl`, reads `active-overrides.json`
- `guide_file` param added to all studio actions; `to-local` standalone action added

**Next Steps:**
1. Reinstall: `uv tool install --python 3.13 --reinstall --editable .`
2. Real-life tests #10–#19 (credits reset ~2026-05-17 17:00)
3. Tag v1.2.0 after real-life tests pass

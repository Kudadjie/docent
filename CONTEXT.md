# CONTEXT — resume hint for next session

**Current Task:** Phase 1.5-A Output Shapes landed; AGENTS.md + contract tests are next.

**Key Decisions:**
- Output Shapes: 7 types in `core/shapes.py`; `ui/renderers.py` Rich dispatcher; all 10 reading results have `to_shapes()`. 141 tests green.
- `oc_delegate.py` gained `--stream` flag (SSE `/event` endpoint, live token + tool-call feed).
- Brief convention: project-specific imports/fixtures must be explicit. See `memory/feedback_oc_brief_conventions.md`.

**Next Steps:**
1. Phase 1.5-B: `AGENTS.md` (3-rule max, architecture invariants)
2. Phase 1.5-B: Contract tests for Tool ABC + registry + dispatcher
3. Phase 1.5-C: `research-to-notebook` skill port (Feynman primary, litellm fallback)

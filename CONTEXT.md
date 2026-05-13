# CONTEXT - resume hint for next session

**Current Task:** CI gap found — tests never run on tag push. Fix before v1.2.0 tag.

**Key Decisions:**
- #27 (setup-node SHA pin) already done — todo was stale
- publish.yml has no pytest step: build goes straight to PyPI without running 340 tests
- Todos restructured to align with Academic Workstation vision phases (v1.3–v2.0+)

**Next Steps:**
1. Add pytest + ruff to publish.yml before the build step (item #28) — START HERE
2. Real-life tests #10–#19 (Feynman/OpenCode credits reset ~2026-05-17 17:00)
3. Tag v1.2.0 (after CI fixed + tests pass)

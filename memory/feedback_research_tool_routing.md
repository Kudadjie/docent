---
name: Studio tool — Feynman routing (no auto-fallback)
description: The studio tool has two explicit backends — feynman (default) and docent (native pipeline). No automatic litellm/Claude fallback exists.
type: feedback
---

The `studio` tool routes through the Feynman agent CLI as primary (`--backend feynman`, the default). The explicit alternate is `--backend docent` — the Docent-native 6-stage pipeline (search-planner → fetch → gap-eval → writer → verifier → reviewer) via OpenCode/OcClient. There is also `--backend free` (Tavily + academic search, no LLM synthesis). There is no automatic litellm/Claude fallback.

**Why:** Feynman is the preferred research agent (deeper, citation-aware). The docent-native backend uses OpenCode Go models (zero Anthropic API cost) and is selected explicitly, not silently on failure. The original plan called for a litellm fallback but was never implemented — the shipped design uses three explicit user-selectable backends.

**How to apply:** When the user calls `docent studio deep-research` / `docent studio lit`, backend defaults to `feynman`. If they want the native pipeline (or Feynman is not installed), they pass `--backend docent`. For a no-cost aggregation-only run, `--backend free`. Do not design for an automatic litellm fallback — it does not exist.

**Note:** The tool was renamed from `research` → `studio` in v2.0.0 (commit `42ccba7`). All references to `docent research` in old notes are stale.

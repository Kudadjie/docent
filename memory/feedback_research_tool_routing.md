---
name: Research tool — Feynman routing with self-fallback
description: The research tool routes LLM calls through Feynman first; falls back to Claude itself if Feynman is unavailable
type: feedback
---

The `research` tool routes through the Feynman agent CLI as primary (`--backend feynman`, the default). The explicit alternate backend is `--backend docent` — the Docent-native 6-stage pipeline (search-planner → fetch → gap-eval → writer → verifier → reviewer) via OpenCode/OcClient. There is no automatic litellm/Claude fallback.

**Why:** Feynman is the preferred research agent (deeper, citation-aware). The docent-native backend uses OpenCode Go models (zero Anthropic API cost) and is selected explicitly, not silently on failure. The original plan called for a litellm fallback but was never implemented — the shipped design uses two explicit user-selectable backends.

**How to apply:** When the user calls `docent research deep/lit`, backend defaults to `feynman`. If they want the native pipeline (or Feynman is not installed), they pass `--backend docent`. Do not design for an automatic litellm fallback — it does not exist.

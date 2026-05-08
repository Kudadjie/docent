---
name: Research tool — Feynman routing with self-fallback
description: The research tool routes LLM calls through Feynman first; falls back to Claude itself if Feynman is unavailable
type: feedback
---

The `research` tool (planned Phase 1.5) routes through the Feynman agent CLI as primary. If Feynman is unavailable or fails, Docent falls back to calling Claude directly (self-default).

**Why:** Feynman is the preferred research agent (deeper, citation-aware), but the tool should still work without it installed.

**How to apply:** When designing the research tool's LLM call layer, implement Feynman as the primary executor and wrap it in a try/fallback that routes to Claude via litellm on failure. Don't hard-require Feynman as a dependency.

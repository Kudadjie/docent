---
name: opencode-usage-limits
description: OpenCode/Hermes delegation is currently unavailable due to usage limit exhaustion; Claude sub-agents are the fallback
metadata:
  type: project
---

OpenCode usage limits were hit on 2026-05-13. Hermes delegation (`hermes_delegate.py`) and OpenCode one-shot delegation (`oc_delegate.py`) are both blocked until credits reset (~2026-05-17 17:00).

**Why:** OpenCode API quota exhausted — not a code issue, purely a billing/usage cap.

**How to apply:** Route all delegation to Claude sub-agents (Agent tool) instead of Hermes/OpenCode scripts. Model routing still applies:
- Haiku → cheap lookups, single-file reads, boilerplate
- Sonnet → multi-file implementation, test writing
- Worktree isolation (`isolation: "worktree"`) for any agent making code changes

Parallel worktree agents replace the Hermes "run pytest until green" loop — spawn two agents for independent todos, review both, merge.

Note: sub-agents don't auto-read `memory/` — summarize relevant context in the prompt when delegating.

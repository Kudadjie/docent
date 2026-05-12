---
name: Use OpenCode for Docent agentic tooling
description: When building agentic LLM-calling tools inside Docent, route LLM calls through OpenCode's session API (not Anthropic API) to avoid extra billing
type: feedback
---

Use OpenCode Go subscription models as the LLM backend for any agentic tooling built inside Docent.

**Why:** User is already paying for OpenCode Go sub. Using Anthropic API for Docent's internal agentic tools would add extra billing on top of existing subscriptions. Since we control the call pattern in Docent (unlike external tools like Feynman), we can design tool actions as single well-structured briefs and route them through OpenCode's session API via `oc_delegate.py` or a direct API call.

**How to apply:**
- When designing a Docent tool that needs an LLM call (summarise, extract, annotate, classify, etc.), default to OpenCode as the backend
- Structure the LLM interaction as a single-shot brief (not multi-turn) — Claude Code/orchestration layer handles any multi-step logic
- Use `oc_delegate.py` for delegation or call `http://127.0.0.1:4096` session API directly from Python
- Only fall back to Anthropic API if the task genuinely requires Claude-specific capabilities (tool use, long structured reasoning, etc.)
- The first agentic tool to apply this pattern: whatever comes after the reading tool rewrite

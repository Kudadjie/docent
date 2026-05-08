---
name: Research tool real-life test blockers (2026-05-08)
description: Two bugs found during first real-life test pass of research-to-notebook; block tests 3-17; fix before v1.2.0 tag
type: project
---

Two bugs found 2026-05-08 during real-life testing (tests 1-2 passed; tests 3+ blocked).

## Bug 1 — Duplicate tool registration (test #3: `docent research usage`)

`ValueError: Tool name 'research' is already registered by research_to_notebook.ResearchTool; cannot re-register from docent.bundled_plugins.research_to_notebook.ResearchTool`

The research tool is being registered twice under the same name. Root cause is likely a double-import or double-registration path in the plugin loader. Fix: deduplicate registration — guard with a name-already-registered check or consolidate import path.

## Bug 2 — Missing `duckduckgo_search` dep (test #4: `docent research deep`)

`ModuleNotFoundError: No module named 'duckduckgo_search'`

**Decision:** Drop `duckduckgo_search` entirely. Switch web search/fetch in the research pipeline to **Tavily**.
- Tavily is designed specifically for LLM/agentic research pipelines; returns clean structured snippets (no HTML parsing needed).
- Free tier: 1,000 calls/month — enough headroom for real research use.
- Tavily API key to be stored in config (`~/.docent/config.toml` under `[research]`, key: `tavily_api_key`).
- Add Tavily request count tracking: count calls made against the 1,000/month quota, expose in `docent research usage`.

**Why Tavily over alternatives:**
- SerpAPI: only 250 req/month free — too tight for a research tool (one deep run = 5–15 queries).
- Perplexity Sonar: answer engine, not a search API — returns pre-synthesized answers, clashes with Docent's own synthesis pipeline, no real free tier.
- Tavily: purpose-built for agentic pipelines, most generous free tier, clean output.

**How to apply:** When implementing, add a `tavily_requests` counter to the spend-tracking file (`~/.docent/cache/research/`) and show it in `usage` output alongside Feynman/OC spend.

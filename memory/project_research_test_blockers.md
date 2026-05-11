---
name: Research tool real-life test blockers (2026-05-08)
description: Two bugs found during first real-life test pass of research-to-notebook; block tests 3-17; fix before v1.2.0 tag
type: project
---

Two bugs found 2026-05-08 during real-life testing (tests 1-2 passed; tests 3+ blocked).

## Bug 1 — Duplicate tool registration (FIXED 2026-05-11)

Root cause: absolute import `from docent.bundled_plugins.research_to_notebook.oc_client` in `usage()` caused `__init__.py` to execute under different `sys.modules` key. Fix A: relative import. Fix B: registry guard warns + skips on duplicate.

## Bug 2 — Missing `duckduckgo_search` dep (FIXED 2026-05-11)

Replaced DDG with Tavily across 6 files: `pyproject.toml`, `settings.py`, `search.py`, `__init__.py`, `pipeline.py`, `docs/cli.md`, `README.md`. Tavily request counter added to `~/.docent/cache/research/tavily_spend.json`. API key stored in config under `[research] tavily_api_key` or env `DOCENT_RESEARCH__TAVILY_API_KEY`.

STATUS: Both bugs fixed (2026-05-11, Hermes session). Tests #3-17 pending — needs WSL venv + Tavily API key in config.

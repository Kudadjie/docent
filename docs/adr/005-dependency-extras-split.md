# ADR-005: Heavy dependencies move to opt-in extras; core install stays light

**Status:** Active
**Date:** 2026-07-01
**Deciders:** John David K. T. Kudadjie

---

## Context

`pip install docent-cli` had grown to install, as mandatory dependencies:
`litellm` (very large, recurring CVE suppressions), `notebooklm-py[browser]`
(a browser-automation stack), `scholarly`, `alphaxiv-py`, `pyzotero`, `ddgs`,
and `tavily-python`. A user who wants only the reading queue paid the full
install-time, disk, and attack-surface cost of the AI research stack. This
contradicted the project's stated identity ("a light personal CLI control
center") and inflated the pip-audit suppression list. The codebase already
lazy-imported or guard-imported most of these — only packaging lagged.

## Decision

- **Core** (`docent-cli`): reading queue, web UI, MCP server — typer, rich,
  pydantic-settings, fastapi/uvicorn, httpx, mcp, filelock, tomli-w.
- **Extras:** `studio` (litellm, tavily-python, ddgs, scholarly, alphaxiv-py),
  `notebook` (notebooklm-py[browser]), `zotero` (pyzotero), `backup`
  (pre-existing Google Drive extra), and `all` (union — the pre-split surface).
- **Graceful degradation:** a new `MissingExtraError` (D009, in
  `docent.errors`) is raised at every lazy-import boundary, naming the feature
  and the exact `pip install 'docent-cli[extra]'` command. The CLI renders it
  as a clean one-liner (Rich markup escaped so the bracketed extra prints).
- **CI and dev environments** install with `--all-extras`; the full test
  suite always runs against the complete dependency set. A core-only smoke
  test verifies all bundled plugins load without any extras installed.

## Consequences

**Good:**
- Base install is a fraction of the size; litellm CVE churn no longer taxes
  reading-queue-only users.
- The install command doubles as documentation of what Docent actually is:
  core + optional capabilities.

**Trade-offs:**
- **Upgrade breakage risk:** existing users who upgrade the bare package lose
  Studio/NotebookLM/Zotero until they reinstall with `[all]`. Mitigated by a
  loud CHANGELOG entry and the self-explanatory D009 error; release-version
  implications decided at tag time.
- README/docs must recommend `docent-cli[all]` as the default install to keep
  the happy path one command.

**Rejected alternatives:**
- **Keep everything mandatory:** the status quo problem.
- **Separate PyPI packages (docent-studio, …):** heavier to maintain and
  version-sync than extras, with no additional benefit for a single-repo tool.

## Related

- `pyproject.toml` — `[project.optional-dependencies]`
- `src/docent/errors.py` — `MissingExtraError` (D009)
- Guarded import sites: `llm/client.py`, `studio/backend.py`,
  `studio/alphaxiv_client.py`, `studio/search.py`, `studio/free_research.py`,
  `reading/zotero_client.py`

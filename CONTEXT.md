# CONTEXT - resume hint for next session

**Current Task:** Tier-4 B fan-out + --expand-citations fully shipped (694 tests green, Win).

**Key Decisions:**
- `fanout.py: parallel_fetch()` — ThreadPoolExecutor, submission-order results, per-task
  None on failure; inserted at action layer (not pipeline internals).
- `--expand-citations` on deep-research + lit (docent backend): parallel cite-graph fetch
  on top anchor DOIs → enrichment LLM pass (citation_enricher.md) synthesises OA abstracts
  into draft; quality guard (≥50% original length); fallback to appended list if it fails.
- UI toggle added to FormTopic (deep/lit only, dimmed with note on non-Docent backends).

**Next Steps:**
- Run WSL test suite before merging (CI runs Linux — mandatory gate).
- PR dev → main.

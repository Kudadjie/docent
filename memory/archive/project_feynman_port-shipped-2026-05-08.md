---
name: Feynman Port — Docent Research Tool Suite (SHIPPED)
description: Pre-implementation plan for the research-to-notebook tool (Phase 1.5-C). Feature shipped 2026-05-08. Archived 2026-05-11.
type: project
---

**STATUS: SHIPPED** as `src/docent/bundled_plugins/research_to_notebook/`. Archived from `memory/project_feynman_port.md` on 2026-05-11.

**Key deviations from the original plan:**
- Backend default is `feynman` (not a runtime prompt — Feynman is the default, `--backend docent` is explicit).
- Web search uses **Tavily** (not duckduckgo-search, which was removed in v1.2.0).
- `research-to-notebook` command was simplified to `research` (actions: `deep`, `lit`, `review`, `usage`, `config-show`, `config-set`).
- No `to-notebook` (NotebookLM) phase shipped yet — deferred.
- Plugin location: `src/docent/bundled_plugins/research_to_notebook/` (matches plan).

---

## Original plan summary (for historical reference)

Build the research stage of `research-to-notebook` (Phase 1.5-C) with two selectable backends.

- **Backend 1 (Feynman):** shell out to `feynman deepresearch/lit/review`, copy output to `research_output_dir`.
- **Backend 2 (Docent-native):** search-planner → web+paper fetch → gap-eval → writer → verifier → reviewer, all via OpenCode Go models.

Feynman architecture reference (agents: researcher/reviewer/verifier/writer; workflows: deepresearch/lit/review/replicate/compare/draft/autoresearch) preserved at `C:\Users\DELL\AppData\Local\Programs\feynman\feynman-0.2.17-win32-x64\app\`.

Build phases A–C shipped 2026-05-08. Phase D (NotebookLM) and Phase E (remaining Feynman workflows) are deferred — see `roadmap_post_phase1.md`.

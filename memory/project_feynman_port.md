---
name: Feynman Port — Docent Research Tool Suite (ARCHIVED)
description: ARCHIVED 2026-05-11 — feature shipped. See archive/project_feynman_port-shipped-2026-05-08.md
type: project
---

**ARCHIVED.** Research tool shipped 2026-05-08. Key deviations from plan: Feynman is now the default backend (not a runtime prompt); Tavily replaced duckduckgo-search (v1.2.0). Full record at `archive/project_feynman_port-shipped-2026-05-08.md`.

## Decision

Build the research stage of `research-to-notebook` (Phase 1.5-C) with two selectable backends. No default — user is always prompted to choose at runtime.

**Why:** Feynman is excellent but costs Anthropic API tokens. A Docent-native pipeline using duckduckgo-search + alpha + OpenCode achieves comparable quality at zero marginal cost. Both options are valid; user decides per-run based on cost tolerance and quality preference.

**How to apply:** When implementing `research-to-notebook`, the research stage always prompts the user to pick a backend before proceeding. The notebook stage (NotebookLM integration) is a separate phase and comes after the research stage is complete.

---

## Feynman's Architecture (source of truth)

Installed at: `C:\Users\DELL\AppData\Local\Programs\feynman\feynman-0.2.17-win32-x64\app\`

### Four subagent roles (`.feynman/agents/`)
| Agent | Role | Thinking level |
|---|---|---|
| `researcher` | Evidence gathering — web + papers + repos. Integrity commandments. Evidence table format. | high |
| `reviewer` | Adversarial peer review — FATAL/MAJOR/MINOR + inline annotations. | high |
| `verifier` | Citation anchoring + URL verification. Adds `[N]` inline citations to drafts. | medium |
| `writer` | Turns research notes into structured drafts. No citations (verifier handles that). | medium |

### Nine workflow prompts (`prompts/`)
| Prompt | What it does |
|---|---|
| `deepresearch.md` | Full 8-step pipeline: plan → parallel researchers → evaluate/loop → write → cite → verify → deliver |
| `lit.md` | Literature review: plan → gather → synthesize → cite → verify → deliver |
| `review.md` | Peer review: researcher gathers evidence → reviewer produces review with inline annotations |
| `replicate.md` | Replication plan/execution: extract → plan → environment → execute → log → report |
| `compare.md` | Source comparison matrix: plan → researcher → verifier → matrix output |
| `draft.md` | Paper-style draft: outline → writer → verifier |
| `autoresearch.md` | Autonomous experiment loop (optimize a metric, iterate until max N) |
| `audit.md` | (not read — likely code/claim audit) |
| `watch.md` | (not read — likely topic watch/monitoring) |

### Core patterns
- **Lead agent**: plans, delegates, synthesizes, delivers. Never dumps large intermediates back to parent.
- **File-based handoffs**: subagents write to `<slug>-research-*.md`, lead reads files. Slug derived from topic.
- **Output conventions**: `outputs/`, `papers/`, `outputs/.plans/`, `outputs/.drafts/`, `notes/`
- **Provenance sidecar**: every final output gets a `<slug>.provenance.md`
- **CHANGELOG.md**: lab notebook for multi-round runs
- **Acceptance criteria**: ≥2 independent sources per critical claim, no single-source critical findings

---

## Docent Translation

### Context
This is the research stage of `research-to-notebook` (Phase 1.5-C). The notebook stage (NotebookLM integration) is a separate subsequent phase.

### Entry point UX
```
docent research-to-notebook "storm surge Ghana"

? Which research backend?
  [1] Docent pipeline  (web search + alpha + OpenCode — free)
  [2] Feynman          (Feynman CLI — uses Anthropic API tokens)
```
No default. User must choose. Same interface regardless of backend. Both produce a research output file that feeds the notebook stage.

### Backend 1: Feynman CLI delegation
- Shell out to `feynman <workflow> "<topic>"` (already installed at `C:\nvm4w\nodejs\feynman`)
- Feynman writes to its own `outputs/` dir
- Docent copies the result to `research_output_dir`
- Workflows: `feynman deepresearch`, `feynman lit`, `feynman review`
- Cost: Anthropic API tokens (Feynman's normal behaviour)

### Backend 2: Docent pipeline (standalone CLI, zero cost)
- Web search: `duckduckgo-search` Python package (free, no API key)
- Paper search: `alpha` CLI (free)
- All LLM stages: OpenCode via `oc_delegate.py` (Go sub, free)
- Fully standalone — no Claude Code session dependency

### Plugin location
`src/docent/bundled_plugins/research_to_notebook/` — same pattern as `src/docent/bundled_plugins/reading/`.

Expected package layout:
```
src/docent/bundled_plugins/research_to_notebook/
    __init__.py              ← registers the tool
    research_to_notebook.py  ← ResearchToNotebookTool (actions: deep, lit, review)
    search.py                ← _web_search(), _alpha_search(), _fetch_pages()
    pipeline.py              ← orchestrates the 5-stage Docent pipeline
    agents/
        researcher.md        ← adapted from Feynman (pi-charts → Rich, rest verbatim)
        writer.md
        verifier.md
        reviewer.md
    workflows/
        deep.md              ← search planner + gap evaluator prompts
        lit.md
        review.md
```

### Output directory
Configurable via `research.output_dir` in Docent config (default: `~/Documents/Docent/research/`).

---

## Full pipeline (all three priority workflows)

### Shared pipeline stages (all workflows)

```
Search planner (OpenCode/GLM)
  → Python fetches results + pages
  → Gap evaluator (OpenCode/GLM) — loop if needed
  → Writer (OpenCode/minimax or GLM)
  → Verifier (OpenCode/GLM)
  → Reviewer (OpenCode/deepseek-v4-pro)
  → Output + provenance sidecar
```

### 1. `docent research deep "<topic>"` — Deep Research

Search strategy: balanced web + papers.
- Search planner generates: 6 web queries (varied angles) + 4 alpha queries + 2 domain-targeted queries (govt, institutional)
- Rounds: 1-2 typical, up to 3 if gaps found by gap evaluator
- Output sections: Executive Summary, thematic findings, Open Questions
- Output: `outputs/<slug>.md` + `outputs/<slug>.provenance.md`

### 2. `docent research lit "<topic>"` — Literature Review

Search strategy: paper-heavy, minimal web.
- Search planner generates: 6 alpha queries (semantic + keyword) + 2 web queries (surveys, review papers only)
- No domain-targeted queries
- Synthesis organises by: consensus findings / active disagreements / open questions / proposed next experiments
- Reviewer checks: zombie sections, single-source critical findings, benchmark leakage
- Output: `outputs/<slug>-lit.md` + provenance sidecar

Difference from deepresearch: search planner is told to bias 80% toward academic sources. Synthesis prompt emphasises inter-paper comparison, not just topic coverage.

### 3. `docent research review "<artifact>"` — Peer Review

Artifact can be: arXiv ID, local PDF path, or URL.
- **No search planner.** The artifact IS the input.
- Researcher stage: fetch artifact + verify cited sources (alpha get + URL checks)
- Skip writer stage — reviewer writes directly
- Reviewer produces: structured review (FATAL/MAJOR/MINOR) + inline annotations quoting exact passages
- If FATAL issues found: fix pass → re-review
- Output: `outputs/<slug>-review.md`

Difference from deepresearch/lit: no search loop. One researcher pass to gather evidence, then straight to reviewer.

---

## Build Phases

### Phase A — tool skeleton + Feynman backend (1 session)
1. Create `src/docent/tools/research_to_notebook.py` with `ResearchToNotebookTool` skeleton
2. Backend prompt: Rich panel asking user to choose Feynman or Docent pipeline
3. Wire Feynman backend: shell out to `feynman deepresearch/lit/review`, copy output to `research_output_dir`
4. Config: `research_output_dir` setting
5. Smoke test: `docent research-to-notebook deep "storm surge Ghana"` → Feynman runs, output copied

### Phase B — Docent pipeline backend, deep workflow (1 session)
6. Add `duckduckgo-search` dep to `pyproject.toml`
7. Implement search layer: `_web_search()`, `_alpha_search()`, `_fetch_pages()`
8. Store agent prompts in `src/docent/tools/agents/` (researcher, writer, verifier, reviewer)
9. Wire 5-stage pipeline: search-planner → fetch → gap-eval → writer → verifier → reviewer
10. Smoke test: Docent pipeline option for `deep`

### Phase C — lit + review on Docent pipeline (1 session)
11. `lit` action — same pipeline, search planner biased 80% toward alpha queries
12. `review` action — no search planner, researcher fetches artifact → reviewer
13. Smoke tests for both on Docent pipeline backend

### Phase D — notebook stage (separate, future)
- NotebookLM integration: take research output, push sources into a NotebookLM notebook
- This is the "to-notebook" half of `research-to-notebook`

### Phase E — remaining Feynman workflows (deferred)
- `compare`, `draft`, `replicate`, `audit`, `watch` on both backends

---

## Skills folder (`.feynman/app/skills/`)

Thin SKILL.md wrappers — no new logic. Each just points to a workflow prompt. Full list:
`alpha-research`, `autoresearch`, `contributing`, `deep-research`, `docker`, `eli5`, `jobs`,
`literature-review`, `modal-compute`, `paper-code-audit`, `paper-writing`, `peer-review`,
`preview`, `replication`, `runpod-compute`, `session-log`, `session-search`, `source-comparison`, `watch`

These are the *same* skills already installed to `~/.claude/skills/` — Feynman installs them there on setup. No new substance vs what's already available in Claude Code.

Notable extras not yet covered by our prompts:
- `audit.md` — paper vs codebase claim comparison (claims → code mismatches, missing code, bad defaults)
- `watch.md` — recurring research watch using `schedule_prompt`; creates baseline then schedules follow-ups
- `session-search` — searches past Feynman JSONL session transcripts at `~/.feynman/sessions/`
- `jobs.md` — lists active background processes and scheduled follow-ups

---

## OpenCode / WebSearch verification result

**OpenCode does NOT have a web_search tool.** `oc_delegate.py` sends plain text to the OpenCode REST API. Tools available to the model are whatever OpenCode's server exposes (standard coding tools: read, bash, grep, write, edit). Web search is not a coding tool — it is not in OpenCode's toolset.

Feynman's `web_search` is **Pi's own tool** (the Claude Code subagent runtime), not a generic tool that maps to OpenCode.

### Architecture consequence (final)

Docent research tool is fully standalone CLI — no Claude Code session dependency.

| Stage | Runs as | Cost |
|---|---|---|
| Search planner | OpenCode brief (GLM) | Free (Go sub) |
| Web search + page fetch | Python: `duckduckgo-search` | Free |
| Paper search | Bash: `alpha search` | Free |
| Gap evaluator | OpenCode brief (GLM) | Free (Go sub) |
| Writer | OpenCode brief (minimax-m2.7) | Free (Go sub) |
| Verifier | OpenCode brief (GLM) | Free (Go sub) |
| Reviewer | OpenCode brief (deepseek-v4-pro) | Free (Go sub) |

---

## Key risks
- **Subagent concurrency**: OpenCode handles one brief at a time. True parallel researcher dispatch (Feynman's `concurrency: 4`) requires parallel `Agent` tool calls in the main session — supported natively in Claude Code.
- **Context size for multi-round runs**: Long research runs accumulate large intermediate files. File-based handoffs (same as Feynman's pattern) keep main context clean.
- **alpha CLI auth**: Researcher depends on `alpha search` being authenticated. If `alpha login` expires, paper search silently degrades to web-only.

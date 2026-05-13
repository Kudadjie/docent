# Analysis: "Docent in the Near Future" Vision Document

Source: `txt/done/docent in the near future.txt` (6KB, 2-line layout)
Analyzed: 2026-05-12 by Hermes (deepseek-v4-pro)

## Summary of the vision document

The document outlines expanding Docent from a personal grad-school script into an **All-Around Academic Workstation** — a local-first orchestrator that serves as "connective tissue" between fragmented academic tools. It proposes four phases:

| Phase | Domain | Key Integration | Complexity |
|-------|--------|----------------|------------|
| 1 | Ingestion | Zotero SQLite bridge, ASReview agentic screening | Low |
| 2 | Discovery | Semantic Scholar / Crossref API scavenger, background PDF retrieval | Medium |
| 3 | Workspace | Obsidian sidecar, Overleaf Git .tex sync, Paperpal-style lint guardrail | Low |
| 4 | Analysis | Atlas.ti alternative (qualitative coding), R/Python data scaffolders | High |

Recommendation: start with the Ingestion-to-Workspace bridge (Zotero → Reading Queue → Studio → Obsidian).

## What the vision gets right

1. **Correct pain point.** Academic tool fragmentation is real and expensive. Researchers spend disproportionate time on manual data movement between tools. Docent as orchestrator is the right framing.

2. **Sensible phase ordering.** Ingestion → Discovery → Writing → Analysis matches actual research workflow. Each phase unlocks value before the next begins.

3. **Honest complexity ratings.** Zotero bridge = Low/High ROI is accurate. Atlas.ti replacement = High complexity is realistic — qualitative coding is a multi-year problem, not a plugin.

4. **Strong architectural fit.** Docent's local-first storage, plugin architecture, and Hermes AI agent make it genuinely well-suited for this role. This isn't a square-peg vision.

## Gaps and risks

### 1. Mendeley is missing from the vision
Docent already ships with `mendeley_sync.py` and Mendeley integration in the reading plugin. The vision document only mentions Zotero. Researchers are tribal about reference managers — supporting both is a competitive advantage. The vision should address: does Mendeley become deprecated, coexist as a parallel bridge, or get phased out?

### 2. Undersells Docent's actual architecture
The document frames Docent as "connective tissue" (passive pipe: detect → copy → queue). But Docent's real power is what happens *after* ingestion: Hermes autonomously reading, synthesizing, tagging, and cross-referencing. The vision mentions this but doesn't center it. Docent is a workstation kernel, not just glue.

### 3. Citation graph analysis difficulty understated
Phase 2's "download top 5 highly cited relevant PDFs" sounds straightforward but requires solving: (a) relevance ranking beyond citation count, (b) open-access availability filtering (paywalls), (c) deduplication across API sources. This is Hard, not Medium.

### 4. No resource/concurrency model
If Hermes is monitoring Zotero, running citation scavengers, linting LaTeX, and doing qualitative coding simultaneously — what's the resource budget? A laptop with 8GB RAM can't run four LLM pipelines at once. Needs: task prioritization, queuing, model selection (cheap model for screening, premium for synthesis).

### 5. Third-party tooling check is critical but underdeveloped
The document's closing note — "something that checks if third party tools are installed and offer to auto install, ensure Auth or APIs are sorted" — is a whole subsystem. This needs: tool discovery, graceful degradation when tools are missing, API key management across Zotero/Semantic Scholar/Overleaf/etc. This is the thing that makes or breaks "it just works" for non-technical researchers. Worth its own dedicated design doc.

### 6. Missing: Developer Experience / plugin stability
If Docent becomes an ecosystem with third-party integrations, the plugin API must be documented, stable, and trivially testable. Phase 0 should be: stabilize the plugin contract and ship developer docs so community contributors can build Zotero bridge, Overleaf sync, etc. as plugins in parallel.

## Alignment with existing roadmap

The existing `roadmap_post_phase1.md` already covers:
- v1.2.0: hardening sprint (UI server, reading split, research DRY-up) + medium debt + v1.3 planning
- v1.3: `docent doctor` onboarding command, Hermes stream view
- v1.4: Obsidian integration
- Parked: plugin builder spec, calendar

The vision document's Phase 1 (Zotero bridge) aligns with the already-planned `project_zotero_integration.md`. Phase 3 (Obsidian sidecar) aligns with v1.4's Obsidian integration. The vision document provides the "why" and the long arc; the existing roadmap provides the "how" and the immediate next steps.

## Recommendation for synthesis

1. **Treat the vision document as the 2-3 year North Star**, not the immediate build plan.
2. **Phase 0 (now): Plugin API stabilization.** Before any new integrations, ship the plugin contract and developer docs so integrations can be built by anyone.
3. **Phase 1 (v1.3-v1.4): Zotero bridge + Obsidian sidecar.** These are already in the roadmap. Execute them as designed.
4. **Phase 2-4 (v2.0+):** Citation scavenger, Overleaf sync, qualitative coding — revisit after Phase 1 ships and real usage data exists.
5. **Write a dedicated "Third-Party Tool Management" design doc** covering discovery, install, auth, and graceful degradation. This is the unglamorous infrastructure that makes the whole vision actually work for users.

## Addendum — 2026-05-13 (Claude session)

**Core recommendation (one sentence):** Stabilize the plugin API contract and ship developer docs *before* Zotero, before Obsidian — without a stable plugin boundary, only one person can build any of this.

**Corrections to the vision document's complexity ratings:**
- Phase 2 citation scavenger: re-rate from **Medium → Hard**. Requires solving relevance ranking beyond raw citation count, open-access/paywall filtering, and deduplication across Semantic Scholar + Crossref simultaneously.

**`docent doctor` is Phase 0, not an afterthought:**
The vision's closing line — "checks if third-party tools are installed, offer to auto install, ensure Auth/APIs are sorted" — is the subsystem that makes or breaks the entire workstation vision for non-technical researchers. It maps directly to the already-planned `docent doctor` command (v1.3). Treat it as a prerequisite to any external integration, not a nice-to-have.

**Concurrency/resource model is a design gap:**
If Hermes monitors Zotero, runs citation sweeps, lints LaTeX, *and* does qualitative coding, a 16GB laptop cannot sustain all pipelines simultaneously. Needs explicit task prioritization, queuing, and model-tier routing (cheap model for bulk screening, premium for synthesis). Docent already has model-routing logic; this should extend it.

**Mendeley coexistence decision is overdue:**
Docent ships Mendeley integration today. The vision ignores it entirely. A decision is needed before Zotero bridge ships: coexist as parallel bridges, deprecate Mendeley, or phase it out on a timeline. Researchers are tribal — this affects adoption.

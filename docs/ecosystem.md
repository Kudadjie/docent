# Docent Ecosystem — Companion Tools

Docent is a research corpus manager and pipeline engine. It handles source gathering,
reading queue management, notebook sync, and multi-stage research synthesis — but it
is not trying to be every academic tool at once.

This page lists tools that pair exceptionally well with Docent. Use them side-by-side
rather than replacing each other.

---

## Academic Writing & Peer Review

### Academic Research Skills
**Author:** Cheng-I Wu  
**Repo:** https://github.com/Imbad0202/academic-research-skills  
**License:** CC-BY-NC 4.0  
**Install:** `/plugin marketplace add Imbad0202/academic-research-skills` in Claude Code

A Claude Code plugin providing a full academic workflow: 13-agent deep research,
12-agent paper writing, 7-agent peer review, and a 10-stage end-to-end orchestrator
with integrity gates. Emphasises "AI as copilot, not pilot."

| ARS Command | Use when |
|-------------|----------|
| `/ars-research` | You want a multi-agent research pass on top of Docent's source output |
| `/ars-write` | You have a synthesis document and want a paper draft |
| `/ars-review` | You want structured peer critique with a devil's advocate perspective |
| `/ars-revision` | You have reviewer feedback and want revision coaching |
| `/ars-pipeline` | End-to-end: research → write → review in one run |

**Suggested pairing with Docent:**
1. Run `docent studio deep-research "topic"` → saves `synthesis.md`
2. Feed `synthesis.md` into `/ars-write` for the paper draft
3. Run `/ars-review` on the draft for structured peer critique
4. Save the final draft with `docent studio to-local`

> Note: CC-BY-NC means free for personal and academic use. Commercial redistribution
> requires contacting the author. Required attribution format:
> *"Based on Academic Research Skills by Cheng-I Wu — https://github.com/Imbad0202/academic-research-skills"*

---

## Research Pipeline Engine

### Feynman
**Author:** Companion (companion.ai)  
**Repo:** https://github.com/companion-inc/feynman  
**Site:** https://feynman.is  
**License:** MIT  
**Install:** `npm install -g @companion-ai/feynman`

An open-source AI research agent CLI. Runs multi-stage research pipelines using
any major LLM provider via a single unified interface.

Docent uses Feynman as an optional research backend (`--backend feynman`), delegating
the full research task to Feynman and collecting its output. This is the highest-quality
backend option for long-form research briefs.

```bash
# Use Feynman as the research engine inside Docent
docent studio deep-research "topic" --backend feynman
docent studio lit "topic" --backend feynman

# Or run Feynman directly (outside Docent)
feynman /deep "topic"
```

> Attribution: Docent's multi-stage pipeline architecture
> (planner → fetch → write → verify → review → refine) is inspired by
> Feynman's approach to AI-assisted research.
> See `src/docent/bundled_plugins/studio/pipeline.py`.

---

## Study & Synthesis

### NotebookLM
**Author:** Google  
**Access:** https://notebooklm.google.com  
**License:** Proprietary (Google product)

NotebookLM lets you upload sources and chat with them, generate study guides,
create audio overviews, and build flashcards. Docent's `to-notebook` command
pushes research output and sources directly into a NotebookLM notebook.

```bash
# After a research run, push output + sources into NotebookLM
docent studio deep-research "topic" --output notebook

# Or post-process an existing output file
docent studio to-notebook --output-file research/my-output.md
```

---

## Inside Docent — Adopted Patterns

Some patterns from the ecosystem have been implemented directly in Docent's codebase.
Attribution is kept in the relevant source files and reproduced here for visibility.

| Pattern | Adopted from | Source file | Attribution |
|---------|-------------|-------------|-------------|
| Multi-stage pipeline architecture (planner → fetch → write → verify → review → refine) | Feynman — Companion (MIT) | `src/docent/bundled_plugins/studio/pipeline.py` | © Companion, https://github.com/companion-inc/feynman |
| Citation API verification (CrossRef + Semantic Scholar triangulation) | Academic Research Skills — Cheng-I Wu (CC-BY-NC 4.0) | `src/docent/bundled_plugins/studio/citation_verifier.py` | © Cheng-I Wu, https://github.com/Imbad0202/academic-research-skills |
| Pipeline integrity gates (minimum-substance guards between stages) | Academic Research Skills — Cheng-I Wu (CC-BY-NC 4.0) | `src/docent/bundled_plugins/studio/pipeline.py` | © Cheng-I Wu, https://github.com/Imbad0202/academic-research-skills |

---

## Suggesting Additions

If you find a tool that pairs well with Docent, open an issue or PR adding an entry
to this file. Include: name, author, repo/site, license, and a one-paragraph
description of when to reach for it over (or alongside) Docent.

# Docent — Memory Index

- [Build progress](build_progress.md) — current step + checklist; read first every session
- [Decisions log](decisions.md) — append-only architectural-decision record; read when "why did we pick X?" comes up, or when making a new call that deserves its own entry. Foundation entries (Steps 1–6, 2026-04-23) in [archive/](archive/decisions-2026-04-foundation.md).
- [Gotchas](gotchas.md) — landmines we've hit (Rich markup, Windows unicode, litellm lazy-import, pydantic v2, …); scan before shipping anything CLI-facing
- [Paper-pipeline port plan](archive/paper-pipeline-port-plan-2026-05.md) — Step 11 series shipped 2026-05-02 (archived; live record in `decisions.md` + `build_progress.md`)
- [Roadmap (post Phase 1)](roadmap_post_phase1.md) — what comes after Steps 11-13: skill ports, Output Shapes landing, Phase 2 UI plan + deferred items
- [Thoughts.txt review (2026-04-29)](thoughts_review_2026_04_29.md) — section-by-section take + 4-phase hardening/governance sequencing
- [Output Shapes deferred](output_shapes_deferred.md) — typed-return vocabulary for tool actions; design settled, explicitly deferred 2026-04-25
- [Harness engineering principles](harness_principles.md) — reference for when Docent gets sophisticated; eval-harness deferred to first real LLM-call tool
- [Narrate architecture decisions on Docent](feedback_narrate_steps.md) — user wants each build step explained before coding, recapped after
- [Real-data testing after each step](feedback_real_data_testing.md) — insist on manual testing with real PDFs/folders/DOIs before marking a build step done; programmatic smoke tests are not enough
- [Keep Docent memory in the repo](feedback_memory_location.md) — save memory files to `memory/` in the repo, not to `~/.claude/projects/…/memory/`
- [User runs global `docent`, not `uv run docent`](feedback_global_docent_install.md) — installed editable 2026-05-02; remind to reinstall after every new dep
- [Reading tool rewrite spec](reading_tool_rewrite_spec.md) — scope doc for graduating paper.py → reading tool; schema fixes, category/deadline/notification model, OUT items; tackle after queue clear
- [Multi-model workflow design](multimodel_workflow.md) — OpenCode (Go sub) as bounded implementer via REST API; Claude Code as architect/orchestrator; brief format, token economics, model selection; implement after reading rewrite
- [OpenCode for Docent agentic tools](feedback_opencode_for_agentic_tools.md) — route LLM calls in Docent's agentic tools through OpenCode (not Anthropic API); design as single-shot briefs; apply to first agentic tool after reading rewrite

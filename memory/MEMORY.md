# Docent — Memory Index

- [Build progress](build_progress.md) — current step + checklist; read first every session
- [Decisions log](decisions.md) — architectural decision record; read when "why did we pick X?" or making a new call. Older entries in archive/
- [Gotchas](gotchas.md) — landmines we've hit (Rich markup, Windows unicode, litellm lazy-import, pydantic v2, …); scan before shipping anything CLI-facing
- [Roadmap (post Phase 1)](roadmap_post_phase1.md) — what comes after Steps 12-13: skill ports, Output Shapes landing, Phase 2 UI plan + deferred items
- [Hardening & governance roadmap](thoughts_review_2026_04_29.md) — post-1.0 polish: security, CLI robustness, state resilience; trigger on pre-launch hardening
- [Output Shapes deferred](output_shapes_deferred.md) — typed-return vocabulary for tool actions; design settled, explicitly deferred 2026-04-25
- [Harness engineering principles](harness_principles.md) — reference for when Docent gets sophisticated; eval-harness deferred to first real LLM-call tool
- [Narrate architecture decisions on Docent](feedback_narrate_steps.md) — user wants each build step explained before coding, recapped after
- [Real-data testing after each step](feedback_real_data_testing.md) — insist on manual testing with real Mendeley/reading data before marking a build step done; programmatic smoke tests are not enough
- [Keep Docent memory in the repo](feedback_memory_location.md) — save memory files to `memory/` in the repo, not to `~/.claude/projects/…/memory/`
- [User runs global `docent`, not `uv run docent`](feedback_global_docent_install.md) — installed editable 2026-05-02; remind to reinstall after every new dep
- [Multi-model workflow design](multimodel_workflow.md) — OpenCode (Go sub) as bounded implementer via REST API; glm-5.1 is default implement model
- [Research tool routing](feedback_research_tool_routing.md) — routes through Feynman first; falls back to Claude (litellm) if Feynman unavailable
- [OpenCode for Docent agentic tools](feedback_opencode_for_agentic_tools.md) — route LLM calls in Docent's agentic tools through OpenCode (not Anthropic API); design as single-shot briefs
- [Release plan](release_plan.md) — two independent release tracks: CLI (v1.0 = Step 13 done) and UI (v1.0 = reading page Must-do complete)

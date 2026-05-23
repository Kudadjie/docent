# CONTEXT - resume hint for next session

**Current Task:** Studio bug-fix sprint — phase strip responsiveness, Feynman silent-success, and progress newline clipping all shipped (commit ff95e61 on dev).

**Key Decisions:**
- WS handler (`opencode.py`) runs `docent studio` as subprocess; status comes from `proc.returncode`, not `ResearchResult.ok`. Fix: cli.py exits non-zero on `ok=False` and emits error progress line.
- Feynman exits 0 on credit/quota failures → `output_file is None` now always returns `ok=False` in all 7 Feynman workflows.
- Progress marker newlines escaped as `\x02` in CLI, unescaped in WS handler — prevents multiline messages (_PRICING_NOTE) from being split across stdout reads.

**Next Steps:**
1. Continue UI test checklist (Studio page items 10–27, then Ecosystem, Docs, Settings, Inbox, Sidebar, User Footer, Cross-cutting) — `memory/tasks/v120_ui_tests.md`
2. Add Feynman model field to Settings UI (CLI-only now: `docent studio config-set --key feynman_model --value <provider/model>`)
3. Studio background runs: lift WS+run state to app layout level so navigation doesn't kill a running task (roadmap: `memory/project_roadmap_post_v120.md`)

---
name: Update memory after each task
description: After every completed Docent task, update the relevant memory file(s) and root CONTEXT.md before moving to the next task
type: feedback
---

After every completed task in the Docent repo, update project memory before starting the next task.

**How to apply:**
- Update `CONTEXT.md` with the current task status, key decisions, and next steps.
- Update any task-specific memory file that tracks the work, such as `memory/project_codex_review_blockers.md`.
- If the task creates a durable preference or operating rule, add a `memory/feedback_*.md` file and index it in `memory/MEMORY.md`.
- Do this even when the next task is obvious; the point is to keep Claude Code and future Codex sessions synchronized.

**Why:** The user explicitly asked on 2026-05-08: "Update the memory and context so Claude Code knows what you have done. Do this after every task."

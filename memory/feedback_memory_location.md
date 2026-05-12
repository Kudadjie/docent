---
name: Keep Docent memory in the repo
description: On the Docent project, save all memory files inside `memory/` in the repo — not in the default `~/.claude/projects/…/memory/` location
type: feedback
---

All project memories for Docent live in `C:\Users\DELL\Desktop\Docent\memory\`, with `memory/MEMORY.md` as the index. Do NOT write to `C:\Users\DELL\.claude\projects\C--Users-DELL-Desktop-Docent\memory\` — that directory has been removed on purpose.

**Why:** The user explicitly asked for in-repo memory so they can read it directly, commit it alongside the code, and keep it portable across machines. The default auto-memory location is invisible to them.

**How to apply:** When saving any new memory file for this project, write it to `memory/` in the repo and add an index entry to `memory/MEMORY.md`. The project-root `CLAUDE.md` is what causes new sessions to find this — keep the pointer in `CLAUDE.md` intact. Same frontmatter + type conventions as the global auto-memory system.

---
name: Narrate architecture decisions on Docent
description: On the Docent project the user wants each step explained — narrate plan, design choices, and recap before/after coding
type: feedback
originSessionId: 15b6c25c-0a8b-474a-8f36-cd6a2350b96d
---
On the Docent project, before writing or modifying code in a new build step, narrate: (1) the goal of the step, (2) the files being created/changed, (3) the non-obvious design choices and the reasoning behind them. After the step, give a short recap with the tree of new files and what was verified.

**Why:** The user said explicitly "Let me understand everything you are doing" when starting the build. They are using Docent as a learning exercise in how the system fits together, not just a task to be completed — silent execution defeats the purpose.

**How to apply:** Applies to the staged 10-step build in `Docent_Architecture.md`. Keep narration focused on *why* a decision was made (entry point shape, source priority order, singleton vs mutation, etc.), not *what* the code does — the code is already in front of them. If the user later signals they want to move faster (e.g. "just do it", "skip the explanation"), downgrade to one-sentence step summaries and update this memory.

**After every completed step**, also outline *what the user can now do* — frame by user-visible capability (commands they can run, workflows that now work end-to-end), not by internal abstraction. Added 2026-04-25 after Step 10: the user explicitly asked for this recap shape.

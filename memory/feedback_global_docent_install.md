---
name: User runs global `docent`, not `uv run docent`
description: User installed via `uv tool install --reinstall --editable .` 2026-05-02 — use bare `docent ...` in instructions and remind to reinstall after dep changes
type: feedback
---

User dislikes typing `uv run docent ...` and installed a global editable command via:

```
uv tool install --reinstall --editable .
```

(2026-05-02, after shipping Step 11.7.)

**How to apply:**
- Write smoke-test commands and CLI examples as `docent reading next`, NOT `uv run docent reading next`.
- **When a build step adds a Python dependency** (e.g., the `mcp` SDK at Step 11.4), the global tool does NOT automatically pick it up — `docent ...` will fail with `ImportError`. After the dep is added, remind the user to run `uv tool install --reinstall --editable .` again. This bit them once at Step 11.4 already.
- Editable means source edits are picked up live; only dep changes need the reinstall.

**Why:** Quality-of-life — typing `uv run` for every command is annoying after a few hundred invocations. The reinstall friction is worth it for the ergonomics.

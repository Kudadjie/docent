---
name: OpenCode brief — project conventions must be explicit
description: When writing oc_delegate.py briefs, project-specific conventions must be spelled out verbatim, not implied
type: feedback
---

OpenCode models follow explicit instructions well but miss implicit project conventions even when told to "look at conftest.py first."

**Rule:** Any project convention that differs from the obvious default must be stated as a hard rule in the brief, not left as something the model should infer.

**Known conventions to always include in briefs that touch tests or imports:**

1. **Import convention for bundled plugins:** Use bare module name `from reading import ...` and `from reading.reading_store import ...` — NOT `from docent.bundled_plugins.reading import ...`. This is because `conftest.py` adds `src/docent/bundled_plugins/` to `sys.path`. Using the full package path causes double-registration of `@register_tool` when the full suite runs.

2. **`seed_queue_entry` fixture:** Don't recreate it — it's in `conftest.py`. Brief should say "use the existing `seed_queue_entry` fixture from conftest."

3. **No Rich markup in shape content:** When writing `to_shapes()`, content strings must be plain text — no `[bold]`, `[dim]` etc. That's the renderer's job.

**Why:** glm-5.1 read conftest.py during the test_shapes.py task but still used the full package import path, causing a double-registration error that only surfaces when the full suite runs together. The fix was trivial but wouldn't have been needed with an explicit rule.

4. **Brief file location:** Always write briefs to `oc_briefs/` (not `briefs/`, not `memory/tasks/`). The folder is `oc_briefs/` at the project root.

**How to apply:** Before finalising any brief that creates test files or imports from bundled plugins, add a "Project conventions" section with these rules spelled out as bullet points. Always save the brief to `oc_briefs/`.

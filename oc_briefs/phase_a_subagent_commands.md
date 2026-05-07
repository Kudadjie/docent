# Brief: Create /code-reviewer and /test-engineer slash commands

Create two new Claude Code slash command files. Both go in `.claude/commands/`.

Use the same frontmatter + markdown format as `.claude/commands/memory-cleanup.md` and the
newly created `.claude/commands/safe-commit.md`.

---

## Command 1: `.claude/commands/code-reviewer.md`

**Purpose:** Project-aware code review for Docent diffs.

**argument-hint:** `[file-or-diff]`

**What it should do when invoked as `/code-reviewer [file-or-diff]`:**

When invoked, Claude should review either:
- The currently staged git diff (`git diff --cached`) if no argument given
- A named file or set of files if an argument is provided

**Review checklist (apply in this order):**

### 1. Docent-specific invariants
- **Import convention:** Bundled plugin code must use `from reading import ...` and
  `from reading.reading_store import ...` — NOT `from docent.bundled_plugins.reading import ...`.
  Flag any full-path import from `docent.bundled_plugins`.
- **No Rich markup in Shape content:** `to_shapes()` methods must return plain text strings.
  Flag any `[bold]`, `[dim]`, `[green]` etc. inside shape `content` / `text` / `reason` fields.
- **litellm lazy-import invariant:** `import litellm` must never appear at module top-level in
  `docent.core`, `docent.config`, `docent.tools`, or `docent.bundled_plugins`. It belongs only
  in `docent.llm.client`. Flag any top-level litellm import outside that module.
- **Tool contract:** Any new Tool subclass must have `name`, `description` class attrs.
  Multi-action tools must not also set `input_schema` or override `run()`. Flag violations.
- **Registry hygiene:** `@register_tool` must only be called once per tool name across the
  entire codebase. Flag duplicate registrations.

### 2. General code quality
- Logic correctness: are there obvious bugs, off-by-one errors, missed edge cases?
- Error handling: are failure modes handled at system boundaries (user input, external APIs)?
  Don't flag missing error handling for internal invariants.
- Test coverage: are new public functions or actions covered by tests? Flag untested
  happy paths or obvious failure modes.

### 3. Output format
Produce a structured review:
```
## Code Review

### Docent invariants
- PASS / FAIL: <finding>

### General quality  
- <finding>

### Verdict
PASS | NEEDS CHANGES
```

If there are no issues, say PASS clearly. Don't invent nitpicks.

---

## Command 2: `.claude/commands/test-engineer.md`

**Purpose:** Write tests for a given Docent module, function, or action following project
conventions. Run the suite and iterate until green.

**argument-hint:** `<target>`

**What it should do when invoked as `/test-engineer <target>`:**

`<target>` is a file path, function name, or description of what to test.

**Project test conventions (hard rules — must be stated in the generated tests):**

1. **Bundled plugin imports:** Use `from reading import ...` and `from reading.reading_store import ...`.
   Never `from docent.bundled_plugins.reading import ...`.

2. **Fixtures from conftest:** Use existing fixtures — don't recreate them:
   - `isolated_registry` — snapshots/restores the global tool registry; use for any test that
     calls `@register_tool`
   - `tmp_docent_home` — redirects `~/.docent` to `tmp_path`; use for any test that touches
     the filesystem (queue, config)
   - `seed_queue_entry` — builds and persists a `QueueEntry` directly; use instead of calling
     `reading add` in test fixtures

3. **Test tool pattern for dispatcher tests:** Define minimal `@register_tool` fixture tools at
   module level with unique names (suffix `-xyz` or similar) to avoid clashing with real tools.

4. **No mocking of the database/filesystem** for integration-style tests — use `tmp_docent_home`
   and real file I/O instead.

**What to produce:**
1. A new test file in `tests/` (name it `test_<target>.py` or extend an existing file if
   clearly the right home)
2. Run `uv run pytest <new-file> --tb=short` — fix failures until green
3. Run `uv run pytest --tb=no -q` — confirm full suite stays green
4. Report: file created, N tests, suite count before → after

---

## Project conventions (both commands)

- Files go in `.claude/commands/` — not anywhere else
- Use frontmatter: `description`, `argument-hint` — match the format of `memory-cleanup.md`
- Do NOT modify any existing files
- After creating both files, run `uv run pytest --tb=no -q` and confirm 160 tests still pass

## Expected outputs

- `.claude/commands/code-reviewer.md`
- `.claude/commands/test-engineer.md`

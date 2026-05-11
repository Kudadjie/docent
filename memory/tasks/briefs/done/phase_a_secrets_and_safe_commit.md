# Brief: Phase A — secrets scan + /safe-commit slash command

Two tasks. Do them in order.

---

## Task 1 — Hardcoded secrets scan

Grep the codebase for patterns that indicate hardcoded secrets or personal data that
should never land in a public GitHub repo.

**Search targets (use ripgrep/grep on `src/`, `tests/`, `scripts/`, `.claude/`):**

Patterns to flag (report file + line number + the offending text):
1. `sk-ant-` or `sk-` followed by alphanumeric — Anthropic/OpenAI API key patterns
2. `AKIA` — AWS access key prefix
3. `password\s*=` or `secret\s*=` — hardcoded credential assignments (case-insensitive)
4. Any email address that isn't in a comment or docstring marked as an example
   (pattern: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`)
5. Hardcoded absolute paths that look like a real user's home dir
   (pattern: `/Users/` or `/home/` or `C:\\Users\\` outside of test fixtures or comments)

For each hit: report `file:line — pattern matched — excerpt`.
If nothing found for a pattern, say "clean".

Do NOT modify any files in Task 1 — report only.

---

## Task 2 — `/safe-commit` slash command

Create `.claude/commands/safe-commit.md`.

**What the command should do (these are instructions for Claude Code, not shell scripts):**

The command is invoked as `/safe-commit [message]` where `[message]` is an optional
commit message hint.

When invoked, Claude should:

1. **Run the test suite** — `uv run pytest --tb=short -q`. If any tests fail, stop and
   report the failures. Do not proceed to commit.

2. **Secrets check on staged/changed files** — scan `git diff --cached` output and
   `git status` for any file matching: `.env`, `*.env`, `*.key`, `*.pem`, `*.secret`,
   or any file containing the string `sk-ant-` or `AKIA`. If found, stop and warn.

3. **Check for accidentally staged dev-only files** — warn if any of these are staged:
   `CLAUDE.md`, `CLAUDE.performance.md`, `.dual-graph/`, `.claude/`, `*.log`,
   `claudemap-*.json`. These are in `.gitignore` on main but tracked on dev; remind
   the user they're dev-only.

4. **Draft a commit message** following the project's conventional commits style
   (visible in `git log --oneline`): `type(scope): short description`.
   If the user passed a message hint, incorporate it.

5. **Show the staged diff summary** (`git diff --cached --stat`) and the drafted message,
   then ask for confirmation before committing.

**Format for the command file:**

Use the same frontmatter + markdown format as `.claude/commands/memory-cleanup.md`:

```
---
description: <one-line description>
argument-hint: '[message]'
---

<body>
```

**File to create:** `.claude/commands/safe-commit.md`

---

## Project conventions

- Do NOT import from `docent.bundled_plugins.reading` — these tasks don't touch tests.
- Do NOT modify any existing files except to create the two outputs listed above.
- After Task 2, run `uv run pytest --tb=no -q` to confirm the suite stays green
  (creating a new `.claude/commands/` file shouldn't affect tests, but verify).
- Brief files belong in `oc_briefs/` — you don't need to move anything.

## Expected outputs

1. Task 1: a plain-text secrets scan report (print to stdout / return as response)
2. Task 2: `.claude/commands/safe-commit.md` created

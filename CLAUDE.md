<!-- dgc-policy-v11 -->
# Dual-Graph Context Policy

This project uses a local dual-graph MCP server for code navigation.

> **Note on the global `~/CLAUDE.md` graphify rule:** that rule does NOT apply to this project. Docent does not use graphify (`graphify-out/`) — it uses dual-graph (`graph_*` MCP tools, `.dual-graph/`). Ignore the graphify instruction when working in this repo.

## MANDATORY: Adaptive graph_continue rule

**Call `graph_continue` ONLY when you do NOT already know the relevant files.**

### Call `graph_continue` when:
- This is the first message of a new task / conversation
- The task shifts to a completely different area of the codebase
- You need files you haven't read yet in this session

### SKIP `graph_continue` when:
- You already identified the relevant files earlier in this conversation
- You are doing follow-up work on files already read (verify, refactor, test, docs, cleanup, commit)
- The task is pure text (writing a commit message, summarising, explaining)

**If skipping, go directly to `graph_read` on the already-known `file::symbol`.**

## When you DO call graph_continue

1. **If `graph_continue` returns `needs_project=true`**: call `graph_scan` with `pwd`. Do NOT ask the user.

2. **If `graph_continue` returns `skip=true`**: fewer than 5 files  -  read only specifically named files.

3. **Read `recommended_files`** using `graph_read`.
   - Always use `file::symbol` notation (e.g. `src/auth.ts::handleLogin`)  -  never read whole files.
   - `recommended_files` entries that already contain `::` must be passed verbatim.

4. **Obey confidence caps:**
   - `confidence=high` -> Stop. Do NOT grep or explore further.
   - `confidence=medium` -> `fallback_rg` at most `max_supplementary_greps` times, then `graph_read` at most `max_supplementary_files` more symbols. Stop.
   - `confidence=low` -> same as medium. Stop.

## Session State (compact, update after every turn)

Maintain a short JSON block in your working memory. Update it after each turn:

```json
{
  "files_identified": ["path/to/file.py"],
  "symbols_changed": ["module::function"],
  "fix_applied": true,
  "features_added": ["description"],
  "open_issues": ["one-line note"]
}
```

Use this state  -  not prose summaries  -  to remember what's been done across turns.

## Token Usage

A `token-counter` MCP is available for tracking live token usage.

- Before reading a large file: `count_tokens({text: "<content>"})` to check cost first.
- To show running session cost: `get_session_stats()`
- To log completed task: `log_usage({input_tokens: N, output_tokens: N, description: "task"})`

## Rules

- Do NOT use `rg`, `grep`, or bash file exploration before calling `graph_continue` (when required).
- Do NOT do broad/recursive exploration at any confidence level.
- `max_supplementary_greps` and `max_supplementary_files` are hard caps  -  never exceed them.
- Do NOT call `graph_continue` more than once per turn.
- Always use `file::symbol` notation with `graph_read`  -  never bare filenames.
- After edits, call `graph_register_edit` with changed files using `file::symbol` notation.

## Memory (source of truth)

The `memory/` directory is the canonical record of decisions, gotchas, feedback, and progress. Treat it as authoritative — `.dual-graph/context-store.json` is no longer maintained, and the dual-graph hook no longer dumps memory at session start.

## Session Start

Before answering the first real message of a new session:

1. `memory/MEMORY.md` is the index — read it.
2. Read `memory/build_progress.md` to check what step we're on.
3. Scan the last 3 entries of `memory/decisions.md` for recent architectural context. (Older entries are archived under `memory/archive/` — read those only when revisiting foundation choices.)
4. Verify the checkboxes in `build_progress.md` match reality: run `uv run docent --version` and glance at `src/docent/` to confirm claimed-done steps actually shipped. If they disagree, trust the code.

Takes 30 seconds. Prevents memory-from-reality drift.

## Session End

When the user signals they are done (e.g. "bye", "done", "wrap up", "end session"), proactively update `CONTEXT.md` in the project root with:
- **Current Task**: one sentence on what was being worked on
- **Key Decisions**: bullet list, max 3 items
- **Next Steps**: bullet list, max 3 items

Keep `CONTEXT.md` under 20 lines total. Do NOT summarize the full conversation  -  only what's needed to resume next session.

If the session produced a real architectural call (alternatives considered, decision made), append a full entry to `memory/decisions.md` using the format at the top of that file. CONTEXT.md is the resume hint; `decisions.md` is the durable record.

## Build discipline (karpathy-guidelines)

When narrating any step or reviewing a diff for this project, apply the four `/karpathy-guidelines` principles explicitly:

1. **Think before coding.** State assumptions. Surface alternatives. If a decision is reversible or high-impact, present it as a choice, not a fait accompli. Narrate design before writing code — the user wants to engage with the reasoning, not just the result.
2. **Simplicity first.** Split every step into "what's IN / what's OUT" with reasons. Flag your own speculation ("adding X because the UI might need it later") as speculation, not as a given. Every feature deferred is a feature you didn't have to build wrong.
3. **Surgical changes.** Every edit traces to the user's request. Don't refactor adjacent code. Don't "clean up" on the side. If you notice an unrelated problem, mention it — don't fix it silently.
4. **Verifiable success.** End each step with a smoke test that exercises the happy path, the obvious failure modes, and any non-obvious invariant (e.g. "litellm is not in sys.modules after importing docent.cli").

If you catch yourself drifting from any of these, say so out loud and course-correct. The user prefers honest pushback over silent compliance.

## Native Claude Model Routing (Agent tool)

For tasks where OpenCode is unavailable or overkill, delegate to cheaper Claude models via the `Agent` tool's `model` parameter. This keeps everything in-session — no external server needed.

**Routing tiers:**

| Tier | Model | Use when |
|------|-------|----------|
| Haiku | `haiku` | Search/grep, file listings, reading a single file, boilerplate generation, formatting, doc edits |
| Sonnet | `sonnet` | Default sub-agent for medium implementation, multi-file reads, test writing |
| Opus | `opus` | Architecture review, complex multi-file refactors, anything requiring `memory/` context |

**Rules:**
- For pure lookup tasks (find a symbol, count lines, check a value), always spawn `haiku` — never do it inline with the main session model.
- When spawning, pass enough context in the prompt so the sub-agent doesn't need `memory/`. If it does, handle it in the main session instead.
- The main session (current model) handles: architectural decisions, `memory/` reads, `CLAUDE.md` edits, and anything where being wrong is hard to reverse.
- Prefer OpenCode delegation over Agent-model routing when the task involves a test-fix loop (`uv run pytest` until green) — OpenCode handles that better.

## Multi-Model Delegation (OpenCode Go sub)

Use `scripts/oc_delegate.py` to delegate bounded implementation tasks to OpenCode (Go subscription models — no Anthropic tokens consumed).

**Delegation is automatic — Claude initiates it, not the user.**

When a task is delegatable, Claude:
1. Health-checks the server: `curl -s http://127.0.0.1:4096/global/health`
2. If server is down: tells the user "Delegating to OpenCode — please run `opencode serve --port 4096` and confirm"
3. Once server is up: calls `python scripts/oc_delegate.py` via Bash tool directly
4. Reads response + diff, runs tests, integrates or corrects

**When to delegate:**
- Task is well-scoped and Claude can write the brief without opening source files
- Implementation is mechanical: add an action, wire a function, add a field
- Brief can include "run `uv run pytest` and fix until green" — let OpenCode handle the loop

**When NOT to delegate:**
- Task requires architectural judgment or reading `memory/`
- Multi-file refactor where being wrong is hard to reverse
- Anything touching `memory/`, `decisions.md`, or `CLAUDE.md`

**How Claude calls it:**
```bash
python scripts/oc_delegate.py --task simple|implement|reason|long brief.md
```

Default model auto-routed by `--task`; keyword heuristics apply if omitted.
Full details: `memory/multimodel_workflow.md`.

## Performance Work

When the user asks about optimization, benchmarking, memory leaks, slow queries, or UI rendering performance, read `CLAUDE.performance.md` before proceeding. It defines mandatory phases (baseline → analysis → refactor → report) and prohibited patterns. Do not suggest a performance change without benchmarking first.


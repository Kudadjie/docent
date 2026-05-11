---
name: Multi-Model Workflow Design
description: Architecture for using OpenCode (Go sub) as a bounded implementer alongside Claude Code as architect/orchestrator
type: project
---

# Multi-Model Workflow Design

**Status:** Two scripts — `scripts/oc_delegate.py` (OpenCode, one-shot) and `scripts/hermes_delegate.py` (Hermes WSL, self-correcting loop).

**Why:** Save Claude Code tokens on bounded implementation tasks. The token savings come primarily from OpenCode reading the codebase on its own subscription budget — not from avoiding orchestration overhead.

---

## How to use

### OpenCode (`oc_delegate.py`)
```bash
opencode serve --port 4096          # start once, keep running
python scripts/oc_delegate.py memory/tasks/briefs/my-brief.md
python scripts/oc_delegate.py --task reason brief.md
python scripts/oc_delegate.py --model deepseek-v4-pro brief.md
```

### Hermes (`hermes_delegate.py`) — no server, WSL only
```bash
python scripts/hermes_delegate.py memory/tasks/briefs/my-brief.md
python scripts/hermes_delegate.py --task loop brief.md       # test-fix loop
python scripts/hermes_delegate.py --timeout 1800 brief.md    # slow test suite
```

Response text → stdout. Diff summary → stderr. Brief archived to `memory/tasks/done/`.

## Architecture

```
Claude Code (Anthropic)               OpenCode Server (Go sub models)
  - reads memory/                        - runs from project working dir
  - makes architectural decisions        - reads codebase files itself
  - writes brief                         - implements
  - calls oc_delegate.py                 - returns diff
  - reads diff, runs tests
  - integrates or corrects
```

## Verified API facts (v1.14.39)

Server start:
```bash
opencode serve --port 4096   # start once; --print-logs for debug
```

Endpoints (all JSON, no auth by default):
- `GET /global/health` → `{"healthy": true, "version": "..."}`
- `POST /session` → `{"id": "ses_...", ...}` (body can be `{}`)
- `POST /session/:id/message` → full response with parts + info
- `GET /session/:id/diff` → `[{"file": "...", "additions": N, "deletions": N}]`

**Critical:** message body uses `parts` (not `content`) and model must be a **nested object**:
```json
{
  "parts": [{"type": "text", "text": "..."}],
  "role": "user",
  "model": {"modelID": "kimi-k2.6", "providerID": "opencode-go"}
}
```
Top-level `modelID`/`providerID` fields are silently ignored — only the nested `model` object works.

Response shape:
```json
{
  "info": {"modelID": "kimi-k2.6", "cost": 0.008, "tokens": {"total": 30000}},
  "parts": [{"type": "text", "text": "..."}]
}
```

## Model options (Go subscription, provider: opencode-go)

| Model ID | Context | Best for |
|----------|---------|----------|
| `glm-5.1` | 200K | **Default (`implement`)** — multi-file implementation |
| `kimi-k2.6` | 256K | Small single-file tasks only — **times out (>600s) on multi-file briefs** |
| `qwen3.5-plus` | 128K | Cheap, simple tasks |
| `minimax-m2.7` | 1M | Long-context tasks |
| `deepseek-v4-pro` | 1M | Reasoning-heavy tasks |
| `deepseek-v4-flash` | 1M | Fast reasoning |

## Brief format (file-backed for audit trail)

Brief must be self-contained — no implicit references to memory/ or decisions. Everything OpenCode needs must be in the brief text.

Brief structure:
- What to build (function/file/action name)
- Relevant schema/types (copy-paste, don't reference)
- Constraints (no new deps, follow this pattern)
- Done criteria (what the test looks like)
- Explicitly what NOT to do

## Token economics

Savings are real when:
- Task is well-scoped and OpenCode gets it right in one shot
- The task would have required Claude Code to read many files before implementing

Savings erode when:
- Brief is wrong → correction rounds pull Claude Code back in
- Task needs deep architectural review of the diff
- Brief is vague → OpenCode reads widely, diff is wide

**Rule of thumb:** If you can write the brief without opening any source files, it's ready to delegate.

## What stays in Claude Code

- All architectural decisions
- Any task touching memory/ or decisions.md
- Multi-file refactors that require understanding why something was built
- Review and integration of OpenCode output
- Anything where being wrong is hard to reverse

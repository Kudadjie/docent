---
name: Thoughts.txt review — hardening & governance roadmap
description: Section-by-section review of user's Thoughts.txt (2026-04-29) covering security audit, CLI robustness, LLM budgeting, subagents, slash commands. Captures opinionated take + 4-phase sequencing for items NOT covered by roadmap_post_phase1.md (which handles capability/UI; this handles hardening/governance). Read when picking up post-Step 11 hardening work or when user asks about pre-1.0 polish.
type: project
---

User wrote `Thoughts.txt` (repo root) on 2026-04-29 — a brain-dump of ~15 work items spanning hardening, features, governance, tooling. Asked for honest section-by-section feedback. Verdict: most items good, some overlap with shipped work, a couple worth pushing back on. **Critical framing:** none of these belong before Step 11 — doing any of them now starves the paper-pipeline port. They're pre-1.0 (and post-1.0) polish.

This file is the durable record of that review. Complements `roadmap_post_phase1.md` (capability arc: skill ports, UI) — this is the **hardening + governance arc**. They run in parallel post-Step 11.

## Section-by-section take

### 1. Group / sub reading queues
Worth doing, post Step 11. Categories on queue entries = small extension. Books-as-queue-entries is bigger (different metadata, no Mendeley path) — separate sub-pipeline, don't wedge in.

### 2. Backup & restore (Google Drive, 100MB filter)
Concept is sound — filesize over extension blocklist is OS-truthful. Two flaws:
- 99MB blobs sneak through. Add a *count + total size* warning so you notice unexpected sweeps.
- PyDrive2 OAuth is a one-time dance; document in `docent setup backup`.

### 3. Security & architecture audit
Mostly straightforward. Caveats:
- BaseSettings fail-fast = at *use* site, not import site. Don't crash on missing Mendeley creds for users who never invoke paper-pipeline.
- `docent.log` — be careful with subprocess interleaving via `Context.executor`. Per-run log file likely beats one global file.
- Hardcoded-secrets scan = cheap, do before first public push.

### 4. CLI robustness (binary check, timeouts, pathlib)
- Binary preflight: cache result in `Context.settings`, run once per session.
- Subprocess timeouts: **kill the process group, not just the parent.** Pandoc on Windows spawns children; parent dies, kids survive. Use `CREATE_NEW_PROCESS_GROUP`.
- Pathlib: probably already there; one-time grep for `os.path.join` to verify.

### 5. UI workflow (Gemini → Claude Design → Claude Code)
Tool-spec MD per completed tool is good *if tools are actually finished*. Don't write a paper-pipeline UI spec until Step 11/12 lands or the spec will lock in a shape that's still moving.

### 6. Versioning + branch strategy
- `pyproject.toml` 0.1.0 → real version when shipping: yes. **Stay at 0.1.0 — Docent is a personal tool that will keep changing; honesty over false stability.**
- `main` stable + `dev` branch: **overkill for solo dev with no users.** Stay on `main` with feature branches until real users exist. Then split.

### 7. Memory / token usage
Confirmed: memory is **manual semantic, on-demand** (correct architecture). What's missing is **discipline** — prune after big steps. `/memory-cleanup` slash command is the enforcement mechanism.

### 8. LLM orchestration & budgeting
- BYOK cloud-only, no Ollama: agree. Local-LLM tax outweighs privacy upside for research-grade reasoning.
- Feynman cost-piping via stdout regex: fragile. Check if Feynman has JSON output mode.
- **l6e-mcp budget guard = most ambitious item in the doc.** Pre-flight per-tool cost estimation is hard. Build crude version first: flat session budget, hard cap at 90%, summarize-and-exit interrupt. Skip per-tool execution-plan estimation until real usage data exists.

### 9. State resilience
- Idempotency via state.json check: biggest UX win for long pipelines. Cheap.
- SIGINT handler: Windows behaves differently for Ctrl+C in subprocess — test it.
- Error code mapping (`D001`...): always print code **plus** underlying exception summary. Opaque codes alone are a UX regression.

### 10. Integrity / portability / doctor
- `docent doctor`: high value, low cost. Pre-public-release.
- Atomic writes: probably already there for state.json. Verify, don't re-implement.
- **Schema versioning: add the field the first time you migrate, not preemptively.** Adding `version: 1` to every Pydantic model before any migration is noise.

### 11. Dependency lifecycle (`docent upgrade`)
Nice-to-have. Skip until users complain. 24h cache for "latest on PyPI" is the right detail when you do build it.

### 12. FastAPI streaming
Future. **SSE > WebSockets for one-way log streaming** (simpler, proxy-friendly, no upgrade dance). **Don't use BackgroundTasks for long jobs** — they die with the request worker. Real task queue or `asyncio.create_task` registry.

### 13. Testing
The mandatory unit-test list is small and correct. Biggest miss: **real-data tests.** Step 10.5 bugs were invisible to programmatic tests. Whatever ships, also dogfood. `feedback_real_data_testing.md` already says this — `test-engineer` subagent must honor it, not replace dogfooding with mocks.

### 14. Subagent task force (5 agents)
**Don't create all 5 now.** Each unused agent is config rot.
- `code-reviewer`: yes, soon, continuous use.
- `test-engineer`: yes, when test-writing starts in earnest.
- `sec-ops`: yes, one-shot before first GitHub push.
- `arch-scribe`: skip. Overlaps with `memory/decisions.md`.
- `ui-spec-writer`: only when first tool is done and ready for handover.

`code-reviewer` and `sec-ops` overlap (different lenses on same diff) — fine, but one is default-on, the other on-demand.

### 15. `/safe-commit` + `/memory-cleanup`
Both lightweight, both good. `/safe-commit` matches existing manual workflow. `/memory-cleanup` is the discipline forcing function from §7. These are slash commands, not skills — small, fast wins. **`/memory-cleanup` shipped 2026-04-30** (`.claude/commands/memory-cleanup.md`); `/safe-commit` still pending.

## Sequencing (the 4-phase plan)

This is the **load-bearing recommendation** — what to do with the list. Mirrors but extends `roadmap_post_phase1.md` (capability arc) with a **hardening arc** running in parallel post-Step 11.

### Phase 0 — RIGHT NOW (pre-Step 11)
**Nothing from Thoughts.txt.** Commit pending bug fixes, do Step 11 design narration, ship paper sync. Discipline matters here — every audit item pulled forward delays the port.

### Phase A — "Ready for first GitHub push" bundle
Trigger: paper-pipeline fully ported (after ~Step 12).
- §3 security audit + `.env.example` + `.gitignore` audit (`.env`, `docent.db`, `*.log`, `.DS_Store`)
- §6 version decision (stay 0.1.0)
- §15 `/safe-commit` + ~~`/memory-cleanup`~~ (shipped 2026-04-30) slash commands
- §14 `sec-ops` subagent (one-shot review before push)

### Phase B — Pre-1.0 hardening pass
Trigger: skills ported, Output Shapes shipped (per `roadmap_post_phase1.md` Phase 1.5).
- §4 CLI robustness (binary preflight, subprocess timeouts with process-group kill, pathlib audit)
- §9 state resilience (idempotency check, SIGINT handler with Windows test, error code mapping w/ underlying exception)
- §10 `docent doctor` + atomic-write verification
- §13 testing (contract-shape unit tests for Tool ABC + registry + dispatcher; per `roadmap_post_phase1.md` Plumbing C)
- §14 `code-reviewer` + `test-engineer` subagents (continuous use)

### Phase C — Post-1.0 features
Trigger: 1.0 shipped, real usage data available.
- §1 group/sub queues + categories
- §2 backup/restore (Google Drive, 100MB filter, count+size warning)
- §8 budgeting — crude version first (flat session cap, 90% interrupt)
- §11 deps lifecycle (`docent upgrade`)
- §12 FastAPI layer (overlaps with `roadmap_post_phase1.md` Phase 2)
- §14 `ui-spec-writer` subagent (when first tool ready for design handover)
- §5 UI workflow (tool spec MDs after each tool completes)

### Explicit skips / re-prioritization
- §10 schema versioning — defer until first real migration.
- §14 `arch-scribe` — drop; redundant with `memory/decisions.md`.
- §8 l6e-mcp full per-tool execution-plan estimation — defer indefinitely; only build crude version.

## When this file is wrong
Snapshot of opinion at 2026-04-29. Re-read `Thoughts.txt` before acting on any phase — user may have updated it. If a phase ships, prune it from here. If priorities flip, reorder. Don't sync via another memory file.

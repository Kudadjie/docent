---
name: Studio real-life tests
description: Full checklist of manual real-life tests for the studio tool (renamed from research-to-notebook). Tests 1–9 PASSED; 10–19 remaining before v1.2.0 tag.
type: project
---

# Studio: Real-Life Test Checklist

All commands assume the global `docent` install is current (`uv tool install --reinstall --editable .`).
Run from any directory unless a test specifies otherwise.

---

## 1. Smoke: CLI surface

```
docent studio --help
```
**Expect:** `deep-research`, `get-paper`, `lit`, `review`, `search-papers`, `to-notebook`, `usage`, `config-show`, `config-set` all listed.
**Result (2026-05-08): PASSED**

---

## 2. Config: show and set

```
docent studio config-show
```
**Expect:** Prints `output_dir`, `feynman_command`, `feynman_budget_usd`, all `oc_model_*` fields, `oc_budget_usd`, `oc_provider`.

```
docent studio config-set --key output_dir --value ~/Documents/Docent/research
docent studio config-show
```
**Expect:** `output_dir` updated. Verify persisted in `~/.docent/config.toml` under `[studio]`.
**Result (2026-05-08): PASSED**

---

## 3. Usage: baseline zero

```
docent studio usage
```
**Expect:** Today's date, Feynman spend $0.0000, OC spend $0.0000 (both "(no limit)" if budgets unset).
If a spend file exists from today, spend may be non-zero — that's correct.
**Result (2026-05-12): PASSED**

---

## 4. Docent pipeline — deep research

```
docent studio deep-research "storm surge Ghana" --backend docent
```

User: Opencode usage Checker: When opencode usage is back, try again and see if it works

**Expect (watch terminal):**
- Progress events for pipeline stages: `research → review → refine` (Tavily path) or `planner → fetch → gap → writer → verifier → reviewer → refiner` (manual fallback)
- No crash; may take 3–10 minutes depending on Tavily + OpenCode server speed
- Output: `<output_dir>/storm-surge-ghana-deep.md` created
- Review file: `<output_dir>/storm-surge-ghana-deep-review.md` created
- Sources file: `<output_dir>/storm-surge-ghana-deep-sources.json` created
- **References in markdown:** `storm-surge-ghana-deep.md` should end with a `## References` section listing numbered entries with title, URL, and source type for each source
- Check sources JSON: `cat ~/Documents/Docent/research/storm-surge-ghana-deep-sources.json` — should be a list of dicts with `title`, `url`, `source_type`

**If OpenCode server is unavailable:**
- Should print an actionable error ("please run `opencode serve --port 4096`"), not a traceback

**Result (2026-05-12): PASSED**

---

## 5. `to-notebook` — after docent deep research

```
docent studio to-notebook
```
**Expect:**
- Auto-detects `storm-surge-ghana-deep.md` as the most recent output
- Creates `<output_dir>/storm-surge-ghana-deep-notebook/` directory
- `sources_urls.txt` contains one URL per line — verify URLs look real (arxiv, journals, web)
- `guide.md` contains step-by-step NotebookLM instructions with URLs listed
- A copy of `storm-surge-ghana-deep.md` is inside the notebook directory
- NotebookLM opens in the browser (`https://notebooklm.google.com`)

**Edge case:** run again immediately — should succeed (overwrites existing notebook dir)

**Result (2026-05-12): PASSED**

---

## 6. `to-notebook` — with explicit file

```
docent studio to-notebook --output-file storm-surge-ghana-deep.md
```
**Expect:** Same result as #5 but using the explicit path.
**Result (2026-05-12): PASSED**

---

## 7. `to-notebook` — error: no sources file (Feynman backend)

If you have a `.md` file in output_dir with no matching `-sources.json`:
```
touch ~/Documents/Docent/research/orphan-test.md
docent studio to-notebook --output-file orphan-test.md
```
**Expect:** `ok=False`, message says "No sources file found… Sources are only saved when using backend='docent'. The Feynman backend does not expose individual sources."
**Result (2026-05-12): PASSED**

---

## 8. `to-notebook` — error: empty output dir

```
docent studio config-set --key output_dir --value /tmp/empty-research-dir
docent studio to-notebook
```
**Expect:** `ok=False`, message says "No research output found… Run `docent studio deep-research` or `docent studio lit` first."
(Reset output_dir to your real path afterward.)
**Result (2026-05-12): PASSED**

---

## 9. Literature review — docent backend

```
docent studio lit "coastal erosion West Africa" --backend docent
```
**Expect:**
- Same pipeline stages but with lit-specific planner/writer prompts
- Output: `<output_dir>/coastal-erosion-west-africa-lit.md`
- Review file: `<output_dir>/coastal-erosion-west-africa-lit-review.md`
- Sources file: `…-lit-sources.json`
- **References in markdown:** `.md` file should end with `## References` section
- Sources list should contain more Semantic Scholar / arXiv entries than web snippets

**Result (2026-05-12): PASSED** — but duplicate References section found (Tavily output already had one + we appended another). Fixed: `_append_references()` now strips existing `## References` before appending.

---

## 10. Feynman backend — deep research

Requires Feynman installed globally (`npm install -g feynman`).
```
docent studio deep-research "sea level rise adaptation" --backend feynman
```
**Expect:**
- Feynman starts up (its progress is printed directly to terminal — you see it running)
- After completion: `<output_dir>/sea-level-rise-adaptation-deep.md` created (copy of Feynman's output)
- NO sources file created (Feynman backend doesn't expose sources)
- `docent studio to-notebook --output-file sea-level-rise-adaptation-deep.md` → fails with "No sources file found"

**Result (2026-05-12): FAILED — FileNotFoundError.** Feynman not on PATH gave raw traceback. Fixed: new `_find_feynman()` resolves PATH + Windows npm fallback, `FeynmanNotFoundError` gives install instructions. Pending: user needs to reinstall feynman (npm only) and set up Anthropic API credits before re-testing.

---

## 11. Feynman backend — budget guard

```
docent studio config-set --key feynman_budget_usd --value 0.01
docent studio deep-research "test topic" --backend feynman
```
**Expect:** Guard fires immediately (0.01 limit, session spend at 90% = $0.009 threshold) OR runs and hits the guard after the first call.
Message: "Feynman budget nearly exhausted ($X.XX of $0.01 spent). Increase with `docent studio config-set feynman_budget_usd <amount>` or use backend='docent'."
(Reset budget to 0.0 afterward.)

---

## 12. Feynman update notification

Start docent with any command:
```
docent reading show
```
**Expect:** If Feynman has a newer npm version than what's cached, a yellow notice prints at startup:
`UPDATE AVAILABLE: feynman X.X.X is available (run: npm install -g feynman)`

To test when already up to date: delete the update cache file under `~/.docent/cache/updates/feynman.json` and run again — should either show the notice (if newer version) or be silent (if up to date).

---

## 13. OC spend tracking

After running a docent-backend research (test #4 or #9):
```
docent studio usage
```
**Expect:** OC spend > $0.0000 (some amount was tracked from the pipeline calls).
Verify the spend file directly:
```
cat ~/.docent/cache/research/oc_spend.json
```
Should show today's date and a non-zero `spend_usd`.

---

## 14. BYOK / provider config

```
docent studio config-set --key oc_provider --value anthropic
docent studio config-set --key oc_model_planner --value claude-sonnet-4-5
docent studio config-show
```
**Expect:** Config-show shows updated `oc_provider` and `oc_model_planner`.
Then run a short research to confirm the pipeline uses the new model (check that it doesn't crash with an unknown model error on the OpenCode side).
Reset to defaults afterward:
```
docent studio config-set --key oc_provider --value opencode-go
docent studio config-set --key oc_model_planner --value glm-5.1
```

---

## 15. Peer review — Feynman backend

```
docent studio review "2401.12345" --backend feynman
```
**Expect:** Feynman starts review workflow for the given arXiv ID. Output: `<output_dir>/2401-12345-review.md`.

---

## 16. MCP tool exposure

```
docent serve &
```
Then in another terminal, check the tool list (e.g. via Claude Desktop or a curl to the MCP stdio server). The following tools should appear:
- `studio__deep_research`
- `studio__get_paper`
- `studio__lit`
- `studio__review`
- `studio__search_papers`
- `studio__to_notebook`
- `studio__usage`
- `studio__config_show`
- `studio__config_set`

---

## 17. UI integration

Start the UI: `docent ui`

Check that the research tool actions work via the MCP sidebar in Claude Desktop (the `/docent` server). Run `research deep` from within a Claude conversation using the MCP tools. Verify the output file appears in `output_dir`.

---

## 18. Tavily quota exhaustion — graceful failure

When the Tavily monthly free tier (1,000 calls) is exhausted, the pipeline should fail with a clear message rather than silently falling back to a path that also uses Tavily.

To test without actually burning quota, temporarily set an invalid Tavily key:
```
docent studio config-set --key tavily_api_key --value tvly-invalid-key-for-testing
docent studio deep-research "test topic" --backend docent
```
**Expect:** An error message about invalid API key (not a silent fallthrough). The error should mention "Tavily" and suggest checking the key.

For quota-specific testing (only possible when quota is actually exhausted):
- Should return: "Tavily monthly free tier (1,000 calls) has been exceeded. Wait for the next billing cycle, upgrade your Tavily plan, or use backend='feynman' which does not require Tavily."
- Should NOT fall back to manual pipeline (which would also fail with Tavily)
- `backend='feynman'` should still work normally

(Reset key to real value afterward: `docent studio config-set --key tavily_api_key --value <real_key>`)

---

## 19. References section in output markdown

After running test #4 or #9, inspect the output `.md` file:
```
cat ~/Documents/Docent/research/storm-surge-ghana-deep.md | tail -30
```
**Expect:**
- The markdown file ends with a `## References` section
- Each entry is numbered (1., 2., 3., …)
- Each entry includes: title (bold), optional authors, URL, and source type in brackets
- Example: `1. **Climate Change in Ghana** — https://example.com/climate [web]`
- Sources without a URL are skipped
- The `*-sources.json` file is still present alongside the `.md` file (both exist)

---

## 20. `to-notebook` full pipeline — phase progress

After test #4 (deep research done), run:
```
docent studio to-notebook
```
**Expect (watch terminal phase tags — all must appear in order):**
- `nlm-check` — "Checking NotebookLM auth..."
- `nlm-research` — "Starting NLM web research: '...'" (NLM web research arm fires non-blocking)
- `nlm-push` — "Adding synthesis document..." then "[1/N] https://..."
- `nlm-research` — "Polling NLM research status..." then "NLM research found N new source(s). Adding..."
- `nlm-stabilise` — "Waiting for sources to stabilise..." then "Stable after Xs: ready: N, error: N, preparing: 0"
- `nlm-quality` — "Running quality gate (validation + contradictions + gaps)..."
- `nlm-quality` — "Quality gate: clean/issues found, N contradiction(s), N gap(s) identified."
- `nlm-perspectives` — "Generating practitioner / skeptic / beginner summaries..."
- `nlm-perspectives` — "Perspectives generated."

**Expect final success message:** "Notebook ready: N source(s) added, N from NLM research, quality gate: ..., perspectives generated, notebook: <id>"

---

## 21. `to-notebook` quality gate — shape output

After test #20, check the rendered shapes in the output:
```
docent studio to-notebook
```
**Expect metric shapes:**
- `Notebook ID` — a non-empty string
- `Sources added` — non-zero integer
- `From NLM research` — non-zero integer (if NLM research found sources)
- `Validation` — either `clean` or `issues found`
- `Contradictions` — integer (0 or more)
- `Gaps filled` — integer (only shown if > 0)
- `Local package` — link to the `<stem>-notebook/` directory

---

## 22. `to-notebook` — skip quality gate and perspectives

```
docent studio to-notebook --no-run-quality-gate --no-run-perspectives
```
**Expect:**
- No `nlm-quality` phase events in terminal
- No `nlm-perspectives` phase events in terminal
- Final message does NOT contain "quality gate:" or "perspectives generated"
- Completes noticeably faster (no NLM ask calls)

---

## 23. `to-notebook` — skip NLM web research arm

```
docent studio to-notebook --no-run-nlm-research
```
**Expect:**
- No `nlm-research` phase events at all
- Goes straight from `nlm-push` (synthesis doc + Feynman URLs) to `nlm-stabilise`
- Final message does NOT contain "from NLM research"

---

## 24. `to-notebook` with `--guide-file`

Create a small guide file first:
```
echo "Focus on sea-level rise adaptation strategies in low-lying coastal zones." > ~/Documents/guide.txt
docent studio to-notebook --guide-file ~/Documents/guide.txt
```
**Expect:**
- Progress event: `nlm-push` — "Adding guide file: guide.txt..."
- Guide file is added as a source (source count increments)
- NLM web research query is enriched — should reflect the guide content in the research query
- If guide file path doesn't exist: progress event "Guide file not found: ... -- ignoring." (no crash)

**Edge case — missing guide file:**
```
docent studio to-notebook --guide-file /tmp/nonexistent-guide.txt
```
**Expect:** "Guide file not found" warning printed, pipeline continues normally.

---

## 25. `to-notebook` with `--notebook-id`

Find the notebook ID from test #20 (shown in the final message or Metric shape).
Then run with a fresh research file:
```
docent studio to-notebook --notebook-id <id-from-test-20>
```
**Expect:**
- No "Creating notebook..." event (skips create step)
- Goes straight to auth check → push sources into the existing notebook
- Deduplication is active: sources already in the notebook are not re-added
- Final message shows the same notebook ID

---

## 26. `to-notebook` self-learning — run-log.jsonl writeback

After any successful `to-notebook` run (test #20 or later):
```
Get-Content $env:USERPROFILE\.claude\skills\research-to-notebook\run-log.jsonl | Select-Object -Last 1 | python -m json.tool
```
**Expect (in the last JSON line):**
- `"timestamp"` — ISO format, today's date
- `"mode"` — `"research"`
- `"topic"` — non-empty string matching your research topic
- `"notebook_id"` — non-empty string
- `"duration_min"` — positive number
- `"sources_final"` — positive integer
- `"quality_gate"` — dict with `"validation"`, `"contradictions"`, `"gaps_filled"`, `"multi_perspective_combined": true`
- `"guide_file"` — `null` (or path if you used `--guide-file`)

---

## 27. `to-notebook` self-learning — source-compat.json domain update

After any `to-notebook` run that adds URL sources:
```
python -m json.tool $env:USERPROFILE\.claude\skills\research-to-notebook\source-compat.json
```
**Expect:**
- `"last_updated"` equals today's date (YYYY-MM-DD)
- `"domains"` section has entries for domains from added URLs, each with:
  - `"success"` — count of successful adds from this domain
  - `"fail"` — count of failed adds
  - `"rate"` — float between 0 and 1 (rounded to 2 decimals)

**Expect NOT:**
- File should NOT be overwritten from scratch — it accumulates across runs
- `"always_skip"` and any pre-existing domain entries should be preserved

---

## 28. `to-notebook` active overrides — skip_gap_analysis

```
$json = '{"skip_gap_analysis": true}'
$dir = "$env:USERPROFILE\.claude\skills\research-to-notebook"
$json | Set-Content "$dir\active-overrides.json" -Encoding utf8
docent studio to-notebook
```
**Expect:**
- Progress event: "Gap analysis disabled by active-overrides (skip_gap_analysis=true)."
- Quality gate STILL runs (validation + contradictions sections)
- But no "Filling gap: '...'" events
- `gaps_filled` = 0 in run-log.jsonl

**Clean up afterward:**
```
Remove-Item "$env:USERPROFILE\.claude\skills\research-to-notebook\active-overrides.json"
```

---

## 29. `to-local` — happy path

After test #4 (deep research done):
```
docent studio to-local
```
**Expect:**
- Creates `<output_dir>/storm-surge-ghana-deep-local/` directory
- Contains `storm-surge-ghana-deep.md` (copy of synthesis doc)
- Contains `sources_urls.txt` with one URL per line (if sources file exists)
- Message: "Local package: .../storm-surge-ghana-deep-local -- N source URL(s)"
- Shape output: `Local package` link pointing to the directory

**Edge case — run again immediately:** should overwrite (no crash).

---

## 30. `to-local` with explicit file

```
docent studio to-local --output-file storm-surge-ghana-deep.md
```
**Expect:** Same result as #29 but using the explicit path.

---

## 31. `to-local` with `--guide-file`

```
echo "Focus on adaptation policy." > ~/Documents/guide.txt
docent studio to-local --guide-file ~/Documents/guide.txt
```
**Expect:**
- Package directory created as in #29
- `guide.txt` is ALSO copied into the `<stem>-local/` directory alongside the synthesis doc

---

## 32. `to-local` error — no research output

```
docent studio config-set --key output_dir --value /tmp/empty-to-local-test
docent studio to-local
```
**Expect:** `ok=False`, message: "No research output found in ... Run `docent studio deep-research` or `docent studio lit` first."
(Reset output_dir to your real path afterward.)

---

## 33. `guide_file` in `deep-research` and `lit`

Create a guide file with focused context:
```
echo "Prioritise peer-reviewed studies from 2018-2024. Focus on West Africa." > ~/Documents/research-guide.txt
docent studio deep-research "coastal flooding" --guide-file ~/Documents/research-guide.txt --backend docent
```
**Expect:**
- Pipeline runs normally
- The guide context is prepended to the research brief sent to OpenCode/Tavily
- Output markdown should reflect the guide's framing (check that West Africa / peer-reviewed framing appears in the introduction)

Repeat for `lit`:
```
docent studio lit "coastal flooding" --guide-file ~/Documents/research-guide.txt --backend docent
```
**Expect:** Same — guide context shapes the literature search.

---

## 34. MCP tool list — `to_local` exposed

```
docent serve &
```
Then via Claude Desktop or MCP client, check that `studio__to_local` appears in the tool list alongside the existing tools from test #16.
(This is a delta check on top of #16 — the full expected list now includes `studio__to_local`.)

---

## Priority order for testing

Given time constraints, run in this order:

1. **#1** — smoke (confirms CLI surface is intact) ✅
2. **#2** — config-show/set (confirms settings layer works) ✅
3. **#4** — docent deep research (core happy path — the longest but most important) ✅
4. **#5** — to-notebook (primary deliverable of the whole tool) ✅
5. **#3 + #13** — usage before and after #4 (confirms spend tracking) ✅
6. **#7 + #8** — to-notebook error cases (robustness) ✅
7. **#9** — lit review (secondary happy path)
8. **#19** — verify references section in output markdown
9. **#18** — Tavily quota exhaustion (use invalid key test)

**New pipeline port tests (run after credits reset ~2026-05-17):**

10. **#20** — full pipeline phase progress (most important new test — validates all 4 phases fire)
11. **#21** — quality gate shape output (validate metric shapes)
12. **#29** — to-local happy path (fast, no NLM needed)
13. **#26 + #27** — run-log + source-compat writeback (verify self-learning side effects)
14. **#22** — skip quality gate/perspectives (fast negative path)
15. **#23** — skip NLM research arm
16. **#24** — guide-file in to-notebook
17. **#28** — active-overrides skip_gap_analysis
18. **#25** — explicit notebook-id
19. **#31 + #32** — to-local guide-file + error case
20. **#33** — guide-file in deep-research and lit
21. **#34** — MCP to_local exposed
22. **#10** — Feynman backend (if Feynman is installed)
23. **#11** — budget guard (if you have time)
24. **#12** — update notification (check cache file)

**Why:** #20 is the critical new test — it validates that all 4 phases of the pipeline fire in order. #29 is the quickest new win (to-local is fast and self-contained). #26 + #27 confirm self-learning writes happen without interfering with the run. Error paths (#22, #23, #31, #32) are cheap. Guide-file and overrides tests (#24, #28, #33) validate the new params. MCP exposure (#34) is the only delta check on the existing #16.
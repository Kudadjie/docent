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
10. **#10** — Feynman backend (if Feynman is installed)
11. **#11** — budget guard (if you have time)
12. **#12** — update notification (check cache file)

**Why:** #4 → #5 → #13 is the core pipeline and validates the most shipped code. Error cases (#7, #8) are quick and confirm graceful failure paths. New #18 and #19 validate the latest changes (quota handling + references in markdown).
---
name: Research tool real-life tests
description: Full checklist of manual real-life tests to run on the research-to-notebook tool before marking v1.2.0 ready
type: project
---

# Research-to-Notebook: Real-Life Test Checklist

All commands assume the global `docent` install is current (`uv tool install --reinstall --editable .`).
Run from any directory unless a test specifies otherwise.

---

## 1. Smoke: CLI surface

```
docent research --help
```
**Expect:** `deep`, `lit`, `review`, `to-notebook`, `usage`, `config-show`, `config-set` all listed.

---

## 2. Config: show and set

```
docent research config-show
```
**Expect:** Prints `output_dir`, `feynman_command`, `feynman_budget_usd`, all `oc_model_*` fields, `oc_budget_usd`, `oc_provider`.

```
docent research config-set --key output_dir --value ~/Documents/Docent/research
docent research config-show
```
**Expect:** `output_dir` updated. Verify persisted in `~/.docent/config.toml` under `[research]`.

---

## 3. Usage: baseline zero

```
docent research usage
```
**Expect:** Today's date, Feynman spend $0.0000, OC spend $0.0000 (both "(no limit)" if budgets unset).
If a spend file exists from today, spend may be non-zero — that's correct.

---

## 4. Docent pipeline — deep research

```
docent research deep "storm surge Ghana" --backend docent
```
**Expect (watch terminal):**
- Progress events for all 6 stages: `planner → fetch → gap → writer → verifier → reviewer`
- No crash; may take 3–10 minutes depending on OpenCode server speed
- Output: `<output_dir>/storm-surge-ghana-deep.md` created
- Review file: `<output_dir>/storm-surge-ghana-deep-review.md` created
- Sources file: `<output_dir>/storm-surge-ghana-deep-sources.json` created
- Check sources JSON: `cat ~/Documents/Docent/research/storm-surge-ghana-deep-sources.json` — should be a list of dicts with `title`, `url`, `source_type`

**If OpenCode server is unavailable:**
- Should print an actionable error ("please run `opencode serve --port 4096`"), not a traceback

---

## 5. `to-notebook` — after docent deep research

```
docent research to-notebook
```
**Expect:**
- Auto-detects `storm-surge-ghana-deep.md` as the most recent output
- Creates `<output_dir>/storm-surge-ghana-deep-notebook/` directory
- `sources_urls.txt` contains one URL per line — verify URLs look real (arxiv, journals, web)
- `guide.md` contains step-by-step NotebookLM instructions with URLs listed
- A copy of `storm-surge-ghana-deep.md` is inside the notebook directory
- NotebookLM opens in the browser (`https://notebooklm.google.com`)

**Edge case:** run again immediately — should succeed (overwrites existing notebook dir)

---

## 6. `to-notebook` — with explicit file

```
docent research to-notebook --output-file storm-surge-ghana-deep.md
```
**Expect:** Same result as #5 but using the explicit path.

---

## 7. `to-notebook` — error: no sources file (Feynman backend)

If you have a `.md` file in output_dir with no matching `-sources.json`:
```
touch ~/Documents/Docent/research/orphan-test.md
docent research to-notebook --output-file orphan-test.md
```
**Expect:** `ok=False`, message says "No sources file found… Sources are only saved when using backend='docent'. The Feynman backend does not expose individual sources."

---

## 8. `to-notebook` — error: empty output dir

```
docent research config-set --key output_dir --value /tmp/empty-research-dir
docent research to-notebook
```
**Expect:** `ok=False`, message says "No research output found… Run `docent research deep` or `docent research lit` first."
(Reset output_dir to your real path afterward.)

---

## 9. Literature review — docent backend

```
docent research lit "coastal erosion West Africa" --backend docent
```
**Expect:**
- Same 6-stage pipeline but planner biases toward paper search (Semantic Scholar queries)
- Output: `<output_dir>/coastal-erosion-west-africa-lit.md`
- Sources file: `…-lit-sources.json`
- Sources list should contain more Semantic Scholar / arXiv entries than web snippets

---

## 10. Feynman backend — deep research

Requires Feynman installed globally (`npm install -g feynman`).
```
docent research deep "sea level rise adaptation" --backend feynman
```
**Expect:**
- Feynman starts up (its progress is printed directly to terminal — you see it running)
- After completion: `<output_dir>/sea-level-rise-adaptation-deep.md` created (copy of Feynman's output)
- NO sources file created (Feynman backend doesn't expose sources)
- `docent research to-notebook --output-file sea-level-rise-adaptation-deep.md` → fails with "No sources file found"

---

## 11. Feynman backend — budget guard

```
docent research config-set --key feynman_budget_usd --value 0.01
docent research deep "test topic" --backend feynman
```
**Expect:** Guard fires immediately (0.01 limit, session spend at 90% = $0.009 threshold) OR runs and hits the guard after the first call.
Message: "Feynman budget nearly exhausted ($X.XX of $0.01 spent). Increase with `docent research config-set feynman_budget_usd <amount>` or use backend='docent'."
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
docent research usage
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
docent research config-set --key oc_provider --value anthropic
docent research config-set --key oc_model_planner --value claude-sonnet-4-5
docent research config-show
```
**Expect:** Config-show shows updated `oc_provider` and `oc_model_planner`.
Then run a short research to confirm the pipeline uses the new model (check that it doesn't crash with an unknown model error on the OpenCode side).
Reset to defaults afterward:
```
docent research config-set --key oc_provider --value opencode-go
docent research config-set --key oc_model_planner --value glm-5.1
```

---

## 15. Peer review — Feynman backend

```
docent research review "2401.12345" --backend feynman
```
**Expect:** Feynman starts review workflow for the given arXiv ID. Output: `<output_dir>/2401-12345-review.md`.

---

## 16. MCP tool exposure

```
docent serve &
```
Then in another terminal, check the tool list (e.g. via Claude Desktop or a curl to the MCP stdio server). The following tools should appear:
- `research__deep`
- `research__lit`
- `research__review`
- `research__to_notebook`
- `research__usage`
- `research__config_show`
- `research__config_set`

---

## 17. UI integration

Start the UI: `docent ui`

Check that the research tool actions work via the MCP sidebar in Claude Desktop (the `/docent` server). Run `research deep` from within a Claude conversation using the MCP tools. Verify the output file appears in `output_dir`.

---

## Priority order for testing

Given time constraints, run in this order:

1. **#1** — smoke (confirms CLI surface is intact)
2. **#2** — config-show/set (confirms settings layer works)
3. **#4** — docent deep research (core happy path — the longest but most important)
4. **#5** — to-notebook (primary deliverable of the whole tool)
5. **#3 + #13** — usage before and after #4 (confirms spend tracking)
6. **#7 + #8** — to-notebook error cases (robustness)
7. **#9** — lit review (secondary happy path)
8. **#10** — Feynman backend (if Feynman is installed)
9. **#11** — budget guard (if you have time)
10. **#12** — update notification (check cache file)

**Why:** #4 → #5 → #13 is the core pipeline and validates the most shipped code. Error cases (#7, #8) are quick and confirm graceful failure paths.

---
name: Studio real-life tests
description: Full checklist of manual real-life tests for the studio tool. All results cleared for full re-run. New tests added for free tier, guide-files, and MCP synthesis prompt.
type: project
---

# Studio: Real-Life Test Checklist

All commands assume the global `docent` install is current (`uv tool install --editable .`).
Run from any directory unless a test specifies otherwise.

---

## 1. Smoke: CLI surface

```
docent studio --help
```
**Expect:** `deep-research`, `get-paper`, `lit`, `review`, `search-papers`, `to-notebook`,
`to-local`, `usage`, `config-show`, `config-set` all listed.

---

## 2. Config: show and set

```
docent studio config-show
```
**Expect:** Prints `output_dir`, `feynman_command`, `feynman_budget_usd`, all `oc_model_*`
fields, `oc_budget_usd`, `oc_provider`.

```
docent studio config-set --key output_dir --value ~/Documents/Docent/research
docent studio config-show
```
**Expect:** `output_dir` updated. Verify persisted in `~/.docent/config.toml` under `[studio]`.

---

## 3. Usage: baseline zero

```
docent studio usage
```
**Expect:** Today's date, Feynman spend $0.0000, OC spend $0.0000 (both "(no limit)" if
budgets unset). If a spend file exists from today, spend may be non-zero — that's correct.

---

## 4. Docent pipeline — deep research

```
docent studio deep-research --topic "storm surge Ghana" --backend docent
```

**Expect (watch terminal):**
- Progress events for pipeline stages
- No crash; may take 3–10 minutes depending on Tavily + OpenCode server speed
- Output: `<output_dir>/storm-surge-ghana-deep.md` created
- Review file: `<output_dir>/storm-surge-ghana-deep-review.md` created
- Sources file: `<output_dir>/storm-surge-ghana-deep-sources.json` created
- `storm-surge-ghana-deep.md` ends with a `## References` section with numbered entries

**If OpenCode server is unavailable:**
- Should print an actionable error ("please run `opencode serve --port 4096`"), not a traceback

---

## 5. `to-notebook` — after docent deep research

```
docent studio to-notebook
```
**Expect:**
- Auto-detects `storm-surge-ghana-deep.md` as the most recent output
- Creates `<output_dir>/storm-surge-ghana-deep-notebook/` directory
- `sources_urls.txt` contains one URL per line
- NotebookLM opens in the browser

**Edge case:** run again immediately — should succeed (overwrites existing notebook dir)

---

## 6. `to-notebook` — with explicit file

```
docent studio to-notebook --output-file storm-surge-ghana-deep.md
```
**Expect:** Same result as #5 but using the explicit path.

---

## 7. `to-notebook` — error: no sources file (Feynman backend)

```
echo "" > ~/Documents/Docent/research/orphan-test.md
docent studio to-notebook --output-file orphan-test.md
```
**Expect:** `ok=False`, message says "No sources file found…"

---

## 8. `to-notebook` — error: empty output dir

```
docent studio config-set --key output_dir --value /tmp/empty-research-dir
docent studio to-notebook
```
**Expect:** `ok=False`, message says "No research output found…"
(Reset output_dir to your real path afterward.)

---

## 9. Literature review — docent backend

```
docent studio lit --topic "coastal erosion West Africa" --backend docent
```
**Expect:**
- Output: `<output_dir>/coastal-erosion-west-africa-lit.md`
- Review file: `<output_dir>/coastal-erosion-west-africa-lit-review.md`
- Sources file: `…-lit-sources.json`
- `.md` file ends with `## References` section

---

## 10. Feynman backend — deep research

Requires Feynman installed globally (`npm install -g feynman`).
```
docent studio deep-research --topic "sea level rise adaptation" --backend feynman
```
**Expect:**
- Feynman starts up (its progress is printed directly to terminal)
- After completion: `<output_dir>/sea-level-rise-adaptation-deep.md` created
- NO sources file created (Feynman backend doesn't expose sources)
- `docent studio to-notebook --output-file sea-level-rise-adaptation-deep.md` → fails with "No sources file found"

---

## 11. Feynman backend — budget guard

```
docent studio config-set --key feynman_budget_usd --value 0.01
docent studio deep-research --topic "test topic" --backend feynman
```
**Expect:** Guard fires immediately or after the first call.
Message mentions budget exhausted and suggests increasing the limit.
(Reset budget to 0.0 afterward.)

---

## 12. Feynman update notification

```
docent reading show
```
**Expect:** If Feynman has a newer npm version than cached, a yellow notice prints:
`UPDATE AVAILABLE: feynman X.X.X is available (run: npm install -g feynman)`

---

## 13. OC spend tracking

After running test #4 or #9:
```
docent studio usage
```
**Expect:** OC spend > $0.0000.
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
**Expect:** Config-show shows updated values. Run a short research to confirm no crash.
Reset afterward:
```
docent studio config-set --key oc_provider --value opencode-go
docent studio config-set --key oc_model_planner --value glm-5.1
```

---

## 15. Peer review — Feynman backend

```
docent studio review --artifact "2401.12345" --backend feynman
```
**Expect:** Output: `<output_dir>/2401-12345-review.md`.

---

## 16. MCP tool exposure

```
docent serve
```
Then via a connected MCP client, the following tools must appear:
- `studio__deep_research`
- `studio__lit`
- `studio__review`
- `studio__compare`
- `studio__draft`
- `studio__replicate`
- `studio__audit`
- `studio__get_paper`
- `studio__search_papers`
- `studio__scholarly_search`
- `studio__to_notebook`
- `studio__to_local`
- `studio__usage`
- `studio__config_show`
- `studio__config_set`

---

## 17. UI integration

Start the UI: `docent ui`
Check that research tool actions work via MCP in Claude Desktop. Run a research action
from within a Claude conversation. Verify the output file appears in `output_dir`.

---

## 18. Tavily quota exhaustion — graceful failure (docent backend)

Set an invalid Tavily key to simulate quota exhaustion:
```
docent studio config-set --key tavily_api_key --value tvly-invalid-key-for-testing
docent studio deep-research --topic "test topic" --backend docent
```
**Expect:** Clear error message mentioning "Tavily" and suggesting checking the key.
Not a silent fallthrough.
(Reset key afterward: `docent studio config-set --key tavily_api_key --value <real_key>`)

---

## 19. References section in output markdown

After test #4 or #9:
```
Get-Content ~/Documents/Docent/research/storm-surge-ghana-deep.md | Select-Object -Last 30
```
**Expect:**
- File ends with a `## References` section
- Each entry is numbered (1., 2., 3., …)
- Each entry includes: title (bold), optional authors, URL, and source type in brackets

---

## 20. `to-notebook` full pipeline — phase progress

After test #4 (deep research done):
```
docent studio to-notebook
```
**Expect all phases in order:** `nlm-check` → `nlm-research` → `nlm-push` → `nlm-stabilise`
→ `nlm-quality` → `nlm-perspectives`

**Final message:** "Notebook ready: N source(s) added, quality gate: ..., perspectives generated"

---

## 21. `to-notebook` quality gate — shape output

After test #20, check metric shapes:
- `Notebook ID` — non-empty string
- `Sources added` — non-zero integer
- `Validation` — either `clean` or `issues found`
- `Contradictions` — integer (0 or more)
- `Local package` — link to the `<stem>-notebook/` directory

---

## 22. `to-notebook` — skip quality gate and perspectives

```
docent studio to-notebook --no-run-quality-gate --no-run-perspectives
```
**Expect:** No `nlm-quality` or `nlm-perspectives` phase events. Completes faster.

---

## 23. `to-notebook` — skip NLM web research arm

```
docent studio to-notebook --no-run-nlm-research
```
**Expect:** No `nlm-research` events. Goes straight from push to stabilise.

---

## 24. `to-notebook` with `--guide-files`

```
echo "Focus on sea-level rise adaptation in low-lying coastal zones." > ~/Documents/guide.txt
docent studio to-notebook --guide-files ~/Documents/guide.txt
```
**Expect:**
- `nlm-push` event: "Adding guide file: guide.txt..."
- Guide file added as a source

**Edge case — missing guide file:**
```
docent studio to-notebook --guide-files /tmp/nonexistent-guide.txt
```
**Expect:** Warning printed ("could not be read"), asked to confirm. Pipeline continues or
exits cleanly depending on user choice.

---

## 25. `to-notebook` with `--notebook-id`

```
docent studio to-notebook --notebook-id <id-from-test-20>
```
**Expect:** Skips create step. Pushes into existing notebook. Deduplication active.

---

## 26. `to-notebook` self-learning — run-log.jsonl writeback

After any successful `to-notebook` run:
```
Get-Content $env:USERPROFILE\.claude\skills\research-to-notebook\run-log.jsonl |
  Select-Object -Last 1 | python -m json.tool
```
**Expect:** `timestamp`, `mode`, `topic`, `notebook_id`, `duration_min`, `sources_final`,
`quality_gate` keys all present.

---

## 27. `to-notebook` self-learning — source-compat.json domain update

```
python -m json.tool $env:USERPROFILE\.claude\skills\research-to-notebook\source-compat.json
```
**Expect:** `last_updated` = today's date. `domains` section has entries with `success`,
`fail`, `rate` per domain. Accumulates across runs (not overwritten from scratch).

---

## 28. `to-notebook` active overrides — skip_gap_analysis

```powershell
'{"skip_gap_analysis": true}' | Set-Content "$env:USERPROFILE\.claude\skills\research-to-notebook\active-overrides.json" -Encoding utf8
docent studio to-notebook
```
**Expect:** "Gap analysis disabled by active-overrides" event. No "Filling gap:" events.
`gaps_filled` = 0 in run-log.
```powershell
Remove-Item "$env:USERPROFILE\.claude\skills\research-to-notebook\active-overrides.json"
```

---

## 29. `to-local` — happy path

After test #4:
```
docent studio to-local
```
**Expect:** Creates `<output_dir>/storm-surge-ghana-deep-local/` with `storm-surge-ghana-deep.md`
and `sources_urls.txt`. Message shows source URL count.

---

## 30. `to-local` with explicit file

```
docent studio to-local --output-file storm-surge-ghana-deep.md
```
**Expect:** Same result as #29.

---

## 31. `to-local` with `--guide-files`

```
echo "Focus on adaptation policy." > ~/Documents/guide.txt
docent studio to-local --guide-files ~/Documents/guide.txt
```
**Expect:** Package directory created as in #29. `guide.txt` is copied into the local package.

---

## 32. `to-local` error — no research output

```
docent studio config-set --key output_dir --value /tmp/empty-to-local-test
docent studio to-local
```
**Expect:** `ok=False`, message: "No research output found…"
(Reset output_dir afterward.)

---

## 33. `--guide-files` in `deep-research` and `lit` — individual files

```
echo "Prioritise peer-reviewed studies from 2018-2024. Focus on West Africa." > ~/Documents/research-guide.txt
docent studio deep-research --topic "coastal flooding" --guide-files ~/Documents/research-guide.txt --backend docent
```
**Expect:** Pipeline runs normally. Guide context shapes the research brief.

```
docent studio lit --topic "coastal flooding" --guide-files ~/Documents/research-guide.txt --backend docent
```
**Expect:** Same — guide context shapes the literature search.

---

## 34. MCP tool list — all studio tools exposed (delta check)

With `docent serve` running, verify `studio__to_local`, `studio__compare`, `studio__draft`,
`studio__replicate`, `studio__audit` appear alongside the tools listed in #16.

---

## 35. Free tier — deep research (Tavily key present)

```
docent studio deep-research --topic "coastal pollution West Africa" --backend free
```
**Expect (before pipeline starts):**
- Disclaimer printed with all bullet points (no AI synthesis, quality caveat, provider list,
  local LLMs coming soon, MCP synthesis tip)
- Prompt: "I understand the limitations. Proceed with the free tier? [y/N]"
- Enter `y` to continue

**Expect (pipeline output):**
- `web_search` — "Searching the web via Tavily…"
- `paper_search` — "Searching academic papers…" → "Found N papers via google_scholar/semantic_scholar"
- `compile` — "Compiling output document…"
- `done` — "Output written to …/coastal-pollution-in-west-africa-deep-free.md"

**Inspect the output file:**
- Top: `> **FREE TIER OUTPUT**` disclaimer blockquote
- Section: `## Web Search Results` with numbered entries, each showing `*(via Tavily)*`
- Section: `## Academic Papers` with title, authors, year, DOI/URL, abstract snippet
- Section: `## Sources` with markdown links
- Footer: human-facing tip about sharing with an AI assistant (NOT the `[AI Assistant — Action Required]` block)

---

## 36. Free tier — deep research (no Tavily key)

Temporarily clear your Tavily key:
```
docent studio config-set --key tavily_api_key --value ""
docent studio deep-research --topic "wave energy Ghana" --backend free
```
After disclaimer + confirm:

**Expect:**
- `web_search` — "No Tavily key — trying DuckDuckGo…"
- `web_search` — "DuckDuckGo returned N results (lower quality than Tavily…)"
- Web results section shows `*(via DuckDuckGo (lower quality — no Tavily key configured))*` label
- Academic papers still present

(Restore Tavily key afterward.)

---

## 37. Free tier — Tavily quota exhausted → DuckDuckGo fallback

Set an invalid key to simulate exhausted quota:
```
docent studio config-set --key tavily_api_key --value tvly-invalid-key-for-testing
docent studio deep-research --topic "storm surge modelling" --backend free
```
After disclaimer + confirm:

**Expect:**
- `web_search` — "Searching the web via Tavily…"
- `web_search` — "Tavily API key invalid: … Falling back to DuckDuckGo…" (or quota exhausted message)
- `web_search` — "DuckDuckGo returned N results. Note: results are broader and less curated than Tavily."
- Web results section shows `*(via DuckDuckGo (fallback — lower quality))*`
- Pipeline completes with both web and academic results

(Reset key afterward.)

---

## 38. Free tier — deep research with guide files

```
echo "Focus on storm surge modelling methods." > ~/Documents/storm-guide.txt
docent studio deep-research --topic "storm surge Ghana" --backend free --guide-files ~/Documents/storm-guide.txt
```
**Expect:**
- Disclaimer shown, proceed with `y`
- Guide context section appears in output document above web results
- Search query is sharpened by guide content (check web result titles for relevance)

---

## 39. Free tier — folder guide files expansion

Create a folder with multiple guide files:
```powershell
New-Item -ItemType Directory -Force ~/Documents/research-guides
"Focus on West Africa." | Set-Content ~/Documents/research-guides/region.txt
"Prioritise 2019-2024 papers." | Set-Content ~/Documents/research-guides/timeframe.md
docent studio deep-research --topic "coastal erosion" --backend free --guide-files ~/Documents/research-guides
```
**Expect:**
- Both `region.txt` and `timeframe.md` are read and concatenated into guide context
- Guide context section in output shows content from both files

---

## 40. Free tier — unreadable guide file: warn and confirm

```powershell
[System.IO.File]::WriteAllBytes("$env:TEMP\bad-guide.md", [byte[]](0xFF,0xFE,0x00,0x01))
docent studio deep-research --topic "flood risk" --backend free --guide-files "$env:TEMP\bad-guide.md"
```
**Expect (before pipeline):**
- Warning: "The following guide file(s) could not be read:"
- `✗ bad-guide.md  (unreadable or corrupted)`
- Prompt: "Proceed anyway (skipping the files above)? [y/N]"
- Enter `y` → pipeline runs without the bad file
- Enter `n` → exits cleanly, no pipeline runs

---

## 41. Free tier — literature review

```
docent studio lit --topic "sea level rise West Africa" --backend free
```
**Expect:**
- Disclaimer + confirm
- `paper_search` — two rounds (scholarly + Semantic Scholar supplement)
- NO `web_search` events (lit free tier is academic-only)
- Output: `<output_dir>/sea-level-rise-west-africa-lit-free.md`
- File contains `## Papers` section with 10–40 papers
- File contains human-facing footer tip (NOT the MCP synthesis block)

---

## 42. Free tier — decline disclaimer

```
docent studio deep-research --topic "test" --backend free
```
At the "Proceed with the free tier? [y/N]" prompt, press Enter (default No) or type `n`.

**Expect:** Exits cleanly with no output file created.

---

## 43. MCP free tier — synthesis prompt in output

**Setup:** Ensure `docent serve` is running and connected to Claude (or another MCP client).

In the AI conversation, invoke:
```
Use the studio deep_research tool with topic="storm surge adaptation" and backend="free"
```

**Expect (AI behaviour):**
1. Tool runs — progress events stream in the MCP response
2. The output document is written to disk with the `_MCP_SYNTHESIS_PROMPT` footer (not the human tip)
3. The AI reads the result and **proactively offers synthesis** before showing the results — e.g.:
   *"I've compiled your research results using Docent's free tier. Would you like me to synthesise this into a structured research brief with an introduction, key findings, critical analysis, and conclusions?"*
4. If you say yes, the AI uses the document sections as source material and produces a coherent brief

**Verify the document footer (open the output file):**
- Contains: `[Instructions for the AI assistant reading this via MCP]`
- Contains: `"Would you like me to synthesise this into a structured research brief…"`
- Does NOT contain the human-facing tip text

---

## 44. MCP free tier — lit via MCP

Same as #43 but using `studio__lit` with `backend="free"`.

**Expect:**
- AI offers synthesis offer before presenting the paper list
- Output file footer is `_MCP_SYNTHESIS_PROMPT` (MCP variant), not the human tip

---

## 45. MCP vs CLI footer distinction

Run the same topic twice:

```
# CLI run:
docent studio deep-research --topic "coastal flooding" --backend free
```
Then via MCP in Claude:
```
studio__deep_research topic="coastal flooding" backend="free"
```

Open both output files and compare the footers:
- CLI file (`coastal-flooding-deep-free.md`): ends with `**Tip:** Share this document...`
- MCP file (`coastal-flooding-deep-free.md` — note: same slug, will overwrite — check before CLI run):
  ends with `[Instructions for the AI assistant reading this via MCP]`

**Expect:** Distinct footers confirming `via_mcp` is correctly threaded from `Context` to the pipeline.

> **Tip for test #45:** Run the MCP version first, copy the output file, then run the CLI version and compare.

---

## Priority order for re-run

### Tier 1 — Core smoke (run first, confirm nothing is broken)
1. **#1** — CLI surface smoke
2. **#2** — config show/set
3. **#3** — usage baseline

### Tier 2 — Free tier (new, no credits needed, run immediately)
4. **#35** — free deep research with Tavily
5. **#36** — free deep research without Tavily (DuckDuckGo)
6. **#37** — Tavily quota exhaustion → DuckDuckGo fallback
7. **#41** — free lit review
8. **#42** — decline disclaimer (quick negative path)
9. **#38** — free deep research with guide file
10. **#40** — unreadable guide file warning + confirm

### Tier 3 — Guide files (no credits needed)
11. **#33** — guide-files in deep-research and lit (docent backend, offline check only)
12. **#39** — folder guide expansion

### Tier 4 — Paid backends (requires OpenCode credits)
13. **#4** — docent deep research
14. **#9** — docent lit review
15. **#13** — OC spend tracking (after #4/#9)
16. **#19** — references section in output

### Tier 5 — to-notebook / to-local pipeline
17. **#5** — to-notebook happy path (after #4)
18. **#29** — to-local happy path
19. **#20** — full pipeline phase progress
20. **#21** — quality gate shape output
21. **#22** — skip quality gate/perspectives
22. **#23** — skip NLM research arm
23. **#24** — guide-files in to-notebook
24. **#26 + #27** — self-learning writeback
25. **#28** — active-overrides
26. **#25** — explicit notebook-id
27. **#31 + #32** — to-local guide-file + error case

### Tier 6 — MCP synthesis prompt (requires MCP client connected)
28. **#43** — MCP free tier deep research + synthesis offer
29. **#44** — MCP free tier lit + synthesis offer
30. **#45** — CLI vs MCP footer distinction

### Tier 7 — Miscellaneous
31. **#16** — full MCP tool list
32. **#34** — delta MCP tool list check
33. **#18** — Tavily quota graceful failure (docent backend)
34. **#10** — Feynman backend (if installed)
35. **#11** — budget guard
36. **#12** — update notification

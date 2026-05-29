# Studio — UI Specification

**Tool:** `studio`  
**Version:** Docent v1.2.0  
**Last updated:** 2026-05-18  
**Audience:** Designer / frontend developer

---

## 1. Overview

Studio is Docent's research workflow engine. It lets researchers run deep literature searches, literature reviews, peer reviews, paper comparisons, draft generation, replication guides, and methodology audits — then push the output to NotebookLM or an Obsidian vault. Research can be done on the free tier (no AI, instant) or via any major AI provider (Feynman, OpenCode/docent, Groq, Gemini, Anthropic, OpenAI, local LLMs). The tool serves two audiences: individual researchers running CLI commands, and AI assistants consuming studio via MCP.

Actions: `deep-research`, `lit`, `review`, `compare`, `draft`, `replicate`, `audit`, `to-notebook`, `search-papers`, `get-paper`, `scholarly-search`, `read-output`, `save-synthesis`, `config-show`, `config-set` (15 total).

---

## 2. Actions Table

| Action | Input fields | Output type | Notes |
|--------|-------------|-------------|-------|
| `deep-research` | `topic: str` (req), `backend: str` (default `feynman`), `output: str` (default `local`), `to_notebook: bool` (default `false`), `guide_files: list[str]` (opt), `confirmed: bool` (default `false`) | `ResearchResult` | Generator — yields progress events. Free backend shows disclaimer + confirm prompt. Emits pricing note for AI backends. |
| `lit` | Same as `deep-research` | `ResearchResult` | Generator. Free backend is academic-only (no web search). Slug: `{topic}-lit` or `{topic}-lit-free`. |
| `review` | `artifact: str` (req — arXiv ID / PDF path / URL), `backend: str` (default `feynman`), `output: str`, `guide_files` | `ResearchResult` | Generator. No free backend. Requires OpenCode (`docent`) or Feynman. |
| `compare` | `artifact_a: str` (req), `artifact_b: str` (req), `backend: str`, `output: str`, `guide_files` | `ResearchResult` | Generator. Compares two artifacts side-by-side. Slug: `{a}-vs-{b}-compare`. |
| `draft` | `topic: str` (req), `backend: str`, `output: str`, `guide_files` | `ResearchResult` | Generator. Produces a paper section or document. |
| `replicate` | `artifact: str` (req), `backend: str`, `output: str`, `guide_files` | `ResearchResult` | Generator. Builds a step-by-step replication guide. |
| `audit` | `artifact: str` (req), `backend: str`, `output: str`, `guide_files` | `ResearchResult` | Generator. Audits methodology, claim validity, reproducibility. |
| `to-notebook` | `output_file: str\|null`, `sources_file: str\|null`, `topic: str\|null`, `max_sources: int` (default 20), `notebook_id: str\|null`, `guide_files: list[str]`, `run_nlm_research: bool` (default `true`), `run_quality_gate: bool` (default `true`), `run_perspectives: bool` (default `true`), `output_files: list[str]` | `ToNotebookResult` | Generator — 6-phase pipeline: `nlm-check` → `nlm-research` → `nlm-push` → `nlm-stabilise` → `nlm-quality` → `nlm-perspectives`. Falls back to browser-open if NLM unavailable. |
| `search-papers` | `query: str` (req), `max_results: int` (default 10) | `SearchPapersResult` | Synchronous. Uses alphaXiv API. |
| `get-paper` | `arxiv_id: str` (req — ID or URL) | `GetPaperResult` | Synchronous. Returns abstract + AI overview via alphaXiv. |
| `scholarly-search` | `query: str` (req), `max_results: int` (default 10) | `ScholarlySearchResult` | Synchronous. Google Scholar → Semantic Scholar → CrossRef fallback chain. |
| `read-output` | `output_file: str` (req — absolute path) | `ReadOutputResult` | Synchronous. MCP-only utility: reads a research output file for AI synthesis. |
| `save-synthesis` | `source_output_file: str` (req), `content: str` (req), `summary: str` (req) | `SaveSynthesisResult` | Synchronous. MCP-only utility: saves AI synthesis adjacent to the source file. |
| `config-show` | _(none)_ | `ConfigShowResult` | Synchronous. Displays all research settings, masking API keys. |
| `config-set` | `key: str` (req), `value: str` (req) | `ConfigSetResult` | Synchronous. Validates against known keys; rejects unknowns. |

---

## 3. Backend Enum

All research actions accept a `backend` field from this set:

| Backend | Tier | Requirements | MCP-safe? |
|---------|------|-------------|-----------|
| `free` | Zero-cost | None (Tavily optional) | Yes — completes in seconds |
| `feynman` | AI (10–30 min) | Feynman CLI installed | No — times out via MCP |
| `docent` | AI (3–10 min) | OpenCode server + API credits | No — times out via MCP |
| `groq` | AI (fast, cheap) | `GROQ_API_KEY` | No |
| `gemini` | AI (free tier available) | `GEMINI_API_KEY` | No |
| `openrouter` | AI (varies) | `OPENROUTER_API_KEY` | No |
| `mistral` | AI | `MISTRAL_API_KEY` | No |
| `cerebras` | AI | `CEREBRAS_API_KEY` | No |
| `anthropic` | AI (expensive) | `ANTHROPIC_API_KEY` | No |
| `openai` | AI | `OPENAI_API_KEY` | No |
| `ollama` | Local AI | Ollama running | No |
| `lm_studio` | Local AI | LM Studio running | No |
| `local` | Local AI | Custom base URL | No |

**UI rule:** Via MCP, always recommend `free` first and show a warning that AI backends time out. For CLI, present all options.

---

## 4. Primary Flows

### Flow 1 — Free-tier deep research (no API key needed)
1. User enters topic
2. User selects `free` backend
3. System shows disclaimer (no AI synthesis, quality caveat, provider list, DuckDuckGo fallback note)
4. User reads disclaimer, types `y` to confirm (default `N` exits cleanly)
5. Pipeline runs: `web_search` → `paper_search` → `compile` → `done`
6. Output file written: `{topic-slug}-deep-free.md`
7. File contains: disclaimer blockquote, web results section, academic papers section, sources section, human-facing tip

### Flow 2 — AI deep research (docent backend)
1. User enters topic + selects `docent` backend
2. System prints pricing note (yellow warning)
3. Preflight: checks OpenCode server is reachable, verifies model has credits
4. If preflight fails: shows `FAIL` message with fix instructions, exits
5. Pipeline runs 6 stages: `search_plan` → `fetch` → `synthesise` → `write` → `verify` → `review`
6. Tavily research runs first; if it fails, falls back to manual search
7. Three files written: `{slug}-deep.md`, `{slug}-deep-review.md`, `{slug}-deep-sources.json`
8. Output `.md` ends with `## References` section (numbered entries)

### Flow 3 — Research → NotebookLM
1. After Flow 1 or 2 completes, user runs `to-notebook`
2. If `output_file` omitted, auto-detects most recent `.md` in `output_dir`
3. NotebookLM auth is checked **up front in the preflight** for any run that will push to NotebookLM (`output=notebook`, `--to-notebook`, or the `to-notebook` action), so a stale session fails fast *before* an expensive research run rather than after. `_nlm_push` Phase 0 re-checks as a fallback (in case auth lapses mid-run). In both places, recovery depends on context: a real terminal (CLI) runs `notebooklm login` inline; a no-TTY caller (UI subprocess or any `via_mcp` caller) opens a visible login terminal and polls auth for up to 2 min while the user signs in, then continues
4. Sources ranked and deduplicated (max 20 by default, capped at 1 per domain)
5. Local package written: `{stem}-notebook/` with `sources_urls.txt` + copy of `.md`
6. Pipeline phases stream in order:
   - `nlm-check` — verify NLM auth
   - `nlm-research` — NLM web research arm runs concurrently (skip with `--no-run-nlm-research`)
   - `nlm-push` — add synthesis doc + source URLs; adds guide files if supplied
   - `nlm-stabilise` — wait for sources to become active, delete failed ones
   - `nlm-quality` — 3-section quality gate: validation / contradictions / gap analysis (skip with `--no-run-quality-gate`)
   - `nlm-perspectives` — 3 summaries: practitioner / skeptic / beginner (skip with `--no-run-perspectives`)
7. Quality report written to `{stem}-notebook/quality-report.md`
8. Result shows: notebook ID, sources added, NLM research count, validation status

### Flow 4 — Paper search and lookup
1. User enters query for `search-papers` or `scholarly-search`
2. Results render as metric rows: `Title (Year) — Authors et al.` + link to arXiv/DOI
3. User picks a paper, calls `get-paper` with arXiv ID
4. Returns: title, abstract, AI-generated overview (truncated to 600 chars in shapes)
5. Link to `https://arxiv.org/abs/{id}` shown

### Flow 5 — Config management
1. User calls `config-show` to see all settings
2. API keys are masked: `sk-a...4321` (first 4 + last 4 chars); unset fields show `(not set)`
3. User calls `config-set --key output_dir --value ~/path`
4. Unknown keys are rejected with a list of all valid keys
5. Settings persisted to `~/.docent/config.toml` under `[research]`

---

## 5. Result Shapes

### ResearchResult
Used by: `deep-research`, `lit`, `review`, `compare`, `draft`, `replicate`, `audit`

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | Whether the workflow succeeded |
| `backend` | `str` | Backend used: `feynman`, `docent`, `free`, etc. |
| `workflow` | `str` | Workflow type: `deep`, `lit`, `review`, `compare`, `draft`, `replicate`, `audit` |
| `topic_or_artifact` | `str` | The topic string or artifact identifier |
| `output_file` | `str\|null` | Absolute path to the primary output `.md` |
| `returncode` | `int\|null` | Process exit code (Feynman branch only; `null` for docent/free) |
| `message` | `str` | Human-readable status or error message |
| `notebook_id` | `str\|null` | NotebookLM notebook ID if `output=notebook` |
| `vault_path` | `str\|null` | Obsidian vault path if `output=vault` |

**Shapes rendered:** `ErrorShape` on failure; `MessageShape(success)` + optional `LinkShape(output_file)` + optional `MetricShape(notebook_id)` + optional `LinkShape(vault_path)` on success.

### ToNotebookResult

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | Whether the pipeline succeeded |
| `output_file` | `str\|null` | Research `.md` used |
| `sources_file` | `str\|null` | Sources JSON used |
| `package_dir` | `str\|null` | Local package directory path |
| `sources_count` | `int` | Total sources ranked |
| `sources_added` | `int` | Sources successfully added to NLM |
| `sources_failed` | `int` | Sources that failed to add |
| `sources_from_feynman` | `int` | Sources from Feynman/research output |
| `sources_from_nlm` | `int` | Additional sources from NLM web research arm |
| `notebook_id` | `str\|null` | NotebookLM notebook ID |
| `quality_gate` | `dict\|null` | `{validation, contradictions, gaps, gaps_filled, raw}` |
| `perspectives` | `dict\|null` | `{practitioner, skeptic, beginner}` |
| `message` | `str` | Summary with save hint if notebook_id is new |

**Quality gate sub-fields:**

| Field | Type | Description |
|-------|------|-------------|
| `validation` | `str` | `"clean"` or `"issues found"` |
| `contradictions` | `int` | Count of source-vs-source contradictions |
| `gaps` | `list[str]` | Identified missing subtopics |
| `gaps_filled` | `int` | Gaps where follow-up research was added |
| `raw` | `str` | Full quality gate response text |

**Perspectives sub-fields:** `practitioner`, `skeptic`, `beginner` — each a multi-paragraph markdown string.

### SearchPapersResult / ScholarlySearchResult

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | Success flag |
| `query` | `str` | Search query used |
| `papers` | `list[dict]` | Paper objects (see Paper dict below) |
| `count` | `int` | Number of results |
| `backend_used` | `str` | (`ScholarlySearch` only) `google_scholar`, `semantic_scholar`, or `crossref` |
| `message` | `str` | Status message |

**Paper dict fields:** `title`, `authors: list[str]`, `year`, `doi`, `arxiv_id`, `arxiv_url`, `abstract`, `published`.

### GetPaperResult

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | Success flag |
| `arxiv_id` | `str` | Normalised arXiv ID |
| `title` | `str\|null` | Paper title |
| `abstract` | `str` | Full abstract |
| `overview` | `str` | AI-generated overview (alphaXiv) |
| `message` | `str` | Status message |

### ConfigShowResult

| Field | Type | Description |
|-------|------|-------------|
| `config_path` | `str` | Absolute path to `config.toml` |
| `output_dir` | `str` | Research output directory |
| `feynman_command` | `list[str]` | Feynman invocation (default `["feynman"]`) |
| `oc_provider` | `str` | OpenCode provider (default `opencode-go`) |
| `oc_model_planner` | `str` | Planner model |
| `oc_model_writer` | `str` | Writer model |
| `oc_model_verifier` | `str` | Verifier model |
| `oc_model_reviewer` | `str` | Reviewer model |
| `oc_model_researcher` | `str` | Researcher model |
| `tavily_api_key` | `str\|null` | Masked if set |
| `tavily_research_timeout` | `float` | Default 600s |
| `semantic_scholar_api_key` | `str\|null` | Masked if set |
| `feynman_model` | `str\|null` | Override model for Feynman |
| `feynman_timeout` | `float` | Default 900s |
| `notebooklm_notebook_id` | `str\|null` | Default notebook |
| `notebooklm_source_limit` | `int` | Default 50 |
| `obsidian_vault` | `str\|null` | Vault path |
| `alphaxiv_api_key` | `str\|null` | Masked if set |

### ConfigSetResult

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | Whether the key was valid and saved |
| `key` | `str` | Setting key |
| `value` | `str` | New value |
| `config_path` | `str` | File path where persisted |
| `message` | `str` | Confirmation or rejection message |

### ReadOutputResult / SaveSynthesisResult

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | Success |
| `output_file` / `saved_file` | `str` | File path |
| `content` / `summary` | `str` | File content / chat-display summary |
| `word_count` | `int` | Word count |
| `message` | `str` | Instruction for AI agent |

---

## 6. Progress Events (Generator Actions)

Generator actions yield `ProgressEvent(phase, message, level?, current?, total?)` before returning the result. The UI should stream these as live log lines.

### Deep-research / Lit phases

| Phase | Level | Description |
|-------|-------|-------------|
| `cost` | `warn` | Pricing note for AI backends — shown before any work begins |
| `start` | `info` | Feynman branch: reports Feynman startup |
| `research` | `info` | Docent branch: Tavily research starting |
| `search_plan` | `info` | Generating search strategy |
| `fetch` | `info` | Fetching web + paper queries |
| `synthesise` | `info` | Running synthesis |
| `write` | `info` | Writing draft |
| `verify` | `info` | Verifying output |
| `review` | `info` | Peer-review pass |
| `web_search` | `info` | Free tier: Tavily / DuckDuckGo search |
| `paper_search` | `info` | Free tier: academic paper search |
| `compile` | `info` | Free tier: compiling output document |
| `done` | `info` | Output file written |

### To-notebook phases

| Phase | Level | Description |
|-------|-------|-------------|
| `package` | `info` | Local package written |
| `nlm-check` | `info` | Verifying NotebookLM auth |
| `nlm-research` | `info` | NLM web research arm running concurrently |
| `nlm-push` | `info` | Adding synthesis doc + source URLs; guide files |
| `nlm-stabilise` | `info` | Waiting for sources to activate; deleting failures |
| `nlm-quality` | `info` | Running quality gate (validation/contradictions/gaps) |
| `nlm-perspectives` | `info` | Generating 3-perspective summaries |

### Error events

| Phase | Level | Trigger |
|-------|-------|---------|
| `error` | `error` | Tavily key invalid/rejected |
| `warn` | `warn` | Tavily quota exhausted (DuckDuckGo fallback) |
| `warn` | `warn` | DuckDuckGo returned results of lower quality |

---

## 7. Free-Tier Disclaimer Flow

This interactive gate runs before the free-tier pipeline starts — **it must be preserved exactly as a blocking confirmation step in the UI.**

1. System prints the disclaimer block (styled yellow/bold):
   - No AI synthesis
   - Quality depends on search coverage
   - Tavily optional (1k/month free), DuckDuckGo fallback
   - This is a starting point, not a finished report
   - Provider list for AI-backed research
   - MCP tip for AI assistant users
2. Prompt: `I understand the limitations. Proceed with the free tier? [y/N]`
3. Default is **N** — pressing Enter exits cleanly, no file created
4. Typing `y` starts the pipeline

Via MCP, the first call without `confirmed=true` returns a `confirmation_required` response with the disclaimer text. The AI must show it to the user, receive acknowledgment, then call again with `confirmed=true`.

---

## 8. Guide Files

The `guide_files` field is accepted by `deep-research`, `lit`, `review`, `compare`, `draft`, `replicate`, `audit`, and `to-notebook`.

- Pass individual files: `--guide-files notes.md --guide-files outline.txt`
- Pass a folder: `--guide-files ~/research-guides/` (all `.md`, `.txt`, `.pdf` inside are included)
- Unreadable files trigger a warning and a `Proceed anyway? [y/N]` prompt before the pipeline starts
- Guide content is prepended to the topic/prompt under a `## Guide context (filename)` heading
- In `to-notebook`: each guide file is added as a source in NLM and the guide content focuses the NLM web research query

---

## 9. Output Routing

The `output` field (default `local`) and shorthand `to_notebook: bool` control where the finished output goes:

| Value | Behaviour |
|-------|-----------|
| `local` | Write to `output_dir` only |
| `notebook` | Write to `output_dir` then immediately push to NotebookLM (runs `to-notebook` inline) |
| `vault` | Write to `output_dir` then copy to Obsidian vault (`obsidian_vault` config key) |

---

## 10. Edge Cases & Error States

### Preflight failures (docent/feynman backends)
- **OpenCode not running** → `FAIL Model check failed: not reachable at http://127.0.0.1:4096. Start with: opencode serve --port 4096`. Exits before pipeline starts.
- **Insufficient API credits** → `FAIL Model {model} is not usable: Insufficient API credits... Top up your account or switch to --backend free`. Exits before pipeline starts.
- **Model rate-limited** → `FAIL Model {model} is not usable: Model rate-limited... Wait a moment and retry`.
- **Feynman not found** → `ResearchResult(ok=False, message="Feynman not found. Install with: npm install -g @companion-ai/feynman@latest")`

### Tavily errors (docent backend)
- **Invalid key** → Bold red `error` progress event. Pipeline continues without web search (academic sources only).
- **Quota exhausted** → Yellow `warn` event. DuckDuckGo fallback. Pipeline continues.

### to-notebook errors
- **No output file in output_dir** → `ToNotebookResult(ok=False, message="No research output found in {dir}. Run docent studio deep-research or docent studio lit first.")`
- **No sources file** → Pipeline continues without Feynman sources; NLM research arm still runs if enabled.
- **NLM unavailable** → Falls back to opening `https://notebooklm.google.com` in browser. Returns `ok=True` with local package path.
- **NLM auth expired** → CLI: runs `notebooklm login` inline (browser opens). UI subprocess: opens a visible login terminal and polls auth for up to 2 min; on timeout returns `ok=False` with a message to authenticate (Settings → NotebookLM) and re-run.

### Config errors
- **Unknown key** → `ConfigSetResult(ok=False, message="Unknown key 'foo'. Known: [sorted list]")`

### search-papers / get-paper errors
- **alphaXiv auth error** → `ok=False, message="alphaXiv API key not configured or invalid. Set alphaxiv_api_key in config."`
- **scholarly-search**: all three backends (Google Scholar, Semantic Scholar, CrossRef) fail → `ok=False, message="Search failed: {error}"`

---

## 11. Known Config Keys

All keys settable via `config-set` (validated against this list):

```
output_dir                feynman_model             oc_model_planner
feynman_timeout           studio_backend            oc_model_writer
oc_provider               groq_api_key              oc_model_verifier
groq_model                gemini_api_key            oc_model_reviewer
gemini_model              openrouter_api_key        oc_model_researcher
openrouter_model          mistral_api_key           tavily_api_key
mistral_model             cerebras_api_key          tavily_research_timeout
cerebras_model            ollama_model              semantic_scholar_api_key
ollama_base_url           lm_studio_model           notebooklm_notebook_id
lm_studio_base_url        local_model               notebooklm_source_limit
local_api_key             local_base_url            obsidian_vault
alphaxiv_api_key          feynman_command
```

---

## 12. Design Invariants

- **Free backend is the only MCP-safe research backend.** All AI backends (feynman, docent, groq, gemini, etc.) run multi-minute pipelines that will time out through an MCP connection. The UI must warn MCP users and offer the terminal command instead.
- **Pricing note always fires for AI backends.** The yellow `cost` progress event is emitted before any work starts. Do not suppress it.
- **Free-tier disclaimer is a mandatory blocking gate.** The UI must show it and require explicit confirmation. Default is No. Never pre-confirm on behalf of the user.
- **Guide files with unreadable entries require confirmation.** A file that cannot be decoded triggers a warn-and-confirm gate before the pipeline starts. Default is No.
- **API keys in config-show are always masked.** Keys shorter than 8 chars show `***`; longer keys show first 4 + `...` + last 4. Never display a full API key.
- **Sources deduplication is URL-based, domain-capped.** At most `_MAX_PER_DOMAIN` sources per domain are kept (prevents a single domain dominating). The UI should not re-sort or re-deduplicate displayed sources.
- **to-notebook self-learning writes on every run.** Run log goes to `~/.local/share/docent/notebook-learning/run-log.jsonl`; domain compat to `source-compat.json`. Both accumulate across runs. The UI must not overwrite them.
- **to-notebook active-overrides.json applies globally.** If `~/.local/share/docent/notebook-learning/active-overrides.json` exists, it suppresses steps (e.g. `skip_gap_analysis`). The UI should surface when an override is active.
- **Notebook ID save hint.** When `to-notebook` creates a new notebook (ID differs from configured value), the result `message` includes `Save with: docent studio config-set --key notebooklm_notebook_id --value {id}`. Surface this prominently.
- **`review`, `compare`, `replicate`, `audit` have no `free` backend.** They require OpenCode or Feynman.

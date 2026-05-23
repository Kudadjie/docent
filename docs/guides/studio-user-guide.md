# Studio User Guide

Studio is Docent's research tool. It runs deep research, literature reviews, peer reviews, paper comparisons, drafts, replication guides, and methodology audits — then optionally pushes everything into a Google NotebookLM notebook or an Obsidian vault.

---

## Quick start

```bash
# Instant, no API key required
docent studio deep-research --topic "storm surge Ghana" --backend free

# Full AI pipeline (requires OpenCode server + API credits)
docent studio deep-research --topic "storm surge Ghana" --backend docent

# Literature review (AI, Feynman)
docent studio lit --topic "coastal erosion West Africa" --backend feynman

# Push last research output to NotebookLM
docent studio to-notebook
```

---

## Backends

| Backend | Cost | Requirements | Best for |
|---------|------|-------------|----------|
| `free` | Free | None (Tavily optional) | Quick sweeps, no API key |
| `feynman` | AI credits | Feynman CLI (`npm install -g @companion-ai/feynman@latest`) | Comprehensive long-form research |
| `docent` | AI credits | `opencode serve --port 4096` | Structured 6-stage pipeline |
| `groq` | Free tier available | `GROQ_API_KEY` | Fast, cheap AI |
| `gemini` | Free tier available | `GEMINI_API_KEY` | Affordable AI |
| `anthropic` | Paid | `ANTHROPIC_API_KEY` | Claude models |
| `openai` | Paid | `OPENAI_API_KEY` | GPT models |
| `ollama` / `lm_studio` | Free | Local server running | Private, offline |

Switch backend at any time with `--backend <name>`.

**Important if you use Docent via Claude Desktop (MCP):** Only the `free` backend works reliably through MCP — AI backends run for several minutes and time out. For AI backends, run the `docent studio` command in your terminal directly.

---

## Deep research

```bash
docent studio deep-research --topic "TOPIC" --backend BACKEND
```

Produces three files in your `output_dir`:
- `{topic-slug}-deep.md` — the research brief (ends with `## References`)
- `{topic-slug}-deep-review.md` — auto-generated peer review
- `{topic-slug}-deep-sources.json` — structured source list for NotebookLM

### Free tier

The free tier has no AI synthesis. It aggregates:
- Web results from Tavily (free account, 1 000 calls/month) or DuckDuckGo (automatic fallback)
- Academic papers from Semantic Scholar and CrossRef (always free, no key needed)

You will see a disclaimer before the pipeline starts. Read it and type `y` to continue. The output is a raw compilation — useful as a starting point or for feeding into an AI assistant.

### AI backends (docent, feynman, groq, gemini, …)

You will see an API cost estimate before work begins. Typical costs:

| Provider | Cost per run |
|----------|-------------|
| Groq, Mistral, Cerebras | ~$0.01–$0.05 |
| Gemini (free tier) | Free |
| OpenAI GPT-4o | ~$0.20–$0.80 |
| Anthropic Claude | ~$0.50–$3.00+ |

---

## Literature review

```bash
docent studio lit --topic "TOPIC" --backend BACKEND
```

Same structure as deep research but focuses on academic literature. The free tier is academic-only (no web search). Produces `{topic-slug}-lit.md`, `...-lit-review.md`, `...-lit-sources.json`.

---

## Peer review

```bash
docent studio review --artifact "2401.12345" --backend feynman
docent studio review --artifact "/path/to/paper.pdf" --backend docent
docent studio review --artifact "https://arxiv.org/abs/2401.12345" --backend feynman
```

Artifact can be an arXiv ID, a local PDF path, or a URL. Output: `{slug}-review.md`. No free backend.

---

## Compare two papers

```bash
docent studio compare --artifact-a "2401.12345" --artifact-b "2312.67890" --backend feynman
```

Side-by-side comparison. Output: `{a-slug}-vs-{b-slug}-compare.md` + review file.

---

## Draft a document

```bash
docent studio draft --topic "Introduction to storm surge modelling" --backend feynman
```

Writes a paper section or document on the given topic. Output: `{slug}-draft.md`.

---

## Replication guide

```bash
docent studio replicate --artifact "2401.12345" --backend feynman
```

Produces a step-by-step guide to replicate a paper's experiments. Output: `{slug}-replicate.md`.

---

## Methodology audit

```bash
docent studio audit --artifact "2401.12345" --backend feynman
```

Audits a paper for methodology issues, claim validity, and reproducibility. Output: `{slug}-audit.md`.

---

## Guide files

Guide files let you steer research with your own notes, outlines, or PDFs.

```bash
# Individual file
docent studio deep-research --topic "flooding" --backend free \
  --guide-files ~/notes/research-focus.md

# Multiple files
docent studio deep-research --topic "flooding" --backend free \
  --guide-files ~/notes/scope.md --guide-files ~/notes/methods.txt

# Whole folder (all .md/.txt/.pdf inside)
docent studio deep-research --topic "flooding" --backend free \
  --guide-files ~/research-guides/
```

If a guide file can't be read (corrupted, wrong encoding), you'll see a warning and a prompt to proceed without it.

For `to-notebook`, guide files are added as sources and used to focus NotebookLM's web research query.

---

## Paper search

### Search alphaXiv

```bash
docent studio search-papers --query "storm surge adaptation"
docent studio search-papers --query "coastal flooding" --max-results 20
```

Requires `alphaxiv_api_key` in config. Returns arXiv IDs, titles, authors, and links.

### Get a specific paper

```bash
docent studio get-paper --arxiv-id "2401.12345"
docent studio get-paper --arxiv-id "https://arxiv.org/abs/2401.12345"
```

Returns the abstract and an AI-generated overview of the paper.

### Google Scholar search

```bash
docent studio scholarly-search --query "sea level rise adaptation measures"
```

Uses Google Scholar first, falls back to Semantic Scholar then CrossRef when rate-limited. No API key needed.

---

## Push to NotebookLM

```bash
# Auto-detect the most recent research output
docent studio to-notebook

# Explicit file
docent studio to-notebook --output-file storm-surge-ghana-deep.md

# Reuse an existing notebook
docent studio to-notebook --notebook-id YOUR_NOTEBOOK_ID

# Add guide files as sources
docent studio to-notebook --guide-files ~/notes/focus.md

# Skip slow phases
docent studio to-notebook --no-run-quality-gate --no-run-perspectives
docent studio to-notebook --no-run-nlm-research
```

### What the pipeline does

`to-notebook` runs six phases:

1. **nlm-check** — verifies NotebookLM auth; re-logs in if expired (opens a browser)
2. **nlm-research** — asks NotebookLM's own research arm to find additional sources (runs concurrently with source upload)
3. **nlm-push** — uploads the research brief and ranked sources; adds guide files
4. **nlm-stabilise** — waits for sources to become active; deletes ones that failed
5. **nlm-quality** — runs a 3-section quality gate: *validation* (claims vs sources), *contradictions* (source disagreements), *gap analysis* (missing subtopics)
6. **nlm-perspectives** — generates three summaries: practitioner, skeptic, beginner

A `quality-report.md` is saved alongside your research output in the local notebook package.

### Source limits

By default up to 20 sources are selected and at most 1 per domain (to avoid one site dominating). Adjust with `--max-sources N`.

### Saving the notebook ID

When `to-notebook` creates a new notebook, the output includes a save hint:

```
Save with: docent studio config-set --key notebooklm_notebook_id --value <id>
```

Run that command so future `to-notebook` runs reuse the same notebook.

---

## Output routing

Research commands support three output destinations:

```bash
# Default: save locally only
docent studio deep-research --topic "flooding" --output local

# Save locally then push to NotebookLM
docent studio deep-research --topic "flooding" --output notebook

# Save locally then copy to Obsidian vault
docent studio deep-research --topic "flooding" --output vault

# Shorthand for notebook
docent studio deep-research --topic "flooding" --to-notebook
```

The vault path is set via `docent studio config-set --key obsidian_vault --value ~/path/to/vault`.

---

## Configuration

Most settings can also be edited directly in **Settings → Studio** in the UI (`docent ui`).

### Show all settings

```bash
docent studio config-show
```

API keys are masked (first 4 + `...` + last 4 characters).

### Set a value

```bash
docent studio config-set --key output_dir --value ~/Documents/Docent/research
docent studio config-set --key tavily_api_key --value tvly-xxxxxxxxxxxxxxxx
docent studio config-set --key oc_provider --value anthropic
docent studio config-set --key oc_model_planner --value claude-sonnet-4-5
docent studio config-set --key feynman_model --value groq/llama-3.3-70b-versatile
docent studio config-set --key notebooklm_notebook_id --value <id>
```

Settings are stored in `~/.docent/config.toml` under `[research]`.

### Key settings reference

| Key | Default | Description |
|-----|---------|-------------|
| `output_dir` | `~/Documents/Docent/research` | Where research files are saved |
| `oc_provider` | `opencode-go` | OpenCode provider for docent backend |
| `oc_model_planner` | `glm-5.1` | Model for the planner stage |
| `oc_model_writer` | `glm-5.1` | Model for the writer stage |
| `feynman_model` | _(Feynman default)_ | Override the Feynman model |
| `feynman_timeout` | `900` | Feynman timeout in seconds |
| `tavily_api_key` | _(not set)_ | Tavily web search key (optional) |
| `tavily_research_timeout` | `600` | Tavily research timeout in seconds |
| `semantic_scholar_api_key` | _(not set)_ | Semantic Scholar key (optional) |
| `notebooklm_notebook_id` | _(not set)_ | Default NotebookLM notebook ID |
| `obsidian_vault` | _(not set)_ | Obsidian vault path |
| `alphaxiv_api_key` | _(not set)_ | alphaXiv API key for paper search |

---

## Troubleshooting

### "FAIL Model is not usable: Insufficient API credits"

Your Anthropic (or other provider) API account has no credits. Either top up at the provider's billing page, or switch to a free backend:

```bash
docent studio config-set --key oc_provider --value groq
# or
docent studio deep-research --topic "..." --backend free
```

### "OpenCode server is not running"

The `docent` backend requires OpenCode to be running:

```bash
opencode serve --port 4096
```

### "Tavily research failed… falling back to manual search"

Your Tavily key is invalid or quota is exhausted. The pipeline continues without web search using academic sources only. Get a new key at [tavily.com](https://tavily.com) (free tier: 1 000 calls/month):

```bash
docent studio config-set --key tavily_api_key --value tvly-xxxxxx
```

### "No research output found"

Run `deep-research` or `lit` first before calling `to-notebook`:

```bash
docent studio deep-research --topic "my topic" --backend free
docent studio to-notebook
```

### "No sources file found"

The Feynman backend does not expose sources. `to-notebook` requires a `*-sources.json` file which only the `docent` and `free` backends produce:

```bash
docent studio deep-research --topic "my topic" --backend docent
docent studio to-notebook
```

### NotebookLM auth expires

`to-notebook` detects auth expiry and runs `notebooklm login` automatically — a browser window opens. If you cancel, it falls back to opening `https://notebooklm.google.com` in your browser and leaving the local package intact.

---

## MCP usage

When using Docent through Claude Desktop or another MCP client, only the `free` backend works reliably. All AI backends run multi-minute pipelines and will time out.

For free-tier research from Claude:

1. Call `studio__deep_research` with `backend="free"`
2. Claude will show you the disclaimer and ask for confirmation
3. After you confirm, Claude re-calls with `confirmed=true`
4. The pipeline runs (seconds, not minutes)
5. Claude reads the output with `studio__read_output`
6. Claude synthesises it into a research brief
7. The synthesis is saved with `studio__save_synthesis`

For AI-backed research, ask Claude to give you the terminal command to run instead.

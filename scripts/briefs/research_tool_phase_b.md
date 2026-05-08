# Brief: Research Tool — Phase B (Docent pipeline backend for `deep`)

## Goal

Implement the Docent-native research pipeline for the `deep` workflow. Wire `backend="docent"` in the existing `ResearchTool.deep()` action. Do NOT touch `lit` or `review` yet.

Three new files to create:
1. `src/docent/bundled_plugins/research_to_notebook/oc_client.py` — inline OpenCode REST client
2. `src/docent/bundled_plugins/research_to_notebook/search.py` — web + paper search + page fetch
3. `src/docent/bundled_plugins/research_to_notebook/pipeline.py` — 6-stage deep research pipeline

One existing file to modify:
4. `src/docent/bundled_plugins/research_to_notebook/__init__.py` — wire `backend="docent"` in `deep()`

Tests:
5. `tests/test_research_search.py` — unit tests for search.py
6. `tests/test_research_pipeline.py` — unit tests for pipeline.py (mock OcClient + search)

---

## File 1: `oc_client.py`

Inline OpenCode REST API client. Mirrors the core logic from `scripts/oc_delegate.py` but as a Python class (no subprocess, no file I/O).

```python
"""Thin OpenCode REST API client for in-process LLM calls."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

_BASE_URL = "http://127.0.0.1:4096"
_DEFAULT_PROVIDER = "opencode-go"


class OcUnavailableError(RuntimeError):
    """Raised when OpenCode server is not reachable."""


class OcClient:
    """Send a prompt to the OpenCode REST API and return the response text.

    Usage:
        client = OcClient()
        text = client.call("Summarise X", model="glm-5.1")
    """

    def __init__(self, base_url: str = _BASE_URL, provider: str = _DEFAULT_PROVIDER) -> None:
        self.base_url = base_url
        self.provider = provider

    def is_available(self) -> bool:
        try:
            result = self._api("GET", "/global/health")
            return bool(result.get("healthy"))
        except (OcUnavailableError, Exception):
            return False

    def call(self, prompt: str, model: str = "glm-5.1", timeout: int = 300) -> str:
        """Create a session, send the prompt, return the text response."""
        session_id = self._api("POST", "/session", {})["id"]
        response = self._api(
            "POST",
            f"/session/{session_id}/message",
            {
                "parts": [{"type": "text", "text": prompt}],
                "role": "user",
                "model": {"modelID": model, "providerID": self.provider},
            },
            timeout=timeout,
        )
        return "\n".join(
            p["text"] for p in response.get("parts", []) if p.get("type") == "text"
        )

    def _api(self, method: str, path: str, body: dict | None = None, timeout: int = 10) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.URLError as e:
            raise OcUnavailableError(
                f"OpenCode server not reachable at {self.base_url}. "
                "Run: opencode serve --port 4096"
            ) from e
```

---

## File 2: `search.py`

Three public functions. All return plain Python dicts/lists — no Pydantic.

### `web_search(query, max_results=8) -> list[dict]`

Uses `duckduckgo_search.DDGS`. Returns list of `{"title": str, "url": str, "snippet": str}`.

```python
from duckduckgo_search import DDGS

def web_search(query: str, max_results: int = 8) -> list[dict]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")} for r in results]
    except Exception:
        return []
```

Note: ddg can raise on rate limit — catch all exceptions, return empty list (caller handles gracefully).

### `paper_search(query, max_results=5) -> list[dict]`

Uses Semantic Scholar API via `httpx`. Returns list of `{"title": str, "url": str, "snippet": str, "authors": str, "year": int | None}`.

Endpoint: `https://api.semanticscholar.org/graph/v1/paper/search`
Params: `query=<query>`, `fields=title,abstract,authors,year,externalIds`, `limit=<max_results>`

```python
import httpx

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_S2_FIELDS = "title,abstract,authors,year,externalIds"

def paper_search(query: str, max_results: int = 5) -> list[dict]:
    try:
        resp = httpx.get(
            f"{_S2_BASE}/paper/search",
            params={"query": query, "fields": _S2_FIELDS, "limit": max_results},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for p in data.get("data", []):
            authors = ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3])
            arxiv_id = (p.get("externalIds") or {}).get("ArXiv")
            url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
            results.append({
                "title": p.get("title") or "",
                "url": url,
                "snippet": (p.get("abstract") or "")[:500],
                "authors": authors,
                "year": p.get("year"),
            })
        return results
    except Exception:
        return []
```

### `fetch_page(url, max_chars=3000) -> str`

Fetches a URL with `httpx`, strips HTML tags, returns first `max_chars` of text. Returns empty string on error.

```python
import re

def fetch_page(url: str, max_chars: int = 3000) -> str:
    if not url:
        return ""
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "Docent/1.0"})
        resp.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return ""
```

---

## File 3: `pipeline.py`

The 6-stage deep research pipeline. All stages use `OcClient`.

Agent prompts are loaded from `agents/` directory relative to this file's location:
```python
_AGENTS_DIR = Path(__file__).parent / "agents"

def _load_prompt(name: str) -> str:
    return (_AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
```

### Public function: `run_deep(topic, oc, *, on_progress=None) -> dict`

```python
def run_deep(
    topic: str,
    oc: OcClient,
    *,
    on_progress: Callable[[str, str], None] | None = None,
) -> dict:
    """Run the full deep research pipeline. Returns result dict."""
```

`on_progress(phase, message)` is called at each stage so the action can yield ProgressEvents.

Return value:
```python
{
    "topic": str,
    "draft": str,         # verifier output (with citations)
    "review": str,        # reviewer output
    "sources": list[dict],  # all sources collected
    "rounds": int,        # how many search rounds were run
    "ok": bool,
    "error": str | None,
}
```

### Stage implementation

```python
import json
from pathlib import Path
from typing import Callable

from .oc_client import OcClient
from .search import web_search, paper_search, fetch_page

_AGENTS_DIR = Path(__file__).parent / "agents"

def _load_prompt(name: str) -> str:
    return (_AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")

def _progress(on_progress, phase, message):
    if on_progress:
        on_progress(phase, message)

def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response, tolerating markdown fences."""
    text = text.strip()
    # Strip ```json ... ``` fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)

def run_deep(topic: str, oc: OcClient, *, on_progress=None) -> dict:
    sources: list[dict] = []
    rounds = 0

    # Stage 1: Search planner
    _progress(on_progress, "search_plan", "Generating search strategy...")
    planner_prompt = _load_prompt("search_planner").replace("{topic}", topic)
    try:
        plan_text = oc.call(planner_prompt, model="glm-5.1")
        plan = _parse_json(plan_text)
    except Exception as e:
        return {"topic": topic, "draft": "", "review": "", "sources": [], "rounds": 0, "ok": False, "error": f"Search planner failed: {e}"}

    web_queries = plan.get("web_queries", [])
    paper_queries = plan.get("paper_queries", [])
    all_queries = web_queries + plan.get("domain_queries", [])

    # Stage 2: Fetch
    def _fetch_round(web_qs, paper_qs):
        nonlocal sources
        _progress(on_progress, "fetch", f"Fetching {len(web_qs)} web + {len(paper_qs)} paper queries...")
        for q in web_qs:
            results = web_search(q, max_results=6)
            for r in results:
                r["query"] = q
                r["source_type"] = "web"
                sources.append(r)
        for q in paper_qs:
            results = paper_search(q, max_results=4)
            for r in results:
                r["query"] = q
                r["source_type"] = "paper"
                sources.append(r)
        # Fetch full text for top web results (first 5 unique URLs)
        seen_urls = set()
        fetched = 0
        for s in sources:
            if s.get("source_type") == "web" and s.get("url") and s["url"] not in seen_urls and fetched < 5:
                s["full_text"] = fetch_page(s["url"])
                seen_urls.add(s["url"])
                fetched += 1

    _fetch_round(all_queries, paper_queries)
    rounds += 1

    # Stage 3: Gap evaluator (max 2 rounds)
    MAX_ROUNDS = 2
    while rounds < MAX_ROUNDS:
        _progress(on_progress, "gap_eval", f"Evaluating coverage (round {rounds})...")
        snippets_summary = "\n".join(
            f"[{i+1}] {s.get('title','?')} — {s.get('snippet','')[:120]}"
            for i, s in enumerate(sources[:20])
        )
        gap_prompt = (
            _load_prompt("gap_evaluator")
            .replace("{topic}", topic)
            .replace("{snippet_count}", str(len(sources)))
            .replace("{snippets_summary}", snippets_summary)
        )
        try:
            gap_text = oc.call(gap_prompt, model="glm-5.1")
            gap = _parse_json(gap_text)
        except Exception:
            break  # If gap eval fails, proceed with what we have
        if gap.get("sufficient", True):
            break
        additional = gap.get("additional_queries", [])
        if not additional:
            break
        _fetch_round(additional, [])
        rounds += 1

    # Deduplicate sources by URL
    seen = set()
    unique_sources = []
    for s in sources:
        key = s.get("url") or s.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique_sources.append(s)
    sources = unique_sources[:30]  # cap at 30 sources

    # Stage 4: Writer
    _progress(on_progress, "write", f"Synthesising {len(sources)} sources into draft...")
    sources_text = "\n\n".join(
        f"[Source {i+1}] {s.get('title','Untitled')}\n"
        f"URL: {s.get('url','')}\n"
        f"{'Authors: ' + s.get('authors','') + chr(10) if s.get('authors') else ''}"
        f"{s.get('full_text') or s.get('snippet','')}"
        for i, s in enumerate(sources)
    )
    writer_prompt = (
        _load_prompt("writer")
        .replace("{topic}", topic)
        .replace("{source_count}", str(len(sources)))
        .replace("{sources}", sources_text)
    )
    try:
        draft = oc.call(writer_prompt, model="minimax-m2.7", timeout=600)
    except Exception as e:
        return {"topic": topic, "draft": "", "review": "", "sources": sources, "rounds": rounds, "ok": False, "error": f"Writer failed: {e}"}

    # Stage 5: Verifier
    _progress(on_progress, "verify", "Anchoring citations...")
    verifier_prompt = (
        _load_prompt("verifier")
        .replace("{draft}", draft)
        .replace("{sources}", sources_text)
    )
    try:
        verified_draft = oc.call(verifier_prompt, model="glm-5.1", timeout=300)
    except Exception:
        verified_draft = draft  # fall back to unverified draft

    # Stage 6: Reviewer
    _progress(on_progress, "review", "Running adversarial review...")
    reviewer_prompt = _load_prompt("reviewer").replace("{draft}", verified_draft)
    try:
        review = oc.call(reviewer_prompt, model="deepseek-v4-pro", timeout=300)
    except Exception:
        review = "(Reviewer unavailable)"

    return {
        "topic": topic,
        "draft": verified_draft,
        "review": review,
        "sources": sources,
        "rounds": rounds,
        "ok": True,
        "error": None,
    }
```

---

## File 4: Modify `__init__.py`

### Replace the `backend="docent"` stub in `deep()`:

Current code (stub):
```python
if inputs.backend == "docent":
    return ResearchResult(
        ok=False,
        backend="docent",
        workflow="deep",
        topic_or_artifact=inputs.topic,
        output_file=None,
        returncode=None,
        message="Docent pipeline backend is not yet available. Use backend='feynman'.",
    )
```

Replace with generator logic. The `deep` action must become a **generator** when `backend="docent"` (it yields `ProgressEvent` objects). The action signature stays the same — it can conditionally yield or just return.

Import additions at top of `__init__.py`:
```python
from docent.core import Context, ProgressEvent, Tool, action, register_tool
```
(ProgressEvent is already exported from docent.core — check if it's in the existing imports, add if missing)

New `deep()` body for `backend="docent"`:
```python
if inputs.backend == "docent":
    from .oc_client import OcClient, OcUnavailableError
    from .pipeline import run_deep

    oc = OcClient()
    if not oc.is_available():
        return ResearchResult(
            ok=False, backend="docent", workflow="deep",
            topic_or_artifact=inputs.topic, output_file=None, returncode=None,
            message="OpenCode server is not running. Start it with: opencode serve --port 4096",
        )

    output_dir = context.settings.research.output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(inputs.topic) + "-deep"

    def _on_progress(phase, message):
        pass  # we yield from outside; update via closure

    progress_events: list[tuple[str, str]] = []

    def _capture_progress(phase, message):
        progress_events.append((phase, message))

    # Prime the generator: yield a start event
    yield ProgressEvent(phase="start", message=f"Starting Docent deep research on: {inputs.topic!r}")

    # Run pipeline (blocking — pipeline is synchronous)
    try:
        result_data = run_deep(inputs.topic, oc, on_progress=_capture_progress)
    except Exception as e:
        return ResearchResult(
            ok=False, backend="docent", workflow="deep",
            topic_or_artifact=inputs.topic, output_file=None, returncode=None,
            message=f"Pipeline error: {e}",
        )

    # Yield captured progress events
    for phase, message in progress_events:
        yield ProgressEvent(phase=phase, message=message)

    if not result_data["ok"]:
        return ResearchResult(
            ok=False, backend="docent", workflow="deep",
            topic_or_artifact=inputs.topic, output_file=None, returncode=None,
            message=result_data.get("error") or "Pipeline failed.",
        )

    # Write output files
    out_file = output_dir / f"{slug}.md"
    review_file = output_dir / f"{slug}-review.md"
    out_file.write_text(result_data["draft"], encoding="utf-8")
    review_file.write_text(result_data["review"], encoding="utf-8")

    yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

    return ResearchResult(
        ok=True, backend="docent", workflow="deep",
        topic_or_artifact=inputs.topic,
        output_file=str(out_file),
        returncode=0,
        message=f"Deep research complete. {result_data['rounds']} search round(s), {len(result_data['sources'])} sources.",
    )
```

**IMPORTANT**: The generator approach means `deep()` is now sometimes a generator (backend=docent) and sometimes returns directly (backend=feynman). Python handles this: if the function body ever contains `yield`, the whole function becomes a generator. So you need to convert ALL branches to generator form, or split into a helper.

**Correct approach**: Add a single `yield` to the feynman branch too (a dummy one), or better — convert `deep()` to always be a generator by yielding an initial progress event in all branches:

```python
@action(description="Deep research on a topic.", input_schema=DeepInputs)
def deep(self, inputs: DeepInputs, context: Context):
    if inputs.backend == "docent":
        # ... generator logic with yields ...
        return  # generator return
    # Feynman branch — make it a generator too
    yield ProgressEvent(phase="start", message=f"Starting Feynman deep research: {inputs.topic!r}")
    feynman_cmd = context.settings.research.feynman_command or ["feynman"]
    output_dir = context.settings.research.output_dir.expanduser()
    workspace_dir = output_dir / "workspace"
    slug = _slugify(inputs.topic) + "-deep"
    cmd = [*feynman_cmd, "deepresearch", inputs.topic]
    returncode, output_file = _run_feynman(cmd, workspace_dir, output_dir, slug)
    # ... return ResearchResult ...
    return ResearchResult(...)
```

Wait — this is wrong. A generator function cannot `return <value>`. It can only `return` (bare). The ResearchResult must be the last `yield` or it won't be captured.

**Actually**: In Docent's dispatcher, generator actions that `return` a value at the end — is that supported? Let me check how the reading plugin handles it.

Looking at `sync_from_mendeley` in `reading/__init__.py`:
```python
def sync_from_mendeley(self, inputs, context):
    ...
    yield ProgressEvent(phase="discover", message="...")
    ...
    return empty.model_copy(...)  # This IS a generator return value
```

So the dispatcher handles `StopIteration.value` — generator return values ARE supported. Good.

So the pattern is: yield ProgressEvents for progress, then `return FinalResult(...)` at the end. Python 3.3+ supports `return value` in generators; the value is stored in `StopIteration.value`.

So the full `deep()` action should:
1. Always be a generator (always has at least one `yield`)
2. `yield ProgressEvent(...)` for progress
3. `return ResearchResult(...)` at the end

For the Feynman branch, add one yield at the start.

---

## Tests

### `tests/test_research_search.py`

8 tests covering search.py with mocked httpx/ddg:

1. `test_web_search_returns_normalised_dicts` — mock DDGS, verify output schema
2. `test_web_search_returns_empty_on_exception` — DDGS raises, returns []
3. `test_paper_search_returns_normalised_dicts` — mock httpx.get, verify output
4. `test_paper_search_returns_empty_on_http_error` — httpx raises, returns []
5. `test_paper_search_arxiv_url_built_correctly` — paper with ArXiv ID → correct URL
6. `test_fetch_page_strips_html` — mock httpx.get with HTML, verify tags stripped
7. `test_fetch_page_truncates_to_max_chars` — long response → truncated
8. `test_fetch_page_returns_empty_on_error` — httpx raises, returns ""

### `tests/test_research_pipeline.py`

8 tests covering pipeline.py with mocked OcClient + search functions:

1. `test_run_deep_happy_path` — mock oc.call + search fns → ok=True, draft non-empty
2. `test_run_deep_planner_failure` — oc.call raises on planner → ok=False, error message
3. `test_run_deep_writer_failure` — oc.call raises on writer → ok=False
4. `test_run_deep_verifier_failure_falls_back_to_draft` — verifier raises → ok=True, uses original draft
5. `test_run_deep_gap_eval_loops` — first gap eval says not sufficient → second fetch round runs
6. `test_run_deep_gap_eval_sufficient_stops_loop` — gap eval says sufficient → single round
7. `test_run_deep_deduplicates_sources` — duplicate URLs in sources → deduped
8. `test_parse_json_strips_markdown_fences` — test the `_parse_json` helper directly

For mocking OcClient:
```python
from unittest.mock import MagicMock, patch
from docent.bundled_plugins.research_to_notebook.pipeline import run_deep, _parse_json
from docent.bundled_plugins.research_to_notebook.oc_client import OcClient
```

---

## Invariants (do NOT violate)

1. `oc_client.py` must NOT import litellm anywhere.
2. `search.py` must NOT import from `docent.*` — it is a standalone module (no circular deps).
3. `pipeline.py` may only import from `.oc_client` and `.search` within the plugin — no other docent imports.
4. `_parse_json` must strip ```json...``` markdown fences before parsing.
5. The `on_progress` callback in `run_deep` is optional (None = no-op) — never call it without checking.
6. `web_search` and `paper_search` must return `[]` on any exception — never propagate.
7. `fetch_page` must return `""` on any exception — never propagate.
8. `deep()` in `__init__.py` must be a generator in ALL branches (feynman + docent).
9. No Rich markup in any string field of any result model.
10. Run `uv run pytest tests/test_research_search.py tests/test_research_pipeline.py -v` and iterate until all pass.
11. Run `uv run pytest --tb=no -q` and confirm the full suite stays green.

---

## Files to create/modify

Create:
- `src/docent/bundled_plugins/research_to_notebook/oc_client.py`
- `src/docent/bundled_plugins/research_to_notebook/search.py`
- `src/docent/bundled_plugins/research_to_notebook/pipeline.py`
- `tests/test_research_search.py`
- `tests/test_research_pipeline.py`

Modify:
- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — wire docent backend in `deep()`, make all action branches generators

Do NOT modify any other file.

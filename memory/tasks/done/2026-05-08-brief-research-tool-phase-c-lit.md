# Brief: Research Tool — Phase C (lit + review on Docent pipeline)

## Goal

Wire `backend="docent"` in the existing `lit()` and `review()` actions in
`src/docent/bundled_plugins/research_to_notebook/__init__.py`, and add
`run_lit` + `run_review` functions to `pipeline.py`.

**Do NOT touch** `deep()`, `oc_client.py`, `search.py`, or the agent prompts
already in `agents/`. Only modify `__init__.py` and `pipeline.py`, and add tests.

---

## What already exists (read these before writing anything)

- `src/docent/bundled_plugins/research_to_notebook/pipeline.py` — has `run_deep`, `_parse_json`, `_load_prompt`, `_progress`
- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — has `ResearchTool` with `deep()` as a generator; `lit()` and `review()` still have the Feynman-only generator bodies
- `src/docent/bundled_plugins/research_to_notebook/agents/` — already contains:
  - `lit_planner.md` — literature review search planner (8 paper queries, 2 web)
  - `lit_writer.md` — literature review writer (inter-paper comparison style)
  - `review_researcher.md` — evidence gatherer for peer review
  - `reviewer.md` — adversarial reviewer (already used by `run_deep`)
  - `verifier.md` — citation verifier (already used by `run_deep`)
  - `search_planner.md`, `gap_evaluator.md`, `writer.md` — used by `run_deep`

Read `pipeline.py` and `__init__.py` fully before writing. Follow their exact patterns.

---

## Changes to `pipeline.py`

Add two new public functions after `run_deep`.

### `run_lit(topic, oc, *, on_progress=None) -> dict`

Identical structure to `run_deep` with these differences:

1. **Stage 1** uses `_load_prompt("lit_planner")` instead of `search_planner`
2. **Stage 4** uses `_load_prompt("lit_writer")` instead of `writer`
3. Everything else (gap evaluator, verifier, reviewer, fetch logic, dedup) is identical to `run_deep`

Return value: same shape as `run_deep` — `{topic, draft, review, sources, rounds, ok, error}`.

**Do NOT copy-paste `run_deep` in full.** Extract the shared fetch+gap+verify+review logic into a private helper `_run_pipeline(topic, oc, planner_name, writer_name, *, on_progress)` that both `run_deep` and `run_lit` call. Then simplify both to one-liners:

```python
def run_deep(topic, oc, *, on_progress=None):
    return _run_pipeline(topic, oc, "search_planner", "writer", on_progress=on_progress)

def run_lit(topic, oc, *, on_progress=None):
    return _run_pipeline(topic, oc, "lit_planner", "lit_writer", on_progress=on_progress)
```

Move the full pipeline body into `_run_pipeline`. Update all existing tests to still pass (the public API is unchanged).

### `run_review(artifact, oc, *, on_progress=None) -> dict`

Different structure — no search planner, no web fetch loop:

```
Stage 1: Fetch artifact content
Stage 2: Researcher (review_researcher.md) — evidence gathering
Stage 3: Reviewer (reviewer.md) — adversarial review using researcher output
```

**Stage 1 — Fetch artifact:**

```python
def _fetch_artifact(artifact: str) -> str:
    """Return text content for an artifact (arXiv ID, URL, or local path)."""
    artifact = artifact.strip()
    # arXiv ID pattern: NNNN.NNNNN or NNNN.NNNNNvN
    import re
    if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", artifact):
        url = f"https://arxiv.org/abs/{artifact}"
        return fetch_page(url, max_chars=6000)
    if artifact.startswith("http://") or artifact.startswith("https://"):
        return fetch_page(artifact, max_chars=6000)
    # Local file path
    path = Path(artifact)
    if path.exists() and path.suffix == ".pdf":
        return f"(Local PDF: {artifact} — text extraction not yet supported; reviewer will work from metadata only)"
    return f"(Could not fetch artifact: {artifact!r})"
```

**Stage 2 — Researcher:**

```python
researcher_prompt = (
    _load_prompt("review_researcher")
    .replace("{artifact}", artifact)
    .replace("{artifact_content}", artifact_content)
)
researcher_notes = oc.call(researcher_prompt, model="glm-5.1", timeout=300)
```

**Stage 3 — Reviewer:**

Pass both the artifact content AND the researcher notes into the reviewer prompt:

```python
combined = f"## Artifact\n\n{artifact_content}\n\n## Researcher Notes\n\n{researcher_notes}"
reviewer_prompt = _load_prompt("reviewer").replace("{draft}", combined)
review = oc.call(reviewer_prompt, model="deepseek-v4-pro", timeout=300)
```

Return value:
```python
{
    "artifact": artifact,
    "artifact_content": artifact_content,
    "researcher_notes": researcher_notes,
    "review": review,
    "ok": True,
    "error": None,
}
```

Error handling: if fetch returns empty/error string, still proceed (researcher handles gracefully).
If researcher stage fails: `ok=False, error="Researcher failed: ..."`.
If reviewer stage fails: `ok=True, review="(Reviewer unavailable)"` (same pattern as `run_deep`).

---

## Changes to `__init__.py`

### Wire `backend="docent"` in `lit()`

Same generator pattern as `deep()`. Replace the current Feynman-only `lit()` body:

```python
@action(description="Literature review on a topic.", input_schema=LitInputs)
def lit(self, inputs: LitInputs, context: Context):
    if inputs.backend == "docent":
        from .oc_client import OcClient, OcUnavailableError
        from .pipeline import run_lit

        oc = OcClient()
        if not oc.is_available():
            yield ProgressEvent(phase="start", message="OpenCode server is not running. Start it with: opencode serve --port 4096")
            return ResearchResult(
                ok=False, backend="docent", workflow="lit",
                topic_or_artifact=inputs.topic, output_file=None, returncode=None,
                message="OpenCode server is not running. Start it with: opencode serve --port 4096",
            )

        output_dir = context.settings.research.output_dir.expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        slug = _slugify(inputs.topic) + "-lit"
        progress_events: list[tuple[str, str]] = []

        def _capture(phase, message): progress_events.append((phase, message))

        yield ProgressEvent(phase="start", message=f"Starting Docent literature review: {inputs.topic!r}")
        try:
            result_data = run_lit(inputs.topic, oc, on_progress=_capture)
        except Exception as e:
            return ResearchResult(ok=False, backend="docent", workflow="lit",
                topic_or_artifact=inputs.topic, output_file=None, returncode=None,
                message=f"Pipeline error: {e}")

        for phase, message in progress_events:
            yield ProgressEvent(phase=phase, message=message)

        if not result_data["ok"]:
            return ResearchResult(ok=False, backend="docent", workflow="lit",
                topic_or_artifact=inputs.topic, output_file=None, returncode=None,
                message=result_data.get("error") or "Pipeline failed.")

        out_file = output_dir / f"{slug}.md"
        review_file = output_dir / f"{slug}-review.md"
        out_file.write_text(result_data["draft"], encoding="utf-8")
        review_file.write_text(result_data["review"], encoding="utf-8")
        yield ProgressEvent(phase="done", message=f"Output written to {out_file}")

        return ResearchResult(
            ok=True, backend="docent", workflow="lit",
            topic_or_artifact=inputs.topic, output_file=str(out_file), returncode=0,
            message=f"Literature review complete. {result_data['rounds']} search round(s), {len(result_data['sources'])} sources.",
        )

    # Feynman branch (unchanged)
    yield ProgressEvent(phase="start", message=f"Starting Feynman literature review: {inputs.topic!r}")
    feynman_cmd = context.settings.research.feynman_command or ["feynman"]
    output_dir = context.settings.research.output_dir.expanduser()
    workspace_dir = output_dir / "workspace"
    slug = _slugify(inputs.topic) + "-lit"
    cmd = [*feynman_cmd, "lit", inputs.topic]
    returncode, output_file = _run_feynman(cmd, workspace_dir, output_dir, slug)
    if returncode != 0:
        return ResearchResult(ok=False, backend="feynman", workflow="lit",
            topic_or_artifact=inputs.topic, output_file=output_file, returncode=returncode,
            message=f"Feynman literature review exited with code {returncode}.")
    if output_file is None:
        return ResearchResult(ok=True, backend="feynman", workflow="lit",
            topic_or_artifact=inputs.topic, output_file=None, returncode=returncode,
            message=f"Literature review completed for {inputs.topic!r}, but no output file was found.")
    return ResearchResult(ok=True, backend="feynman", workflow="lit",
        topic_or_artifact=inputs.topic, output_file=output_file, returncode=returncode,
        message=f"Literature review completed for {inputs.topic!r}.")
```

### Wire `backend="docent"` in `review()`

```python
@action(description="Peer review of an artifact (arXiv ID, PDF path, or URL).", input_schema=ReviewInputs)
def review(self, inputs: ReviewInputs, context: Context):
    if inputs.backend == "docent":
        from .oc_client import OcClient
        from .pipeline import run_review

        oc = OcClient()
        if not oc.is_available():
            yield ProgressEvent(phase="start", message="OpenCode server is not running. Start it with: opencode serve --port 4096")
            return ResearchResult(
                ok=False, backend="docent", workflow="review",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                message="OpenCode server is not running. Start it with: opencode serve --port 4096",
            )

        output_dir = context.settings.research.output_dir.expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        slug = _slugify(_artifact_slug(inputs.artifact)) + "-review"
        progress_events: list[tuple[str, str]] = []

        def _capture(phase, message): progress_events.append((phase, message))

        yield ProgressEvent(phase="start", message=f"Starting Docent peer review: {inputs.artifact!r}")
        try:
            result_data = run_review(inputs.artifact, oc, on_progress=_capture)
        except Exception as e:
            return ResearchResult(ok=False, backend="docent", workflow="review",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                message=f"Pipeline error: {e}")

        for phase, message in progress_events:
            yield ProgressEvent(phase=phase, message=message)

        if not result_data["ok"]:
            return ResearchResult(ok=False, backend="docent", workflow="review",
                topic_or_artifact=inputs.artifact, output_file=None, returncode=None,
                message=result_data.get("error") or "Review failed.")

        out_file = output_dir / f"{slug}.md"
        out_file.write_text(result_data["review"], encoding="utf-8")
        yield ProgressEvent(phase="done", message=f"Review written to {out_file}")

        return ResearchResult(
            ok=True, backend="docent", workflow="review",
            topic_or_artifact=inputs.artifact, output_file=str(out_file), returncode=0,
            message=f"Peer review complete for {inputs.artifact!r}.",
        )

    # Feynman branch (unchanged)
    yield ProgressEvent(phase="start", message=f"Starting Feynman review: {inputs.artifact!r}")
    feynman_cmd = context.settings.research.feynman_command or ["feynman"]
    output_dir = context.settings.research.output_dir.expanduser()
    workspace_dir = output_dir / "workspace"
    slug = _slugify(_artifact_slug(inputs.artifact)) + "-review"
    cmd = [*feynman_cmd, "review", inputs.artifact]
    returncode, output_file = _run_feynman(cmd, workspace_dir, output_dir, slug)
    if returncode != 0:
        return ResearchResult(ok=False, backend="feynman", workflow="review",
            topic_or_artifact=inputs.artifact, output_file=output_file, returncode=returncode,
            message=f"Feynman review exited with code {returncode}.")
    if output_file is None:
        return ResearchResult(ok=True, backend="feynman", workflow="review",
            topic_or_artifact=inputs.artifact, output_file=None, returncode=returncode,
            message=f"Review completed for {inputs.artifact!r}, but no output file was found.")
    return ResearchResult(ok=True, backend="feynman", workflow="review",
        topic_or_artifact=inputs.artifact, output_file=output_file, returncode=returncode,
        message=f"Review completed for {inputs.artifact!r}.")
```

---

## Tests to add

### In `tests/test_research_pipeline.py` — add a new `TestRunLit` class and `TestRunReview` class

**`TestRunLit`** (4 tests):
1. `test_run_lit_happy_path` — mock oc + search → ok=True, draft non-empty (same pattern as TestRunDeep.test_run_deep_happy_path but calls `run_lit`)
2. `test_run_lit_planner_failure` — oc.call raises on first call → ok=False, "Search planner failed"
3. `test_run_lit_uses_lit_prompts` — verify `oc.call` is invoked with a prompt containing text from `lit_planner.md` (check the first call's args contain the topic)
4. `test_run_lit_writer_failure` — writer stage raises → ok=False, "Writer failed"

**`TestRunReview`** (5 tests):
1. `test_run_review_arxiv_id_fetches_url` — mock fetch_page, verify it's called with `https://arxiv.org/abs/2401.12345`
2. `test_run_review_url_artifact` — mock fetch_page with a URL artifact, verify called correctly
3. `test_run_review_happy_path` — mock fetch_page + oc.call (researcher + reviewer) → ok=True, review non-empty
4. `test_run_review_researcher_failure` — oc.call raises on researcher → ok=False
5. `test_run_review_reviewer_failure_returns_ok` — reviewer raises → ok=True, review=="(Reviewer unavailable)"

### In `tests/test_research_tool.py` — add `TestLitDocent` and `TestReviewDocent` classes

**`TestLitDocent`** (2 tests — mirror TestDeepFeynman pattern but for docent backend):
1. `test_lit_docent_server_unavailable` — OcClient.is_available() returns False → result.ok=False, "not running" in message
2. `test_lit_docent_happy_path` — mock OcClient.is_available()=True + run_lit → ok=True, output_file set

**`TestReviewDocent`** (2 tests):
1. `test_review_docent_server_unavailable` — ok=False, "not running"
2. `test_review_docent_happy_path` — mock is_available + run_review → ok=True

---

## Invariants

1. `_fetch_artifact` must be a module-level function in `pipeline.py` (not nested).
2. `run_deep` and `run_lit` must both delegate to `_run_pipeline` — no copy-paste.
3. All existing `TestRunDeep` tests must still pass after the refactor.
4. `lit()` and `review()` in `__init__.py` must be generators in ALL branches.
5. No Rich markup in any string field.
6. Run `uv run pytest --tb=short -q` (or `python -m pytest`) and iterate until 100% green.
7. Report final test count.

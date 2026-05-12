# Brief: Research Tool — Phase D (NotebookLM integration)

## Goal

Complete the `research-to-notebook` workflow by:
1. Persisting sources JSON when the Docent pipeline completes for `deep` and `lit`
2. Adding a new `to-notebook` action that reads saved sources, builds a notebook-ready package, and opens NotebookLM in the browser

**Only modify:** `src/docent/bundled_plugins/research_to_notebook/__init__.py`
**Add tests to:** `tests/test_research_tool.py`

Do NOT touch `pipeline.py`, `search.py`, `oc_client.py`, agents, or any other file.

---

## Read these files first

- `src/docent/bundled_plugins/research_to_notebook/__init__.py` — full file
- `tests/test_research_tool.py` — for fixture patterns

---

## Change 1: Persist sources JSON in `deep()` and `lit()` Docent branches

In both `deep()` and `lit()`, after writing the draft and review files, also write a sources JSON file:

```python
# After:
out_file.write_text(result_data["draft"], encoding="utf-8")
review_file.write_text(result_data["review"], encoding="utf-8")

# Add:
import json as _json
sources_file = output_dir / f"{slug}-sources.json"
sources_file.write_text(
    _json.dumps(result_data.get("sources", []), indent=2, ensure_ascii=False),
    encoding="utf-8",
)
```

Do NOT use a bare `import json` at the top of the method — use a local import `import json as _json` inside the branch (or use the already-imported `json` if it's in scope — check first).

Actually, `json` IS already imported at the top of `__init__.py`? Check — if not, do a local import. Looking at the file: it imports `json` at the top (`import json`). So just use `json.dumps(...)` directly. No new import needed.

The sources file path pattern: `{output_dir}/{slug}-sources.json`
- For `deep()`: slug = `_slugify(inputs.topic) + "-deep"` → file = `output_dir / f"{slug}-sources.json"`
- For `lit()`: slug = `_slugify(inputs.topic) + "-lit"` → file = `output_dir / f"{slug}-sources.json"`

Also update the final `ResearchResult` to include the sources file path in the message, or just leave the message unchanged. Either is fine.

---

## Change 2: New models

### `ToNotebookInputs`

```python
class ToNotebookInputs(BaseModel):
    output_file: str | None = Field(
        None,
        description=(
            "Path to a research output .md file (e.g. 'storm-surge-ghana-deep.md'). "
            "If omitted, the most recent output in research.output_dir is used."
        ),
    )
    max_sources: int = Field(
        20,
        description="Maximum number of sources to include in the notebook package (default 20).",
    )
```

### `ToNotebookResult`

```python
class ToNotebookResult(BaseModel):
    ok: bool
    output_file: str | None          # the research .md file used
    sources_file: str | None         # the -sources.json file found
    package_dir: str | None          # the notebook package directory written
    sources_count: int               # number of sources included
    message: str

    def to_shapes(self) -> list[Shape]:
        if not self.ok:
            return [ErrorShape(reason=self.message)]
        shapes: list[Shape] = [MessageShape(text=self.message, level="success")]
        if self.package_dir:
            shapes.append(LinkShape(url=self.package_dir, label="Notebook package"))
        return shapes

    def __rich_console__(self, console, options):
        from docent.ui.renderers import render_shapes
        render_shapes(self.to_shapes(), console)
        yield from ()
```

---

## Change 3: New `to_notebook` action

```python
@action(
    description=(
        "Prepare research sources for NotebookLM and open the browser. "
        "Reads the sources collected by the Docent pipeline (deep or lit) "
        "and writes a notebook-ready package."
    ),
    input_schema=ToNotebookInputs,
    name="to-notebook",
)
def to_notebook(self, inputs: ToNotebookInputs, context: Context) -> ToNotebookResult:
    ...
```

### Implementation

**Step 1: Resolve the output file**

```python
output_dir = context.settings.research.output_dir.expanduser()

if inputs.output_file:
    out_path = Path(inputs.output_file)
    if not out_path.is_absolute():
        out_path = output_dir / inputs.output_file
else:
    # Find the most recently modified .md file in output_dir
    # excluding -review.md files
    candidates = [
        p for p in output_dir.glob("*.md")
        if not p.name.endswith("-review.md")
    ] if output_dir.is_dir() else []
    if not candidates:
        return ToNotebookResult(
            ok=False, output_file=None, sources_file=None,
            package_dir=None, sources_count=0,
            message=(
                f"No research output found in {output_dir}. "
                "Run `docent research deep` or `docent research lit` first."
            ),
        )
    out_path = max(candidates, key=lambda p: p.stat().st_mtime)
```

**Step 2: Find the corresponding sources JSON**

The sources JSON is always next to the output file with `-sources.json` replacing `.md`:

```python
stem = out_path.stem  # e.g. "storm-surge-ghana-deep"
sources_path = out_path.parent / f"{stem}-sources.json"

if not sources_path.exists():
    return ToNotebookResult(
        ok=False, output_file=str(out_path), sources_file=None,
        package_dir=None, sources_count=0,
        message=(
            f"No sources file found at {sources_path}. "
            "Sources are only saved when using backend='docent'. "
            "The Feynman backend does not expose individual sources."
        ),
    )

import json
sources: list[dict] = json.loads(sources_path.read_text(encoding="utf-8"))
```

**Step 3: Filter and rank sources**

```python
def _rank_sources(sources: list[dict], max_sources: int) -> list[dict]:
    """Rank sources: papers first (have abstracts), then web with full_text, then rest."""
    papers = [s for s in sources if s.get("source_type") == "paper" and s.get("url")]
    web_with_text = [
        s for s in sources
        if s.get("source_type") == "web" and s.get("url") and s.get("full_text")
    ]
    web_snippet_only = [
        s for s in sources
        if s.get("source_type") == "web" and s.get("url") and not s.get("full_text")
    ]
    ranked = papers + web_with_text + web_snippet_only
    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[dict] = []
    for s in ranked:
        url = s.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(s)
    return unique[:max_sources]
```

**Step 4: Write notebook package**

```python
package_dir = out_path.parent / f"{stem}-notebook"
package_dir.mkdir(parents=True, exist_ok=True)

selected = _rank_sources(sources, inputs.max_sources)

# sources_urls.txt — one URL per line for pasting into NotebookLM
urls_file = package_dir / "sources_urls.txt"
urls_file.write_text(
    "\n".join(s["url"] for s in selected if s.get("url")),
    encoding="utf-8",
)

# Copy the research draft
import shutil
shutil.copy2(out_path, package_dir / out_path.name)

# guide.md — step-by-step instructions
guide_lines = [
    "# NotebookLM Setup Guide",
    "",
    f"Research: {out_path.name}",
    f"Sources: {len(selected)} selected",
    "",
    "## Steps",
    "",
    "1. Open https://notebooklm.google.com and create a new notebook",
    f"2. Add the research draft as a source: drag `{out_path.name}` into the Sources panel",
    "3. Add each URL below as a 'Website' source (copy/paste one at a time):",
    "",
]
for i, s in enumerate(selected, 1):
    title = s.get("title", "Untitled")[:80]
    url = s.get("url", "")
    stype = s.get("source_type", "web")
    guide_lines.append(f"   [{i}] [{stype}] {title}")
    guide_lines.append(f"       {url}")
    guide_lines.append("")

guide_lines += [
    "## Tips",
    "",
    "- Add the draft first so NotebookLM can cross-reference it with sources",
    "- Use the 'Notebook guide' feature to get an overview after adding all sources",
    "- Generate a podcast or study guide once sources are loaded",
]
(package_dir / "guide.md").write_text("\n".join(guide_lines), encoding="utf-8")
```

**Step 5: Open browser**

```python
import webbrowser
webbrowser.open("https://notebooklm.google.com")
```

**Step 6: Return result**

```python
return ToNotebookResult(
    ok=True,
    output_file=str(out_path),
    sources_file=str(sources_path),
    package_dir=str(package_dir),
    sources_count=len(selected),
    message=(
        f"Notebook package ready: {len(selected)} sources. "
        f"NotebookLM opened in browser. "
        f"Follow the guide in {package_dir / 'guide.md'}."
    ),
)
```

Put `_rank_sources` as a module-level function (not inside the method).

---

## Tests to add in `tests/test_research_tool.py`

Add a new `TestToNotebook` class with 7 tests:

### Setup: sources fixture

```python
SAMPLE_SOURCES = [
    {"title": "Paper A", "url": "https://arxiv.org/abs/2401.00001", "source_type": "paper", "snippet": "Abstract A"},
    {"title": "Web B", "url": "https://example.com/b", "source_type": "web", "full_text": "Full text B", "snippet": "Snippet B"},
    {"title": "Web C", "url": "https://example.com/c", "source_type": "web", "snippet": "Snippet C"},
    {"title": "Paper D", "url": "https://arxiv.org/abs/2401.00002", "source_type": "paper", "snippet": "Abstract D"},
]
```

### Tests

1. **`test_to_notebook_no_output_dir`** — output_dir doesn't exist → ok=False, message says "No research output found"

2. **`test_to_notebook_no_md_files`** — output_dir exists but no .md files → ok=False

3. **`test_to_notebook_no_sources_json`** — .md file exists but no -sources.json → ok=False, message says "No sources file found"

4. **`test_to_notebook_happy_path`** — mock `webbrowser.open`, provide .md + sources.json → ok=True, package_dir created, sources_urls.txt written, guide.md written, webbrowser.open called with NotebookLM URL

5. **`test_to_notebook_uses_specified_output_file`** — pass explicit output_file path → uses that file, not auto-detected

6. **`test_to_notebook_ranks_papers_first`** — mixed sources → papers appear before web sources in sources_urls.txt

7. **`test_to_notebook_respects_max_sources`** — 10 sources but max_sources=3 → only 3 in package

### Test fixture pattern (follow existing `_mock_context`):

```python
import json
import webbrowser
from unittest.mock import patch

class TestToNotebook:
    def _write_research_files(self, output_dir: Path, slug: str = "test-deep") -> tuple[Path, Path]:
        """Helper: write .md + -sources.json in output_dir."""
        output_dir.mkdir(parents=True, exist_ok=True)
        md_file = output_dir / f"{slug}.md"
        sources_file = output_dir / f"{slug}-sources.json"
        md_file.write_text("# Research Draft\n\nContent here.", encoding="utf-8")
        sources_file.write_text(json.dumps(SAMPLE_SOURCES), encoding="utf-8")
        return md_file, sources_file

    def test_to_notebook_no_output_dir(self, tmp_path):
        tool = ResearchTool()
        ctx = _mock_context(output_dir=tmp_path / "nonexistent")
        result = tool.to_notebook(ToNotebookInputs(), ctx)
        assert result.ok is False
        assert "No research output found" in result.message

    def test_to_notebook_no_md_files(self, tmp_path):
        output_dir = tmp_path / "research"
        output_dir.mkdir()
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        result = tool.to_notebook(ToNotebookInputs(), ctx)
        assert result.ok is False
        assert "No research output found" in result.message

    def test_to_notebook_no_sources_json(self, tmp_path):
        output_dir = tmp_path / "research"
        output_dir.mkdir()
        (output_dir / "test-deep.md").write_text("# Draft", encoding="utf-8")
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        result = tool.to_notebook(ToNotebookInputs(), ctx)
        assert result.ok is False
        assert "No sources file" in result.message

    def test_to_notebook_happy_path(self, tmp_path):
        output_dir = tmp_path / "research"
        md_file, _ = self._write_research_files(output_dir)
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch("webbrowser.open") as mock_browser:
            result = tool.to_notebook(ToNotebookInputs(), ctx)
        assert result.ok is True
        assert result.sources_count == len(SAMPLE_SOURCES)
        assert result.package_dir is not None
        pkg = Path(result.package_dir)
        assert (pkg / "sources_urls.txt").exists()
        assert (pkg / "guide.md").exists()
        assert (pkg / md_file.name).exists()
        mock_browser.assert_called_once_with("https://notebooklm.google.com")

    def test_to_notebook_uses_specified_output_file(self, tmp_path):
        output_dir = tmp_path / "research"
        md_file, _ = self._write_research_files(output_dir, slug="climate-lit")
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch("webbrowser.open"):
            result = tool.to_notebook(ToNotebookInputs(output_file=str(md_file)), ctx)
        assert result.ok is True
        assert "climate-lit" in result.output_file

    def test_to_notebook_ranks_papers_first(self, tmp_path):
        output_dir = tmp_path / "research"
        self._write_research_files(output_dir)
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch("webbrowser.open"):
            result = tool.to_notebook(ToNotebookInputs(), ctx)
        urls_content = (Path(result.package_dir) / "sources_urls.txt").read_text()
        lines = [l for l in urls_content.strip().splitlines() if l]
        # First two URLs should be the paper URLs (arxiv)
        assert "arxiv.org" in lines[0]

    def test_to_notebook_respects_max_sources(self, tmp_path):
        output_dir = tmp_path / "research"
        self._write_research_files(output_dir)
        tool = ResearchTool()
        ctx = _mock_context(output_dir=output_dir)
        with patch("webbrowser.open"):
            result = tool.to_notebook(ToNotebookInputs(max_sources=2), ctx)
        assert result.sources_count == 2
        urls_content = (Path(result.package_dir) / "sources_urls.txt").read_text()
        assert len(urls_content.strip().splitlines()) == 2
```

---

## Import additions needed

At the top of `__init__.py`, check if these are already imported:
- `import json` — check if present; if not, add it
- `import shutil` — check if present; add if not
- `import webbrowser` — add inside the `to_notebook` method (local import to avoid polluting module namespace)
- `from pathlib import Path` — already imported via `from pathlib import Path` check

The `ToNotebookInputs` and `ToNotebookResult` also need `Shape` shapes — `ErrorShape`, `MessageShape`, `LinkShape` are already imported at the top of `__init__.py`. Verify before adding duplicates.

---

## Invariants

1. `webbrowser` must be imported locally inside `to_notebook` (not at module top-level — it has side effects on some platforms).
2. `_rank_sources` must be a module-level function (not nested).
3. No Rich markup in any string field.
4. `to_notebook` is NOT a generator — it returns `ToNotebookResult` directly (no `yield`).
5. Exclude `-review.md` files when auto-detecting the most recent output file.
6. The sources_urls.txt must contain only valid URLs (non-empty `url` field).
7. Run `python -m pytest tests/test_research_tool.py --tb=short -q` and iterate until all pass.
8. Run `python -m pytest --tb=no -q` to confirm full suite stays green. Report final count.

---

## Also add `ToNotebookInputs` and `ToNotebookResult` to the test imports

In `tests/test_research_tool.py`, add to the existing import block:
```python
from docent.bundled_plugins.research_to_notebook import (
    ...
    ToNotebookInputs,
    ToNotebookResult,
    ...
)
```

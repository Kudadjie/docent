# Brief: Research Tool — Phase A (Feynman backend)

## Goal

Create `src/docent/bundled_plugins/research_to_notebook/__init__.py` — a new Docent bundled plugin that runs research workflows by delegating to the Feynman CLI. Also write tests in `tests/test_research_tool.py`.

This is Phase A: Feynman CLI backend only. No Docent pipeline yet.

---

## Pattern to follow

`src/docent/bundled_plugins/reading/__init__.py` — follow this file exactly for:
- Import paths from `docent.*`
- `@register_tool` class decorated with `Tool` base class
- `@action(description=..., input_schema=..., name=...)` decorator
- `BaseModel` subclasses for Inputs and Results
- `to_shapes()` + `__rich_console__` on every Result
- `RunLog` for logging events
- `write_setting` for config mutations

**Read that file before implementing.**

---

## Settings (already added to `src/docent/config/settings.py`)

```python
class ResearchSettings(BaseModel):
    output_dir: Path = Field(default_factory=lambda: Path("~/Documents/Docent/research"))
    feynman_command: list[str] | None = None  # defaults to ["feynman"] if None
```

Access via `context.settings.research`. Exported from `docent.config` (same as `ReadingSettings`).

---

## Plugin file to create

`src/docent/bundled_plugins/research_to_notebook/__init__.py`

Also create the `__init__.py` for the package (it can be empty or just have a docstring).

Wait — the file IS the `__init__.py`. Create the directory and put all code in `__init__.py`.

---

## Tool class

```python
@register_tool
class ResearchTool(Tool):
    name = "research"
    description = "Run research workflows (deep research, literature review, peer review) via Feynman."
    category = "research"
```

No `__init__` needed (no store to initialize, unlike reading).

---

## Actions

### 1. `deep` — Deep research on a topic

```
docent research deep "storm surge Ghana"
```

**Inputs:**
```python
class DeepInputs(BaseModel):
    topic: str = Field(..., description="Research topic or question.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default). 'docent' is planned.")
```

**Behaviour:**
- If `backend == "docent"`: return `ResearchResult(ok=False, ..., message="Docent pipeline backend is not yet available. Use backend='feynman'.")`
- If `backend == "feynman"`:
  1. Resolve feynman command: `context.settings.research.feynman_command or ["feynman"]`
  2. Resolve workspace dir: `context.settings.research.output_dir.expanduser() / "workspace"` — create it if it doesn't exist
  3. Snapshot existing `.md` files in `workspace/outputs/` (if dir exists)
  4. Run `[*feynman_cmd, "deepresearch", inputs.topic]` via `subprocess.run(cmd, cwd=workspace_dir, check=False)` — let feynman inherit terminal (no capture_output)
  5. After completion, scan `workspace/outputs/` for new `.md` files (diff vs snapshot)
  6. Copy newest new `.md` file to `output_dir / f"{slug}.md"` (slug = slugify topic)
  7. Return `ResearchResult`

**IMPORTANT subprocess call:** Use `subprocess.run(cmd, cwd=workspace_dir)` — do NOT set `capture_output=True` or `stdout=subprocess.PIPE`. Feynman must inherit the terminal so its output goes directly to the user. This is intentional: feynman is a long-running interactive process.

### 2. `lit` — Literature review

Same as `deep` but uses `feynman_cmd = [*feynman_cmd, "lit", inputs.topic]` and slug suffix is `-lit`.

**Inputs:** `LitInputs(topic: str, backend: str = "feynman")` — same shape as DeepInputs.

### 3. `review` — Peer review of an artifact

```
docent research review "2401.12345"          # arXiv ID
docent research review "/path/to/paper.pdf"  # local PDF
docent research review "https://..."         # URL
```

**Inputs:**
```python
class ReviewInputs(BaseModel):
    artifact: str = Field(..., description="arXiv ID, local PDF path, or URL to review.")
    backend: str = Field("feynman", description="Research backend: 'feynman' (default).")
```

Feynman command: `[*feynman_cmd, "review", inputs.artifact]`. Slug derived from artifact string (strip URL parts, use last path component). Suffix `-review`.

### 4. `config-show` — Show research settings

```python
class ConfigShowInputs(BaseModel):
    pass

class ConfigShowResult(BaseModel):
    config_path: str
    output_dir: str
    feynman_command: list[str]
    # to_shapes() returns MetricShapes for each field
```

### 5. `config-set` — Set a research setting

```python
_KNOWN_RESEARCH_KEYS = {"output_dir"}  # feynman_command is list-typed, not settable via config-set

class ConfigSetInputs(BaseModel):
    key: str = Field(..., description="Setting key under [research]: 'output_dir'.")
    value: str = Field(..., description="New value.")
```

Uses `write_setting(f"research.{inputs.key}", inputs.value)` — same as reading plugin.

---

## Result types

### `ResearchResult`

```python
class ResearchResult(BaseModel):
    ok: bool
    backend: str           # "feynman" or "docent"
    workflow: str          # "deep", "lit", "review"
    topic_or_artifact: str
    output_file: str | None  # absolute path to copied output file, or None if not found
    returncode: int | None   # feynman process exit code, or None if not run
    message: str

    def to_shapes(self) -> list[Shape]: ...
    def __rich_console__(self, console, options): ...
```

`to_shapes()`:
- If `not ok`: `[ErrorShape(reason=self.message)]`
- If `ok`: `[MessageShape(text=self.message, level="success"), LinkShape(url=self.output_file, label="Output file")]` (if output_file is not None)

Use `ErrorShape`, `MessageShape`, `LinkShape`, `MarkdownShape` from `docent.core.shapes`. Check what's available — use what's there.

---

## Slug helper

```python
import re

def _slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric with hyphens, collapse runs."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    return s.strip("-")[:60]
```

---

## Workspace and output-file scan

```python
def _run_feynman(
    cmd: list[str],
    workspace_dir: Path,
    output_dir: Path,
    slug: str,
) -> tuple[int, str | None]:
    """Run feynman and return (returncode, output_file_path | None)."""
    workspace_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir = workspace_dir / "outputs"

    # Snapshot before
    before: set[Path] = set(outputs_dir.glob("*.md")) if outputs_dir.is_dir() else set()

    result = subprocess.run(cmd, cwd=workspace_dir)  # inherits terminal

    # Find new output files
    after: set[Path] = set(outputs_dir.glob("*.md")) if outputs_dir.is_dir() else set()
    new_files = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)

    if not new_files:
        return result.returncode, None

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / f"{slug}.md"
    import shutil
    shutil.copy2(new_files[0], dest)
    return result.returncode, str(dest)
```

---

## Tests: `tests/test_research_tool.py`

Write at least 8 tests. Use `pytest` and `unittest.mock.patch` to mock `subprocess.run`. Do NOT call feynman for real.

Test cases to cover:
1. `test_deep_feynman_happy_path` — mock subprocess.run (returncode=0), mock outputs dir with one new .md file → ResearchResult ok=True, output_file set
2. `test_deep_feynman_no_output_file` — subprocess.run succeeds but no new .md files → ok=True, output_file=None, message warns
3. `test_deep_feynman_nonzero_exit` — subprocess.run returns returncode=1 → ok=False
4. `test_lit_feynman_happy_path` — same as deep but workflow="lit"
5. `test_review_feynman_happy_path` — workflow="review", artifact="2401.12345"
6. `test_deep_docent_backend_not_implemented` — backend="docent" → ok=False, message contains "not yet available"
7. `test_config_show` — returns ConfigShowResult with correct fields
8. `test_config_set_unknown_key` — key="bad_key" → ConfigSetResult ok=False

**Fixture approach:** instantiate `ResearchTool()` directly. Pass a mock `Context` with `context.settings.research.output_dir` and `context.settings.research.feynman_command`. Use `unittest.mock.MagicMock` for Context.

**Import paths in tests:**
```python
from docent.bundled_plugins.research_to_notebook import ResearchTool, DeepInputs, LitInputs, ReviewInputs
```

---

## Invariants (do NOT violate these)

1. `subprocess.run` for feynman must NOT use `capture_output=True` — feynman inherits the terminal.
2. No Rich markup (`[bold]`, `[red]` etc.) in any `message` or `str` fields — only in `__rich_console__`.
3. `to_shapes()` returns `list[Shape]` — all shapes from `docent.core.shapes`.
4. `_slugify` must strip hyphens from start/end and truncate to 60 chars.
5. `config-set` only allows `output_dir` (not `feynman_command` — it's list-typed).
6. The tool must NOT import from `docent.ui` at module level (lazy-import only, same pattern as reading plugin's `__rich_console__`).

---

## Files to create

1. `src/docent/bundled_plugins/research_to_notebook/__init__.py` — full implementation
2. `tests/test_research_tool.py` — 8+ tests

Run `uv run pytest tests/test_research_tool.py -v` and iterate until all pass.

Do NOT modify `settings.py` or `config/__init__.py` — those are already updated by the main session.
Do NOT modify `cli.py` or any other existing file.

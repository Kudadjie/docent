# Brief: Consolidate _form_to_studio_args and _build_studio_cmd

## Problem
`src/docent/ui_server.py` has two functions that both convert a `StudioRunBody` into action-specific data. They mirror each other action-by-action, and when a new studio action is added, BOTH must be updated. The review calls them "drift magnets."

- `_form_to_studio_args(action_id, body)` → `dict` (kwargs for in-process `run_action`)
- `_build_studio_cmd(body)` → `list[str]` (subprocess argv for `docent studio <action> ...`)

## Solution: Extract a shared parser

Add a dataclass/NamedTuple `_StudioSpec` that captures the parsed, normalized form:
```python
from typing import NamedTuple

class _StudioSpec(NamedTuple):
    action: str       # e.g. "deep-research"
    args: dict        # ready for run_action('studio', action, args)
```

Implement `_parse_studio_body(body: StudioRunBody) -> _StudioSpec | None` that does all action-dispatch logic once.

Then rewrite:
- `_form_to_studio_args(action_id, body)` to call `_parse_studio_body(body)` and return `spec.args` (keep the function signature for backward compatibility with callers)
- `_build_studio_cmd(body)` to call `_parse_studio_body(body)` and convert `spec.args` to CLI argv

## How to convert spec.args → CLI argv
The CLI arg names mostly match the Python field names with underscores→hyphens. Implement a helper:
```python
def _args_to_cli(action: str, args: dict) -> list[str]:
    """Convert run_action args dict to CLI argv for docent studio <action>."""
    # Map dict keys to --flag names; handle list fields with repeated flags.
    ...
```

Key mappings (from studying _build_studio_cmd at lines 1044-1086 of ui_server.py):
- `topic` → `["--topic", value]`
- `backend` → `["--backend", value]`
- `output` → `["--output", value]`
- `confirmed: True` → `["--confirmed"]` (bool flag, no value)
- `guide_files: list` → repeated `["--guide-files", g]` for each g
- `artifact` → `["--artifact", value]`
- `artifact_a` → `["--artifact-a", value]`
- `artifact_b` → `["--artifact-b", value]`
- `query` → `["--query", value]`
- `max_results` → `["--max-results", str(value)]`
- `arxiv_id` → `["--arxiv-id", value]`
- `sources_file` → `["--sources-file", value]` (only if non-empty)
- `output_file` → `["--output-file", value]` (only if non-empty)
- `max_sources` → `["--max-sources", str(value)]`
- `run_nlm_research: False` → `["--no-run-nlm-research"]` (bool flags: False = add --no-flag)
- `run_quality_gate: False` → `["--no-run-quality-gate"]`
- `run_perspectives: False` → `["--no-run-perspectives"]`
- `key` → `["--key", value]`
- `value` → `["--value", value]`

## Verification
Run: `uv run pytest -x -q`
All 501+ tests must pass. The function signatures of `_form_to_studio_args` and `_build_studio_cmd` must remain the same (they are called by the streaming endpoints).

## Files to touch
ONLY `src/docent/ui_server.py` — this is a pure refactor of two functions in that file.
Do NOT add new modules, do NOT change any tests.

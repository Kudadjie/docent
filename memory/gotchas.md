---
name: Docent gotchas
description: Landmines we've stepped on; consult when debugging weird behavior or before writing something that smells similar
type: project
---

Short actionable notes on non-obvious failures. Newest at the bottom. When a gotcha becomes obsolete (e.g., fixed upstream), delete the entry — don't let this file rot.

## Rich markup eats bracketed words as style tags

`console.print("[required]")` renders nothing — Rich interprets `[required]` as an unknown style and silently swallows it. Same for `[default=...]`, `[optional]`, etc.

- Use parentheses: `"(required)"` / `"(default=1)"`.
- Or escape: `from rich.markup import escape; escape("[required]")`.

## pydantic-settings `env_prefix` scopes env var reads

Settings class has `env_prefix="DOCENT_"`, so `anthropic_api_key` reads from `DOCENT_ANTHROPIC_API_KEY`, **not** `ANTHROPIC_API_KEY`. The LLMClient bridges this: reads `settings.anthropic_api_key` (scoped), pushes into `os.environ["ANTHROPIC_API_KEY"]` (unscoped) for litellm to find. Don't assume the field name matches the standard env var.

## litellm import is ~1s

Never `import litellm` at module top. Put it inside `LLMClient.complete()`. Meta commands must stay fast.

Invariant test:
```python
import sys, docent.cli
assert "litellm" not in sys.modules
```

If this assertion ever fires, someone hoisted the import — revert.

## `discover_tools()` skips `_`-prefixed modules

`src/docent/tools/_anything.py` is invisible to autodiscovery. Reserved for scratch and test fixtures. If a real tool file isn't showing up in `docent list`, check the filename doesn't start with `_`.

## Windows legacy console (cp1252) can't render unicode symbols

`▸`, `→`, `…`, `📚`, emoji — all crash with `UnicodeEncodeError` when Rich tries to write to the Windows legacy console. Rich does not catch this.

- Stick to ASCII in anything the CLI might print: help text, info panels, list output, error messages.
- If a specific glyph is essential, gate it on `sys.stdout.encoding.lower() in ("utf-8", "utf8")` or use an ASCII fallback.

## Pydantic v2 API for introspecting fields

When generating CLI options from a schema:
- Fields dict: `schema.model_fields` (v2), NOT `__fields__` (v1).
- Required check: `finfo.is_required()` (v2 method), NOT comparing `default` to a sentinel.
- Field annotation: `finfo.annotation` (v2), NOT `finfo.outer_type_`.

Mixing v1/v2 patterns silently produces wrong CLI signatures.

## Executor `env=` replaces the environment, it doesn't merge

Matches `subprocess.run`. `env={"FOO": "bar"}` gives the child **only** `FOO=bar`. To add to parent env: `env={**os.environ, "FOO": "bar"}`.

## `Tool.run` is no longer `@abstractmethod` (post Step 7a)

It has a default implementation that raises `NotImplementedError`. Don't rely on `ABC.__abstractmethods__` to catch misconfigured tools — the registry catches that with a clearer error (`"Tool X must define run() or at least one @action method"`). If you see a tool mysteriously "not failing" when you expected it to, check registry validation, not ABC.

## Git Bash `/tmp/...` path ≠ Windows Python path

On Windows with Git Bash:
- `mktemp -d` gives something like `/tmp/tmp.abcXYZ`
- Git Bash `ls`, `rm` translate that to the real Windows temp dir transparently
- **Native Windows Python (what `uv run python` invokes) does NOT** — `Path('/tmp/tmp.abcXYZ')` is treated as `C:\tmp\tmp.abcXYZ`, a DIFFERENT location

Symptom: inside a bash script, `uv run docent <tool>` writes to some location and `ls` confirms files exist; then `uv run python -c "open('/tmp/...')"` fails with FileNotFoundError pointing at the same string.

Fix for smoke tests that span shell + Python:
- Resolve paths inside Python using the same helpers the tool uses: `from docent.utils.paths import data_dir; p = data_dir() / 'paper'`.
- Or convert to a Windows path first with `cygpath -w "$TMPHOME"` before passing to Windows-native tools.
- Cleanest: do all file verification inside one `uv run python` invocation that reads `os.environ["DOCENT_HOME"]` and constructs paths the Python-native way.

## `Prompt.ask` inside a generator action gets eaten by Rich `Live`

`_drive_progress` (cli.py) wraps generator iteration in `with Progress(...) as progress:`, which starts a Rich `Live` display redrawing ~12×/sec. Any `Prompt.ask` (and therefore `prompt_for_path`) called from inside the generator body renders for one frame, then gets overwritten by the next Live redraw. The user sees the prompt flash and disappear; pressing Enter submits the empty default with no chance to type a real value.

Caught in Step 10.5 real-data testing: the first-run database-dir prompt fired during a generator action, flashed and vanished, and `~/Documents/Papers` got picked silently.

Fix pattern: resolve interactive prompts in a non-generator setup phase, then return a generator for the streaming work. The CLI's dispatcher (`inspect.isgenerator(maybe)` at cli.py) supports actions returning either a plain value or a generator from the same method.

```python
def my_action(self, inputs, context):
    folder, early = self._resolve(inputs, context)  # may prompt — plain return
    if early is not None:
        return early
    return self._stream(folder, inputs, context)    # generator
```

Don't try to suspend/restart Live around the prompt from inside a domain helper — it leaks CLI rendering details into business logic and breaks if the helper is ever called from a non-CLI caller (MCP, tests).

## User-pasted paths need quote-stripping AND existence validation before persisting

Two related landmines around `prompt_for_path` + persist-to-config flows, both caught in Step 10.5 real-data testing:

1. **Pasted paths often arrive wrapped in quotes.** Windows users reflexively wrap paths with spaces in `"…"`. `Path(raw).expanduser()` does NOT strip them — you get a Path whose name literally contains `"` characters, `is_dir()` returns False, and the error message looks insane because the path *displayed* in it looks correct. Fix lives in `prompt_for_path` (prompt.py): strip a matched pair of surrounding `"` or `'` after `.strip()`. Generic — benefits every caller.

2. **A first-run prompt that persists before validating corrupts config silently.** If the prompt resolves to a Path that doesn't exist, calling `write_setting` immediately means subsequent runs all fail the same way — and `config-show` lies, displaying the bad value as if everything's configured. Fix lives in the caller (e.g. `_require_database_dir`): validate `path.is_dir()` (or whatever invariant matters) BEFORE `write_setting`. On failure: print a clear remediation message and return None. Do not persist.

The original symptom: pasted `"C:\Users\…\Papers"` with surrounding quotes → `is_dir()` False → "Folder not found" → but `config-show` happily printed the quoted path as if accepted. One trigger, two latent flaws.

Apply this pattern whenever user input flows into a value that gets written to disk: **normalize first (strip quotes / whitespace), validate second (does it satisfy the invariant?), persist only if both pass.**

## `typer.Exit(1)` is `click.exceptions.Exit` (RuntimeError), NOT `SystemExit`

When a preflight function aborts with `typer.Exit(1)`, tests must catch `typer.Exit` (which is `click.exceptions.Exit → RuntimeError → Exception`), NOT `SystemExit`. `SystemExit` is a `BaseException`, not caught by `except Exception`.

```python
# WRONG:
with pytest.raises(SystemExit):    # typer.Exit is NOT a SystemExit!
    _preflight_docent(inputs, ctx)

# CORRECT:
import typer
with pytest.raises(typer.Exit):    # click.exceptions.Exit
    _preflight_docent(inputs, ctx)
```

## `web_search()` must never silently return `[]` on auth/rate-limit errors

`except Exception: return []` silently swallowed `InvalidAPIKeyError` and `UsageLimitExceededError`, producing 0 sources and garbage LLM output with no warning. **Always re-raise auth and rate-limit exceptions; log everything else.**

```python
# WRONG:
except Exception:
    return []   # silently hides every failure

# CORRECT:
from tavily.errors import InvalidAPIKeyError, UsageLimitExceededError
# (imported at module level with try/except ImportError fallback)

try:
    ...
except (InvalidAPIKeyError, UsageLimitExceededError):
    raise  # propagate auth/rate-limit failures
except Exception as exc:
    logger.warning("Tavily search for %r failed: %s", query, exc)
    return []
```

## Windows .venv vs WSL .venv-wsl — deps must be in BOTH

Docent runs from Windows Python (`.venv`), but tests run from WSL (`.venv-wsl`). Adding a dep to `pyproject.toml` requires syncing BOTH venvs:

```bash
# WSL (testing):
cd /mnt/c/Users/DELL/Desktop/Docent
.venv-wsl/bin/pip install -e ".[dev]"

# Windows (running docent):
cd C:\Users\DELL\Desktop\Docent
uv sync
```

**Symptom of wrong venv:** `ModuleNotFoundError: No module named 'X'` from `docent` CLI even though `uv run pytest` passes.

**If Windows `.venv` breaks** (no `pyvenv.cfg`, `uv sync` fails with access denied):
```powershell
Stop-Process -Name docent -Force -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .venv
uv venv --python 3.11
uv sync
```

## Refiner and verifier quality guards — LLMs can return diffs instead of full drafts

When an LLM is asked to "revise" or "verify" a draft, it sometimes returns inline correction notes or a diff instead of the complete revised document. The pipeline has two guards:

1. **Verifier guard** (`pipeline.py`): If `len(verified_draft) < 0.3 * len(draft)`, falls back to the original draft. Threshold 30% chosen because diff-style outputs are typically very short.

2. **Refiner guard** (`pipeline.py`): If `len(refined_draft) < 0.5 * len(original)`, keeps the verified/original draft. Higher threshold (50%) because the refiner should produce something close in length to the input.

If either guard triggers, a warning is logged. Do NOT remove these guards — they prevent garbage output silently replacing a good draft.

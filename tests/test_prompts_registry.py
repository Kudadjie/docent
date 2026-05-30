"""Prompts-as-first-class-code guards for the studio package.

Three things are enforced here:

1. The prompt registry (``prompts.PROMPT_NAMES``) and the ``agents/*.md`` files
   on disk are in exact correspondence — no orphan files, no dangling entries.
2. Every literal ``load_prompt("name")`` call site in the studio package points
   at a registered prompt (catches typos and renames).
3. No prompt file has been edited without the hash manifest being refreshed —
   the tripwire that forces a re-run of the eval suite before a prompt change
   lands. See ``regenerate_manifest`` below for how to update it.

To update the manifest after an *intentional* prompt change:

    uv run python tests/test_prompts_registry.py --update
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from docent.bundled_plugins.studio import prompts

_MANIFEST = Path(__file__).parent / "golden" / "studio" / "prompt_hashes.json"
_STUDIO_PKG = Path(prompts.__file__).parent


def _prompt_files() -> dict[str, Path]:
    """Return {stem: path} for every .md file in the agents/ directory."""
    return {p.stem: p for p in prompts.AGENTS_DIR.glob("*.md")}


def _hash(path: Path) -> str:
    """SHA-256 of a prompt file with newlines normalized to LF.

    Normalizing makes the hash identical on Windows and WSL regardless of
    git's autocrlf setting — this suite runs on both.
    """
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ─── 1. registry ↔ disk correspondence ─────────────────────────────────────────

def test_no_orphan_or_dangling_prompts() -> None:
    on_disk = set(_prompt_files())
    registered = set(prompts.PROMPT_NAMES)
    assert on_disk == registered, (
        f"agents/*.md and PROMPT_NAMES disagree.\n"
        f"  On disk but unregistered: {sorted(on_disk - registered)}\n"
        f"  Registered but missing file: {sorted(registered - on_disk)}"
    )


def test_every_registered_prompt_loads_non_empty() -> None:
    for name in prompts.PROMPT_NAMES:
        text = prompts.load_prompt(name)
        assert text.strip(), f"Prompt {name!r} is empty"


# ─── 2. literal call sites are registered ───────────────────────────────────────

_CALL_RE = re.compile(r"""\b_?load_prompt\(\s*["']([a-z_]+)["']""")


def test_literal_call_sites_are_registered() -> None:
    offenders: dict[str, list[str]] = {}
    for py in _STUDIO_PKG.rglob("*.py"):
        if py.name == "prompts.py":
            continue
        for name in _CALL_RE.findall(py.read_text(encoding="utf-8")):
            if name not in prompts.PROMPT_NAMES:
                offenders.setdefault(py.name, []).append(name)
    assert not offenders, f"load_prompt() call sites referencing unregistered prompts: {offenders}"


# ─── 3. change tripwire ─────────────────────────────────────────────────────────

def test_prompt_hashes_unchanged() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    current = {name: _hash(p) for name, p in _prompt_files().items()}
    changed = [n for n in current if manifest.get(n) != current[n]]
    new = [n for n in current if n not in manifest]
    removed = [n for n in manifest if n not in current]
    assert not (changed or new or removed), (
        "Prompt files changed without refreshing the hash manifest.\n"
        f"  changed: {sorted(changed)}\n  new: {sorted(new)}\n  removed: {sorted(removed)}\n"
        "If this was an intentional prompt edit, re-run the eval suite\n"
        "    uv run pytest tests/eval_studio.py -m eval\n"
        "then update the manifest:\n"
        "    uv run python tests/test_prompts_registry.py --update"
    )


# ─── manifest regeneration ──────────────────────────────────────────────────────

def regenerate_manifest() -> None:
    """Write the hash manifest from the current prompt files. Used by --update."""
    data = {name: _hash(p) for name, p in sorted(_prompt_files().items())}
    _MANIFEST.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(data)} prompt hashes to {_MANIFEST}")


if __name__ == "__main__":
    import sys

    if "--update" in sys.argv:
        regenerate_manifest()
    else:
        print("Pass --update to regenerate the prompt hash manifest.")

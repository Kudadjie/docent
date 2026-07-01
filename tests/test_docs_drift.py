"""Docs drift gate — every `docent <tool> <action>` command shown in the docs
must exist in the live registry.

Rationale: docs/cli.md and README.md have historically drifted from the CLI
surface (renamed actions, removed tools). This test parses every ``docent ...``
invocation out of inline code and code fences and asserts the tool and action
still exist. It is the same "presence, not prose" contract as
test_mcp_surface.py, pointed at the docs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

DOC_FILES = [
    REPO / "docs" / "cli.md",
    REPO / "README.md",
]

# Built-in Typer commands defined directly in cli.py (not registry tools).
BUILTIN_COMMANDS = {
    "list",
    "plugins",
    "info",
    "whatsnew",
    "update",
    "ui",
    "backup",
    "restore",
    "serve",
    "doctor",
    "setup",
    "version",
    "config",
}

# Tool names used purely as documentation examples (README "Adding a tool").
EXAMPLE_TOOLS = {"echo", "mytool", "myplugin"}

# `docent <tool> <maybe-action>` — tokens start with a letter; flags, quoted
# args, placeholders (<...>), and paths never match the token pattern.
_CMD_RE = re.compile(r"\bdocent\s+([a-z][a-z0-9_-]*)(?:\s+([a-z][a-z0-9-]*))?")


def _extract_commands(text: str) -> list[tuple[str, str | None]]:
    """Pull (tool, action|None) pairs from code fences and inline code spans."""
    chunks: list[str] = re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.DOTALL)
    chunks += re.findall(r"`([^`\n]*)`", text)
    found: list[tuple[str, str | None]] = []
    for chunk in chunks:
        for m in _CMD_RE.finditer(chunk):
            found.append((m.group(1), m.group(2)))
    return found


@pytest.fixture(scope="module")
def registry() -> dict:
    """Shipped tool surface, tolerant of import caching and fixture-tool leakage.

    Do NOT clear-and-rediscover: plugin modules already imported by earlier
    tests won't re-execute their ``@register_tool`` decorators, which would
    leave a cleared registry empty in full-suite runs. Instead, register on
    top (the loader warn-and-skips duplicates), keep only tools defined under
    the ``docent`` package (drops test-fixture tools other tests leak in),
    and restore the registry to its prior state afterwards.
    """
    import docent.core.registry as reg_mod
    from docent.core import load_plugins
    from docent.tools import discover_tools

    snapshot = dict(reg_mod._REGISTRY)
    try:
        discover_tools()
        load_plugins()
        full = dict(reg_mod._REGISTRY)
    finally:
        reg_mod._REGISTRY.clear()
        reg_mod._REGISTRY.update(snapshot)

    return {
        name: cls
        for name, cls in full.items()
        if (getattr(cls, "__module__", "") or "").startswith("docent.")
    }


@pytest.mark.parametrize("doc_path", DOC_FILES, ids=lambda p: p.name)
def test_documented_commands_exist(doc_path: Path, registry: dict) -> None:
    from docent.core.tool import collect_actions

    text = doc_path.read_text(encoding="utf-8")
    problems: list[str] = []

    for tool_name, action_name in _extract_commands(text):
        if tool_name in BUILTIN_COMMANDS or tool_name in EXAMPLE_TOOLS:
            continue
        if tool_name not in registry:
            problems.append(f"`docent {tool_name}` — no such tool or built-in command")
            continue
        if action_name is None:
            continue
        actions = collect_actions(registry[tool_name])
        if actions and action_name not in actions:
            problems.append(
                f"`docent {tool_name} {action_name}` — tool exists but has no "
                f"action '{action_name}' (available: {sorted(actions)})"
            )

    assert not problems, (
        f"{doc_path.name} references commands that don't exist "
        f"({len(problems)} problem(s)):\n  " + "\n  ".join(problems)
    )

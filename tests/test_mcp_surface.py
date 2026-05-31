"""Model-facing surface contract for the MCP adapter (Tier-4 C).

Every Docent action is exposed to a calling LLM over MCP as a name + description
+ input-field schema. To that model the descriptions ARE the documentation — a
bare field or an empty description means the model has to guess. The 2026-05-30
audit found the shipped surface already fully described; this test is the
regression gate that keeps it that way: a new action (or a new field) can't ship
without a real description.

What's enforced:
  * Every MCP tool has a non-empty, non-placeholder description.
  * Every input field has a non-empty, non-placeholder description.

What's deliberately NOT enforced: a subjective "quality" bar on wording. The
floor here is presence + not-a-placeholder, not prose review.
"""

from __future__ import annotations

import pytest

_PLACEHOLDERS = {"...", "todo", "tbd", "fixme", "xxx", "n/a"}
_MIN_DESC_LEN = 10


def _mcp_tools():
    """Build the MCP tool list for the *shipped* surface only.

    ``build_mcp_tools()`` reads the global tool registry. In a full-suite run
    other tests (``test_tool_abc.py``, ``test_dispatcher.py``) register
    throwaway fixture tools into that same registry, and those leak in here.
    To test exactly the surface Docent ships — and nothing a sibling test left
    behind — snapshot the registry, rebuild it from a clean discover+load, then
    restore it so this test neither sees nor causes pollution.
    """
    import docent.core.registry as registry
    from docent.core import load_plugins
    from docent.mcp_server import build_mcp_tools
    from docent.tools import discover_tools

    saved = dict(registry._REGISTRY)
    registry._REGISTRY.clear()
    try:
        discover_tools()
        load_plugins()
        return build_mcp_tools()
    finally:
        registry._REGISTRY.clear()
        registry._REGISTRY.update(saved)


def _is_placeholder(text: str) -> bool:
    return text.strip().lower() in _PLACEHOLDERS


@pytest.fixture(scope="module")
def mcp_tools():
    return _mcp_tools()


def test_every_tool_has_a_real_description(mcp_tools) -> None:
    bad = []
    for t in mcp_tools:
        desc = (t.description or "").strip()
        if len(desc) < _MIN_DESC_LEN or _is_placeholder(desc):
            bad.append((t.name, desc))
    assert not bad, f"MCP tools with empty/placeholder/too-short descriptions: {bad}"


def test_every_input_field_has_a_real_description(mcp_tools) -> None:
    bad: dict[str, list[str]] = {}
    for t in mcp_tools:
        props = (t.inputSchema or {}).get("properties", {})
        for field, spec in props.items():
            desc = (spec.get("description") or "").strip()
            if not desc or _is_placeholder(desc):
                bad.setdefault(t.name, []).append(field)
    assert not bad, f"MCP tool fields missing a real description: {bad}"

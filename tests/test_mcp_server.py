"""Tests for Step 13 — MCP server adapter (src/docent/mcp_server.py)."""
from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

# Importing from `reading` triggers @register_tool, populating the registry.
from reading import ReadingQueue  # noqa: F401

from docent.core.context import Context
from docent.core.registry import register_tool
from docent.core.tool import Tool
from docent.mcp_server import (
    build_mcp_tools,
    invoke_action,
    mcp_tool_name,
    parse_mcp_tool_name,
)


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

def test_mcp_tool_name_simple():
    assert mcp_tool_name("reading", "next") == "reading__next"


def test_mcp_tool_name_hyphenated_action():
    assert mcp_tool_name("reading", "sync-from-mendeley") == "reading__sync_from_mendeley"


def test_parse_mcp_tool_name_round_trip():
    original = "reading__sync_from_mendeley"
    result = parse_mcp_tool_name(original)
    assert result == ("reading", "sync-from-mendeley")


def test_parse_mcp_tool_name_no_separator():
    assert parse_mcp_tool_name("reading") is None


# ---------------------------------------------------------------------------
# Registry introspection
# ---------------------------------------------------------------------------

def test_build_mcp_tools_returns_reading_actions():
    tools = build_mcp_tools()
    names = {t.name for t in tools}
    assert "reading__next" in names
    assert "reading__stats" in names
    assert "reading__search" in names
    assert "reading__done" in names
    assert "reading__sync_from_mendeley" in names


def test_build_mcp_tools_schema_is_object():
    tools = build_mcp_tools()
    for t in tools:
        schema = t.inputSchema
        assert isinstance(schema, dict), f"{t.name} inputSchema must be a dict"
        # Pydantic JSON schema always has "type": "object" or "properties".
        assert schema.get("type") == "object" or "properties" in schema, (
            f"{t.name} inputSchema should describe an object"
        )


def test_build_mcp_tools_description_prefixed_with_tool():
    tools = build_mcp_tools()
    reading_tools = [t for t in tools if t.name.startswith("reading__")]
    assert reading_tools, "Expected at least one reading__ tool"
    assert all(t.description.startswith("[reading]") for t in reading_tools)


# ---------------------------------------------------------------------------
# Action invocation
# ---------------------------------------------------------------------------

def test_invoke_action_stats(tmp_docent_home):
    """invoke_action('reading', 'stats', {}) should return valid JSON."""
    text = invoke_action("reading", "stats", {})
    data = json.loads(text)
    assert isinstance(data, dict)


def test_invoke_action_bad_tool():
    with pytest.raises(ValueError, match="No tool named"):
        invoke_action("nonexistent", "next", {})


def test_invoke_action_bad_action():
    with pytest.raises(ValueError, match="no action"):
        invoke_action("reading", "does-not-exist", {})


# ---------------------------------------------------------------------------
# Single-action tool support
# ---------------------------------------------------------------------------

class _SingleActionInputs(BaseModel):
    name: str = "world"


@register_tool
class _SingleActionTool(Tool):
    name = "singleton"
    description = "A single-action test tool."
    input_schema = _SingleActionInputs

    def run(self, inputs: _SingleActionInputs, context: Context) -> dict:
        return {"greeting": f"Hello, {inputs.name}!"}


@pytest.fixture
def _single_action_registered(isolated_registry):
    """Register a temporary single-action tool.  Cleans up after the test."""
    return _SingleActionTool


def test_build_mcp_tools_includes_single_action_tool(_single_action_registered):
    tools = build_mcp_tools()
    names = {t.name for t in tools}
    assert "singleton__run" in names

    singleton = next(t for t in tools if t.name == "singleton__run")
    assert singleton.description == "[singleton] A single-action test tool."
    schema = singleton.inputSchema
    assert isinstance(schema, dict)
    assert "name" in schema.get("properties", {})


def test_invoke_action_single_action_tool(_single_action_registered, tmp_docent_home):
    text = invoke_action("singleton", "run", {"name": "Hermes"})
    data = json.loads(text)
    assert data == {"greeting": "Hello, Hermes!"}


def test_invoke_action_single_action_bad_action(_single_action_registered, tmp_docent_home):
    with pytest.raises(ValueError, match="single-action"):
        invoke_action("singleton", "stats", {})


def test_invoke_action_single_action_bad_tool():
    with pytest.raises(ValueError, match="No tool named"):
        invoke_action("nonexistent", "run", {})

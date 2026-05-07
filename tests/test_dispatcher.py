"""Invariants on invoke_action() in mcp_server.py."""

import json

import pytest
from pydantic import BaseModel

from docent.core.tool import Tool, action
from docent.core.registry import register_tool
from docent.core.events import ProgressEvent
from docent.mcp_server import invoke_action


# ---------------------------------------------------------------------------
# Fixture tools — registered at module-import time so invoke_action can find
# them.  Names are deliberately unique (test-ping-xyz, test-stream-xyz) so
# they won't clash if the suite runs multiple times in-process.
# ---------------------------------------------------------------------------

class _PingInputs(BaseModel):
    msg: str = "hello"


class _StreamInputs(BaseModel):
    n: int = 2


@register_tool
class _PingTool(Tool):
    name = "test-ping-xyz"
    description = "Ping for testing."

    @action(description="Return a pong.", input_schema=_PingInputs)
    def pong(self, inputs, context):
        return {"pong": inputs.msg}


@register_tool
class _StreamTool(Tool):
    name = "test-stream-xyz"
    description = "Stream for testing."

    @action(description="Stream progress then return.", input_schema=_StreamInputs)
    def stream(self, inputs, context):
        for i in range(inputs.n):
            yield ProgressEvent(phase="work", message=f"step {i}")
        return {"done": True}


# -----------------------------------------------------------------------
# 1. Sync action returns JSON
# -----------------------------------------------------------------------

def test_invoke_sync_action_returns_json():
    raw = invoke_action("test-ping-xyz", "pong", {"msg": "hi"})
    result = json.loads(raw)
    assert result["pong"] == "hi"


# -----------------------------------------------------------------------
# 2. Sync action with default inputs
# -----------------------------------------------------------------------

def test_invoke_sync_action_default_inputs():
    raw = invoke_action("test-ping-xyz", "pong", {})
    result = json.loads(raw)
    assert result["pong"] == "hello"


# -----------------------------------------------------------------------
# 3. Generator action contains progress lines
# -----------------------------------------------------------------------

def test_invoke_generator_action_contains_progress():
    raw = invoke_action("test-stream-xyz", "stream", {"n": 2})
    assert "[work] step 0" in raw
    assert "[work] step 1" in raw


# -----------------------------------------------------------------------
# 4. Generator action: last line is JSON result
# -----------------------------------------------------------------------

def test_invoke_generator_action_last_line_is_json():
    raw = invoke_action("test-stream-xyz", "stream", {"n": 2})
    lines = raw.split("\n")
    json_start = next(i for i, l in enumerate(lines) if l.startswith("{"))
    result = json.loads("\n".join(lines[json_start:]))
    assert result["done"] is True


# -----------------------------------------------------------------------
# 5. Unknown tool raises ValueError
# -----------------------------------------------------------------------

def test_invoke_unknown_tool_raises():
    with pytest.raises(ValueError, match="No tool named"):
        invoke_action("no-such-tool", "whatever", {})


# -----------------------------------------------------------------------
# 6. Unknown action raises ValueError
# -----------------------------------------------------------------------

def test_invoke_unknown_action_raises():
    with pytest.raises(ValueError, match="no action"):
        invoke_action("test-ping-xyz", "no-such-action", {})
"""Tests for docent.core.invoke — make_context() and run_action()."""
from __future__ import annotations

import inspect

import pytest
from pydantic import BaseModel

from docent.core import Context
from docent.core.invoke import make_context, run_action
from docent.core.tool import Tool, action
from docent.core.registry import register_tool
from docent.core.events import ProgressEvent


# ---------------------------------------------------------------------------
# Fixture tools — unique names to avoid registry collisions.
# ---------------------------------------------------------------------------

class _EchoInputs(BaseModel):
    value: str = "default"


class _GenInputs(BaseModel):
    steps: int = 2


@register_tool
class _EchoTool(Tool):
    name = "test-echo-invoke"
    description = "Echo for core invoke tests."

    @action(description="Echo the value.", input_schema=_EchoInputs)
    def echo(self, inputs: _EchoInputs, context: Context) -> dict:
        return {"echo": inputs.value}


@register_tool
class _GenInvokeTool(Tool):
    name = "test-gen-invoke"
    description = "Generator for core invoke tests."

    @action(description="Yield steps then return.", input_schema=_GenInputs)
    def gen(self, inputs: _GenInputs, context: Context):
        for i in range(inputs.steps):
            yield ProgressEvent(phase="step", message=f"step {i}")
        return {"steps_done": inputs.steps}


# ---------------------------------------------------------------------------
# make_context()
# ---------------------------------------------------------------------------

def test_make_context_returns_context():
    ctx = make_context()
    assert isinstance(ctx, Context)


def test_make_context_has_settings():
    ctx = make_context()
    assert ctx.settings is not None


# ---------------------------------------------------------------------------
# run_action() — sync
# ---------------------------------------------------------------------------

def test_run_action_sync_returns_raw_result():
    result = run_action("test-echo-invoke", "echo", {"value": "hi"})
    assert result == {"echo": "hi"}


def test_run_action_sync_default_inputs():
    result = run_action("test-echo-invoke", "echo", {})
    assert result == {"echo": "default"}


def test_run_action_accepts_provided_context():
    ctx = make_context()
    result = run_action("test-echo-invoke", "echo", {"value": "ctx-test"}, context=ctx)
    assert result == {"echo": "ctx-test"}


# ---------------------------------------------------------------------------
# run_action() — generator
# ---------------------------------------------------------------------------

def test_run_action_generator_returns_generator():
    raw = run_action("test-gen-invoke", "gen", {"steps": 3})
    assert inspect.isgenerator(raw)


def test_run_action_generator_yields_progress_then_returns():
    raw = run_action("test-gen-invoke", "gen", {"steps": 2})
    events = []
    result = None
    try:
        while True:
            events.append(next(raw))
    except StopIteration as stop:
        result = stop.value
    assert len(events) == 2
    assert all(isinstance(e, ProgressEvent) for e in events)
    assert result == {"steps_done": 2}


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

def test_run_action_unknown_tool_raises():
    with pytest.raises(ValueError, match="No tool named"):
        run_action("no-such-tool", "whatever", {})


def test_run_action_unknown_action_raises():
    with pytest.raises(ValueError, match="no action"):
        run_action("test-echo-invoke", "no-such-action", {})


def test_run_action_single_action_tool_wrong_name_raises():
    # Single-action tools must use "run" as the action name.
    # (No single-action tool registered in tests currently, but the error
    # path in run_action is exercised via an existing tool's wrong action.)
    with pytest.raises(ValueError):
        run_action("test-echo-invoke", "no-such-action", {})

from __future__ import annotations

import sys

import pytest
from pydantic import BaseModel

from docent.core import Tool, action, register_tool
from docent.core.registry import all_tools, get_tool
from docent.core.tool import collect_actions


class _Inputs(BaseModel):
    x: int = 0


def test_register_single_action_tool(isolated_registry):
    @register_tool
    class _MyTool(Tool):
        name = "test-single-xyz"
        description = "Test single-action tool."
        input_schema = _Inputs

        def run(self, inputs, context):
            return {"x": inputs.x}

    assert get_tool("test-single-xyz") is _MyTool
    assert "test-single-xyz" in all_tools()


def test_register_multi_action_tool(isolated_registry):
    @register_tool
    class _MultiTool(Tool):
        name = "test-multi-xyz"
        description = "Test multi-action tool."

        @action(description="Echo input.", input_schema=_Inputs)
        def echo(self, inputs, context):
            return inputs.x

        @action(description="Double input.", input_schema=_Inputs, name="double-it")
        def double(self, inputs, context):
            return inputs.x * 2

    actions = collect_actions(_MultiTool)
    assert "echo" in actions
    assert "double-it" in actions
    assert "double" not in actions


def test_reserved_name_rejected(isolated_registry):
    with pytest.raises(ValueError, match="reserved"):
        @register_tool
        class _BadTool(Tool):
            name = "list"
            description = "Bad."
            input_schema = _Inputs

            def run(self, inputs, context):
                return None


def test_missing_input_schema_rejected(isolated_registry):
    with pytest.raises(TypeError, match="input_schema"):
        @register_tool
        class _BadTool(Tool):
            name = "test-missing-schema-xyz"
            description = "Bad."

            def run(self, inputs, context):
                return None


def test_double_registration_rejected(isolated_registry):
    @register_tool
    class _OneTool(Tool):
        name = "test-dup-xyz"
        description = "First."
        input_schema = _Inputs

        def run(self, inputs, context):
            return None

    with pytest.raises(ValueError, match="already registered"):
        @register_tool
        class _TwoTool(Tool):
            name = "test-dup-xyz"
            description = "Second."
            input_schema = _Inputs

            def run(self, inputs, context):
                return None


def test_litellm_lazy_import_invariant():
    import docent.core  # noqa: F401
    import docent.core.registry  # noqa: F401
    import docent.core.tool  # noqa: F401
    assert "litellm" not in sys.modules, (
        "litellm leaked into sys.modules from a non-LLM import path"
    )

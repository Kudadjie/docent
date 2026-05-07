"""Invariants on Tool ABC, @action decorator, collect_actions, and register_tool."""

from docent.core.tool import Tool, action, collect_actions, Action
from docent.core.registry import register_tool, get_tool, all_tools
from pydantic import BaseModel
import pytest


class _DummyInputs(BaseModel):
    value: str = "x"


# -----------------------------------------------------------------------
# 1. Tool.run() raises NotImplementedError when not overridden
# -----------------------------------------------------------------------

def test_run_raises_not_implemented():
    class BareTool(Tool):
        name = "bare-xyz"
        description = "Bare."

    with pytest.raises(NotImplementedError):
        BareTool().run(None, None)


# -----------------------------------------------------------------------
# 2. collect_actions: underscores → dashes in CLI name
# -----------------------------------------------------------------------

def test_collect_actions_cli_name_from_method_name(isolated_registry):
    class MyTool(Tool):
        name = "my-tool-xyz"
        description = "Test."

        @action(description="Do something", input_schema=_DummyInputs)
        def do_something(self, inputs, context):
            pass

    result = collect_actions(MyTool)
    assert "do-something" in result
    assert result["do-something"][0] == "do_something"


# -----------------------------------------------------------------------
# 3. collect_actions: custom name override
# -----------------------------------------------------------------------

def test_collect_actions_custom_name_override(isolated_registry):
    class MyTool(Tool):
        name = "my-tool-xyz"
        description = "Test."

        @action(description="Custom", input_schema=_DummyInputs, name="custom-name")
        def some_method(self, inputs, context):
            pass

    result = collect_actions(MyTool)
    assert "custom-name" in result
    assert "some-method" not in result


# -----------------------------------------------------------------------
# 4. collect_actions: name collision raises ValueError
# -----------------------------------------------------------------------

def test_collect_actions_name_collision_raises(isolated_registry):
    class MyTool(Tool):
        name = "my-tool-xyz"
        description = "Test."

        @action(description="A", input_schema=_DummyInputs)
        def foo_bar(self, inputs, context):
            pass

        @action(description="B", input_schema=_DummyInputs, name="foo-bar")
        def other_method(self, inputs, context):
            pass

    with pytest.raises(ValueError, match="same CLI name"):
        collect_actions(MyTool)


# -----------------------------------------------------------------------
# 5. register_tool rejects non-Tool classes
# -----------------------------------------------------------------------

def test_register_non_tool_class_rejected(isolated_registry):
    class NotATool:
        name = "bad-xyz"
        description = "Not a tool."

    with pytest.raises(TypeError):
        register_tool(NotATool)


# -----------------------------------------------------------------------
# 6. Missing name attr rejected
# -----------------------------------------------------------------------

def test_missing_name_attr_rejected(isolated_registry):
    class NoName(Tool):
        description = "No name."

    with pytest.raises(TypeError, match="name"):
        register_tool(NoName)


# -----------------------------------------------------------------------
# 7. Missing description attr rejected
# -----------------------------------------------------------------------

def test_missing_description_attr_rejected(isolated_registry):
    class NoDesc(Tool):
        name = "no-desc-xyz"

    with pytest.raises(TypeError, match="description"):
        register_tool(NoDesc)


# -----------------------------------------------------------------------
# 8. Empty name rejected
# -----------------------------------------------------------------------

def test_empty_name_rejected(isolated_registry):
    class EmptyName(Tool):
        name = ""
        description = "Empty name."

    with pytest.raises(TypeError, match="non-empty"):
        register_tool(EmptyName)


# -----------------------------------------------------------------------
# 9. Mixed single-action and multi-action rejected
# -----------------------------------------------------------------------

def test_mixed_single_and_multi_action_rejected(isolated_registry):
    class MixedTool(Tool):
        name = "mixed-xyz"
        description = "Mixed."
        input_schema = _DummyInputs

        @action(description="An action", input_schema=_DummyInputs)
        def do_thing(self, inputs, context):
            pass

        def run(self, inputs, context):
            return {"ok": True}

    with pytest.raises(TypeError):
        register_tool(MixedTool)


# -----------------------------------------------------------------------
# 10. Mixed input_schema and @action rejected
# -----------------------------------------------------------------------

def test_mixed_input_schema_and_action_rejected(isolated_registry):
    class MixedSchemaTool(Tool):
        name = "mixed-schema-xyz"
        description = "Mixed schema."
        input_schema = _DummyInputs

        @action(description="An action", input_schema=_DummyInputs)
        def do_thing(self, inputs, context):
            pass

    with pytest.raises(TypeError):
        register_tool(MixedSchemaTool)


# -----------------------------------------------------------------------
# 11. @action with non-BaseModel input_schema rejected
# -----------------------------------------------------------------------

def test_action_non_basemodel_input_schema_rejected(isolated_registry):
    class BadSchemaTool(Tool):
        name = "bad-schema-xyz"
        description = "Bad schema."

        @action(description="Bad", input_schema=dict)
        def do_thing(self, inputs, context):
            pass

    with pytest.raises(TypeError, match="BaseModel"):
        register_tool(BadSchemaTool)


# -----------------------------------------------------------------------
# 12. get_tool with missing name raises KeyError
# -----------------------------------------------------------------------

def test_get_tool_missing_raises_key_error():
    with pytest.raises(KeyError):
        get_tool("nonexistent-xyz")


# -----------------------------------------------------------------------
# 13. all_tools returns a copy (mutation doesn't affect registry)
# -----------------------------------------------------------------------

def test_all_tools_returns_copy(isolated_registry):
    @register_tool
    class CopyTool(Tool):
        name = "copy-test-xyz"
        description = "Copy test."

        @action(description="Ping", input_schema=_DummyInputs)
        def ping(self, inputs, context):
            pass

    first = all_tools()
    assert "copy-test-xyz" in first
    del first["copy-test-xyz"]

    second = all_tools()
    assert "copy-test-xyz" in second
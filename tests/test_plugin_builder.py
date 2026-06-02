"""Tests for the Plugin Builder bundled plugin."""

from __future__ import annotations

import ast
import json
from unittest.mock import MagicMock, patch

import pytest

from docent.bundled_plugins.plugin_builder import (
    GenerateInputs,
    InstallInputs,
    IterateInputs,
    PluginBuilderTool,
    SandboxTestInputs,
    ValidateInputs,
    _extract_actions_from_ast,
    _extract_tool_name_from_ast,
    _static_validate,
)

# ---------------------------------------------------------------------------
# Minimal plugin code used across tests
# ---------------------------------------------------------------------------

_VALID_PLUGIN = """\
from pydantic import BaseModel, Field
from docent.core.tool import Tool, action
from docent.core.registry import register_tool
from docent.core.context import Context


class PingInputs(BaseModel):
    message: str = Field(description="Message to echo back.")


class PingResult(BaseModel):
    ok: bool
    echo: str


@register_tool
class PingTool(Tool):
    name = "ping_sandbox_test"
    description = "Echo a message."

    @action(description="Echo the input message.", input_schema=PingInputs)
    def ping(self, inputs: PingInputs, context: Context) -> PingResult:
        return PingResult(ok=True, echo=inputs.message)
"""

_INVALID_PLUGIN_NO_TOOL = """\
from pydantic import BaseModel

class NotATool:
    pass
"""

_INVALID_PLUGIN_SYNTAX = """\
def broken(:
    pass
"""


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def test_extract_actions():
    tree = ast.parse(_VALID_PLUGIN)
    actions = _extract_actions_from_ast(tree)
    assert "ping" in actions


def test_extract_tool_name():
    tree = ast.parse(_VALID_PLUGIN)
    name = _extract_tool_name_from_ast(tree)
    assert name == "ping_sandbox_test"


def test_extract_tool_name_missing():
    code = "from docent.core.tool import Tool\nclass T(Tool): pass"
    tree = ast.parse(code)
    assert _extract_tool_name_from_ast(tree) is None


# ---------------------------------------------------------------------------
# _static_validate
# ---------------------------------------------------------------------------


def test_validate_valid_plugin():
    valid, errors, warnings = _static_validate(_VALID_PLUGIN)
    assert valid is True
    assert errors == []


def test_validate_no_tool_subclass():
    valid, errors, warnings = _static_validate(_INVALID_PLUGIN_NO_TOOL)
    assert valid is False
    assert any("Tool" in e for e in errors)


def test_validate_syntax_error():
    valid, errors, warnings = _static_validate(_INVALID_PLUGIN_SYNTAX)
    assert valid is False
    assert any("Syntax" in e for e in errors)


def test_validate_missing_register_tool():
    code = """\
from pydantic import BaseModel, Field
from docent.core.tool import Tool, action
from docent.core.context import Context

class MyInputs(BaseModel):
    x: str = Field(description="x")

class MyResult(BaseModel):
    ok: bool

class MyTool(Tool):
    name = "my_tool"
    description = "desc"

    @action(description="run", input_schema=MyInputs)
    def run(self, inputs: MyInputs, context: Context) -> MyResult:
        return MyResult(ok=True)
"""
    valid, errors, _ = _static_validate(code)
    assert valid is False
    assert any("register_tool" in e for e in errors)


# ---------------------------------------------------------------------------
# validate action
# ---------------------------------------------------------------------------


@pytest.fixture
def tool():
    return PluginBuilderTool()


@pytest.fixture
def ctx():
    from docent.config.settings import PluginBuilderSettings, Settings

    settings = Settings(plugin_builder=PluginBuilderSettings(model="test/model"))
    ctx = MagicMock()
    ctx.settings = settings
    return ctx


def test_validate_action_valid(tool, ctx):
    result = tool.validate(ValidateInputs(code=_VALID_PLUGIN), ctx)
    assert result.ok is True
    assert result.valid is True
    assert result.errors == []


def test_validate_action_invalid(tool, ctx):
    result = tool.validate(ValidateInputs(code=_INVALID_PLUGIN_NO_TOOL), ctx)
    assert result.ok is True
    assert result.valid is False
    assert len(result.errors) > 0


# ---------------------------------------------------------------------------
# sandbox_test action
# ---------------------------------------------------------------------------


def test_sandbox_test_success(tool, ctx):
    result = tool.sandbox_test(
        SandboxTestInputs(
            code=_VALID_PLUGIN,
            action="ping",
            inputs='{"message": "hello"}',
        ),
        ctx,
    )
    assert result.ok is True
    assert result.success is True
    output = json.loads(result.output)
    assert output["ok"] is True
    assert output["echo"] == "hello"
    assert result.errors == []


def test_sandbox_test_wrong_action(tool, ctx):
    result = tool.sandbox_test(
        SandboxTestInputs(
            code=_VALID_PLUGIN,
            action="nonexistent",
            inputs="{}",
        ),
        ctx,
    )
    assert result.ok is True
    assert result.success is False
    assert result.errors != []


def test_sandbox_test_invalid_json(tool, ctx):
    result = tool.sandbox_test(
        SandboxTestInputs(code=_VALID_PLUGIN, action="ping", inputs="not-json"),
        ctx,
    )
    assert result.ok is False
    assert any("JSON" in e for e in result.errors)


def test_sandbox_test_restores_registry(tool, ctx):
    """Registry must be identical before and after a sandbox run."""
    import docent.core.registry as reg

    before = set(reg._REGISTRY.keys())
    tool.sandbox_test(
        SandboxTestInputs(code=_VALID_PLUGIN, action="ping", inputs='{"message": "x"}'),
        ctx,
    )
    after = set(reg._REGISTRY.keys())
    assert before == after


# Plugin with nested models and `from __future__ import annotations` — this
# pattern triggers the Pydantic v2 forward-reference error that the sandbox
# must resolve via model_rebuild(_types_namespace=ns).
_NESTED_MODELS_PLUGIN = """\
from __future__ import annotations
from pydantic import BaseModel, Field
from docent.core.tool import Tool, action
from docent.core.registry import register_tool
from docent.core.context import Context


class ItemEntry(BaseModel):
    id: str
    label: str


class ListResult(BaseModel):
    ok: bool
    items: list[ItemEntry] = Field(default_factory=list)
    total: int = 0


class ListInputs(BaseModel):
    limit: int = 5


@register_tool
class ListTool(Tool):
    name = "list_tool"
    description = "A tool with nested Pydantic models."

    @action(description="Return a list of items.", input_schema=ListInputs)
    def list_items(self, inputs: ListInputs, context: Context) -> ListResult:
        items = [ItemEntry(id=str(i), label=f"item-{i}") for i in range(inputs.limit)]
        return ListResult(ok=True, items=items, total=len(items))
"""


def test_sandbox_nested_pydantic_models(tool, ctx):
    """Sandbox must not raise PydanticUserError for nested model forward refs."""
    result = tool.sandbox_test(
        SandboxTestInputs(code=_NESTED_MODELS_PLUGIN, action="list-items", inputs='{"limit": 3}'),
        ctx,
    )
    assert result.ok is True, result.errors
    assert result.success is True, result.errors
    output = json.loads(result.output)
    assert output["ok"] is True
    assert output["total"] == 3
    assert len(output["items"]) == 3


# ---------------------------------------------------------------------------
# install action
# ---------------------------------------------------------------------------


def test_install_writes_file(tool, ctx, tmp_path):
    with patch("docent.bundled_plugins.plugin_builder._plugins_dir", return_value=tmp_path):
        result = tool.install(InstallInputs(code=_VALID_PLUGIN, name="my_test_plugin"), ctx)
    assert result.ok is True
    assert (tmp_path / "my_test_plugin.py").exists()
    assert "ping" in result.actions_registered


def test_install_collision_blocked(tool, ctx, tmp_path):
    (tmp_path / "clash.py").write_text("# existing", encoding="utf-8")
    with patch("docent.bundled_plugins.plugin_builder._plugins_dir", return_value=tmp_path):
        result = tool.install(InstallInputs(code=_VALID_PLUGIN, name="clash"), ctx)
    assert result.ok is False
    assert "already exists" in (result.error or "")


def test_install_force_overwrites(tool, ctx, tmp_path):
    (tmp_path / "clash.py").write_text("# old", encoding="utf-8")
    with patch("docent.bundled_plugins.plugin_builder._plugins_dir", return_value=tmp_path):
        result = tool.install(InstallInputs(code=_VALID_PLUGIN, name="clash", force=True), ctx)
    assert result.ok is True


def test_install_invalid_name(tool, ctx, tmp_path):
    with patch("docent.bundled_plugins.plugin_builder._plugins_dir", return_value=tmp_path):
        result = tool.install(InstallInputs(code=_VALID_PLUGIN, name="Bad-Name!"), ctx)
    assert result.ok is False
    assert "snake_case" in (result.error or "")


# ---------------------------------------------------------------------------
# generate / iterate (mocked LLM)
# ---------------------------------------------------------------------------

_LLM_RESPONSE = f"Here is the plugin:\n\n```python\n{_VALID_PLUGIN}\n```"


def _drain(gen):
    """Drain a generator action and return its final result value."""
    import inspect

    if not inspect.isgenerator(gen):
        return gen
    result = None
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        result = stop.value
    return result


def test_generate_calls_llm_and_parses_code(tool, ctx):
    with patch(
        "docent.bundled_plugins.plugin_builder._llm_generate",
        return_value=_LLM_RESPONSE,
    ):
        result = _drain(tool.generate(GenerateInputs(spec="Echo a message back to the user."), ctx))
    assert result.ok is True
    assert "PingTool" in result.code
    assert "ping" in result.actions
    assert result.plugin_id  # non-empty UUID


def test_generate_llm_error_returns_failure(tool, ctx):
    with patch(
        "docent.bundled_plugins.plugin_builder._llm_generate",
        side_effect=RuntimeError("model unavailable"),
    ):
        result = _drain(tool.generate(GenerateInputs(spec="anything"), ctx))
    assert result.ok is False
    assert "model unavailable" in (result.error or "")


def test_iterate_revises_code(tool, ctx):
    with patch(
        "docent.bundled_plugins.plugin_builder._llm_generate",
        return_value=_LLM_RESPONSE,
    ):
        result = _drain(
            tool.iterate(
                IterateInputs(
                    plugin_id="abc-123",
                    code=_VALID_PLUGIN,
                    feedback="Add a --loud flag",
                ),
                ctx,
            )
        )
    assert result.ok is True
    assert result.plugin_id == "abc-123"
    assert "PingTool" in result.code


# ---------------------------------------------------------------------------
# Doctor check
# ---------------------------------------------------------------------------


def test_check_plugin_builder_ok():
    from unittest.mock import MagicMock, patch

    from docent.cli_doctor import _check_plugin_builder_model
    from docent.config.settings import PluginBuilderSettings, Settings

    settings = Settings(plugin_builder=PluginBuilderSettings(model="glm-5.1"))
    mock_client = MagicMock()
    mock_client.is_available.return_value = True
    with patch("docent.bundled_plugins.studio.oc_client.OcClient", return_value=mock_client):
        label, status, version, _ = _check_plugin_builder_model(settings)
    assert label == "Plugin Builder"
    assert status == "OK"
    assert "glm-5.1" in version


def test_check_plugin_builder_opencode_down():
    from unittest.mock import MagicMock, patch

    from docent.cli_doctor import _check_plugin_builder_model
    from docent.config.settings import PluginBuilderSettings, Settings

    settings = Settings(plugin_builder=PluginBuilderSettings(model="glm-5.1"))
    mock_client = MagicMock()
    mock_client.is_available.return_value = False
    with patch("docent.bundled_plugins.studio.oc_client.OcClient", return_value=mock_client):
        label, status, _, detail = _check_plugin_builder_model(settings)
    assert label == "Plugin Builder"
    assert status == "WARN"
    assert "OpenCode" in detail


# ---------------------------------------------------------------------------
# PluginBuilderSettings defaults
# ---------------------------------------------------------------------------


def test_plugin_builder_settings_defaults():
    from docent.config.settings import PluginBuilderSettings

    s = PluginBuilderSettings()
    assert s.model == "glm-5.1"

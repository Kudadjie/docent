from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from docent.core import all_tools, load_plugins, register_tool, run_startup_hooks
from docent.core.registry import _REGISTRY
from docent.core.tool import Tool


@pytest.fixture
def plugin_dirs(tmp_path, monkeypatch, isolated_registry):
    """Provide isolated plugin directories and clean up global state after each test."""
    import docent.core.plugin_loader as pl

    bundled = tmp_path / "bundled_plugins"
    user = tmp_path / "plugins"

    monkeypatch.setattr(pl, "_bundled_plugins_dir", lambda: bundled)
    monkeypatch.setattr(pl, "plugins_dir", lambda: user)

    original_path = list(sys.path)
    original_modules = set(sys.modules.keys())
    original_hooks = list(pl._STARTUP_HOOKS)

    yield {"bundled": bundled, "user": user}

    sys.path[:] = original_path
    for mod in list(sys.modules.keys()):
        if mod not in original_modules:
            del sys.modules[mod]
    pl._STARTUP_HOOKS[:] = original_hooks


def _write_flat_plugin(directory: Path, name: str, content: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.py"
    path.write_text(content, encoding="utf-8")
    return path


def _write_package_plugin(directory: Path, name: str, content: str) -> Path:
    pkg_dir = directory / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    init_file = pkg_dir / "__init__.py"
    init_file.write_text(content, encoding="utf-8")
    return init_file


VALID_FLAT_PLUGIN = """
from docent.core import Tool, register_tool
from pydantic import BaseModel

class FakeInputs(BaseModel):
    pass

@register_tool
class FakeTool(Tool):
    name = "fake-plugin-tool"
    description = "test"
    input_schema = FakeInputs

    def run(self, inputs, context):
        return None
"""

VALID_PACKAGE_PLUGIN = """
from docent.core import Tool, register_tool
from pydantic import BaseModel

class FakeInputs(BaseModel):
    pass

@register_tool
class FakePackageTool(Tool):
    name = "fake-package-tool"
    description = "test package"
    input_schema = FakeInputs

    def run(self, inputs, context):
        return None
"""

BROKEN_PLUGIN = "this is not valid python !!!"

STARTUP_HOOK_PLUGIN = """
from docent.core import Tool, register_tool
from pydantic import BaseModel

class FakeInputs(BaseModel):
    pass

@register_tool
class FakeTool(Tool):
    name = "startup-tool"
    description = "test"
    input_schema = FakeInputs

    def run(self, inputs, context):
        return None

def on_startup(context):
    context._hook_called = True
"""

CONFLICT_PLUGIN = """
from docent.core import Tool, register_tool
from pydantic import BaseModel

class FakeInputs(BaseModel):
    pass

@register_tool
class FakeTool(Tool):
    name = "conflict-tool"
    description = "conflict"
    input_schema = FakeInputs

    def run(self, inputs, context):
        return None
"""


class TestPluginLoader:
    def test_no_plugins_dir(self, plugin_dirs, capsys):
        """load_plugins with nonexistent dirs is a no-op."""
        load_plugins()
        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""

    def test_empty_plugins_dir_is_noop(self, plugin_dirs):
        """An existing but empty plugins directory loads nothing."""
        plugin_dirs["user"].mkdir(parents=True)
        before = dict(all_tools())
        load_plugins()
        assert dict(all_tools()) == before

    def test_valid_flat_plugin(self, plugin_dirs):
        _write_flat_plugin(plugin_dirs["user"], "flat_tool", VALID_FLAT_PLUGIN)
        load_plugins()
        tools = all_tools()
        assert "fake-plugin-tool" in tools

    def test_valid_package_plugin(self, plugin_dirs):
        _write_package_plugin(plugin_dirs["user"], "pkg_tool", VALID_PACKAGE_PLUGIN)
        load_plugins()
        tools = all_tools()
        assert "fake-package-tool" in tools

    def test_broken_plugin_skipped_others_load(self, plugin_dirs, capsys):
        _write_flat_plugin(plugin_dirs["user"], "broken", BROKEN_PLUGIN)
        _write_flat_plugin(plugin_dirs["user"], "good", VALID_FLAT_PLUGIN)
        load_plugins()
        captured = capsys.readouterr()
        assert "failed to load plugin 'broken'" in captured.err
        tools = all_tools()
        assert "fake-plugin-tool" in tools

    def test_name_conflict_warns_and_skips(self, plugin_dirs, capsys):
        from pydantic import BaseModel

        class PreInputs(BaseModel):
            pass

        @register_tool
        class PreTool(Tool):
            name = "conflict-tool"
            description = "pre-existing"
            input_schema = PreInputs

            def run(self, inputs, context):
                return None

        _write_flat_plugin(plugin_dirs["user"], "conflict", CONFLICT_PLUGIN)
        load_plugins()
        captured = capsys.readouterr()
        assert "already registered" in captured.err
        assert "conflict-tool" in captured.err

    def test_on_startup_hook_collected(self, plugin_dirs):
        _write_flat_plugin(plugin_dirs["user"], "startup", STARTUP_HOOK_PLUGIN)
        load_plugins()
        mock_ctx = MagicMock()
        run_startup_hooks(mock_ctx)
        assert mock_ctx._hook_called is True

    def test_underscore_prefixed_skipped(self, plugin_dirs):
        _write_flat_plugin(plugin_dirs["user"], "_private", VALID_FLAT_PLUGIN)
        _write_package_plugin(plugin_dirs["user"], "_private_pkg", VALID_PACKAGE_PLUGIN)
        load_plugins()
        tools = all_tools()
        assert "fake-plugin-tool" not in tools
        assert "fake-package-tool" not in tools

    def test_dir_without_init_skipped(self, plugin_dirs):
        """A directory without __init__.py is not treated as a plugin package."""
        bare = plugin_dirs["user"] / "bare_dir"
        bare.mkdir(parents=True)
        (bare / "some_module.py").write_text("x = 1", encoding="utf-8")
        before = dict(all_tools())
        load_plugins()
        assert dict(all_tools()) == before

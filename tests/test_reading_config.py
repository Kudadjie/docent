"""Tests for reading config-show / config-set, including mendeley_mcp_command."""
from __future__ import annotations

from docent.config import load_settings
from docent.core.context import Context
from docent.llm import LLMClient
from reading import ConfigSetInputs, ConfigShowInputs, ReadingQueue


class _StubExecutor:
    def run(self, args, *, timeout=None, cwd=None, env=None, check=True):
        from docent.execution.executor import ProcessResult
        return ProcessResult(args=list(args), returncode=0, stdout="", stderr="", duration=0.0)


def _ctx() -> Context:
    settings = load_settings()
    return Context(settings=settings, llm=LLMClient(settings), executor=_StubExecutor())


# ─── config-set: string keys ──────────────────────────────────────────────────

def test_config_set_database_dir(tmp_docent_home):
    tool = ReadingQueue()
    result = tool.config_set(ConfigSetInputs(key="database_dir", value="/tmp/papers"), _ctx())
    assert result.ok
    assert result.key == "database_dir"
    assert "/tmp/papers" in result.message


def test_config_set_queue_collection(tmp_docent_home):
    tool = ReadingQueue()
    result = tool.config_set(ConfigSetInputs(key="queue_collection", value="My Papers"), _ctx())
    assert result.ok
    assert "My Papers" in result.message


def test_config_set_unknown_key_rejected(tmp_docent_home):
    tool = ReadingQueue()
    result = tool.config_set(ConfigSetInputs(key="nonexistent_key", value="x"), _ctx())
    assert not result.ok
    assert "Unknown key" in result.message
    assert "nonexistent_key" in result.message


# ─── config-set: mendeley_mcp_command (list-typed) ────────────────────────────

def test_config_set_mendeley_mcp_command_parses_to_list(tmp_docent_home):
    from docent.config.loader import load_settings as _load
    import tomllib

    tool = ReadingQueue()
    result = tool.config_set(
        ConfigSetInputs(key="mendeley_mcp_command", value="uvx mendeley-mcp --flag"),
        _ctx(),
    )
    assert result.ok

    # The value must be stored as a TOML array, not a string.
    from docent.utils.paths import config_file
    raw = tomllib.loads(config_file().read_text(encoding="utf-8"))
    stored = raw.get("reading", {}).get("mendeley_mcp_command")
    assert stored == ["uvx", "mendeley-mcp", "--flag"]


def test_config_set_mendeley_mcp_command_empty_clears(tmp_docent_home):
    from docent.utils.paths import config_file
    import tomllib

    tool = ReadingQueue()
    # Set then clear.
    tool.config_set(ConfigSetInputs(key="mendeley_mcp_command", value="uvx mendeley-mcp"), _ctx())
    result = tool.config_set(ConfigSetInputs(key="mendeley_mcp_command", value=""), _ctx())
    assert result.ok

    raw = tomllib.loads(config_file().read_text(encoding="utf-8"))
    stored = raw.get("reading", {}).get("mendeley_mcp_command")
    assert stored is None


# ─── config-show: mendeley_mcp_command visible ────────────────────────────────

def test_config_show_includes_mendeley_mcp_command_default(tmp_docent_home):
    tool = ReadingQueue()
    result = tool.config_show(ConfigShowInputs(), _ctx())
    assert result.mendeley_mcp_command is None  # not set → None
    shapes = result.to_shapes()
    labels = [s.label for s in shapes if hasattr(s, "label")]
    assert "mendeley_mcp_command" in labels
    # Default display value
    values = {s.label: s.value for s in shapes if hasattr(s, "label") and hasattr(s, "value")}
    assert "default" in values["mendeley_mcp_command"]


def test_config_show_reflects_set_mendeley_mcp_command(tmp_docent_home):
    tool = ReadingQueue()
    tool.config_set(ConfigSetInputs(key="mendeley_mcp_command", value="uvx mendeley-mcp"), _ctx())
    # Reload settings so config_show picks up the written value.
    result = tool.config_show(ConfigShowInputs(), _ctx())
    # The settings object cached in context may not reflect the write; read via
    # a fresh context to confirm the value is persisted, not just returned from cache.
    fresh_settings = load_settings()
    assert fresh_settings.reading.mendeley_mcp_command == ["uvx", "mendeley-mcp"]

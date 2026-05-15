from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from docent.config.settings import Settings
from docent.utils.paths import cache_dir, config_file, data_dir, logs_dir, root_dir

_DEFAULT_CONFIG_TOML = """# Docent configuration
# Env vars (DOCENT_*) override these values.

default_model = "anthropic/claude-sonnet-4-6"
verbose = false
no_color = false

# anthropic_api_key = "sk-ant-..."
# openai_api_key = "sk-..."

[tools]
# Per-tool settings live here. Example:
# [tools.feynman]
# binary_path = "/usr/local/bin/feynman"
"""


def _ensure_runtime_dirs() -> None:
    for d in (root_dir(), cache_dir(), logs_dir(), data_dir()):
        d.mkdir(parents=True, exist_ok=True)


def _ensure_config_file() -> Path:
    path = config_file()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_DEFAULT_CONFIG_TOML, encoding="utf-8")
    return path


def load_settings() -> Settings:
    _ensure_runtime_dirs()
    path = _ensure_config_file()
    with path.open("rb") as f:
        toml_data = tomllib.load(f)
    return Settings(**toml_data)


def write_setting(key_path: str, value: Any) -> Path:
    """Persist a setting into config.toml under a dotted key path.

    `key_path` is a dotted path like "paper.database_dir". Sections are
    created on demand. Existing TOML structure is preserved (round-trip
    via tomllib + tomli_w). Returns the config-file path written.

    Use for one-off `config-set` style writes; not for bulk migration.
    """
    if not key_path or any(not seg for seg in key_path.split(".")):
        raise ValueError(f"Invalid setting key {key_path!r}")
    _ensure_runtime_dirs()
    path = _ensure_config_file()
    with path.open("rb") as f:
        data = tomllib.load(f)
    cursor: dict[str, Any] = data
    segments = key_path.split(".")
    for seg in segments[:-1]:
        next_cursor = cursor.get(seg)
        if not isinstance(next_cursor, dict):
            next_cursor = {}
            cursor[seg] = next_cursor
        cursor = next_cursor
    if value is None:
        cursor.pop(segments[-1], None)
    else:
        cursor[segments[-1]] = value
    with path.open("wb") as f:
        tomli_w.dump(data, f)
    return path

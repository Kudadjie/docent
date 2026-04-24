from __future__ import annotations

import tomllib
from pathlib import Path

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

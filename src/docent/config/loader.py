from __future__ import annotations

import hashlib
import os
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


# Memoized Settings, invalidated when the config file contents or any DOCENT_*
# env var change. The UI server dispatches every action through make_context ->
# load_settings; without this it re-read and re-parsed config.toml on every
# request. The cache key hashes the raw file bytes (not mtime — too coarse on
# filesystems with 1s granularity) plus the DOCENT_* env snapshot, so callers
# and tests that mutate either always get a fresh load. Reading the small TOML
# file is cheap; the cache exists to skip the tomllib parse + Pydantic
# validation, which is the actual cost.
_settings_cache: dict[str, Any] = {"key": None, "value": None}


def _env_snapshot() -> tuple:
    return tuple(sorted((k, v) for k, v in os.environ.items() if k.startswith("DOCENT_")))


def load_settings() -> Settings:
    """Load Docent settings with env-var-over-file priority.

    Priority (highest → lowest):
      1. Environment variables (``DOCENT_*``) — via Pydantic's env_settings source.
      2. ``~/.docent/config.toml`` — loaded here as explicit kwargs, fed to
         Pydantic's ``init_settings`` source.
      3. Model defaults declared on ``Settings`` / ``ResearchSettings`` / etc.

    Why TOML goes through init_settings instead of a custom Pydantic source:
    Pydantic Settings' ``settings_customise_sources`` lists ``env_settings``
    first, so env vars always win.  TOML data is passed as constructor kwargs,
    which Pydantic treats as ``init_settings`` — the second-highest priority.
    This keeps the implementation simple while preserving correct override order.

    Result is memoized (see ``_settings_cache``); the cache self-invalidates on
    config-file mtime or DOCENT_* env changes.
    """
    _ensure_runtime_dirs()
    path = _ensure_config_file()
    raw = path.read_bytes()
    key = (str(path), hashlib.sha256(raw).hexdigest(), _env_snapshot())
    if _settings_cache["value"] is not None and _settings_cache["key"] == key:
        return _settings_cache["value"]
    toml_data = tomllib.loads(raw.decode("utf-8"))
    settings = Settings(**toml_data)
    _settings_cache["key"] = key
    _settings_cache["value"] = settings
    return settings


_KNOWN_TOP_LEVEL_SECTIONS = frozenset(
    {
        "reading",
        "research",
        "tools",
        # Root-level scalar keys (no section prefix)
        "default_model",
        "verbose",
        "no_color",
        "anthropic_api_key",
        "openai_api_key",
    }
)


def write_setting(key_path: str, value: Any) -> Path:
    """Persist a setting into config.toml under a dotted key path.

    `key_path` is a dotted path like "reading.database_dir". Sections are
    created on demand. Existing TOML structure is preserved (round-trip
    via tomllib + tomli_w). Returns the config-file path written.

    Use for one-off `config-set` style writes; not for bulk migration.
    """
    if not key_path or any(not seg for seg in key_path.split(".")):
        raise ValueError(f"Invalid setting key {key_path!r}")
    top = key_path.split(".")[0]
    if top not in _KNOWN_TOP_LEVEL_SECTIONS:
        raise ValueError(
            f"Unknown config section {top!r}. Known sections: {sorted(_KNOWN_TOP_LEVEL_SECTIONS)}"
        )
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
    # Atomic write: write to a sibling temp file then rename to avoid corruption on crash.
    tmp = path.with_suffix(".toml.tmp")
    with tmp.open("wb") as f:
        tomli_w.dump(data, f)
    os.replace(tmp, path)
    return path

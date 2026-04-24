from __future__ import annotations

from pathlib import Path

_ROOT_ENV = "DOCENT_HOME"


def root_dir() -> Path:
    import os

    override = os.environ.get(_ROOT_ENV)
    return Path(override).expanduser() if override else Path.home() / ".docent"


def config_dir() -> Path:
    return root_dir()


def config_file() -> Path:
    return config_dir() / "config.toml"


def cache_dir() -> Path:
    return root_dir() / "cache"


def logs_dir() -> Path:
    return root_dir() / "logs"


def data_dir() -> Path:
    return root_dir() / "data"


def plugins_dir() -> Path:
    return root_dir() / "plugins"

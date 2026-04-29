from __future__ import annotations

import tomllib

import pytest

from docent.config import write_setting
from docent.utils.paths import config_file


def test_round_trip_simple_value(tmp_docent_home):
    path = write_setting("paper.database_dir", "/some/path")
    with path.open("rb") as f:
        data = tomllib.load(f)
    assert data["paper"]["database_dir"] == "/some/path"


def test_preserves_unrelated_keys(tmp_docent_home):
    write_setting("paper.database_dir", "/path-a")
    write_setting("paper.mendeley_watch_subdir", "Watch")
    write_setting("default_model", "openai/gpt-5")

    with config_file().open("rb") as f:
        data = tomllib.load(f)
    assert data["paper"]["database_dir"] == "/path-a"
    assert data["paper"]["mendeley_watch_subdir"] == "Watch"
    assert data["default_model"] == "openai/gpt-5"


def test_overwrites_existing_value(tmp_docent_home):
    write_setting("paper.database_dir", "/first")
    write_setting("paper.database_dir", "/second")
    with config_file().open("rb") as f:
        data = tomllib.load(f)
    assert data["paper"]["database_dir"] == "/second"


def test_invalid_key_rejected(tmp_docent_home):
    with pytest.raises(ValueError):
        write_setting("", "x")
    with pytest.raises(ValueError):
        write_setting("paper..database_dir", "x")
    with pytest.raises(ValueError):
        write_setting(".leading", "x")

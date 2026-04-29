"""Shared pytest fixtures for the Docent test suite.

Two cross-cutting concerns: redirect ~/.docent to a tmp dir so tests can't
touch the user's real config/data, and snapshot the global tool registry so
tests that call @register_tool don't leak into one another.
"""
from __future__ import annotations

import os

import pytest

from docent.core.registry import _REGISTRY


@pytest.fixture
def tmp_docent_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCENT_HOME", str(tmp_path))
    for key in list(os.environ):
        if key.startswith("DOCENT_") and key != "DOCENT_HOME":
            monkeypatch.delenv(key, raising=False)
    return tmp_path


@pytest.fixture
def isolated_registry():
    snapshot = dict(_REGISTRY)
    try:
        yield _REGISTRY
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(snapshot)

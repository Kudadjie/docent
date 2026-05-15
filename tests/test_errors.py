"""Tests for docent.errors — D-series codes and formatted() output."""
from __future__ import annotations

import pytest

from docent.errors import (
    AuthError,
    ConfigMissingError,
    DocentError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    SubprocessError,
    ToolNotFoundError,
    UsageLimitError,
)


def test_docent_error_has_code():
    err = DocentError("base error")
    assert err.code == "D000"
    assert str(err) == "base error"


def test_formatted_without_cause():
    err = ToolNotFoundError("feynman not found")
    assert err.formatted() == "[D002] feynman not found"


def test_formatted_with_cause_appends_it():
    cause = FileNotFoundError("no such file")
    err = ToolNotFoundError("feynman not found", cause=cause)
    result = err.formatted()
    assert "[D002]" in result
    assert "FileNotFoundError" in result
    assert "no such file" in result


def test_formatted_skips_cause_when_already_in_message():
    cause = ValueError("quota exceeded")
    err = UsageLimitError("quota exceeded — upgrade your plan", cause=cause)
    result = err.formatted()
    # cause text is already in the message — should NOT be duplicated
    assert result.count("quota exceeded") == 1


def test_all_subclass_codes():
    assert ConfigMissingError.code == "D001"
    assert ToolNotFoundError.code == "D002"
    assert AuthError.code == "D003"
    assert UsageLimitError.code == "D004"
    assert SubprocessError.code == "D005"
    assert ResourceNotFoundError.code == "D006"
    assert ServiceUnavailableError.code == "D007"


def test_docent_error_is_runtime_error():
    err = DocentError("oops")
    assert isinstance(err, RuntimeError)


def test_subclass_is_docent_error():
    from docent.bundled_plugins.studio import FeynmanNotFoundError, FeynmanBudgetExceededError
    assert issubclass(FeynmanNotFoundError, DocentError)
    assert issubclass(FeynmanBudgetExceededError, DocentError)
    assert FeynmanNotFoundError.code == "D002"
    assert FeynmanBudgetExceededError.code == "D004"


def test_oc_exceptions_are_docent_errors():
    from docent.bundled_plugins.studio.oc_client import (
        OcUnavailableError,
        OcBudgetExceededError,
        OcModelError,
    )
    assert issubclass(OcUnavailableError, DocentError)
    assert issubclass(OcBudgetExceededError, DocentError)
    assert issubclass(OcModelError, DocentError)
    assert OcUnavailableError.code == "D007"
    assert OcBudgetExceededError.code == "D004"
    assert OcModelError.code == "D003"


def test_oc_model_error_http_code():
    from docent.bundled_plugins.studio.oc_client import OcModelError
    err = OcModelError("rate limited", http_code=429)
    assert err.http_code == 429
    assert err.code == "D003"  # D-code unchanged

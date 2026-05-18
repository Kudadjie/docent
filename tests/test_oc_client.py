"""Tests for OcClient error handling and model checking."""
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

import docent.bundled_plugins.studio.oc_client as oc_mod
from docent.bundled_plugins.studio.oc_client import (
    OcClient,
    OcModelError,
    OcUnavailableError,
)


def test_call_returns_text():
    client = OcClient()
    mock_response = {"parts": [{"type": "text", "text": "ok"}]}
    with patch.object(client, "_api") as mock_api:
        mock_api.side_effect = [{"id": "sess1"}, mock_response]
        result = client.call("test prompt", model="glm-5.1")
    assert result == "ok"


def test_call_no_cost_field_still_succeeds():
    client = OcClient()
    mock_response = {"parts": [{"type": "text", "text": "hello"}]}
    with patch.object(client, "_api") as mock_api:
        mock_api.side_effect = [{"id": "sess1"}, mock_response]
        result = client.call("test prompt", model="glm-5.1")
    assert result == "hello"


# ── OcModelError — HTTP-level detection ────────────────────────────────────

def test_api_raises_model_error_on_429(monkeypatch):
    """HTTP 429 from the OpenCode server → OcModelError (not OcUnavailableError)."""
    client = OcClient()
    err = urllib.error.HTTPError(url="", code=429, msg="Too Many Requests", hdrs=None, fp=None)

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(OcModelError) as exc_info:
            client._api("GET", "/test")
    assert exc_info.value.http_code == 429
    assert "rate-limited" in str(exc_info.value).lower()


def test_api_raises_model_error_on_401(monkeypatch):
    """HTTP 401 → OcModelError with auth guidance."""
    client = OcClient()
    err = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=None)

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(OcModelError) as exc_info:
            client._api("GET", "/test")
    assert exc_info.value.http_code == 401
    assert "authentication" in str(exc_info.value).lower()


def test_api_raises_unavailable_on_500(monkeypatch):
    """HTTP 500 → OcUnavailableError (not a model quota error)."""
    import io
    client = OcClient()
    err = urllib.error.HTTPError(
        url="", code=500, msg="Server Error", hdrs=None,
        fp=io.BytesIO(b"internal error"),
    )

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(OcUnavailableError):
            client._api("GET", "/test")


# ── OcModelError — embedded model errors in 200 response body ──────────────

def test_call_raises_model_error_on_quota_in_response():
    """Response with error.message containing 'quota exceeded' → OcModelError."""
    client = OcClient()
    err_response = {
        "parts": [],
        "error": {"code": 429, "message": "RESOURCE_EXHAUSTED: quota exceeded for model"},
    }
    with patch.object(client, "_api") as mock_api:
        mock_api.side_effect = [{"id": "s"}, err_response]
        with pytest.raises(OcModelError) as exc_info:
            client.call("hi", model="glm-5.1")
    assert "quota" in str(exc_info.value).lower() or "exceeded" in str(exc_info.value).lower()


def test_call_raises_model_error_on_auth_in_response():
    """Response with auth error → OcModelError."""
    client = OcClient()
    err_response = {
        "parts": [],
        "error": {"code": 403, "message": "Forbidden: invalid API key"},
    }
    with patch.object(client, "_api") as mock_api:
        mock_api.side_effect = [{"id": "s"}, err_response]
        with pytest.raises(OcModelError) as exc_info:
            client.call("hi", model="glm-5.1")
    assert "authentication" in str(exc_info.value).lower()


def test_call_raises_model_error_on_generic_error_in_response():
    """Response with unrecognised error dict → OcModelError."""
    client = OcClient()
    err_response = {
        "parts": [],
        "error": {"code": 0, "message": "Model blew up"},
    }
    with patch.object(client, "_api") as mock_api:
        mock_api.side_effect = [{"id": "s"}, err_response]
        with pytest.raises(OcModelError):
            client.call("hi", model="glm-5.1")


# ── check_model() — pre-task usage limit gate ──────────────────────────────

def test_check_model_passes_and_caches(monkeypatch):
    """check_model() caches a successful result; second call skips the API."""
    import docent.bundled_plugins.studio.oc_client as oc_mod
    monkeypatch.setattr(oc_mod, "_model_check_cache", {})

    client = OcClient()
    good_response = {"parts": [{"type": "text", "text": "ok"}]}
    call_count = 0

    def fake_api(method, path, body=None, timeout=10):
        nonlocal call_count
        call_count += 1
        if "/session" in path and not path.endswith("/message"):
            return {"id": "s"}
        return good_response

    with patch.object(client, "_api", side_effect=fake_api):
        client.check_model("test-model")

    first_call_count = call_count
    # Second call should hit the cache and make NO new API calls.
    client2 = OcClient()
    with patch.object(client2, "_api", side_effect=fake_api):
        client2.check_model("test-model")

    assert call_count == first_call_count, "cached result should skip the API on second call"


def test_check_model_caches_failure_and_reraises(monkeypatch):
    """check_model() caches an OcModelError; second call re-raises without an API call."""
    import docent.bundled_plugins.studio.oc_client as oc_mod
    monkeypatch.setattr(oc_mod, "_model_check_cache", {})

    client = OcClient()
    err_response = {
        "parts": [],
        "error": {"code": 429, "message": "quota exceeded"},
    }

    def fake_api(method, path, body=None, timeout=10):
        if "/session" in path and not path.endswith("/message"):
            return {"id": "s"}
        return err_response

    with patch.object(client, "_api", side_effect=fake_api):
        with pytest.raises(OcModelError):
            client.check_model("bad-model")

    # Second call (different instance) should re-raise from cache, no API calls.
    client2 = OcClient()
    with patch.object(client2, "_api", side_effect=Exception("should not be called")):
        with pytest.raises(OcModelError, match="quota"):
            client2.check_model("bad-model")
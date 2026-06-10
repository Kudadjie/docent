"""Session-token guard for mutating web-UI API requests.

The Origin check blocks cross-site browser requests, but not requests from
other localhost origins or local processes. _SessionTokenGuard closes that:
once run_server() sets a token, every mutating /api/* request must carry it
in X-Docent-Token. Reads stay open; enforcement is off when no token is set
(the TestClient default), so the rest of the suite is unaffected.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from docent import ui_server


@pytest.fixture
def token_client():
    ui_server.set_session_token("test-token-123")
    try:
        yield TestClient(ui_server.app)
    finally:
        ui_server.set_session_token(None)


def test_mutating_request_without_token_is_rejected(token_client):
    resp = token_client.post("/api/tools/invoke", json={"tool": "x", "action": "run"})
    assert resp.status_code == 403
    assert "X-Docent-Token" in resp.json()["error"]


def test_mutating_request_with_wrong_token_is_rejected(token_client):
    resp = token_client.post(
        "/api/tools/invoke",
        json={"tool": "x", "action": "run"},
        headers={"X-Docent-Token": "wrong"},
    )
    assert resp.status_code == 403


def test_mutating_request_with_token_passes_guard(token_client):
    resp = token_client.post(
        "/api/tools/invoke",
        json={"tool": "nonexistent-tool", "action": "run"},
        headers={"X-Docent-Token": "test-token-123"},
    )
    # The guard lets it through; the route itself rejects the unknown tool.
    assert resp.status_code != 403


def test_get_requests_do_not_require_token(token_client):
    resp = token_client.get("/api/tooling")
    assert resp.status_code == 200


def test_auth_token_endpoint_returns_token(token_client):
    resp = token_client.get("/api/auth/token")
    assert resp.status_code == 200
    assert resp.json() == {"token": "test-token-123"}


def test_no_token_set_means_no_enforcement():
    assert ui_server.get_session_token() is None
    resp = TestClient(ui_server.app).post(
        "/api/tools/invoke", json={"tool": "nonexistent-tool", "action": "run"}
    )
    assert resp.status_code != 403

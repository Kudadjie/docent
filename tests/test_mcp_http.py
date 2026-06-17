"""Tests for MCP HTTP + SSE transport (mount_mcp_sse, _LocalhostGuard exemption)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Populate registry before building the MCP server.
from reading import ReadingQueue  # noqa: F401

from docent.mcp_server import mount_mcp_sse

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

API_KEY = "test-secret-key-abc123"


@pytest.fixture(scope="module")
def mcp_app() -> FastAPI:
    """Minimal FastAPI app with MCP SSE transport mounted."""
    app = FastAPI()
    mount_mcp_sse(app, API_KEY)
    return app


@pytest.fixture(scope="module")
def client(mcp_app: FastAPI) -> TestClient:
    return TestClient(mcp_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


def test_sse_no_key_returns_401(client: TestClient) -> None:
    resp = client.get("/mcp/sse")
    assert resp.status_code == 401


def test_sse_wrong_key_returns_401(client: TestClient) -> None:
    resp = client.get("/mcp/sse", headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 401


def test_post_messages_no_key_returns_401(client: TestClient) -> None:
    resp = client.post("/mcp/messages/")
    assert resp.status_code == 401


def test_post_messages_wrong_key_returns_401(client: TestClient) -> None:
    resp = client.post("/mcp/messages/", headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Routes exist (correct key doesn't 404)
# ---------------------------------------------------------------------------


def test_sse_with_correct_key_not_404(client: TestClient) -> None:
    # SSE streams indefinitely — the test client will get a non-404 response
    # (likely 200 with streaming or a disconnect, not 404/401).
    resp = client.get("/mcp/sse", headers={"Authorization": f"Bearer {API_KEY}"})
    assert resp.status_code != 404
    assert resp.status_code != 401


def test_post_messages_with_correct_key_not_404(client: TestClient) -> None:
    resp = client.post("/mcp/messages/", headers={"Authorization": f"Bearer {API_KEY}"})
    assert resp.status_code != 404
    assert resp.status_code != 401


# ---------------------------------------------------------------------------
# LocalhostGuard exemption
# ---------------------------------------------------------------------------


def test_mcp_routes_exempt_from_localhost_guard() -> None:
    """Non-localhost Origin must be allowed on /mcp/* but blocked on other routes."""
    from docent.ui_server import _is_localhost_origin, _LocalhostGuard

    # Verify that a non-localhost origin would normally be rejected.
    assert not _is_localhost_origin("http://evil.example.com")

    # The guard exempts /mcp/* — test via a fresh app with the middleware.
    app = FastAPI()
    app.add_middleware(_LocalhostGuard)
    mount_mcp_sse(app, API_KEY)

    @app.get("/ui/check")
    async def ui_check() -> dict:
        return {"ok": True}

    c = TestClient(app, raise_server_exceptions=False)

    # /mcp/sse from a non-localhost Origin → passes guard (still needs API key)
    resp = c.get("/mcp/sse", headers={"Origin": "http://evil.example.com"})
    assert resp.status_code != 403  # guard did not block it

    # /ui/check from a non-localhost Origin → blocked by guard
    resp = c.get("/ui/check", headers={"Origin": "http://evil.example.com"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# ServeSettings
# ---------------------------------------------------------------------------


def test_serve_settings_defaults() -> None:
    from docent.config.settings import ServeSettings

    s = ServeSettings()
    assert s.api_key is None
    assert s.host == "127.0.0.1"
    assert s.http_mcp_enabled is True


def test_check_mcp_http_no_key() -> None:
    from docent.cli_doctor import _check_mcp_http
    from docent.config.settings import ServeSettings, Settings

    settings = Settings(serve=ServeSettings(api_key=None))
    label, status, _, detail = _check_mcp_http(settings)
    assert label == "MCP HTTP"
    assert status == "WARN"
    assert "api_key" in detail.lower() or "key" in detail.lower()


def test_check_mcp_http_key_set() -> None:
    from docent.cli_doctor import _check_mcp_http
    from docent.config.settings import ServeSettings, Settings

    settings = Settings(serve=ServeSettings(api_key="some-key"))
    label, status, _, _ = _check_mcp_http(settings)
    assert label == "MCP HTTP"
    assert status == "OK"


def test_check_mcp_http_disabled() -> None:
    from docent.cli_doctor import _check_mcp_http
    from docent.config.settings import ServeSettings, Settings

    settings = Settings(serve=ServeSettings(http_mcp_enabled=False))
    label, status, _, _ = _check_mcp_http(settings)
    assert label == "MCP HTTP"
    assert status == "SKIP"

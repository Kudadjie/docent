"""Cross-origin policy for the local UI server (HTTP guard)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from docent import ui_server
from docent.ui_routes._shared import _is_localhost_origin


class TestOriginHelper:
    def test_empty_origin_allowed(self):
        # Non-browser clients (curl, local tooling) send no Origin.
        assert _is_localhost_origin("") is True

    @pytest.mark.parametrize(
        "origin",
        [
            "http://localhost",
            "http://localhost:7432",
            "http://127.0.0.1:7432",
            "https://localhost",  # user's own machine — scheme is not the threat
            "http://[::1]:7432",
        ],
    )
    def test_localhost_allowed(self, origin):
        assert _is_localhost_origin(origin) is True

    @pytest.mark.parametrize(
        "origin",
        [
            "http://evil.com",
            "http://localhost.evil.com",  # the prefix-match bypass this fix closes
            "http://127.0.0.1.evil.com",
            "ftp://localhost",
        ],
    )
    def test_foreign_origin_rejected(self, origin):
        assert _is_localhost_origin(origin) is False


class TestHttpGuard:
    def test_foreign_origin_gets_403(self):
        resp = TestClient(ui_server.app).get("/api/tooling", headers={"origin": "http://evil.com"})
        assert resp.status_code == 403

    def test_no_origin_passes_guard(self):
        # Should not be blocked by the guard (may 200 or fail downstream, but never 403).
        resp = TestClient(ui_server.app).get("/api/version")
        assert resp.status_code != 403

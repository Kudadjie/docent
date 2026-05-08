"""Tests for packaged UI tooling endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from docent import ui_server


def test_tooling_endpoint_reports_npm_tool_versions(monkeypatch):
    async def fake_installed(package: str) -> str | None:
        assert package == "@companion-ai/feynman"
        return "1.2.3"

    async def fake_latest(package: str) -> str | None:
        assert package == "@companion-ai/feynman"
        return "1.2.4"

    monkeypatch.setattr(ui_server, "_get_npm_installed", fake_installed)
    monkeypatch.setattr(ui_server, "_fetch_npm_latest", fake_latest)

    response = TestClient(ui_server.app).get("/api/tooling")

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "@companion-ai/feynman",
            "label": "Feynman",
            "installed": "1.2.3",
            "latest": "1.2.4",
            "up_to_date": False,
            "upgrade_cmd": "npm install -g @companion-ai/feynman",
        }
    ]


def test_tooling_endpoint_marks_matching_version_current(monkeypatch):
    async def fake_installed(package: str) -> str | None:
        return "1.2"

    async def fake_latest(package: str) -> str | None:
        return "1.2.0"

    monkeypatch.setattr(ui_server, "_get_npm_installed", fake_installed)
    monkeypatch.setattr(ui_server, "_fetch_npm_latest", fake_latest)

    response = TestClient(ui_server.app).get("/api/tooling")

    assert response.status_code == 200
    assert response.json()[0]["up_to_date"] is True

"""Tests for packaged UI tooling endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

import docent.ui_routes.doctor as _doctor_mod
from docent import ui_server
from docent.ui_routes import _studio_request as studio_request


def test_tooling_endpoint_reports_npm_tool_versions(monkeypatch):
    async def fake_installed(package: str) -> str | None:
        assert package == "@companion-ai/feynman"
        return "1.2.3"

    async def fake_latest(package: str) -> str | None:
        assert package == "@companion-ai/feynman"
        return "1.2.4"

    monkeypatch.setattr(_doctor_mod, "_get_npm_installed", fake_installed)
    monkeypatch.setattr(_doctor_mod, "_fetch_npm_latest", fake_latest)

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

    monkeypatch.setattr(_doctor_mod, "_get_npm_installed", fake_installed)
    monkeypatch.setattr(_doctor_mod, "_fetch_npm_latest", fake_latest)

    response = TestClient(ui_server.app).get("/api/tooling")

    assert response.status_code == 200
    assert response.json()[0]["up_to_date"] is True


# --- studio request builder: the confirmed gate ---------------------------
# Regression for the Studio UI "draft" crash: the builder used to emit
# confirmed=True for draft, but DraftInputs has no such field (draft is
# AI-backend-only and skips the free-tier disclaimer), so input validation
# rejected it. Only deep/lit may carry it. The subprocess argv renderer this
# guarded against drifting from was deleted with the WS transport (v2.3) —
# build_studio_request kwargs are now the only rendering.


def test_builder_confirmed_only_for_deep_and_lit():
    cases = {"draft": False, "deep": True, "lit": True}
    for action_id, want_confirmed in cases.items():
        body = studio_request.StudioRunBody(
            action_id=action_id, topic="X", backend="free", dest="local"
        )
        _action, args = studio_request._parse_studio_body(body)
        assert ("confirmed" in args) is want_confirmed


def test_build_studio_request_maps_every_action_id():
    for action_id in studio_request._STUDIO_ACTION_MAP:
        body = studio_request.StudioRunBody(
            action_id=action_id, topic="X", backend="free", dest="local"
        )
        req = studio_request.build_studio_request(body)
        assert req is not None, action_id
        assert req.action == studio_request._STUDIO_ACTION_MAP[action_id]


def test_build_studio_request_unknown_action_returns_none():
    body = studio_request.StudioRunBody(action_id="does-not-exist")
    assert studio_request.build_studio_request(body) is None

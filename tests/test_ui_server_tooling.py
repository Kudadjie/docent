"""Tests for packaged UI tooling endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from docent import ui_server
import docent.ui_routes.doctor as _doctor_mod


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


# --- studio command builders: the --confirmed gate ------------------------
# Regression for the Studio UI "draft" crash: both the subprocess builder
# (_build_studio_cmd) and the in-process builder (_parse_studio_body) used to
# emit --confirmed for draft, but DraftInputs has no such field (draft is
# AI-backend-only and skips the free-tier disclaimer), so Click rejected the
# command with "No such option '--confirmed'". Only deep/lit may carry it.

def test_subprocess_builder_omits_confirmed_for_draft(monkeypatch):
    import docent.ui_routes.opencode as oc

    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/docent")
    body = oc.StudioRunBody(action_id="draft", topic="X", backend="free", dest="local")
    cmd = oc._build_studio_cmd(body)
    assert cmd is not None
    assert "--confirmed" not in cmd


def test_subprocess_builder_keeps_confirmed_for_deep_and_lit(monkeypatch):
    import docent.ui_routes.opencode as oc

    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/docent")
    for action_id in ("deep", "lit"):
        body = oc.StudioRunBody(action_id=action_id, topic="X", backend="free", dest="local")
        cmd = oc._build_studio_cmd(body)
        assert cmd is not None
        assert "--confirmed" in cmd


def test_inprocess_builder_confirmed_only_for_deep_and_lit():
    cases = {"draft": False, "deep": True, "lit": True}
    for action_id, want_confirmed in cases.items():
        body = ui_server.StudioRunBody(action_id=action_id, topic="X", backend="free", dest="local")
        _action, args = ui_server._parse_studio_body(body)
        assert ("confirmed" in args) is want_confirmed

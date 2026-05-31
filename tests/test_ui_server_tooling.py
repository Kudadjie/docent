"""Tests for packaged UI tooling endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

import docent.ui_routes.doctor as _doctor_mod
from docent import ui_server


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


# --- unification guard: both surfaces render from ONE source of truth ---------
# build_studio_request is the single builder; _parse_studio_body (in-process)
# and _build_studio_cmd (subprocess) are thin renderers over it. These tests
# lock that in so the two surfaces can never drift again (the original class of
# bug: an arg added to one builder but not the other).

_ALL_ACTION_IDS = list(ui_server._STUDIO_ACTION_MAP)


def test_both_builders_agree_on_confirmed_gate(monkeypatch):
    """The in-process kwargs and the CLI argv must agree on --confirmed for
    every action — not just deep/lit by happy coincidence."""
    import docent.ui_routes.opencode as oc

    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/docent")
    for action_id in _ALL_ACTION_IDS:
        body = ui_server.StudioRunBody(action_id=action_id, topic="X", backend="free", dest="local")
        parsed = ui_server._parse_studio_body(body)
        cmd = oc._build_studio_cmd(body)
        assert parsed is not None and cmd is not None
        kwargs_has_confirmed = "confirmed" in parsed[1]
        argv_has_confirmed = "--confirmed" in cmd
        assert kwargs_has_confirmed == argv_has_confirmed, action_id


def test_build_studio_request_unknown_action_returns_none():
    body = ui_server.StudioRunBody(action_id="does-not-exist")
    assert ui_server.build_studio_request(body) is None


def test_subprocess_cmd_renders_request_argv(monkeypatch):
    """_build_studio_cmd is just `docent studio <action>` + the shared argv."""
    import docent.ui_routes.opencode as oc

    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/docent")
    body = ui_server.StudioRunBody(
        action_id="lit", topic="reefs", backend="free", dest="local", expand_citations=True
    )
    req = ui_server.build_studio_request(body)
    cmd = oc._build_studio_cmd(body)
    assert cmd == ["/usr/bin/docent", "studio", req.action, *req.argv]
    # spot-check the lit-specific flags survive the round-trip
    assert "--confirmed" in cmd and "--expand-citations" in cmd

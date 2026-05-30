"""Tests for the generic /api/tools introspection + invocation endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

# Importing the bundled tools triggers @register_tool, populating the registry
# that /api/tools introspects.
from reading import ReadingQueue  # noqa: F401
import studio  # noqa: F401

from docent import ui_server


def _client() -> TestClient:
    return TestClient(ui_server.app)


def test_list_tools_includes_reading_and_studio():
    resp = _client().get("/api/tools")
    assert resp.status_code == 200
    cat = resp.json()
    names = {t["tool"] for t in cat}
    assert {"reading", "studio"} <= names


def test_list_tools_exposes_action_schemas():
    cat = _client().get("/api/tools").json()
    reading = next(t for t in cat if t["tool"] == "reading")
    search = next(a for a in reading["actions"] if a["action"] == "search")
    # The JSON schema is passed through untouched from model_json_schema().
    assert "query" in search["schema"]["properties"]
    assert search["schema"]["required"] == ["query"]


def test_single_action_tool_uses_run(monkeypatch):
    # Register a throwaway single-action tool and confirm it surfaces as "run".
    from pydantic import BaseModel
    from docent.core.registry import register_tool, _REGISTRY
    from docent.core.tool import Tool

    class PingInputs(BaseModel):
        host: str

    @register_tool
    class _Ping(Tool):
        name = "pingtest"
        description = "Ping a host."
        input_schema = PingInputs

        def run(self, inputs, context):  # noqa: ANN001
            return {"pong": inputs.host}

    try:
        cat = _client().get("/api/tools").json()
        ping = next(t for t in cat if t["tool"] == "pingtest")
        assert [a["action"] for a in ping["actions"]] == ["run"]
    finally:
        _REGISTRY.pop("pingtest", None)


def test_invoke_read_only_action_succeeds(tmp_docent_home):
    resp = _client().post("/api/tools/invoke", json={
        "tool": "reading", "action": "stats", "inputs": {},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert isinstance(body["result"], dict)


def test_invoke_unknown_tool_returns_400():
    resp = _client().post("/api/tools/invoke", json={
        "tool": "nope", "action": "run", "inputs": {},
    })
    assert resp.status_code == 400
    assert resp.json()["ok"] is False


def test_invoke_missing_required_field_returns_400(tmp_docent_home):
    # reading.show requires `id`; omitting it must fail validation, not 500.
    resp = _client().post("/api/tools/invoke", json={
        "tool": "reading", "action": "show", "inputs": {},
    })
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]


def test_invoke_action_that_calls_asyncio_run_succeeds():
    """Regression: actions that call asyncio.run() internally (e.g. the Mendeley
    overlay on reading.search) must not blow up with 'asyncio.run() cannot be
    called from a running event loop'. The route runs them in a worker thread.
    """
    import asyncio
    from pydantic import BaseModel
    from docent.core.registry import register_tool, _REGISTRY
    from docent.core.tool import Tool, action

    class _Inp(BaseModel):
        pass

    @register_tool
    class _AsyncRunner(Tool):
        name = "asyncruntest"
        description = "Calls asyncio.run inside the action."

        @action(description="Run a coroutine via asyncio.run.", input_schema=_Inp)
        def go(self, inputs, context):  # noqa: ANN001
            async def _coro():
                return "ran"
            return {"value": asyncio.run(_coro())}

    try:
        resp = _client().post("/api/tools/invoke", json={
            "tool": "asyncruntest", "action": "go", "inputs": {},
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["result"]["value"] == "ran"
    finally:
        _REGISTRY.pop("asyncruntest", None)

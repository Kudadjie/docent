"""Tests for the generic /api/tools introspection + invocation endpoints."""

from __future__ import annotations

import studio  # noqa: F401
from fastapi.testclient import TestClient

# Importing the bundled tools triggers @register_tool, populating the registry
# that /api/tools introspects.
from reading import ReadingQueue  # noqa: F401

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

    from docent.core.registry import _REGISTRY, register_tool
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
    resp = _client().post(
        "/api/tools/invoke",
        json={
            "tool": "reading",
            "action": "stats",
            "inputs": {},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert isinstance(body["result"], dict)


def test_invoke_unknown_tool_returns_400():
    resp = _client().post(
        "/api/tools/invoke",
        json={
            "tool": "nope",
            "action": "run",
            "inputs": {},
        },
    )
    assert resp.status_code == 400
    assert resp.json()["ok"] is False


def test_invoke_missing_required_field_returns_400(tmp_docent_home):
    # reading.show requires `id`; omitting it must fail validation, not 500.
    resp = _client().post(
        "/api/tools/invoke",
        json={
            "tool": "reading",
            "action": "show",
            "inputs": {},
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]


def _parse_sse(body: str) -> list[dict]:
    """Parse a raw SSE response body into a list of decoded event dicts."""
    import json as _json

    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(_json.loads(line[6:]))
    return events


def test_stream_sync_action_emits_result_event(tmp_docent_home):
    """Non-generator actions emit a single result event with no progress events."""
    resp = _client().post(
        "/api/tools/stream",
        json={"tool": "reading", "action": "stats", "inputs": {}},
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events, "Expected at least one SSE event"
    assert events[-1]["type"] == "result"
    assert events[-1]["ok"] is True
    # No progress events for a sync action.
    assert all(e["type"] != "progress" for e in events[:-1])


def test_stream_generator_action_emits_progress_then_result(tmp_docent_home):
    """Generator actions emit ProgressEvent rows before the final result event."""
    from pydantic import BaseModel

    from docent.core.events import ProgressEvent
    from docent.core.registry import _REGISTRY, register_tool
    from docent.core.tool import Tool, action

    class _Inp(BaseModel):
        pass

    @register_tool
    class _Streamer(Tool):
        name = "streamertest"
        description = "Yields progress then returns."

        @action(description="Stream two progress events.", input_schema=_Inp)
        def go(self, inputs, context):  # noqa: ANN001
            yield ProgressEvent(phase="alpha", message="step 1")
            yield ProgressEvent(phase="beta", message="step 2", level="warn")
            return {"done": True}

    try:
        resp = _client().post(
            "/api/tools/stream",
            json={"tool": "streamertest", "action": "go", "inputs": {}},
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        progress = [e for e in events if e["type"] == "progress"]
        results = [e for e in events if e["type"] == "result"]
        assert len(progress) == 2
        assert progress[0]["phase"] == "alpha"
        assert progress[0]["message"] == "step 1"
        assert progress[0]["level"] == "info"
        assert progress[1]["phase"] == "beta"
        assert progress[1]["level"] == "warn"
        assert len(results) == 1
        assert results[0]["ok"] is True
        assert results[0]["result"]["done"] is True
    finally:
        _REGISTRY.pop("streamertest", None)


def test_stream_unknown_tool_emits_error_event():
    resp = _client().post(
        "/api/tools/stream",
        json={"tool": "nope", "action": "run", "inputs": {}},
    )
    assert resp.status_code == 200  # HTTP level is always 200 for SSE
    events = _parse_sse(resp.text)
    assert events[-1]["type"] == "error"
    assert events[-1]["ok"] is False
    assert events[-1]["error"]


def test_stream_missing_required_field_emits_error_event(tmp_docent_home):
    resp = _client().post(
        "/api/tools/stream",
        json={"tool": "reading", "action": "show", "inputs": {}},
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events[-1]["type"] == "error"
    assert events[-1]["ok"] is False


def test_stream_result_includes_shapes_when_result_implements_to_shapes():
    """Result events must include a ``shapes`` list when the result has to_shapes()."""
    from pydantic import BaseModel

    from docent.core.registry import _REGISTRY, register_tool
    from docent.core.shapes import MessageShape, MetricShape
    from docent.core.tool import Tool, action

    class _Inp(BaseModel):
        pass

    class _Result(BaseModel):
        value: int

        def to_shapes(self):  # noqa: ANN201
            return [
                MetricShape(label="value", value=self.value, unit="items"),
                MessageShape(text="all good", level="success"),
            ]

    @register_tool
    class _ShapeTool(Tool):
        name = "shapetest"
        description = "Returns a result with to_shapes()."

        @action(description="Return a shaped result.", input_schema=_Inp)
        def go(self, inputs, context):  # noqa: ANN001
            return _Result(value=42)

    try:
        resp = _client().post(
            "/api/tools/stream",
            json={"tool": "shapetest", "action": "go", "inputs": {}},
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        result_evt = next(e for e in events if e["type"] == "result")
        assert result_evt["ok"] is True
        shapes = result_evt.get("shapes")
        assert isinstance(shapes, list), "shapes field must be a list"
        assert len(shapes) == 2
        assert shapes[0]["type"] == "metric"
        assert shapes[0]["label"] == "value"
        assert shapes[0]["value"] == 42
        assert shapes[0]["unit"] == "items"
        assert shapes[1]["type"] == "message"
        assert shapes[1]["level"] == "success"
    finally:
        _REGISTRY.pop("shapetest", None)


def test_stream_result_omits_shapes_when_result_has_no_to_shapes():
    """Result events must NOT include a ``shapes`` key for plain dict results."""
    from pydantic import BaseModel

    from docent.core.registry import _REGISTRY, register_tool
    from docent.core.tool import Tool, action

    class _Inp(BaseModel):
        pass

    @register_tool
    class _PlainTool(Tool):
        name = "plaintest"
        description = "Returns a plain dict with no to_shapes."

        @action(description="Return a plain dict.", input_schema=_Inp)
        def go(self, inputs, context):  # noqa: ANN001
            return {"x": 1}

    try:
        resp = _client().post(
            "/api/tools/stream",
            json={"tool": "plaintest", "action": "go", "inputs": {}},
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        result_evt = next(e for e in events if e["type"] == "result")
        assert "shapes" not in result_evt
    finally:
        _REGISTRY.pop("plaintest", None)


def test_invoke_action_that_calls_asyncio_run_succeeds():
    """Regression: actions that call asyncio.run() internally (e.g. the Mendeley
    overlay on reading.search) must not blow up with 'asyncio.run() cannot be
    called from a running event loop'. The route runs them in a worker thread.
    """
    import asyncio

    from pydantic import BaseModel

    from docent.core.registry import _REGISTRY, register_tool
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
        resp = _client().post(
            "/api/tools/invoke",
            json={
                "tool": "asyncruntest",
                "action": "go",
                "inputs": {},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["result"]["value"] == "ran"
    finally:
        _REGISTRY.pop("asyncruntest", None)

"""JobManager (core.jobs) + jobs tool + MCP async routing + /api/jobs routes."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest
from pydantic import BaseModel, Field

import docent.core.jobs as jobs_mod
import docent.core.registry as reg_mod
from docent.core import Context, Tool, action, register_tool
from docent.core.jobs import JobManager, JobNotFoundError, JobRecord

# ── fixture tool ──────────────────────────────────────────────────────────────


class _JobFixInputs(BaseModel):
    n: int = Field(3, description="Number of progress events to emit.")
    fail: bool = Field(False, description="Raise instead of returning.")
    slow: bool = Field(False, description="Sleep between events (cancellation window).")


class _JobFixResult(BaseModel):
    ok: bool = Field(True, description="Whether the run succeeded.")
    total: int = Field(..., description="Events emitted.")


@pytest.fixture
def jobfix_tool():
    """Register a throwaway generator tool; remove it from the registry after."""
    from docent.core.events import ProgressEvent

    @register_tool
    class JobFix(Tool):
        name = "jobfix-xyz"
        description = "Test fixture for the job manager."

        @action(description="Emit N progress events then return.", input_schema=_JobFixInputs)
        def emit(self, inputs: _JobFixInputs, context: Context):
            def gen():
                for i in range(inputs.n):
                    if inputs.slow:
                        time.sleep(0.05)
                    yield ProgressEvent(phase="work", message=f"step {i + 1}")
                if inputs.fail:
                    raise RuntimeError("boom")
                return _JobFixResult(total=inputs.n)

            return gen()

    yield "jobfix-xyz"
    reg_mod._REGISTRY.pop("jobfix-xyz", None)


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """Isolated JobManager wired in as the process singleton."""
    mgr = JobManager(jobs_dir=tmp_path / "jobs")
    monkeypatch.setattr(jobs_mod, "_manager", mgr)
    return mgr


@pytest.fixture
def jobs_registered():
    """Ensure the shipped `jobs` tool is in the registry.

    Importing the module registers it; if another test cleared the registry
    while the module stayed cached, re-insert the class directly.
    """
    import docent.tools.jobs as jobs_tool_mod

    if "jobs" not in reg_mod._REGISTRY:
        reg_mod._REGISTRY["jobs"] = jobs_tool_mod.JobsTool
    yield


def _wait(mgr: JobManager, job_id: str, timeout: float = 10.0) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = mgr.get(job_id)
        if job.state not in ("queued", "running"):
            return job
        time.sleep(0.02)
    pytest.fail(f"job {job_id} still {mgr.get(job_id).state} after {timeout}s")


# ── manager core ──────────────────────────────────────────────────────────────


def test_submit_runs_to_done_with_events_and_result(manager, jobfix_tool):
    job = manager.submit(jobfix_tool, "emit", {"n": 3})
    finished = _wait(manager, job.id)
    assert finished.state == "done"
    assert [e["message"] for e in finished.events] == ["step 1", "step 2", "step 3"]
    assert json.loads(finished.result_json) == {"ok": True, "total": 3}
    assert finished.started and finished.finished


def test_failing_action_marks_job_failed(manager, jobfix_tool):
    job = manager.submit(jobfix_tool, "emit", {"n": 1, "fail": True})
    finished = _wait(manager, job.id)
    assert finished.state == "failed"
    assert "boom" in finished.error


def test_job_record_persists_to_disk(manager, jobfix_tool, tmp_path):
    job = manager.submit(jobfix_tool, "emit", {"n": 1})
    _wait(manager, job.id)
    on_disk = json.loads((tmp_path / "jobs" / f"{job.id}.json").read_text(encoding="utf-8"))
    assert on_disk["state"] == "done"


def test_cancel_running_job_stops_between_events(manager, jobfix_tool):
    job = manager.submit(jobfix_tool, "emit", {"n": 200, "slow": True})
    # Let it start, then cancel.
    time.sleep(0.15)
    manager.cancel(job.id)
    finished = _wait(manager, job.id)
    assert finished.state == "cancelled"
    assert len(finished.events) < 200


def test_unknown_job_raises(manager):
    with pytest.raises(JobNotFoundError):
        manager.get("job-nope")


def test_active_records_marked_interrupted_on_load(tmp_path):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    stale = JobRecord(id="job-stale00001", tool="t", action="a", state="running")
    (jobs_dir / f"{stale.id}.json").write_text(stale.model_dump_json(), encoding="utf-8")

    mgr = JobManager(jobs_dir=jobs_dir)
    assert mgr.get("job-stale00001").state == "interrupted"


def test_retention_prunes_oldest_beyond_limit(tmp_path):
    mgr = JobManager(jobs_dir=tmp_path / "jobs")
    for i in range(jobs_mod.RETENTION + 5):
        rec = JobRecord(
            id=f"job-r{i:09d}",
            tool="t",
            action="a",
            state="done",
            created=f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00",
        )
        mgr._jobs[rec.id] = rec
        mgr._persist(rec)
    mgr._prune()
    assert len(mgr._jobs) == jobs_mod.RETENTION
    assert "job-r000000000" not in mgr._jobs  # oldest pruned
    assert len(list((tmp_path / "jobs").glob("job-*.json"))) == jobs_mod.RETENTION


# ── jobs tool ─────────────────────────────────────────────────────────────────


def test_jobs_tool_status_result_list(manager, jobfix_tool, jobs_registered):
    from docent.core.invoke import run_action

    job = manager.submit(jobfix_tool, "emit", {"n": 2})
    _wait(manager, job.id)

    status = run_action("jobs", "status", {"id": job.id})
    assert status.job["state"] == "done"
    assert "result" in status.hint

    result = run_action("jobs", "result", {"id": job.id})
    assert result.ok is True
    assert result.result == {"ok": True, "total": 2}

    listing = run_action("jobs", "list", {})
    assert any(j["id"] == job.id for j in listing.jobs)


def test_jobs_tool_result_before_done_reports_state(manager, jobfix_tool, jobs_registered):
    from docent.core.invoke import run_action

    job = manager.submit(jobfix_tool, "emit", {"n": 200, "slow": True})
    res = run_action("jobs", "result", {"id": job.id})
    assert res.ok is False
    assert res.state in ("queued", "running")
    manager.cancel(job.id)
    _wait(manager, job.id)


def test_jobs_tool_unknown_id_is_docent_error(manager, jobs_registered):
    from docent.core.invoke import run_action
    from docent.errors import ResourceNotFoundError

    with pytest.raises(ResourceNotFoundError, match="jobs list"):
        run_action("jobs", "status", {"id": "job-nope"})


# ── MCP async routing ─────────────────────────────────────────────────────────


def test_should_run_async_table():
    from docent.mcp_server import _should_run_async

    assert _should_run_async("studio", "deep-research", {"backend": "feynman"})
    assert _should_run_async("studio", "lit", {"backend": "groq"})
    assert _should_run_async("studio", "to-notebook", {})
    assert not _should_run_async("studio", "deep-research", {"backend": "free"})
    assert not _should_run_async("studio", "search-papers", {})
    assert not _should_run_async("reading", "show", {})


def test_mcp_invoke_submits_async_job(manager, jobfix_tool, monkeypatch):
    import docent.mcp_server as mcp

    monkeypatch.setattr(mcp, "_ASYNC_ACTIONS", frozenset({(jobfix_tool, "emit")}))
    payload = json.loads(mcp.invoke_action(jobfix_tool, "emit", {"n": 2}))
    assert payload["async"] is True
    assert payload["job_id"].startswith("job-")
    assert "jobs__status" in payload["message"]

    finished = _wait(manager, payload["job_id"])
    assert finished.state == "done"


# ── /api/jobs routes ──────────────────────────────────────────────────────────


def test_api_jobs_routes(manager, jobfix_tool):
    from fastapi.testclient import TestClient

    from docent.ui_server import app

    client = TestClient(app)
    job = manager.submit(jobfix_tool, "emit", {"n": 2})
    _wait(manager, job.id)

    listing = client.get("/api/jobs")
    assert listing.status_code == 200
    assert any(j["id"] == job.id for j in listing.json()["jobs"])

    detail = client.get(f"/api/jobs/{job.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["state"] == "done"
    assert len(body["events"]) == 2
    assert json.loads(body["result_json"]) == {"ok": True, "total": 2}

    assert client.get("/api/jobs/job-nope").status_code == 404

    slow = manager.submit(jobfix_tool, "emit", {"n": 200, "slow": True})
    cancel = client.post(f"/api/jobs/{slow.id}/cancel")
    assert cancel.status_code == 200
    assert _wait(manager, slow.id).state == "cancelled"

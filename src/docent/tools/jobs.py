"""Background-job inspection tool — poll, fetch, and cancel long-running jobs.

Long studio actions invoked over MCP are submitted as background jobs (see
``docent.core.jobs``); this tool is how callers follow up:

    docent jobs status --id job-abc123
    docent jobs result --id job-abc123
    docent jobs cancel --id job-abc123
    docent jobs list

Over MCP the same actions are ``jobs__status`` / ``jobs__result`` /
``jobs__cancel`` / ``jobs__list``.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from docent.core import Context, Tool, action, register_tool
from docent.core.jobs import JobNotFoundError, get_job_manager
from docent.errors import ResourceNotFoundError


class JobIdInputs(BaseModel):
    id: str = Field(..., description="Job id returned at submission (e.g. 'job-1a2b3c4d5e').")


class JobListInputs(BaseModel):
    limit: int = Field(default=20, description="Maximum number of jobs to list, newest first.")


class JobStatusResult(BaseModel):
    ok: bool = Field(default=True, description="Whether the lookup succeeded.")
    job: dict[str, Any] = Field(
        ..., description="Job summary: state, timestamps, recent progress events, error if any."
    )
    hint: str = Field(default="", description="What to do next given the job's state.")


class JobResultResult(BaseModel):
    ok: bool = Field(..., description="True when the job finished successfully.")
    state: str = Field(..., description="Final (or current) job state.")
    result: Any = Field(
        default=None,
        description="The action's result payload (parsed JSON) when state is 'done'.",
    )
    error: str | None = Field(default=None, description="Failure reason when state is not 'done'.")


class JobListResult(BaseModel):
    ok: bool = Field(default=True, description="Whether the listing succeeded.")
    jobs: list[dict[str, Any]] = Field(
        ..., description="Job summaries, newest first (state, timestamps, event counts)."
    )


_STATE_HINTS = {
    "queued": "Waiting for a slot. Poll jobs status again in ~30 seconds.",
    "running": "In progress. Poll jobs status again in 30-60 seconds.",
    "done": "Finished. Call jobs result with this id to fetch the output.",
    "failed": "Failed — see the error field. Rerun the original action to retry.",
    "cancelled": "Cancelled. Rerun the original action to retry.",
    "interrupted": "The Docent process exited mid-run. Rerun the original action.",
}


def _lookup(job_id: str) -> Any:
    try:
        return get_job_manager().get(job_id)
    except JobNotFoundError:
        raise ResourceNotFoundError(
            f"No job '{job_id}'. It may have been pruned (only the last 50 are kept) — "
            "run 'docent jobs list' to see current jobs."
        ) from None


@register_tool
class JobsTool(Tool):
    name = "jobs"
    description = "Inspect, fetch results from, and cancel background jobs."
    category = "core"

    @action(
        description="Show a background job's state and recent progress events.",
        input_schema=JobIdInputs,
    )
    def status(self, inputs: JobIdInputs, context: Context) -> JobStatusResult:
        job = _lookup(inputs.id)
        return JobStatusResult(
            job=job.public_summary(),
            hint=_STATE_HINTS.get(job.state, ""),
        )

    @action(
        description="Fetch the final result of a finished background job.",
        input_schema=JobIdInputs,
    )
    def result(self, inputs: JobIdInputs, context: Context) -> JobResultResult:
        job = _lookup(inputs.id)
        if job.state != "done":
            return JobResultResult(
                ok=False,
                state=job.state,
                error=job.error or _STATE_HINTS.get(job.state, "Not finished yet."),
            )
        parsed: Any = job.result_json
        if job.result_json:
            try:
                parsed = json.loads(job.result_json)
            except ValueError:
                parsed = job.result_json  # non-JSON result — return as text
        return JobResultResult(ok=True, state=job.state, result=parsed)

    @action(
        description="Request cancellation of a queued or running background job.",
        input_schema=JobIdInputs,
    )
    def cancel(self, inputs: JobIdInputs, context: Context) -> JobStatusResult:
        job = get_job_manager().cancel(_lookup(inputs.id).id)
        return JobStatusResult(
            job=job.public_summary(),
            hint=(
                "Cancellation requested. Queued jobs stop before starting; running "
                "jobs stop at their next progress event. Poll jobs status to confirm."
            ),
        )

    @action(
        description="List recent background jobs, newest first.",
        input_schema=JobListInputs,
        name="list",
    )
    def list_jobs(self, inputs: JobListInputs, context: Context) -> JobListResult:
        jobs = get_job_manager().list_jobs(limit=inputs.limit)
        return JobListResult(jobs=[j.public_summary() for j in jobs])

"""Background-job endpoints for the web UI.

GET  /api/jobs            → recent jobs, newest first
GET  /api/jobs/{job_id}   → one job's state + progress events (poll target)
POST /api/jobs/{job_id}/cancel → request cancellation

GETs are read-only polling targets (token-exempt like all reads); the cancel
POST goes through the session-token guard like every other mutation.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/jobs")
async def list_jobs(limit: int = 20) -> JSONResponse:
    from docent.core.jobs import get_job_manager

    jobs = get_job_manager().list_jobs(limit=limit)
    return JSONResponse({"jobs": [j.public_summary() for j in jobs]})


@router.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> JSONResponse:
    from docent.core.jobs import JobNotFoundError, get_job_manager

    try:
        job = get_job_manager().get(job_id)
    except JobNotFoundError:
        return JSONResponse({"error": f"No job '{job_id}'"}, status_code=404)
    payload = job.public_summary()
    payload["events"] = job.events  # full event log for the run view
    if job.state == "done":
        payload["result_json"] = job.result_json
    return JSONResponse(payload)


@router.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> JSONResponse:
    from docent.core.jobs import JobNotFoundError, get_job_manager
    from docent.ui_routes._shared import _audit

    try:
        job = get_job_manager().cancel(job_id)
    except JobNotFoundError:
        return JSONResponse({"error": f"No job '{job_id}'"}, status_code=404)
    _audit("job.cancel", job_id)
    return JSONResponse(job.public_summary())

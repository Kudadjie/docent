"""Background job manager — submit → poll for long-running actions.

Why this exists: most studio backends run multi-minute pipelines that cannot
complete inside an MCP tool-call timeout, and the web UI historically needed
two parallel streaming transports (SSE + WebSocket subprocess) to work around
it. The JobManager turns any registered action into a background job:

    submit(tool, action, args)  →  job id
    status(job_id)              →  state + progress events so far
    result(job_id)              →  final serialized result

Design (ADR-006):
- **Thread-per-job.** The whole action stack is sync generators; threads match
  the existing fan-out primitive and avoid asyncio collisions with FastAPI's
  event loop. Threads are daemonic — job records for runs killed by process
  exit are marked ``interrupted`` on the next startup scan.
- **Admission by semaphore.** At most ``MAX_CONCURRENT`` jobs execute at once;
  excess submissions sit in ``queued`` until a slot frees.
- **Persistence.** One JSON file per job under ``~/.docent/data/jobs/``.
  Records survive restarts; the last ``RETENTION`` records are kept.
- **Cooperative cancellation.** Cancel is honoured between ProgressEvents for
  generator actions and before start for queued jobs. A blocking single-shot
  action cannot be interrupted mid-flight — the request is recorded and the
  job is marked cancelled when the action returns.
"""

from __future__ import annotations

import datetime
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from docent.utils.paths import data_dir

logger = logging.getLogger("docent.jobs")

MAX_CONCURRENT = 2  # fallback when settings are unavailable; see serve.jobs_max_concurrent
RETENTION = 50  # finished job records kept on disk
MAX_EVENTS = 500  # progress-event ring buffer per job
# Chatty pipelines can emit hundreds of ProgressEvents; rewriting the whole job
# JSON per event is O(n²) disk churn. Events are flushed at most this often —
# state transitions always persist immediately, and _finish() writes the full
# record, so at most this window of *intermediate* events is lost on a crash.
EVENT_PERSIST_INTERVAL = 2.0  # seconds

JobState = Literal["queued", "running", "done", "failed", "cancelled", "interrupted"]

_ACTIVE_STATES: frozenset[str] = frozenset({"queued", "running"})


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


def _configured_max_concurrent() -> int:
    """Read serve.jobs_max_concurrent, falling back to MAX_CONCURRENT.

    Settings load can fail in stripped-down contexts (tests without a config
    home); the job manager must still construct, so failure means fallback.
    """
    try:
        from docent.config import load_settings

        return int(load_settings().serve.jobs_max_concurrent)
    except Exception:
        return MAX_CONCURRENT


class JobRecord(BaseModel):
    """Persistent record of one background job."""

    id: str
    tool: str
    action: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    state: JobState = "queued"
    created: str = Field(default_factory=_now)
    started: str | None = None
    finished: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    result_json: str | None = None
    error: str | None = None
    cancel_requested: bool = False

    def public_summary(self) -> dict[str, Any]:
        """Status payload without the (potentially large) result body."""
        return {
            "id": self.id,
            "tool": self.tool,
            "action": self.action,
            "state": self.state,
            "created": self.created,
            "started": self.started,
            "finished": self.finished,
            "cancel_requested": self.cancel_requested,
            "event_count": len(self.events),
            "last_events": self.events[-5:],
            "error": self.error,
        }


class JobNotFoundError(KeyError):
    """No job with the given id (may have been pruned by retention)."""


class JobManager:
    """In-process job table with thread-per-job execution and JSON persistence."""

    def __init__(self, jobs_dir: Path | None = None, max_concurrent: int | None = None) -> None:
        self._dir = jobs_dir if jobs_dir is not None else data_dir() / "jobs"
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}
        self._cancel_flags: dict[str, threading.Event] = {}
        self._last_event_flush: dict[str, float] = {}
        if max_concurrent is None:
            max_concurrent = _configured_max_concurrent()
        self._slots = threading.BoundedSemaphore(max(1, max_concurrent))
        self._load_existing()

    # ── persistence ──────────────────────────────────────────────────────────

    def _job_file(self, job_id: str) -> Path:
        return self._dir / f"{job_id}.json"

    def _persist(self, job: JobRecord) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            tmp = self._job_file(job.id).with_suffix(".json.tmp")
            tmp.write_text(job.model_dump_json(indent=2), encoding="utf-8")
            tmp.replace(self._job_file(job.id))
        except OSError as exc:
            logger.warning("Failed to persist job %s: %s", job.id, exc)

    def _load_existing(self) -> None:
        """Load prior job records; mark any left active as interrupted."""
        if not self._dir.is_dir():
            return
        for path in self._dir.glob("job-*.json"):
            try:
                record = JobRecord.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Skipping unreadable job file %s: %s", path.name, exc)
                continue
            if record.state in _ACTIVE_STATES:
                record.state = "interrupted"
                record.finished = record.finished or _now()
                record.error = record.error or "Interrupted: the Docent process exited mid-run."
                self._persist(record)
            self._jobs[record.id] = record
        self._prune()

    def _prune(self) -> None:
        """Keep only the newest RETENTION non-active records (call under lock or at init)."""
        finished = [j for j in self._jobs.values() if j.state not in _ACTIVE_STATES]
        excess = sorted(finished, key=lambda j: j.created)[: max(0, len(finished) - RETENTION)]
        for job in excess:
            self._jobs.pop(job.id, None)
            try:
                self._job_file(job.id).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Failed to prune job file %s: %s", job.id, exc)

    # ── public API ───────────────────────────────────────────────────────────

    def submit(
        self,
        tool: str,
        action: str,
        arguments: dict[str, Any],
        *,
        via_mcp: bool = False,
    ) -> JobRecord:
        """Create a job and start its worker thread. Returns the queued record.

        ``via_mcp`` shapes the job's Context the same way a direct call would:
        MCP-submitted jobs get MCP output framing in their stored result.
        """
        job = JobRecord(
            id=f"job-{uuid.uuid4().hex[:10]}",
            tool=tool,
            action=action,
            arguments=dict(arguments),
        )
        cancel_flag = threading.Event()
        with self._lock:
            self._jobs[job.id] = job
            self._cancel_flags[job.id] = cancel_flag
            self._persist(job)

        worker = threading.Thread(
            target=self._run_job,
            args=(job.id, via_mcp, cancel_flag),
            name=f"docent-{job.id}",
            daemon=True,
        )
        worker.start()
        return job

    def get(self, job_id: str) -> JobRecord:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def cancel(self, job_id: str) -> JobRecord:
        """Request cancellation. Queued jobs die before starting; running
        generator actions stop at their next ProgressEvent."""
        job = self.get(job_id)
        with self._lock:
            if job.state in _ACTIVE_STATES:
                job.cancel_requested = True
                flag = self._cancel_flags.get(job_id)
                if flag is not None:
                    flag.set()
                self._persist(job)
        return job

    def list_jobs(self, limit: int = 20) -> list[JobRecord]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)
        return jobs[:limit]

    # ── worker ───────────────────────────────────────────────────────────────

    def _finish(self, job: JobRecord, state: JobState, *, error: str | None = None) -> None:
        with self._lock:
            job.state = state
            job.finished = _now()
            if error is not None:
                job.error = error
            self._cancel_flags.pop(job.id, None)
            self._last_event_flush.pop(job.id, None)
            self._persist(job)  # full record incl. all events — supersedes throttled flushes
            self._prune()

    def _append_event(self, job: JobRecord, event: Any) -> None:
        entry = {
            "ts": _now(),
            "phase": getattr(event, "phase", ""),
            "message": getattr(event, "message", ""),
            "level": getattr(event, "level", "info"),
        }
        with self._lock:
            job.events.append(entry)
            if len(job.events) > MAX_EVENTS:
                del job.events[: len(job.events) - MAX_EVENTS]
            # Throttled flush (see EVENT_PERSIST_INTERVAL). In-memory state —
            # what status() serves — is always current; only the on-disk crash
            # record lags by at most the interval.
            now = time.monotonic()
            if now - self._last_event_flush.get(job.id, 0.0) >= EVENT_PERSIST_INTERVAL:
                self._last_event_flush[job.id] = now
                self._persist(job)

    def _run_job(self, job_id: str, via_mcp: bool, cancel_flag: threading.Event) -> None:
        import inspect

        from docent.core.events import ProgressEvent
        from docent.core.invoke import make_context, run_action, serialize_result

        job = self.get(job_id)

        with self._slots:
            if cancel_flag.is_set():
                self._finish(job, "cancelled", error="Cancelled while queued.")
                return

            with self._lock:
                job.state = "running"
                job.started = _now()
                self._persist(job)

            try:
                context = make_context(via_mcp=via_mcp, non_interactive=True, auto_confirm=True)
                raw = run_action(job.tool, job.action, job.arguments, context=context)

                if inspect.isgenerator(raw):
                    result_value: Any = None
                    while True:
                        if cancel_flag.is_set():
                            raw.close()
                            self._finish(
                                job, "cancelled", error="Cancelled between progress events."
                            )
                            return
                        try:
                            evt = next(raw)
                        except StopIteration as stop:
                            result_value = stop.value
                            break
                        if isinstance(evt, ProgressEvent):
                            self._append_event(job, evt)
                else:
                    result_value = raw

                with self._lock:
                    job.result_json = serialize_result(result_value)
                if cancel_flag.is_set():
                    # A blocking action can't be interrupted — record that the
                    # cancel arrived too late but keep the result.
                    self._finish(job, "cancelled", error="Cancel arrived after completion.")
                else:
                    self._finish(job, "done")
            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                self._finish(job, "failed", error=f"{type(exc).__name__}: {exc}")


_manager: JobManager | None = None
_manager_lock = threading.Lock()


def get_job_manager() -> JobManager:
    """Process-wide JobManager singleton (created lazily)."""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = JobManager()
        return _manager


def reset_job_manager() -> None:
    """Drop the singleton — for tests that need an isolated jobs directory."""
    global _manager
    with _manager_lock:
        _manager = None

"""Persistence + state recompute for the reading queue.

Owns three files inside `<root>/`:
- queue.json        — source-of-truth list of QueueEntry dicts
- queue-index.json  — id -> {title, status, order} for fast lookups
- state.json        — banner counts + last_updated timestamp

Reads return safe defaults if a file is missing. Writes self-initialize the
directory and use atomic rename so a crash mid-write can't leave a partial
JSON file in place.
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from filelock import FileLock
from pydantic import BaseModel

_logger = logging.getLogger(__name__)

# Increment this when queue.json needs a structural migration.
# Rule: additive field additions do NOT require a version bump (Pydantic handles
# them via defaults).  Only renames, removals, or type changes need a bump + a
# corresponding _migrate_vN_to_vM() function below.
_QUEUE_SCHEMA_VERSION = 1


def _infer_schema_version(entries: list[dict[str, Any]]) -> int:
    """Guess the schema version from the first entry's keys.

    Keep this logic cheap and conservative — when in doubt return the lowest
    plausible version so the migration guard runs.
    """
    return 1  # only one version exists today; extend as migrations are added


def _run_migrations(entries: list[dict[str, Any]], from_version: int) -> list[dict[str, Any]]:
    """Apply all pending migrations in order from *from_version* to _QUEUE_SCHEMA_VERSION."""
    # Example shape for future use:
    #   if from_version < 2:
    #       entries = _migrate_v1_to_v2(entries)
    # Nothing to do yet — v1 is current.
    return entries


class BannerCounts(BaseModel):
    queued: int = 0
    reading: int = 0
    done: int = 0


class ReadingQueueStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def queue_path(self) -> Path:
        return self.root / "queue.json"

    @property
    def index_path(self) -> Path:
        return self.root / "queue-index.json"

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    @contextmanager
    def lock(self, timeout: float = 0) -> Iterator[None]:
        """File lock for a read-modify-write cycle.
        timeout=0 (default): fail immediately if another process holds the lock.
        """
        from filelock import Timeout as _FileLockTimeout
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            with FileLock(str(self.root / "queue.json.lock"), timeout=timeout):
                yield
        except _FileLockTimeout:
            raise RuntimeError(
                "Queue is busy — another Docent process is currently writing. "
                "Retry in a moment."
            ) from None

    def load_queue(self) -> list[dict[str, Any]]:
        if not self.queue_path.exists():
            return []
        try:
            entries: list[dict[str, Any]] = json.loads(self.queue_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _logger.warning("queue.json is corrupt (%s) — treating as empty queue", exc)
            return []
        detected = _infer_schema_version(entries)
        if detected < _QUEUE_SCHEMA_VERSION:
            _logger.info(
                "queue.json schema v%d detected; migrating to v%d",
                detected, _QUEUE_SCHEMA_VERSION,
            )
            entries = _run_migrations(entries, detected)
        return entries

    def load_index(self) -> dict[str, dict[str, Any]]:
        if not self.index_path.exists():
            return {}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _logger.warning("queue-index.json is corrupt (%s) — treating as empty index", exc)
            return {}

    def save_queue(self, queue: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(self.queue_path, queue)
        self._atomic_write_json(self.index_path, self._recompute_index(queue))
        self._write_state(queue)

    def banner_counts(self) -> BannerCounts:
        if not self.state_path.exists():
            return BannerCounts()
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _logger.warning("state.json is corrupt (%s) — using zero counts", exc)
            return BannerCounts()
        return BannerCounts(
            queued=data.get("queued", 0),
            reading=data.get("reading", 0),
            done=data.get("done", 0),
        )

    @staticmethod
    def list_database_pdfs(database_dir: Path) -> list[Path]:
        """Return all PDFs found recursively in `database_dir`.
        Missing directory yields an empty list, not an error.
        """
        if not database_dir.is_dir():
            return []
        return sorted(database_dir.rglob("*.pdf"))

    @staticmethod
    def _recompute_index(queue: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {
            e["id"]: {
                "title": e.get("title", ""),
                "status": e["status"],
                "order": e.get("order", 0),
            }
            for e in queue
        }

    def _write_state(self, queue: list[dict[str, Any]]) -> None:
        state = {
            "queued": sum(1 for e in queue if e["status"] == "queued"),
            "reading": sum(1 for e in queue if e["status"] == "reading"),
            "done": sum(1 for e in queue if e["status"] == "done"),
            "last_updated": datetime.now().isoformat(),
        }
        self._atomic_write_json(self.state_path, state)

    @staticmethod
    def _atomic_write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

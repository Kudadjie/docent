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
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel


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

    def load_queue(self) -> list[dict[str, Any]]:
        if not self.queue_path.exists():
            return []
        return json.loads(self.queue_path.read_text(encoding="utf-8"))

    def load_index(self) -> dict[str, dict[str, Any]]:
        if not self.index_path.exists():
            return {}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def save_queue(self, queue: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(self.queue_path, queue)
        self._atomic_write_json(self.index_path, self._recompute_index(queue))
        self._write_state(queue)

    def banner_counts(self) -> BannerCounts:
        if not self.state_path.exists():
            return BannerCounts()
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
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

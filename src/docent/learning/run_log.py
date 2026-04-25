"""Per-namespace run-log helpers.

A `RunLog(namespace)` is a JSONL file at `~/.docent/data/<namespace>/run-log.jsonl`
capped at `max_lines` (default 50). Append is cheap (single line write); tail is
cheap (read + split); rollover rewrites atomically when the cap is hit.

Entries are free-form JSON dicts. A `timestamp` field is auto-added on append
if the caller didn't supply one.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from docent.utils.paths import data_dir


class RunLog:
    def __init__(self, namespace: str, *, max_lines: int = 50) -> None:
        if not namespace or "/" in namespace or "\\" in namespace:
            raise ValueError(f"Invalid namespace: {namespace!r}")
        if max_lines < 1:
            raise ValueError(f"max_lines must be >= 1, got {max_lines}")
        self.namespace = namespace
        self.max_lines = max_lines

    @property
    def path(self) -> Path:
        return data_dir() / self.namespace / "run-log.jsonl"

    def append(self, entry: dict[str, Any]) -> None:
        record = dict(entry)
        record.setdefault("timestamp", datetime.now().isoformat())
        line = json.dumps(record, ensure_ascii=False)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._read_lines()

        if len(existing) >= self.max_lines:
            kept = existing[-(self.max_lines - 1):] if self.max_lines > 1 else []
            self._atomic_rewrite(kept + [line])
        else:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def tail(self, n: int) -> list[dict[str, Any]]:
        if n < 0:
            raise ValueError(f"n must be >= 0, got {n}")
        if n == 0:
            return []
        lines = self._read_lines()
        return [json.loads(line) for line in lines[-n:]]

    def all(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self._read_lines()]

    def _read_lines(self) -> list[str]:
        if not self.path.exists():
            return []
        text = self.path.read_text(encoding="utf-8")
        return [line for line in text.splitlines() if line.strip()]

    def _atomic_rewrite(self, lines: list[str]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        os.replace(tmp, self.path)

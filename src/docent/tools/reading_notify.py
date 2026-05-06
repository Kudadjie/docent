"""Startup deadline notifications for the reading queue.

Called once per day on first `docent` invocation. Prints a warning for any
entry whose deadline is within 3 days or already past. Deduplicates within a
calendar day so the same alert doesn't repeat across multiple commands.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any


def check_deadlines(store_root: Path) -> list[str]:
    """Return alert lines for entries with deadlines within 3 days or past due.

    Only fires once per calendar day — seen entries are tracked in
    `<store_root>/deadline-seen.json`. Returns an empty list when there is
    nothing to report or when the daily gate has already fired.
    """
    queue_path = store_root / "queue.json"
    seen_path = store_root / "deadline-seen.json"

    if not queue_path.exists():
        return []

    today_str = date.today().isoformat()
    seen: dict[str, str] = {}  # entry_id -> last-seen date
    if seen_path.exists():
        try:
            seen = json.loads(seen_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            seen = {}

    try:
        queue: list[dict[str, Any]] = json.loads(queue_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    today = date.today()
    warn_horizon = today + timedelta(days=3)
    alerts: list[str] = []
    updated_seen = dict(seen)

    for entry in queue:
        if entry.get("status") in ("done", "removed"):
            continue
        deadline_str = entry.get("deadline")
        if not deadline_str:
            continue
        eid = entry.get("id", "")
        if seen.get(eid) == today_str:
            continue  # already alerted today
        try:
            deadline = date.fromisoformat(deadline_str)
        except ValueError:
            continue

        if deadline <= warn_horizon:
            days_left = (deadline - today).days
            title = entry.get("title") or eid
            if days_left < 0:
                alerts.append(f"[OVERDUE {abs(days_left)}d] {title!r} — deadline was {deadline_str}")
            elif days_left == 0:
                alerts.append(f"[DUE TODAY] {title!r} — deadline {deadline_str}")
            else:
                alerts.append(f"[DUE IN {days_left}d] {title!r} — deadline {deadline_str}")
            updated_seen[eid] = today_str

    if updated_seen != seen:
        store_root.mkdir(parents=True, exist_ok=True)
        tmp = seen_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(updated_seen, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, seen_path)

    return alerts

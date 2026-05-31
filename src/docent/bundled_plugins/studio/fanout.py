"""Tier-4 B: concurrent IO fan-out primitive.

parallel_fetch() is the one public symbol — run independent blocking/IO-bound
callables in parallel threads and get back results in submission order.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

logger = logging.getLogger(__name__)


def parallel_fetch(
    tasks: list[Callable[[], Any]],
    *,
    max_workers: int | None = None,
) -> list[Any | None]:
    """Run callables concurrently in threads. Returns results in submission order.

    Failed tasks log a warning and contribute None to the result list so the
    caller always gets a list of the same length as tasks.

    Args:
        tasks: zero-argument callables to run concurrently.
        max_workers: thread pool size; defaults to min(len(tasks), 8).
    """
    if not tasks:
        return []
    workers = max_workers or min(len(tasks), 8)
    results: list[Any | None] = [None] * len(tasks)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_idx = {pool.submit(t): i for i, t in enumerate(tasks)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                logger.warning(
                    "parallel_fetch task[%d] failed: %s: %s",
                    idx,
                    type(exc).__name__,
                    exc,
                )
    return results

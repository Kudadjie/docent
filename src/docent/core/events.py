from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProgressEvent(BaseModel):
    """Streaming event yielded by long-running actions.

    A generator-based action yields zero or more `ProgressEvent` values during
    execution and `return`s its final result. The CLI dispatcher renders each
    event live (via Rich `Progress`) and captures the result from
    `StopIteration.value`. Tests can drive the same generator and collect
    events into a list.

    Field semantics:
    - `phase`: short identifier for the work the action is doing now
      (e.g. "discover", "add", "scholar"). Phase changes signal that the
      renderer should swap to a fresh progress bar.
    - `current` / `total`: optional 1-based progress within the phase.
      When both are set, the renderer draws a bar; when both are None,
      the event is rendered as an info line.
    - `item`: short label for the current item (filename, DOI, ...).
    - `message`: free-form text; required when there's no (current, total).
    - `level`: severity. Errors and warnings render as console lines
      independent of any progress bar.
    """

    phase: str
    message: str = ""
    current: int | None = None
    total: int | None = None
    item: str = ""
    level: Literal["info", "warn", "error"] = "info"

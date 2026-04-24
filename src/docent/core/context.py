from __future__ import annotations

from dataclasses import dataclass

from docent.config import Settings


@dataclass(frozen=True)
class Context:
    settings: Settings

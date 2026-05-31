"""Small helpers shared between action mixin modules."""

from __future__ import annotations

from pathlib import Path


def _path_under(path: Path, root: Path) -> bool:
    """Return True if *path* is equal to or under *root* (both must be resolved)."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

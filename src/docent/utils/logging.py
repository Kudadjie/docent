"""Docent logging setup.

Usage:
    # In cli.py main() callback, once at startup:
    from docent.utils.logging import configure_logging
    configure_logging(verbose=settings.verbose, log_dir=logs_dir())

    # In any module:
    from docent.utils.logging import get_logger
    _log = get_logger(__name__)
    _log.debug("fetching %d sources", n)
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_configured = False

_FILE_FMT = logging.Formatter(
    "%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_STREAM_FMT = logging.Formatter("%(name)s %(levelname)s %(message)s")


def configure_logging(*, verbose: bool, log_dir: Path) -> None:
    """Configure the 'docent' logger. Safe to call multiple times; only acts once."""
    global _configured
    if _configured:
        return
    _configured = True

    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("docent")
    root.setLevel(logging.DEBUG)
    # Prevent propagation to the root logger (avoids double-printing when
    # third-party code sets up a root handler).
    root.propagate = False

    # Rotating file — always on, DEBUG level.
    fh = logging.handlers.RotatingFileHandler(
        log_dir / "docent.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_FILE_FMT)
    root.addHandler(fh)

    # stderr mirror — only when --verbose is set.
    if verbose:
        sh = logging.StreamHandler()
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(_STREAM_FMT)
        root.addHandler(sh)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger namespaced under 'docent'.

    Pass ``__name__`` from the calling module — the function prepends 'docent.'
    if the name doesn't already start with it.
    """
    if not name.startswith("docent"):
        name = f"docent.{name}"
    return logging.getLogger(name)

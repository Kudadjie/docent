"""Tests for docent.utils.logging — configure_logging and get_logger."""
from __future__ import annotations

import logging
from pathlib import Path

import pytest


def _reset_docent_logger():
    """Remove all handlers from the 'docent' logger between tests."""
    root = logging.getLogger("docent")
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()


@pytest.fixture(autouse=True)
def clean_logger():
    _reset_docent_logger()
    # Also reset the module-level _configured flag so each test starts fresh.
    import docent.utils.logging as _mod
    _mod._configured = False
    yield
    _reset_docent_logger()
    _mod._configured = False


def test_configure_logging_creates_log_file(tmp_path: Path) -> None:
    from docent.utils.logging import configure_logging
    configure_logging(verbose=False, log_dir=tmp_path)
    assert (tmp_path / "docent.log").exists()


def test_configure_logging_file_handler_attached(tmp_path: Path) -> None:
    from docent.utils.logging import configure_logging
    configure_logging(verbose=False, log_dir=tmp_path)
    root = logging.getLogger("docent")
    assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers)


def test_configure_logging_no_stream_handler_when_not_verbose(tmp_path: Path) -> None:
    from docent.utils.logging import configure_logging
    configure_logging(verbose=False, log_dir=tmp_path)
    root = logging.getLogger("docent")
    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)
                       and not isinstance(h, logging.FileHandler)]
    assert len(stream_handlers) == 0


def test_configure_logging_adds_stream_handler_when_verbose(tmp_path: Path) -> None:
    from docent.utils.logging import configure_logging
    configure_logging(verbose=True, log_dir=tmp_path)
    root = logging.getLogger("docent")
    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)
                       and not isinstance(h, logging.FileHandler)]
    assert len(stream_handlers) == 1


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    from docent.utils.logging import configure_logging
    configure_logging(verbose=False, log_dir=tmp_path)
    configure_logging(verbose=False, log_dir=tmp_path)  # second call is no-op
    root = logging.getLogger("docent")
    file_handlers = [h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
    assert len(file_handlers) == 1  # not doubled


def test_get_logger_prepends_docent_namespace(tmp_path: Path) -> None:
    from docent.utils.logging import configure_logging, get_logger
    configure_logging(verbose=False, log_dir=tmp_path)
    logger = get_logger("my_module")
    assert logger.name == "docent.my_module"


def test_get_logger_preserves_existing_docent_prefix(tmp_path: Path) -> None:
    from docent.utils.logging import configure_logging, get_logger
    configure_logging(verbose=False, log_dir=tmp_path)
    logger = get_logger("docent.cli")
    assert logger.name == "docent.cli"


def test_log_message_written_to_file(tmp_path: Path) -> None:
    from docent.utils.logging import configure_logging, get_logger
    configure_logging(verbose=False, log_dir=tmp_path)
    log = get_logger("test_module")
    log.debug("hello from test")
    # Flush handlers.
    for h in logging.getLogger("docent").handlers:
        h.flush()
    content = (tmp_path / "docent.log").read_text(encoding="utf-8")
    assert "hello from test" in content


import logging.handlers  # noqa: E402  (needed for isinstance check above)

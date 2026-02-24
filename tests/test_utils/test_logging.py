"""Tests for logging setup."""

import logging

from sprachassistent.utils.logging import get_logger, setup_logging


def test_get_logger_returns_namespaced_logger():
    """get_logger returns a logger under 'sprachassistent' namespace."""
    logger = get_logger("test.module")
    assert logger.name == "sprachassistent.test.module"
    assert isinstance(logger, logging.Logger)


def test_setup_logging_configures_root():
    """setup_logging adds a handler to the sprachassistent root logger."""
    setup_logging(level=logging.DEBUG)
    root = logging.getLogger("sprachassistent")
    assert root.level == logging.DEBUG
    assert len(root.handlers) > 0


def test_setup_logging_is_idempotent():
    """Calling setup_logging multiple times doesn't add duplicate handlers."""
    import sprachassistent.utils.logging as log_mod

    log_mod._configured = False
    setup_logging()
    count_1 = len(logging.getLogger("sprachassistent").handlers)
    setup_logging()
    count_2 = len(logging.getLogger("sprachassistent").handlers)
    assert count_2 == count_1


def test_setup_logging_with_file(tmp_path):
    """setup_logging with log_file creates a FileHandler."""
    import sprachassistent.utils.logging as log_mod

    log_mod._configured = False
    root = logging.getLogger("sprachassistent")
    original_handlers = list(root.handlers)

    log_file = tmp_path / "test.log"
    setup_logging(level=logging.DEBUG, log_file=str(log_file))

    new_handlers = [h for h in root.handlers if h not in original_handlers]
    assert len(new_handlers) == 1
    assert isinstance(new_handlers[0], logging.FileHandler)

    # Clean up: remove the handler we added and reset
    root.removeHandler(new_handlers[0])
    new_handlers[0].close()
    log_mod._configured = False

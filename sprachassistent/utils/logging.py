"""Structured logging setup for the voice assistant.

Logs to a file when configured, otherwise falls back to a simple stderr handler.
"""

import logging
import sys

_configured = False


def setup_logging(level: int = logging.INFO, log_file: str | None = None) -> None:
    """Configure logging for the assistant.

    Args:
        level: Logging level (default: INFO).
        log_file: Path to a log file. If given, logs go to the file.
            If None, logs go to stderr with a simple format.
    """
    global _configured
    if _configured:
        return

    if log_file:
        handler = logging.FileHandler(log_file, encoding="utf-8")
    else:
        handler = logging.StreamHandler(sys.stderr)

    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    root_logger = logging.getLogger("sprachassistent")
    root_logger.setLevel(level)
    root_logger.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger under the sprachassistent namespace.

    Args:
        name: Module name (e.g., "audio.microphone").

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(f"sprachassistent.{name}")

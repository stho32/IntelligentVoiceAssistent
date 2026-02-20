"""Structured logging setup using Rich."""

import logging

from rich.console import Console
from rich.logging import RichHandler

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure Rich-based logging for the assistant.

    Args:
        level: Logging level (default: INFO).
    """
    global _configured
    if _configured:
        return

    console = Console(stderr=True)
    handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))

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

"""Linux restart strategy using os.execv (POSIX process replacement)."""

import os
import sys

from sprachassistent.utils.logging import get_logger

log = get_logger("platform.linux_restart")


def linux_restart() -> None:
    """Replace the current process with a fresh Python interpreter.

    Uses ``os.execv`` which is POSIX-only and replaces the process
    image in-place (no new PID).
    """
    log.info("Restarting assistant process via os.execv...")
    os.execv(sys.executable, [sys.executable] + sys.argv)

"""Windows restart strategy using subprocess + sys.exit."""

import subprocess
import sys

from sprachassistent.utils.logging import get_logger

log = get_logger("platform.windows_restart")


def windows_restart() -> None:
    """Spawn a new Python process and exit the current one.

    On Windows ``os.execv`` does not truly replace the process, so we
    launch a detached subprocess and then exit cleanly.
    """
    log.info("Restarting assistant process via subprocess.Popen + sys.exit...")
    subprocess.Popen([sys.executable] + sys.argv)
    sys.exit(0)

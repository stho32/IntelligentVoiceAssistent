"""Non-blocking keyboard monitor for detecting keypresses during LISTENING phase.

Uses termios/tty to put stdin in cbreak mode and a background thread with
select.select() polling to detect keypresses without blocking the main loop.
"""

import queue
import select
import sys
import termios
import threading
import tty


class KeyboardMonitor:
    """Monitors stdin for keypresses in a background thread.

    Usage::

        with KeyboardMonitor() as kb:
            while True:
                key = kb.check()
                if key is not None:
                    print(f"Pressed: {key}")
    """

    def __init__(self, poll_interval: float = 0.05):
        self._poll_interval = poll_interval
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = False
        self._paused = False
        self._old_settings: list | None = None

    def __enter__(self) -> "KeyboardMonitor":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
        return None

    def start(self) -> None:
        """Start monitoring stdin for keypresses.

        Sets terminal to cbreak mode and starts a polling thread.
        Does nothing if stdin is not a TTY (e.g. in CI or pipes).
        """
        if not sys.stdin.isatty():
            return

        try:
            self._old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except termios.error:
            return

        self._active = True
        self._paused = False
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop monitoring and restore terminal settings."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None
        self._restore_terminal()
        self._active = False

    def check(self) -> str | None:
        """Non-blocking check for a keypress.

        Returns:
            The pressed character, or None if no key was pressed.
        """
        if not self._active or self._paused:
            return None
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def pause(self) -> None:
        """Pause monitoring and restore terminal to cooked mode.

        Call this before handing control to TextInput so that
        normal line-editing (backspace, arrow keys) works.
        """
        self._paused = True
        self._restore_terminal()

    def resume(self) -> None:
        """Resume monitoring after pause, re-entering cbreak mode."""
        if not self._active:
            return
        try:
            tty.setcbreak(sys.stdin.fileno())
        except (termios.error, ValueError):
            return
        # Drain any characters that accumulated during pause
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._paused = False

    def _poll_loop(self) -> None:
        """Background thread: poll stdin and enqueue keypresses."""
        while not self._stop_event.is_set():
            if self._paused:
                self._stop_event.wait(timeout=self._poll_interval)
                continue
            try:
                ready, _, _ = select.select([sys.stdin], [], [], self._poll_interval)
                if ready and not self._paused:
                    ch = sys.stdin.read(1)
                    if ch:
                        self._queue.put(ch)
            except (ValueError, OSError):
                break

    def _restore_terminal(self) -> None:
        """Restore original terminal settings."""
        if self._old_settings is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
            except (termios.error, ValueError):
                pass

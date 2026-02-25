"""Tests for KeyboardMonitor."""

from unittest.mock import patch

from sprachassistent.input.keyboard import KeyboardMonitor


@patch("sprachassistent.input.keyboard.sys")
def test_non_tty_graceful_degradation(mock_sys):
    """KeyboardMonitor stays inactive when stdin is not a TTY."""
    mock_sys.stdin.isatty.return_value = False

    kb = KeyboardMonitor()
    kb.start()

    assert not kb._active
    assert kb.check() is None

    kb.stop()


@patch("sprachassistent.input.keyboard.sys")
def test_check_returns_none_when_inactive(mock_sys):
    """check() returns None when monitor is not active."""
    mock_sys.stdin.isatty.return_value = False
    kb = KeyboardMonitor()
    assert kb.check() is None


def test_check_returns_queued_characters():
    """check() returns characters from the internal queue (FIFO)."""
    kb = KeyboardMonitor()
    kb._active = True
    kb._queue.put("a")
    kb._queue.put("b")

    assert kb.check() == "a"
    assert kb.check() == "b"
    assert kb.check() is None


def test_check_returns_none_when_paused():
    """check() returns None when monitor is paused."""
    kb = KeyboardMonitor()
    kb._active = True
    kb._paused = True
    kb._queue.put("x")

    assert kb.check() is None


@patch("sprachassistent.input.keyboard.sys")
def test_context_manager(mock_sys):
    """Context manager calls start() and stop()."""
    mock_sys.stdin.isatty.return_value = False

    with KeyboardMonitor() as kb:
        assert isinstance(kb, KeyboardMonitor)
    # After exit, should be inactive
    assert not kb._active


@patch("sprachassistent.input.keyboard.termios")
@patch("sprachassistent.input.keyboard.tty")
@patch("sprachassistent.input.keyboard.sys")
def test_start_sets_cbreak_mode(mock_sys, mock_tty, mock_termios):
    """start() sets terminal to cbreak mode when stdin is a TTY."""
    mock_sys.stdin.isatty.return_value = True
    mock_sys.stdin.fileno.return_value = 0
    mock_termios.tcgetattr.return_value = [1, 2, 3]

    kb = KeyboardMonitor()
    kb.start()

    mock_termios.tcgetattr.assert_called_once_with(mock_sys.stdin)
    mock_tty.setcbreak.assert_called_once_with(0)
    assert kb._active

    kb.stop()


@patch("sprachassistent.input.keyboard.termios")
@patch("sprachassistent.input.keyboard.tty")
@patch("sprachassistent.input.keyboard.sys")
def test_stop_restores_terminal(mock_sys, mock_tty, mock_termios):
    """stop() restores original terminal settings."""
    mock_sys.stdin.isatty.return_value = True
    mock_sys.stdin.fileno.return_value = 0
    old_settings = [1, 2, 3]
    mock_termios.tcgetattr.return_value = old_settings

    kb = KeyboardMonitor()
    kb.start()
    kb.stop()

    mock_termios.tcsetattr.assert_called_once_with(
        mock_sys.stdin, mock_termios.TCSADRAIN, old_settings
    )
    assert not kb._active


@patch("sprachassistent.input.keyboard.termios")
@patch("sprachassistent.input.keyboard.tty")
@patch("sprachassistent.input.keyboard.sys")
def test_pause_restores_terminal(mock_sys, mock_tty, mock_termios):
    """pause() restores terminal and sets paused flag."""
    mock_sys.stdin.isatty.return_value = True
    mock_sys.stdin.fileno.return_value = 0
    old_settings = [1, 2, 3]
    mock_termios.tcgetattr.return_value = old_settings

    kb = KeyboardMonitor()
    kb.start()
    kb.pause()

    assert kb._paused
    mock_termios.tcsetattr.assert_called_once()

    kb.stop()


@patch("sprachassistent.input.keyboard.termios")
@patch("sprachassistent.input.keyboard.tty")
@patch("sprachassistent.input.keyboard.sys")
def test_resume_sets_cbreak_and_drains_queue(mock_sys, mock_tty, mock_termios):
    """resume() re-enters cbreak mode and drains accumulated characters."""
    mock_sys.stdin.isatty.return_value = True
    mock_sys.stdin.fileno.return_value = 0
    mock_termios.tcgetattr.return_value = [1, 2, 3]

    kb = KeyboardMonitor()
    kb.start()
    kb.pause()
    # Simulate accumulated chars during pause
    kb._queue.put("x")
    kb._queue.put("y")

    mock_tty.setcbreak.reset_mock()
    kb.resume()

    assert not kb._paused
    mock_tty.setcbreak.assert_called_once_with(0)
    # Queue should be drained
    assert kb._queue.empty()

    kb.stop()


def test_resume_when_not_active():
    """resume() does nothing when monitor was never started."""
    kb = KeyboardMonitor()
    kb._paused = True
    kb.resume()  # Should not raise
    assert kb._paused  # Unchanged since not active

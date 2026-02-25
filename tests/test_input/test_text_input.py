"""Tests for TextInput."""

from unittest.mock import MagicMock, patch

from sprachassistent.input.text_input import TextInput


def _make_ui():
    """Create a mock UI with console."""
    ui = MagicMock()
    ui.console = MagicMock()
    return ui


def test_single_line_text():
    """Single line of text followed by empty line is returned."""
    ui = _make_ui()
    text_input = TextInput()

    # initial_char="h", first input() returns "ello", second returns ""
    with patch("builtins.input", side_effect=["ello", ""]):
        result = text_input.collect(initial_char="h", ui=ui)

    assert result == "hello"
    ui.stop_live.assert_called_once()
    ui.start_live.assert_called_once()


def test_multi_line_text():
    """Multiple lines followed by empty line are joined."""
    ui = _make_ui()
    text_input = TextInput()

    with patch("builtins.input", side_effect=["irst line", "second line", ""]):
        result = text_input.collect(initial_char="f", ui=ui)

    assert result == "first line\nsecond line"


def test_esc_on_first_line_cancels():
    """Esc character as first input cancels and returns None."""
    ui = _make_ui()
    text_input = TextInput()

    # initial_char is Esc, first input returns empty
    with patch("builtins.input", return_value=""):
        result = text_input.collect(initial_char="\x1b", ui=ui)

    assert result is None
    ui.stop_live.assert_called_once()
    ui.start_live.assert_called_once()


def test_esc_on_subsequent_line_cancels():
    """Esc on a subsequent line cancels and returns None."""
    ui = _make_ui()
    text_input = TextInput()

    with patch("builtins.input", side_effect=["ello", "\x1b"]):
        result = text_input.collect(initial_char="h", ui=ui)

    assert result is None


def test_empty_text_returns_none():
    """Whitespace-only input returns None."""
    ui = _make_ui()
    text_input = TextInput()

    # initial_char is space, first input returns empty, second is empty line
    with patch("builtins.input", side_effect=["", ""]):
        result = text_input.collect(initial_char=" ", ui=ui)

    assert result is None


def test_eof_error_returns_none():
    """EOFError during input returns None."""
    ui = _make_ui()
    text_input = TextInput()

    with patch("builtins.input", side_effect=EOFError):
        result = text_input.collect(initial_char="a", ui=ui)

    assert result is None
    ui.start_live.assert_called_once()


def test_keyboard_interrupt_returns_none():
    """KeyboardInterrupt during input returns None."""
    ui = _make_ui()
    text_input = TextInput()

    with patch("builtins.input", side_effect=KeyboardInterrupt):
        result = text_input.collect(initial_char="a", ui=ui)

    assert result is None
    ui.start_live.assert_called_once()


def test_eof_on_subsequent_line_returns_none():
    """EOFError on a subsequent line returns None."""
    ui = _make_ui()
    text_input = TextInput()

    with patch("builtins.input", side_effect=["ello", EOFError]):
        result = text_input.collect(initial_char="h", ui=ui)

    assert result is None


def test_live_restarted_on_error():
    """start_live is called even if _read_input raises an unexpected error."""
    ui = _make_ui()
    text_input = TextInput()

    with patch("builtins.input", side_effect=RuntimeError("unexpected")):
        try:
            text_input.collect(initial_char="x", ui=ui)
        except RuntimeError:
            pass

    # start_live must be called in finally block
    ui.start_live.assert_called_once()


def test_initial_char_prepended():
    """The initial_char appears at the start of the collected text."""
    ui = _make_ui()
    text_input = TextInput()

    with patch("builtins.input", side_effect=["ath/to/file", ""]):
        result = text_input.collect(initial_char="/", ui=ui)

    assert result == "/ath/to/file"

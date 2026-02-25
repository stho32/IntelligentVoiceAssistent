"""Tests for TerminalUI and AssistantState."""

from unittest.mock import MagicMock, patch

from rich.markdown import Markdown
from rich.text import Text

from sprachassistent.utils.terminal_ui import AssistantState, TerminalUI


def test_assistant_state_values():
    """All expected states exist with correct values."""
    assert AssistantState.IDLE.value == "idle"
    assert AssistantState.LISTENING.value == "listening"
    assert AssistantState.RECORDING.value == "recording"
    assert AssistantState.PROCESSING.value == "processing"
    assert AssistantState.SPEAKING.value == "speaking"
    assert AssistantState.ERROR.value == "error"
    assert AssistantState.TYPING.value == "typing"


def test_state_enum_has_all_states():
    """Enum has exactly 7 states."""
    assert len(AssistantState) == 7


@patch("sprachassistent.utils.terminal_ui.Live")
def test_context_manager_starts_live(mock_live_cls):
    """Entering context starts the Live display."""
    mock_live = MagicMock()
    mock_live_cls.return_value = mock_live

    with TerminalUI():
        mock_live.start.assert_called_once()
    mock_live.stop.assert_called_once()


@patch("sprachassistent.utils.terminal_ui.Live")
def test_set_state_updates_display(mock_live_cls):
    """set_state triggers a display refresh."""
    mock_live = MagicMock()
    mock_live_cls.return_value = mock_live

    with TerminalUI() as ui:
        ui.set_state(AssistantState.RECORDING)
        mock_live.update.assert_called()


@patch("sprachassistent.utils.terminal_ui.Live")
def test_set_transcription(mock_live_cls):
    """set_transcription stores text and timestamp."""
    mock_live = MagicMock()
    mock_live_cls.return_value = mock_live

    with TerminalUI() as ui:
        ui.set_transcription("Hallo Computer")
        assert ui._transcription == "Hallo Computer"
        assert ui._transcription_time != ""


@patch("sprachassistent.utils.terminal_ui.Live")
def test_set_response(mock_live_cls):
    """set_response stores text and timestamp."""
    mock_live = MagicMock()
    mock_live_cls.return_value = mock_live

    with TerminalUI() as ui:
        ui.set_response("Wie kann ich helfen?")
        assert ui._response == "Wie kann ich helfen?"
        assert ui._response_time != ""


def test_render_without_live():
    """_render works even without Live context."""
    ui = TerminalUI()
    panel = ui._render()
    assert panel is not None


@patch("sprachassistent.utils.terminal_ui.Live")
def test_transient_true(mock_live_cls):
    """Live is created with transient=True."""
    mock_live = MagicMock()
    mock_live_cls.return_value = mock_live

    with TerminalUI():
        pass

    _, kwargs = mock_live_cls.call_args
    assert kwargs.get("transient") is True


def test_render_only_shows_status():
    """Panel contains only status, not transcription or response."""
    ui = TerminalUI()
    ui._transcription = "some text"
    ui._response = "some response"
    panel = ui._render()
    # The panel renderable is a Text object with only status info
    content = panel.renderable
    assert isinstance(content, Text)
    plain = content.plain
    assert "Status:" in plain
    assert "some text" not in plain
    assert "some response" not in plain


@patch("sprachassistent.utils.terminal_ui.Live")
def test_print_conversation_turn(mock_live_cls):
    """print_conversation_turn prints formatted blocks via console.print()."""
    mock_live = MagicMock()
    mock_console = MagicMock()
    mock_live.console = mock_console
    mock_live_cls.return_value = mock_live

    with TerminalUI() as ui:
        ui.set_transcription("Hallo Jarvis")
        ui.set_response("Hallo! Wie kann ich helfen?")
        ui.print_conversation_turn()

    # console.print() should have been called with Text and Markdown objects
    print_calls = mock_console.print.call_args_list
    assert len(print_calls) >= 3  # user line, blank, header, markdown, blank

    # First call: user line (Text with "Du:")
    first_arg = print_calls[0][0][0]
    assert isinstance(first_arg, Text)
    assert "Du:" in first_arg.plain

    # One of the calls should have Markdown content
    markdown_calls = [c for c in print_calls if c[0] and isinstance(c[0][0], Markdown)]
    assert len(markdown_calls) == 1


@patch("sprachassistent.utils.terminal_ui.Live")
def test_log_uses_print_not_log(mock_live_cls):
    """log() uses console.print() instead of console.log()."""
    mock_live = MagicMock()
    mock_console = MagicMock()
    mock_live.console = mock_console
    mock_live_cls.return_value = mock_live

    with TerminalUI() as ui:
        ui.log("Test message")

    mock_console.print.assert_called()
    mock_console.log.assert_not_called()


def test_typing_state_in_render():
    """TYPING state renders correctly in the status panel."""
    ui = TerminalUI()
    ui.set_state(AssistantState.TYPING)
    panel = ui._render()
    content = panel.renderable
    assert "Texteingabe" in content.plain


def test_listening_hint_includes_key_press():
    """LISTENING label includes hint about pressing a key to type."""
    ui = TerminalUI()
    ui.set_state(AssistantState.LISTENING)
    panel = ui._render()
    content = panel.renderable
    assert "press any key to type" in content.plain


@patch("sprachassistent.utils.terminal_ui.Live")
def test_keyboard_marker_in_conversation(mock_live_cls):
    """print_conversation_turn shows [Tastatur] when input_source is keyboard."""
    mock_live = MagicMock()
    mock_console = MagicMock()
    mock_live.console = mock_console
    mock_live_cls.return_value = mock_live

    with TerminalUI() as ui:
        ui.set_input_source("keyboard")
        ui.set_transcription("~/some/path")
        ui.set_response("Got it.")
        ui.print_conversation_turn()

    print_calls = mock_console.print.call_args_list
    first_arg = print_calls[0][0][0]
    assert isinstance(first_arg, Text)
    assert "[Tastatur]" in first_arg.plain


@patch("sprachassistent.utils.terminal_ui.Live")
def test_voice_marker_not_shown_for_voice(mock_live_cls):
    """print_conversation_turn does NOT show [Tastatur] for voice input."""
    mock_live = MagicMock()
    mock_console = MagicMock()
    mock_live.console = mock_console
    mock_live_cls.return_value = mock_live

    with TerminalUI() as ui:
        ui.set_input_source("voice")
        ui.set_transcription("Hallo Jarvis")
        ui.set_response("Hallo!")
        ui.print_conversation_turn()

    print_calls = mock_console.print.call_args_list
    first_arg = print_calls[0][0][0]
    assert isinstance(first_arg, Text)
    assert "[Tastatur]" not in first_arg.plain
    assert "Du:" in first_arg.plain


@patch("sprachassistent.utils.terminal_ui.Live")
def test_stop_live(mock_live_cls):
    """stop_live() stops the Live display."""
    mock_live = MagicMock()
    mock_live_cls.return_value = mock_live

    with TerminalUI() as ui:
        mock_live.stop.reset_mock()
        ui.stop_live()
        mock_live.stop.assert_called_once()


@patch("sprachassistent.utils.terminal_ui.Live")
def test_start_live(mock_live_cls):
    """start_live() restarts the Live display."""
    mock_live = MagicMock()
    mock_live_cls.return_value = mock_live

    with TerminalUI() as ui:
        ui.start_live()
        # start is called once in __enter__ and once by start_live
        assert mock_live.start.call_count == 2


def test_stop_live_without_context():
    """stop_live() is safe to call without entering context."""
    ui = TerminalUI()
    ui.stop_live()  # Should not raise


def test_start_live_without_context():
    """start_live() is safe to call without entering context."""
    ui = TerminalUI()
    ui.start_live()  # Should not raise

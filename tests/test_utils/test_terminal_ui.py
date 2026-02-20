"""Tests for TerminalUI and AssistantState."""

from unittest.mock import MagicMock, patch

from sprachassistent.utils.terminal_ui import AssistantState, TerminalUI


def test_assistant_state_values():
    """All expected states exist with correct values."""
    assert AssistantState.IDLE.value == "idle"
    assert AssistantState.LISTENING.value == "listening"
    assert AssistantState.RECORDING.value == "recording"
    assert AssistantState.PROCESSING.value == "processing"
    assert AssistantState.SPEAKING.value == "speaking"
    assert AssistantState.ERROR.value == "error"


def test_state_enum_has_all_states():
    """Enum has exactly 6 states."""
    assert len(AssistantState) == 6


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
    """set_transcription stores text and refreshes."""
    mock_live = MagicMock()
    mock_live_cls.return_value = mock_live

    with TerminalUI() as ui:
        ui.set_transcription("Hallo Computer")
        assert ui._transcription == "Hallo Computer"


@patch("sprachassistent.utils.terminal_ui.Live")
def test_set_response(mock_live_cls):
    """set_response stores text and refreshes."""
    mock_live = MagicMock()
    mock_live_cls.return_value = mock_live

    with TerminalUI() as ui:
        ui.set_response("Wie kann ich helfen?")
        assert ui._response == "Wie kann ich helfen?"


def test_render_without_live():
    """_render works even without Live context."""
    ui = TerminalUI()
    panel = ui._render()
    assert panel is not None

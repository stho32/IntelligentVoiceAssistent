"""Tests for the main loop (all components mocked)."""

import queue
import subprocess
import threading
from unittest.mock import MagicMock, patch

import pytest

from sprachassistent.chat.message import ChatMessage
from sprachassistent.exceptions import AIBackendError
from sprachassistent.main import (
    _process_chat_message,
    _RestartRequested,
    create_components,
    run_chat_loop,
    run_loop,
)
from sprachassistent.utils.terminal_ui import AssistantState


def _make_config():
    """Create a minimal test config."""
    return {
        "wake_word": {"model_path": "models/test.onnx", "threshold": 0.5},
        "audio": {
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 1280,
            "vad_threshold": 0.5,
            "silence_threshold_sec": 1.5,
            "max_recording_sec": 30,
        },
        "stt": {"model": "whisper-1", "language": "de"},
        "ai": {
            "backend": "claude-code",
            "working_directory": "/tmp/test",
            "system_prompt_path": "ai/prompts/system.md",
        },
        "tts": {"model": "tts-1", "voice": "onyx", "speed": 1.0},
    }


def _make_mock_components():
    """Create mock components for the loop."""
    transcriber = MagicMock()
    # filter_transcript should pass text through by default
    transcriber.filter_transcript.side_effect = lambda text: text
    return {
        "wake_word": MagicMock(),
        "recorder": MagicMock(),
        "transcriber": transcriber,
        "ai_backend": MagicMock(),
        "tts": MagicMock(),
    }


def test_full_cycle():
    """Test a complete wake-word -> record -> STT -> AI -> TTS cycle."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    # Setup: wake word detected on first call, then raise to exit loop
    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True  # detected
        raise KeyboardInterrupt  # exit after one cycle

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False  # recording done immediately
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Hallo Computer"
    components["ai_backend"].ask.return_value = "Hallo! Wie kann ich helfen?"

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    # Verify full pipeline was called
    components["wake_word"].reset.assert_called_once()
    components["recorder"].start.assert_called_once()
    components["transcriber"].transcribe.assert_called_once()
    components["ai_backend"].ask.assert_called_once_with("Hallo Computer")
    components["tts"].speak.assert_called_once()


def test_keyboard_interrupt_exits():
    """KeyboardInterrupt exits the loop cleanly."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    mic.read_chunk.side_effect = KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)


def test_stt_error_continues():
    """STT errors don't crash the loop."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.side_effect = RuntimeError("API error")

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    # AI should not be called since STT failed
    components["ai_backend"].ask.assert_not_called()
    # Error message should be spoken via TTS
    components["tts"].speak.assert_called_once()
    spoken_text = components["tts"].speak.call_args[0][0]
    assert "nicht verstehen" in spoken_text


def test_stt_error_speaks_error_message():
    """STT error causes error message to be spoken via TTS."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.side_effect = RuntimeError("API error")

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    components["tts"].speak.assert_called_once()
    spoken_text = components["tts"].speak.call_args[0][0]
    assert "nicht verstehen" in spoken_text


def test_ai_error_speaks_error_message():
    """AI error causes general error message to be spoken via TTS."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Test input"
    components["ai_backend"].ask.side_effect = RuntimeError("Backend unavailable")

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    components["tts"].speak.assert_called_once()
    spoken_text = components["tts"].speak.call_args[0][0]
    assert "Fehler aufgetreten" in spoken_text


def test_ai_timeout_speaks_timeout_message():
    """AI timeout causes timeout-specific error message."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Test input"

    # AIBackendError with TimeoutExpired as __cause__
    timeout_err = subprocess.TimeoutExpired(cmd="claude", timeout=300)
    ai_err = AIBackendError("Claude Code did not respond within 300s")
    ai_err.__cause__ = timeout_err
    components["ai_backend"].ask.side_effect = ai_err

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    components["tts"].speak.assert_called_once()
    spoken_text = components["tts"].speak.call_args[0][0]
    assert "zu lange gedauert" in spoken_text


@patch("sprachassistent.main._ERROR_SOUND_PATH")
def test_tts_error_plays_error_sound(mock_error_path):
    """TTS failure falls back to error.wav sound."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Test"
    components["ai_backend"].ask.return_value = "Response"
    components["tts"].speak.side_effect = RuntimeError("TTS API down")
    mock_error_path.exists.return_value = True

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    player.play_wav.assert_any_call(mock_error_path)


@patch("sprachassistent.main._ERROR_SOUND_PATH")
def test_error_tts_failure_does_not_crash(mock_error_path):
    """If speaking the error message also fails, assistant doesn't crash."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.side_effect = RuntimeError("STT failed")

    # TTS fails for the error message too
    components["tts"].speak.side_effect = RuntimeError("TTS also down")
    mock_error_path.exists.return_value = True

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    # Verify it returned to LISTENING despite double failure
    last_state_call = ui.set_state.call_args_list[-1]
    assert last_state_call.args[0] == AssistantState.LISTENING


def test_cancel_command_after_transcription():
    """Cancel keyword after transcription skips AI and speaks confirmation."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Stopp"

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui, cancel_keywords=["stopp", "abbrechen"])

    # AI should not be called
    components["ai_backend"].ask.assert_not_called()
    # TTS should speak "Alles klar."
    components["tts"].speak.assert_called_once()
    spoken_text = components["tts"].speak.call_args[0][0]
    assert "Alles klar" in spoken_text


def test_non_cancel_text_proceeds_normally():
    """Normal text is not treated as cancel command."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Schreibe eine Notiz"
    components["ai_backend"].ask.return_value = "Erledigt."

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui, cancel_keywords=["stopp", "abbrechen"])

    # AI should be called normally
    components["ai_backend"].ask.assert_called_once_with("Schreibe eine Notiz")


def test_cancel_during_ai_processing():
    """Cancel via wake word during AI processing terminates the request."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    # AI takes a long time (blocks until cancelled)
    ai_cancelled = threading.Event()

    def slow_ask(msg):
        ai_cancelled.wait(timeout=5)
        raise RuntimeError("Cancelled")

    components["ai_backend"].ask.side_effect = slow_ask

    # Wake word detection: first=True (initial), then False during AI,
    # then True (cancel wake word), then raise to exit
    wake_calls = [0]

    def wake_word_side_effect(chunk):
        wake_calls[0] += 1
        if wake_calls[0] == 1:
            return True  # Initial wake word
        if wake_calls[0] == 3:
            return True  # Cancel wake word during AI processing
        if wake_calls[0] > 10:
            raise KeyboardInterrupt
        return False

    components["wake_word"].process.side_effect = wake_word_side_effect

    # First recording: normal command
    # Second recording (cancel): "Stopp"
    record_calls = [0]

    def recorder_get_audio():
        record_calls[0] += 1
        return b"\x00" * 3200

    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.side_effect = recorder_get_audio

    # First transcription: normal, second: cancel keyword
    transcribe_calls = [0]

    def transcribe_side_effect(audio):
        transcribe_calls[0] += 1
        if transcribe_calls[0] == 1:
            return "Schreibe eine Notiz"
        return "Stopp"

    components["transcriber"].transcribe.side_effect = transcribe_side_effect

    def cancel_side_effect():
        ai_cancelled.set()

    components["ai_backend"].cancel.side_effect = cancel_side_effect

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui, cancel_keywords=["stopp", "abbrechen"])

    # cancel() should have been called on the backend
    components["ai_backend"].cancel.assert_called_once()


def test_reset_command_resets_session():
    """Reset keyword resets the AI session and speaks confirmation."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Neue Konversation"

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            reset_keywords=["neue konversation", "reset"],
        )

    # AI should not be called
    components["ai_backend"].ask.assert_not_called()
    # reset_session should be called
    components["ai_backend"].reset_session.assert_called_once()
    # TTS should speak confirmation
    components["tts"].speak.assert_called_once()
    spoken_text = components["tts"].speak.call_args[0][0]
    assert "neue Konversation" in spoken_text


def test_reset_before_cancel_priority():
    """Cancel keywords are checked before reset keywords."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    # "Stopp" matches cancel, not reset
    components["transcriber"].transcribe.return_value = "Stopp"

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            cancel_keywords=["stopp"],
            reset_keywords=["reset"],
        )

    # Cancel takes priority - reset should NOT be called
    components["ai_backend"].reset_session.assert_not_called()
    components["ai_backend"].ask.assert_not_called()


def test_restart_command_raises_restart_requested():
    """Restart keyword causes _RestartRequested to be raised."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Starte neu"

    with pytest.raises(_RestartRequested):
        run_loop(
            components,
            mic,
            player,
            ui,
            restart_keywords=["neustart", "starte neu"],
        )

    # AI should not be called
    components["ai_backend"].ask.assert_not_called()
    # TTS should speak confirmation
    components["tts"].speak.assert_called_once()
    spoken_text = components["tts"].speak.call_args[0][0]
    assert "starte jetzt neu" in spoken_text


def test_restart_priority_after_cancel_and_reset():
    """Restart is checked after cancel and reset (lowest priority)."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    # "stopp" matches cancel, should NOT reach restart
    components["transcriber"].transcribe.return_value = "Stopp"

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            cancel_keywords=["stopp"],
            reset_keywords=["reset"],
            restart_keywords=["neustart"],
        )

    # Cancel takes priority - AI and reset should NOT be called
    components["ai_backend"].ask.assert_not_called()
    components["ai_backend"].reset_session.assert_not_called()


def test_restart_tts_failure_still_raises():
    """Even if TTS fails, restart is still triggered."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Neustart"
    components["tts"].speak.side_effect = RuntimeError("TTS down")

    with pytest.raises(_RestartRequested):
        run_loop(
            components,
            mic,
            player,
            ui,
            restart_keywords=["neustart"],
        )


@patch("sprachassistent.main._restart_assistant")
@patch("sys.argv", ["sprachassistent"])
def test_main_handles_restart_requested(mock_restart):
    """main() catches _RestartRequested and calls _restart_assistant."""
    with (
        patch("sprachassistent.main.setup_logging"),
        patch("sprachassistent.main.get_config") as mock_cfg,
        patch("sprachassistent.main.create_components"),
        patch("sprachassistent.main.create_audio_input"),
        patch("sprachassistent.main.create_audio_output"),
        patch("sprachassistent.main.TerminalUI"),
        patch("sprachassistent.main.KeyboardMonitor"),
        patch("sprachassistent.main.TextInput"),
        patch("sprachassistent.main.run_loop") as mock_run_loop,
    ):
        mock_cfg.return_value = {
            "audio": {"sample_rate": 16000, "channels": 1, "chunk_size": 1280},
            "ai": {"thinking_beep_interval": 3},
            "commands": {},
        }
        mock_run_loop.side_effect = _RestartRequested

        from sprachassistent.main import main

        main()

        mock_restart.assert_called_once()


@patch("sprachassistent.main.WakeWordDetector")
@patch("sprachassistent.main.SpeechRecorder")
@patch("sprachassistent.main.WhisperTranscriber")
@patch("sprachassistent.main.ClaudeCodeBackend")
@patch("sprachassistent.main.OpenAITextToSpeech")
def test_create_components(mock_tts, mock_ai, mock_stt, mock_rec, mock_ww):
    """create_components initializes all components from config."""
    config = _make_config()
    components = create_components(config)

    assert "wake_word" in components
    assert "recorder" in components
    assert "transcriber" in components
    assert "ai_backend" in components
    assert "tts" in components


@patch("sprachassistent.main.WakeWordDetector")
@patch("sprachassistent.main.SpeechRecorder")
@patch("sprachassistent.main.WhisperTranscriber")
@patch("sprachassistent.main.ClaudeCodeBackend")
@patch("sprachassistent.main.OpenAITextToSpeech")
def test_create_components_passes_resume_session(mock_tts, mock_ai, mock_stt, mock_rec, mock_ww):
    """create_components passes resume_session=False to ClaudeCodeBackend."""
    config = _make_config()
    create_components(config, resume_session=False)

    mock_ai.assert_called_once()
    kwargs = mock_ai.call_args.kwargs
    assert kwargs["resume_session"] is False


@patch("sprachassistent.main.WakeWordDetector")
@patch("sprachassistent.main.SpeechRecorder")
@patch("sprachassistent.main.WhisperTranscriber")
@patch("sprachassistent.main.ClaudeCodeBackend")
@patch("sprachassistent.main.OpenAITextToSpeech")
def test_create_components_default_resume_session(mock_tts, mock_ai, mock_stt, mock_rec, mock_ww):
    """create_components defaults to resume_session=True."""
    config = _make_config()
    create_components(config)

    mock_ai.assert_called_once()
    kwargs = mock_ai.call_args.kwargs
    assert kwargs["resume_session"] is True


@patch("sprachassistent.main._restart_assistant")
@patch("sys.argv", ["sprachassistent", "--new-session"])
def test_main_new_session_flag(mock_restart):
    """--new-session in argv sets resume_session=False."""
    with (
        patch("sprachassistent.main.setup_logging"),
        patch("sprachassistent.main.get_config") as mock_cfg,
        patch("sprachassistent.main.create_components") as mock_create,
        patch("sprachassistent.main.create_audio_input"),
        patch("sprachassistent.main.create_audio_output"),
        patch("sprachassistent.main.TerminalUI"),
        patch("sprachassistent.main.KeyboardMonitor"),
        patch("sprachassistent.main.TextInput"),
        patch("sprachassistent.main.run_loop") as mock_run_loop,
    ):
        mock_cfg.return_value = {
            "audio": {"sample_rate": 16000, "channels": 1, "chunk_size": 1280},
            "ai": {"thinking_beep_interval": 3},
            "commands": {},
        }
        mock_run_loop.side_effect = KeyboardInterrupt

        from sprachassistent.main import main

        main()

        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        assert kwargs["resume_session"] is False


# --- Text input tests ---


def test_text_input_bypasses_recording_and_stt():
    """Keyboard text input skips wake word, recording, and STT."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    keyboard_monitor = MagicMock()
    text_input = MagicMock()

    # First check: key pressed, second check (after AI cycle): raise to exit
    call_count = 0

    def check_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "h"
        raise KeyboardInterrupt

    keyboard_monitor.check.side_effect = check_side_effect
    text_input.collect.return_value = "hello world"
    components["ai_backend"].ask.return_value = "Hi there!"

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            keyboard_monitor=keyboard_monitor,
            text_input=text_input,
        )

    # Wake word, recorder, transcriber should NOT be used
    components["wake_word"].process.assert_not_called()
    components["recorder"].start.assert_not_called()
    components["transcriber"].transcribe.assert_not_called()

    # AI should receive the typed text
    components["ai_backend"].ask.assert_called_once_with("hello world")
    # TTS should speak the response
    components["tts"].speak.assert_called_once()

    # Keyboard monitor should be paused/resumed
    keyboard_monitor.pause.assert_called_once()
    keyboard_monitor.resume.assert_called_once()


def test_text_input_cancel_returns_to_listening():
    """Cancelled text input returns to LISTENING without calling AI."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    keyboard_monitor = MagicMock()
    text_input = MagicMock()

    call_count = 0

    def check_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "\x1b"  # Esc key
        raise KeyboardInterrupt

    keyboard_monitor.check.side_effect = check_side_effect
    text_input.collect.return_value = None  # Cancelled

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            keyboard_monitor=keyboard_monitor,
            text_input=text_input,
        )

    components["ai_backend"].ask.assert_not_called()
    # Should return to LISTENING
    state_calls = [c.args[0] for c in ui.set_state.call_args_list]
    assert AssistantState.TYPING in state_calls
    assert state_calls[-1] == AssistantState.LISTENING


def test_text_input_commands_recognized():
    """Cancel/reset/restart commands work with keyboard input too."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    keyboard_monitor = MagicMock()
    text_input = MagicMock()

    call_count = 0

    def check_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "s"
        raise KeyboardInterrupt

    keyboard_monitor.check.side_effect = check_side_effect
    text_input.collect.return_value = "stopp"

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            cancel_keywords=["stopp"],
            keyboard_monitor=keyboard_monitor,
            text_input=text_input,
        )

    # Cancel should fire, AI should NOT be called
    components["ai_backend"].ask.assert_not_called()
    components["tts"].speak.assert_called_once()
    spoken_text = components["tts"].speak.call_args[0][0]
    assert "Alles klar" in spoken_text


def test_text_input_sets_keyboard_source():
    """Keyboard input sets input_source to 'keyboard'."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    keyboard_monitor = MagicMock()
    text_input = MagicMock()

    call_count = 0

    def check_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "t"
        raise KeyboardInterrupt

    keyboard_monitor.check.side_effect = check_side_effect
    text_input.collect.return_value = "test message"
    components["ai_backend"].ask.return_value = "Response"

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            keyboard_monitor=keyboard_monitor,
            text_input=text_input,
        )

    # Should have set input_source to "keyboard" and then back to "voice"
    source_calls = [c.args[0] for c in ui.set_input_source.call_args_list]
    assert "keyboard" in source_calls
    assert source_calls[-1] == "voice"


def test_backward_compat_without_keyboard_monitor():
    """run_loop works without keyboard_monitor (backward compat)."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Hello"
    components["ai_backend"].ask.return_value = "Hi!"

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    # Normal voice path should work without keyboard_monitor
    components["ai_backend"].ask.assert_called_once_with("Hello")


# --- Matrix chat integration tests ---


def _make_chat_msg(text="Hello", sender="@user:matrix.org", room_id="!room:matrix.org"):
    """Create a ChatMessage for testing."""
    return ChatMessage(
        room_id=room_id,
        sender=sender,
        text=text,
        timestamp=1700000000000,
        event_id="$evt1",
    )


def test_chat_message_processed_in_idle_loop():
    """Chat message from Matrix queue is processed when wake word is not detected."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    incoming = queue.Queue()
    outgoing = queue.Queue()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First iteration: no wake word, but chat message waiting
            return False
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["ai_backend"].ask.return_value = "Chat response"

    incoming.put(_make_chat_msg("Hello from chat"))

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            matrix_incoming=incoming,
            matrix_outgoing=outgoing,
        )

    components["ai_backend"].ask.assert_called_once()
    assert "[Chat-Nachricht" in components["ai_backend"].ask.call_args[0][0]
    room_id, response = outgoing.get_nowait()
    assert response == "Chat response"


def test_chat_not_processed_without_queues():
    """Without matrix queues, the loop works as before."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    components["ai_backend"].ask.assert_not_called()


def test_process_chat_message_cancel():
    """Cancel keyword in chat message triggers cancel."""
    ai = MagicMock()
    outgoing = queue.Queue()
    ui = MagicMock()
    msg = _make_chat_msg("Stopp")

    _process_chat_message(msg, ai, outgoing, ui, ["stopp"], [])

    ai.cancel.assert_called_once()
    room_id, text = outgoing.get_nowait()
    assert "Abgebrochen" in text


def test_process_chat_message_reset():
    """Reset keyword in chat message triggers session reset."""
    ai = MagicMock()
    outgoing = queue.Queue()
    ui = MagicMock()
    msg = _make_chat_msg("reset")

    _process_chat_message(msg, ai, outgoing, ui, [], ["reset"])

    ai.reset_session.assert_called_once()
    room_id, text = outgoing.get_nowait()
    assert "zurueckgesetzt" in text


def test_process_chat_message_restart_ignored():
    """Restart keywords are just normal text in chat (not handled specially)."""
    ai = MagicMock()
    ai.ask.return_value = "Some response"
    outgoing = queue.Queue()
    ui = MagicMock()
    msg = _make_chat_msg("Neustart")

    _process_chat_message(msg, ai, outgoing, ui, [], [])

    ai.ask.assert_called_once()
    assert "[Chat-Nachricht" in ai.ask.call_args[0][0]


def test_process_chat_message_normal():
    """Normal chat message is forwarded to AI with markdown prefix."""
    ai = MagicMock()
    ai.ask.return_value = "AI answer"
    outgoing = queue.Queue()
    ui = MagicMock()
    msg = _make_chat_msg("What is the weather?")

    _process_chat_message(msg, ai, outgoing, ui, [], [])

    ai.ask.assert_called_once()
    assert "What is the weather?" in ai.ask.call_args[0][0]
    assert "[Chat-Nachricht, Markdown-Antwort erlaubt]" in ai.ask.call_args[0][0]
    room_id, text = outgoing.get_nowait()
    assert text == "AI answer"


def test_process_chat_message_ai_error():
    """AI error results in error message sent to chat."""
    ai = MagicMock()
    ai.ask.side_effect = RuntimeError("AI down")
    outgoing = queue.Queue()
    ui = MagicMock()
    msg = _make_chat_msg("Test")

    _process_chat_message(msg, ai, outgoing, ui, [], [])

    room_id, text = outgoing.get_nowait()
    assert "Fehler" in text


def test_chat_only_loop_processes_messages():
    """Chat-only loop processes messages from the queue."""
    ai = MagicMock()
    ai.ask.return_value = "Response"
    incoming = queue.Queue()
    outgoing = queue.Queue()
    ui = MagicMock()

    incoming.put(_make_chat_msg("Hello"))

    call_count = [0]
    original_get = incoming.get

    def get_with_exit(timeout=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return original_get(timeout=0)
        raise KeyboardInterrupt

    incoming.get = get_with_exit

    with pytest.raises(KeyboardInterrupt):
        run_chat_loop(ai, ui, incoming, outgoing)

    ai.ask.assert_called_once()
    room_id, text = outgoing.get_nowait()
    assert text == "Response"


@patch("sprachassistent.main.WakeWordDetector")
@patch("sprachassistent.main.SpeechRecorder")
@patch("sprachassistent.main.WhisperTranscriber")
@patch("sprachassistent.main.ClaudeCodeBackend")
@patch("sprachassistent.main.OpenAITextToSpeech")
def test_create_components_chat_only(mock_tts, mock_ai, mock_stt, mock_rec, mock_ww):
    """create_components with chat_only=True only creates AI backend."""
    config = _make_config()
    components = create_components(config, chat_only=True)

    assert "ai_backend" in components
    assert "wake_word" not in components
    assert "recorder" not in components
    assert "transcriber" not in components
    assert "tts" not in components
    mock_ww.assert_not_called()
    mock_rec.assert_not_called()
    mock_stt.assert_not_called()
    mock_tts.assert_not_called()


# --- Transcript filtering tests ---


def test_short_recording_skipped():
    """Recording shorter than min_recording_sec is not transcribed."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    # 1 second of audio at 16kHz, 16-bit = 32000 bytes (< 2s threshold)
    components["recorder"].get_audio.return_value = b"\x00" * 32000

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            sample_rate=16000,
            min_recording_sec=2.0,
        )

    # Transcriber should NOT be called
    components["transcriber"].transcribe.assert_not_called()
    components["ai_backend"].ask.assert_not_called()


def test_recording_at_min_duration_transcribed():
    """Recording exactly at min_recording_sec threshold is processed."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    # Exactly 2 seconds at 16kHz, 16-bit = 64000 bytes
    components["recorder"].get_audio.return_value = b"\x00" * 64000
    components["transcriber"].transcribe.return_value = "Hallo"
    components["transcriber"].filter_transcript.return_value = "Hallo"
    components["ai_backend"].ask.return_value = "Hi!"

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            sample_rate=16000,
            min_recording_sec=2.0,
        )

    # Transcriber SHOULD be called
    components["transcriber"].transcribe.assert_called_once()
    components["ai_backend"].ask.assert_called_once()

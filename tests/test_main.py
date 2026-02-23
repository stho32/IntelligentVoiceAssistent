"""Tests for the main loop (all components mocked)."""

import subprocess
import threading
from unittest.mock import MagicMock, patch

import pytest

from sprachassistent.exceptions import AIBackendError
from sprachassistent.main import _RestartRequested, create_components, run_loop
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
    return {
        "wake_word": MagicMock(),
        "recorder": MagicMock(),
        "transcriber": MagicMock(),
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
        patch("sprachassistent.main.MicrophoneStream"),
        patch("sprachassistent.main.AudioPlayer"),
        patch("sprachassistent.main.TerminalUI"),
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
        patch("sprachassistent.main.MicrophoneStream"),
        patch("sprachassistent.main.AudioPlayer"),
        patch("sprachassistent.main.TerminalUI"),
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

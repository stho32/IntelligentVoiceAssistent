"""Tests for the main loop (all components mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from sprachassistent.main import create_components, run_loop


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

"""Integration tests for the full voice assistant pipeline.

All external services (OpenAI, Claude Code, PyAudio) are mocked.
Tests verify that components connect correctly end-to-end.
"""

import wave
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from sprachassistent.main import run_loop

SOUNDS_DIR = Path(__file__).parent.parent / "sprachassistent" / "audio" / "sounds"


def test_ding_wav_exists():
    """The ding.wav confirmation sound file must exist."""
    ding_path = SOUNDS_DIR / "ding.wav"
    assert ding_path.exists(), "ding.wav not found - run scripts/generate_ding.py"


def test_ding_wav_is_valid():
    """ding.wav is a valid WAV file with correct format."""
    ding_path = SOUNDS_DIR / "ding.wav"
    with wave.open(str(ding_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() > 0


def _make_mock_components():
    """Create mock components for integration tests."""
    return {
        "wake_word": MagicMock(),
        "recorder": MagicMock(),
        "transcriber": MagicMock(),
        "ai_backend": MagicMock(),
        "tts": MagicMock(),
    }


def test_pipeline_wake_word_to_response():
    """Full pipeline: wake word -> record -> transcribe -> AI -> TTS."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    # Simulate: wake word on first chunk, then exit
    cycle = [0]

    def wake_word_effect(chunk):
        cycle[0] += 1
        if cycle[0] == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = np.zeros(16000, dtype=np.int16).tobytes()
    components["transcriber"].transcribe.return_value = "Schreibe eine Notiz"
    components["ai_backend"].ask.return_value = "Ich habe die Notiz erstellt."

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    # Verify full pipeline execution
    components["recorder"].start.assert_called_once()
    components["transcriber"].transcribe.assert_called_once()
    components["ai_backend"].ask.assert_called_once_with("Schreibe eine Notiz")
    components["tts"].speak.assert_called_once()

    # Verify UI state transitions happened
    state_calls = [c.args[0].value for c in ui.set_state.call_args_list]
    assert "listening" in state_calls
    assert "recording" in state_calls
    assert "processing" in state_calls
    assert "speaking" in state_calls


def test_pipeline_empty_transcription_skips_ai():
    """Empty transcription should skip AI and TTS."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    cycle = [0]

    def wake_word_effect(chunk):
        cycle[0] += 1
        if cycle[0] == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = np.zeros(16000, dtype=np.int16).tobytes()
    components["transcriber"].transcribe.return_value = ""  # empty transcription

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    components["ai_backend"].ask.assert_not_called()
    components["tts"].speak.assert_not_called()


def test_pipeline_ai_error_recovers():
    """AI errors don't crash the pipeline."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    cycle = [0]

    def wake_word_effect(chunk):
        cycle[0] += 1
        if cycle[0] == 1:
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = np.zeros(16000, dtype=np.int16).tobytes()
    components["transcriber"].transcribe.return_value = "Test"
    components["ai_backend"].ask.side_effect = RuntimeError("AI unavailable")

    with pytest.raises(KeyboardInterrupt):
        run_loop(components, mic, player, ui)

    # TTS should not be called since AI failed
    components["tts"].speak.assert_not_called()

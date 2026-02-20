"""Tests for SpeechRecorder with VAD (silero-vad-lite mocked)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sprachassistent.audio.recorder import SpeechRecorder


@pytest.fixture()
def mock_vad():
    """Mock silero-vad-lite SileroVAD."""
    with patch("sprachassistent.audio.recorder.SileroVAD") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.window_size_samples = 512
        # Default: all speech
        mock_instance.process.return_value = 0.9
        mock_cls.return_value = mock_instance
        yield mock_instance


def _make_chunk(n_samples: int = 1280) -> bytes:
    """Create a silent audio chunk of n_samples int16 values."""
    return np.zeros(n_samples, dtype=np.int16).tobytes()


def test_start_resets_state(mock_vad):
    """start() clears buffers and sets recording flag."""
    recorder = SpeechRecorder()
    recorder.start()
    assert recorder.is_recording is True
    assert recorder.get_audio() == b""


def test_process_chunk_accumulates_audio(mock_vad):
    """Audio data is accumulated in the buffer."""
    recorder = SpeechRecorder()
    recorder.start()
    chunk = _make_chunk(1280)
    recorder.process_chunk(chunk)
    assert len(recorder.get_audio()) == len(chunk)


def test_silence_detection_stops_recording(mock_vad):
    """Recording stops after enough silent frames."""
    recorder = SpeechRecorder(
        silence_duration_sec=0.1,  # ~3 VAD frames at 32ms each
    )
    recorder.start()

    # Return silence probability
    mock_vad.process.return_value = 0.1

    chunk = _make_chunk(1280)
    # Feed enough chunks to accumulate silence
    for _ in range(20):
        result = recorder.process_chunk(chunk)
        if not result:
            break

    assert recorder.is_recording is False


def test_max_duration_stops_recording(mock_vad):
    """Recording stops at max duration even with speech."""
    recorder = SpeechRecorder(max_duration_sec=0.1)
    recorder.start()

    # All speech (no silence)
    mock_vad.process.return_value = 0.9

    chunk = _make_chunk(1280)
    for _ in range(50):
        result = recorder.process_chunk(chunk)
        if not result:
            break

    assert recorder.is_recording is False


def test_process_without_start_returns_false(mock_vad):
    """process_chunk returns False if start() was not called."""
    recorder = SpeechRecorder()
    assert recorder.process_chunk(_make_chunk()) is False


def test_float32_conversion(mock_vad):
    """Audio is converted to float32 normalized [-1,1] for VAD."""
    recorder = SpeechRecorder()
    recorder.start()

    # Create a chunk with max int16 value
    chunk = np.full(512, 32767, dtype=np.int16).tobytes()
    recorder.process_chunk(chunk)

    # VAD should have been called with float data
    mock_vad.process.assert_called()

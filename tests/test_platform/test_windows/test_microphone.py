"""Tests for WindowsMicrophoneStream (sounddevice mocked)."""

import sys
from unittest.mock import MagicMock

import pytest

# Ensure sounddevice is available as a mock for the initial import
if "sounddevice" not in sys.modules:
    sys.modules["sounddevice"] = MagicMock()

import sprachassistent.platform.windows.microphone as _mic_mod  # noqa: E402
from sprachassistent.platform.windows.microphone import WindowsMicrophoneStream  # noqa: E402


@pytest.fixture(autouse=True)
def mock_sd(monkeypatch):
    """Patch the sd module reference inside the microphone module."""
    sd = MagicMock()
    sd.InputStream = MagicMock()
    monkeypatch.setattr(_mic_mod, "sd", sd)
    return sd


def test_context_manager_opens_and_closes_stream(mock_sd):
    """__enter__ starts an InputStream, __exit__ stops and closes it."""
    mock_stream = MagicMock()
    mock_sd.InputStream.return_value = mock_stream

    with WindowsMicrophoneStream(rate=16000, channels=1, chunk_size=1280):
        mock_sd.InputStream.assert_called_once()
        mock_stream.start.assert_called_once()

    mock_stream.stop.assert_called_once()
    mock_stream.close.assert_called_once()


def test_read_chunk_returns_bytes_from_queue(mock_sd):
    """read_chunk() returns bytes pushed by the callback."""
    mock_stream = MagicMock()
    mock_sd.InputStream.return_value = mock_stream

    mic = WindowsMicrophoneStream(rate=16000, channels=1, chunk_size=1280)
    with mic:
        # Simulate the callback pushing data
        mic._queue.put(b"\x00" * 2560)
        chunk = mic.read_chunk()
        assert chunk == b"\x00" * 2560


def test_read_chunk_without_open_raises():
    """read_chunk() raises RuntimeError if stream is not open."""
    mic = WindowsMicrophoneStream()
    with pytest.raises(RuntimeError, match="not open"):
        mic.read_chunk()


def test_properties():
    """Rate, channels, and chunk_size are stored as properties."""
    mic = WindowsMicrophoneStream(rate=44100, channels=2, chunk_size=512)
    assert mic.rate == 44100
    assert mic.channels == 2
    assert mic.chunk_size == 512


def test_open_failure_raises_audio_error(mock_sd):
    """AudioError is raised if InputStream fails to open."""
    from sprachassistent.exceptions import AudioError

    mock_sd.InputStream.side_effect = RuntimeError("No device")

    mic = WindowsMicrophoneStream()
    with pytest.raises(AudioError, match="Failed to open microphone"):
        mic.__enter__()

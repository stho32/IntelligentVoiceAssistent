"""Tests for MicrophoneStream (all hardware mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from sprachassistent.audio.microphone import MicrophoneStream


@pytest.fixture()
def mock_pyaudio():
    """Mock PyAudio and its stream."""
    with patch("sprachassistent.audio.microphone.pyaudio") as mock_pa_module:
        mock_pa = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"\x00" * 2560  # 1280 frames * 2 bytes
        mock_pa.open.return_value = mock_stream
        mock_pa_module.PyAudio.return_value = mock_pa
        mock_pa_module.paInt16 = 8  # pyaudio.paInt16 constant
        yield {"module": mock_pa_module, "pa": mock_pa, "stream": mock_stream}


def test_init_defaults():
    """MicrophoneStream initializes with correct defaults."""
    mic = MicrophoneStream()
    assert mic.rate == 16000
    assert mic.channels == 1
    assert mic.chunk_size == 1280


def test_context_manager_opens_stream(mock_pyaudio):
    """Entering context opens a PyAudio stream."""
    with MicrophoneStream() as mic:
        assert mic._stream is not None
        mock_pyaudio["pa"].open.assert_called_once()


def test_context_manager_closes_stream(mock_pyaudio):
    """Exiting context stops and closes the stream."""
    with MicrophoneStream():
        pass
    mock_pyaudio["stream"].stop_stream.assert_called_once()
    mock_pyaudio["stream"].close.assert_called_once()
    mock_pyaudio["pa"].terminate.assert_called_once()


def test_read_chunk_returns_bytes(mock_pyaudio):
    """read_chunk returns bytes from the stream."""
    with MicrophoneStream() as mic:
        data = mic.read_chunk()
        assert isinstance(data, bytes)
        assert len(data) == 2560


def test_read_chunk_without_context_raises():
    """read_chunk raises RuntimeError when stream is not open."""
    mic = MicrophoneStream()
    with pytest.raises(RuntimeError, match="not open"):
        mic.read_chunk()


def test_close_is_idempotent(mock_pyaudio):
    """Calling close multiple times does not raise."""
    mic = MicrophoneStream()
    mic.__enter__()
    mic.close()
    mic.close()  # should not raise

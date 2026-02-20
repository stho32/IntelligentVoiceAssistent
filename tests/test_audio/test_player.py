"""Tests for AudioPlayer (PyAudio mocked)."""

import struct
import wave
from unittest.mock import MagicMock, patch

import pytest

from sprachassistent.audio.player import AudioPlayer


@pytest.fixture()
def mock_pyaudio():
    """Mock PyAudio for playback tests."""
    with patch("sprachassistent.audio.player.pyaudio") as mock_mod:
        mock_pa = MagicMock()
        mock_stream = MagicMock()
        mock_pa.open.return_value = mock_stream
        mock_pa.get_format_from_width.return_value = 8  # paInt16
        mock_mod.PyAudio.return_value = mock_pa
        mock_mod.paInt16 = 8
        yield {"module": mock_mod, "pa": mock_pa, "stream": mock_stream}


def test_context_manager(mock_pyaudio):
    """AudioPlayer creates and terminates PyAudio."""
    with AudioPlayer():
        pass
    mock_pyaudio["pa"].terminate.assert_called_once()


def test_play_wav(mock_pyaudio, tmp_path):
    """play_wav opens and plays a WAV file."""
    # Create a minimal WAV file
    wav_path = tmp_path / "test.wav"
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(struct.pack("<h", 0) * 100)

    with AudioPlayer() as player:
        player.play_wav(wav_path)

    mock_pyaudio["pa"].open.assert_called_once()
    mock_pyaudio["stream"].write.assert_called()
    mock_pyaudio["stream"].close.assert_called_once()


def test_play_wav_not_open():
    """play_wav raises RuntimeError when player is not open."""
    player = AudioPlayer()
    with pytest.raises(RuntimeError, match="not open"):
        player.play_wav("nonexistent.wav")


def test_play_wav_file_not_found(mock_pyaudio):
    """play_wav raises FileNotFoundError for missing files."""
    with AudioPlayer() as player:
        with pytest.raises(FileNotFoundError):
            player.play_wav("/nonexistent/file.wav")


def test_play_pcm(mock_pyaudio):
    """play_pcm writes PCM data to an output stream."""
    pcm_data = b"\x00" * 4800  # some PCM bytes

    with AudioPlayer() as player:
        player.play_pcm(pcm_data, rate=24000)

    mock_pyaudio["stream"].write.assert_called_once_with(pcm_data)
    mock_pyaudio["stream"].close.assert_called_once()


def test_open_pcm_stream(mock_pyaudio):
    """open_pcm_stream returns a PyAudio output stream."""
    with AudioPlayer() as player:
        stream = player.open_pcm_stream(rate=24000)
        assert stream is not None

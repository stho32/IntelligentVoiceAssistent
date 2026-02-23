"""Tests for WindowsAudioPlayer and _SoundDevicePcmStream (sounddevice mocked)."""

import sys
from unittest.mock import MagicMock

import pytest

# Ensure sounddevice is available as a mock for the initial import
if "sounddevice" not in sys.modules:
    sys.modules["sounddevice"] = MagicMock()

import numpy as np  # noqa: E402

import sprachassistent.platform.windows.player as _player_mod  # noqa: E402
from sprachassistent.platform.windows.player import (  # noqa: E402
    WindowsAudioPlayer,
    _SoundDevicePcmStream,
)


@pytest.fixture(autouse=True)
def mock_sd(monkeypatch):
    """Patch the sd module reference inside the player module."""
    sd = MagicMock()
    sd.OutputStream = MagicMock()
    sd.play = MagicMock()
    sd.wait = MagicMock()
    monkeypatch.setattr(_player_mod, "sd", sd)
    return sd


class TestSoundDevicePcmStream:
    def test_write_sends_int16_array(self, mock_sd):
        mock_stream = MagicMock()
        mock_sd.OutputStream.return_value = mock_stream

        stream = _SoundDevicePcmStream(rate=24000, channels=1)
        data = b"\x00\x01" * 512
        stream.write(data)

        mock_stream.write.assert_called_once()
        written = mock_stream.write.call_args[0][0]
        assert written.dtype == np.int16

    def test_stop_stream_and_close(self, mock_sd):
        mock_stream = MagicMock()
        mock_sd.OutputStream.return_value = mock_stream

        stream = _SoundDevicePcmStream(rate=24000, channels=1)
        stream.stop_stream()
        stream.close()

        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()


class TestWindowsAudioPlayer:
    def test_context_manager(self):
        with WindowsAudioPlayer() as player:
            assert player is not None

    def test_play_wav_streams_via_output_stream(self, tmp_path, mock_sd):
        """play_wav streams audio chunks through an sd.OutputStream."""
        import wave

        wav_path = tmp_path / "test.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 3200)

        mock_stream = MagicMock()
        mock_sd.OutputStream.return_value = mock_stream

        player = WindowsAudioPlayer()
        player.play_wav(wav_path)

        mock_sd.OutputStream.assert_called_once_with(
            samplerate=16000, channels=1, dtype="int16"
        )
        mock_stream.start.assert_called_once()
        assert mock_stream.write.call_count >= 1
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()

    def test_play_wav_missing_file_raises(self):
        player = WindowsAudioPlayer()
        with pytest.raises(FileNotFoundError):
            player.play_wav("/nonexistent/file.wav")

    def test_play_pcm_streams_via_output_stream(self, mock_sd):
        mock_stream = MagicMock()
        mock_sd.OutputStream.return_value = mock_stream

        player = WindowsAudioPlayer()
        data = b"\x00\x01" * 512
        player.play_pcm(data, rate=24000, channels=1)

        mock_sd.OutputStream.assert_called_once_with(
            samplerate=24000, channels=1, dtype="int16"
        )
        mock_stream.start.assert_called_once()
        mock_stream.write.assert_called_once()
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()

    def test_open_pcm_stream_returns_stream(self, mock_sd):
        mock_stream = MagicMock()
        mock_sd.OutputStream.return_value = mock_stream

        player = WindowsAudioPlayer()
        stream = player.open_pcm_stream(rate=24000, channels=1)

        assert isinstance(stream, _SoundDevicePcmStream)
        mock_sd.OutputStream.assert_called_once()

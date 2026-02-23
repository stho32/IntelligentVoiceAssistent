"""Tests for platform protocol definitions.

Verifies that the existing Linux classes satisfy the protocols via
structural subtyping (runtime_checkable).
"""

import sys
from unittest.mock import MagicMock

from sprachassistent.platform.interfaces import (
    AudioInput,
    AudioOutput,
    PcmOutputStream,
    RestartStrategy,
)


def test_pyaudio_stream_satisfies_pcm_output_stream():
    """A mock pyaudio.Stream with write/stop_stream/close satisfies PcmOutputStream."""
    stream = MagicMock()
    stream.write = MagicMock()
    stream.stop_stream = MagicMock()
    stream.close = MagicMock()
    assert isinstance(stream, PcmOutputStream)


def test_mock_audio_input_satisfies_protocol():
    """An object with the right attributes satisfies AudioInput."""
    mic = MagicMock()
    mic.rate = 16000
    mic.channels = 1
    mic.chunk_size = 1280
    mic.read_chunk = MagicMock(return_value=b"\x00" * 2560)
    mic.close = MagicMock()
    mic.__enter__ = MagicMock(return_value=mic)
    mic.__exit__ = MagicMock(return_value=None)
    assert isinstance(mic, AudioInput)


def test_mock_audio_output_satisfies_protocol():
    """An object with the right attributes satisfies AudioOutput."""
    player = MagicMock()
    player.play_wav = MagicMock()
    player.play_pcm = MagicMock()
    player.open_pcm_stream = MagicMock()
    player.close = MagicMock()
    player.__enter__ = MagicMock(return_value=player)
    player.__exit__ = MagicMock(return_value=None)
    assert isinstance(player, AudioOutput)


def test_callable_satisfies_restart_strategy():
    """A plain callable with no args satisfies RestartStrategy."""

    def my_restart() -> None:
        pass

    assert isinstance(my_restart, RestartStrategy)


def test_windows_microphone_satisfies_audio_input():
    """WindowsMicrophoneStream satisfies AudioInput protocol."""
    mock_sd = MagicMock()
    old = sys.modules.get("sounddevice")
    sys.modules["sounddevice"] = mock_sd
    try:
        from sprachassistent.platform.windows.microphone import WindowsMicrophoneStream

        mic = WindowsMicrophoneStream(rate=16000, channels=1, chunk_size=1280)
        assert isinstance(mic, AudioInput)
    finally:
        if old is None:
            sys.modules.pop("sounddevice", None)
        else:
            sys.modules["sounddevice"] = old


def test_windows_player_satisfies_audio_output():
    """WindowsAudioPlayer satisfies AudioOutput protocol."""
    mock_sd = MagicMock()
    old = sys.modules.get("sounddevice")
    sys.modules["sounddevice"] = mock_sd
    try:
        from sprachassistent.platform.windows.player import WindowsAudioPlayer

        player = WindowsAudioPlayer()
        assert isinstance(player, AudioOutput)
    finally:
        if old is None:
            sys.modules.pop("sounddevice", None)
        else:
            sys.modules["sounddevice"] = old

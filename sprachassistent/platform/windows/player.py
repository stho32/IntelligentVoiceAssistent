"""Windows audio playback using sounddevice."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


class _SoundDevicePcmStream:
    """Wraps a ``sounddevice.OutputStream`` to match the ``PcmOutputStream`` protocol."""

    def __init__(self, rate: int = 24000, channels: int = 1):
        self._stream = sd.OutputStream(
            samplerate=rate,
            channels=channels,
            dtype="int16",
        )
        self._stream.start()

    def write(self, data: bytes) -> None:
        """Write raw PCM bytes to the output stream."""
        samples = np.frombuffer(data, dtype=np.int16)
        self._stream.write(samples)

    def stop_stream(self) -> None:
        """Stop the output stream."""
        self._stream.stop()

    def close(self) -> None:
        """Close the output stream and release resources."""
        self._stream.close()


class WindowsAudioPlayer:
    """Audio output using sounddevice (PortAudio/WASAPI).

    Usage::

        with WindowsAudioPlayer() as player:
            player.play_wav("sounds/ding.wav")
            player.play_pcm(pcm_bytes, rate=24000)
    """

    def __enter__(self) -> WindowsAudioPlayer:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def play_wav(self, path: str | Path) -> None:
        """Play a WAV file through the speakers.

        Uses an explicit ``sd.OutputStream`` instead of the convenience
        ``sd.play()`` to avoid global-state issues when switching sample
        rates between different WAV files (e.g. 16 kHz ding followed by
        44.1 kHz processing signal).

        Args:
            path: Path to the WAV file.

        Raises:
            FileNotFoundError: If the WAV file does not exist.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"WAV file not found: {path}")

        with wave.open(str(path), "rb") as wf:
            rate = wf.getframerate()
            channels = wf.getnchannels()
            chunk_frames = 1024

            stream = sd.OutputStream(
                samplerate=rate,
                channels=channels,
                dtype="int16",
            )
            stream.start()
            try:
                data = wf.readframes(chunk_frames)
                while len(data) > 0:
                    samples = np.frombuffer(data, dtype=np.int16).copy()
                    if channels > 1:
                        samples = samples.reshape(-1, channels)
                    stream.write(samples)
                    data = wf.readframes(chunk_frames)
            finally:
                stream.stop()
                stream.close()

    def play_pcm(self, data: bytes, rate: int = 24000, channels: int = 1) -> None:
        """Play raw PCM audio (int16, little-endian).

        Args:
            data: Raw PCM bytes.
            rate: Sample rate in Hz.
            channels: Number of audio channels.
        """
        samples = np.frombuffer(data, dtype=np.int16).copy()
        if channels > 1:
            samples = samples.reshape(-1, channels)
        stream = sd.OutputStream(samplerate=rate, channels=channels, dtype="int16")
        stream.start()
        try:
            stream.write(samples)
        finally:
            stream.stop()
            stream.close()

    def open_pcm_stream(self, rate: int = 24000, channels: int = 1) -> _SoundDevicePcmStream:
        """Open a raw PCM output stream for streaming playback.

        Args:
            rate: Sample rate in Hz.
            channels: Number of audio channels.

        Returns:
            A stream object with write/stop_stream/close methods.
        """
        return _SoundDevicePcmStream(rate=rate, channels=channels)

    def close(self) -> None:
        """Release resources (no-op for sounddevice)."""

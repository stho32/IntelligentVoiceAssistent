"""Audio playback using PyAudio.

Plays WAV files and raw PCM streams through the system speakers.
"""

import wave
from pathlib import Path

import pyaudio


class AudioPlayer:
    """Audio output using PyAudio.

    Usage::

        with AudioPlayer() as player:
            player.play_wav("sounds/ding.wav")
            player.play_pcm(pcm_bytes, rate=24000)
    """

    def __init__(self):
        self._pa: pyaudio.PyAudio | None = None

    def __enter__(self) -> "AudioPlayer":
        self._pa = pyaudio.PyAudio()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
        return None

    def play_wav(self, path: str | Path) -> None:
        """Play a WAV file through the speakers.

        Args:
            path: Path to the WAV file.

        Raises:
            RuntimeError: If the player is not open.
            FileNotFoundError: If the WAV file does not exist.
        """
        if self._pa is None:
            raise RuntimeError("AudioPlayer is not open. Use as context manager.")

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"WAV file not found: {path}")

        with wave.open(str(path), "rb") as wf:
            stream = self._pa.open(
                format=self._pa.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )
            try:
                chunk_size = 1024
                data = wf.readframes(chunk_size)
                while data:
                    stream.write(data)
                    data = wf.readframes(chunk_size)
            finally:
                stream.stop_stream()
                stream.close()

    def play_pcm(self, data: bytes, rate: int = 24000, channels: int = 1) -> None:
        """Play raw PCM audio (int16, little-endian).

        Args:
            data: Raw PCM bytes.
            rate: Sample rate in Hz.
            channels: Number of audio channels.

        Raises:
            RuntimeError: If the player is not open.
        """
        if self._pa is None:
            raise RuntimeError("AudioPlayer is not open. Use as context manager.")

        stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            output=True,
        )
        try:
            stream.write(data)
        finally:
            stream.stop_stream()
            stream.close()

    def open_pcm_stream(self, rate: int = 24000, channels: int = 1) -> pyaudio.Stream:
        """Open a raw PCM output stream for streaming playback.

        The caller is responsible for writing data and closing the stream.

        Args:
            rate: Sample rate in Hz.
            channels: Number of audio channels.

        Returns:
            PyAudio output stream.
        """
        if self._pa is None:
            raise RuntimeError("AudioPlayer is not open. Use as context manager.")

        return self._pa.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            output=True,
        )

    def close(self) -> None:
        """Release PyAudio resources."""
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None

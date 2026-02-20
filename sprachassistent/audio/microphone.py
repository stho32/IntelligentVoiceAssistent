"""PyAudio-based microphone stream as a context manager.

Provides a clean interface for reading audio chunks from the
system default microphone.
"""

import pyaudio

from sprachassistent.exceptions import AudioError
from sprachassistent.utils.logging import get_logger

log = get_logger("audio.microphone")


class MicrophoneStream:
    """Microphone input stream using PyAudio.

    Usage::

        with MicrophoneStream(rate=16000, chunk_size=1280) as mic:
            data = mic.read_chunk()  # returns bytes (int16 PCM)
    """

    def __init__(
        self,
        rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1280,
        audio_format: int = pyaudio.paInt16,
    ):
        self.rate = rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.audio_format = audio_format
        self._pa: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None

    def __enter__(self) -> "MicrophoneStream":
        try:
            self._pa = pyaudio.PyAudio()
            self._stream = self._pa.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk_size,
            )
        except Exception as e:
            self.close()
            raise AudioError(f"Failed to open microphone: {e}") from e
        log.info("Microphone stream opened (rate=%d, chunk=%d)", self.rate, self.chunk_size)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
        return None

    def read_chunk(self) -> bytes:
        """Read one chunk of audio data from the microphone.

        Returns:
            Raw PCM bytes (int16, mono).

        Raises:
            RuntimeError: If the stream is not open.
        """
        if self._stream is None:
            raise RuntimeError("MicrophoneStream is not open. Use as context manager.")
        return self._stream.read(self.chunk_size, exception_on_overflow=False)

    def close(self) -> None:
        """Stop and clean up the audio stream."""
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None

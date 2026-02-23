"""Windows microphone input using sounddevice."""

from __future__ import annotations

import queue

import sounddevice as sd

from sprachassistent.exceptions import AudioError
from sprachassistent.utils.logging import get_logger

log = get_logger("platform.windows.microphone")


class WindowsMicrophoneStream:
    """Microphone input stream using sounddevice (PortAudio/WASAPI).

    Usage::

        with WindowsMicrophoneStream(rate=16000, chunk_size=1280) as mic:
            data = mic.read_chunk()  # returns bytes (int16 PCM)
    """

    def __init__(
        self,
        rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1280,
    ):
        self.rate = rate
        self.channels = channels
        self.chunk_size = chunk_size
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        """Called by sounddevice for each audio block."""
        self._queue.put(bytes(indata))

    def __enter__(self) -> WindowsMicrophoneStream:
        try:
            self._stream = sd.InputStream(
                samplerate=self.rate,
                channels=self.channels,
                dtype="int16",
                blocksize=self.chunk_size,
                callback=self._callback,
            )
            self._stream.start()
        except Exception as e:
            self.close()
            raise AudioError(f"Failed to open microphone: {e}") from e
        log.info("Microphone stream opened (rate=%d, chunk=%d)", self.rate, self.chunk_size)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def read_chunk(self) -> bytes:
        """Read one chunk of audio data from the microphone.

        Returns:
            Raw PCM bytes (int16, mono).

        Raises:
            RuntimeError: If the stream is not open.
        """
        if self._stream is None:
            raise RuntimeError("WindowsMicrophoneStream is not open. Use as context manager.")
        return self._queue.get()

    def close(self) -> None:
        """Stop and clean up the audio stream."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

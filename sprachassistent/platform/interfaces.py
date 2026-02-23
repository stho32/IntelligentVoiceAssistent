"""Platform-agnostic protocols for audio I/O and process management.

These protocols use structural subtyping so that existing classes
(e.g. ``pyaudio.Stream``, ``MicrophoneStream``, ``AudioPlayer``)
satisfy them without modification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class PcmOutputStream(Protocol):
    """Writable PCM audio output stream.

    Must support ``write``, ``stop_stream``, and ``close`` -- the same
    interface exposed by ``pyaudio.Stream``.
    """

    def write(self, data: bytes) -> None:  # noqa: D401
        """Write raw PCM bytes to the stream."""
        ...

    def stop_stream(self) -> None:
        """Stop playback on the stream."""
        ...

    def close(self) -> None:
        """Release stream resources."""
        ...


@runtime_checkable
class AudioInput(Protocol):
    """Microphone / audio capture device.

    Must be usable as a context manager and expose ``read_chunk``.
    """

    rate: int
    channels: int
    chunk_size: int

    def __enter__(self) -> AudioInput: ...

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None: ...

    def read_chunk(self) -> bytes:
        """Read one chunk of PCM audio (int16, mono)."""
        ...

    def close(self) -> None:
        """Release hardware resources."""
        ...


@runtime_checkable
class AudioOutput(Protocol):
    """Speaker / audio playback device.

    Must be usable as a context manager and expose WAV/PCM playback
    plus a streaming PCM output.
    """

    def __enter__(self) -> AudioOutput: ...

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None: ...

    def play_wav(self, path: str | Path) -> None:
        """Play a WAV file through the speakers."""
        ...

    def play_pcm(self, data: bytes, rate: int = 24000, channels: int = 1) -> None:
        """Play raw PCM audio (int16, little-endian)."""
        ...

    def open_pcm_stream(self, rate: int = 24000, channels: int = 1) -> PcmOutputStream:
        """Open a raw PCM output stream for streaming playback."""
        ...

    def close(self) -> None:
        """Release hardware resources."""
        ...


@runtime_checkable
class RestartStrategy(Protocol):
    """Callable that restarts the assistant process."""

    def __call__(self) -> None:
        """Restart the current process."""
        ...

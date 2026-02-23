"""Platform detection and factory functions.

All platform-specific imports are lazy so that Linux-only dependencies
are never loaded on Windows and vice versa.
"""

from __future__ import annotations

import sys

from sprachassistent.platform.interfaces import AudioInput, AudioOutput, RestartStrategy


def detect_platform() -> str:
    """Detect the current operating system.

    Returns:
        ``"linux"`` or ``"windows"``.

    Raises:
        RuntimeError: If the platform is unsupported.
    """
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "win32":
        return "windows"
    raise RuntimeError(f"Unsupported platform: {sys.platform}")


def create_audio_input(
    rate: int = 16000,
    channels: int = 1,
    chunk_size: int = 1280,
    platform: str | None = None,
) -> AudioInput:
    """Create a platform-appropriate microphone input.

    Args:
        rate: Sample rate in Hz.
        channels: Number of audio channels.
        chunk_size: Frames per read chunk.
        platform: Override auto-detection (``"linux"`` or ``"windows"``).

    Returns:
        An :class:`AudioInput` implementation.
    """
    platform = platform or detect_platform()

    if platform == "linux":
        from sprachassistent.audio.microphone import MicrophoneStream

        return MicrophoneStream(rate=rate, channels=channels, chunk_size=chunk_size)

    if platform == "windows":
        from sprachassistent.platform.windows.microphone import WindowsMicrophoneStream

        return WindowsMicrophoneStream(rate=rate, channels=channels, chunk_size=chunk_size)

    raise RuntimeError(f"Unsupported platform: {platform}")


def create_audio_output(platform: str | None = None) -> AudioOutput:
    """Create a platform-appropriate audio player.

    Args:
        platform: Override auto-detection (``"linux"`` or ``"windows"``).

    Returns:
        An :class:`AudioOutput` implementation.
    """
    platform = platform or detect_platform()

    if platform == "linux":
        from sprachassistent.audio.player import AudioPlayer

        return AudioPlayer()

    if platform == "windows":
        from sprachassistent.platform.windows.player import WindowsAudioPlayer

        return WindowsAudioPlayer()

    raise RuntimeError(f"Unsupported platform: {platform}")


def create_restart_strategy(platform: str | None = None) -> RestartStrategy:
    """Create a platform-appropriate restart callable.

    Args:
        platform: Override auto-detection (``"linux"`` or ``"windows"``).

    Returns:
        A callable that restarts the assistant process.
    """
    platform = platform or detect_platform()

    if platform == "linux":
        from sprachassistent.platform._linux_restart import linux_restart

        return linux_restart

    if platform == "windows":
        from sprachassistent.platform.windows.restart import windows_restart

        return windows_restart

    raise RuntimeError(f"Unsupported platform: {platform}")

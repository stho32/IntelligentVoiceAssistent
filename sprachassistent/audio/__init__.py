"""Audio subsystem: microphone input, wake-word detection, recording, playback."""

from sprachassistent.audio.microphone import MicrophoneStream
from sprachassistent.audio.wake_word import WakeWordDetector

__all__ = ["MicrophoneStream", "WakeWordDetector"]

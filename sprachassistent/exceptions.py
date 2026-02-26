"""Custom exception hierarchy for the voice assistant."""


class AssistantError(Exception):
    """Base exception for all voice assistant errors."""


class AudioError(AssistantError):
    """Errors related to audio input/output."""


class WakeWordError(AssistantError):
    """Errors related to wake-word detection."""


class RecordingError(AssistantError):
    """Errors during speech recording."""


class TranscriptionError(AssistantError):
    """Errors during speech-to-text transcription."""


class AIBackendError(AssistantError):
    """Errors from the AI backend (Claude Code)."""


class TTSError(AssistantError):
    """Errors during text-to-speech synthesis."""


class ConfigError(AssistantError):
    """Errors related to configuration loading."""


class MatrixChatError(AssistantError):
    """Errors related to the Matrix chat integration."""

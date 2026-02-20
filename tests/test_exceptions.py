"""Tests for the exception hierarchy."""

from sprachassistent.exceptions import (
    AIBackendError,
    AssistantError,
    AudioError,
    ConfigError,
    RecordingError,
    TranscriptionError,
    TTSError,
    WakeWordError,
)


def test_all_exceptions_inherit_from_base():
    """All custom exceptions inherit from AssistantError."""
    for exc_class in (
        AudioError,
        WakeWordError,
        RecordingError,
        TranscriptionError,
        AIBackendError,
        TTSError,
        ConfigError,
    ):
        assert issubclass(exc_class, AssistantError)
        assert issubclass(exc_class, Exception)


def test_assistant_error_is_catchable():
    """AssistantError can be caught as a base class."""
    try:
        raise WakeWordError("test")
    except AssistantError as e:
        assert str(e) == "test"


def test_each_exception_carries_message():
    """Each exception correctly stores its message."""
    assert str(AudioError("mic failed")) == "mic failed"
    assert str(TranscriptionError("api timeout")) == "api timeout"
    assert str(AIBackendError("subprocess died")) == "subprocess died"

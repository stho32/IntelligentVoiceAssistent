"""Tests for ChatMessage, AssistantMessage, and related types."""

import pytest

from sprachassistent.chat.message import (
    AssistantMessage,
    ChatMessage,
    InputType,
    MessageSource,
)
from sprachassistent.exceptions import AssistantError, MatrixChatError

# --- ChatMessage (unchanged) ---


def test_chat_message_creation():
    """ChatMessage can be created with all required fields."""
    msg = ChatMessage(
        room_id="!abc:matrix.org",
        sender="@user:matrix.org",
        text="Hello Jarvis",
        timestamp=1700000000000,
        event_id="$event123",
    )
    assert msg.room_id == "!abc:matrix.org"
    assert msg.sender == "@user:matrix.org"
    assert msg.text == "Hello Jarvis"
    assert msg.timestamp == 1700000000000
    assert msg.event_id == "$event123"


def test_chat_message_is_frozen():
    """ChatMessage is immutable (frozen dataclass)."""
    msg = ChatMessage(
        room_id="!abc:matrix.org",
        sender="@user:matrix.org",
        text="Hello",
        timestamp=1700000000000,
        event_id="$event123",
    )
    with pytest.raises(AttributeError):
        msg.text = "Modified"


def test_chat_message_equality():
    """Two ChatMessages with same fields are equal."""
    kwargs = {
        "room_id": "!abc:matrix.org",
        "sender": "@user:matrix.org",
        "text": "Hello",
        "timestamp": 1700000000000,
        "event_id": "$event123",
    }
    assert ChatMessage(**kwargs) == ChatMessage(**kwargs)


def test_matrix_chat_error_inherits_assistant_error():
    """MatrixChatError is a subclass of AssistantError."""
    assert issubclass(MatrixChatError, AssistantError)


def test_matrix_chat_error_can_be_raised():
    """MatrixChatError can be raised and caught."""
    with pytest.raises(MatrixChatError, match="connection failed"):
        raise MatrixChatError("connection failed")


# --- MessageSource ---


def test_message_source_values():
    """MessageSource enum has the expected members."""
    assert MessageSource.VOICE.value == "voice"
    assert MessageSource.KEYBOARD.value == "keyboard"
    assert MessageSource.MATRIX.value == "matrix"


# --- InputType ---


def test_input_type_values():
    """InputType enum has the expected members."""
    assert InputType.TEXT.value == "text"
    assert InputType.AUDIO.value == "audio"


# --- AssistantMessage ---


def test_assistant_message_text():
    """AssistantMessage can be created with TEXT content."""
    msg = AssistantMessage(
        source=MessageSource.KEYBOARD,
        input_type=InputType.TEXT,
        content="Hello world",
    )
    assert msg.source == MessageSource.KEYBOARD
    assert msg.input_type == InputType.TEXT
    assert msg.content == "Hello world"
    assert msg.room_id is None
    assert msg.sender is None
    assert msg.event_id is None


def test_assistant_message_audio():
    """AssistantMessage can be created with AUDIO content."""
    pcm = b"\x00\x01\x02\x03"
    msg = AssistantMessage(
        source=MessageSource.VOICE,
        input_type=InputType.AUDIO,
        content=pcm,
    )
    assert msg.source == MessageSource.VOICE
    assert msg.input_type == InputType.AUDIO
    assert msg.content == pcm


def test_assistant_message_matrix():
    """AssistantMessage carries Matrix-specific fields."""
    msg = AssistantMessage(
        source=MessageSource.MATRIX,
        input_type=InputType.TEXT,
        content="Chat text",
        room_id="!room:matrix.org",
        sender="@user:matrix.org",
        event_id="$evt1",
    )
    assert msg.room_id == "!room:matrix.org"
    assert msg.sender == "@user:matrix.org"
    assert msg.event_id == "$evt1"


def test_assistant_message_is_frozen():
    """AssistantMessage is immutable (frozen dataclass)."""
    msg = AssistantMessage(
        source=MessageSource.VOICE,
        input_type=InputType.TEXT,
        content="test",
    )
    with pytest.raises(AttributeError):
        msg.content = "modified"


def test_assistant_message_equality():
    """Two AssistantMessages with same fields are equal."""
    kwargs = {
        "source": MessageSource.MATRIX,
        "input_type": InputType.TEXT,
        "content": "Hello",
        "room_id": "!room:matrix.org",
        "sender": "@user:matrix.org",
        "event_id": "$evt1",
    }
    assert AssistantMessage(**kwargs) == AssistantMessage(**kwargs)

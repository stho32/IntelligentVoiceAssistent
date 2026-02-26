"""Tests for ChatMessage and MatrixChatError."""

import pytest

from sprachassistent.chat.message import ChatMessage
from sprachassistent.exceptions import AssistantError, MatrixChatError


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

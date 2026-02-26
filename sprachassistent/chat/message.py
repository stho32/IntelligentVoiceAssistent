"""Data classes for chat messages."""

from dataclasses import dataclass
from enum import Enum


class MessageSource(Enum):
    """Origin of an incoming message."""

    VOICE = "voice"
    KEYBOARD = "keyboard"
    MATRIX = "matrix"


class InputType(Enum):
    """Payload type of an incoming message."""

    TEXT = "text"
    AUDIO = "audio"


@dataclass(frozen=True)
class AssistantMessage:
    """Unified message type for the shared work queue.

    All input sources (voice, keyboard, Matrix) produce instances of this
    dataclass.  The worker thread consumes them sequentially.

    Attributes:
        source: Where the message originated.
        input_type: Whether content is text or raw audio bytes.
        content: Text string or raw PCM bytes.
        room_id: Matrix room ID (only set for MATRIX source).
        sender: Matrix sender ID (only set for MATRIX source).
        event_id: Matrix event ID (only set for MATRIX source).
    """

    source: MessageSource
    input_type: InputType
    content: str | bytes
    room_id: str | None = None
    sender: str | None = None
    event_id: str | None = None


@dataclass(frozen=True)
class ChatMessage:
    """An incoming chat message from a Matrix room.

    Attributes:
        room_id: The Matrix room ID the message was sent in.
        sender: The Matrix user ID of the sender.
        text: The message text content.
        timestamp: Server timestamp in milliseconds since epoch.
        event_id: The Matrix event ID for this message.
    """

    room_id: str
    sender: str
    text: str
    timestamp: int
    event_id: str

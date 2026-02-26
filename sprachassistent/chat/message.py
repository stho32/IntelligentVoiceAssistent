"""Data classes for chat messages."""

from dataclasses import dataclass


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

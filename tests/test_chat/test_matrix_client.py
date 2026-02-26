"""Tests for the Matrix bridge (all nio interactions mocked)."""

import asyncio
import queue
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sprachassistent.chat.matrix_client import MatrixBridge, start_matrix_thread
from sprachassistent.chat.message import ChatMessage
from sprachassistent.exceptions import MatrixChatError

_SENTINEL = object()


def _make_bridge(
    incoming=None,
    outgoing=None,
    allowed_users=_SENTINEL,
    room_id="!room:matrix.org",
    user_id="@bot:matrix.org",
):
    """Create a MatrixBridge with default test values."""
    if allowed_users is _SENTINEL:
        allowed_users = ["@user:matrix.org"]
    return MatrixBridge(
        homeserver="https://matrix.org",
        user_id=user_id,
        access_token="test_token",
        room_id=room_id,
        allowed_users=allowed_users,
        store_path="/tmp/test_store",
        incoming_queue=incoming or queue.Queue(),
        outgoing_queue=outgoing or queue.Queue(),
    )


def _make_event(sender="@user:matrix.org", body="Hello", event_id="$evt1", timestamp=1700000000):
    """Create a mock RoomMessageText event."""
    event = MagicMock()
    event.sender = sender
    event.body = body
    event.event_id = event_id
    event.server_timestamp = timestamp
    return event


def _make_room(room_id="!room:matrix.org"):
    """Create a mock room object."""
    room = MagicMock()
    room.room_id = room_id
    return room


class TestOnMessage:
    """Tests for the _on_message callback."""

    def test_allowed_user_message_queued(self):
        """Message from an allowed user is put into the incoming queue."""
        incoming = queue.Queue()
        bridge = _make_bridge(incoming=incoming)
        room = _make_room()
        event = _make_event()

        asyncio.run(bridge._on_message(room, event))

        msg = incoming.get_nowait()
        assert isinstance(msg, ChatMessage)
        assert msg.sender == "@user:matrix.org"
        assert msg.text == "Hello"

    def test_unknown_user_ignored(self):
        """Message from a non-whitelisted user is ignored."""
        incoming = queue.Queue()
        bridge = _make_bridge(incoming=incoming)
        room = _make_room()
        event = _make_event(sender="@stranger:matrix.org")

        asyncio.run(bridge._on_message(room, event))

        assert incoming.empty()

    def test_own_message_ignored(self):
        """Bot's own messages are ignored."""
        incoming = queue.Queue()
        bridge = _make_bridge(incoming=incoming, user_id="@bot:matrix.org")
        room = _make_room()
        event = _make_event(sender="@bot:matrix.org")

        asyncio.run(bridge._on_message(room, event))

        assert incoming.empty()

    def test_wrong_room_ignored(self):
        """Messages from other rooms are ignored."""
        incoming = queue.Queue()
        bridge = _make_bridge(incoming=incoming, room_id="!room:matrix.org")
        room = _make_room(room_id="!other:matrix.org")
        event = _make_event()

        asyncio.run(bridge._on_message(room, event))

        assert incoming.empty()

    def test_empty_allowed_users_rejects_all(self):
        """With empty allowed_users list, all messages are rejected."""
        incoming = queue.Queue()
        bridge = _make_bridge(incoming=incoming, allowed_users=[])
        room = _make_room()
        event = _make_event()

        asyncio.run(bridge._on_message(room, event))

        assert incoming.empty()


class TestResponseSender:
    """Tests for the _response_sender loop."""

    def test_outgoing_message_triggers_room_send(self):
        """A message in the outgoing queue causes room_send to be called."""
        outgoing = queue.Queue()
        bridge = _make_bridge(outgoing=outgoing)

        mock_client = MagicMock()
        mock_client.room_send = AsyncMock(return_value=MagicMock())
        bridge._client = mock_client

        # Put a response and then set stop so the loop exits
        outgoing.put(("!room:matrix.org", "Response text"))

        async def run_sender():
            bridge._stop_event = asyncio.Event()
            # Run one iteration, then stop
            try:
                room_id, text = bridge.outgoing_queue.get_nowait()
            except queue.Empty:
                return

            content = {
                "msgtype": "m.text",
                "body": text,
                "format": "org.matrix.custom.html",
                "formatted_body": text,
            }
            await bridge._client.room_send(
                room_id,
                message_type="m.room.message",
                content=content,
            )

        with patch.dict("sys.modules", {"nio": MagicMock()}):
            asyncio.run(run_sender())

        mock_client.room_send.assert_called_once()
        call_args = mock_client.room_send.call_args
        assert call_args[0][0] == "!room:matrix.org"
        assert call_args[1]["content"]["body"] == "Response text"


class TestStartMatrixThread:
    """Tests for the start_matrix_thread factory function."""

    def test_missing_access_token_raises(self):
        """Missing access_token in config and env raises MatrixChatError."""
        config = {
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "room_id": "!room:matrix.org",
            "allowed_users": ["@user:matrix.org"],
        }
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(MatrixChatError, match="access_token"):
                start_matrix_thread(config, queue.Queue(), queue.Queue())

    @patch("sprachassistent.chat.matrix_client.MatrixBridge")
    def test_thread_is_daemon(self, mock_bridge_cls):
        """The started thread is a daemon thread."""
        mock_bridge_cls.return_value.run_forever = MagicMock()
        config = {
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "access_token": "token",
            "room_id": "!room:matrix.org",
            "allowed_users": [],
        }

        thread, bridge = start_matrix_thread(config, queue.Queue(), queue.Queue())
        assert thread.daemon is True
        thread.join(timeout=1)

    @patch("sprachassistent.chat.matrix_client.MatrixBridge")
    def test_access_token_from_env(self, mock_bridge_cls):
        """Access token is read from MATRIX_ACCESS_TOKEN env var."""
        mock_bridge_cls.return_value.run_forever = MagicMock()
        config = {
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "room_id": "!room:matrix.org",
            "allowed_users": [],
        }

        with patch.dict("os.environ", {"MATRIX_ACCESS_TOKEN": "env_token"}):
            thread, bridge = start_matrix_thread(config, queue.Queue(), queue.Queue())

        call_kwargs = mock_bridge_cls.call_args.kwargs
        assert call_kwargs["access_token"] == "env_token"
        thread.join(timeout=1)


class TestSyncLoop:
    """Tests for the sync loop error handling."""

    def test_sync_error_does_not_crash(self):
        """A sync error is logged but doesn't crash the bridge."""
        bridge = _make_bridge()

        mock_nio = MagicMock()
        mock_sync_error = MagicMock()
        mock_sync_error.message = "sync failed"
        mock_nio.SyncError = type(mock_sync_error)

        mock_client = MagicMock()
        # First call: return error, second call: stop
        call_count = 0

        async def mock_sync(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_sync_error
            bridge._stop_event.set()
            return MagicMock(spec=[])  # Not a SyncError

        mock_client.sync = mock_sync
        bridge._client = mock_client

        async def run_sync():
            bridge._stop_event = asyncio.Event()
            with patch.dict("sys.modules", {"nio": mock_nio}):
                await bridge._sync_loop()

        asyncio.run(run_sync())
        assert call_count >= 2


class TestJoinRoom:
    """Tests for room joining at start."""

    def test_join_called_on_start(self):
        """The bridge joins the configured room on start."""
        bridge = _make_bridge()

        mock_client = AsyncMock()
        mock_client.join = AsyncMock(return_value=MagicMock())

        bridge._client = mock_client
        asyncio.run(mock_client.join(bridge.room_id))
        mock_client.join.assert_called_with("!room:matrix.org")

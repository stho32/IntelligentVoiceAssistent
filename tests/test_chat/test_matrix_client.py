"""Tests for the Matrix bridge (all nio interactions mocked)."""

import asyncio
import os
import queue
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sprachassistent.chat.matrix_client import MatrixBridge, start_matrix_thread
from sprachassistent.chat.message import ChatMessage
from sprachassistent.exceptions import MatrixChatError, TranscriptionError

_SENTINEL = object()


def _make_nio_mock(**overrides):
    """Create a mock nio module with proper types for isinstance checks."""
    mock_nio = MagicMock()
    mock_nio.DownloadError = type("DownloadError", (), {})
    mock_nio.RoomSendError = type("RoomSendError", (), {})
    for key, val in overrides.items():
        setattr(mock_nio, key, val)
    return mock_nio


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

    def test_missing_credentials_raises(self):
        """Missing both access_token and password raises MatrixChatError."""
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

    @patch("sprachassistent.chat.matrix_client.MatrixBridge")
    def test_password_from_config(self, mock_bridge_cls):
        """Password from config is passed to the bridge."""
        mock_bridge_cls.return_value.run_forever = MagicMock()
        config = {
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "password": "secret",
            "room_id": "!room:matrix.org",
            "allowed_users": [],
        }

        with patch.dict("os.environ", {}, clear=True):
            thread, bridge = start_matrix_thread(config, queue.Queue(), queue.Queue())

        call_kwargs = mock_bridge_cls.call_args.kwargs
        assert call_kwargs["password"] == "secret"
        assert call_kwargs["access_token"] == ""
        thread.join(timeout=1)

    @patch("sprachassistent.chat.matrix_client.MatrixBridge")
    def test_password_from_env(self, mock_bridge_cls):
        """MATRIX_PASSWORD env var is passed to the bridge."""
        mock_bridge_cls.return_value.run_forever = MagicMock()
        config = {
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "room_id": "!room:matrix.org",
            "allowed_users": [],
        }

        with patch.dict("os.environ", {"MATRIX_PASSWORD": "env_pass"}, clear=True):
            thread, bridge = start_matrix_thread(config, queue.Queue(), queue.Queue())

        call_kwargs = mock_bridge_cls.call_args.kwargs
        assert call_kwargs["password"] == "env_pass"
        thread.join(timeout=1)


class TestPasswordLogin:
    """Tests for password-based login in start()."""

    def test_login_called_when_password_given(self):
        """When no access_token but password is given, login() is called."""
        bridge = MatrixBridge(
            homeserver="https://matrix.org",
            user_id="@bot:matrix.org",
            access_token="",
            room_id="!room:matrix.org",
            allowed_users=[],
            store_path="/tmp/test_store",
            incoming_queue=queue.Queue(),
            outgoing_queue=queue.Queue(),
            password="secret",
        )

        mock_login_resp = MagicMock()
        mock_login_resp.user_id = "@bot:matrix.org"
        mock_login_resp.device_id = "JARVIS"

        mock_nio = MagicMock()
        mock_nio.LoginError = type("LoginError", (), {})
        mock_client = AsyncMock()
        mock_client.login = AsyncMock(return_value=mock_login_resp)
        mock_client.join = AsyncMock(return_value=MagicMock())
        mock_nio.AsyncClient.return_value = mock_client
        mock_nio.RoomMessageText = MagicMock()

        async def run():
            bridge._stop_event = asyncio.Event()
            bridge._stop_event.set()  # stop immediately after start
            with patch.dict("sys.modules", {"nio": mock_nio}):
                # Patch start to only do the login part, not the sync loops
                import nio

                os.makedirs(bridge.store_path, exist_ok=True)
                bridge._client = nio.AsyncClient(
                    bridge.homeserver, bridge.user_id, store_path=bridge.store_path
                )
                resp = await bridge._client.login(password=bridge.password, device_name="JARVIS")
                assert not isinstance(resp, nio.LoginError)

        asyncio.run(run())
        mock_client.login.assert_called_once_with(password="secret", device_name="JARVIS")

    def test_login_error_raises(self):
        """A failed login raises MatrixChatError."""
        bridge = MatrixBridge(
            homeserver="https://matrix.org",
            user_id="@bot:matrix.org",
            access_token="",
            room_id="!room:matrix.org",
            allowed_users=[],
            store_path="/tmp/test_store",
            incoming_queue=queue.Queue(),
            outgoing_queue=queue.Queue(),
            password="wrong",
        )

        mock_nio = MagicMock()
        mock_login_error = MagicMock()
        mock_login_error.message = "Invalid password"
        mock_nio.LoginError = type(mock_login_error)

        mock_client = AsyncMock()
        mock_client.login = AsyncMock(return_value=mock_login_error)
        mock_nio.AsyncClient.return_value = mock_client
        mock_nio.RoomMessageText = MagicMock()

        async def run():
            with patch.dict("sys.modules", {"nio": mock_nio}):
                await bridge.start()

        with pytest.raises(MatrixChatError, match="login failed"):
            asyncio.run(run())

    def test_token_mode_skips_login(self):
        """When access_token is set, login() is not called."""
        bridge = _make_bridge()

        mock_nio = MagicMock()
        mock_client = AsyncMock()
        mock_client.join = AsyncMock(return_value=MagicMock())
        mock_client.sync = AsyncMock(return_value=MagicMock(spec=[]))
        mock_nio.AsyncClient.return_value = mock_client
        mock_nio.RoomMessageText = MagicMock()

        async def run():
            bridge._stop_event = asyncio.Event()
            with patch.dict("sys.modules", {"nio": mock_nio}):
                import nio

                os.makedirs(bridge.store_path, exist_ok=True)
                bridge._client = nio.AsyncClient(
                    bridge.homeserver, bridge.user_id, store_path=bridge.store_path
                )
                # Simulate token mode: set access_token directly
                bridge._client.access_token = bridge.access_token
                bridge._client.user_id = bridge.user_id
                bridge._client.device_id = bridge._client.device_id or "JARVIS"

        asyncio.run(run())
        mock_client.login.assert_not_called()


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


def _make_audio_event(
    sender="@user:matrix.org",
    body="voice-message.ogg",
    event_id="$audio1",
    timestamp=1700000000,
    url="mxc://matrix.org/audio123",
    file_size=5000,
):
    """Create a mock RoomMessageAudio event."""
    event = MagicMock()
    event.sender = sender
    event.body = body
    event.event_id = event_id
    event.server_timestamp = timestamp
    event.url = url
    event.source = {
        "content": {
            "info": {"size": file_size},
        }
    }
    return event


def _make_audio_bridge(incoming=None, transcriber=None, **kwargs):
    """Create a MatrixBridge with a transcriber and a mock nio client."""
    bridge = _make_bridge(incoming=incoming, **kwargs)
    bridge._transcriber = transcriber
    mock_client = AsyncMock()
    mock_client.room_send = AsyncMock(return_value=MagicMock())
    bridge._client = mock_client
    return bridge


class TestOnAudioMessage:
    """Tests for the _on_audio_message callback."""

    def test_happy_path(self):
        """Audio is transcribed and ChatMessage is enqueued."""
        incoming = queue.Queue()
        transcriber = MagicMock()
        transcriber.transcribe_file.return_value = "Hallo Welt"

        bridge = _make_audio_bridge(incoming=incoming, transcriber=transcriber)
        download_resp = MagicMock()
        download_resp.body = b"\x00\x01\x02"
        bridge._client.download = AsyncMock(return_value=download_resp)

        room = _make_room()
        event = _make_audio_event()

        with patch.dict("sys.modules", {"nio": _make_nio_mock()}):
            asyncio.run(bridge._on_audio_message(room, event))

        msg = incoming.get_nowait()
        assert isinstance(msg, ChatMessage)
        assert msg.text == "Hallo Welt"
        assert msg.sender == "@user:matrix.org"

        # Transcript quote was sent
        bridge._client.room_send.assert_called_once()
        call_kwargs = bridge._client.room_send.call_args
        assert "> Transkript: Hallo Welt" in call_kwargs[1]["content"]["body"]

    def test_wrong_room_ignored(self):
        """Audio from a different room is ignored."""
        incoming = queue.Queue()
        transcriber = MagicMock()
        bridge = _make_audio_bridge(incoming=incoming, transcriber=transcriber)

        room = _make_room(room_id="!other:matrix.org")
        event = _make_audio_event()

        asyncio.run(bridge._on_audio_message(room, event))

        assert incoming.empty()
        transcriber.transcribe_file.assert_not_called()

    def test_own_message_ignored(self):
        """Bot's own audio messages are ignored."""
        incoming = queue.Queue()
        transcriber = MagicMock()
        bridge = _make_audio_bridge(
            incoming=incoming,
            transcriber=transcriber,
            user_id="@bot:matrix.org",
        )

        room = _make_room()
        event = _make_audio_event(sender="@bot:matrix.org")

        asyncio.run(bridge._on_audio_message(room, event))

        assert incoming.empty()
        transcriber.transcribe_file.assert_not_called()

    def test_non_allowed_user_ignored(self):
        """Audio from non-whitelisted user is ignored."""
        incoming = queue.Queue()
        transcriber = MagicMock()
        bridge = _make_audio_bridge(incoming=incoming, transcriber=transcriber)

        room = _make_room()
        event = _make_audio_event(sender="@stranger:matrix.org")

        asyncio.run(bridge._on_audio_message(room, event))

        assert incoming.empty()
        transcriber.transcribe_file.assert_not_called()

    def test_file_too_large(self):
        """Audio over 25 MB is rejected with an error message."""
        incoming = queue.Queue()
        transcriber = MagicMock()
        bridge = _make_audio_bridge(incoming=incoming, transcriber=transcriber)

        room = _make_room()
        event = _make_audio_event(file_size=26 * 1024 * 1024)

        with patch.dict("sys.modules", {"nio": _make_nio_mock()}):
            asyncio.run(bridge._on_audio_message(room, event))

        assert incoming.empty()
        transcriber.transcribe_file.assert_not_called()
        bridge._client.room_send.assert_called_once()
        sent_body = bridge._client.room_send.call_args[1]["content"]["body"]
        assert "zu gross" in sent_body

    def test_download_error(self):
        """Download returning DownloadError sends error message."""
        incoming = queue.Queue()
        transcriber = MagicMock()
        bridge = _make_audio_bridge(incoming=incoming, transcriber=transcriber)

        DownloadError = type("DownloadError", (), {"message": "not found"})
        download_error = DownloadError()
        mock_nio = _make_nio_mock(DownloadError=DownloadError)
        bridge._client.download = AsyncMock(return_value=download_error)

        room = _make_room()
        event = _make_audio_event()

        with patch.dict("sys.modules", {"nio": mock_nio}):
            asyncio.run(bridge._on_audio_message(room, event))

        assert incoming.empty()
        bridge._client.room_send.assert_called_once()
        sent_body = bridge._client.room_send.call_args[1]["content"]["body"]
        assert "Fehler" in sent_body

    def test_download_exception(self):
        """Download raising an exception sends error message."""
        incoming = queue.Queue()
        transcriber = MagicMock()
        bridge = _make_audio_bridge(incoming=incoming, transcriber=transcriber)
        bridge._client.download = AsyncMock(side_effect=RuntimeError("network error"))

        room = _make_room()
        event = _make_audio_event()

        with patch.dict("sys.modules", {"nio": _make_nio_mock()}):
            asyncio.run(bridge._on_audio_message(room, event))

        assert incoming.empty()
        bridge._client.room_send.assert_called_once()

    def test_transcription_error(self):
        """Transcription failure sends error message."""
        incoming = queue.Queue()
        transcriber = MagicMock()
        transcriber.transcribe_file.side_effect = TranscriptionError("API failed")
        bridge = _make_audio_bridge(incoming=incoming, transcriber=transcriber)

        download_resp = MagicMock()
        download_resp.body = b"\x00\x01\x02"
        bridge._client.download = AsyncMock(return_value=download_resp)

        room = _make_room()
        event = _make_audio_event()

        with patch.dict("sys.modules", {"nio": _make_nio_mock()}):
            asyncio.run(bridge._on_audio_message(room, event))

        assert incoming.empty()
        bridge._client.room_send.assert_called_once()
        sent_body = bridge._client.room_send.call_args[1]["content"]["body"]
        assert "Transkription" in sent_body

    def test_empty_transcript(self):
        """Empty transcript sends info message, no ChatMessage enqueued."""
        incoming = queue.Queue()
        transcriber = MagicMock()
        transcriber.transcribe_file.return_value = "   "
        bridge = _make_audio_bridge(incoming=incoming, transcriber=transcriber)

        download_resp = MagicMock()
        download_resp.body = b"\x00\x01\x02"
        bridge._client.download = AsyncMock(return_value=download_resp)

        room = _make_room()
        event = _make_audio_event()

        with patch.dict("sys.modules", {"nio": _make_nio_mock()}):
            asyncio.run(bridge._on_audio_message(room, event))

        assert incoming.empty()
        bridge._client.room_send.assert_called_once()
        sent_body = bridge._client.room_send.call_args[1]["content"]["body"]
        assert "nicht transkribiert" in sent_body

    def test_no_transcriber_no_audio_callback(self):
        """Without a transcriber, no audio callback is registered."""
        bridge = _make_bridge()  # No transcriber

        mock_client = MagicMock()
        mock_nio = MagicMock()
        mock_nio.AsyncClient.return_value = mock_client
        mock_nio.LoginError = type("LoginError", (), {})
        mock_client.join = AsyncMock(return_value=MagicMock())

        async def run():
            bridge._stop_event = asyncio.Event()
            bridge._stop_event.set()
            with patch.dict("sys.modules", {"nio": mock_nio}):
                import nio

                os.makedirs(bridge.store_path, exist_ok=True)
                bridge._client = nio.AsyncClient(
                    bridge.homeserver, bridge.user_id, store_path=bridge.store_path
                )
                bridge._client.access_token = bridge.access_token
                bridge._client.user_id = bridge.user_id
                bridge._client.device_id = bridge._client.device_id or "JARVIS"

                bridge._client.add_event_callback(bridge._on_message, nio.RoomMessageText)
                # Audio callback should NOT be registered
                assert bridge._transcriber is None

        asyncio.run(run())
        # Verify add_event_callback was called only once (for text, not audio)
        calls = mock_client.add_event_callback.call_args_list
        assert len(calls) == 1

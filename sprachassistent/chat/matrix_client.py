"""Matrix chat bridge using matrix-nio.

Runs in a background thread with its own asyncio event loop.
Communicates with the main thread via thread-safe queues.
"""

import asyncio
import os
import queue
import threading
from typing import Any

from sprachassistent.chat.message import AssistantMessage, InputType, MessageSource
from sprachassistent.exceptions import MatrixChatError, TranscriptionError
from sprachassistent.utils.logging import get_logger

log = get_logger("chat.matrix")


class MatrixBridge:
    """Async Matrix client that bridges messages to/from the main thread.

    Supports two authentication modes:
    - Password login: provide ``password`` to call the login API on start.
    - Access token: provide ``access_token`` for pre-authenticated sessions.

    Args:
        homeserver: Matrix homeserver URL (e.g. "https://matrix.org").
        user_id: Bot's Matrix user ID (e.g. "@jarvis:matrix.org").
        room_id: The Matrix room to operate in.
        allowed_users: List of Matrix user IDs allowed to interact with the bot.
        store_path: Path to store E2E encryption keys.
        incoming_queue: Queue for messages from Matrix -> main thread.
        outgoing_queue: Queue for responses from main thread -> Matrix.
        password: Password for login-based authentication (optional if access_token given).
        access_token: Pre-existing access token (optional if password given).
        transcriber: Optional transcriber for audio message support.
    """

    def __init__(
        self,
        homeserver: str,
        user_id: str,
        room_id: str,
        allowed_users: list[str],
        store_path: str,
        incoming_queue: queue.Queue,
        outgoing_queue: queue.Queue,
        *,
        password: str = "",
        access_token: str = "",
        transcriber: Any = None,
        start_timestamp: int = 0,
    ):
        if not access_token and not password:
            raise MatrixChatError("Either password or access_token is required")
        self.homeserver = homeserver
        self.user_id = user_id
        self.access_token = access_token
        self.password = password
        self.room_id = room_id
        self.allowed_users = allowed_users
        self.store_path = store_path
        self.incoming_queue = incoming_queue
        self.outgoing_queue = outgoing_queue
        self._transcriber = transcriber
        self._start_timestamp = start_timestamp
        self._stop_event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: Any = None

    async def start(self) -> None:
        """Start the Matrix client, join the room, and run sync + response loops."""
        import nio

        os.makedirs(self.store_path, exist_ok=True)

        self._client = nio.AsyncClient(
            self.homeserver,
            self.user_id,
            store_path=self.store_path,
        )

        if self.access_token:
            log.debug("Authenticating with access token")
            self._client.access_token = self.access_token
            self._client.user_id = self.user_id
            self._client.device_id = self._client.device_id or "JARVIS"
        elif self.password:
            log.debug("Logging in with password for %s", self.user_id)
            resp = await self._client.login(password=self.password, device_name="JARVIS")
            if isinstance(resp, nio.LoginError):
                raise MatrixChatError(f"Matrix login failed: {resp.message}")
            log.info("Logged in as %s (device %s)", resp.user_id, resp.device_id)
            self.access_token = resp.access_token
        else:
            raise MatrixChatError("No access_token or password provided")

        self._client.add_event_callback(self._on_message, nio.RoomMessageText)

        if self._transcriber is not None:
            self._client.add_event_callback(self._on_audio_message, nio.RoomMessageAudio)

        # Join room (idempotent if already joined)
        try:
            resp = await self._client.join(self.room_id)
            if isinstance(resp, nio.JoinError):
                log.error("Failed to join room %s: %s", self.room_id, resp.message)
            else:
                log.info("Joined room %s", self.room_id)
        except Exception as e:
            log.error("Error joining room %s: %s", self.room_id, e)

        try:
            await asyncio.gather(
                self._sync_loop(),
                self._response_sender(),
            )
        finally:
            await self._client.close()

    async def _sync_loop(self) -> None:
        """Run the Matrix sync loop indefinitely."""
        import nio

        # Initial sync to get current state (marks backlog start point)
        try:
            log.debug("Starting initial sync...")
            resp = await self._client.sync(timeout=10000, full_state=True)
            if isinstance(resp, nio.SyncError):
                log.error("Initial sync failed: %s", resp.message)
            else:
                log.debug("Initial sync complete, next_batch=%s", resp.next_batch)
        except Exception as e:
            log.error("Initial sync error: %s", e)

        # Ongoing sync
        while not self._stop_event.is_set():
            try:
                resp = await self._client.sync(timeout=30000)
                if isinstance(resp, nio.SyncError):
                    log.warning("Sync error: %s", resp.message)
                    await asyncio.sleep(5)
                else:
                    rooms_with_events = [
                        r for r, data in resp.rooms.join.items() if data.timeline.events
                    ]
                    if rooms_with_events:
                        log.debug("Sync returned events in rooms: %s", rooms_with_events)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("Sync exception: %s", e)
                await asyncio.sleep(5)

    async def _on_message(self, room: Any, event: Any) -> None:
        """Handle incoming room messages."""
        # Only process messages from the configured room
        if room.room_id != self.room_id:
            log.debug(
                "Ignoring message from room %s (sender=%s, text=%s)",
                room.room_id,
                event.sender,
                event.body[:80] if hasattr(event, "body") else "<no body>",
            )
            return

        # Ignore own messages
        if event.sender == self.user_id:
            return

        # Ignore messages that predate this session
        if self._start_timestamp and event.server_timestamp < self._start_timestamp:
            log.debug(
                "Ignoring old message (ts=%d < %d)", event.server_timestamp, self._start_timestamp
            )
            return

        # Check sender whitelist
        if event.sender not in self.allowed_users:
            log.debug("Ignoring message from non-whitelisted user %s", event.sender)
            return

        msg = AssistantMessage(
            source=MessageSource.MATRIX,
            input_type=InputType.TEXT,
            content=event.body,
            room_id=room.room_id,
            sender=event.sender,
            event_id=event.event_id,
        )
        log.info("Chat message from %s: %s", msg.sender, str(msg.content)[:80])
        self.incoming_queue.put(msg)

    async def _send_text(self, room_id: str, text: str) -> None:
        """Send a text message directly to a Matrix room.

        Args:
            room_id: The room to send to.
            text: The message text.
        """
        import nio

        content = {
            "msgtype": "m.text",
            "body": text,
            "format": "org.matrix.custom.html",
            "formatted_body": text,
        }
        try:
            resp = await self._client.room_send(
                room_id,
                message_type="m.room.message",
                content=content,
            )
            if isinstance(resp, nio.RoomSendError):
                log.error("Failed to send message: %s", resp.message)
        except Exception as e:
            log.error("Error sending message: %s", e)

    async def _on_audio_message(self, room: Any, event: Any) -> None:
        """Handle incoming audio messages (voice notes)."""
        _MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB (Whisper API limit)

        if room.room_id != self.room_id:
            return

        if event.sender == self.user_id:
            return

        # Ignore messages that predate this session
        if self._start_timestamp and event.server_timestamp < self._start_timestamp:
            log.debug(
                "Ignoring old audio message (ts=%d < %d)",
                event.server_timestamp,
                self._start_timestamp,
            )
            return

        if event.sender not in self.allowed_users:
            log.debug("Ignoring audio from non-whitelisted user %s", event.sender)
            return

        # Check file size from event metadata
        try:
            file_size = event.source["content"]["info"]["size"]
        except (KeyError, TypeError):
            file_size = 0

        if file_size > _MAX_FILE_SIZE:
            log.warning("Audio from %s too large (%d bytes), rejecting", event.sender, file_size)
            await self._send_text(
                room.room_id,
                "Audio-Datei ist zu gross (max. 25 MB).",
            )
            return

        import nio

        # Download audio
        try:
            resp = await self._client.download(mxc=event.url)
            if isinstance(resp, nio.DownloadError):
                log.error("Audio download failed: %s", resp.message)
                await self._send_text(
                    room.room_id,
                    "Fehler beim Herunterladen der Audio-Datei.",
                )
                return
            audio_bytes = resp.body
        except Exception as e:
            log.error("Audio download exception: %s", e)
            await self._send_text(
                room.room_id,
                "Fehler beim Herunterladen der Audio-Datei.",
            )
            return

        # Determine filename from event body
        filename = getattr(event, "body", "audio.ogg") or "audio.ogg"

        # Transcribe
        try:
            text = await asyncio.to_thread(
                self._transcriber.transcribe_file, audio_bytes, filename
            )
        except (TranscriptionError, Exception) as e:
            log.error("Audio transcription failed: %s", e)
            await self._send_text(
                room.room_id,
                "Fehler bei der Transkription der Sprachnachricht.",
            )
            return

        text = self._transcriber.filter_transcript(text)

        if not text or not text.strip():
            await self._send_text(
                room.room_id,
                "Sprachnachricht konnte nicht transkribiert werden (kein Text erkannt).",
            )
            return

        # Send transcript as quote
        await self._send_text(room.room_id, f"> Transkript: {text}")

        # Create AssistantMessage and enqueue
        msg = AssistantMessage(
            source=MessageSource.MATRIX,
            input_type=InputType.TEXT,
            content=text,
            room_id=room.room_id,
            sender=event.sender,
            event_id=event.event_id,
        )
        log.info("Audio message from %s transcribed: %s", msg.sender, str(msg.content)[:80])
        self.incoming_queue.put(msg)

    async def _response_sender(self) -> None:
        """Poll the outgoing queue and send responses to the Matrix room."""
        import nio

        while not self._stop_event.is_set():
            try:
                room_id, text = self.outgoing_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.1)
                continue

            content = {
                "msgtype": "m.text",
                "body": text,
                "format": "org.matrix.custom.html",
                "formatted_body": text,
            }
            try:
                resp = await self._client.room_send(
                    room_id,
                    message_type="m.room.message",
                    content=content,
                )
                if isinstance(resp, nio.RoomSendError):
                    log.error("Failed to send message: %s", resp.message)
                else:
                    log.info("Sent response to room %s", room_id)
            except Exception as e:
                log.error("Error sending message: %s", e)

    def run_forever(self) -> None:
        """Blocking entry-point for the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self.start())
        except Exception as e:
            log.error("Matrix bridge crashed: %s", e)
        finally:
            self._loop.close()

    def request_stop(self) -> None:
        """Request the bridge to stop (thread-safe)."""
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop_event.set)


def start_matrix_thread(
    config: dict,
    incoming_queue: queue.Queue,
    outgoing_queue: queue.Queue,
    transcriber: Any = None,
    start_timestamp: int = 0,
) -> tuple[threading.Thread, MatrixBridge]:
    """Start the Matrix bridge in a background daemon thread.

    Args:
        config: The 'matrix' section of the application config.
        incoming_queue: Queue for messages from Matrix -> main thread.
        outgoing_queue: Queue for responses from main thread -> Matrix.
        transcriber: Optional WhisperTranscriber for audio message support.
        start_timestamp: Ignore Matrix events older than this (ms since epoch).

    Returns:
        Tuple of (thread, bridge) for lifecycle management.

    Raises:
        MatrixChatError: If required config fields are missing.
    """
    access_token = config.get("access_token") or os.environ.get("MATRIX_ACCESS_TOKEN", "")
    password = config.get("password") or os.environ.get("MATRIX_PASSWORD", "")
    if not access_token and not password:
        raise MatrixChatError(
            "Matrix: either access_token/MATRIX_ACCESS_TOKEN or "
            "password/MATRIX_PASSWORD must be provided"
        )

    bridge = MatrixBridge(
        homeserver=config["homeserver"],
        user_id=config["user_id"],
        room_id=config["room_id"],
        allowed_users=config.get("allowed_users", []),
        store_path=config.get("store_path", "~/.config/jarvis/matrix_store"),
        incoming_queue=incoming_queue,
        outgoing_queue=outgoing_queue,
        password=password,
        access_token=access_token,
        transcriber=transcriber,
        start_timestamp=start_timestamp,
    )

    thread = threading.Thread(target=bridge.run_forever, daemon=True, name="matrix-bridge")
    thread.start()
    log.info("Matrix bridge thread started")

    return thread, bridge

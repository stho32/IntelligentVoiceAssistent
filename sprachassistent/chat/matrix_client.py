"""Matrix chat bridge using matrix-nio.

Runs in a background thread with its own asyncio event loop.
Communicates with the main thread via thread-safe queues.
"""

import asyncio
import os
import queue
import threading
from typing import Any

from sprachassistent.chat.message import ChatMessage
from sprachassistent.exceptions import MatrixChatError
from sprachassistent.utils.logging import get_logger

log = get_logger("chat.matrix")


class MatrixBridge:
    """Async Matrix client that bridges messages to/from the main thread.

    Args:
        homeserver: Matrix homeserver URL (e.g. "https://matrix.org").
        user_id: Bot's Matrix user ID (e.g. "@jarvis:matrix.org").
        access_token: Access token for authentication.
        room_id: The Matrix room to operate in.
        allowed_users: List of Matrix user IDs allowed to interact with the bot.
        store_path: Path to store E2E encryption keys.
        incoming_queue: Queue for messages from Matrix -> main thread.
        outgoing_queue: Queue for responses from main thread -> Matrix.
    """

    def __init__(
        self,
        homeserver: str,
        user_id: str,
        access_token: str,
        room_id: str,
        allowed_users: list[str],
        store_path: str,
        incoming_queue: queue.Queue,
        outgoing_queue: queue.Queue,
    ):
        self.homeserver = homeserver
        self.user_id = user_id
        self.access_token = access_token
        self.room_id = room_id
        self.allowed_users = allowed_users
        self.store_path = store_path
        self.incoming_queue = incoming_queue
        self.outgoing_queue = outgoing_queue
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
        self._client.access_token = self.access_token
        self._client.user_id = self.user_id
        self._client.device_id = self._client.device_id or "JARVIS"

        self._client.add_event_callback(self._on_message, nio.RoomMessageText)

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
            resp = await self._client.sync(timeout=10000, full_state=True)
            if isinstance(resp, nio.SyncError):
                log.error("Initial sync failed: %s", resp.message)
        except Exception as e:
            log.error("Initial sync error: %s", e)

        # Ongoing sync
        while not self._stop_event.is_set():
            try:
                resp = await self._client.sync(timeout=30000)
                if isinstance(resp, nio.SyncError):
                    log.warning("Sync error: %s", resp.message)
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("Sync exception: %s", e)
                await asyncio.sleep(5)

    async def _on_message(self, room: Any, event: Any) -> None:
        """Handle incoming room messages."""
        # Only process messages from the configured room
        if room.room_id != self.room_id:
            log.debug("Ignoring message from room %s", room.room_id)
            return

        # Ignore own messages
        if event.sender == self.user_id:
            return

        # Check sender whitelist
        if event.sender not in self.allowed_users:
            log.debug("Ignoring message from non-whitelisted user %s", event.sender)
            return

        msg = ChatMessage(
            room_id=room.room_id,
            sender=event.sender,
            text=event.body,
            timestamp=event.server_timestamp,
            event_id=event.event_id,
        )
        log.info("Chat message from %s: %s", msg.sender, msg.text[:80])
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
) -> tuple[threading.Thread, MatrixBridge]:
    """Start the Matrix bridge in a background daemon thread.

    Args:
        config: The 'matrix' section of the application config.
        incoming_queue: Queue for messages from Matrix -> main thread.
        outgoing_queue: Queue for responses from main thread -> Matrix.

    Returns:
        Tuple of (thread, bridge) for lifecycle management.

    Raises:
        MatrixChatError: If required config fields are missing.
    """
    access_token = config.get("access_token") or os.environ.get("MATRIX_ACCESS_TOKEN", "")
    if not access_token:
        raise MatrixChatError("Matrix access_token not configured")

    bridge = MatrixBridge(
        homeserver=config["homeserver"],
        user_id=config["user_id"],
        access_token=access_token,
        room_id=config["room_id"],
        allowed_users=config.get("allowed_users", []),
        store_path=config.get("store_path", "~/.config/jarvis/matrix_store"),
        incoming_queue=incoming_queue,
        outgoing_queue=outgoing_queue,
    )

    thread = threading.Thread(target=bridge.run_forever, daemon=True, name="matrix-bridge")
    thread.start()
    log.info("Matrix bridge thread started")

    return thread, bridge
